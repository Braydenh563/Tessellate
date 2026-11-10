"""A database made before Brief 7 (the event log) is upgraded for real (t20#18).

`tests/fixtures/pre_brief7_schema.sql` is a dump of a database the code of the
commit before the audit log gained `actor` and `payload` created itself (its
own `DatabaseManager`, stamped at the baseline revision), plus a few rows. The
tests open it with today's code: columns the model gained arrive, the rows
survive, the old audit row reads as a user action, and Alembic reaches head.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from tessellate.core.database import DatabaseManager, Entry, _ensure_alembic_baseline, _migrations_root

FIXTURE = Path(__file__).parent / "fixtures" / "pre_brief7_schema.sql"


def _old_db(tmp_path) -> Path:
    path = tmp_path / "old.db"
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(FIXTURE.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()
    return path


def _columns(path: Path, table: str) -> set[str]:
    conn = sqlite3.connect(str(path))
    try:
        return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
    finally:
        conn.close()


def test_the_fixture_really_predates_the_event_log(tmp_path):
    cols = _columns(_old_db(tmp_path), "audit_log")
    assert "actor" not in cols and "payload" not in cols


def test_opening_it_adds_the_columns_and_keeps_every_row(tmp_path):
    path = _old_db(tmp_path)
    DatabaseManager(path).engine.dispose()
    assert {"actor", "payload"} <= _columns(path, "audit_log")
    conn = sqlite3.connect(str(path))
    try:
        notes = conn.execute("SELECT id, content, is_deleted FROM entries ORDER BY id").fetchall()
        audit = conn.execute("SELECT action, detail, actor FROM audit_log").fetchall()
    finally:
        conn.close()
    assert notes == [(1, "Book the ferry to Hvar for June", 0), (2, "A binned note about tram times", 1)]
    assert audit == [("created", "first note", "user")]


def test_alembic_upgrades_it_to_head_without_a_duplicate_column_error(tmp_path):
    path = _old_db(tmp_path)
    DatabaseManager(path).engine.dispose()
    _ensure_alembic_baseline(path)  # the constructor skips it under pytest
    root = _migrations_root()
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    head = ScriptDirectory.from_config(cfg).get_current_head()
    conn = sqlite3.connect(str(path))
    try:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == head
    finally:
        conn.close()


def test_the_upgraded_database_serves_its_old_notes(tmp_path):
    path = _old_db(tmp_path)
    manager = DatabaseManager(path)
    try:
        with manager.session() as session:
            alive = session.query(Entry).filter(Entry.is_deleted.is_(False)).all()
            assert [e.id for e in alive] == [1]
    finally:
        manager.engine.dispose()
