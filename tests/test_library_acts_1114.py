"""Library acts (L-chat-46 to 49): archive and unarchive, move a reminder, tag many notes, start
a board. Each is a card that waits for Confirm; a bulk one counts first and has one Undo.
Clock: Tuesday 10 November 2026, 09:00."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import select

from tessellate.ai import library_acts, tools
from tessellate.api import chat_said, chat_turn, routes_chat, routes_insights
from tessellate.core.database import Entry, Reminder
from tessellate.entry import manager

from tests.test_parity_acts_1110 import NOW, card_of, confirm, stream, undo  # noqa: F401  (fixed clock fixture is autouse there)


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    from tessellate.core import config

    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    for module in (routes_chat, chat_said, chat_turn, routes_insights):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)


def _note(session, content, when=None, **kw):
    entry = manager.create_entry(session, content, **kw)
    if when:
        entry.created_at = when
    session.commit()
    return entry.id


def _archived(session, note_id) -> bool:
    session.expire_all()
    return session.get(Entry, note_id).archived_at is not None


def test_archive_counts_first_then_one_undo_brings_them_back(client, session):
    a = _note(session, "# Lisbon trip\n\nBook the flights.")
    b = _note(session, "# Trip packing\n\nPassport, charger.")
    c = _note(session, "# Wifi\n\nBluegum-5G.")
    out = stream(client, "archive the trip notes")
    card = card_of(out)
    assert "2 notes" in card["label"]
    assert not _archived(session, a), "nothing happens before Confirm"
    done = confirm(client, card)
    assert _archived(session, a) and _archived(session, b) and not _archived(session, c)
    assert len(done["undo"]) == 1 and done["undo"][0]["name"] == "archive_note"
    undo(client, done)
    assert not _archived(session, a) and not _archived(session, b)


def test_unarchive_reads_only_archived_notes(client, session):
    a = _note(session, "# Lisbon trip\n\nBook the flights.")
    manager.archive_entry(session, session.get(Entry, a))
    session.commit()
    card = card_of(stream(client, "unarchive the trip notes"))
    confirm(client, card)
    assert not _archived(session, a)


def test_private_notes_are_never_archived(session):
    note_id = _note(session, "# Diary\n\nPrivate thoughts.")
    entry = session.get(Entry, note_id)
    entry.is_private = True
    session.commit()
    refused = tools.execute_tool(session, "archive_note", {"note_id": note_id})
    assert "error" in refused
    assert not _archived(session, note_id)


def test_archive_note_tool_says_when_nothing_changed(session):
    note_id = _note(session, "# Wifi\n\nBluegum-5G.")
    said = tools.execute_tool(session, "archive_note", {"note_id": note_id, "archived": False})
    assert "Nothing to do" in said["error"]


def test_tag_many_counts_first_and_undoes_as_one(client, session):
    march = [_note(session, f"# Spring job {i}\n\nWork.", datetime(2026, 3, 5 + i, 9)) for i in range(3)]
    other = _note(session, "# November\n\nNow.", datetime(2026, 11, 2, 9))
    card = card_of(stream(client, "tag everything from March with spring"))
    assert "3 notes" in card["label"] and "spring" in card["label"]
    session.expire_all()
    assert "spring" not in (session.get(Entry, march[0]).tags or [])
    done = confirm(client, card)
    session.expire_all()
    assert all("spring" in session.get(Entry, n).tags for n in march)
    assert "spring" not in session.get(Entry, other).tags
    undo(client, done)
    session.expire_all()
    assert all("spring" not in session.get(Entry, n).tags for n in march)


def test_tag_many_with_an_unreadable_span_asks_instead_of_guessing(client, session):
    _note(session, "# One\n\nx.", datetime(2026, 3, 5, 9))
    out = stream(client, "tag everything from the zorgblat era with spring")
    assert not [e for e in out.get("act", []) if e.get("steps")]


def test_span_reads_months_weeks_and_relative_spans():
    today = NOW.date()
    assert library_acts.span("March", today)[:2] == (date(2026, 3, 1), date(2026, 4, 1))
    assert library_acts.span("last month", today)[:2] == (date(2026, 10, 1), date(2026, 11, 1))
    assert library_acts.span("March 2025", today)[0] == date(2025, 3, 1)
    assert library_acts.span("last 10 days", today)[0] == date(2026, 11, 1)
    assert library_acts.span("the zorgblat era", today) is None


def test_reschedule_names_the_old_time_and_undo_puts_it_back(client, session):
    session.add(Reminder(text="Call the dentist", due_at=datetime(2026, 11, 11, 9)))
    session.commit()
    card = card_of(stream(client, "move the dentist reminder to Friday at 9"))
    assert "tomorrow" in card["label"] and "Friday" in card["label"]
    done = confirm(client, card)
    session.expire_all()
    assert session.scalars(select(Reminder)).first().due_at.replace(tzinfo=None) == datetime(2026, 11, 13, 9)
    undo(client, done)
    session.expire_all()
    assert session.scalars(select(Reminder)).first().due_at.replace(tzinfo=None) == datetime(2026, 11, 11, 9)


def test_make_board_reads_the_board_back_as_its_answer(client, session):
    card = card_of(stream(client, "start a board for the kitchen"))
    done = confirm(client, card)
    assert "I read it back" in done["summary"] and "Kitchen" in done["summary"]
    assert done["undo"][0]["name"] == "delete_note"
