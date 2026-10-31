"""`GET /timeline` costs a fixed handful of SQL statements, however big the
notebook is and whichever range or page is asked for.

A statement *count*, not a wall clock (the reason `test_scale_query_counts.py`
gives): a per-note query, or a placement that is read again per note, shows as
a count that rises with the notebook, and that is a fact about the code and
not about the machine running the test. The 19.5 s first page reported at 4,602
notes was measured on a machine at load 8; at 5,000 notes the endpoint itself
is 13 statements, and these pin that.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import event

from tessellate.core.database import Entry, EntryDate, EntryProperty, utcnow

#: The most statements one page may take: the auth read, the three sources,
#: the density, the dates, meetings, categories, spaces and links. Measured at
#: 13; two spare, so a new column does not trip it but a query per row does.
CEILING = 15


def _statements(session, fn):
    seen: list[str] = []

    def before(_conn, _cursor, statement, *_rest):
        seen.append(statement)

    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", before)
    try:
        fn()
    finally:
        event.remove(engine, "before_cursor_execute", before)
    return seen


def _notebook(session, n: int) -> None:
    """`n` notes over a year: a third mention a date, one in ten is a meeting."""
    now = utcnow()
    for i in range(n):
        entry = Entry(content=f"note {i} about the garden", created_at=now - timedelta(days=i % 300, minutes=i))
        session.add(entry)
        session.flush()
        if i % 3 == 0:
            session.add(EntryDate(entry_id=entry.id, phrase="tomorrow", at=entry.created_at + timedelta(days=1)))
        if i % 10 == 0:
            session.add(EntryProperty(entry_id=entry.id, key="type", value="meeting"))
            session.add(EntryProperty(entry_id=entry.id, key="date", value="d", date=entry.created_at))
    session.commit()


ASKS = {
    "first page": "/timeline?limit=10",
    "everything": "/timeline?days=0&limit=10",
    "a range": "/timeline?start=2026-01-01T00:00:00&end=2027-12-31T00:00:00&limit=10",
    "a range and also": "/timeline?start=2026-01-01T00:00:00&end=2027-12-31T00:00:00&limit=10&also=true",
    "notes by thread": "/timeline?days=0&group=thread&kind=note&limit=10",
}


def test_a_timeline_page_costs_the_same_statements_at_any_notebook_size(client, session):
    _notebook(session, 20)
    small = {name: len(_statements(session, lambda url=url: client.get(url))) for name, url in ASKS.items()}
    _notebook(session, 200)
    large = {name: len(_statements(session, lambda url=url: client.get(url))) for name, url in ASKS.items()}
    assert large == small, f"statements grew with the notebook: {small} to {large}"
    assert max(large.values()) <= CEILING, large


def test_a_cursor_page_costs_no_more_than_the_first(client, session):
    _notebook(session, 120)
    first = client.get("/timeline?days=0&limit=10").json()
    cursor = first["next_cursor"]
    assert cursor
    later = len(_statements(session, lambda: client.get(f"/timeline?days=0&limit=10&cursor={cursor}")))
    assert later <= len(_statements(session, lambda: client.get("/timeline?days=0&limit=10"))) + 1
    assert later <= CEILING


def test_a_bigger_page_does_not_add_a_statement_per_row(client, session):
    _notebook(session, 150)
    five = len(_statements(session, lambda: client.get("/timeline?days=0&limit=5")))
    hundred = len(_statements(session, lambda: client.get("/timeline?days=0&limit=100")))
    assert hundred == five


def test_where_a_note_sits_is_not_a_subquery_per_note(client, session):
    """The window and the density read a note's first mention and a meeting's
    own date from one grouped join. A correlated subquery here ran again per
    note for each use, 40 ms at 5,000 notes and rising with the notebook."""
    _notebook(session, 30)
    window = _statements(session, lambda: client.get("/timeline?start=2026-01-01T00:00:00&end=2027-12-31T00:00:00&limit=10"))
    for statement in window:
        if "entry_dates" in statement and "entries" in statement:
            assert "entry_dates.entry_id = entries.id" not in statement, statement
            assert "entry_properties.entry_id = entries.id" not in statement, statement


def test_link_counts_are_what_the_full_links_would_have_counted(session):
    """The count the timeline draws is `len` of `links_for_entries_bulk`, for a
    note linked both ways, one linked to itself and one linked one way,
    without loading the other end's text."""
    from tessellate.core.database import EntryLink
    from tessellate.entry import manager

    notes = [Entry(content=f"n{i}") for i in range(5)]
    session.add_all(notes)
    session.flush()
    a, b, c, d, e = (note.id for note in notes)
    session.add_all(
        [
            EntryLink(source_entry_id=a, target_entry_id=b),
            EntryLink(source_entry_id=b, target_entry_id=a),
            EntryLink(source_entry_id=a, target_entry_id=a),
            EntryLink(source_entry_id=c, target_entry_id=a),
            EntryLink(source_entry_id=d, target_entry_id=e),
        ]
    )
    session.commit()
    ids = [a, b, c, d, e]
    full = manager.links_for_entries_bulk(session, ids)
    assert manager.link_counts_bulk(session, ids) == {i: len(rows) for i, rows in full.items()}
    assert manager.link_counts_bulk(session, [a, b]) == {i: len(rows) for i, rows in manager.links_for_entries_bulk(session, [a, b]).items()}
    assert manager.link_counts_bulk(session, []) == {}
