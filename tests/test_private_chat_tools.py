"""A private chat keeps nothing, whichever path the turn takes (INBOX 1481).

`test_private_chat.py` covers the plain turn. A reviewer then found four paths
that each forgot the flag: a skill or plan run, a tool call's audit row, the
process ledger and the log naming a tool's arguments, and the rows cache. The
fix is one fact, "this turn is private" (`core/private_turn.py`), read at every
durable write, so these tests drive each path and count what is left: audit
rows, preferences, log records and ledger lines that carry the question or a
tool's arguments. Each has a control without the flag that still writes.
"""

from __future__ import annotations

import json
import logging

import pytest

from tessellate.ai import skills
from tessellate.core import deps, jobruns
from tessellate.core.database import AuditLog, UserPreference
from tessellate.entry import manager

QUESTION = "zebra quokka marmalade question about beans"
ARGUMENT = "xylophone gazebo argument"


def _turn(client, question, **body):
    events = []
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as r:
        for line in r.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    return events


def _tool(name, **arguments):
    return [{"name": name, "arguments": arguments}]


@pytest.fixture()
def beans(session):
    manager.create_entry(session, "The beans need netting next week")
    session.commit()
    return session


@pytest.fixture()
def web(app_state, monkeypatch):
    """Web search on, against a fake transport that answers one hit."""
    from tessellate.search import websearch

    app_state.set_preference("web_search_enabled", True)
    hit = {"title": "Beans", "url": "https://example.org/beans", "snippet": "Netting.", "domain": "example.org", "engine": "fake"}
    monkeypatch.setattr(websearch, "search_web", lambda query, **kw: [hit])
    return hit


def _save_skill(name="Bean check", prompt=f"Check the beans. {QUESTION}"):
    config = deps.get_config()
    config.set_preference("skills", [*skills.stored(config), {"name": name, "prompt": prompt}])
    return name


def _ledger_text():
    rows = [*jobruns.finished(), *jobruns.live()]
    return json.dumps(rows, default=str)


def _kept(session, caplog):
    """What is left behind, as words and numbers."""
    session.expire_all()
    return {
        "audit": session.query(AuditLog).count(),
        "preferences": session.query(UserPreference).count(),
        "log": "\n".join(r.getMessage() for r in caplog.records),
        "ledger": _ledger_text(),
    }


def _assert_silent(kept, before, *markers):
    assert kept["audit"] == before["audit"], "an audit row was written"
    assert kept["preferences"] == before["preferences"]
    for marker in markers:
        assert marker not in kept["log"], f"the log carries {marker!r}"
        assert marker not in kept["ledger"], f"the ledger carries {marker!r}"


@pytest.fixture()
def before(beans, caplog):
    caplog.set_level(logging.DEBUG)
    jobruns.clear_finished()
    caplog.clear()
    return _kept(beans, caplog)


def _agent_script(fake, *calls):
    fake.tool_script = [list(c) for c in calls]
    fake.librarian_reply = "You wrote about netting."


# --- an agent turn calling a read-only tool ---------------------------------


@pytest.mark.parametrize(
    "call",
    [_tool("search_notes", query=ARGUMENT), _tool("web_search", query=ARGUMENT)],
    ids=["search_notes", "web_search"],
)
def test_a_private_tool_call_leaves_no_audit_row_no_log_no_ledger_line(ai_client, fake_ollama, web, beans, caplog, before, call):
    _agent_script(fake_ollama, call)
    events = _turn(ai_client, QUESTION, private=True, use_tools=True)

    assert any(e["type"] == "tool" for e in events), "the tool ran"
    _assert_silent(_kept(beans, caplog), before, ARGUMENT, QUESTION)


@pytest.mark.parametrize(
    "call",
    [_tool("search_notes", query=ARGUMENT), _tool("web_search", query=ARGUMENT)],
    ids=["search_notes", "web_search"],
)
def test_the_same_tool_call_not_private_is_recorded(ai_client, fake_ollama, web, beans, caplog, before, call):
    """The control: the silence above is the flag's."""
    _agent_script(fake_ollama, call)
    _turn(ai_client, QUESTION, use_tools=True)
    kept = _kept(beans, caplog)

    assert kept["audit"] > before["audit"]
    assert ARGUMENT in beans.query(AuditLog).filter(AuditLog.action == "ai_tool").one().detail
    assert ARGUMENT in kept["ledger"], "the process ledger names what was asked"


def test_a_private_tool_failure_names_no_arguments(ai_client, fake_ollama, beans, caplog, before):
    """A refused or failed call's error can quote its arguments."""
    _agent_script(fake_ollama, _tool("get_note", note_id=987654321, label=ARGUMENT))
    _turn(ai_client, QUESTION, private=True, use_tools=True)
    _assert_silent(_kept(beans, caplog), before, ARGUMENT, QUESTION)


# --- regenerate -------------------------------------------------------------


def test_a_regenerated_private_answer_leaves_nothing(ai_client, fake_ollama, beans, caplog, before):
    fake_ollama.librarian_reply = "You wrote about netting the beans."
    for attempt in range(3):
        for mode in ({"notes_only": True}, {"use_tools": False}, {"use_tools": True}):
            _turn(ai_client, QUESTION, private=True, attempt=attempt, **mode)
    _assert_silent(_kept(beans, caplog), before, QUESTION)


def test_a_private_question_does_not_enter_the_rows_cache(ai_client, fake_ollama, beans):
    from tessellate.api import routes_chat

    routes_chat._ROWS_KEPT.clear()
    fake_ollama.running = False  # the composed path is the one that remembers rows
    _turn(ai_client, "what did I write about beans", private=True)
    assert not routes_chat._ROWS_KEPT


def test_the_rows_cache_refuses_a_write_while_the_turn_is_private():
    import datetime

    from tessellate.api import routes_chat
    from tessellate.core import private_turn

    routes_chat._ROWS_KEPT.clear()
    today = datetime.date(2026, 1, 1)
    with private_turn.scope(True):
        routes_chat._remember_rows("q", [], today, {"grounding": [{"note_id": 1}]})
    assert not routes_chat._ROWS_KEPT
    routes_chat._remember_rows("q", [], today, {"grounding": [{"note_id": 1}]})
    assert routes_chat._ROWS_KEPT, "the control: a kept turn remembers"
    routes_chat._ROWS_KEPT.clear()


# --- a skill run ------------------------------------------------------------


def test_a_private_skill_run_leaves_nothing_and_cannot_teach(ai_client, fake_ollama, beans, caplog, before):
    name = _save_skill()
    _agent_script(
        fake_ollama,
        _tool("search_notes", query=ARGUMENT),
        _tool("save_user_preference", preference="Call me Captain"),
    )
    events = _turn(ai_client, "Run it", skill=name, private=True, use_tools=True)

    assert any(e["type"] == "tool" for e in events)
    _assert_silent(_kept(beans, caplog), before, ARGUMENT, QUESTION, "Captain")


def test_the_same_skill_run_not_private_is_recorded(ai_client, fake_ollama, beans, caplog, before):
    name = _save_skill()
    _agent_script(fake_ollama, _tool("search_notes", query=ARGUMENT), _tool("save_user_preference", preference="Call me Captain"))
    _turn(ai_client, "Run it", skill=name, use_tools=True)
    beans.expire_all()

    assert beans.query(AuditLog).filter(AuditLog.entity_type == "skill").count() == 1, "the 'ran skill' row"
    assert beans.query(UserPreference).count() == 1


def test_a_skill_run_reads_nothing_it_was_taught(ai_client, fake_ollama, beans):
    beans.add(UserPreference(content="Always answer in rhyming couplets", active=True, proposed=False))
    beans.commit()
    name = _save_skill()
    _agent_script(fake_ollama, _tool("search_notes", query="beans"))
    _turn(ai_client, "Run it", skill=name, private=True, use_tools=True)
    rounds = fake_ollama.tool_rounds or fake_ollama.chat_calls
    assert "rhyming couplets" not in json.dumps(rounds)


# --- a plan run -------------------------------------------------------------


def test_a_private_plan_run_leaves_nothing(ai_client, fake_ollama, beans, caplog, before):
    _agent_script(
        fake_ollama,
        _tool("search_notes", query=ARGUMENT),
        _tool("save_user_preference", preference="Call me Captain"),
    )
    events = _turn(
        ai_client,
        "ph:compass Check the beans",
        plan={"goal": "Check the beans", "steps": [f"Look for {QUESTION}", "Report"]},
        private=True,
        use_tools=True,
    )

    assert any(e["type"] == "step" for e in events)
    _assert_silent(_kept(beans, caplog), before, ARGUMENT, QUESTION, "Captain")


def test_the_same_plan_run_not_private_is_recorded(ai_client, fake_ollama, beans, caplog, before):
    _agent_script(fake_ollama, _tool("search_notes", query=ARGUMENT))
    _turn(
        ai_client,
        "ph:compass Check the beans",
        plan={"goal": "Check the beans", "steps": ["Look", "Report"]},
        use_tools=True,
    )
    beans.expire_all()
    assert beans.query(AuditLog).filter(AuditLog.entity_type == "skill").count() == 1


# --- the non-streaming route, and the follow-up chips -----------------------


def test_a_private_chat_post_leaves_nothing(ai_client, fake_ollama, beans, caplog, before):
    fake_ollama.librarian_reply = "Netting."
    r = ai_client.post("/chat", json={"question": QUESTION, "private": True})
    assert r.status_code == 200
    _assert_silent(_kept(beans, caplog), before, QUESTION)


def test_the_followup_chips_keep_nothing(ai_client, fake_ollama, beans, caplog, before):
    fake_ollama.librarian_reply = "What else did I note about beans?"
    r = ai_client.post("/chat/followups", json={"question": QUESTION, "answer": "You wrote about netting."})
    assert r.status_code == 200
    _assert_silent(_kept(beans, caplog), before, QUESTION)


# --- the one switch ---------------------------------------------------------


def test_an_audit_event_is_refused_inside_a_private_scope_only(beans):
    from tessellate.core import private_turn

    start = beans.query(AuditLog).count()
    with private_turn.scope(True):
        manager.log_action(beans, "ai_tool", "chat", detail="web_search {}")
        manager.log_action(beans, "ran", "skill", None, "Bean check")
        manager.log_action(beans, "queried", "ask", detail=QUESTION)
    beans.flush()
    assert beans.query(AuditLog).count() == start

    manager.log_action(beans, "ai_tool", "chat", detail="web_search {}")
    beans.flush()
    assert beans.query(AuditLog).count() == start + 1


def test_a_data_change_is_still_recorded_in_a_private_scope(beans):
    """Undo and history need a note the assistant wrote, private chat or not."""
    from tessellate.core import private_turn

    start = beans.query(AuditLog).count()
    with private_turn.scope(True):
        manager.create_entry(beans, "A note the assistant was asked to write")
    beans.flush()
    assert beans.query(AuditLog).count() > start


def test_scope_nests_and_never_clears_an_outer_private():
    from tessellate.core import private_turn

    assert not private_turn.active()
    with private_turn.scope(True):
        with private_turn.scope(False):
            assert private_turn.active()
    assert not private_turn.active()


def test_a_stepped_generator_is_private_on_every_step():
    """A streamed turn is advanced step by step, each in a copy of the
    context, so a flag set once inside it would be lost after the first."""
    from tessellate.core import private_turn

    seen = []

    def lines():
        for _ in range(3):
            seen.append(private_turn.active())
            yield "x"

    assert list(private_turn.stepped(lines(), True)) == ["x"] * 3
    assert seen == [True, True, True]
    assert not private_turn.active()
