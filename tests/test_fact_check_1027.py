"""The check on a model's words in a facts turn (`ai/fact_check.py`,
`routes_chat._fact_events`), from the second review of 2026-10-27: each case
here was a miscount the check kept, or a right answer it refused, measured
through `/chat/stream` with a fake model and a fixed clock.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core.database import Entry, Reminder

#: A fixed clock (CLAUDE.md section 8), Tuesday 27 October 2026, 9:30.
NOW = datetime(2026, 10, 27, 9, 30)


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch):
    monkeypatch.setattr(routes_chat, "user_now", lambda _config=None: NOW)


def _seed(session, last=datetime(2026, 11, 20, 11)) -> None:
    """Three reminders: two this week, the third `last`."""
    for text, due in (("call mum", datetime(2026, 10, 28, 9)), ("pay rent", datetime(2026, 10, 29, 10)), ("book dentist", last)):
        session.add(Reminder(text=text, due_at=due))
    session.commit()


def _kept(client, fake, question: str, prose: str, use_tools: bool = False) -> bool:
    """Whether the model's words were kept: they lead the answer and the
    latest `meta` names the model."""
    fake.librarian_reply = prose
    events = []
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": use_tools}) as response:
        for line in response.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    assert fake.chat_calls, "the model was never asked"
    answer = "".join(e.get("delta", "") for e in events if e["type"] == "answer")
    meta = [e for e in events if e["type"] == "meta"][-1]
    return answer.startswith(prose) and bool(meta["answered_by"])


SURFACES = pytest.mark.parametrize("use_tools", [False, True], ids=["chat", "popup-agent"])


@SURFACES
@pytest.mark.parametrize(
    ("question", "prose", "ok"),
    [
        ("what reminders do I have this week", "You have 3 reminders this week.", False),
        ("what reminders do I have this week", "You have 2 reminders this week.", True),
        ("what reminders do I have today", "You have 3 reminders today.", False),
        ("what reminders do I have today", "You have no reminders today.", True),
    ],
)
def test_a_windowed_list_is_checked_against_the_window(ai_client, fake_ollama, session, question, prose, ok, use_tools):
    """The counts were the whole list's (3) while the engine said the week's (2)."""
    _seed(session)
    assert _kept(ai_client, fake_ollama, question, prose, use_tools) is ok


@pytest.mark.parametrize(
    ("question", "prose", "ok"),
    [
        ("how many minutes in 2 hours", "That is 130 minutes.", False),
        ("how many minutes in 2 hours", "That is 120 minutes.", True),
        ("how many minutes in 2 hours", "That is 2 hours.", False),
        ("how many days until christmas", "There are 90 days until Christmas.", False),
        ("how many days until christmas", "There are 59 days until Christmas.", True),
        ("how many days until christmas", "Christmas is about 8 weeks away.", True),
        ("convert 3 hours to minutes", "That's 200 minutes.", False),
        ("convert 3 hours to minutes", "That's 180 minutes.", True),
        ("how many weeks until 1 january", "That is 20 weeks.", False),
        ("how many weeks until 1 january", "That is about 9 weeks.", True),
        ("how many seconds in a day", "A day is 86,400 seconds.", True),
        ("how many seconds in a day", "A day is 86,000 seconds.", False),
    ],
)
def test_a_span_the_engine_computed_is_checked(ai_client, fake_ollama, session, question, prose, ok):
    """A figure before a time unit was never read, so any span stood."""
    _seed(session)
    assert _kept(ai_client, fake_ollama, question, prose) is ok


@SURFACES
def test_a_span_the_engine_did_not_compute_is_the_models(ai_client, fake_ollama, session, use_tools):
    """Under a list of dated reminders, "in 2 days" is the model's reading."""
    _seed(session)
    assert _kept(ai_client, fake_ollama, "what reminders do I have", "You have 3 reminders; pay rent is in 2 days.", use_tools)


@SURFACES
@pytest.mark.parametrize(
    ("prose", "ok"),
    [
        ("Only one is waiting.", False),
        ("One is due soon.", False),
        ("You have 3 reminders. One of them, call mum, is due tomorrow.", True),
        ("You have 3 reminders; the first one is call mum.", True),
    ],
)
def test_a_bare_one_counts_unless_it_points(ai_client, fake_ollama, session, prose, ok, use_tools):
    """A bare "one" always stood, so "Only one is waiting" passed with 3."""
    _seed(session)
    assert _kept(ai_client, fake_ollama, "what reminders do I have", prose, use_tools) is ok


@SURFACES
@pytest.mark.parametrize(
    ("prose", "ok"),
    [
        ("You have a couple of reminders.", False),
        ("You have a dozen reminders.", False),
        ("You have a hundred reminders.", False),
        ("You have two dozen reminders.", False),
        ("You have three reminders.", True),
    ],
)
def test_an_amount_said_in_words_is_a_figure(ai_client, fake_ollama, session, prose, ok, use_tools):
    """"a couple of", "a dozen" and "a hundred" passed with 3."""
    _seed(session)
    assert _kept(ai_client, fake_ollama, "what reminders do I have", prose, use_tools) is ok


@SURFACES
@pytest.mark.parametrize(
    "prose",
    [
        "Call mum is due October 28, 2026; you have 3 reminders.",
        "You have 3 reminders; pay rent is due Thursday by 10.",
        "You have 3 reminders; call mum is due by 9.30 tomorrow.",
        "Call mum is due 2026-10-28; you have 3 reminders.",
    ],
)
def test_a_year_a_time_and_an_iso_date_are_no_figures(ai_client, fake_ollama, session, prose, use_tools):
    """Each was refused for a figure that counts nothing."""
    _seed(session)
    assert _kept(ai_client, fake_ollama, "what reminders do I have", prose, use_tools)


@pytest.mark.parametrize(("notes", "prose", "ok"), [(1, "You have a single note.", True), (2, "You have a single note.", False)])
def test_a_single_note_is_one(ai_client, fake_ollama, session, notes, prose, ok):
    for n in range(notes):
        session.add(Entry(content=f"Gym plan {n}"))
    session.commit()
    assert _kept(ai_client, fake_ollama, "how many notes do I have", prose) is ok
