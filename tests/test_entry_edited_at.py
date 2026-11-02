"""`EntryOut.edited_at`: when a person last changed what a note says.

Asked for so the notes list can sort by "recently edited" and say "edited
2h ago". `Entry.updated_at` cannot be that field: it has `onupdate=utcnow`,
so it moves when a note is merely opened (the open bumps `access_count`) or
filed by the AI, and a list sorted by it reorders itself on every click.
`edited_at` moves on a change to the text, title, tags or category, and on
nothing else. Null means never edited since it was written; a list sorts by
`edited_at ?? created_at`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from tessellate.core.database import DatabaseManager, Entry, _ensure_alembic_baseline
from tessellate.entry import manager


def _edited(client, entry_id):
    return client.get(f"/entries/{entry_id}").json()["edited_at"]


def test_a_new_note_has_not_been_edited(client):
    made = client.post("/entries", json={"content": "fresh"}).json()
    assert made["edited_at"] is None
    assert _edited(client, made["id"]) is None  # opening it is not an edit


def test_content_tags_and_category_edits_set_it(client):
    for change in ({"content": "changed"}, {"tags": ["new"]}, {"category": "Elsewhere"}):
        made = client.post("/entries", json={"content": "a note"}).json()
        out = client.put(f"/entries/{made['id']}", json=change).json()
        assert out["edited_at"] is not None, change
        assert _edited(client, made["id"]) == out["edited_at"]


def test_pinning_and_filing_do_not(client, session):
    made = client.post("/entries", json={"content": "a note"}).json()
    client.put(f"/entries/{made['id']}", json={"pinned": True})
    assert _edited(client, made["id"]) is None

    entry = session.get(Entry, made["id"])
    assert manager.record_filing(session, entry, "Filed by the AI")
    session.commit()
    assert _edited(client, made["id"]) is None


def test_the_migration_upgrades_over_the_auto_migrator(tmp_path):
    """The guard: `_add_missing_columns` has already added the column by the
    time Alembic runs, so the migration must not add it a second time."""
    db_path = tmp_path / "edited-at.db"
    DatabaseManager(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        assert "edited_at" in {row[1] for row in conn.execute('PRAGMA table_info("entries")')}
        conn.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
        conn.execute("DELETE FROM alembic_version")
        conn.execute("INSERT INTO alembic_version VALUES ('d3b7c2a91e45')")
        conn.commit()
    finally:
        conn.close()

    _ensure_alembic_baseline(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchall() == [(_alembic_head(),)]
    finally:
        conn.close()


def _alembic_head() -> str:
    """The migrations' head, read rather than written here: a pinned id goes
    stale the moment the next migration lands (two did, the same day)."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    return ScriptDirectory.from_config(config).get_current_head()


def test_a_string_default_with_a_quote_still_upgrades(tmp_path, monkeypatch):
    """Audit 1028 K21: the added column's default went into the DDL inside
    single quotes as it was, so one apostrophe broke every start."""
    from tessellate.core.database import Base

    db_path = tmp_path / "quote.db"
    DatabaseManager(db_path).engine.dispose()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute('ALTER TABLE audit_log DROP COLUMN "actor"')
        conn.commit()
    finally:
        conn.close()
    column = Base.metadata.tables["audit_log"].c.actor
    monkeypatch.setattr(column.default, "arg", "the owner's")
    DatabaseManager(db_path).engine.dispose()
    conn = sqlite3.connect(str(db_path))
    try:
        defaults = {row[1]: row[4] for row in conn.execute('PRAGMA table_info("audit_log")')}
    finally:
        conn.close()
    assert defaults["actor"] == "'the owner''s'"


def test_a_clean_quit_runs_pragma_optimize(tmp_path):
    """Audit 1028 K37: no statistics were ever gathered, so plans drifted as
    notebooks grew. `optimize` runs it; the app's lifespan calls it on quit."""
    import inspect

    from tessellate.api import app as app_module

    db = DatabaseManager(tmp_path / "opt.db")
    seen = []
    from sqlalchemy import event

    event.listen(db.engine, "before_cursor_execute", lambda *a: seen.append(a[2]))
    db.optimize()
    db.engine.dispose()
    assert "PRAGMA optimize" in seen
    source = inspect.getsource(app_module)
    assert "deps._db.optimize()" in source
