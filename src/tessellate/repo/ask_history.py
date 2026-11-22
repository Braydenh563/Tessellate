"""The Ask history's rows: the browsable list, its counts and the notes a turn cites (L-world-class-820).

`api/routes_ask_history.py` shapes these into summaries. See
`repo/__init__.py` for the rules every repository keeps.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import LIKE_ESCAPE, AskTurn, Entry, like_escape


def page(session: Session, pinned_only: bool, term: str, limit: int, offset: int) -> tuple[int, list[AskTurn]]:
    """(the filtered total, one page): pinned first, then newest."""
    query = select(AskTurn)
    if pinned_only:
        query = query.where(AskTurn.pinned == True)  # noqa: E712
    if term:
        like = f"%{like_escape(term)}%"
        query = query.where(AskTurn.question.ilike(like, escape=LIKE_ESCAPE) | AskTurn.answer.ilike(like, escape=LIKE_ESCAPE))
    ordered = query.order_by(AskTurn.pinned.desc(), AskTurn.created_at.desc())
    total = session.scalar(select(func.count()).select_from(ordered.subquery())) or 0
    return total, list(session.scalars(ordered.limit(limit).offset(offset)).all())


def counts(session: Session) -> tuple[int, int]:
    """(every turn, the pinned ones)."""
    total = session.scalar(select(func.count(AskTurn.id))) or 0
    pinned = session.scalar(select(func.count(AskTurn.id)).where(AskTurn.pinned == True)) or 0  # noqa: E712
    return total, pinned


def visible_notes(session: Session, ids: Iterable[int]) -> dict[int, Entry]:
    """The cited notes that are neither binned nor private, by id."""
    return {
        e.id: e
        for e in session.scalars(select(Entry).where(Entry.id.in_(list(ids))))
        if not e.is_deleted and not e.is_private
    }


def clearable(session: Session, keep_pinned: bool) -> list[AskTurn]:
    query = select(AskTurn)
    if keep_pinned:
        query = query.where(AskTurn.pinned == False)  # noqa: E712
    return list(session.scalars(query).all())
