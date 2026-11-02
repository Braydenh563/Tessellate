"""The note-properties repository's verbs, against a real session (INBOX 1499).

`test_properties_kg4.py` and the timeline tests hold the routes unchanged;
these hold the repository's reads: a note's rows in block order, the first
`type` per note, a meeting's own date, and the join that places it.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from tessellate.core.database import Entry, EntryProperty
from tessellate.repo import NotFound, properties


def _note(session, *rows: tuple[str, str, datetime | None]) -> Entry:
    entry = Entry(content="n")
    session.add(entry)
    session.flush()
    for key, value, when in rows:
        session.add(EntryProperty(entry_id=entry.id, key=key, value=value, date=when))
    session.flush()
    return entry


def test_find_get_and_page_read_one_notes_rows_in_block_order(session):
    a = _note(session, ("type", "Meeting", None), ("tags", "x", None), ("tags", "y", None))
    b = _note(session, ("type", "Book", None))
    assert properties.find(session, a.id, "tags").value == "x"
    assert properties.find(session, a.id, "nope") is None
    assert properties.get(session, b.id, "type").value == "Book"
    with pytest.raises(NotFound):
        properties.get(session, b.id, "tags")
    rows, total = properties.page(session, a.id, limit=2)
    assert [r.key for r in rows] == ["type", "tags"] and total == 3
    rest, _ = properties.page(session, a.id, limit=2, offset=2)
    assert [r.value for r in rest] == ["y"]


def test_types_lists_every_type_oldest_row_first(session):
    a = _note(session, ("type", "book", None))
    b = _note(session, ("type", "Meeting", None))
    _note(session, ("author", "Ann", None))
    assert properties.types(session) == [(a.id, "book"), (b.id, "Meeting")]


def test_meeting_dates_are_only_for_meetings_with_a_readable_date(session):
    day = datetime(2026, 3, 4, 9, 30, tzinfo=timezone.utc)
    meeting = _note(session, ("type", "meeting", None), ("date", "2026-03-04 09:30", day))
    _note(session, ("type", "Book", None), ("date", "2026-01-01", datetime(2026, 1, 1)))
    unreadable = _note(session, ("type", "Meeting", None), ("date", "soon", None))
    ids = [meeting.id, unreadable.id, 9999]
    assert properties.meeting_dates(session, ids) == {meeting.id: (day, "2026-03-04 09:30")}
    assert properties.meeting_dates(session, []) == {}


def test_join_meeting_date_puts_a_meetings_own_date_on_the_note_row(session):
    day = datetime(2026, 5, 6, tzinfo=timezone.utc)
    meeting = _note(session, ("type", "Meeting", None), ("date", "2026-05-06", day))
    plain = _note(session, ("type", "Book", None))
    joined, column = properties.join_meeting_date(select(Entry.id), Entry.id)
    got = dict(session.execute(joined.add_columns(column).order_by(Entry.id)).all())
    assert got == {meeting.id: day, plain.id: None}
