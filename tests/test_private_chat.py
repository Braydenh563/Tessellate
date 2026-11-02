"""A private chat (INBOX 1481): "privat chat sessions might be good??"

The server half. A turn sent with `private: true` still answers from the
notes, and leaves nothing behind: no audit row (so no Ask again chip), no use
count on the notes it read, no Ask history, no conversation, nothing learned
read or written, no usage ledger entry. The page's half (the toggle, the
confirm, never calling `/conversations`) is in `test_private_chat_ui.py`.
"""

from __future__ import annotations

import json

import pytest

from tessellate.core import deps
from tessellate.core.database import AskTurn, AuditLog, Conversation, Entry, UserPreference
from tessellate.entry import manager


def _turn(client, question, **body):
    """One streamed turn; the events, in order."""
    events = []
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as r:
        for line in r.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    return events


def _answer(events):
    return "".join(e.get("delta", "") for e in events if e["type"] == "answer")


def _footprint(session):
    """Everything a turn could leave in the notebook, as numbers."""
    session.expire_all()
    return {
        "audit": session.query(AuditLog).count(),
        "asks": session.query(AskTurn).count(),
        "conversations": session.query(Conversation).count(),
        "preferences": session.query(UserPreference).count(),
        "uses": sum(e.access_count or 0 for e in session.query(Entry)),
    }


@pytest.fixture()
def beans(session):
    manager.create_entry(session, "The beans need netting next week")
    session.commit()
    return session


MODES = [
    {"notes_only": True},  # the Notes tab's Ask box
    {"use_tools": False},  # Chat, Ask the Librarian
    {"use_tools": True},  # Chat, Agent mode
]


def test_private_turns_leave_no_trace(ai_client, fake_ollama, beans):
    fake_ollama.librarian_reply = "You wrote about netting the beans."
    before = _footprint(beans)
    for n in range(4):
        for mode in MODES:
            events = _turn(ai_client, f"what did I write about beans {n}", private=True, **mode)
            assert "netting the beans" in _answer(events)

    assert _footprint(beans) == before
    assert ai_client.get("/chat/recent").json() == []
    assert ai_client.get("/ask-history").json()["total"] == 0


def test_the_same_turns_not_private_do_leave_one(ai_client, fake_ollama, beans):
    """The control: the footprint above is empty because of the flag."""
    fake_ollama.librarian_reply = "You wrote about netting the beans."
    before = _footprint(beans)
    _turn(ai_client, "what did I write about beans", use_tools=False)
    _turn(ai_client, "what did I write about beans", notes_only=True)
    after = _footprint(beans)

    assert after["audit"] > before["audit"]
    assert after["uses"] > before["uses"]
    assert after["asks"] == before["asks"] + 1
    assert "what did I write about beans" in ai_client.get("/chat/recent").json()


def test_a_private_turn_does_not_touch_the_usage_ledger(ai_client, fake_ollama, beans):
    path = deps.get_config().data_dir / "usage.json"
    before = path.read_text() if path.exists() else None
    _turn(ai_client, "what did I write about beans", private=True, use_tools=False)
    assert (path.read_text() if path.exists() else None) == before


def test_the_model_still_reads_the_notes(ai_client, fake_ollama, beans):
    fake_ollama.librarian_reply = "Netting."
    events = _turn(ai_client, "what did I write about beans", private=True, use_tools=False)

    meta = next(e for e in events if e["type"] == "meta")
    assert meta["raw_results"], "retrieval still ran"
    assert any("netting" in str(m).lower() for m in fake_ollama.chat_calls[-1])


def _taught(session, text="Always answer in rhyming couplets"):
    session.add(UserPreference(content=text, active=True, proposed=False))
    session.commit()


def _prompt(fake_ollama):
    rounds = fake_ollama.chat_calls or fake_ollama.tool_rounds
    return json.dumps(rounds[-1])


@pytest.mark.parametrize("mode", [{"use_tools": False}, {"use_tools": True}])
def test_what_the_ai_was_taught_is_not_read(ai_client, fake_ollama, beans, mode):
    _taught(beans)
    _turn(ai_client, "what did I write about beans", **mode)
    assert "rhyming couplets" in _prompt(fake_ollama), "the control: a normal turn reads it"

    fake_ollama.chat_calls.clear()
    fake_ollama.tool_rounds.clear()
    _turn(ai_client, "what did I write about beans", private=True, **mode)
    assert "rhyming couplets" not in _prompt(fake_ollama)


def test_the_ai_cannot_save_a_preference_in_a_private_chat(ai_client, fake_ollama, beans):
    fake_ollama.tool_script = [[{"name": "save_user_preference", "arguments": {"preference": "Call me Captain"}}]]
    fake_ollama.librarian_reply = "Noted."
    _turn(ai_client, "remember to call me Captain", private=True, use_tools=True)
    assert beans.query(UserPreference).count() == 0

    fake_ollama.tool_script = [[{"name": "save_user_preference", "arguments": {"preference": "Call me Captain"}}]]
    _turn(ai_client, "remember to call me Captain", use_tools=True)
    beans.expire_all()
    assert beans.query(UserPreference).count() == 1, "the control: a normal turn may"


def test_the_learned_stores_are_not_read(ai_client, fake_ollama, beans, monkeypatch):
    """The person's word on insights and on sentences shapes an answer only
    in a chat that is remembered."""
    from tessellate.ai import insights, verdicts

    seen = []
    monkeypatch.setattr(insights, "memory", lambda s: seen.append("insights") or None)
    monkeypatch.setattr(verdicts, "known", lambda s: seen.append("verdicts") or None)
    fake_ollama.running = False  # the app composes the answer itself: the path that reads them

    _turn(ai_client, "what did I write about beans", private=True)
    assert seen == []

    _turn(ai_client, "what did I write about beans")
    assert seen, "the control: a normal turn reads them"


def test_the_ledger_names_the_run_without_the_question(ai_client, fake_ollama, beans):
    from tessellate.api import routes_chat

    class _Req:
        class body:  # noqa: N801
            question = "my secret question"
            private = True
            skill = None

        skill = None
        use_tools = True

    from tessellate.core import private_turn

    with private_turn.scope(True):
        assert routes_chat._run_title(_Req) == "Private chat"
    assert "my secret question" in routes_chat._run_title(_Req)
