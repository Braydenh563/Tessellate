"""Redo of an AI-change undo (L805), split from `events` to keep it under its size cap.

`events.undo` writes `restored` events; `redo` here takes them back.
"""

from __future__ import annotations

import threading
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


def _edits_after(session: Session, rows: list[AuditLog]) -> dict[int, int]:
    """Per `restored` row, the events on its note after it, but its own redo: one query for all rows."""
    if not rows:
        return {}
    later = session.execute(
        select(AuditLog.id, AuditLog.entity_type, AuditLog.entity_id, AuditLog.action, AuditLog.payload).where(
            AuditLog.entity_id.in_({row.entity_id for row in rows}),
            AuditLog.id > min(row.id for row in rows),
            AuditLog.action.notin_(sorted(QUIET_ACTIONS)),
        )
    ).all()
    counts: dict[int, int] = {}
    for row in rows:
        counts[row.id] = sum(
            1
            for other_id, kind, entity_id, action, payload in later
            if kind == row.entity_type
            and entity_id == row.entity_id
            and other_id > row.id
            and not (action == "redone" and isinstance(payload, dict) and payload.get("redid") == [row.id])
        )
    return counts


def _redo_fields(payload: dict) -> dict[str, Any]:
    target = {k: v for k, v in (payload.get("before") or {}).items() if k in _UNDOABLE_ENTRY_FIELDS}
    if "content" in target and not _readable_now(target["content"]):
        target.pop("content")
    return target


def _redo_status(row: AuditLog, entry: Entry | None, taken: set[int], edits: int, force: bool) -> tuple[str, dict[str, Any]]:
    """One `restored` event's redo: its status and the fields.

    A binned or private note is left alone (review 5899353774): a redo would
    write a bin's or a vault's note from the event log, and `changed` would
    keep its words there in the clear."""
    payload = row.payload if isinstance(row.payload, dict) else {}
    if row.id in taken:
        return "already redone", {}
    if not [i for i in payload.get("undid") or [] if isinstance(i, int)]:
        return "not undoable", {}
    if edits and not force:
        return "changed since", {}
    if entry is None:
        return "gone", {}
    if entry.is_deleted:
        return "binned", {}
    if entry.is_private:
        return "private", {}
    target = _redo_fields(payload)
    return ("redo" if target else "no values recorded"), target


def _redo_taken(session: Session, restored_ids: list[int]) -> set[int]:
    taken: set[int] = set()
    for payload in session.scalars(
        select(AuditLog.payload).where(AuditLog.action == "redone", AuditLog.id > min(restored_ids, default=0))
    ):
        if isinstance(payload, dict):
            taken.update(i for i in payload.get("redid") or [] if isinstance(i, int))
    return taken


#: Check, write and commit as one step: two redos of the same undo (a double
#: press, two tabs) could both read "not yet redone" before either wrote.
_LOCK = threading.Lock()


def redo(session: Session, restored_ids: list[int], *, apply: bool = False, force: bool = False) -> dict[str, Any]:
    """Take an undo back (L805): re-apply what `undo` reversed.

    `restored_ids` are the `restored` events an applied undo returned. Each
    one's recorded `before` (the values the AI had set) goes back, unless the
    note changed again after the undo ("changed since", unless `force`). Each
    note gets one `redone` event naming the `restored` one in `redid`, which
    makes the AI's events live again for a later undo. An applied redo
    commits under `_LOCK`; a dry run leaves the session as it was.
    """
    if not apply:
        return _redo(session, restored_ids, apply=False, force=force)
    with _LOCK:
        result = _redo(session, restored_ids, apply=True, force=force)
        session.commit()
    return result


def _redo(session: Session, restored_ids: list[int], *, apply: bool, force: bool) -> dict[str, Any]:
    rows = list(
        session.scalars(
            select(AuditLog).where(AuditLog.id.in_(restored_ids), AuditLog.action == "restored").order_by(AuditLog.id)
        )
    )
    taken = _redo_taken(session, restored_ids)
    edits = _edits_after(session, rows)
    items: list[dict[str, Any]] = []
    redone = 0
    for row in rows:
        entry = session.get(Entry, row.entity_id) if row.entity_type == "entry" else None
        status, target = _redo_status(row, entry, taken, edits.get(row.id, 0), force)
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
