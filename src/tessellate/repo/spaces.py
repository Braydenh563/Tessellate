"""Spaces: the one place the `spaces` table is read, and the per-space counts
(row 3a). The wholesale delete and restore walk every model and stay in
`api/routes_spaces.py` until they move here in a later step. See
`repo/__init__.py` for the rules every repository keeps.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from tessellate.core.database import Document, Entry, Space
from tessellate.core.deps import impersonate_workspace


def ids(session: Session) -> set[str]:
    return {row[0] for row in session.query(Space.id).all()}


def all_spaces(session: Session) -> list[Space]:
    return session.query(Space).all()


def find(session: Session, space_id: str) -> Space | None:
    return session.get(Space, space_id)


def counts(session: Session, space_id: str) -> dict[str, int]:
    """What deleting the space would take with it; read across every workspace."""
    with impersonate_workspace(session, "all"):
        notes = session.query(func.count(Entry.id)).filter(Entry.workspace_id == space_id).scalar() or 0
        documents = session.query(func.count(Document.id)).filter(Document.workspace_id == space_id).scalar() or 0
    return {"notes": notes, "documents": documents}
