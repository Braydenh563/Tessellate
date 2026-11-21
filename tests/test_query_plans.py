"""The lists are served in index order, in the view people are in (WORLD_CLASS_PLAN 19.3).

The `EXPLAIN QUERY PLAN` pass of 2026-10-05 (`scratchpad/plat1005_query_plans.py`,
every GET route over a 5,000-note notebook) found that every composite index
built for a list led with `workspace_id`, and that the page's default view,
All spaces, never sends an equality on it. So the notes list, the bin, the
archive, the Timeline, the Library's activity, uploads, documents, chats and
reminders all sorted their whole table on every page. `database._INDEXES` now
carries the same orders without the space column; this asserts each list's
own statement, as the route really runs it, is planned without a sort.

It also holds the trap the first cut fell into: an index that leads with a
flag SQLite takes for a selective equality (`is_deleted = 0`, `archived_at IS
NULL`) turns "every live note, by id" from a table read in rowid order into an
index lookup plus a sort. The last test pins those statements to the plan
they had.

SQLite plans these without statistics (nothing runs `ANALYZE`), so the plan
does not depend on how many rows the test seeds; a few dozen is enough.
"""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from sqlalchemy import event

from tessellate.core import deps
from tessellate.core.database import (
    AuditLog,
    Conversation,
    Document,
    Entry,
    MediaUpload,
    Reminder,
    utcnow,
)
from tests._clock import SUITE_NOW, pin_clock


@pytest.fixture(autouse=True)
def _suite_clock(monkeypatch):
    """Data here is built from SUITE_NOW, and the app reads the same pinned clock."""
    pin_clock(monkeypatch, SUITE_NOW)

#: route -> the ORDER BY each of its list statements must be served from.
SORTED_LISTS = {
    "/entries": "ORDER BY entries.pinned DESC",
    "/entries?deleted=true": "ORDER BY entries.deleted_at DESC",
    "/entries?archived=true": "ORDER BY entries.archived_at DESC",
    "/library": "ORDER BY audit_log.created_at DESC",
    "/timeline": "ORDER BY entries.created_at DESC",
    "/entries/most-accessed": "ORDER BY entries.access_count DESC",
    "/media": "ORDER BY media_uploads.created_at DESC",
    "/documents": "ORDER BY documents.updated_at DESC",
    "/conversations": "ORDER BY conversations.pinned DESC",
    "/reminders": "ORDER BY reminders.due_at",
}


@pytest.fixture()
def seeded(client):
    session = deps.get_db().session()
    now = utcnow()
    try:
        notes = [
            Entry(content=f"Note {i}", created_at=now - timedelta(minutes=i), access_count=i % 4)
            for i in range(40)
        ]
        session.add_all(notes)
        session.flush()
        for note in notes[:5]:
            note.is_deleted = True
            note.deleted_at = now
        for note in notes[5:9]:
            note.archived_at = now
        for i in range(40):
            session.add(AuditLog(action="edited", entity_type="entry", entity_id=notes[i].id, actor="user"))
            session.add(MediaUpload(filename=f"m{i}.png", original_name=f"m{i}.png"))
            session.add(Document(title=f"Doc {i}", content="x"))
            session.add(Conversation(title=f"Chat {i}"))
            session.add(Reminder(entry_id=notes[i].id, text=f"R {i}", due_at=now + timedelta(days=i)))
        session.commit()
    finally:
        session.close()
    return client


def _statements(client, url: str) -> list[tuple[str, tuple]]:
    seen: list[tuple[str, tuple]] = []

    def before(_conn, _cursor, statement, parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            seen.append((statement, parameters))

    engine = deps.get_db().engine
    event.listen(engine, "before_cursor_execute", before)
    try:
        assert client.get(url).status_code == 200, url
    finally:
        event.remove(engine, "before_cursor_execute", before)
    return seen


def _plan(statement: str, parameters) -> list[str]:
    raw = deps.get_db().engine.raw_connection()
    try:
        rows = raw.cursor().execute("EXPLAIN QUERY PLAN " + statement, parameters or ()).fetchall()
    finally:
        raw.close()
    return [row[-1] for row in rows]


@pytest.mark.parametrize("url", sorted(SORTED_LISTS))
def test_each_list_page_is_read_in_index_order(seeded, url):
    order = SORTED_LISTS[url]
    matching = [(s, p) for s, p in _statements(seeded, url) if order in " ".join(s.split())]
    assert matching, f"{url} ran no statement with {order!r}"
    for statement, parameters in matching:
        plan = _plan(statement, parameters)
        assert not any("TEMP B-TREE FOR ORDER BY" in step for step in plan), (url, plan)


def test_a_read_of_every_live_note_by_id_stays_a_table_read(seeded):
    """The regression the first cut caused: duplicates and a note's
    connections read every live note in id order, which is the table's own
    order; an index led by `is_deleted` made SQLite look it up and sort."""
    statements = _statements(seeded, "/duplicates")
    by_id = [(s, p) for s, p in statements if re.search(r"FROM entries WHERE .* ORDER BY entries\.id\b", " ".join(s.split()))]
    assert by_id
    for statement, parameters in by_id:
        plan = _plan(statement, parameters)
        assert not any("TEMP B-TREE" in step for step in plan), plan
