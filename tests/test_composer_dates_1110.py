"""F3 f and g of the 1110 composer audit, no model, clock fixed at Tuesday 10 November 2026, 09:00.

- f: "remind me the day before", "and a week before that" count from the date the answer before showed.
- g: "move it to the 16th" after a reminder moves the reminder, never a category called "the 16th"."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.ai import follow_items
from tessellate.ai import recognise_questions
from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.entry import manager
from tests._consent import confirmed

NOW = datetime(2026, 11, 10, 9, 0)
SET = [{"question": "remind me to renew passport on 30 November at 9am", "answer": "Got it, I will remind you on 30 November at 9: renew passport."}]
FACT = [{"question": "when is the dentist check-up", "answer": "Check-up 21 November, from your Dentist note, written today."}]


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)


def _events(client, question, **body):
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        return [json.loads(line) for line in response.iter_lines() if line.strip()]


def _said(events):
    return "".join(e.get("delta", "") for e in events if e.get("type") == "answer")


@pytest.mark.parametrize("text, days", [
    ("the day before", -1), ("a week before that", -7), ("two days later", 2), ("the week before", -7), ("a few weeks after", 21), ("an hour before", None), ("hello", None),
])
def test_the_recogniser_reads_a_span_from_a_day(text, days):
    assert recognise_questions.days_apart(text) == days


@pytest.mark.parametrize("ask, sentence", [
    ("remind me the day before", "remind me to renew passport on 29 November at 9am"),
    ("and a week before that", "remind me to renew passport on 23 November at 9am"),
    ("also remind me two days before", "remind me to renew passport on 28 November at 9am"),
])
def test_a_span_counts_from_the_reminder_just_set(ask, sentence):
    assert follow_items.read(ask, SET, NOW) == (sentence, None)


def test_a_span_counts_from_the_date_a_fact_stated():
    said, ask = follow_items.read("remind me the day before", FACT, NOW)
    assert said == "remind me about the Dentist note on 20 November at 9am" and ask is None


def test_a_span_with_no_date_before_it_is_left_alone():
    assert follow_items.read("remind me the day before", [{"question": "hi", "answer": "Hello."}], NOW) == (None, None)
    assert follow_items.read("remind me the day before", SET) == (None, None)


def test_the_day_before_sets_the_reminder_for_the_day_before(client):
    events = _events(client, "remind me the day before", history=SET)
    #: Whether the act runs at once or waits behind Confirm (owner order 2026-11-10), it carries the day before.
    blob = json.dumps(events)
    assert "2026-11-29T09:00:00" in blob and "enew passport" in blob, blob[:600]


@pytest.mark.parametrize("ask", ["move it to the 16th", "push it to the 16th", "change it to the 16th", "reschedule it to the 16th"])
def test_move_it_to_a_day_moves_the_reminder(ask):
    assert follow_items.read(ask, SET, NOW) == ("move the reminder renew passport to 16 November at 9am", None)


def test_a_clock_in_the_move_is_kept():
    assert follow_items.read("move it to the 16th at 3pm", SET, NOW)[0] == "move the reminder renew passport to 16 November at 3pm"


@pytest.mark.parametrize("ask", ["move it to Admin", "move it to the bin", "move it to Travel"])
def test_a_move_to_a_category_is_not_a_day(ask):
    assert follow_items.read(ask, SET, NOW) == (None, None)


def test_move_it_to_the_16th_moves_the_reminder(client, session):
    manager.create_entry(session, "# Passport\n\nRenew passport by 30 November.")
    session.commit()
    first = confirmed(client, _events(client, "remind me to renew passport on 30 November at 9am"))
    events = _events(client, "move it to the 16th", history=[{"question": "remind me to renew passport on 30 November at 9am", "answer": _said(first)}])
    blob = json.dumps(events)
    assert "snooze_reminder" in blob and "2026-11-16T09:00:00" in blob, blob[:600]
    assert "category" not in _said(events).lower()


def test_move_it_to_a_day_after_a_dated_fact_offers_a_reminder_instead():
    said, ask = follow_items.read("move it to the 16th", FACT, NOW)
    assert said is None and "16 November" in ask and "remind" in ask.lower(), ask
