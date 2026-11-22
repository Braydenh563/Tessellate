"""Counts the diagnostics report reads (L-world-class-820).

See `repo/__init__.py` for the rules every repository keeps.
"""

from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from tessellate.core.database import Attachment, Entry, MediaUpload


def entry_counts(session: Session) -> dict[str, int]:
    """Every entry row, the binned ones and the private ones."""
    count = select(func.count(Entry.id))
    return {
        "entries": session.scalar(count) or 0,
        "entries_deleted": session.scalar(count.where(Entry.is_deleted == True)) or 0,  # noqa: E712
        "entries_private": session.scalar(count.where(Entry.is_private == True)) or 0,  # noqa: E712
    }


def kind_counts(session: Session) -> dict[str, int]:
    """Every live row, then the three kinds a person counts separately (notes, drafts, boards).

    Settings, About said "96 notes" for a notebook whose dashboard said 44: the
    other 52 were boards and drafts. The same split the dashboard uses.
    """
    live = Entry.is_deleted == False  # noqa: E712
    count = select(func.count(Entry.id))
    return {
        "entries": session.scalar(count.where(live)) or 0,
        "notes": session.scalar(count.where(live, Entry.is_board == False, Entry.is_draft == False)) or 0,  # noqa: E712
        "drafts": session.scalar(count.where(live, Entry.is_board == False, Entry.is_draft == True)) or 0,  # noqa: E712
        "boards": session.scalar(count.where(live, Entry.is_board == True)) or 0,  # noqa: E712
    }


def file_counts(session: Session) -> dict[str, int]:
    return {
        "media": session.scalar(select(func.count(MediaUpload.id))) or 0,
        "attachments": session.scalar(select(func.count(Attachment.id))) or 0,
    }


def note_count(session: Session) -> int:
    return (
        session.scalar(
            select(func.count(Entry.id)).where(
                Entry.is_deleted == False, Entry.is_board == False, Entry.is_draft == False  # noqa: E712
            )
        )
        or 0
    )


def integrity_rows(session: Session) -> list[str]:
    return [str(row[0]) for row in session.execute(text("PRAGMA integrity_check")).fetchall()]
