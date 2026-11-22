"""The queries the timeline feed is built from (L-world-class-820).

`api/routes_timeline.py` decides the window, the kinds and the page; these
are the statements. See `repo/__init__.py` for the rules every repository keeps.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, String, func, select
from sqlalchemy.orm import Session, aliased

from tessellate.core.database import Entry, EntryDate, Space


def visible_notes() -> Select:
    """Notes and boards that are not binned; private text stays out of a view."""
    return select(Entry).where(
        Entry.is_deleted == False,  # noqa: E712
        Entry.is_private == False,  # noqa: E712
    )


def dates_of(session: Session, entry_ids: list[int]) -> list[EntryDate]:
    """Every date the notes mention, lowest id first. One query rather than one per note."""
    return list(session.scalars(select(EntryDate).where(EntryDate.entry_id.in_(entry_ids)).order_by(EntryDate.id)))


def space_names(session: Session) -> dict[str, str]:
    return {space.id: space.name for space in session.scalars(select(Space))}


def with_first_mention(query: Select):  # noqa: ANN201
    """`query` joined to each note's first mentioned date (its lowest-id row).

    Found once for the whole notebook as a grouped subquery and joined, so the
    window, the density and the page read a plain column. As correlated
    subqueries they ran per note for every use. Returns (query, the alias).
    """
    first_pick = (
        select(EntryDate.entry_id.label("entry_id"), func.min(EntryDate.id).label("pick"))
        .group_by(EntryDate.entry_id)
        .subquery("first_mention")
    )
    mention = aliased(EntryDate)
    joined = query.outerjoin(first_pick, first_pick.c.entry_id == Entry.id).outerjoin(mention, mention.id == first_pick.c.pick)
    return joined, mention


def names_a_date_between(since_wall: datetime | None, until_wall: datetime | None):  # noqa: ANN201
    """An EXISTS clause: the note names some date overlapping the window (decision 13).

    A span overlaps the window when it starts before the window ends and ends
    after it starts; a day's end is its own start.
    """
    named = [EntryDate.entry_id == Entry.id]
    named += [func.coalesce(EntryDate.until, EntryDate.at) >= since_wall] if since_wall is not None else []
    named += [EntryDate.at <= until_wall] if until_wall is not None else []
    return select(EntryDate.id).where(*named).correlate(Entry).exists()


def day_counts(session: Session, ranged: Select, mention_at) -> dict[str, int]:  # noqa: ANN001
    """Notes per day, counted in SQL (ARCH-11). Dates are stored as naive UTC text, so the day is its first ten characters."""
    day = func.substr(func.coalesce(mention_at, Entry.created_at), 1, 10, type_=String)
    rows = session.execute(
        ranged.with_only_columns(day.label("day"), func.count()).select_from(Entry).order_by(None).group_by("day")
    ).all()
    return {str(when): int(count) for when, count in rows if when}
