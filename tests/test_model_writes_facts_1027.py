"""With a model up, the model writes every answer and the engine only hands it
facts (CHAT_PLAN decision 75; the owner, 2026-10-27: "why is it responding as
the composer when my ai is in use?? I want the ai to be able to do what the
composer can do but better"). "What is due?" in the popup agent was answered
by the composer's reminder list with the model running: no "Asked <model>"
line, the no-model badge.

The engine's exact answer (the due list, a count, a worked sum) goes into the
model's prompt as facts; its structured parts (the list, the chart, the
panel) still ride under the reply; prose that states a number the facts do
not hold is refused and the engine's own words stand. With no model the
engine answers as before.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core.database import Entry, Reminder

#: A fixed clock (CLAUDE.md section 8), Tuesday 27 October 2026, 9:30.
NOW = datetime(2026, 10, 27, 9, 30)
DUE = (("call mum", datetime(2026, 10, 28, 9, 0)), ("pay rent", datetime(2026, 10, 29, 10, 0)), ("book dentist", datetime(2026, 10, 30, 11, 0)))


@pytest.fixture()
def fixed_clock(monkeypatch):
    monkeypatch.setattr(routes_chat, "user_now", lambda _config=None: NOW)


def _seed(session, reminders: bool = True) -> None:
    for text in ("Boiler pressure is low", "Gym plan for the week", "Sourdough starter feeding"):
        session.add(Entry(content=text))
    if reminders:
        for text, due in DUE:
            session.add(Reminder(text=text, due_at=due))
    session.commit()


def _stream(client, question: str, use_tools: bool) -> tuple[list, str]:
    events = []
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": use_tools}) as response:
        for line in response.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    return events, "".join(e.get("delta", "") for e in events if e["type"] == "answer")


def _last_meta(events: list) -> dict:
    return [e for e in events if e["type"] == "meta"][-1]


def _prompt(fake) -> str:
    return "\n".join(str(m.get("content") or "") for m in fake.chat_calls[-1])


#: Chat's Ask mode (no tools) and the popup agent (`palette.js` streams
#: `/chat/stream` with `useTools: true`): one route, both surfaces.
SURFACES = pytest.mark.parametrize("use_tools", [False, True], ids=["chat", "popup-agent"])


@SURFACES
def test_what_is_due_is_written_by_the_model_from_the_due_rows(ai_client, fake_ollama, session, fixed_clock, use_tools):
    _seed(session)
    fake_ollama.librarian_reply = "Three things are waiting, and call mum comes first."
    events, answer = _stream(ai_client, "What is due?", use_tools)
    assert fake_ollama.chat_calls, "the model was never asked"
    prompt = _prompt(fake_ollama)
    for text, _due in DUE:
        assert text in prompt, (text, prompt)
    assert answer.startswith(fake_ollama.librarian_reply), answer
    #: The list rides under the reply as the engine drew it: the model wrote
    #: the words, not the table.
    for text, _due in DUE:
        assert text in answer.split(fake_ollama.librarian_reply, 1)[1], answer
    meta = _last_meta(events)
    assert meta["answered_by"] and meta["composed"] is False
    assert any(e["type"] == "stats" and e.get("model") for e in events)


@SURFACES
def test_how_many_notes_is_written_by_the_model_with_the_count(ai_client, fake_ollama, session, fixed_clock, use_tools):
    _seed(session, reminders=False)
    fake_ollama.librarian_reply = "Your notebook holds 3 notes so far."
    events, answer = _stream(ai_client, "How many notes do I have?", use_tools)
    assert fake_ollama.chat_calls, "the model was never asked"
    assert "3 notes" in _prompt(fake_ollama)
    assert fake_ollama.librarian_reply in answer
    assert _last_meta(events)["answered_by"]


@SURFACES
def test_a_worked_sum_is_written_by_the_model_with_the_result(ai_client, fake_ollama, session, fixed_clock, use_tools):
    fake_ollama.librarian_reply = "That comes to 84."
    events, answer = _stream(ai_client, "what is 12 * 7", use_tools)
    assert "84" in _prompt(fake_ollama)
    assert answer == "That comes to 84."
    assert _last_meta(events)["answered_by"]
    #: The worked answer's calculator still rides under it (INBOX 1300 C06).
    assert [e["panel"] for e in events if e["type"] == "panel"] == ["calculator"]


@SURFACES
def test_prose_that_contradicts_the_facts_is_refused(ai_client, fake_ollama, session, fixed_clock, use_tools):
    """A 1.5B model said "two reminders" when there were three (2026-10-12,
    `test_reminders_with_model.py`): the engine's own words stand instead,
    and no model is named under them."""
    _seed(session)
    fake_ollama.librarian_reply = "You have two reminders."
    events, answer = _stream(ai_client, "What is due?", use_tools)
    assert fake_ollama.chat_calls
    assert "two reminders" not in answer
    for text, _due in DUE:
        assert text in answer
    assert _last_meta(events)["answered_by"] is None
    assert not any(e["type"] == "stats" and e.get("model") for e in events)


def test_a_count_that_drops_the_figure_is_refused(ai_client, fake_ollama, session, fixed_clock):
    _seed(session, reminders=False)
    fake_ollama.librarian_reply = "You have a lovely notebook."
    events, answer = _stream(ai_client, "How many notes do I have?", False)
    assert "lovely" not in answer and "3" in answer
    assert _last_meta(events)["answered_by"] is None


@pytest.mark.parametrize("question", ["What is due?", "How many notes do I have?", "what is 12 * 7"])
@SURFACES
def test_with_no_model_the_engine_still_answers(client, session, fixed_clock, question, use_tools):
    _seed(session)
    events, answer = _stream(client, question, use_tools)
    assert answer.strip()
    assert _last_meta(events)["answered_by"] is None
    if question == "What is due?":
        for text, _due in DUE:
            assert text in answer
    elif question.startswith("How many"):
        assert "3 notes" in answer
    else:
        assert "84" in answer


@pytest.mark.parametrize(
    ("prose", "ok"),
    [
        ("Three things are waiting; call mum is first.", True),
        ("You have 3 reminders, the first on 28 October at 9:00.", True),
        ("You have two reminders.", False),
        ("You have 4 reminders.", False),
    ],
)
def test_the_fact_check(fixed_clock, monkeypatch, prose: str, ok: bool) -> None:
    monkeypatch.setattr(routes_chat.deps, "get_config", lambda: None)
    facts = "You have 3 reminders waiting.\n\n| call mum | Wed 28 Oct, 9:00 |\n| pay rent | Thu 29 Oct, 10:00 |\n| book dentist | Fri 30 Oct, 11:00 |"
    assert routes_chat._prose_keeps_facts(prose, facts, "What is due?", needs_figure=False) is ok


def test_the_facts_prompt_is_budgeted() -> None:
    """Prompt text is budgeted (CLAUDE.md section 7): the brief is one short
    paragraph, and the facts are cut to a fixed size however long the list."""
    from tessellate.ai import librarian

    assert len(librarian.FACTS_BRIEF) <= 400
    messages = librarian.build_facts_messages("What is due?", "row\n" * 5000)
    assert len(messages[-1]["content"]) <= librarian.FACTS_MAX_CHARS + 300


def test_the_guide_says_who_writes_a_counted_answer() -> None:
    """Help moves with the behaviour (standing order 13)."""
    from tessellate.ai import help_chat

    topics = {t["id"]: t["body"] for t in help_chat.HELP_TOPICS}
    assert "says the counted answer in its own words" in topics["notebook-questions"]
