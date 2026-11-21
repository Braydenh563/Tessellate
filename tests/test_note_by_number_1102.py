"""OPEN 1522: a single-note act takes a note by its number ("pin note 12"),
the way "open note 12" already did. Before, the number was searched as the
words "note 12" and found nothing."""

from __future__ import annotations

import datetime as dt

import pytest

from tessellate.ai import acts
from tessellate.core import config
from tessellate.entry import manager

NOW = dt.datetime(2026, 10, 28, 10, 0, 0)


def _two(session):
    a = manager.create_entry(session, "# Dentist\n\nBook a check-up.")
    b = manager.create_entry(session, "# Lisbon trip\n\nFlights.")
    session.commit()
    return a, b


@pytest.mark.parametrize("ask", ["pin note {a}", "pin the note {a}", "pin entry {a}", "pin note #{a}"])
def test_pin_takes_a_note_by_number(session, monkeypatch, ask):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    a, _b = _two(session)
    parsed = acts.parse(ask.format(a=a.id), NOW)
    assert parsed is not None and parsed["note_id"] == a.id, parsed
    planned = acts.preview(session, parsed)
    step = planned["card"]["steps"][0]
    assert step["name"] == "pin_note" and step["arguments"]["note_id"] == a.id, planned
    assert "Dentist" in planned["card"]["label"]


def test_delete_and_rename_take_a_number(session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    a, b = _two(session)
    gone = acts.preview(session, acts.parse(f"delete note {b.id}", NOW))
    assert gone["card"]["steps"][0]["arguments"]["note_id"] == b.id
    renamed = acts.preview(session, acts.parse(f"rename note {a.id} to Dentist visit", NOW))
    assert renamed["card"]["steps"][0]["arguments"]["note_id"] == a.id, renamed


def test_link_and_tag_take_numbers(session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    a, b = _two(session)
    linked = acts.preview(session, acts.parse(f"link note {a.id} to note {b.id}", NOW))
    args = linked["card"]["steps"][0]["arguments"]
    assert (args["note_id"], args["other_note_id"]) == (a.id, b.id), linked
    tagged = acts.preview(session, acts.parse(f"tag note {a.id} with health", NOW))
    assert tagged["card"]["steps"][0]["arguments"]["note_ids"] == [a.id], tagged


def test_a_missing_number_is_said_not_searched(session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    _two(session)
    planned = acts.preview(session, acts.parse("pin note 9999", NOW))
    assert "card" not in planned and "9999" in planned["line"], planned


def test_a_title_with_a_number_still_searches(session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    manager.create_entry(session, "# Route 66 trip\n\nMaps.")
    session.commit()
    planned = acts.preview(session, acts.parse("pin my route 66 trip note", NOW))
    assert planned["card"]["steps"][0]["name"] == "pin_note", planned
