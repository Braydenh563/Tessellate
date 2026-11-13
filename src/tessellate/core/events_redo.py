"""Redo of an AI-change undo (L805), split from `events` to keep it under its size cap.

`events.undo` writes `restored` events; `redo` here takes them back.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.core.database import AuditLog, Entry
from tessellate.core.events import (
    _UNDOABLE_ENTRY_FIELDS,
    ACTOR_USER,
    QUIET_ACTIONS,
    _readable_now,
    _write_fields,
    acting_as,
    changed,
    entry_state,
    record,
)


def _edited_since(session: Session, row: AuditLog) -> int:
    """Events on the note after this `restored` one, but its own redo."""
    return sum(
        1
        for action, other in session.execute(
            select(AuditLog.action, AuditLog.payload).where(
                AuditLog.entity_type == row.entity_type,
                AuditLog.entity_id == row.entity_id,
                AuditLog.id > row.id,
                AuditLog.action.notin_(sorted(QUIET_ACTIONS)),
            )
        )
        if not (action == "redone" and isinstance(other, dict) and other.get("redid") == [row.id])
    )


def _redo_fields(payload: dict) -> dict[str, Any]:
    target = {k: v for k, v in (payload.get("before") or {}).items() if k in _UNDOABLE_ENTRY_FIELDS}
    if "content" in target and not _readable_now(target["content"]):
        target.pop("content")
    return target


def _redo_status(session: Session, row: AuditLog, taken: set[int], force: bool) -> tuple[str, Entry | None, dict[str, Any]]:
    """One `restored` event's redo: its status, the note and the fields."""
    payload = row.payload if isinstance(row.payload, dict) else {}
    if row.id in taken:
        return "already redone", None, {}
    if not [i for i in payload.get("undid") or [] if isinstance(i, int)]:
        return "not undoable", None, {}
    if _edited_since(session, row) and not force:
        return "changed since", None, {}
    entry = session.get(Entry, row.entity_id) if row.entity_type == "entry" else None
    if entry is None:
        return "gone", None, {}
    target = _redo_fields(payload)
    return ("redo" if target else "no values recorded"), entry, target


def _redo_taken(session: Session, restored_ids: list[int]) -> set[int]:
    taken: set[int] = set()
    for payload in session.scalars(
        select(AuditLog.payload).where(AuditLog.action == "redone", AuditLog.id > min(restored_ids, default=0))
    ):
        if isinstance(payload, dict):
            taken.update(i for i in payload.get("redid") or [] if isinstance(i, int))
    return taken


def redo(session: Session, restored_ids: list[int], *, apply: bool = False, force: bool = False) -> dict[str, Any]:
    """Take an undo back (L805): re-apply what `undo` reversed.

    `restored_ids` are the `restored` events an applied undo returned. Each
    one's recorded `before` (the values the AI had set) goes back, unless the
    note changed again after the undo ("changed since", unless `force`). Each
    note gets one `redone` event naming the `restored` one in `redid`, which
    makes the AI's events live again for a later undo. The caller commits.
    """
    rows = list(
        session.scalars(
            select(AuditLog).where(AuditLog.id.in_(restored_ids), AuditLog.action == "restored").order_by(AuditLog.id)
        )
    )
    taken = _redo_taken(session, restored_ids)
    items: list[dict[str, Any]] = []
    redone = 0
    for row in rows:
        status, entry, target = _redo_status(session, row, taken, force)
        item: dict[str, Any] = {"entity_type": row.entity_type, "entity_id": row.entity_id, "restored": row.id, "status": status}
        items.append(item)
        if status != "redo" or entry is None:
            continue
        item["fields"] = sorted(target)
        if not apply:
            continue
        undid = [i for i in row.payload.get("undid") if isinstance(i, int)]
        was = entry_state(entry)
        _write_fields(session, entry, target)
        with acting_as(ACTOR_USER):
            record(
                session,
                "redone",
                "entry",
                entry.id,
                detail=f"redid {len(undid)} change(s)"[:200],
                payload={**changed(was, entry_state(entry)), "redid": [row.id], "undid": undid},
            )
        redone += 1
    if apply:
        session.flush()
    return {"dry_run": not apply, "redone": redone, "items": items}
