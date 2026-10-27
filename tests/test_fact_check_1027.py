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
from tessellate.core.database import Reminder

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
