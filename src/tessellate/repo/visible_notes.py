"""Reads of visible notes (not deleted, not private) that a chat turn binds to.

The turn's follow-on scope (`api/chat_turn.py`: `_turn_scope`, `_framed_scope`,
`_visible_elsewhere`) reads ids the client sent back and words the user typed,
so every read here keeps the bin and private floors. Reads only: see
`repo/__init__.py` (flush, never commit).
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.core.database import LIKE_ESCAPE, Entry, like_escape


def _visible():  # noqa: ANN202
    return (Entry.is_deleted == False, Entry.is_private == False)  # noqa: E712


def holding(session: Session, words: str, *, limit: int, besides: Iterable[int] = ()) -> list:
    """(id, content) of visible notes whose text holds `words`, outside `besides`."""
    query = select(Entry.id, Entry.content).where(
        *_visible(), Entry.content.ilike(f"%{like_escape(words)}%", escape=LIKE_ESCAPE)
    )
    besides = list(besides)
    if besides:
        query = query.where(Entry.id.notin_(besides))
    return session.execute(query.limit(limit)).all()


def by_ids(session: Session, ids: Iterable[int]) -> list:
    """(id, content) of the visible notes among `ids`: client input, so read again."""
    return session.execute(select(Entry.id, Entry.content).where(Entry.id.in_(list(ids)), *_visible())).all()


def recent(session: Session, *, limit: int) -> list:
    """(id, content) of the newest visible notes: what an overview with no topic tells."""
    return session.execute(select(Entry.id, Entry.content).where(*_visible()).order_by(Entry.id.desc()).limit(limit)).all()


def content_of(session: Session, note_id: int) -> str | None:
    """The text of one visible note (not a board either: the note tools' floor), or None."""
    return session.scalar(
        select(Entry.content).where(Entry.id == note_id, *_visible(), Entry.is_board == False)  # noqa: E712
    )


def written(session: Session, ids: Iterable[int]) -> dict[int, tuple[str, object]]:
    """`{id: (content, created_at)}` for the visible notes among `ids`, for a quoted answer's sources."""
    rows = session.execute(select(Entry.id, Entry.content, Entry.created_at).where(Entry.id.in_(list(ids)), *_visible()))
    return {row.id: (row.content or "", row.created_at) for row in rows}


def matching(session: Session, like: str, *, limit: int) -> list[Entry]:
    """Visible notes whose text matches the escaped LIKE pattern `like`, newest first.

    A private note is encrypted at rest, so its content would not match anyway;
    the floor is here so that stays true by decision rather than by side effect."""
    query = select(Entry).where(*_visible(), Entry.content.ilike(like, escape=LIKE_ESCAPE))
    return list(session.scalars(query.order_by(Entry.id.desc()).limit(limit)))
