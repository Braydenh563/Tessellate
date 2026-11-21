"""The reads behind the review queue, the most-opened strip, the tidy proposals and the chart counts (L-world-class-820).

`api/routes_vision.py` builds the live-note filters and shapes the answers.
See `repo/__init__.py` for the rules every repository keeps.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import AuditLog, Category, Entry, EntryOpen


def review_page(session: Session, review_filter, limit: int) -> tuple[int, list[int]]:  # noqa: ANN001
    """(how many notes wait, the newest `limit` ids), for a ready-made filter."""
    base = select(Entry.id).outerjoin(Category, Category.id == Entry.category_id).where(review_filter)
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    ids = list(session.scalars(base.order_by(Entry.created_at.desc(), Entry.id.desc()).limit(limit)))
    return total, ids


def most_opened(session: Session, since: str, live_filters, limit: int) -> dict[int, int]:  # noqa: ANN001
    """note id to how often it was opened since the day `since`, most first."""
    opened = func.sum(EntryOpen.count).label("opened")
    rows = session.execute(
        select(EntryOpen.entry_id, opened)
        .join(Entry, Entry.id == EntryOpen.entry_id)
        .where(EntryOpen.day >= since, *live_filters)
        .group_by(EntryOpen.entry_id)
        .order_by(opened.desc(), EntryOpen.entry_id.desc())
        .limit(limit)
    ).all()
    return {entry_id: int(n) for entry_id, n in rows}


def entries_by_ids(session: Session, ids: list[int]) -> dict[int, Entry]:
    return {e.id: e for e in session.scalars(select(Entry).where(Entry.id.in_(ids)))}


def renamed_by_person(session: Session) -> set[int]:
    """Ids of categories a person renamed."""
    rows = session.scalars(
        select(AuditLog.entity_id).where(
            AuditLog.entity_type == "category",
            AuditLog.action == "edited",
            AuditLog.actor == "user",
            AuditLog.detail.like("%→%"),
        )
    )
    return {int(i) for i in rows if i is not None}


def counts_by_category(session: Session) -> dict:
    return dict(
        session.execute(
            select(Entry.category_id, func.count(Entry.id))
            .where(Entry.is_deleted == False)  # noqa: E712
            .group_by(Entry.category_id)
        ).all()
    )


def notes_where(session: Session, filters) -> list[Entry]:  # noqa: ANN001
    return list(session.scalars(select(Entry).where(*filters)))
