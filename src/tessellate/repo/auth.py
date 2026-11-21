"""The sign-in rows: the one user, the vault and the notes a re-key walks (L-world-class-820).

See `repo/__init__.py` for the rules every repository keeps.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.core.database import Entry, User, Vault


def user(session: Session) -> User | None:
    return session.scalar(select(User))


def vault(session: Session) -> Vault | None:
    return session.scalar(select(Vault))


def every_entry(session: Session) -> list[Entry]:
    """All notes, the binned and private ones too (a re-key walks them all); the caller sets the workspace floor."""
    return list(session.scalars(select(Entry)))
