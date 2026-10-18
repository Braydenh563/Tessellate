"""The reminders path gives way to the notes' own days (CHAT_PLAN Phase 6 P13).

Measured 2026-10-18 on the running app, no model: "what is due this week" in
Ask said "You have no reminders waiting." over three notes that name days, so
the computed answer (`ai/composer_lists.py`) never showed. With nothing
waiting in Reminders and days in the notes, the notes answer; a reminder that
is waiting still wins, and a notebook with no days still says there is nothing.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from tessellate.entry import manager

SUNDAY = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)


def _ask(client, question: str) -> str:
    text = ""
    with client.stream("POST", "/chat/stream", json={"question": question, "notes_only": True, "use_tools": False}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event["type"] == "answer":
                    text += event.get("delta", "")
    return text


@pytest.fixture()
def clock(monkeypatch):
    from tessellate.api import routes_chat

    monkeypatch.setattr(routes_chat, "user_now", lambda cfg: SUNDAY)


@pytest.fixture()
def dated_notebook(session, clock):
    for content, category, tags in (
        ("Work notes: standup moved to 10am. Send the invoice by 16 October 2026.", "Work", ["work"]),
        ("Boiler service on 20 October 2026.", "Home", ["home"]),
        ("Dentist appointment on 3 November 2026 at 9am.", "Health", ["dentist"]),
    ):
        entry = manager.create_entry(session, content, category, tags)
        entry.created_at = datetime(2026, 10, 1, 10, 0)
    session.commit()


def test_due_this_week_is_the_notes_own_days_not_an_empty_reminder_list(client, dated_notebook):
    text = _ask(client, "what is due this week")
    assert "no reminders" not in text.lower(), text
    assert "16 October" in text and "invoice" in text.lower(), text
    assert "20 October" not in text, text


def test_due_tomorrow_names_the_next_day_in_the_notes(client, dated_notebook):
    text = _ask(client, "what is due tomorrow")
    assert text.startswith("Nothing in your notes falls tomorrow."), text
    assert "16 October" in text, text


def test_a_notebook_with_no_days_still_says_no_reminders(client, session, clock):
    manager.create_entry(session, "Gym: squats 80 kg for 5.", "Fitness", ["gym"])
    session.commit()
    assert "no reminders waiting" in _ask(client, "what is due this week").lower()


def test_a_reminder_that_is_waiting_still_wins(client, dated_notebook):
    created = client.post("/reminders", json={"text": "Call the plumber", "due_at": "2030-01-01T09:00:00"})
    assert created.status_code in (200, 201), created.text
    text = _ask(client, "what is due this week")
    assert "plumber" in text, text
