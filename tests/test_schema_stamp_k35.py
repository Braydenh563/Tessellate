"""Audit 1028 K35: a start that finds the schema as it stamped it skips the column scan.

`_add_missing_columns` ran `PRAGMA table_info` for every model table at every
start. The database now keeps a fingerprint of the model's columns and of the
tables as SQLite holds them (`PRAGMA user_version`); a start that finds the same
fingerprint has nothing to add, and any change (a dropped column, a new model
column) changes it, so the scan runs again and restamps.
"""

from __future__ import annotations

import sqlite3

from tessellate.core.database_manager import DatabaseManager


def _spy(monkeypatch):
    calls = []
    original = DatabaseManager._add_missing_columns

    def wrapper(self):
        calls.append(1)
        return original(self)

    monkeypatch.setattr(DatabaseManager, "_add_missing_columns", wrapper)
    return calls


def test_a_second_start_with_nothing_changed_skips_the_column_scan(tmp_path, monkeypatch):
    path = tmp_path / "stamp.db"
    calls = _spy(monkeypatch)
    DatabaseManager(path).engine.dispose()
    assert calls == [1]  # a new database has no stamp yet: scanned once, then stamped
    conn = sqlite3.connect(str(path))
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] > 0
    finally:
        conn.close()
    DatabaseManager(path).engine.dispose()
    DatabaseManager(path).engine.dispose()
    assert calls == [1]


def test_a_dropped_column_changes_the_stamp_and_comes_back(tmp_path, monkeypatch):
    path = tmp_path / "drop.db"
    DatabaseManager(path).engine.dispose()
    conn = sqlite3.connect(str(path))
    try:
        conn.execute('ALTER TABLE audit_log DROP COLUMN "actor"')
        conn.commit()
    finally:
        conn.close()
    calls = _spy(monkeypatch)
    DatabaseManager(path).engine.dispose()
    assert calls == [1]
    conn = sqlite3.connect(str(path))
    try:
        names = {row[1] for row in conn.execute('PRAGMA table_info("audit_log")')}
    finally:
        conn.close()
    assert "actor" in names
    DatabaseManager(path).engine.dispose()
    assert calls == [1]  # restamped: the next start is quiet again


def test_the_stamp_reads_the_models_columns_and_types(tmp_path):
    """A column added to a model changes the fingerprint, so the next start scans."""
    signature = DatabaseManager._model_signature()
    assert "audit_log(" in signature and "actor " in signature
