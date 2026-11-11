"""Sync through a folder: the home-network sync's segments, carried by a file (WORLD_CLASS_PLAN B6 decision 14, row 36).

Two installs share nothing but a folder (a USB stick, Syncthing, a cloud drive's local copy). Each writes **only
its own file**, `tessellate-sync-<device>.json`, so a file-sync tool never has two writers to reconcile, and reads
the others'. The file is sealed with a key from a passphrase the computers share (scrypt, salt in the header;
AES-256-GCM): the folder may sit on a cloud drive and show nothing. The passphrase is never stored.

**One apply path (decision 14).** The file carries what the home-network transport serves: this notebook's
note segments from the start of its log (`sync_segments.export_segment`), the documents, boards and files
manifest and every item's state (`sync_extras`), and each attached file's bytes sealed beside it in
`tessellate-sync-<device>-files/`. Reading a peer's file is `sync_pull.pull_from` over `FolderLink`, the same
transport protocol as the LAN link, so a note, document, board or file changed on both is settled by the
same rules (decisions 3 and 13: the later change wins, the other words stay in History) and each peer keeps
its own cursor and agreed hashes in `sync-state.json` (`device_id` is the same name the LAN uses).

**Private notes never go into the folder.** The passphrase is the folder's only lock and no data key is
wrapped for a folder peer, so private notes are left out of the segments, and private documents, boards and
files of private notes are listed with an empty hash, which the reader skips (they stay home, as items a
private space seals do). A note that went into the folder in the clear and was made private since goes as a
`withheld` marker, its name and time only, so the other computer withdraws its copy (INBOX 1783); the names
that went out in the clear are kept in `folder_sync_state.json` as `shipped`. A document or board made private
since goes the same way (`sync_extras.withheld`, listed as `document|<sid>` in `shipped`).

**One notebook, one name.** A notebook folder copied to a second computer carries the same `sync-state.json`;
a file in the folder whose device is this computer's, or is not the name it is filed under, is refused.
Two copies that both write the one file are found by a random token in the file's body, new at every write and
remembered here as `token` in `folder_sync_state.json`: our own file holding a token we did not write means
another copy writes it too, and the run stops before it reads, writes or deletes anything.

Pure of the web layer; `api/routes_folder_sync.py` is the one caller. The folder and the time of the last run
are remembered in `folder_sync_state.json` beside the database so the sheet can offer them next time.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import threading
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.core import atomic_io, crypto, paths, sync_state
from tessellate.core import events
from tessellate.core.database import Entry, impersonate_workspace, utcnow
from tessellate.entry import manager, sync_extras, sync_pull, sync_segments

FORMAT = "tessellate-sync"
VERSION = 2
FILE_PREFIX = "tessellate-sync-"
FILE_SUFFIX = ".json"
FILES_SUFFIX = "-files"
STATE_FILE = "folder_sync_state.json"
#: The quietest folder a person can point this at still has to hold a passphrase worth the name.
MIN_PASSPHRASE = 8
_OPEN_ERRORS = (crypto.DecryptionError, ValueError, KeyError, TypeError, OSError)


#: The last SyncError sentence, per thread. The route shows this, never text read off the exception: CodeQL
#: reads anything taken from a caught exception as stack-trace information (the ai/skills.py pattern).
_LAST_PROBLEM = threading.local()


class SyncError(ValueError):
    """Something the person can fix: a folder that is not one, a passphrase too short, a file not ours."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        _LAST_PROBLEM.text = message


def last_problem() -> str:
    """The sentence of the last SyncError raised on this thread."""
    return str(getattr(_LAST_PROBLEM, "text", "") or "Sync through the folder stopped.")


def state_path(data_dir: Path) -> Path:
    return Path(data_dir) / STATE_FILE


def load_state(data_dir: Path) -> dict[str, str]:
    """{folder, last}: what the sheet offers next time."""
    try:
        raw = json.loads(state_path(data_dir).read_text("utf-8"))
        return {k: str(raw.get(k) or "") for k in ("folder", "last")}
    except (OSError, ValueError, TypeError, AttributeError):
        return {"folder": "", "last": ""}


def _key(passphrase: str, salt: bytes) -> bytes:
    return crypto.derive_kek(passphrase, salt)


def _sync_roots() -> list[str]:
    """Where a sync folder may live, as real paths with a trailing separator: home (Syncthing and a cloud
    drive's local copy sit there) and the places a USB stick mounts. On Windows a stick is its own drive,
    so every drive but the system one."""
    roots = [os.path.expanduser("~"), "/media", "/run/media", "/mnt", "/Volumes"]
    if os.name == "nt":
        system = os.environ.get("SystemDrive", "C:").upper().rstrip("\\")
        roots += [f"{letter}:\\" for letter in "DEFGHIJKLMNOPQRSTUVWXYZ" if f"{letter}:" != system]
    return [os.path.join(os.path.realpath(root), "") for root in roots]


def _root_of(real: str) -> str:
    """The sync root `real` sits in or is, without its trailing separator; a NUL when it is in none."""
    for root in _sync_roots():
        if os.path.join(real, "").startswith(root):
            return root.rstrip("/\\") or root
    return "\x00"


def _checked(folder: str, passphrase: str, notebook: Path | None = None) -> Path:
    """The folder, resolved with links followed, or a SyncError. Inside home or a removable drive (the route
    takes a path from a request: CodeQL path injection), never the notebook's own folder or one inside it:
    a sync file there would travel with every copy of the notebook."""
    if not folder.strip() or "\x00" in folder:
        raise SyncError("Choose a folder that exists on this computer.")
    # The same shape as core/paths.contained, the one CodeQL counts as a guard: a bare negative `startswith` on the
    # `realpath` result itself, a raise, and that same value used after it. `_root_of` holds the separator test, so a
    # sibling such as /home/user2 never passes for /home/user; it returns the root without its separator, so the
    # root folder itself passes, and a NUL (refused above, so never a prefix) when the folder is in no root.
    real = os.path.realpath(os.path.expanduser(folder))
    if not real.startswith(_root_of(real)):
        raise SyncError("Choose a folder in your home folder or on a removable drive.")
    if notebook is not None and os.path.join(real, "").startswith(os.path.join(os.path.realpath(str(notebook)), "")):
        raise SyncError("Choose a folder outside the notebook's own folder.")
    path = Path(real)
    if not path.is_dir():
        raise SyncError("Choose a folder that exists on this computer.")
    if len(passphrase) < MIN_PASSPHRASE:
        raise SyncError(f"Use a sync passphrase of at least {MIN_PASSPHRASE} characters, the same on every computer.")
    return path


# --- this computer's file -------------------------------------------------------


def _shipped(data_dir: Path) -> set[str] | None:
    """The notes this computer has put into the folder in the clear; None when a sync ran before that was kept
    or the record cannot be read, so every private note goes as withheld once and is kept from then on."""
    try:
        raw = json.loads(state_path(data_dir).read_text("utf-8"))
    except FileNotFoundError:
        return set()
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    found = raw.get("shipped")
    if isinstance(found, list):
        return {str(sid) for sid in found}
    return None if raw.get("last") else set()


def _announce_withdrawals(session: Session) -> None:
    """The first run after the record was lost: each private note gets one new change in this notebook's log, so the
    marker sits above every cursor (a computer that pulled the note in the clear already read past its last change)."""
    with events.acting_as("system:folder-sync"), impersonate_workspace(session, ""):
        for entry in session.scalars(select(Entry).where(Entry.is_private.is_(True), Entry.is_board.is_(False))):
            manager.log_action(session, "dated", "entry", entry.id)
        session.commit()


def _for_folder(notes: list[dict], shipped: set[str] | None) -> list[dict]:
    """A plain note as it is; a private one as withheld when it went out in the clear before, else not at all."""
    return [n if not n["is_private"] else sync_segments.withheld(n)
            for n in notes if not n["is_private"] or shipped is None or n["sid"] in shipped]


def segments(session: Session, device: str, shipped: set[str] | None = None) -> list[dict[str, Any]]:
    """Every ordinary note, as the chain of segments a LAN peer pulling from the start would get; a private one
    only as withheld, when it is in `shipped` (None: every private one)."""
    out: list[dict[str, Any]] = []
    since = 0
    for _ in range(sync_pull.MAX_ROUNDS):
        segment = sync_segments.export_segment(session, device, since, "")
        notes = _for_folder(segment["notes"], shipped)
        out.append({**segment, "notes": notes, "digest": sync_segments.digest(notes)})
        if not segment["more"] or segment["upto"] <= since:
            break
        since = segment["upto"]
    return out


def _private(session: Session, device: str, item: dict) -> bool:
    if item["kind"] != "file":
        return bool(item.get("is_private"))
    note = sync_segments._find(session, device, item.get("note") or "")  # noqa: SLF001  # the note lookup, one place
    return note is None or bool(note.is_private)


def _withdrawn(item: dict, shipped: set[str] | None) -> bool:
    """A private document or board that went out in the clear before (None: any, once)."""
    return (item["kind"] in ("document", "board") and bool(item.get("is_private"))
            and (shipped is None or f"{item['kind']}|{item['sid']}" in shipped))


def extras(session: Session, data_dir: Path, device: str, shipped: set[str] | None = None) -> tuple[dict, dict]:
    """(manifest, {kind: {sid: state}}) for the folder: private ones listed with an empty hash, no state, except
    a document or board shipped in the clear before, which goes as a withheld marker."""
    whole = sync_extras.manifest(session, data_dir, device)
    found: dict[str, dict[str, dict]] = {kind: {} for kind in sync_extras.KINDS}
    for kind in sync_extras.KINDS:
        sids = [x["sid"] for x in whole["items"] if x["kind"] == kind and x["hash"]]
        for start in range(0, len(sids), sync_extras.MAX_ITEMS):
            for item in sync_extras.items(session, data_dir, device, kind, sids[start:start + sync_extras.MAX_ITEMS]):
                if not _private(session, device, item):
                    found[kind][item["sid"]] = item
                elif _withdrawn(item, shipped):
                    found[kind][item["sid"]] = sync_extras.withheld(item)
    lines = [{**x, "hash": _listed(x, found[x["kind"]])} for x in whole["items"]]
    return {**whole, "items": lines, "digest": sync_extras.digest(lines)}, found


def _listed(line: dict, found: dict[str, dict]) -> str:
    state = found.get(line["sid"])
    if state is None:
        return ""
    return sync_extras.WITHHELD if state.get("withheld") else line["hash"]


def _blob_name(sid: str) -> str:
    return sid.replace(":", "-") + ".bin"


def _sealed_sha1(target: Path) -> str:
    try:
        return str(json.loads(target.read_text("utf-8")).get("sha1") or "")
    except (OSError, ValueError, AttributeError):
        return ""


def _write_blobs(session: Session, data_dir: Path, blobs: Path, files: dict, sealing: tuple[bytes, bool]) -> None:
    """Each attached file sealed once under its sid (again under a new key); one gone from the manifest leaves too."""
    key, kept = sealing
    blobs.mkdir(exist_ok=True)
    keep = set()
    for sid, item in files.items():
        name = _blob_name(sid)
        keep.add(name)
        try:  # a sid is checked where its manifest arrives; contained() also stops a planted link
            target = paths.contained(blobs, name)
        except paths.OutsideFolder:
            continue
        if kept and _sealed_sha1(target) == item["sha1"]:
            continue
        found = sync_extras.file_bytes(session, data_dir, sync_state.device_id(data_dir), sid)
        if found is not None:
            sealed = crypto.encrypt(key, base64.b64encode(found[0]).decode("ascii"))
            atomic_io.atomic_write_json(target, {"sha1": item["sha1"], "data": sealed}, indent=0)
    for old in blobs.glob("*.bin"):
        if old.name not in keep:
            old.unlink(missing_ok=True)


def _own_salt(own: Path, passphrase: str) -> tuple[bytes, bool]:
    """(salt, kept): the salt of this computer's last file when the passphrase still opens it, so the
    files sealed beside it stay readable; else a new one, and every file is sealed again."""
    try:
        sealed = json.loads(own.read_text("utf-8"))
        salt = base64.b64decode(sealed["salt"])
        crypto.decrypt(_key(passphrase, salt), sealed["data"])
        return salt, True
    except _OPEN_ERRORS:
        return crypto.new_salt(), False


def write(session: Session, data_dir: Path, path: Path, passphrase: str, token: str = "") -> tuple[int, list[str]]:
    """This computer's file and its sealed attachments; (the notes it carries in the clear, every name it has sent).
    `token` is this write's own, left in the file for the next run to find (see `_written_by_a_copy`)."""
    device = sync_state.device_id(data_dir)
    own = path / f"{FILE_PREFIX}{device}{FILE_SUFFIX}"
    salt, kept = _own_salt(own, passphrase)
    key = _key(passphrase, salt)
    shipped = _shipped(data_dir)
    if shipped is None:
        _announce_withdrawals(session)
    manifest, found = extras(session, data_dir, device, shipped)
    body = {"device": device, "written": utcnow().isoformat(), "token": token,
            "segments": segments(session, device, shipped), "manifest": manifest, "items": found}
    sent = [n for s in body["segments"] for n in s["notes"]]
    sent_extras = {f"{kind}|{sid}" for kind in ("document", "board") for sid in found[kind]}
    names = sorted((shipped or set()) | {n["sid"] for n in sent} | sent_extras)
    #: Before the file is written: a write cut short must not forget what may already have gone out.
    save_state(data_dir, shipped=names, token=token, prev=_raw_state(data_dir).get("token") or "")
    _write_blobs(session, data_dir, path / f"{FILE_PREFIX}{device}{FILES_SUFFIX}", found["file"], (key, kept))
    sealed = {"format": FORMAT, "version": VERSION, "device": device,
              "salt": base64.b64encode(salt).decode("ascii"),
              "data": crypto.encrypt(key, json.dumps(body, ensure_ascii=False))}
    atomic_io.atomic_write_json(own, sealed, indent=0)
    return sum(not n["is_private"] for n in sent), names


# --- reading a peer --------------------------------------------------------------


class FolderLink:
    """A peer's file as the sync transport (`sync_pull.Transport`): what the LAN routes would answer."""

    #: The folder carries no key, so it alone sends a private note as a withheld marker (`sync_segments.check`).
    withdraws = True

    def __init__(self, body: dict, blobs: Path, key: bytes) -> None:
        self.name = str(body["device"])
        self._segments = list(body["segments"])
        self._manifest = body["manifest"]
        self._items = body["items"]
        self._blobs, self._key = blobs, key
        if not self._segments:
            raise SyncError("That is not a Tessellate sync file.")

    def fetch(self, since: int, me: str) -> dict:
        for segment in self._segments:
            if segment["upto"] > since:
                return segment
        last = self._segments[-1]
        return {**last, "since": since, "upto": max(since, last["upto"]), "more": False,
                "notes": [], "digest": sync_segments.digest([])}

    def manifest(self, me: str) -> dict:
        return self._manifest

    def items(self, kind: str, sids: list[str], me: str) -> list:
        found = self._items.get(kind) or {}
        return [found[sid] for sid in sids if sid in found]

    def file(self, sid: str, me: str) -> bytes | None:
        """The bytes, or None while the folder has not got them yet (a sync tool still copying)."""
        try:
            sealed = json.loads(paths.contained(self._blobs, _blob_name(sid)).read_text("utf-8"))
            return base64.b64decode(crypto.decrypt(self._key, sealed["data"]))
        except _OPEN_ERRORS:
            return None


class SameIdError(SyncError):
    """The file carries this computer's own sync id: a copied notebook folder (sync_segments.SAME_ID)."""


def open_peer(path: Path, file: Path, passphrase: str, me: str) -> FolderLink:
    sealed = json.loads(file.read_text("utf-8"))
    if sealed.get("format") != FORMAT or sealed.get("version") != VERSION:
        raise SyncError("That is not a Tessellate sync file.")
    key = _key(passphrase, base64.b64decode(sealed["salt"]))
    body = json.loads(crypto.decrypt(key, sealed["data"]))
    device = str(body["device"])
    if len(device) != 12 or not device.isalnum():  # sync_state.device_id's own shape; it names a folder here
        raise SyncError("That is not a Tessellate sync file.")
    if device == me:  # a sync tool's conflict copy of the file two copies of one notebook both write
        raise SameIdError(sync_segments.SAME_ID)
    if file.name != f"{FILE_PREFIX}{device}{FILE_SUFFIX}":
        raise SyncError("That is not a Tessellate sync file.")
    return FolderLink(body, path / f"{FILE_PREFIX}{body['device']}{FILES_SUFFIX}", key)


# --- one sync ----------------------------------------------------------------


def _raw_state(data_dir: Path) -> dict:
    try:
        raw = json.loads(state_path(data_dir).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def save_state(data_dir: Path, **fields: Any) -> None:
    """Merge `fields` into `folder_sync_state.json`."""
    atomic_io.atomic_write_json(state_path(data_dir), {**_raw_state(data_dir), **fields})


def _written_by_a_copy(data_dir: Path, own: Path, passphrase: str) -> bool:
    """This computer's own file holds a write token this computer did not write: the notebook folder was copied
    and the other copy writes the file too. A file with no token (older) or one that cannot be opened is not."""
    try:
        sealed = json.loads(own.read_text("utf-8"))
        body = json.loads(crypto.decrypt(_key(passphrase, base64.b64decode(sealed["salt"])), sealed["data"]))
    except _OPEN_ERRORS:
        return False
    found = body.get("token") if isinstance(body, dict) else None
    mine = _raw_state(data_dir)  # `prev` too: a write cut short after its token was kept leaves the one before
    return isinstance(found, str) and bool(found) and found not in (mine.get("token"), mine.get("prev"))


def run(session: Session, data_dir: Path, folder: str, passphrase: str) -> dict[str, Any]:
    """Read every peer's file through the one apply path, then write this computer's. Returns what changed."""
    path = _checked(folder, passphrase, data_dir)
    device = sync_state.device_id(data_dir)
    counts: dict[str, Any] = {"applied": 0, "conflicts": 0, "waiting": 0, "unreadable": 0, "peers": 0, "error": "",
                              "shared": 0}
    if _written_by_a_copy(data_dir, path / f"{FILE_PREFIX}{device}{FILE_SUFFIX}", passphrase):
        counts["error"] = sync_segments.SAME_ID  # nothing is read, written or deleted while two copies share the name
        return counts
    for file in sorted(path.glob(f"{FILE_PREFIX}*{FILE_SUFFIX}")):
        if file.name != f"{FILE_PREFIX}{device}{FILE_SUFFIX}":
            _read_peer(session, data_dir, (path, file, passphrase), counts)
    token = secrets.token_hex(8)
    counts["shared"], _ = write(session, data_dir, path, passphrase, token)
    save_state(data_dir, folder=folder, last=utcnow().isoformat())
    return counts


def _read_peer(session: Session, data_dir: Path, where: tuple[Path, Path, str], counts: dict[str, Any]) -> None:
    """One peer's file through the one apply path, its counts added; one that cannot be opened is counted."""
    path, file, passphrase = where
    try:
        link = open_peer(path, file, passphrase, sync_state.device_id(data_dir))
    except _OPEN_ERRORS as exc:
        counts["unreadable"] += 1
        if isinstance(exc, SameIdError):
            counts["error"] = counts["error"] or sync_segments.SAME_ID
        return
    done = sync_pull.pull_from(session, data_dir, link, "folder")
    counts["peers"] += 1
    for key in ("applied", "conflicts", "waiting"):
        counts[key] += int(done.get(key) or 0)
    counts["error"] = counts["error"] or done["error"]


__all__ = ["FolderLink", "SyncError", "last_problem", "load_state", "run", "state_path", "write"]
