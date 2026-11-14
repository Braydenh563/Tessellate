"""The harness reads back every write before the model sees its result
(AGENT_SKILLS_REFORM Phase E, decision 4).

`contracts.py` re-reads the rows for the note, tag, category and reminder
tools. The document, board, map and skill tools returned a label and were
believed: a `create_document` whose row never landed, or a board item that
was not where the result said, read as done to the model and so to the
person. This module holds a verifier for each of those, and `check` runs the
contract's postconditions and these together, so `execute_tool` has one door.

`tests/test_tool_verifiers.py` fails on a tool in `WRITE_TOOLS` that has
neither, so a new write tool cannot ship unchecked.

Same rule as the contracts: a verifier that cannot run (a stub session in a
test) is skipped, never failed, because a fault in the checker must not cost
the person the write. Only models and config are imported here, never the
tool modules or the routes, so this file adds no edge to the import graph's
lazy cycle (`tests/test_complexity.py`).
"""

from __future__ import annotations

import logging
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core import deps
from tessellate.core.database import (
    Document,
    Entry,
    EntryLink,
    WhiteboardNode,
    WhiteboardObject,
    WhiteboardSketch,
)

from .contracts import CONTRACTS, _loggable, postcondition

_log = logging.getLogger("tessellate.tools")

Verifier = Callable[[Session, dict, dict], "str | None"]

#: Board items live in three tables; a tool names which by `kind`.
_ITEM_MODELS = {"card": WhiteboardNode, "object": WhiteboardObject, "shape": WhiteboardSketch}

#: How far a moved item may sit from where the result said, in board units.
#: The handler rounds the reported position, so an exact match would fail
#: every move to a fractional coordinate.
MOVE_TOLERANCE = 1.0


def _row(session: Session, model, row_id) -> object | None:
    try:
        return session.get(model, int(row_id))
    except (TypeError, ValueError):
        return None


def _missing(session: Session, model, ids, what: str) -> str | None:
    """The first id in `ids` with no row, said as one clause, or None."""
    for row_id in ids:
        if _row(session, model, row_id) is None:
            return f"{what} {row_id} is not there"
    return None


def _document_created(session: Session, args: dict, result: dict) -> str | None:
    document = _row(session, Document, result.get("id"))
    if document is None:
        return f"no document with id {result.get('id')} was saved"
    if str(args.get("title") or "").strip()[:200] != document.title:
        return f"document {document.id} is titled {document.title!r}, not the title asked for"
    return None


def _document_deleted(session: Session, args: dict, result: dict) -> str | None:
    document = _row(session, Document, args.get("document_id"))
    if document is not None and document.deleted_at is None:
        return f"document {args.get('document_id')} is still there"
    return None


def _card_placed(session: Session, args: dict, result: dict) -> str | None:
    card = _row(session, WhiteboardNode, result.get("card_id"))
    if card is None:
        return f"card {result.get('card_id')} is not on any board"
    if card.entry_id != result.get("note_id"):
        return f"card {card.id} shows note {card.entry_id}, not note {result.get('note_id')}"
    return None


def _link_drawn(session: Session, args: dict, result: dict) -> str | None:
    return _missing(session, WhiteboardSketch, [result.get("link_id")], "link")


def _diagram_placed(session: Session, args: dict, result: dict) -> str | None:
    ids = [card.get("card_id") for card in result.get("cards") or [] if isinstance(card, dict)]
    if not ids:
        return "the diagram placed no cards"
    return _missing(session, WhiteboardNode, ids, "card")


def _mindmap_created(session: Session, args: dict, result: dict) -> str | None:
    if _row(session, Entry, result.get("board_id")) is None:
        return f"map {result.get('board_id')} was not saved"
    if result.get("root_id") is None:
        return None  # a plain board (kind "board") starts with nothing on it
    root = _row(session, WhiteboardObject, result.get("root_id"))
    if root is None or root.board_id != result.get("board_id"):
        return f"the map's root topic {result.get('root_id')} is not on it"
    return None


def _map_from_note_made(session: Session, args: dict, result: dict) -> str | None:
    if _row(session, Entry, result.get("board_id")) is None:
        return f"map {result.get('board_id')} was not saved"
    on = session.scalar(select(func.count()).select_from(WhiteboardObject).where(WhiteboardObject.board_id == result.get("board_id"))) or 0
    if on != result.get("nodes"):
        return f"the map holds {on} topics, not the {result.get('nodes')} it reported"
    return None


def _map_node_added(session: Session, args: dict, result: dict) -> str | None:
    node = _row(session, WhiteboardObject, result.get("node_id"))
    if node is None or node.board_id != result.get("board_id"):
        return f"node {result.get('node_id')} is not on map {result.get('board_id')}"
    return None


def _item(session: Session, result: dict) -> object | None:
    model = _ITEM_MODELS.get(str(result.get("kind") or ""))
    return _row(session, model, result.get("item_id")) if model is not None else None


def _item_present(session: Session, args: dict, result: dict) -> str | None:
    if _item(session, result) is None:
        return f"{result.get('kind') or 'item'} {result.get('item_id')} is not on the board"
    return None


def _item_moved(session: Session, args: dict, result: dict) -> str | None:
    row = _item(session, result)
    if row is None:
        return f"{result.get('kind')} {result.get('item_id')} is not on the board"
    if result.get("kind") == "shape":
        # A shape's position is its path's corner, which only the board code
        # computes; that it is still there is what can be checked from here.
        return None
    try:
        far = max(abs(row.x - float(args["x"])), abs(row.y - float(args["y"])))
    except (KeyError, TypeError, ValueError):
        return None
    if far > MOVE_TOLERANCE:
        return f"{result.get('kind')} {row.id} is at {round(row.x)}, {round(row.y)}"
    return None


def _item_removed(session: Session, args: dict, result: dict) -> str | None:
    if _item(session, result) is not None:
        return f"{result.get('kind')} {result.get('item_id')} is still on the board"
    return None


def _library_placed(session: Session, args: dict, result: dict) -> str | None:
    sketches = list(result.get("sketch_ids") or [])
    objects = list(result.get("object_ids") or [])
    if not sketches and not objects:
        return "nothing was placed"
    return _missing(session, WhiteboardSketch, sketches, "shape") or _missing(
        session, WhiteboardObject, objects, "object"
    )


def _links_audited(session: Session, args: dict, result: dict) -> str | None:
    updated = result.get("updated")
    if not isinstance(updated, int) or updated < 0:
        return "it did not say how many link reasons it rewrote"
    total = session.scalar(select(func.count()).select_from(EntryLink)) or 0
    if updated > total:
        return f"it claims {updated} rewrites and the notebook has {total} links"
    return None


def _learned_checked(session: Session, args: dict, result: dict) -> str | None:
    from tessellate.ai import learned_audit_run

    retired = result.get("retired")
    if not isinstance(retired, int) or retired < 0:
        return "it did not say how many learned things it retired"
    kept = learned_audit_run.last_run(session)
    if retired and (kept["run"] != result.get("run") or len(kept["retired"]) != retired):
        return f"it claims {retired} retired and the learned list shows {len(kept['retired'])}"
    return None


def _skill_names() -> set[str]:
    stored = deps.get_config().get_preference("skills", []) or []
    return {str(skill.get("name")) for skill in stored if isinstance(skill, dict)}


def _skill_saved(session: Session, args: dict, result: dict) -> str | None:
    if str(result.get("name")) not in _skill_names():
        return f"no saved skill is called {result.get('name')!r}"
    return None


def _skill_deleted(session: Session, args: dict, result: dict) -> str | None:
    if str(result.get("name")) in _skill_names():
        return f"the skill {result.get('name')!r} is still saved"
    return None


#: The write tools `contracts.py` does not cover, each with the read that
#: proves its result. A tool in both would be checked twice; the lint keeps
#: the two tables apart.
VERIFIERS: dict[str, Verifier] = {
    "create_document": _document_created,
    "delete_document": _document_deleted,
    "add_whiteboard_card": _card_placed,
    "add_whiteboard_link": _link_drawn,
    "link_map_nodes": _link_drawn,
    "generate_diagram": _diagram_placed,
    "create_mindmap": _mindmap_created,
    "map_from_note": _map_from_note_made,
    "add_map_node": _map_node_added,
    "move_board_item": _item_moved,
    "edit_board_item": _item_present,
    "add_board_shape": _item_present,
    "restore_board_item": _item_present,
    "delete_board_item": _item_removed,
    "place_library_item": _library_placed,
    "audit_link_reasons": _links_audited,
    "check_learned": _learned_checked,
    "save_skill": _skill_saved,
    "delete_skill": _skill_deleted,
}


def has_verifier(name: str) -> bool:
    """True when the harness reads back what `name` claims to have written."""
    return name in VERIFIERS or bool(CONTRACTS.get(name, ((), ()))[1])


def check(session: Session, name: str, args: dict, result: dict) -> str | None:
    """What the call claimed and the notebook does not show, or None.

    The contracts first (they carry the note tools' wording), then this
    module's own; the sentence has the same shape either way, so the model
    reads one kind of refusal.
    """
    broken = postcondition(session, name, args, result)
    if broken or name not in VERIFIERS:
        return broken
    try:
        problem = VERIFIERS[name](session, args, result)
    except Exception:  # noqa: BLE001  # a checker's fault is not the call's
        _log.debug("verifier of %s skipped", _loggable(name), exc_info=True)
        return None
    if problem:
        return f"{name} did not take effect: {problem}. Say so rather than claim it."
    return None

