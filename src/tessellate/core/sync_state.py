"""What this data folder knows about sync (WORLD_CLASS_PLAN B6, decisions 2 and 8).

One small file, `sync-state.json` (0600, beside `lan-trust.json`): this
folder's random device id, and per peer the cursor into that peer's event
log, when the last pull ran and how it ended. Kept out of preferences for
the reason `lantrust` gives: `PUT /preferences` must not reach it, and a
file that cannot be read gives safe defaults (a new device id would only
mean the other computer sees a new peer, and a lost cursor only means the
next pull starts over, which the idempotent apply makes harmless).
"""

from __future__ import annotations

import contextlib
import functools
import hashlib
import json
import os
import secrets
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tessellate.core.atomic_io import atomic_write_text

FILE_NAME = "sync-state.json"

#: Held around every read-then-write below: the pair route, a pass being issued and the first
#: device id all run outside `sync_pull.RUNNING`, so without it two threads lose each other's update.
_LOCK = threading.RLock()


def _locked(fn: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(fn)
    def run(*args: Any, **kwargs: Any) -> Any:
        with _LOCK:
            return fn(*args, **kwargs)

    return run


def _path(data_dir: Path) -> Path:
    return Path(data_dir) / FILE_NAME


def _read(data_dir: Path) -> dict:
    try:
        raw = json.loads(_path(data_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write(data_dir: Path, state: dict) -> None:
    path = _path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    # A unique temp file (mkstemp is 0600) so no two writers ever share one.
    atomic_write_text(path, json.dumps(state, indent=1))
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)


@_locked
def device_id(data_dir: Path) -> str:
    """This folder's sync name, made once: 12 hex characters, never shown as a secret."""
    state = _read(data_dir)
    found = state.get("device")
    if isinstance(found, str) and len(found) == 12 and found.isalnum():
        return found
    state["device"] = secrets.token_hex(6)
    _write(data_dir, state)
    return state["device"]


def peer(data_dir: Path, name: str) -> dict:
    """What is known about one peer; `cursor` 0 when it was never pulled."""
    found = _read(data_dir).get("peers", {}).get(name)
    found = found if isinstance(found, dict) else {}
    cursor = found.get("cursor")
    return {**found, "cursor": cursor if isinstance(cursor, int) and cursor > 0 else 0}


@_locked
def save_peer(data_dir: Path, name: str, **fields: object) -> dict:
    """Merge `fields` into the peer's record and stamp the time of the try."""
    state = _read(data_dir)
    peers = state.get("peers") if isinstance(state.get("peers"), dict) else {}
    record = {**peer(data_dir, name), **fields, "tried_at": time.time()}
    state["peers"] = {**peers, name: record}
    _write(data_dir, state)
    return record


def last_peer(data_dir: Path) -> tuple[str, dict] | None:
    """The peer pulled from most recently, for the Settings line."""
    peers = _read(data_dir).get("peers")
    if not isinstance(peers, dict) or not peers:
        return None
    rows = [(name, row) for name, row in peers.items() if isinstance(row, dict)]
    if not rows:
        return None
    return max(rows, key=lambda pair: pair[1].get("tried_at") or 0)



# --- the sync pass (decision 11): this computer's side ---------------------------


def _pass_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()


@_locked
def issue_pass(data_dir: Path, device: str) -> str:
    """A new pass for the allowed device `device` (its `lantrust` hash); only the hash is kept.

    One pass per device: pairing again replaces the old one."""
    raw = secrets.token_urlsafe(32)
    state = _read(data_dir)
    passes = state.get("passes") if isinstance(state.get("passes"), dict) else {}
    kept = {h: d for h, d in passes.items() if d != device}
    state["passes"] = {**kept, _pass_hash(raw): device}
    _write(data_dir, state)
    return raw


def pass_device(data_dir: Path, raw: str | None) -> str:
    """The device a pass was issued to, or '' for no such pass."""
    if not raw or len(raw) > 100:
        return ""
    passes = _read(data_dir).get("passes")
    found = passes.get(_pass_hash(raw)) if isinstance(passes, dict) else None
    return found if isinstance(found, str) else ""


# --- the paired computer (decision 10): the other side's address and pass -------


def link(data_dir: Path) -> dict:
    """The paired computer as stored, or {} when none is paired."""
    found = _read(data_dir).get("link")
    return found if isinstance(found, dict) else {}


@_locked
def save_link(data_dir: Path, **fields: object) -> dict:
    state = _read(data_dir)
    state["link"] = {**link(data_dir), **fields}
    _write(data_dir, state)
    return state["link"]


@_locked
def forget_link(data_dir: Path) -> None:
    state = _read(data_dir)
    state.pop("link", None)
    _write(data_dir, state)


# --- documents and files from another computer (decision 13) -----------------------


def _landed(value: object) -> list | None:
    if isinstance(value, int):
        return [value, ""]
    ok = isinstance(value, list) and len(value) == 2 and isinstance(value[0], int) and isinstance(value[1], str)
    return value if ok else None


def arrived(data_dir: Path) -> dict[str, dict[str, list]]:
    """{kind: {sid: [local id, mark]}} for each document and file that came from another computer.

    The mark (`sync_extras.mark`) tells the row that landed from a later one that took its freed id."""
    found = _read(data_dir).get("arrived")
    if not isinstance(found, dict):
        return {}
    return {kind: {s: _landed(i) for s, i in rows.items() if _landed(i)}
            for kind, rows in found.items() if isinstance(rows, dict)}


@_locked
def save_arrived(data_dir: Path, kind: str, sid: str, local_id: int | None, mark: str = "") -> None:
    """Remember (or, with None, forget) where an item from another computer landed here."""
    state = _read(data_dir)
    rows = arrived(data_dir)
    kept = {s: i for s, i in rows.get(kind, {}).items() if s != sid}
    if local_id is not None:
        kept[sid] = [local_id, mark]
    state["arrived"] = {**rows, kind: kept}
    _write(data_dir, state)


@_locked
def save_arrived_many(data_dir: Path, marks: list[tuple[str, str, int | None, str]]) -> None:
    """`save_arrived` for a batch of (kind, sid, local id or None, mark): one write, not one each."""
    if not marks:
        return
    state = _read(data_dir)
    rows = arrived(data_dir)
    for kind, sid, local_id, stamp in marks:
        kept = {s: i for s, i in rows.get(kind, {}).items() if s != sid}
        if local_id is not None:
            kept[sid] = [local_id, stamp]
        rows = {**rows, kind: kept}
    state["arrived"] = rows
    _write(data_dir, state)
