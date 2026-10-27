"""Old boards keep their look under one stacking order (WHITEBOARD_PLAN
decision 43, the owner 2026-10-27: "each stroke stacks").

Before it, every drawing painted under every card whatever the numbers said,
so a board's drawings carry z values (a shape 5, a note 1) that would put
them over cards they used to sit under. Migration c4e8a1f6b2d9 moves each
board's drawings under its lowest card, frames aside, their order kept, and
does the same inside saved library stencils; the built-in stencils get it
when they are read (`drawings_under_cards`).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from sqlalchemy import create_engine

from tessellate.api.routes_board_library import _builtin_index, drawings_under_cards
from tessellate.core.database import Base

ROOT = Path(__file__).resolve().parents[1]
BEFORE = "d9b4e1a7c3f2"
REV = "c4e8a1f6b2d9"


def _config(db_path: Path) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _old_db(db_path: Path) -> None:
    """Today's tables, stamped at the revision before this one."""
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    command.stamp(_config(db_path), BEFORE)


def _insert(con: sqlite3.Connection, table: str, values: dict) -> int:
    """A row with the given values and a plain default for any other NOT NULL column."""
    for _, name, kind, notnull, default, _pk in con.execute(f"PRAGMA table_info({table})").fetchall():
        if notnull and default is None and name not in values and name != "id":
            values[name] = 0 if any(k in kind.upper() for k in ("INT", "BOOL", "FLOAT", "REAL")) else ("2026-01-01 00:00:00" if "DATE" in kind.upper() else "")
    cur = con.execute(f"INSERT INTO {table} ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})", list(values.values()))
    return cur.lastrowid


def _zs(con: sqlite3.Connection, board) -> list:
    return [r[0] for r in con.execute("SELECT z FROM whiteboard_sketches WHERE board_id IS ? ORDER BY id", (board,))]


def test_each_boards_drawings_move_under_its_lowest_card_in_their_order(tmp_path):
    db = tmp_path / "old.db"
    _old_db(db)
    con = sqlite3.connect(db)
    try:
        # Board 1: drawings 5 and 7 over a note at 1 and a box at 3; a frame at -20 is left out.
        for z in (5, 7):
            _insert(con, "whiteboard_sketches", {"board_id": 1, "data": "{}", "x": 0, "y": 0, "z": z})
        _insert(con, "whiteboard_nodes", {"board_id": 1, "entry_id": 1, "x": 0, "y": 0, "z": 1})
        _insert(con, "whiteboard_objects", {"board_id": 1, "kind": "text", "data": "{}", "x": 0, "y": 0, "z": 3})
        _insert(con, "whiteboard_objects", {"board_id": 1, "kind": "frame", "data": "{}", "x": 0, "y": 0, "z": -20})
        # Board 2: drawings already under its card; board 3: drawings and no card; the scratch board (NULL).
        _insert(con, "whiteboard_sketches", {"board_id": 2, "data": "{}", "x": 0, "y": 0, "z": -4})
        _insert(con, "whiteboard_objects", {"board_id": 2, "kind": "image", "data": "{}", "x": 0, "y": 0, "z": 0})
        _insert(con, "whiteboard_sketches", {"board_id": 3, "data": "{}", "x": 0, "y": 0, "z": 9})
        _insert(con, "whiteboard_sketches", {"board_id": None, "data": "{}", "x": 0, "y": 0, "z": 2})
        _insert(con, "whiteboard_objects", {"board_id": None, "kind": "text", "data": "{}", "x": 0, "y": 0, "z": 2})
        con.commit()
    finally:
        con.close()
    command.upgrade(_config(db), REV)
    con = sqlite3.connect(db)
    try:
        assert _zs(con, 1) == [-2, 0]
        assert _zs(con, 2) == [-4]
        assert _zs(con, 3) == [9]
        assert _zs(con, None) == [1]
        assert con.execute("SELECT COUNT(*) FROM whiteboard_sketches").fetchone()[0] == 5
    finally:
        con.close()


def test_a_saved_stencil_keeps_its_drawings_under_its_words(tmp_path):
    db = tmp_path / "old.db"
    _old_db(db)
    items = [
        {"key": "a", "kind": "sketch", "z": 5},
        {"key": "b", "kind": "sketch", "z": 6},
        {"key": "t", "kind": "object", "type": "text", "z": 1},
    ]
    con = sqlite3.connect(db)
    try:
        lib = _insert(con, "board_libraries", {"name": "Mine"})
        row = _insert(con, "board_library_items", {"library_id": lib, "kind": "element", "name": "Box", "payload": json.dumps({"box": {"w": 1, "h": 1}, "items": items, "links": []})})
        con.commit()
    finally:
        con.close()
    command.upgrade(_config(db), REV)
    con = sqlite3.connect(db)
    try:
        payload = json.loads(con.execute("SELECT payload FROM board_library_items WHERE id = ?", (row,)).fetchone()[0])
    finally:
        con.close()
    assert [i["z"] for i in payload["items"]] == [-1, 0, 1]
    assert payload["box"] == {"w": 1, "h": 1}


def test_the_built_in_stencils_paint_as_they_did() -> None:
    """Five built-in stencils hold a drawing (z 5) and a card (z 1)."""
    mixed = 0
    for entry in _builtin_index().values():
        items = (entry.get("payload") or {}).get("items") or []
        drawings = [i["z"] for i in items if i.get("kind") == "sketch"]
        cards = [i["z"] for i in items if i.get("kind") != "sketch" and i.get("type") != "frame"]
        if drawings and cards:
            mixed += 1
            assert max(drawings) < min(cards), entry.get("key")
    assert mixed >= 5
    assert drawings_under_cards([{"kind": "sketch", "z": 1}, {"kind": "object", "type": "frame", "z": 0}]) == [{"kind": "sketch", "z": 1}, {"kind": "object", "type": "frame", "z": 0}]
