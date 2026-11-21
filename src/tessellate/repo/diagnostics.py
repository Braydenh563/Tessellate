"""Counts the diagnostics report reads (L-world-class-820).

See `repo/__init__.py` for the rules every repository keeps.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import Entry


def entry_counts(session: Session) -> dict[str, int]:
    """Every entry row, the binned ones and the private ones."""
    count = select(func.count(Entry.id))
    return {
        "entries": session.scalar(count) or 0,
        "entries_deleted": session.scalar(count.where(Entry.is_deleted == True)) or 0,  # noqa: E712
        "entries_private": session.scalar(count.where(Entry.is_private == True)) or 0,  # noqa: E712
    }
