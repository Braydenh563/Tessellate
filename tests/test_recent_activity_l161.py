"""L161 (b), INBOX 1841: "what was I working on" and "what did I change
today" are answered from the notes most recently edited, on a fixed clock."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tessellate.ai import activity_recent
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc)


def _notes(session):
    """Three notes: one edited this morning, one made today and never edited,
    one edited ten days ago (UTC, naive, as stored)."""
    morning = manager.create_entry(session, "# Harbor launch plan\n\nShip the app.")
    fresh = manager.create_entry(session, "# Dentist\n\nCheck-up on the 21st.")
    old = manager.create_entry(session, "# Gym plan\n\nTuesday and Thursday.")
    base = NOW.replace(tzinfo=None)
    morning.created_at, morning.edited_at = base - timedelta(days=30), base.replace(hour=9)
    fresh.created_at, fresh.edited_at = base.replace(hour=11), None
    old.created_at, old.edited_at = base - timedelta(days=40), base - timedelta(days=10)
    session.commit()


@pytest.mark.parametrize("question", ["what was I working on", "What was I working on?", "what did I last edit", "what have I been working on"])
def test_working_on_reads_the_newest_touch_first(session, question):
    _notes(session)
    said = activity_recent.answer(question, session, NOW).text
    assert said.index("Dentist") < said.index("Harbor launch plan") < said.index("Gym plan")
    assert "(#/notes/" in said and "!" not in said and chr(0x2014) not in said


def test_changed_today_lists_what_was_touched_today_only(session):
    _notes(session)
    said = activity_recent.answer("what did I change today", session, NOW).text
    assert "Harbor launch plan" in said and "Dentist" in said and "Gym plan" not in said
    assert "edited" in said and "made" in said  # the one never edited is said as made


def test_a_quiet_day_names_the_last_touch(session):
    _notes(session)
    said = activity_recent.answer("what did I change yesterday", session, NOW).text
    assert said.startswith("No note was changed yesterday.") and "Gym plan" in said


def test_other_questions_are_left_alone(session):
    _notes(session)
    for question in ("what did I change in the harbor plan", "what is the gym plan", "what am I working on", "what did I do today"):
        assert activity_recent.answer(question, session, NOW) is None, question


def test_no_notes_says_so(session):
    assert "no notes" in activity_recent.answer("what was I working on", session, NOW).text.lower()


def test_the_chat_answers_it_with_no_model(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    _notes(session)
    text = _ask(client, "what did I change today")["text"]
    assert "Harbor launch plan" in text and "Dentist" in text and "Gym plan" not in text
