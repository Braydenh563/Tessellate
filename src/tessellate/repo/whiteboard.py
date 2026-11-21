"""Whiteboard: the board list's thumbnail fingerprints, read in bulk.

The rules every repository keeps are in `repo/__init__.py`: reads only, the
route owns the transaction.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import Entry, WhiteboardNode, WhiteboardObject, WhiteboardSketch


def preview_stamps(db: Session, entries: list) -> dict[int | None, list]:
    """`_preview_fingerprint`'s four (count, newest) pairs for a page of boards
    (`Entry` rows, `None` for the default board) at once: one grouped query per table instead of four per board (audit K36).
    A board with nothing on a table gets the same `(0, "None")` the
    per-board query would have returned, so both paths build equal keys."""
    wanted = {None if entry is None else entry.id for entry in entries}
    empty = (0, "None")
    out: dict[int | None, list] = {b: [empty, empty, empty, empty] for b in wanted}
    queries = [
        (i, select(model.board_id, func.count(), func.max(model.updated_at)).group_by(model.board_id))
        for i, model in enumerate((WhiteboardNode, WhiteboardSketch, WhiteboardObject))
    ]
    queries.append((3, (
        select(WhiteboardNode.board_id, func.count(), func.max(Entry.updated_at))
        .select_from(WhiteboardNode)
        .join(Entry, Entry.id == WhiteboardNode.entry_id)
        .group_by(WhiteboardNode.board_id)
    )))
    for slot, query in queries:
        for board, count, newest in db.execute(query).all():
            if board in wanted:
                out[board][slot] = (count, str(newest))
    return out


def board_words(db: Session, board_id: int, limit: int) -> list[str]:
    """What is written on a board, one line each: a map's topics and a board's
    stickies and text (an object's `content`), then the titles of the note cards
    on it. A private or deleted note's title is left out, as everywhere the
    model could read it."""
    import json

    from tessellate.entry import manager_text

    lines: list[str] = []
    for obj in db.scalars(
        select(WhiteboardObject).where(WhiteboardObject.board_id == board_id).order_by(WhiteboardObject.id)
    ):
        try:
            data = json.loads(obj.data or "{}")
        except ValueError:
            continue
        text = " ".join(str(data.get("content") or data.get("text") or "").split()) if isinstance(data, dict) else ""
        if text:
            lines.append(text[:120])
    cards = db.scalars(select(Entry).join(WhiteboardNode, WhiteboardNode.entry_id == Entry.id).where(WhiteboardNode.board_id == board_id))
    for entry in cards:
        if entry.is_deleted or entry.is_private:
            continue
        text = manager_text.readable_content(entry)
        title = manager_text.extract_title(text) or text.strip().split("\n")[0]
        if title.strip():
            lines.append(title.strip()[:120])
    return lines[:limit]


def board_objects(db: Session, board_id: int) -> list[WhiteboardObject]:
    """A board's objects (frames, text, stickies, shapes), in no set order."""
    return list(db.scalars(select(WhiteboardObject).where(WhiteboardObject.board_id == board_id)))


def board_cards(db: Session, board_id: int) -> list[tuple[WhiteboardNode, Entry | None]]:
    """A board's note cards with their notes (`None` for a note gone from the table)."""
    nodes = list(db.scalars(select(WhiteboardNode).where(WhiteboardNode.board_id == board_id)))
    return [(node, db.get(Entry, node.entry_id)) for node in nodes]


def text_objects(db: Session, board_id: int, ids: list[int]) -> list[WhiteboardObject]:
    """The text objects (stickies) among `ids` that sit on this board."""
    where = (WhiteboardObject.board_id == board_id, WhiteboardObject.id.in_(set(ids)), WhiteboardObject.kind == "text")
    return list(db.scalars(select(WhiteboardObject).where(*where)).all())


def objects_of_kinds(db: Session, board_id: int | None, kinds: tuple[str, ...]) -> list[WhiteboardObject]:
    """The board's objects of these kinds (frames for bindings, words for a name)."""
    where = (WhiteboardObject.board_id == board_id, WhiteboardObject.kind.in_(kinds))
    return list(db.scalars(select(WhiteboardObject).where(*where)).all())


def board_nodes(db: Session, board_id: int) -> list[WhiteboardNode]:
    """The board's note cards, oldest first."""
    return list(db.scalars(select(WhiteboardNode).where(WhiteboardNode.board_id == board_id).order_by(WhiteboardNode.id)).all())


def entry(db: Session, entry_id: int) -> Entry | None:
    """The note behind a card."""
    return db.get(Entry, entry_id)


def entries(db: Session, ids: list[int]) -> list[Entry]:
    """The notes behind these cards."""
    return list(db.scalars(select(Entry).where(Entry.id.in_(ids))).all()) if ids else []


def audit_event(db: Session, event_id: int):
    """One audit-log row by id, or None (the board history's narrate route)."""
    from tessellate.core.database import AuditLog

    return db.get(AuditLog, event_id)
