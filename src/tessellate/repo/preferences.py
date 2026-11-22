"""What the AI has been told to remember: the preference rows (L-world-class-820).

See `repo/__init__.py` for the rules every repository keeps.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import UserPreference


def page(session: Session, limit: int, offset: int) -> tuple[int, list[UserPreference]]:
    """(the total, one page newest first)."""
    total = session.scalar(select(func.count(UserPreference.id))) or 0
    rows = list(
        session.scalars(
            select(UserPreference)
            .order_by(UserPreference.created_at.desc(), UserPreference.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return total, rows


def active(session: Session) -> list[UserPreference]:
    return list(session.scalars(select(UserPreference).where(UserPreference.active == True)))  # noqa: E712


def add(session: Session, content: str) -> UserPreference:
    row = UserPreference(content=content)
    session.add(row)
    return row


def delete(session: Session, row: UserPreference) -> None:
    session.delete(row)
