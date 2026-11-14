"""Frames bound to a note property (L-whiteboard-12, "a kanban that edits your
notebook"). A frame's `binds: {property, value}` makes it a column: a card
whose corner lands inside writes that value to its note, through the same
properties save any edit takes (revision, conflict guard, index). The other
way, `POST /boards/{id}/binds/sync` moves a card whose note now holds another
bound frame's value into that frame; the board calls it on open, so a note
edited elsewhere moves its card the next time the board is looked at."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from tessellate.repo import whiteboard as whiteboard_repo
from sqlalchemy.orm import Session

from tessellate.core import events
from tessellate.core.database import WhiteboardNode, WhiteboardObject
from tessellate.core.deps import get_session
from tessellate.core.events import node_state
from tessellate.entry import manager, manager_text
from tessellate.entry import properties as note_properties
from tessellate.repo.content import BOARDS

router = APIRouter()
log = logging.getLogger(__name__)

#: Where a card lands in a frame it is moved into: under the title, then a
#: step down for each card already moved there in the same sync.
_INSET_X, _INSET_Y, _STEP_Y = 16.0, 48.0, 24.0


def bound_frames(db: Session, board_id: int | None) -> list[tuple[WhiteboardObject, dict]]:
    """The board's frames that carry a binding, each with it."""
    out = []
    rows = whiteboard_repo.objects_of_kinds(db, board_id, ("frame",))
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


def _readable(entry) -> str | None:  # noqa: ANN001
    """The note's text, or None while it is a locked private note: its
    readable text is then a placeholder, which must never be written back."""
    if entry is None or manager.note_is_sealed(entry.is_private):
        return None
    return manager_text.readable_content(entry)


def _value(entry, prop: str) -> str | None:  # noqa: ANN001
    """The note's value for `prop`; None when the note cannot be read."""
    text = _readable(entry)
    return None if text is None else _held(note_properties.split(text)[0], prop)


def write_binding(db: Session, entry_id: int, binds: dict) -> bool:
    """Write the frame's value to the card's note; False when it already holds
    it, is locked, or changed under this write (the version is passed, so an
    edit made meanwhile is kept and this card is skipped, never overwritten)."""
    from tessellate.api import routes_entries
    from tessellate.api.edit_conflicts import content_hash
    from tessellate.api.schemas import EntryUpdate

    entry = whiteboard_repo.entry(db, entry_id)
    text = _readable(entry)
    if text is None:
        return False
    found, _ = note_properties.split(text)
    if _held(found, binds["property"]) == binds["value"]:
        return False
    found[binds["property"]] = binds["value"]
    update = EntryUpdate(content=note_properties.write(text, found), base_hash=content_hash(text))
    try:
        routes_entries.update_entry(entry_id, update, response=Response(), session=db, if_match=None)
    except HTTPException as err:
        db.rollback()
        log.info("frame binding skipped note %s: %s", entry_id, err.status_code)
        return False
    return True


def apply_card_binding(db: Session, node: WhiteboardNode) -> None:
    """After a card moved: its note takes the value of the bound frame it is in."""
    binds = frame_at(bound_frames(db, node.board_id), node.x or 0.0, node.y or 0.0)
    if not binds:
        return
    #: The card's own save is already committed: a binding that fails is logged
    #: and skipped, it never turns that save into an error.
    try:
        write_binding(db, node.entry_id, binds)
    except Exception:  # noqa: BLE001
        db.rollback()
        log.warning("frame binding failed for note %s", node.entry_id, exc_info=True)


def _target(frames: list[tuple[WhiteboardObject, dict]], node: WhiteboardNode, entry) -> WhiteboardObject | None:  # noqa: ANN001
    """The bound frame this card's note now names, when it sits in another one."""
    #: Only a card on the kanban moves: one loose on the board was put there.
    here = frame_at(frames, node.x or 0.0, node.y or 0.0)
    if here is None:
        return None
    held = _value(entry, here["property"])
    if held is None or held == here["value"]:
        return None
    return next((frame for frame, binds in frames if binds["property"] == here["property"] and binds["value"] == held), None)


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
    nodes = whiteboard_repo.board_nodes(db, board_id)
    notes = {entry.id: entry for entry in whiteboard_repo.entries(db, [node.entry_id for node in nodes])}
    for node in nodes:
        target = _target(frames, node, notes.get(node.entry_id))
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
