"""Reading the dates in notes saved before written-out dates were read.

The owner, 2026-10-11: "things written on specific dates dont show". New notes
get them read on save (`timewords`); notes already in the notebook are read once
by `entry/redate.py`, in the background. What has to hold: a stale note moves
to the date it names; a second run changes nothing; a run cut short continues
from its cursor; the pass drains to done and shows as finished in the job
registry; a private note is left alone.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select

from tessellate.core import deps, jobruns
from tessellate.core.database import Entry, EntryDate
from tessellate.entry import redate


def _stale(client, session, text: str) -> int:
    """A note as an older version saved it: no stored date for what it names."""
    made = client.post("/entries", json={"content": text, "category": "Journal"}).json()
    session.execute(delete(EntryDate).where(EntryDate.entry_id == made["id"]))
    session.get(Entry, made["id"]).created_at = datetime(2024, 3, 2, 10, 0)
    session.commit()
    return made["id"]


def _dates(session, entry_id: int) -> list:
    session.expire_all()
    return [row.at.date().isoformat() for row in session.scalars(select(EntryDate).where(EntryDate.entry_id == entry_id).order_by(EntryDate.id))]


def test_a_stale_note_is_placed_on_the_date_it_names_and_a_second_run_changes_nothing(client, session):
    first = _stale(client, session, "Council tax is due on 2031-02-03.")
    plain = _stale(client, session, "Nothing dated here at all.")
    assert redate.pending() is True
    outcome = redate.run()
    assert outcome["done"] is True and outcome["changed"] == 1
    assert _dates(session, first) == ["2031-02-03"] and _dates(session, plain) == []
    assert redate.pending() is False
    again = redate.run()
    assert again["changed"] == 0 and _dates(session, first) == ["2031-02-03"]


def test_a_relative_phrase_is_read_against_the_notes_own_day_not_today(client, session):
    note = _stale(client, session, "Dentist tomorrow, and the exam on 2031-02-03.")
    redate.run()
    assert _dates(session, note) == ["2024-03-03", "2031-02-03"]


def test_a_run_cut_short_continues_from_its_cursor(client, session, monkeypatch):
    ids = [_stale(client, session, f"Item {n} falls on 2031-02-0{n}.") for n in range(1, 4)]
    seen: list[int] = []
    real = redate._reread

    def stop_after_two(db, entry):
        seen.append(entry.id)
        if len(seen) == 3:
            raise KeyboardInterrupt  # the process went away in the second chunk
        return real(db, entry)

    monkeypatch.setattr(redate, "_reread", stop_after_two)
    try:
        redate.run(chunk=2)
    except KeyboardInterrupt:  # the stand-in for a quit
        pass
    assert int(deps.get_config().get_preference(redate.CURSOR_KEY, 0)) == ids[1]
    assert redate.pending() is True
    monkeypatch.setattr(redate, "_reread", real)
    seen.clear()
    finished = redate.run(chunk=2)
    assert finished["notes"] == 1 and _dates(session, ids[2]) == ["2031-02-03"]
    assert redate.pending() is False


def test_the_pass_is_recorded_as_finished_in_the_job_registry(client, session):
    _stale(client, session, "Rent is due on 2031-02-03.")
    redate.run()
    row = next(r for r in jobruns.last_runs() if r["kind"] == "redate")
    assert row["ran"] is True and row["status"] in ("ok", "done", "success") and "placed" in row["result"]
    assert row["finished_at"] is not None and not row["error"]
    assert any(item["kind"] == "redate" for item in jobruns.finished())


def test_a_private_note_is_not_read(client, session):
    note = _stale(client, session, "Secret meeting on 2031-02-03.")
    session.get(Entry, note).is_private = True
    session.commit()
    redate.run()
    assert _dates(session, note) == []


def test_start_up_queues_the_pass_only_while_notes_are_unread(client, monkeypatch):
    from tessellate.core import jobs

    queued: list[str] = []
    monkeypatch.setattr(jobs, "enqueue", lambda kind, *a, **k: queued.append(kind))
    assert redate.enqueue_if_pending() is True and queued == ["redate"]
    deps.get_config().set_preference(redate.DONE_KEY, redate.VERSION)
    assert redate.enqueue_if_pending() is False and queued == ["redate"]


def test_a_range_saved_before_until_existed_gets_its_last_day(client, session):
    """Review on #222: `entry_dates.until` arrived with the range reading, so a row saved before
    it holds the range's first day and no last. Version 4 reads such notes again, once."""
    made = client.post("/entries", json={"content": "Away 3 to 7 March 2031.", "category": "Journal"}).json()
    session.expire_all()
    rows = session.scalars(select(EntryDate).where(EntryDate.entry_id == made["id"])).all()
    assert rows and rows[0].until is not None  # the save reads it today
    for row in rows:
        row.until = None  # as the row stood before the column
    session.get(Entry, made["id"]).created_at = datetime(2024, 3, 2, 10, 0)
    session.commit()
    deps.get_config().set_preference(redate.DONE_KEY, 3)
    assert redate.VERSION >= 4 and redate.pending() is True
    assert redate.run()["changed"] == 1
    session.expire_all()
    got = session.scalars(select(EntryDate).where(EntryDate.entry_id == made["id"])).all()
    assert [(r.at.date().isoformat(), r.until.date().isoformat() if r.until else None) for r in got] == [("2031-03-03", "2031-03-07")]
    assert redate.run()["changed"] == 0  # a second pass changes nothing
