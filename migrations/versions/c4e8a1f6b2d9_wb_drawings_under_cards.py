"""whiteboard: drawings keep their look under one stacking order

WHITEBOARD_PLAN decision 43 (the owner, 2026-10-27: "each stroke stacks"):
a stroke now sits above or below a card by its z, where before every drawing
painted in one layer under every card whatever its z. A board's drawings
carried z values that meant nothing against the cards' (a drawn shape 5, a
note 1), so read under one order they would cover cards they used to sit
under. Each board's drawings move under its lowest card (frames aside:
decision 14 keeps frames under everything), their own order kept; the
library's saved stencils get the same. Data only: no row is added, dropped
or changed beyond `z`.

Revision ID: c4e8a1f6b2d9
Revises: d9b4e1a7c3f2
Create Date: 2026-10-27

"""
import json
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic. See the baseline migration for the
# __all__ (read by attribute name, never imported).
__all__ = ["revision", "down_revision", "branch_labels", "depends_on"]
revision: str = "c4e8a1f6b2d9"
down_revision: Union[str, Sequence[str], None] = "d9b4e1a7c3f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables(bind) -> set:  # noqa: ANN001
    return {row[0] for row in bind.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}


def _shift(top_drawing, low_card) -> int:  # noqa: ANN001
    """How far a board's drawings go down: none when there is no card or no
    drawing, or they are already all under the lowest card."""
    if top_drawing is None or low_card is None or top_drawing < low_card:
        return 0
    return int(top_drawing) - int(low_card) + 1


def _has_workspace(bind) -> bool:  # noqa: ANN001
    """`workspace_id` comes from `_add_missing_columns()` at startup, so a
    database migrated outside the app may not have it yet."""
    return all(
        "workspace_id" in {row[1] for row in bind.exec_driver_sql(f'PRAGMA table_info("{name}")')}
        for name in ("whiteboard_sketches", "whiteboard_nodes", "whiteboard_objects")
    )


def _boards(bind) -> None:  # noqa: ANN001
    #: A board is its workspace and its id; the scratch board's id is NULL,
    #: so `IS` rather than `=` matches it.
    ws = "workspace_id" if _has_workspace(bind) else "'default'"
    rows = bind.exec_driver_sql(
        f"SELECT {ws}, board_id, MAX(z) FROM whiteboard_sketches GROUP BY {ws}, board_id"
    ).fetchall()
    for workspace, board, top in rows:
        low = bind.exec_driver_sql(
            "SELECT MIN(z) FROM ("
            f" SELECT z FROM whiteboard_nodes WHERE {ws} IS ? AND board_id IS ?"
            " UNION ALL"
            f" SELECT z FROM whiteboard_objects WHERE {ws} IS ? AND board_id IS ? AND kind != 'frame')",
            (workspace, board, workspace, board),
        ).scalar()
        shift = _shift(top, low)
        if shift:
            bind.exec_driver_sql(
                f"UPDATE whiteboard_sketches SET z = z - ? WHERE {ws} IS ? AND board_id IS ?",
                (shift, workspace, board),
            )


def _stencil_items(items: list) -> list | None:
    """The same move for one saved stencil's items; None when unchanged.
    Mirrors `drawings_under_cards` in routes_board_library.py, copied so
    this migration runs the same whatever that function becomes."""
    drawings = [i for i in items if isinstance(i, dict) and i.get("kind") == "sketch"]
    cards = [i for i in items if isinstance(i, dict) and i.get("kind") != "sketch" and i.get("type") != "frame"]
    if not drawings or not cards:
        return None
    shift = _shift(max(int(i.get("z") or 0) for i in drawings), min(int(i.get("z") or 0) for i in cards))
    if not shift:
        return None
    return [{**i, "z": int(i.get("z") or 0) - shift} if isinstance(i, dict) and i.get("kind") == "sketch" else i for i in items]


def _stencils(bind) -> None:  # noqa: ANN001
    for row_id, raw in bind.exec_driver_sql("SELECT id, payload FROM board_library_items WHERE payload IS NOT NULL").fetchall():
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except ValueError:
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            continue
        items = _stencil_items(payload["items"])
        if items is not None:
            bind.exec_driver_sql(
                "UPDATE board_library_items SET payload = ? WHERE id = ?",
                (json.dumps({**payload, "items": items}), row_id),
            )


def upgrade() -> None:
    """Upgrade data."""
    bind = op.get_bind()
    have = _tables(bind)
    if {"whiteboard_sketches", "whiteboard_nodes", "whiteboard_objects"} <= have:
        _boards(bind)
    if "board_library_items" in have:
        _stencils(bind)


def downgrade() -> None:
    """Nothing to undo: the old one-layer order painted every drawing under
    every card whatever its z, so the lowered z values look the same there."""
