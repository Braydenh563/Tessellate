"""Sync without a server: notes carried between computers by a folder (WORLD_CLASS_PLAN row 36, Q34).

Two installs share nothing but a folder (a USB stick, Syncthing, a cloud drive's local copy). Each writes **only
its own file**, `tessellate-sync-<device>.json`, so a file-sync tool never has two writers to reconcile, and reads
the others'. A file is a snapshot of the sender's ordinary notes, encrypted (AES-256-GCM, key from a passphrase
the two computers share through scrypt, salt in the file header): the folder may sit on a cloud drive and show
nothing. The passphrase is never stored.

**Private notes never leave.** `Entry.is_private` (which also covers every note in a private space) is left out
of the file and left alone on the way in. Boards are left out too (they are canvases, not text).

**Conflicts keep both versions.** Each note has a stable `uid` (a device's own notes are `<device>-<id>`, an
imported one keeps the sender's) and each snapshot carries the note's hash and its `parent`, the version the
sender last agreed on with a peer. Reading a peer's note against ours:

- same hash: nothing to do;
- ours is the `parent` the peer built on: the peer's edit is simply newer, take it;
- the peer still sits on the version we last agreed on (its hash is our `base`): only we changed, keep ours;
- otherwise both changed since they last agreed: the **later edit wins** and the other text is kept as a
  `EntryRevision`, so History holds both, once (`handled` remembers the peer version already settled, so a second
  read of the same file adds nothing). Both computers pick the same winner (stamp, then device name), so they
  converge. This is per note, not per field: a note's text, tags, category, colour and pin travel together.

A note deleted on one side is deleted on the other unless the other changed it since; then the later of the two
wins like any conflict, and the words that lose stay in History or the recycle bin.
Not carried: a note's links, reminders, attachments and thread parent (a note's words and filing are what sync).

Pure of the web layer; `api/routes_sync.py` is the one caller. The state (device name, uid map, bases) is a small
JSON file beside the database so a restart changes nothing.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.core import atomic_io, crypto
from tessellate.core.database import Entry, EntryRevision, utcnow
from tessellate.entry import manager

FORMAT = "tessellate-sync"
VERSION = 1
FILE_PREFIX = "tessellate-sync-"
FILE_SUFFIX = ".json"
#: The quietest folder a person can point this at still has to hold a passphrase worth the name.
MIN_PASSPHRASE = 8


class SyncError(ValueError):
    """Something the person can fix: a folder that is not one, a passphrase too short."""


@dataclass
class State:
    """What this install remembers between runs (`sync_state.json`)."""

    device: str = field(default_factory=lambda: secrets.token_hex(4))
    folder: str = ""
    last: str = ""
    #: entry id -> uid
    uids: dict[str, str] = field(default_factory=dict)
    #: uid -> the hash this install last agreed on with a peer (or wrote, before any peer read it)
    base: dict[str, str] = field(default_factory=dict)
    #: "uid@device" -> the peer version already settled
    handled: dict[str, str] = field(default_factory=dict)


def load_state(path: Path) -> State:
    try:
        raw = json.loads(path.read_text("utf-8"))
        return State(**{k: raw[k] for k in State.__dataclass_fields__ if k in raw})
    except (OSError, ValueError, TypeError):
        return State()


def save_state(path: Path, state: State) -> None:
    atomic_io.atomic_write_json(path, state.__dict__)


# --- a note as the file carries it -------------------------------------------


def _when(value: datetime | str | None) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _stamp(entry: Entry) -> str:
    return _when(entry.deleted_at if entry.is_deleted else (entry.edited_at or entry.created_at)).isoformat()


def _fields(session: Session, entry: Entry) -> dict:
    if entry.is_deleted:
        return {"deleted": True}
    category = manager.category_name_for(session, entry)
    return {
        "deleted": False,
        "content": entry.content,
        "tags": manager.tags_from_json(entry.tags),
        "category": category,
        "pinned": bool(entry.pinned),
        "colour": entry.colour,
    }


def _hash(fields: dict) -> str:
    return hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:24]


def _ours(session: Session) -> list[Entry]:
    return list(session.scalars(select(Entry).where(Entry.is_private == False, Entry.is_board == False).order_by(Entry.id)))  # noqa: E712


def snapshot(session: Session, state: State) -> dict:
    """Every ordinary note of this install, with the version each was built on."""
    notes = []
    for entry in _ours(session):
        uid = state.uids.setdefault(str(entry.id), f"{state.device}-{entry.id}")
        fields = _fields(session, entry)
        digest = _hash(fields)
        state.base.setdefault(uid, digest)
        notes.append({"uid": uid, "stamp": _stamp(entry), "hash": digest, "parent": state.base[uid], **fields})
    return {"device": state.device, "written": utcnow().isoformat(), "notes": notes}


# --- the files ---------------------------------------------------------------


def _seal(passphrase: str, device: str, body: dict) -> dict:
    salt = crypto.new_salt()
    key = crypto.derive_kek(passphrase, salt)
    return {
        "format": FORMAT,
        "version": VERSION,
        "device": device,
        "salt": base64.b64encode(salt).decode("ascii"),
        "data": crypto.encrypt(key, json.dumps(body, ensure_ascii=False)),
    }


def _open(passphrase: str, sealed: dict) -> dict:
    if sealed.get("format") != FORMAT or sealed.get("version") != VERSION:
        raise SyncError("That is not a Tessellate sync file.")
    key = crypto.derive_kek(passphrase, base64.b64decode(sealed["salt"]))
    return json.loads(crypto.decrypt(key, sealed["data"]))


def _sync_roots() -> list[str]:
    """Where a sync folder may live, as real paths with a trailing separator: home (Syncthing and a cloud
    drive's local copy sit there) and the places a USB stick mounts. On Windows a stick is its own drive,
    so every drive but the system one."""
    roots = [os.path.expanduser("~"), "/media", "/run/media", "/mnt", "/Volumes"]
    if os.name == "nt":
        system = os.environ.get("SystemDrive", "C:").upper().rstrip("\\")
        roots += [f"{letter}:\\" for letter in "DEFGHIJKLMNOPQRSTUVWXYZ" if f"{letter}:" != system]
    return [os.path.join(os.path.realpath(root), "") for root in roots]


def _checked(folder: str, passphrase: str, notebook: Path | None = None) -> Path:
    """The folder, resolved with links followed, or a SyncError. Inside home or a removable drive (the route
    takes a path from a request: CodeQL path injection), never the notebook's own folder or one inside it:
    a sync file there would travel with every copy of the notebook."""
    if not folder.strip() or "\x00" in folder:
        raise SyncError("Choose a folder that exists on this computer.")
    real = os.path.join(os.path.realpath(os.path.expanduser(folder)), "")
    # The positive prefix test sits here, beside the read, in the shape CodeQL counts as a guard (core/paths.py).
    if not any(real.startswith(root) for root in _sync_roots()):
        raise SyncError("Choose a folder in your home folder or on a removable drive.")
    if notebook is not None and real.startswith(os.path.join(os.path.realpath(str(notebook)), "")):
        raise SyncError("Choose a folder outside the notebook's own folder.")
    path = Path(real)
    if not path.is_dir():
        raise SyncError("Choose a folder that exists on this computer.")
    if len(passphrase) < MIN_PASSPHRASE:
        raise SyncError(f"Use a sync passphrase of at least {MIN_PASSPHRASE} characters, the same on every computer.")
    return path


def _apply(session: Session, entry: Entry, note: dict) -> None:
    """Make `entry` say what the peer's note says. A delete or a restore as well as a rewrite."""
    if note["deleted"]:
        if not entry.is_deleted:
            manager.soft_delete_entry(session, entry)
        return
    if entry.is_deleted:
        manager.restore_entry(session, entry)
    elif note["content"] != entry.content:
        manager.record_revision(session, entry)  # the words about to be replaced stay in History
    manager.update_entry(session, entry, note["content"], note["category"], note["tags"])
    entry.pinned = bool(note["pinned"])
    entry.colour = note["colour"]
    entry.edited_at = _when(note["stamp"])


def _keep_text(session: Session, entry: Entry, content: str | None, tags: list[str]) -> None:
    """The loser's words, as a version in History."""
    if content:
        session.add(EntryRevision(entry_id=entry.id, content=content, tags=json.dumps(tags)))


def _settle(session: Session, entry: Entry, note: dict, peer: str, counts: dict, state: State, uid: str) -> None:
    ours = _fields(session, entry)
    mine, theirs = _hash(ours), note["hash"]
    if mine == theirs:
        state.base[uid] = theirs
        return
    if mine == note["parent"]:
        _apply(session, entry, note)
        counts["updated"] += 1
        state.base[uid] = theirs
        return
    if theirs == state.base.get(uid):
        return  # the peer has not moved since we last agreed: only we changed
    counts["conflicts"] += 1
    remote_wins = (_when(note["stamp"]), peer) > (_when(_stamp(entry)), state.device)
    if remote_wins:
        _apply(session, entry, note)
        state.base[uid] = theirs
    else:
        _keep_text(session, entry, note.get("content"), note.get("tags") or [])
        state.base[uid] = mine


def _bring_in(session: Session, note: dict, state: State) -> None:
    entry = manager.create_entry(
        session, note["content"], note["category"], note["tags"], commit=False
    )
    entry.pinned = bool(note["pinned"])
    entry.colour = note["colour"]
    entry.created_at = entry.edited_at = _when(note["stamp"])
    session.flush()
    state.uids[str(entry.id)] = note["uid"]
    state.base[note["uid"]] = note["hash"]


def read_peer(session: Session, body: dict, state: State, counts: dict) -> None:
    peer = body["device"]
    by_uid = {uid: int(entry_id) for entry_id, uid in state.uids.items()}
    for note in body["notes"]:
        uid = note["uid"]
        marker = f"{uid}@{peer}"
        if state.handled.get(marker) == note["hash"]:
            continue
        state.handled[marker] = note["hash"]
        entry = session.get(Entry, by_uid[uid]) if uid in by_uid else None
        if entry is None:
            if not note["deleted"]:
                _bring_in(session, note, state)
                counts["added"] += 1
            continue
        if entry.is_private or entry.is_board:
            continue  # a note that has since become private is never overwritten
        _settle(session, entry, note, peer, counts, state, uid)


# --- one sync ----------------------------------------------------------------


def run(session: Session, state: State, folder: str, passphrase: str, notebook: Path | None = None) -> dict:
    """Read every peer's file, then write this install's. Commits. Returns what changed."""
    path = _checked(folder, passphrase, notebook)
    counts = {"added": 0, "updated": 0, "conflicts": 0, "unreadable": 0, "peers": 0}
    for file in sorted(path.glob(f"{FILE_PREFIX}*{FILE_SUFFIX}")):
        if file.name == f"{FILE_PREFIX}{state.device}{FILE_SUFFIX}":
            continue
        try:
            body = _open(passphrase, json.loads(file.read_text("utf-8")))
            read_peer(session, body, state, counts)
            counts["peers"] += 1
        except (crypto.DecryptionError, SyncError, ValueError, KeyError, TypeError, OSError):
            counts["unreadable"] += 1
    session.commit()
    mine = snapshot(session, state)
    atomic_io.atomic_write_json(path / f"{FILE_PREFIX}{state.device}{FILE_SUFFIX}", _seal(passphrase, state.device, mine), indent=0)
    counts["shared"] = len(mine["notes"])
    state.folder, state.last = folder, utcnow().isoformat()
    return counts


__all__ = ["State", "SyncError", "load_state", "run", "save_state", "snapshot"]
