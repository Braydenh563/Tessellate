"""Audit 1028 E64: a chat act names a note by its title, never `#14`. The id is
internal; the card's steps still carry it, but no line, label or item a student
reads does. A hashtag (`#travel`) is a tag, not an id, and stays."""

from __future__ import annotations

import datetime as dt
import json
import re

import pytest

from tessellate.ai import acts, commands
from tessellate.core import config
from tessellate.entry import manager

NOW = dt.datetime(2026, 10, 28, 10, 0, 0)
ID = re.compile(r"(?<![\w&])#\d+\b|\b(?:note|reminder) #\d+")


def _seed(session):
    a = manager.create_entry(session, "# Dentist\n\nBook a check-up for the trip.")
    b = manager.create_entry(session, "# Lisbon trip\n\nFlights and hotel.")
    session.commit()
    return a, b


def _shown(planned: dict) -> str:
    card = planned.get("card") or {}
    return json.dumps([planned.get("line"), card.get("label"), card.get("items"), card.get("title")], ensure_ascii=False)


ASKS = [
    "tag my dentist note with health",
    "tag my notes about the trip with travel",
    "move my dentist note to Health",
    "move my notes about the trip to Travel",
    "untag travel from my lisbon trip note",
    "delete my dentist note",
    "pin my dentist note",
    "rename my dentist note to Dentist visit",
    "link my dentist note to my lisbon trip note",
    "remind me tomorrow at 9 to call the dentist",
]


@pytest.mark.parametrize("ask", ASKS)
def test_no_card_line_or_item_shows_a_note_id(session, monkeypatch, ask):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    _seed(session)
    parsed = acts.parse(ask, NOW)
    assert parsed is not None, ask
    planned = acts.preview(session, parsed)
    assert not ID.search(_shown(planned)), (ask, _shown(planned))


def test_a_card_item_is_the_note_title(session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    a, _b = _seed(session)
    planned = acts.preview(session, acts.parse("pin my dentist note", NOW))
    assert planned["card"]["items"] == ["Dentist"]
    assert planned["card"]["steps"][0]["arguments"]["note_id"] == a.id


def test_opening_a_note_by_its_number_names_it_by_title(session):
    a, _b = _seed(session)
    planned = commands.plan(session, {"intent": "open", "note_id": a.id})
    assert "Dentist" in planned["line"] and not ID.search(planned["line"]), planned["line"]


def test_the_reminder_labels_name_the_words_not_the_number(session):
    from datetime import datetime

    from tessellate.core.database import Reminder

    row = Reminder(text="Call the dentist", due_at=datetime(2030, 1, 2, 9, 0))
    session.add(row)
    session.commit()
    from tessellate.ai import task_acts

    binned = commands._bin_reminder(session, {"reminder_id": row.id})
    assert "Call the dentist" in binned["label"] and not ID.search(binned["label"]), binned["label"]
    restored = task_acts.run_step(session, "restore_reminder", {"reminder_id": row.id})
    assert "Call the dentist" in restored["label"] and not ID.search(restored["label"]), restored["label"]
    snoozed = task_acts.run_step(session, "snooze_reminder", {"reminder_id": row.id, "due_at": "2030-01-03T09:00:00", "was": "2030-01-02T09:00:00"})
    assert "Call the dentist" in snoozed["label"] and not ID.search(snoozed["label"]), snoozed["label"]
