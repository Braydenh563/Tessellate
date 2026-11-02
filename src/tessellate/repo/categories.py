"""Categories (`Category`): the names notes are filed under.

The seventh resource behind a repository (INBOX 1499); the rules every
repository keeps are in `repo/__init__.py`. These are the reads that name or
count categories. The verbs that file, merge and rename stay in
`entry/manager.py` and `entry/moving.py` with the rules that keep a note's
space and its category in step, and the queries that select notes by their
category (the library's lists, the review queue's filter, the chat's category
match) stay with the notes they select until the entries repository exists.
"""

from __future__ import annotations

from sqlalchemy import Row, func, select
from sqlalchemy.orm import Session

from tessellate.core.database import Category, Entry


def find(session: Session, category_id: int) -> Category | None:
    return session.get(Category, category_id)


def name_of(session: Session, category_id: int | None) -> str | None:
    """The category's name, or None for no category or one that is gone."""
    if category_id is None:
        return None
    category = find(session, category_id)
    return category.name if category is not None else None


def names(session: Session) -> list[str]:
    return list(session.execute(select(Category.name)).scalars())


def all_rows(session: Session) -> list[Category]:
    """Every category, oldest first."""
    return list(session.scalars(select(Category).order_by(Category.id)))


def id_names(session: Session) -> list[Row]:
    """(id, name) of every category by id: the graph cache's fingerprint."""
    return list(session.execute(select(Category.id, Category.name).order_by(Category.id)))


def count(session: Session) -> int:
    return session.scalar(select(func.count(Category.id))) or 0


def note_counts(session: Session, *note_filters) -> list[Row]:  # noqa: ANN002
    """(name, notes) per category name for the notes `note_filters` keep,
    biggest first; a category with none of them is left out."""
    return list(
        session.execute(
            select(Category.name, func.count(Entry.id))
            .join(Entry, Entry.category_id == Category.id)
            .where(*note_filters)
            .group_by(Category.name)
            .order_by(func.count(Entry.id).desc())
        ).all()
    )


def names_by_entry(session: Session, entry_ids: list[int]) -> dict[int, str]:
    """Each note's category name; a note with none is left out."""
    if not entry_ids:
        return {}
    rows = session.execute(
        select(Entry.id, Category.name).join(Category, Category.id == Entry.category_id).where(Entry.id.in_(entry_ids))
    )
    return {entry_id: name for entry_id, name in rows}


def names_by_id(session: Session, category_ids: set[int]) -> dict[int, str]:
    if not category_ids:
        return {}
    return dict(session.execute(select(Category.id, Category.name).where(Category.id.in_(category_ids))).all())
