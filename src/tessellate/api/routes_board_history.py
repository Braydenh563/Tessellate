"""A board's time machine (the features audit W2; WHITEBOARD_PLAN decision 33).

A board's items each have an event log (`routes_whiteboard.py`'s "the event
log for a board"): every card, drawing and object records `created`,
`edited` and `deleted` with whole field values. A note has a History sheet
that reads its log back; a board had nothing, so "what did this board look
like an hour ago" had no answer short of pressing Undo until it did, and
none at all across a reload. Three reads of that log:

- `GET /whiteboard/history`: the board's changes as moments, newest first,
  each a run of events no longer than `SESSION_SECONDS` from end to start,
  with how many items it added, changed and took away.
- `GET /whiteboard/history/{event_id}`: every item as it was straight after
  that event, in the shape `GET /whiteboard/` answers, so the board draws it.
- `POST /whiteboard/history/{event_id}/restore`: the board (or only the items
  named) put back to that moment in one transaction: rows made, changed and
  removed to match, each with its own event, so the restore is itself in the
  history and the client records it as one Undo step.

**Which items are the board's.** Every item whose events name this board
(`after.board_id`, or `before.board_id` on a delete), and every row on it now.
An item with no events at all (a duplicated board's copies, a generated or
imported map) is taken to have been there from the start, as it was now; an
item whose first event is not `created` was there before its log began, as
that event's `before` says. A library placement used to record one board
event naming no item; it records each item's `created` now
(`routes_board_library.place_library_item`), so a placed item replays like
any other. One placed before that is read as there from the start.

**Compacted history** (`events.compact`): an event older than ninety days may
have lost its values to a snapshot after it. A moment inside such a run
cannot be drawn honestly, so its preview and restore answer 410 rather than
show a board that never existed; the moment is still listed (`kept: false`).
"""

from __future__ import annotations

import json
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from tessellate.core import events
from tessellate.core.database import AuditLog, Entry, WhiteboardNode, WhiteboardObject, WhiteboardSketch
from tessellate.core.deps import get_session

router = APIRouter(prefix="/whiteboard", tags=["whiteboard"])

#: The three kinds of item a board holds: the client's kind, the event log's
#: entity type, the table.
KINDS = {
    "node": ("whiteboard_node", WhiteboardNode),
    "sketch": ("whiteboard_sketch", WhiteboardSketch),
    "object": ("whiteboard_object", WhiteboardObject),
}
KIND_OF_TYPE = {etype: kind for kind, (etype, _) in KINDS.items()}

#: A moment is a run of events at most this long, end to start: one sitting's
#: worth of edits reads as one step on the slider rather than forty.
SESSION_SECONDS = 120
MOMENTS_PAGE = 60

#: The fields a restore writes back, per kind. `id` and `board_id` are never
#: taken from the past: the row stays on this board under its own id.
FIELDS = {
    "node": ("entry_id", "x", "y", "z", "width", "height", "rotation", "group_id", "locked", "comments", "hidden"),
    "sketch": ("data", "x", "y", "z", "group_id"),
    "object": ("kind", "data", "x", "y", "z", "width", "height", "rotation", "group_id", "parent_id"),
}


def _board_param(board_id: int | None) -> int | None:
    """0 and None are both the unnamed scratch board, as elsewhere."""
    return board_id or None


def _names_board(column: str, board_id: int | None):
    """An event whose payload's `column` (after or before) names this board."""
    path = f"$.{column}.board_id"
    if board_id is None:
        return sqlfunc.json_type(AuditLog.payload, path) == "null"
    return sqlfunc.json_extract(AuditLog.payload, path) == board_id


def _current_rows(db: Session, board_id: int | None) -> dict[str, object]:
    out: dict[str, object] = {}
    for kind, (_, model) in KINDS.items():
        where = model.board_id.is_(None) if board_id is None else model.board_id == board_id
        for row in db.scalars(select(model).where(where)):
            out[f"{kind}:{row.id}"] = row
    return out


def _state_of(kind: str, row) -> dict:
    if kind == "node":
        return events.node_state(row)
    if kind == "sketch":
        return events.sketch_state(row)
    return events.object_state(row)


def _board_events(db: Session, board_id: int | None, current: dict[str, object]) -> dict[str, list[AuditLog]]:
    """Every event of every item that is or was on this board, by item key,
    oldest first."""
    ids: dict[str, set[int]] = {kind: set() for kind in KINDS}
    for key in current:
        kind, raw = key.split(":")
        ids[kind].add(int(raw))
    named = db.execute(
        select(AuditLog.entity_type, AuditLog.entity_id).where(
            AuditLog.entity_type.in_([etype for etype, _ in KINDS.values()]),
            or_(_names_board("after", board_id), _names_board("before", board_id)),
        )
    )
    for etype, entity_id in named:
        if entity_id is not None:
            ids[KIND_OF_TYPE[etype]].add(int(entity_id))
    out: dict[str, list[AuditLog]] = {}
    for kind, (etype, _) in KINDS.items():
        wanted = sorted(ids[kind])
        for start in range(0, len(wanted), 500):
            chunk = wanted[start : start + 500]
            rows = db.scalars(
                select(AuditLog)
                .where(AuditLog.entity_type == etype, AuditLog.entity_id.in_(chunk))
                .order_by(AuditLog.id.asc())
            )
            for row in rows:
                out.setdefault(f"{kind}:{row.entity_id}", []).append(row)
    #: **Only this board's part of each log.** SQLite gives a deleted row's id
    #: to the next row made (no AUTOINCREMENT), so one id's log can hold an
    #: item from another board before this one: each event is placed by the
    #: board its payload names, or by the one before it when it names none
    #: (a compacted row names nothing: before any board is named, it waits for
    #: the first one that is).
    for key, rows in list(out.items()):
        kept, where, waiting = [], None, []
        for row in rows:
            payload = row.payload or {}
            named = False
            for side in ("after", "before"):
                value = payload.get(side)
                if isinstance(value, dict) and "board_id" in value:
                    where, named = value["board_id"], True
                    break
            if not named and where is None and not kept:
                waiting.append(row)
                continue
            if where == board_id:
                kept.extend(waiting)
                kept.append(row)
            waiting = []
        if kept:
            out[key] = kept
        else:
            del out[key]
    return out


def _is_delete(row: AuditLog) -> bool:
    after = (row.payload or {}).get("after")
    return row.action == "deleted" or after == events.DELETED


def _states_at(
    board_id: int | None, current: dict[str, object], logs: dict[str, list[AuditLog]], event_id: int
) -> tuple[dict[str, dict], bool]:
    """Each item's state straight after `event_id`, for the items on this
    board then; and whether every one of them is known exactly (False when a
    compacted run hides one)."""
    known = True
    states: dict[str, dict] = {}
    for key in set(current) | set(logs):
        kind = key.split(":")[0]
        rows = logs.get(key, [])
        row_now = current.get(key)
        if not rows:
            if row_now is not None:
                states[key] = _state_of(kind, row_now)
            continue
        first = rows[0]
        present = first.action != "created"
        state: dict = {}
        unknown = False
        if present:
            #: There before its log began: as its first event's `before` says,
            #: or failing that as it is now (the nearest thing known).
            before = (first.payload or {}).get("before")
            if isinstance(before, dict):
                state = dict(before)
            elif row_now is not None:
                state = _state_of(kind, row_now)
            else:
                continue
        for row in rows:
            if row.id > event_id:
                break
            payload = row.payload or {}
            if events.is_compacted(row):
                unknown = True
                if row.action == "created":
                    present = True
                elif _is_delete(row):
                    present = False
                continue
            if _is_delete(row):
                present, state, unknown = False, {}, False
                continue
            after = payload.get("after")
            if isinstance(after, dict):
                #: A `created` starts the row afresh: SQLite hands a deleted
                #: row's id to the next row made (no AUTOINCREMENT), so one
                #: id's log can hold two items, the second starting here.
                if payload.get(events.COMPACTED) or row.action == "created":
                    state, unknown = dict(after), False
                else:
                    state.update(after)
                present = True
        if not present:
            continue
        if unknown:
            known = False
            continue
        if state.get("board_id", board_id) != board_id:
            continue
        states[key] = state
    return states, known


def _moments(rows: list[AuditLog]) -> list[dict]:
    """Newest first: a moment closes when the next older event is more than
    `SESSION_SECONDS` before the moment's newest."""
    out: list[dict] = []
    current: dict | None = None
    for row in rows:
        if current is None or current["_end"] - row.created_at > timedelta(seconds=SESSION_SECONDS):
            current = {
                "id": row.id, "first_id": row.id, "at": row.created_at.isoformat(), "_end": row.created_at,
                "count": 0, "added": 0, "changed": 0, "removed": 0, "actors": set(), "kept": True,
            }
            out.append(current)
        current["first_id"] = row.id
        current["count"] += 1
        if row.action == "created":
            current["added"] += 1
        elif _is_delete(row):
            current["removed"] += 1
        else:
            current["changed"] += 1
        current["actors"].add(row.actor or "user")
        if events.is_compacted(row):
            current["kept"] = False
    for moment in out:
        moment.pop("_end")
        moment["actors"] = sorted(moment["actors"])
    return out


def _require_board(db: Session, board_id: int | None) -> None:
    if board_id is None:
        return
    entry = db.get(Entry, board_id)
    if entry is None or entry.is_deleted:
        raise HTTPException(status_code=404, detail="That board could not be found.")


@router.get("/history")
def board_history(
    board_id: int | None = None,
    before: int | None = None,
    limit: int = Query(default=MOMENTS_PAGE, ge=1, le=200),
    db: Session = Depends(get_session),
) -> dict:
    """The board's changes as moments, newest first, a page at a time
    (`before`: the oldest moment's `first_id` from the last page)."""
    board_id = _board_param(board_id)
    _require_board(db, board_id)
    current = _current_rows(db, board_id)
    logs = _board_events(db, board_id, current)
    rows = sorted((row for rows in logs.values() for row in rows), key=lambda r: r.id, reverse=True)
    if before is not None:
        rows = [row for row in rows if row.id < before]
    moments = _moments(rows)
    return {"moments": moments[:limit], "more": len(moments) > limit, "session_seconds": SESSION_SECONDS}


def _row_out(kind: str, key: str, state: dict) -> dict | None:
    item_id = int(key.split(":")[1])
    if kind == "object":
        try:
            data = json.loads(state.get("data") or "{}")
        except (TypeError, ValueError):
            return None
        return {**{f: state.get(f) for f in FIELDS["object"]}, "data": data, "board_id": state.get("board_id"), "id": item_id}
    return {**{f: state.get(f) for f in FIELDS[kind]}, "board_id": state.get("board_id"), "id": item_id}


#: **Named snapshots** (Brief 77, WHITEBOARD_PLAN "Deepened 2026-10-10" row
#: 4: draw.io's revision list). A snapshot is a name on the board's newest
#: event, kept in the board's own settings: the event log already holds the
#: board as it was then (`board_at`) and puts it back (`restore_board`), so a
#: name is all a revision needs. Registered before `/history/{event_id}`,
#: which would take "snapshots" for an id.
SNAPSHOTS_MAX = 50


class SnapshotBody(BaseModel):
    board_id: int
    name: str | None = Field(default=None, max_length=120)


def _board_settings(entry: Entry) -> dict:
    try:
        parsed = json.loads(entry.board_settings or "{}")
    except (TypeError, ValueError):
        parsed = {}
    return parsed if isinstance(parsed, dict) else {}


def _snapshot_board(db: Session, board_id: int) -> Entry:
    entry = db.get(Entry, board_id)
    if entry is None or entry.is_deleted:
        raise HTTPException(status_code=404, detail="That board could not be found.")
    return entry


@router.get("/history/snapshots")
def list_snapshots(
    board_id: int,
    response: Response,
    limit: int = Query(default=SNAPSHOTS_MAX, ge=1, le=SNAPSHOTS_MAX),
    db: Session = Depends(get_session),
) -> dict:
    """The board's named snapshots, newest first, up to `limit` (the most a
    board keeps is `SNAPSHOTS_MAX`, so the default is all of them)."""
    entry = _snapshot_board(db, board_id)
    snaps = [s for s in _board_settings(entry).get("snapshots") or [] if isinstance(s, dict)]
    response.headers["X-Total-Count"] = str(len(snaps))
    return {"snapshots": sorted(snaps, key=lambda s: s.get("event_id", 0), reverse=True)[:limit]}


@router.post("/history/snapshots", status_code=201)
def save_snapshot(body: SnapshotBody, db: Session = Depends(get_session)) -> dict:
    """Name the board as it is now (its newest event)."""
    from datetime import datetime

    entry = _snapshot_board(db, body.board_id)
    current = _current_rows(db, body.board_id)
    logs = _board_events(db, body.board_id, current)
    newest = max((row.id for rows in logs.values() for row in rows), default=None)
    if newest is None:
        raise HTTPException(status_code=409, detail="This board has nothing on it yet, so there is nothing to keep.")
    settings = _board_settings(entry)
    snaps = [s for s in settings.get("snapshots") or [] if isinstance(s, dict)]
    now = datetime.now()
    snap = {
        "id": max((int(s.get("id", 0)) for s in snaps), default=0) + 1,
        "name": (body.name or "").strip() or f"Snapshot {now:%H:%M}",
        "event_id": newest,
        "at": now.isoformat(timespec="seconds"),
    }
    settings["snapshots"] = (snaps + [snap])[-SNAPSHOTS_MAX:]
    entry.board_settings = json.dumps(settings)
    db.commit()
    return snap


@router.delete("/history/snapshots/{snapshot_id}", status_code=204)
def delete_snapshot(snapshot_id: int, board_id: int, db: Session = Depends(get_session)) -> None:
    entry = _snapshot_board(db, board_id)
    settings = _board_settings(entry)
    snaps = [s for s in settings.get("snapshots") or [] if isinstance(s, dict)]
    kept = [s for s in snaps if s.get("id") != snapshot_id]
    if len(kept) == len(snaps):
        raise HTTPException(status_code=404, detail="That snapshot could not be found.")
    settings["snapshots"] = kept
    entry.board_settings = json.dumps(settings)
    db.commit()


@router.get("/history/{event_id}")
def board_at(event_id: int, board_id: int | None = None, db: Session = Depends(get_session)) -> dict:
    """Every item on the board as it was straight after `event_id`."""
    board_id = _board_param(board_id)
    _require_board(db, board_id)
    current = _current_rows(db, board_id)
    logs = _board_events(db, board_id, current)
    states, known = _states_at(board_id, current, logs, event_id)
    if not known:
        raise HTTPException(
            status_code=410,
            detail="That moment is older than the board's history keeps in full, so it cannot be shown.",
        )
    out = {"nodes": [], "sketches": [], "objects": [], "event_id": event_id}
    for key, state in sorted(states.items()):
        kind = key.split(":")[0]
        row = _row_out(kind, key, state)
        if row is not None:
            out[{"node": "nodes", "sketch": "sketches", "object": "objects"}[kind]].append(row)
    return out


class RestoreBody(BaseModel):
    #: Only these items ("node:12", "sketch:4"), or the whole board when absent.
    keys: list[str] | None = Field(default=None, max_length=5000)


def _link_ends(data: dict) -> list[tuple[str, str]]:
    return [(id_key, kind_key) for id_key, kind_key in (("sourceId", "sourceKind"), ("targetId", "targetKind")) if data.get(id_key) is not None]


def _link_data(raw: str | None) -> dict | None:
    """A connector's parsed data, or None when `raw` is not one."""
    try:
        data = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return None
    if isinstance(data, dict) and str(data.get("type", "")).startswith("link-"):
        return data
    return None


def _remove_gone(db: Session, board_id: int, scope: set[str], current: dict, states: dict, counts: dict) -> set[str]:
    """Removed: on the board now, not then."""
    removed: set[str] = set()
    for key in sorted(scope):
        if key in current and key not in states:
            removed.add(key)
            kind = key.split(":")[0]
            row = current[key]
            events.record(db, "deleted", KINDS[kind][0], row.id, f"{kind} off board {board_id} (history)",
                          payload={"before": _state_of(kind, row), "after": dict(events.DELETED)})
            db.delete(row)
            counts["removed"] += 1
    return removed


def _restore_order(scope: set[str], states: dict) -> list[str]:
    # Objects first (a topic's parent), links last.
    order = {"object": 0, "node": 1, "sketch": 2}
    return sorted(
        (k for k in scope if k in states),
        key=lambda k: (order[k.split(":")[0]], _link_data(states[k].get("data")) is not None, int(k.split(":")[1])),
    )


def _restore_one(db: Session, board_id: int, key: str, state: dict, current: dict, made: dict, counts: dict, touched: list) -> None:
    """Make one item again, or write it back when it is still here."""
    kind = key.split(":")[0]
    etype, model = KINDS[kind]
    if kind == "node":
        entry = db.get(Entry, state.get("entry_id"))
        if entry is None or entry.is_deleted:
            return
    values = {f: state.get(f) for f in FIELDS[kind] if f in state}
    if kind == "node":
        values["locked"] = bool(values.get("locked"))
        values["hidden"] = bool(values.get("hidden"))
    row = current.get(key)
    if row is None:
        row = model(board_id=board_id, **values)
        db.add(row)
        db.flush()
        made[key] = row.id
        touched.append((kind, row))
        counts["made"] += 1
        return
    before = _state_of(kind, row)
    for field, value in values.items():
        setattr(row, field, value)
    after = _state_of(kind, row)
    if after != before:
        touched.append((kind, row))
        events.record(db, "edited", etype, row.id, f"{kind} on board {board_id} (history)",
                      payload={"before": before, "after": after})
        counts["changed"] += 1


def _drop_orphaned_links(db: Session, board_id: int, current: dict, removed: set[str], touched: list, counts: dict) -> None:
    """Drop a connector already here whose end this restore took away."""
    for key, row in current.items():
        if key in removed or not key.startswith("sketch:") or any(row is r for _, r in touched):
            continue
        data = _link_data(row.data)
        if data is None:
            continue
        if any(f"{data.get(kind_key) or 'node'}:{data[id_key]}" in removed for id_key, kind_key in _link_ends(data)):
            events.record(db, "deleted", "whiteboard_sketch", row.id, f"sketch off board {board_id} (history)",
                          payload={"before": _state_of("sketch", row), "after": dict(events.DELETED)})
            db.delete(row)
            counts["removed"] += 1


def _repoint_link(db: Session, row, made: dict, alive: set[str], counts: dict) -> None:  # noqa: ANN001
    """Point a connector at the remade ends; a remade connector left with an end
    on nothing is dropped again."""
    data = _link_data(row.data)
    if data is None:
        return
    whole = True
    for id_key, kind_key in _link_ends(data):
        end = f"{data.get(kind_key) or 'node'}:{data[id_key]}"
        if end in made:
            data[id_key] = made[end]
        elif end not in alive:
            whole = False
    row.data = json.dumps(data)
    if not whole and row.id in made.values():
        db.delete(row)
        counts["made"] -= 1
        for k in [k for k, v in made.items() if v == row.id]:
            del made[k]


def _repoint(db: Session, touched: list, made: dict, alive: set[str], counts: dict) -> None:
    """Re-point what names a remade item."""
    for kind, row in touched:
        if kind == "object" and row.parent_id is not None and f"object:{row.parent_id}" in made:
            row.parent_id = made[f"object:{row.parent_id}"]
        if kind == "sketch":
            _repoint_link(db, row, made, alive, counts)


@router.post("/history/{event_id}/restore")
def restore_board(
    event_id: int, body: RestoreBody, board_id: int | None = None, db: Session = Depends(get_session)
) -> dict:
    """Put the board, or the items named, back as they were after `event_id`.

    Rows that were not there then are removed, rows that were and are gone
    are made again (new ids, their links and a map topic's parent re-pointed
    at the new ones), rows that changed are written back; each with its own
    event, in one transaction. A card whose note is gone is left out, and so
    is a connector with an end that is."""
    board_id = _board_param(board_id)
    _require_board(db, board_id)
    current = _current_rows(db, board_id)
    logs = _board_events(db, board_id, current)
    states, known = _states_at(board_id, current, logs, event_id)
    if not known:
        raise HTTPException(
            status_code=410,
            detail="That moment is older than the board's history keeps in full, so it cannot be put back.",
        )
    scope = set(body.keys) if body.keys is not None else set(states) | set(current)
    made: dict[str, int] = {}
    counts = {"made": 0, "changed": 0, "removed": 0}
    touched: list[tuple[str, object]] = []

    removed = _remove_gone(db, board_id, scope, current, states, counts)
    for key in _restore_order(scope, states):
        _restore_one(db, board_id, key, states[key], current, made, counts, touched)
    # A connector with an end on nothing goes: one made again, or one already
    # here whose end this restore took away.
    _drop_orphaned_links(db, board_id, current, removed, touched, counts)
    _repoint(db, touched, made, set(current) - removed, counts)
    db.flush()
    for kind, row in touched:
        if row.id in made.values():
            events.record(db, "created", KINDS[kind][0], row.id, f"{kind} on board {board_id} (history)",
                          payload={"after": _state_of(kind, row)})
    events.record(db, "restored", "board", board_id, f"board put back to event {event_id}"[:80],
                  payload={"event_id": event_id, **counts})
    db.commit()
    return {**counts, "event_id": event_id}
