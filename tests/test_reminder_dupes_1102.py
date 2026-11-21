"""Audit 1028 E29: the same reminder (same words, same time) made twice was
never warned about and then listed twice in "what is due". It is said to exist
at creation, by the chat act and by the tool, and listed once."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import commands, composer_plan, composer_study, tools
from tessellate.core.database import Reminder

NOW = datetime(2026, 11, 2, 9, 0)


def _count(session) -> int:
    return session.query(Reminder).count()


@pytest.mark.parametrize("second", ["water the plants", "Water the plants", "  water   the plants "])
def test_the_tool_does_not_make_the_same_reminder_twice(ai_client, session, second):
    first = tools.execute_tool(session, "set_reminder", {"text": "water the plants", "due_at": "2030-01-02T09:00"})
    again = tools.execute_tool(session, "set_reminder", {"text": second, "due_at": "2030-01-02T09:00"})
    assert again["id"] == first["id"] and again.get("existing") is True
    assert _count(session) == 1


def test_another_time_or_other_words_is_another_reminder(ai_client, session):
    tools.execute_tool(session, "set_reminder", {"text": "water the plants", "due_at": "2030-01-02T09:00"})
    tools.execute_tool(session, "set_reminder", {"text": "water the plants", "due_at": "2030-01-03T09:00"})
    tools.execute_tool(session, "set_reminder", {"text": "feed the cat", "due_at": "2030-01-02T09:00"})
    assert _count(session) == 3


def test_a_done_reminder_does_not_block_a_new_one(ai_client, session):
    first = tools.execute_tool(session, "set_reminder", {"text": "water the plants", "due_at": "2030-01-02T09:00"})
    tools.execute_tool(session, "complete_reminder", {"reminder_id": first["id"]})
    tools.execute_tool(session, "set_reminder", {"text": "water the plants", "due_at": "2030-01-02T09:00"})
    assert _count(session) == 2


@pytest.mark.parametrize(
    "ask",
    [
        "remind me tomorrow at 9am to call the dentist",
        "remind me to call the dentist tomorrow at 9am",
        "set a reminder to call the dentist tomorrow at 9am",
    ],
)
def test_the_chat_act_says_it_already_exists_for_the_same_text_and_time(session, monkeypatch, ask):
    from tessellate.core import config

    monkeypatch.setattr(config, "user_now", lambda cfg: NOW)
    parsed = commands.parse(ask, NOW)
    assert parsed is not None and parsed.args["intent"] == "reminder", ask
    session.add(Reminder(text=parsed.args["text"], due_at=parsed.args["due_at"]))
    session.commit()
    planned = commands.plan(session, parsed.args)
    assert "already" in planned["line"].lower() and "card" not in planned, planned
    assert "Add another" not in planned["line"]


def test_the_chat_act_still_asks_for_the_same_words_at_another_time(session, monkeypatch):
    from tessellate.core import config

    monkeypatch.setattr(config, "user_now", lambda cfg: NOW)
    parsed = commands.parse("remind me tomorrow at 9am to call the dentist", NOW)
    session.add(Reminder(text=parsed.args["text"], due_at=datetime(2026, 11, 5, 9, 0)))
    session.commit()
    planned = commands.plan(session, parsed.args)
    assert "Add another" in planned["line"] and "card" in planned


@pytest.mark.parametrize("question", ["what is due this week", "what's due this week", "anything due this week?"])
def test_a_due_list_shows_identical_reminders_once(question):
    due = datetime(2026, 11, 4, 9, 0)
    rows = [
        {"text": "Call the dentist", "due_at": due, "done": False},
        {"text": "call the dentist ", "due_at": due, "done": False},
        {"text": "Call the dentist", "due_at": datetime(2026, 11, 5, 9, 0), "done": False},
    ]
    ctx = composer_study.Ctx(question=question, notes=[], now=NOW, reminders=rows)
    said = composer_plan.answer(ctx)
    assert said is not None
    assert said.text.lower().count("call the dentist") == 2, said.text
    assert "two dated items" in said.text, said.text
