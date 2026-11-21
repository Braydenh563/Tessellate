"""Plain reads of note rows that several routes share (L-world-class-820).

Each answers rows the caller then filters or shapes; the floors a caller must
add (private, draft, board) stay with it. See `repo/__init__.py` for the rules
every repository keeps.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from tessellate.core.database import LIKE_ESCAPE, Entry


def by_ids(session: Session, ids: Iterable[int]) -> list[Entry]:
    """The notes with these ids, binned and private ones included."""
    return list(session.scalars(select(Entry).where(Entry.id.in_(list(ids)))).all())


def live_by_ids(session: Session, ids: Iterable[int]) -> list[Entry]:
    """The notes with these ids that are not binned."""
    return list(session.scalars(select(Entry).where(Entry.id.in_(list(ids)), Entry.is_deleted.is_(False))).all())


def child_ids(session: Session, parent_id: int) -> list[int]:
    return list(session.scalars(select(Entry.id).where(Entry.parent_id == parent_id, Entry.is_deleted == False)))  # noqa: E712


def board_count(session: Session) -> int:
    """Live entries that carry board settings (maps and boards)."""
    return (
        session.scalar(select(func.count(Entry.id)).where(Entry.is_deleted == False, Entry.board_settings.is_not(None)))  # noqa: E712
        or 0
    )


def by_source_url(session: Session, url: str) -> Entry | None:
    return session.scalar(
        select(Entry).where(Entry.source_url == url, Entry.is_deleted.is_(False)).order_by(Entry.id).limit(1)
    )


def source_texts(session: Session) -> list[tuple[str, str | None, bool]]:
    """(source path, content, is private) of every live note that came from a file."""
    return [
        (path, content, private)
        for path, content, private in session.execute(
            select(Entry.source_path, Entry.content, Entry.is_private).where(
                Entry.source_path != "", Entry.is_deleted.is_(False)
            )
        )
    ]


def mentioning(
    session: Session,
    likes: list[str],
    limit: int,
    *,
    linked_ids: set[int] | None = None,
    except_id: int | None = None,
) -> list[Entry]:
    """Live, non-private notes whose text matches any LIKE (or whose id is in `linked_ids`), newest first.

    A private note is encrypted at rest, so its content would not match the
    LIKE anyway; the filter keeps that true by decision rather than by side effect.
    """
    matches = [Entry.content.ilike(like, escape=LIKE_ESCAPE) for like in likes]
    if linked_ids is not None:
        matches.insert(0, Entry.id.in_(linked_ids))
    where = [Entry.is_deleted.is_(False), Entry.is_private.is_(False), or_(*matches)]
    if except_id is not None:
        where.insert(0, Entry.id != except_id)
    return list(session.scalars(select(Entry).where(*where).order_by(Entry.id.desc()).limit(limit)))


def created_span(session: Session, filters) -> tuple:  # noqa: ANN001
    """(the oldest, the newest) `created_at` among the notes the filters keep; None for an empty notebook."""
    return session.query(func.min(Entry.created_at), func.max(Entry.created_at)).filter(*filters).one()
