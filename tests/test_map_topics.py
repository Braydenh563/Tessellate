"""UX-06's remainder (audit 2026-10-05, ux.md): a concept map's topics are
notes, and they flooded the notebook; a board's links were counted as
"sketches".

- A note made by a map gesture (Tab, Enter, a new concept map's root) says so
  (`map_topic`), so Notes and Recently added can leave it out while every
  search still finds it.
- A board's listing counts its connectors apart from its drawings
  (`link_count`), so a card that says "2 sketches" for two lines between
  cards can say "2 links".
"""
import json

from fastapi.testclient import TestClient

from tessellate.core import deps


def _client():
    from tessellate.api.app import create_app
    from tests.fakes import FakeEmbeddingService, FakeOllama

    deps.override_ai(
        ollama=FakeOllama(running=False),
        embeddings=FakeEmbeddingService(available=False),
    )
    return TestClient(create_app())


def test_a_note_made_on_a_map_says_so_and_an_ordinary_one_does_not(app_state):
    client = _client()
    topic = client.post("/entries", json={"content": "Dogs", "map_topic": True, "defer_filing": True})
    assert topic.status_code in (200, 201), topic.text
    assert topic.json()["map_topic"] is True
    plain = client.post("/entries", json={"content": "An ordinary note", "defer_filing": True}).json()
    assert plain["map_topic"] is False
    listed = {e["id"]: e for e in client.get("/entries").json()}
    #: Still in the list: the card on the board reads its text from it.
    assert listed[topic.json()["id"]]["map_topic"] is True
    assert listed[plain["id"]]["map_topic"] is False


def test_a_board_counts_its_links_apart_from_its_drawings(app_state):
    client = _client()
    board = client.post("/whiteboard/boards", json={"name": "Pets"}).json()
    a = client.post("/entries", json={"content": "Cats", "map_topic": True, "defer_filing": True}).json()
    b = client.post("/entries", json={"content": "Dogs", "map_topic": True, "defer_filing": True}).json()
    na = client.post("/whiteboard/nodes", json={"entry_id": a["id"], "board_id": board["id"]}).json()
    nb = client.post("/whiteboard/nodes", json={"entry_id": b["id"], "board_id": board["id"]}).json()
    link = json.dumps({"type": "link-curved", "sourceId": na["id"], "targetId": nb["id"]})
    client.post("/whiteboard/sketches", json={"data": link, "board_id": board["id"]})
    client.post("/whiteboard/sketches", json={"data": "M0 0 L1 1", "board_id": board["id"]})
    row = next(r for r in client.get("/whiteboard/boards").json() if r["id"] == board["id"])
    assert row["node_count"] == 2
    assert row["sketch_count"] == 2
    assert row["link_count"] == 1
    one = client.put(f"/whiteboard/boards/{board['id']}", json={}).json()
    assert one.get("link_count") == 1


def test_the_upgrade_marks_the_topics_a_map_gesture_already_made(tmp_path):
    """The old maps' topics leave Notes too: a short note whose card went on
    a board within seconds of it being written is marked; a note placed long
    after, a long note and a board are not."""
    import sqlite3

    from tessellate.core.database_manager import DatabaseManager, _ensure_alembic_baseline

    from datetime import datetime

    from sqlalchemy.orm import Session

    from tessellate.core.database import Entry, WhiteboardNode

    db_path = tmp_path / "old-maps.db"
    manager = DatabaseManager(db_path)
    at = datetime.fromisoformat
    with Session(manager.engine) as db:
        db.add_all([
            Entry(id=1, content="# Pets", is_board=True, created_at=at("2026-10-01 10:00:00")),
            Entry(id=2, content="Dogs", created_at=at("2026-10-01 10:00:05")),
            Entry(id=3, content="An older note dragged on later", created_at=at("2026-09-01 09:00:00")),
            Entry(id=4, content="x" * 300, created_at=at("2026-10-01 10:00:06")),
        ])
        db.flush()
        for entry_id, when in ((2, "2026-10-01 10:00:06"), (3, "2026-10-01 10:00:07"), (4, "2026-10-01 10:00:07")):
            db.add(WhiteboardNode(board_id=1, entry_id=entry_id, created_at=at(when)))
        db.commit()
    manager.engine.dispose()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("UPDATE entries SET map_topic = 0")
        conn.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
        conn.execute("DELETE FROM alembic_version")
        conn.execute("INSERT INTO alembic_version VALUES ('a7d3e9c1f5b2')")
        conn.commit()
    finally:
        conn.close()
    _ensure_alembic_baseline(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        marked = dict(conn.execute("SELECT id, map_topic FROM entries").fetchall())
        version = conn.execute("SELECT version_num FROM alembic_version").fetchall()
    finally:
        conn.close()
    # The head, read rather than pinned: a pinned id goes stale the moment the
    # next migration lands (the vault's recovery key, the next day).
    from tests.test_entry_edited_at import _alembic_head

    assert version == [(_alembic_head(),)]
    assert marked == {1: 0, 2: 1, 3: 0, 4: 0}
