"""The paging and wording steps of `list_notes`, split out of `tool_read._list_notes`.

One step per function (the tag page, the "no such category" hint, the filter
description) so the tool itself reads as filter, page, describe.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.ai.tools._common import _visible
from tessellate.core.database import Category, Entry
from tessellate.entry import manager


def page_of_notes(session: Session, filters: list, tag: str, offset: int, limit: int) -> tuple[list, int, bool]:
    """The page of notes, the count matching, and whether more follow."""
    query = select(Entry).where(*_visible(*filters))
    rows = list(
        session.scalars(
            query.order_by(Entry.created_at.desc(), Entry.id.desc())
            # Over-fetch when a tag filter is on, because the exact tag match
            # below can only remove rows, never add them.
            .offset(offset).limit(limit + 1 if not tag else (limit + 1) * 4)
        )
    )
    if tag:
        wanted = tag.lower()
        rows = [e for e in rows if wanted in {t.lower() for t in manager.entry_tags(e)}]
    has_more = len(rows) > limit
    rows = rows[:limit]
    if not tag:
        return rows, session.scalar(select(func.count(Entry.id)).where(*_visible(*filters))) or 0, has_more
    # An exact count needs the same per-row check, so it can't be a
    # SQL count(). Cheap enough: tags, not content.
    total = sum(
        1
        for e in session.scalars(select(Entry).where(*_visible(*filters)))
        if tag.lower() in {t.lower() for t in manager.entry_tags(e)}
    )
    return rows, total, offset + len(rows) < total


def category_exists(session: Session, name: str) -> bool:
    """Is `name` a category (any case) or the uncategorised bucket?"""
    if name == manager.UNCATEGORISED:
        return True
    return session.scalar(select(Category.id).where(func.lower(Category.name) == name.lower())) is not None


def unknown_category_hint(session: Session, category: str) -> str | None:
    """A name that is not a category matches nothing, on purpose; a model
    that guessed "notes" needs to be told that, and shown the real ones."""
    if category_exists(session, category):
        return None
    known = ", ".join(f"“{c['name']}”" for c in manager.all_categories(session)[:12])
    return (
        f"There is no category called “{category}”, so nothing matched. "
        + (f"The categories that exist are {known}. " if known else "")
        + "Call list_notes without `category` to see every note."
    )


def describe_filters(category: str, tag: str, since_days: int | None) -> str:
    return ", ".join(
        part
        for part in (category, f"#{tag}" if tag else "", f"last {since_days} days" if since_days is not None else "")
        if part
    )
