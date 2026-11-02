"""Note properties: the index of each note's `---` block (GRAPH_PLAN KG4).

The fifth resource behind a repository (INBOX 1499); the rules every
repository keeps are in `repo/__init__.py`. The note's text is the truth and
`manager.reindex_properties` rebuilds these rows on every save, so this module
only reads: a row per value, `number` and `date` being the value read as one
when it reads. A private note has no rows at all.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, aliased

from tessellate.core.database import EntryProperty
from tessellate.repo import NotFound

MISSING = "That note has no such property."


def find(session: Session, entry_id: int, key: str) -> EntryProperty | None:
    """The note's first row for `key` (lowest id), or None."""
    return session.scalars(
        select(EntryProperty)
        .where(EntryProperty.entry_id == entry_id, EntryProperty.key == key)
        .order_by(EntryProperty.id)
        .limit(1)
    ).first()


def get(session: Session, entry_id: int, key: str) -> EntryProperty:
    row = find(session, entry_id, key)
    if row is None:
        raise NotFound(MISSING)
    return row


def page(session: Session, entry_id: int, *, limit: int, offset: int = 0) -> tuple[list[EntryProperty], int]:
    """One note's rows in the order they sit in its block, and how many it has."""
    total = session.scalar(select(func.count(EntryProperty.id)).where(EntryProperty.entry_id == entry_id)) or 0
    rows = session.scalars(
        select(EntryProperty)
        .where(EntryProperty.entry_id == entry_id)
        .order_by(EntryProperty.id)
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total


def types(session: Session) -> list[tuple[int, str]]:
    """Every note's `type` values as (note id, value), oldest row first, so a
    caller keeping the first per note keeps the one written first."""
    return [(i, v) for i, v in session.execute(
        select(EntryProperty.entry_id, EntryProperty.value)
        .where(EntryProperty.key == "type")
        .order_by(EntryProperty.id)
    )]


def meeting_dates(session: Session, entry_ids: list[int]) -> dict[int, tuple[datetime, str]]:
    """Each meeting's own date among `entry_ids` as (date, the value as
    written): a note typed Meeting whose `date:` reads as one. Two queries for
    the page; the first date row per note wins."""
    if not entry_ids:
        return {}
    typed = set(
        session.scalars(
            select(EntryProperty.entry_id).where(
                EntryProperty.entry_id.in_(entry_ids),
                EntryProperty.key == "type",
                func.lower(EntryProperty.value) == "meeting",
            )
        )
    )
    if not typed:
        return {}
    found: dict[int, tuple[datetime, str]] = {}
    for row in session.scalars(
        select(EntryProperty).where(
            EntryProperty.entry_id.in_(typed),
            EntryProperty.key == "date",
            EntryProperty.date.is_not(None),
        )
    ):
        found.setdefault(row.entry_id, (row.date, row.value))
    return found


def join_meeting_date(query: Select, entry_id) -> tuple[Select, object]:
    """`query` with each meeting's own `date:` joined on, and that column.

    The lowest-id date row of a note typed Meeting, found once for the whole
    notebook as a grouped subquery and joined on `entry_id` (a note's id
    column), so a window, a density and a page read a plain column instead of
    a correlated subquery per note.
    """
    meetings = select(EntryProperty.entry_id).where(
        EntryProperty.key == "type", func.lower(EntryProperty.value) == "meeting"
    )
    own_pick = (
        select(EntryProperty.entry_id.label("entry_id"), func.min(EntryProperty.id).label("pick"))
        .where(EntryProperty.key == "date", EntryProperty.date.is_not(None), EntryProperty.entry_id.in_(meetings))
        .group_by(EntryProperty.entry_id)
        .subquery("own_date")
    )
    own = aliased(EntryProperty)
    joined = query.outerjoin(own_pick, own_pick.c.entry_id == entry_id).outerjoin(own, own.id == own_pick.c.pick)
    return joined, own.date
