"""The time on a board's Library card is when a person last changed the board
(reported 2026-10-10: "idk why it says just now on the mindmap when I hadnt
been on it").

Measured cause: `Entry.updated_at` has `onupdate=utcnow`, so any UPDATE of the
board's entry row moved it. Opening the entry (`GET /entries/{id}` bumps
`access_count` and `last_opened_at`), a librarian stamp or an Ask result that
touched it were each enough, and the listing shows the newest of the board's
own row and its objects. Opening the map, listing the Library, exporting,
searching and re-indexing were measured not to write; they stay pinned here so
a later change cannot start.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select, text

from tessellate.core.database import Entry, WhiteboardObject

THEN = datetime(2026, 9, 1, 12, 0, 0)


@pytest.fixture
def old_map(client, session):
    mind = client.post("/whiteboard/boards", json={"name": "test", "type": "map", "layout": "tree-right"}).json()["id"]
    root = client.post(
        f"/whiteboard/boards/{mind}/nodes", json={"kind": "topic", "parent_id": None, "text": "test"}
    ).json()
    client.post(f"/whiteboard/boards/{mind}/nodes", json={"kind": "topic", "parent_id": root["id"], "text": "child"})
    # Raw SQL: an ORM write here would itself run `onupdate`.
    session.execute(text("UPDATE entries SET updated_at = :t WHERE id = :i"), {"t": THEN, "i": mind})
    session.execute(text("UPDATE whiteboard_objects SET updated_at = :t WHERE board_id = :i"), {"t": THEN, "i": mind})
    session.commit()
    return mind


def _listed(client, mind):
    card = next(b for b in client.get("/whiteboard/boards").json() if b["id"] == mind)
    return datetime.fromisoformat(card["updated_at"].replace("Z", "")).replace(microsecond=0)


def test_the_fixture_starts_at_the_old_time(client, old_map):
    assert _listed(client, old_map) == THEN


def test_opening_listing_exporting_searching_and_indexing_leave_the_time_alone(client, session, old_map):
    from tessellate.search import index

    client.get(f"/whiteboard/boards/{old_map}/tree")
    client.get(f"/whiteboard/boards/{old_map}/export")
    client.get("/library")
    client.get("/search", params={"q": "test"})
    index.rebuild(session)
    session.commit()
    assert _listed(client, old_map) == THEN


def test_opening_the_boards_entry_leaves_the_time_alone(client, old_map):
    """The measured culprit: a note card's link chip opens `GET /entries/{id}`."""
    opened = client.get(f"/entries/{old_map}?open=1")
    assert opened.status_code == 200
    assert opened.json()["access_count"] == 1, "the open is still counted"
    assert _listed(client, old_map) == THEN


def test_the_librarians_bookkeeping_leaves_the_time_alone(client, session, old_map):
    entry = session.get(Entry, old_map)
    entry.access_count += 3
    entry.filing_state = "done"
    entry.ai_confidence = 0.4
    session.commit()
    assert _listed(client, old_map) == THEN


def test_a_persons_rename_moves_the_time(client, old_map):
    renamed = client.put(f"/whiteboard/boards/{old_map}", json={"title": "renamed"})
    assert renamed.status_code == 200, renamed.text
    assert _listed(client, old_map) > THEN


def test_a_persons_new_topic_moves_the_time(client, old_map):
    client.post(f"/whiteboard/boards/{old_map}/nodes", json={"kind": "topic", "parent_id": None, "text": "new"})
    assert _listed(client, old_map) > THEN


def test_a_notes_updated_at_still_moves_as_before(client, session):
    """Notes are not boards: the rule is kept to the entry that has `edited_at`
    and a stamp (`lexical_filing`) keyed on `updated_at`."""
    from tessellate.entry import manager

    note = manager.create_entry(session, "A plain note", category_name="Work")
    session.execute(text("UPDATE entries SET updated_at = :t WHERE id = :i"), {"t": THEN, "i": note.id})
    session.commit()
    session.expire_all()
    session.get(Entry, note.id).access_count += 1
    session.commit()
    session.expire_all()
    assert session.get(Entry, note.id).updated_at.replace(tzinfo=None) > THEN


def test_the_object_rows_are_untouched_by_reads(client, session, old_map):
    client.get(f"/whiteboard/boards/{old_map}/tree")
    client.get("/whiteboard/boards")
    session.expire_all()
    newest = max(session.scalars(select(WhiteboardObject.updated_at).where(WhiteboardObject.board_id == old_map)))
    assert newest.replace(tzinfo=None) == THEN
