"""Tags, a category and properties on documents and files (decision 65, L-world-class-392 and 393).

The storage (three columns on `documents` and `media_uploads`, migration
a3d7c1e9b5f4) and the one endpoint the Library's Documents and Media selection
bars write through, with the Undo that puts every row back.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic.script import ScriptDirectory

from tessellate.core import deps
from tessellate.core.database import Document, MediaUpload
from tessellate.core.database_manager import DatabaseManager

from tests.test_alembic_full_chain import _config


@pytest.fixture()
def rows(app_state):
    s = deps.get_db().session()
    docs = [Document(title="One", content="a"), Document(title="Two", content="b")]
    files = [MediaUpload(filename="a.png", original_name="a.png"), MediaUpload(filename="b.png", original_name="b.png")]
    s.add_all([*docs, *files])
    s.commit()
    ids = ([d.id for d in docs], [f.id for f in files])
    s.close()
    return ids


def _read(client, kind, ids):
    return client.get("/library/meta", params={"kind": kind, "ids": ",".join(map(str, ids))}).json()["items"]


@pytest.mark.parametrize("kind,at", [("document", 0), ("media", 1)])
def test_tags_category_and_a_property_land_on_every_row_and_undo_restores(client, rows, kind, at):
    ids = rows[at]
    body = {"kind": kind, "ids": ids, "add": ["Study, #exam"], "category": "School",
            "property_name": "term", "property_value": "autumn"}
    out = client.post("/library/meta/bulk", json=body).json()
    assert out["changed"] == 2 and all(b["tags"] == [] and b["category"] is None for b in out["before"])
    got = _read(client, kind, ids)
    assert [i["tags"] for i in got] == [["Study", "exam"]] * 2
    assert {i["category"] for i in got} == {"School"}
    assert all(i["properties"] == {"term": "autumn"} for i in got)
    # Take one tag off, clear the category, remove the property (no value).
    client.post("/library/meta/bulk", json={"kind": kind, "ids": ids, "remove": ["study"], "clear_category": True,
                                            "property_name": "term"})
    got = _read(client, kind, ids)
    assert [i["tags"] for i in got] == [["exam"]] * 2
    assert all(i["category"] is None and i["properties"] == {} for i in got)
    # Undo of the first write: the states it returned.
    client.post("/library/meta/restore", json={"kind": kind, "items": out["before"]})
    got = _read(client, kind, ids)
    assert all(i["tags"] == [] and i["category"] is None and i["properties"] == {} for i in got)


def test_a_bad_kind_or_property_is_refused(client, rows):
    wrong_kind = client.post("/library/meta/bulk", json={"kind": "note", "ids": [1], "add": ["x"]})
    refused = client.post("/library/meta/bulk", json={"kind": "document", "ids": rows[0], "property_name": "  "})
    assert (wrong_kind.status_code, refused.status_code) == (422, 422)


def test_a_database_from_before_the_columns_gains_them_and_keeps_its_rows(tmp_path):
    path = tmp_path / "old.db"
    DatabaseManager(path).engine.dispose()
    con = sqlite3.connect(path)
    try:
        for table in ("documents", "media_uploads"):
            con.execute("PRAGMA legacy_alter_table = ON")
            #: category_id is a foreign key, which SQLite will not drop: rebuild the table as it was.
            keep = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")') if r[1] not in ("tags", "category_id", "properties")]
            con.execute(f"CREATE TABLE old_{table} AS SELECT {', '.join(keep)} FROM {table}")
            con.execute(f"DROP TABLE {table}")
            con.execute(f"ALTER TABLE old_{table} RENAME TO {table}")
        con.execute(
            "INSERT INTO documents (title, content, file_type, workspace_id, created_at, updated_at, threads, is_private, sealed_by_space) "
            "VALUES ('kept','x','md','default','2026-01-01','2026-01-01','',0,0)"
        )
        con.execute("PRAGMA user_version = 0")
        con.commit()
    finally:
        con.close()
    DatabaseManager(path).engine.dispose()
    con = sqlite3.connect(path)
    try:
        for table in ("documents", "media_uploads"):
            assert {"tags", "category_id", "properties"} <= {r[1] for r in con.execute(f'PRAGMA table_info("{table}")')}
        assert con.execute("SELECT title, tags, category_id, properties FROM documents").fetchall() == [("kept", "[]", None, "{}")]
    finally:
        con.close()


def test_the_migration_is_the_chain_head():
    assert ScriptDirectory.from_config(_config(Path("/x.db"))).get_current_head() == "a3d7c1e9b5f4"
