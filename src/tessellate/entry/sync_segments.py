"""Sync as log shipping: a segment out of one notebook, into another (WORLD_CLASS_PLAN B6).

The decisions are numbered in the plan; this module is decisions 1, 2, 3, 5,
7 and 8. In short: a segment is every note whose events in the audit log
fall after the receiver's cursor, each as its whole current state, so a
compacted run ships as the snapshot it already is. The receiver compares
each note's state with its own: the same is nothing to do, a difference is
settled by the later `updated_at`, and a text that loses is kept in the
note's History first. Each note's apply commits on its own and is a no-op
the second time, so a segment cut off part way is simply applied again;
the caller moves its cursor only after the last note (`sync_pull.pull`).

Private notes travel as the ciphertext in their column and land as it:
the key never leaves (decision 5).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core import events
from tessellate.core.database import AuditLog, Entry, EntryRevision, Space, impersonate_workspace
from tessellate.entry import manager, sync_keys

FORMAT = 1
#: Notes per segment; a longer log answers `more` and is pulled in turns.
MAX_NOTES = 200
#: `client_key` prefix of a note that came from another computer.
KEY_PREFIX = "sync:"
DAMAGED = "A sync segment arrived damaged or cut off; nothing from it was applied."
_FIELDS = {"sid": str, "content": str, "tags": list, "category": str, "space": str,
           "is_private": bool, "is_deleted": bool, "updated_at": str}


class SegmentError(ValueError):
    """A segment refused whole, before any write; the message is the Settings sentence."""


def sync_actor(device: str) -> str:
    """The audit actor of a change that came from `device`."""
    return f"sync:{device}"


def note_sid(entry: Entry, device: str) -> str:
    """A note's name across computers: `<device>:<id>` where it was written (decision 2)."""
    key = entry.client_key or ""
    return key[len(KEY_PREFIX):] if key.startswith(KEY_PREFIX) else f"{device}:{entry.id}"


def _iso(value: datetime | None) -> str | None:
    return _utc(value).isoformat() if value else None


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _when(text: str | None) -> datetime | None:
    try:
        return _utc(datetime.fromisoformat(text)) if text else None
    except ValueError:
        return None


def note_state(session: Session, entry: Entry, device: str) -> dict[str, Any]:
    """The whole note as a segment carries it: values, never a diff."""
    return {
        "sid": note_sid(entry, device),
        "content": entry.content,
        "tags": events.tags_of(entry),
        "category": manager.category_name_for(session, entry),
        "space": entry.workspace_id or "default",
        "is_private": bool(entry.is_private),
        "is_deleted": bool(entry.is_deleted),
        "deleted_at": _iso(entry.deleted_at),
        "archived_at": _iso(entry.archived_at),
        "updated_at": _iso(entry.updated_at) or "",
    }


def digest(notes: list) -> str:
    return hashlib.sha256(json.dumps(notes, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _changed(session: Session, since: int, top: int, peer: str) -> list[tuple[int, int]]:
    """(note id, its last event id) for notes changed after `since`, oldest first;
    a change `peer` itself caused is not echoed back to it."""
    last = func.max(AuditLog.id)
    return list(session.execute(
        select(AuditLog.entity_id, last)
        .where(AuditLog.entity_type == "entry", AuditLog.entity_id.is_not(None),
               AuditLog.id > since, AuditLog.id <= top, AuditLog.actor != sync_actor(peer))
        .group_by(AuditLog.entity_id).order_by(last).limit(MAX_NOTES + 1)
    ).all())


def _shipped(entry: Entry | None) -> bool:
    """Boards and notes sealed by a private space stay home in this slice (decision 1)."""
    return entry is not None and not entry.is_board and not entry.sealed_by_space


def export_segment(session: Session, device: str, since: int, peer: str) -> dict[str, Any]:
    """Every note changed after `since` in this notebook's log, for `peer`."""
    top = session.scalar(select(func.max(AuditLog.id))) or 0
    with impersonate_workspace(session, ""):  # every space: no request's view applies here
        rows = _changed(session, max(since, 0), top, peer)
        more = len(rows) > MAX_NOTES
        rows = rows[:MAX_NOTES]
        notes = [note_state(session, e, device) for e in (session.get(Entry, i) for i, _ in rows) if _shipped(e)]
    upto = rows[-1][1] if more else max(top, since)
    return {"format": FORMAT, "device": device, "since": since, "upto": upto, "more": more,
            "notes": notes, "digest": digest(notes)}


def _valid_note(item: object) -> bool:
    if not isinstance(item, dict) or not all(isinstance(item.get(k), t) for k, t in _FIELDS.items()):
        return False
    return ":" in item["sid"] and _when(item["updated_at"]) is not None


def check(segment: object, me: str) -> list[dict]:
    """The segment's notes, or SegmentError before anything is written (decision 8)."""
    if not isinstance(segment, dict) or segment.get("format") != FORMAT:
        raise SegmentError(DAMAGED)
    notes, upto = segment.get("notes"), segment.get("upto")
    if not isinstance(notes, list) or not isinstance(upto, int) or segment.get("digest") != digest(notes):
        raise SegmentError(DAMAGED)
    if segment.get("device") == me or not isinstance(segment.get("device"), str):
        raise SegmentError("That segment came from this computer; nothing was applied.")
    if not all(_valid_note(item) for item in notes):
        raise SegmentError(DAMAGED)
    return notes


def _find(session: Session, me: str, sid: str) -> Entry | None:
    device, _, local = sid.partition(":")
    if device == me:
        return session.get(Entry, int(local)) if local.isdigit() else None
    return session.scalars(select(Entry).where(Entry.client_key == KEY_PREFIX + sid)).first()


def _space(session: Session, item: dict) -> str:
    """The note's own space if this notebook has one by that id, else the default."""
    return item["space"] if session.get(Space, item["space"]) is not None else "default"


def _set_state(session: Session, entry: Entry, item: dict) -> None:
    """Write the whole state; ciphertext stays ciphertext, sealed with this key when `sync_keys.opened` could."""
    entry.content = item["content"]
    entry.tags = json.dumps(item["tags"])
    entry.category_id = manager.get_or_create_category(session, item["category"], workspace_id=entry.workspace_id).id
    entry.is_private = item["is_private"]
    entry.is_deleted = item["is_deleted"]
    entry.deleted_at = _when(item.get("deleted_at"))
    entry.archived_at = _when(item.get("archived_at"))
    session.flush()
    if not entry.is_private:
        manager.record_dates(session, entry)
        manager.reindex_properties(session, entry)
    # Last, after anything above that touched the row: the sender's time, not
    # this computer's, so the next comparison of the two is like with like.
    entry.updated_at = _when(item["updated_at"])
    session.flush()


def _create(session: Session, item: dict) -> None:
    space = _space(session, item)
    entry = Entry(content="", client_key=KEY_PREFIX + item["sid"], workspace_id=space)
    session.add(entry)
    session.flush()
    _set_state(session, entry, item)
    manager.log_action(session, "created", "entry", entry.id, "from the other computer",
                       payload={"after": events.entry_state(entry)})


def _words(state: dict) -> str | None:
    """The words to compare: in the clear for a private note opened with both keys (decision 12)."""
    return state["plain"] if "plain" in state else state["content"]


def _comparable(state: dict) -> tuple:
    return (_words(state), tuple(state["tags"]), state["category"], state["is_private"],
            state["is_deleted"], bool(state.get("archived_at")))


def _theirs_win(entry: Entry, item: dict, me: str, peer: str) -> bool:
    """The later `updated_at` wins the whole note; on a tie, the larger device id (decision 3)."""
    mine, theirs = _utc(entry.updated_at), _when(item["updated_at"])
    return theirs > mine or (theirs == mine and peer > me)


def _keep_theirs_as_version(session: Session, entry: Entry, item: dict) -> None:
    """The other computer's text, kept in this note's History rather than lost."""
    session.add(EntryRevision(entry_id=entry.id, content=item["content"], tags=json.dumps(item["tags"])))
    manager.log_action(session, "revised", "entry", entry.id, "the other computer's version")


def _apply_one(session: Session, me: str, peer: str, item: dict, both: sync_keys.Keys | None = None) -> str:
    entry = _find(session, me, item["sid"])
    if entry is None:
        _create(session, item)
        return "applied"
    mine = note_state(session, entry, me)
    if "plain" in item:
        mine["plain"] = sync_keys.local_plain(entry.content, both)
    if _comparable(mine) == _comparable(item):
        return "same"
    if _theirs_win(entry, item, me, peer):
        if _words(mine) != _words(item):
            manager.record_revision(session, entry)
        was = events.entry_state(entry)
        _set_state(session, entry, item)
        manager.log_action(session, "edited", "entry", entry.id, "from the other computer",
                           payload=events.changed(was, events.entry_state(entry)))
        return "applied"
    if _words(mine) != _words(item):
        _keep_theirs_as_version(session, entry, item)
        return "conflicts"
    return "same"


def apply_segment(session: Session, me: str, segment: dict, both: sync_keys.Keys | None = None) -> dict[str, int]:
    """Apply a checked segment, one committed note at a time; counts by outcome.

    `both` (the other computer's data key and this one's) reseals its private notes here."""
    notes = check(segment, me)
    peer = segment["device"]
    report = {"applied": 0, "same": 0, "conflicts": 0}
    with events.acting_as(sync_actor(peer)), impersonate_workspace(session, ""):
        for item in notes:
            report[_apply_one(session, me, peer, sync_keys.opened(item, both), both)] += 1
            session.commit()
    return report
