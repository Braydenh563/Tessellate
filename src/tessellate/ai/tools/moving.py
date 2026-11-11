"""The `move_notes` tool: file notes under a category, or send them to a space.

Bulk re-filing was the one organising job the agent could not do (BACKLOG 14,
OPEN row 1374). It uses `entry/moving.py`, the same code the Move buttons and
the Spaces menu use, so a note moved by Atlas is moved exactly as one moved by
hand. It is marked destructive: the app shows what will move and asks before it
runs. It is undoable: the result carries the call that puts every note back
(its old category and whether a person had filed it, or its old space).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import Entry, Space
from tessellate.entry import manager, moving

from ._common import ToolError

#: Notes one call may move. A whole category is a `merge_categories`; this is
#: for a chosen handful, and a bigger list is a sign the ids were guessed.
MAX_MOVE = 100


def _note_ids(args: dict) -> list[int]:
    ids: list[int] = []
    for value in args.get("ids") or []:
        try:
            ids.append(int(value))
        except (TypeError, ValueError) as exc:
            raise ToolError(f"“{value}” is not a note id.") from exc
    ids = list(dict.fromkeys(ids))
    if not ids:
        raise ToolError("No note ids were given.")
    if len(ids) > MAX_MOVE:
        raise ToolError(f"Move at most {MAX_MOVE} notes at a time; {len(ids)} were given.")
    return ids


def _live_notes(session: Session, ids: list[int], binned: bool = False) -> list[Entry]:
    """The notes by id; `binned` also takes those in the bin (an Undo files them back, they stay binned)."""
    query = select(Entry).where(Entry.id.in_(ids))
    entries = list(session.scalars(query if binned else query.where(Entry.is_deleted.is_(False))))
    found = {e.id for e in entries}
    missing = [i for i in ids if i not in found]
    if missing:
        shown = ", ".join(f"#{i}" for i in missing[:8])
        raise ToolError(f"No note with the id {shown}. Nothing was moved.")
    return entries


def _find_space(session: Session, wanted: str) -> Space:
    text = wanted.strip()
    found = session.get(Space, text) or session.scalar(select(Space).where(func.lower(Space.name) == text.lower()))
    if found is None:
        known = ", ".join(f"“{s.name}”" for s in session.scalars(select(Space)).all()[:12])
        raise ToolError(f"There is no space called “{wanted}”." + (f" The ones that exist are {known}." if known else ""))
    return found


def _plural(count: int) -> str:
    return f"{count} note{'' if count == 1 else 's'}"


def _put_back(session: Session, args: dict) -> dict | None:
    """An undo's own call: the arguments the move returned, applied in reverse."""
    categories = args.get("restore_categories")
    spaces = args.get("restore_spaces")
    if not categories and not spaces:
        return None
    count = 0
    if isinstance(categories, list):
        groups: dict[tuple[str, bool], list[int]] = {}
        for row in categories:
            groups.setdefault((str(row.get("category") or manager.UNCATEGORISED), bool(row.get("user_filed"))), []).append(int(row["id"]))
        for (name, filed), note_ids in groups.items():
            entries = _live_notes(session, note_ids)
            count += len(moving.to_category(session, entries, name, filed))
    if isinstance(spaces, dict):
        by_space: dict[str, list[int]] = {}
        for note_id, space_id in spaces.items():
            by_space.setdefault(str(space_id), []).append(int(note_id))
        for space_id, note_ids in by_space.items():
            count += moving.to_space(session, space_id, note_ids)["moved"]
    return {"restored": count, "label": f"ph:arrow-u-up-left Put {_plural(count)} back"}


def _describe(session: Session, name: str, description: str) -> None:
    """A category an Undo made again gets its old description back (one that has its own is left alone)."""
    if description.strip():
        row = manager.get_or_create_category(session, name)
        if not row.description:
            row.description = description.strip()[:500]
            session.commit()


def _move_notes(session: Session, args: dict) -> dict:
    """Move notes into a category (by name, made when new) or into a space."""
    restored = _put_back(session, args)
    if restored is not None:
        return restored
    ids = _note_ids(args)
    category = str(args.get("category") or "").strip()
    space = str(args.get("space") or "").strip()
    if bool(category) == bool(space):
        raise ToolError("Say where they go: either a category or a space, not both.")
    entries = _live_notes(session, ids, bool(args.get("include_binned")))
    if category:
        try:
            previous = moving.to_category(session, entries, category)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        _describe(session, category, str(args.get("description") or ""))
        if not previous:
            return {"moved": 0, "category": category, "label": f"ph:folder Already in “{category}”"}
        return {
            "moved": len(previous),
            "category": category,
            "ids": [row["id"] for row in previous],
            "label": f"ph:folder Moved {_plural(len(previous))} to “{category}”",
            "undo": {"tool": "move_notes", "arguments": {"ids": [row["id"] for row in previous], "restore_categories": previous}},
        }
    target = _find_space(session, space)
    try:
        result = moving.to_space(session, target.id, ids)
    except (ValueError, LookupError) as exc:
        raise ToolError(str(exc)) from exc
    if not result["moved"]:
        return {"moved": 0, "space": target.name, "label": f"ph:squares-four Already in “{target.name}”"}
    return {
        "moved": result["moved"],
        "space": target.name,
        "ids": [int(i) for i in result["from"]],
        "label": f"ph:squares-four Moved {_plural(result['moved'])} to the space “{target.name}”",
        "undo": {"tool": "move_notes", "arguments": {"ids": [int(i) for i in result["from"]], "restore_spaces": result["from"]}},
    }
