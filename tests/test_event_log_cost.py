"""Measured bound for the event log (WORLD_CLASS_PLAN 19.5, LEDGER L-world-class-73).

There is no publish/subscribe bus in this app: "the event bus" is
`core/events.py`, a synchronous append to `AuditLog` inside the caller's
transaction. So the three things 19.5 asks about have counted answers, and
none depends on a clock:

- cost per event: one INSERT, no per-event SELECT (a private-capable entity
  adds one `get` for its owner row; a flush adds one sqlite_master probe);
- subscribers: none, the only consumers read the table later;
- back-pressure: none, `record()` never blocks or queues, and a write scope
  folds every inner event into the one row, so a write costs one row however
  many things it did on the way.
"""
from __future__ import annotations

from sqlalchemy import event as sa_event

from tessellate.core import events
from tessellate.core.database import AuditLog


def _statements(session, fn):
    seen: list[str] = []

    def hook(_conn, _cursor, statement, *_a, **_k):
        seen.append(statement.strip())

    engine = session.get_bind()
    sa_event.listen(engine, "before_cursor_execute", hook)
    try:
        fn()
    finally:
        sa_event.remove(engine, "before_cursor_execute", hook)
    return seen


def test_one_event_is_one_insert_and_no_read(session):
    def run():
        for i in range(50):
            events.record(session, "edited", "entry", i + 1, "x")
        session.flush()

    seen = _statements(session, run)
    reads = [x for x in seen if x.startswith("SELECT")]
    # The one read is a per-flush probe of sqlite_master (the search index), not per event.
    assert len(reads) <= 1 and all("sqlite_master" in x for x in reads), reads
    assert len([x for x in seen if x.startswith("INSERT")]) == 50, "one INSERT per event, never more"
    assert session.query(AuditLog).count() == 50


def test_cost_does_not_grow_with_the_log(session):
    """An event costs the same on a log of 500 rows as on an empty one."""
    for i in range(500):
        events.record(session, "edited", "entry", i + 1, "x")
    session.flush()

    def one():
        events.record(session, "edited", "entry", 1, "y")
        session.flush()

    seen = _statements(session, one)
    inserts = [x for x in seen if x.startswith("INSERT")]
    assert len(inserts) == 1 and len(seen) <= 2, seen


def test_a_write_scope_folds_inner_events_into_one_row(session):
    """The bound on events per write is one, whatever the write does inside."""

    @events.writes("entry", "created")
    def write(session):
        events.record(session, "created", "entry", 1)
        for _ in range(20):
            events.record(session, "dated", "entry", 1)

    before = session.query(AuditLog).count()
    write(session)
    session.flush()
    assert session.query(AuditLog).count() - before == 1


def test_there_are_no_subscribers():
    """Nothing registers a callback on the log: back-pressure cannot exist."""
    public = [n.lower() for n in dir(events) if not n.startswith("_")]
    assert not [n for n in public if any(w in n for w in ("subscribe", "listener", "handler", "callback"))]
