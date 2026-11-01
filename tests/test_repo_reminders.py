"""The reminders repository's verbs, against a real session (INBOX 1499).

The route tests (`test_reminders_api.py`, `test_reminders_ics.py` and the
rest) hold the HTTP behaviour unchanged; these hold the repository's own
contract: it flushes but leaves the commit to its caller, a binned reminder is
out of every read but the bin's, and its errors are the domain names the
routes answer with. Fixed dates only, never the real clock for an assertion.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from tessellate.core.database import Entry
from tessellate.repo import Conflict, NotFound, reminders

DUE = datetime(2030, 3, 4, 9, 0)


def _make(session, text="Water the plants", due=DUE, **fields):
    return reminders.create(session, text=text, due_at=due, **fields)


def test_create_flushes_an_id_and_leaves_the_commit_to_the_caller(session):
    reminder = _make(session)
    assert reminder.id is not None
    session.rollback()
    with pytest.raises(NotFound):
        reminders.get(session, reminder.id)


def test_page_is_soonest_first_with_the_id_as_tiebreaker_and_counts_the_filter(session):
    later = _make(session, "later", DUE + timedelta(days=1))
    a = _make(session, "a")
    b = _make(session, "b")
    done = _make(session, "done", DUE - timedelta(days=1), done=True)
    rows, total = reminders.page(session, limit=2, offset=0)
    assert [r.id for r in rows] == [done.id, a.id] and total == 4
    rows, total = reminders.page(session, limit=10, offset=0, include_done=False)
    assert [r.id for r in rows] == [a.id, b.id, later.id] and total == 3


def test_twin_names_an_open_reminder_with_the_same_words_and_time(session):
    first = _make(session, "Call Sam")
    assert reminders.twin(session, "  call sam ", DUE) == first.id
    assert reminders.twin(session, "Call Sam", DUE + timedelta(hours=1)) is None


def test_counts_for_notes_leaves_done_out_unless_asked(session):
    note = Entry(content="host")
    session.add(note)
    session.flush()
    _make(session, entry_id=note.id)
    _make(session, "ticked", entry_id=note.id, done=True)
    assert reminders.counts_for_notes(session, [note.id], include_done=False) == {note.id: 1}
    assert reminders.counts_for_notes(session, [note.id], include_done=True) == {note.id: 2}


def test_a_binned_reminder_is_out_of_every_read_but_the_bins(session):
    reminder = _make(session)
    reminders.move_to_bin(session, reminder)
    session.expunge_all()
    with pytest.raises(NotFound):
        reminders.get(session, reminder.id)
    assert reminders.page(session, limit=10, offset=0) == ([], 0)
    binned = reminders.get_any(session, reminder.id)
    reminders.restore(session, binned)
    assert reminders.get(session, reminder.id).deleted_at is None


def test_purge_refuses_a_live_reminder(session):
    reminder = _make(session)
    with pytest.raises(Conflict) as raised:
        reminders.purge(session, reminder)
    assert raised.value.status_code == 409
    reminders.move_to_bin(session, reminder)
    reminders.purge(session, reminders.get_any(session, reminder.id))
    with pytest.raises(NotFound):
        reminders.get_any(session, reminder.id)


def test_complete_ticks_a_one_off_and_rolls_a_repeating_one_on(session):
    once = _make(session, "once", datetime(2020, 1, 1, 9, 0))
    reminders.complete(session, once, 0)
    assert once.done is True
    weekly = _make(session, "weekly", datetime(2020, 1, 1, 9, 0), recurring="weekly")
    reminders.complete(session, weekly, 0)
    assert weekly.done is False and weekly.due_at.weekday() == datetime(2020, 1, 1).weekday()
    assert weekly.due_at.replace(tzinfo=None) > datetime(2020, 1, 1, 9, 0)


def test_due_by_is_the_open_ones_due_by_the_end_of_tomorrow(session):
    today = date(2030, 3, 3)
    soon = _make(session, "soon", datetime(2030, 3, 4, 23, 0))
    _make(session, "far", datetime(2030, 3, 6, 9, 0))
    _make(session, "ticked", datetime(2030, 3, 4, 8, 0), done=True)
    assert [r["id"] for r in reminders.due_by(session, today)] == [soon.id]
