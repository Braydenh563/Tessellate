"""Frames bound to a note property (L-whiteboard-12, "a kanban that edits your
notebook"). A frame's `binds: {property, value}` makes it a column: a card
whose corner lands inside writes that value to its note, through the same
properties save any edit takes (revision, conflict guard, index). The other
way, `POST /boards/{id}/binds/sync` moves a card whose note now holds another
bound frame's value into that frame; the board calls it on open, so a note
edited elsewhere moves its card the next time the board is looked at."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.core import events
from tessellate.core.database import Entry, WhiteboardNode, WhiteboardObject
from tessellate.core.deps import get_session
from tessellate.core.events import node_state
from tessellate.entry import manager_text
from tessellate.entry import properties as note_properties
from tessellate.repo.content import BOARDS

router = APIRouter()

#: Where a card lands in a frame it is moved into: under the title, then a
#: step down for each card already moved there in the same sync.
_INSET_X, _INSET_Y, _STEP_Y = 16.0, 48.0, 24.0


def bound_frames(db: Session, board_id: int | None) -> list[tuple[WhiteboardObject, dict]]:
    """The board's frames that carry a binding, each with it."""
    out = []
    rows = db.scalars(select(WhiteboardObject).where(WhiteboardObject.board_id == board_id, WhiteboardObject.kind == "frame")).all()
    for frame in rows:
        try:
            binds = (json.loads(frame.data or "{}") or {}).get("binds")
        except ValueError:
            continue
        if isinstance(binds, dict) and binds.get("property") and binds.get("value"):
            out.append((frame, binds))
    return out


def _inside(frame: WhiteboardObject, x: float, y: float) -> bool:
    fx, fy = frame.x or 0.0, frame.y or 0.0
    return fx <= x <= fx + (frame.width or 0.0) and fy <= y <= fy + (frame.height or 0.0)


def frame_at(frames: list[tuple[WhiteboardObject, dict]], x: float, y: float) -> dict | None:
    """The binding of the topmost bound frame under a card's corner."""
    hits = [(frame, binds) for frame, binds in frames if _inside(frame, x, y)]
    return max(hits, key=lambda hit: (hit[0].z or 0, hit[0].id))[1] if hits else None


def _held(found: dict[str, list[str]], prop: str) -> str:
    """A property as one string: `split` reads every value as a list."""
    return ", ".join(found.get(prop) or [])


def _value(db: Session, entry_id: int, prop: str) -> str:
    entry = db.get(Entry, entry_id)
    if entry is None:
        return ""
    found, _ = note_properties.split(manager_text.readable_content(entry))
    return _held(found, prop)


def write_binding(db: Session, entry_id: int, binds: dict) -> bool:
    """Write the frame's value to the card's note; False when it already holds it."""
    from tessellate.api import routes_entries
    from tessellate.api.schemas import EntryUpdate

    entry = db.get(Entry, entry_id)
    if entry is None:
        return False
    found, _ = note_properties.split(manager_text.readable_content(entry))
    if _held(found, binds["property"]) == binds["value"]:
        return False
    found[binds["property"]] = binds["value"]
    text = note_properties.write(manager_text.readable_content(entry), found)
    routes_entries.update_entry(entry_id, EntryUpdate(content=text), response=Response(), session=db, if_match=None)
    return True


def apply_card_binding(db: Session, node: WhiteboardNode) -> None:
    """After a card moved: its note takes the value of the bound frame it is in."""
    binds = frame_at(bound_frames(db, node.board_id), node.x or 0.0, node.y or 0.0)
    if binds:
        write_binding(db, node.entry_id, binds)


@router.post("/boards/{board_id}/binds/sync")
def sync_board_binds(board_id: int, db: Session = Depends(get_session)) -> dict:
    """Move each card whose note holds another bound frame's value into that
    frame. A card in no bound frame, or whose note names no frame's value,
    stays where it is."""
    BOARDS.writable(db, board_id)
    frames = bound_frames(db, board_id)
    moved: list[int] = []
    if not frames:
        return {"moved": moved}
    landed: dict[int, int] = {}
    for node in db.scalars(select(WhiteboardNode).where(WhiteboardNode.board_id == board_id).order_by(WhiteboardNode.id)).all():
        #: Only a card on the kanban moves: one loose on the board was put there.
        here = frame_at(frames, node.x or 0.0, node.y or 0.0)
        if here is None:
            continue
        held = _value(db, node.entry_id, here["property"])
        if held == here["value"]:
            continue
        target = next((frame for frame, binds in frames if binds["property"] == here["property"] and binds["value"] == held), None)
        if target is None:
            continue
        before = node_state(node)
        slot = landed.get(target.id, 0)
        landed[target.id] = slot + 1
        node.x = (target.x or 0.0) + _INSET_X
        node.y = min((target.y or 0.0) + _INSET_Y + slot * _STEP_Y, (target.y or 0.0) + (target.height or 0.0) - 1)
        events.record(db, "edited", "whiteboard_node", node.id, f"card on board {board_id}, moved by its note",
                      payload={"after": node_state(node), "before": before})
        moved.append(node.id)
    db.commit()
    return {"moved": moved}
