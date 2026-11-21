"""The scans behind a note's references: the boards it sits on and the notes that name it (L-world-class-820).

`api/routes_entries_refs.py` turns these rows into reference cards. See
`repo/__init__.py` for the rules every repository keeps.
"""

from __future__ import annotations

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from tessellate.core.database import Entry, WhiteboardNode, WhiteboardObject


def boards_holding_cards(session: Session, wanted: set[int]) -> list[tuple[int, int | None, Entry]]:
    """(note id, board id, board) for every card of these notes on a live board, in card order."""
    return [
        tuple(row)
        for row in session.execute(
            select(WhiteboardNode.entry_id, WhiteboardNode.board_id, Entry)
            .join(Entry, Entry.id == WhiteboardNode.board_id)
            .where(WhiteboardNode.entry_id.in_(wanted), Entry.is_deleted.is_(False))
            .order_by(WhiteboardNode.id)
        ).all()
    ]


def boards_holding_note_objects(session: Session, wanted: set[int]) -> list[tuple[int | None, Entry, str | None]]:
    """(board id, board, the object's JSON) for every map `note` object that refers to one of these notes."""
    return [
        tuple(row)
        for row in session.execute(
            select(WhiteboardObject.board_id, Entry, WhiteboardObject.data)
            .join(Entry, Entry.id == WhiteboardObject.board_id)
            .where(
                WhiteboardObject.kind == "note",
                func.json_extract(WhiteboardObject.data, "$.ref_id").in_(wanted),
                Entry.is_deleted.is_(False),
            )
            .order_by(WhiteboardObject.id)
        ).all()
    ]


def scan_notes(session: Session, flags: list, phrases: list[str] | None) -> list:
    """Rows of (id, content, one match flag per `flags`) for live, non-private notes where any flag holds, newest first.

    `phrases`, when given, narrows the scan to notes the full-text index
    finds for any of them (one phrase per flag); None reads every note.
    A private note is encrypted at rest, so its content could not match the
    LIKE anyway; the filter keeps that true by decision rather than by side effect.
    """
    where = [Entry.is_deleted.is_(False), Entry.is_private.is_(False), or_(*flags)]
    if phrases is not None:
        where.append(
            Entry.id.in_(
                text(
                    " UNION ".join(
                        f"SELECT rowid FROM entries_fts WHERE entries_fts MATCH :p{i}" for i in range(len(phrases))
                    )
                ).bindparams(**{f"p{i}": phrase for i, phrase in enumerate(phrases)})
            )
        )
    return list(
        session.execute(
            select(Entry.id, Entry.content, *[f.label(f"m{i}") for i, f in enumerate(flags)])
            .where(*where)
            .order_by(Entry.id.desc())
        )
    )
