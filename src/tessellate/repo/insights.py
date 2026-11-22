"""The note reads behind the dashboard stats, heatmap, digests and anniversaries (L-world-class-820).

`api/routes_insights.py` shapes these into numbers and sentences. See
`repo/__init__.py` for the rules every repository keeps.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import Entry


def _notes():  # noqa: ANN202
    """Notes only: not binned, not a draft, not a board (the one count the app shows)."""
    return (Entry.is_deleted == False, Entry.is_draft == False, Entry.is_board == False)  # noqa: E712


def total_and_oldest(session: Session):  # noqa: ANN201
    """(the note count, the oldest note's day) in one statement (L-world-class-352)."""
    return session.execute(select(func.count(Entry.id), func.min(Entry.created_at)).where(*_notes())).one()


def created_since(session: Session, since: datetime) -> list[datetime]:
    """Only the day is read, so only the column is (a note loaded whole was 204 ms on 5,000)."""
    return list(session.scalars(select(Entry.created_at).where(*_notes(), Entry.created_at >= since)))


def on_this_day(session: Session, now: datetime, limit: int = 5) -> list[Entry]:
    """Notes written on today's day of the month, at least 28 days ago; never a private one."""
    return list(
        session.scalars(
            select(Entry)
            .where(
                Entry.is_deleted == False,  # noqa: E712
                Entry.is_private == False,  # noqa: E712
                Entry.created_at <= now - timedelta(days=28),
                func.strftime("%d", Entry.created_at) == f"{now.day:02d}",
            )
            .order_by(Entry.id)
            .limit(limit)
        )
    )


def shared_since(session: Session, cutoff: datetime, limit: int | None = None) -> list[Entry]:
    """Non-private notes written since `cutoff`, oldest first (they go to the AI)."""
    query = select(Entry).where(
        Entry.is_deleted == False,  # noqa: E712
        Entry.is_private == False,  # noqa: E712
        Entry.created_at >= cutoff,
    )
    if limit:
        query = query.order_by(Entry.created_at).limit(limit)
    return list(session.scalars(query))
