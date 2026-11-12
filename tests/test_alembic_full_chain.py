"""The whole migration chain, run from the baseline revision (audit 2026-10-10, item 1).

`test_alembic_baseline.py` proves the stamp; the per-migration tests prove one
step each. Nothing ran every revision in order on a database that holds data,
which is what a person updating from an old release is. This builds a database
at the baseline revision, puts a note in it, upgrades to head, and asserts the
note survived and the result has the same columns `create_all()` would build.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from tessellate.core.database import Base
from tessellate.core.database_manager import DatabaseManager, _ensure_alembic_baseline

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "8a8a14407cc0"


def _config(db_path: Path) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _columns(db_path: Path) -> dict[str, set[str]]:
    con = sqlite3.connect(db_path)
    try:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {t: {r[1] for r in con.execute(f"PRAGMA table_info({t})")} for t in tables if t != "alembic_version"}
    finally:
        con.close()


def test_the_chain_has_one_head():
    config = _config(Path("unused.db"))
    assert len(ScriptDirectory.from_config(config).get_heads()) == 1


def test_baseline_to_head_keeps_a_note_and_lands_on_the_models_columns(tmp_path):
    old = tmp_path / "old.db"
    command.upgrade(_config(old), BASELINE)
    con = sqlite3.connect(old)
    try:
        have = {r[1] for r in con.execute("PRAGMA table_info(entries)")}
        values = {"content": "kept across the chain", "created_at": "2026-01-01 00:00:00", "updated_at": "2026-01-01 00:00:00"}
        values = {k: v for k, v in values.items() if k in have}
        # Any NOT NULL column the baseline has beyond these gets a plain default.
        for _, name, kind, notnull, default, _pk in con.execute("PRAGMA table_info(entries)").fetchall():
            if notnull and default is None and name not in values and name != "id":
                values[name] = 0 if "INT" in kind.upper() or "BOOL" in kind.upper() else ""
        con.execute(
            f"INSERT INTO entries ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})",
            list(values.values()),
        )
        con.commit()
    finally:
        con.close()

    # What a real update does on launch: the model's create_all() and the
    # additive auto-migrator run first (tables born after the baseline exist
    # only through them), then Alembic walks the stamped revision to head.
    DatabaseManager(old)
    _ensure_alembic_baseline(old)

    con = sqlite3.connect(old)
    try:
        assert con.execute("SELECT content FROM entries").fetchall() == [("kept across the chain",)]
        assert con.execute("SELECT version_num FROM alembic_version").fetchall() == [
            (ScriptDirectory.from_config(_config(old)).get_current_head(),)
        ]
    finally:
        con.close()

    fresh = tmp_path / "fresh.db"
    DatabaseManager(fresh)
    migrated, built = _columns(old), _columns(fresh)
    missing = {t: sorted(built[t] - migrated.get(t, set())) for t in built if built[t] - migrated.get(t, set())}
    assert missing == {}, f"a database migrated from the baseline lacks what a fresh one has: {missing}"
    assert set(built) <= set(migrated)
    assert Base.metadata.tables  # the models were imported


def _stamp_at(db_path: Path, revision: str) -> None:
    con = sqlite3.connect(db_path)
    try:
        con.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
        con.execute("DELETE FROM alembic_version")
        con.execute("INSERT INTO alembic_version VALUES (?)", (revision,))
        con.commit()
    finally:
        con.close()


def test_an_update_that_will_migrate_takes_a_safety_copy_first(tmp_path):
    """Audit 2026-10-10, item 8: a launcher update that pulls a migration ran
    it straight on the only copy of the notebook; the nightly backup might be a
    day old. A database stamped behind the code now gets a copy first, and one
    already at head (every ordinary launch) gets none."""
    db_path = tmp_path / "tessellate.db"
    DatabaseManager(db_path)
    _stamp_at(db_path, "d3b7c2a91e45")  # behind: later revisions are pending
    _ensure_alembic_baseline(db_path)
    copies = sorted((tmp_path / "backups").glob("tessellate-*.db"))
    assert len(copies) == 1, "a migration was pending and no safety copy was taken"
    assert sqlite3.connect(copies[0]).execute("SELECT version_num FROM alembic_version").fetchall() == [("d3b7c2a91e45",)]

    _ensure_alembic_baseline(db_path)  # now at head: an ordinary launch
    assert len(list((tmp_path / "backups").glob("tessellate-*.db"))) == 1
