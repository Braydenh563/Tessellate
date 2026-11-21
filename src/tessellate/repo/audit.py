"""The activity log's reads and its one slice delete (L-world-class-820).

`api/routes_settings.py` shapes these rows into the viewer, the CSV and the
feed. See `repo/__init__.py` for the rules every repository keeps.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import AuditLog, Entry


def events_page(session: Session, row_id: int | None, entity_type: str, limit: int) -> list[AuditLog]:
    query = select(AuditLog)
    if row_id is not None:
        query = query.where(AuditLog.id == row_id)
    elif entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    return list(session.scalars(query.order_by(AuditLog.id.desc()).limit(limit)))


def not_private(query):  # noqa: ANN001, ANN201
    """Drop every event about a private note, and the vault's own.

    The file leaves the app, and a private note exists so that nothing about
    what it says does. An event on one carries its title or a clip of it in
    `detail`; the vault's events (unlocking, re-keying) say that private notes
    exist and when they were opened. Neither is part of a hand-over file.

    Two ways an event is about a private note: the note is still there and
    private (looked up by id), or it was purged, and its id matches nothing
    any more. A purge seals the events it leaves behind with a `private` flag
    in their payload (`manager_purge.seal_private_events`), and that flag is the
    second test. `is_(True)` rather than `== True`, so an event with no
    payload at all (SQL null) is kept rather than dropped by a null compare.
    """
    private_ids = select(Entry.id).where(Entry.is_private == True)  # noqa: E712
    return query.where(
        AuditLog.entity_type != "vault",
        ~(AuditLog.entity_type.in_(("entry", "note", "entries")) & AuditLog.entity_id.in_(private_ids)),
        ~AuditLog.payload["private"].as_boolean().is_(True),
    )


def export_page(session: Session, entity_type: str, limit: int, offset: int) -> tuple[int, list[AuditLog]]:
    """(the filtered set's size, one page of it oldest first), private notes' events left out."""
    query = not_private(select(AuditLog))
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    return total, list(session.scalars(query.order_by(AuditLog.id).limit(limit).offset(offset)))


def feed(
    session: Session, since: int, types: list[str], quiet_actions: list[str] | None, tail: int, limit: int
) -> list[AuditLog]:
    """Events after `since`, oldest first; `tail` takes the newest that many instead.
    `quiet_actions` is the list to leave out, or None to keep them all."""
    query = select(AuditLog).where(AuditLog.id > since)
    if types:
        query = query.where(AuditLog.entity_type.in_(types))
    if quiet_actions is not None:
        query = query.where(AuditLog.action.notin_(quiet_actions))
    if tail:
        return list(session.scalars(query.order_by(AuditLog.id.desc()).limit(tail)))[::-1]
    return list(session.scalars(query.order_by(AuditLog.id.asc()).limit(limit)))


def clear_type(session: Session, entity_type: str) -> int:
    return session.query(AuditLog).filter(AuditLog.entity_type == entity_type).delete()
