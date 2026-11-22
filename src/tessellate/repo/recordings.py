"""Recordings: the library's page, one row by id, and the sealed-space probe.

The rules every repository keeps are in `repo/__init__.py`: the route owns the
transaction. The files, the transcription runs and the bin's purge stay in
`core/recordings.py`; this module is only the rows' reads and the one add.
"""

from __future__ import annotations

import json

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from tessellate.core.database import LIKE_ESCAPE, Recording, like_escape


def find(session: Session, recording_id: int) -> Recording | None:
    """The row by id through the session's filters (a binned one is seen only
    under `including_binned`)."""
    return session.get(Recording, recording_id)


def find_by_query(session: Session, recording_id: int) -> Recording | None:
    """The row by a query rather than the identity map, as the background
    runs read it in their own session."""
    return session.scalar(select(Recording).where(Recording.id == recording_id).limit(1))


def page(session: Session, needle: str, offset: int, limit: int) -> tuple[list[Recording], int]:
    """Saved recordings newest first: one page and the whole count. `needle`
    keeps those whose name or transcript has the words; the transcript is
    stored as JSON, so a quote in the words is an escaped quote there."""
    where = [Recording.state == "saved"]
    if needle:
        stored = json.dumps(needle, ensure_ascii=False)[1:-1]
        where.append(
            or_(
                Recording.title.ilike(f"%{like_escape(needle)}%", escape=LIKE_ESCAPE),
                Recording.segments.ilike(f"%{like_escape(stored)}%", escape=LIKE_ESCAPE),
            )
        )
    total = session.scalar(select(func.count(Recording.id)).where(*where)) or 0
    rows = list(
        session.scalars(select(Recording).where(*where).order_by(Recording.created_at.desc()).offset(offset).limit(limit))
    )
    return rows, int(total)


def add(session: Session, row: Recording) -> Recording:
    """Store a new row and give it its id (flushed, not committed)."""
    session.add(row)
    session.flush()
    return row


def space_of(session: Session, recording_id: int) -> str | None:
    """The live row's space, read raw: a raw statement is not narrowed by the
    space filter (`database._add_workspace_filter`), so a row in a sealed
    space still answers."""
    return session.execute(
        text("SELECT workspace_id FROM recordings WHERE id = :id AND deleted_at IS NULL"), {"id": recording_id}
    ).scalar()
