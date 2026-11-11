"""Note properties and note types (GRAPH_PLAN KG4, INBOX 528).

A note's properties live in its own text, a `---` frontmatter block as
Obsidian writes it; `entry_properties` is an index rebuilt on save. The block
is never the note's name: a note opening with properties is named by the
first line after them. Done when a vault's frontmatter imports as
properties and a type adds its fields to a new note.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from tessellate.entry import properties

NOTE = "---\nstatus: open\ntags: [a, b]\n---\n# Kiln plan\n\nFire on Thursday."


# --- the pure half ---------------------------------------------------------------


def test_split_reads_the_block_and_leaves_the_body():
    props, body = properties.split(NOTE)
    assert props == {"status": ["open"], "tags": ["a", "b"]}
    assert body == "# Kiln plan\n\nFire on Thursday."


def test_only_a_closed_block_on_line_one_is_frontmatter():
    assert properties.split("# Title\n\n---\n\nafter a rule") == ({}, "# Title\n\n---\n\nafter a rule")
    assert properties.split("---\nstatus: open\nno closing fence") == ({}, "---\nstatus: open\nno closing fence")
    assert properties.strip("plain") == "plain"


def test_write_changes_the_block_and_never_the_body():
    out = properties.write(NOTE, {"status": "done", "due": "2026-10-10", "tags": ["a", "c"]})
    assert out.endswith("# Kiln plan\n\nFire on Thursday.")
    assert properties.split(out)[0] == {"status": ["done"], "due": ["2026-10-10"], "tags": ["a", "c"]}
    cleared = properties.write(NOTE, {})
    assert cleared == "# Kiln plan\n\nFire on Thursday."
    added = properties.write("plain note", {"status": "new"})
    assert added == "---\nstatus: new\n---\nplain note"


# --- the notes ---------------------------------------------------------------------


def _note(client, text, **extra):
    return client.post("/entries", json={"content": text, **extra}).json()


def test_a_note_with_properties_is_named_by_its_first_line_after_them(client):
    made = _note(client, NOTE)
    assert made["title"] == "Kiln plan"
    assert made["properties"] == {"status": ["open"], "tags": ["a", "b"]}
    other = _note(client, "See [[Kiln plan]] for dates.")
    linked = client.get(f"/entries/{other['id']}").json()["links"]
    assert linked and linked[0]["entry_id"] == made["id"]
    assert not linked[0]["preview"].startswith("---")


def test_the_properties_route_reads_and_writes_the_block(client, session):
    from tessellate.core.database import Entry, EntryProperty

    made = _note(client, NOTE)
    got = client.get(f"/entries/{made['id']}/properties").json()
    assert got["properties"] == {"status": ["open"], "tags": ["a", "b"]}
    put = client.put(f"/entries/{made['id']}/properties", json={"properties": {"status": "done", "effort": "3", "due": "2026-10-10"}})
    assert put.status_code == 200, put.text
    session.expire_all()
    text = session.get(Entry, made["id"]).content
    assert text.endswith("# Kiln plan\n\nFire on Thursday.") and "status: done" in text
    rows = {(r.key, r.value): r for r in session.query(EntryProperty).filter_by(entry_id=made["id"])}
    assert ("status", "done") in rows
    assert rows[("effort", "3")].number == 3.0
    assert rows[("due", "2026-10-10")].date is not None
    assert ("status", "open") not in rows


def test_a_private_note_is_not_indexed(client, session):
    from tessellate.core import vault
    from tessellate.core.database import EntryProperty

    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    made = _note(client, "---\nsecret: yes\n---\nDiary")
    assert session.query(EntryProperty).filter_by(entry_id=made["id"]).count() == 1
    assert client.post(f"/entries/{made['id']}/privacy", json={"private": True}).status_code == 200
    assert session.query(EntryProperty).filter_by(entry_id=made["id"]).count() == 0
    client.put(f"/entries/{made['id']}", json={"content": "---\nsecret: still\n---\nDiary"})
    assert session.query(EntryProperty).filter_by(entry_id=made["id"]).count() == 0
    vault.close()


def test_a_type_adds_its_fields_to_a_new_note(client):
    made = client.post(
        "/note-types",
        json={"name": "Meeting", "icon": "users", "fields": [{"name": "attendees", "kind": "list"}, {"name": "date", "kind": "date"}]},
    )
    assert made.status_code == 201, made.text
    assert client.post("/note-types", json={"name": "meeting"}).status_code == 409
    assert client.post("/note-types", json={"name": "Bad", "fields": [{"name": "x", "kind": "colour"}]}).status_code == 422
    note = _note(client, "# Standup\n\nWhat we said.", note_type="Meeting")
    assert note["content"].startswith("---\ntype: Meeting\nattendees: []\ndate:\n---\n# Standup")
    assert note["title"] == "Standup" and note["note_type"] == "Meeting"
    got = client.get(f"/entries/{note['id']}/properties").json()
    assert got["type"] == "Meeting"
    assert [f["name"] for f in got["fields"]] == ["attendees", "date"]
    assert client.get("/note-types").json()[0]["fields"][1]["kind"] == "date"


def test_a_vault_s_frontmatter_imports_as_properties(client):
    files = [("files", ("plan.md", b"---\ncategory: Work\ntags: [kiln]\nstatus: draft\nowner: Priya\n---\n# Plan\n\nBody.", "text/markdown"))]
    body = client.post("/import/markdown", files=files).json()
    assert body["imported"] == 1
    entry = client.get(f"/entries/{body['ids'][0]}").json()
    assert entry["category"] == "Work" and entry["tags"] == ["kiln"]
    assert entry["properties"] == {"status": ["draft"], "owner": ["Priya"]}
    assert entry["title"] == "Plan"
    assert "category:" not in entry["content"]


def test_the_markdown_export_writes_one_block(client):
    import io
    import zipfile

    _note(client, NOTE)
    archive = zipfile.ZipFile(io.BytesIO(client.get("/export/markdown").content))
    text = archive.read(archive.namelist()[0]).decode()
    assert text.count("\n---\n") == 1 and text.startswith("---\n")
    assert "status: open" in text and "category:" in text


def test_the_migration_adds_the_two_tables(tmp_path):
    from tessellate.core.database_manager import DatabaseManager, _ensure_alembic_baseline

    db_path = tmp_path / "kg4.db"
    DatabaseManager(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("DROP TABLE entry_properties")
        conn.execute("DROP TABLE note_types")
        conn.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
        conn.execute("DELETE FROM alembic_version")
        conn.execute("INSERT INTO alembic_version VALUES ('c3f7a9e2d5b8')")
        conn.commit()
    finally:
        conn.close()
    _ensure_alembic_baseline(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchall() == [(_alembic_head(),)]
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"entry_properties", "note_types"} <= tables
    finally:
        conn.close()


def _alembic_head() -> str:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    return ScriptDirectory.from_config(config).get_current_head()
