"""Sweep 1028b W30: the seeded "Default Space" is "Default space" (sentence case),
and a migration renames a stored one without touching a space the person named."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from tessellate.core.database import Base

ROOT = Path(__file__).resolve().parents[1]
BEFORE = "f1b3c5d7e9a2"


def _config(db_path: Path) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _db(tmp_path: Path, rows: list[tuple[str, str]]) -> Path:
    path = tmp_path / "t.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    command.stamp(_config(path), BEFORE)
    con = sqlite3.connect(path)
    con.execute("DELETE FROM spaces")
    for space_id, name in rows:
        con.execute("INSERT INTO spaces (id, name, icon) VALUES (?, ?, 'ph-house')", (space_id, name))
    con.commit()
    con.close()
    return path


def _names(path: Path) -> dict:
    con = sqlite3.connect(path)
    try:
        return dict(con.execute("SELECT id, name FROM spaces").fetchall())
    finally:
        con.close()


def test_the_seeded_name_is_renamed(tmp_path):
    path = _db(tmp_path, [("default", "Default Space"), ("work", "Work")])
    command.upgrade(_config(path), "head")
    assert _names(path) == {"default": "Default space", "work": "Work"}


def test_a_name_the_person_chose_is_left_alone(tmp_path):
    path = _db(tmp_path, [("default", "Home base")])
    command.upgrade(_config(path), "head")
    assert _names(path) == {"default": "Home base"}


def test_it_does_not_make_two_spaces_the_same(tmp_path):
    path = _db(tmp_path, [("default", "Default Space"), ("mine", "default space")])
    command.upgrade(_config(path), "head")
    assert _names(path)["default"] == "Default Space"


def test_downgrade_restores_the_old_name(tmp_path):
    path = _db(tmp_path, [("default", "Default Space")])
    command.upgrade(_config(path), "head")
    command.downgrade(_config(path), BEFORE)
    assert _names(path) == {"default": "Default Space"}


def test_a_fresh_notebook_seeds_the_new_name():
    text = (ROOT / "src/tessellate/core/database.py").read_text(encoding="utf-8")
    assert 'name="Default space"' in text and 'name="Default Space"' not in text
