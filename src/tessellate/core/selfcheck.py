"""The data folder's self-check: what the app does when files under it are gone.

The owner, 2026-11-03 (INBOX 1573): "if the user deletes any files or folders
from their data folder, can the app automatically handle that?? like make
replacements, be able to reimplement backups". Measured first, by deleting
each path in a scratch copy and starting the server: a missing database, or
a missing `-wal` beside a main file that never had its log folded in, started
a blank notebook with the backups unmentioned; a damaged database stopped the
server; an unreadable `preferences.json` stopped it too; a missing attached
file was a 404 nobody listed. Folders the app owns were already made again on
first use, and a missing backups folder already got a fresh backup at start.

Each kind of path has one answer, and none of them deletes anything:

- recreate: a folder the app owns (`OWNED_FOLDERS`) is made again, empty;
- set aside: a file the app cannot read (the database, `preferences.json`) is
  renamed beside itself, kept byte for byte, and the app starts without it;
- offer: a notebook with no account while a backup holds notes is offered
  that backup on the lock screen (`restore_offer`), the person's choice;
- report: a note whose attached file is gone is listed (`missing_files`).

Everything derived (the search index and the vectors live in the database;
board thumbnails, the compressed page cache and the window's profile are
made again on first use) needs nothing here.

Cheap by design: one `stat` per owned folder and one directory listing per
file folder, never a walk; measured in `tests/test_data_dir_selfcheck.py`.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("tessellate.selfcheck")

#: The folders a notebook keeps whether or not anything is in them yet.
OWNED_FOLDERS = ("uploads", "media", "backups")

#: How many missing files the report names; the count is always whole.
MISSING_LISTED = 50

_lock = threading.Lock()
#: What was set aside or made again during this start, before the check ran
#: (the preferences are read, and the database opened, before it can).
_noted: list[str] = []
#: The database file's state when this process first looked at it.
_start: dict[str, object] = {}
_last: dict = {}
_offers: dict[str, dict | None] = {}


def _now() -> datetime:
    """The clock, one seam for the tests' fixed one."""
    return datetime.now(timezone.utc)


def note(line: str) -> None:
    """Something repaired before the check could run, said in its report."""
    with _lock:
        if line not in _noted:
            _noted.append(line)
    logger.warning("%s", line)


def reset_for_tests() -> None:
    with _lock:
        _noted.clear()
        _start.clear()
        _last.clear()
        _offers.clear()


def _stamp() -> str:
    return _now().strftime("%Y%m%d-%H%M%S")


def set_aside(path: Path, label: str) -> Path:
    """Rename an unreadable file beside itself, never over another one.

    A rename, not a copy: the bytes are exactly what was there, and the app
    then starts as if the file were missing. `label` names why."""
    stem = f"{path.name}.{label}-{_stamp()}"
    target = path.with_name(stem)
    number = 1
    while target.exists():
        number += 1
        target = path.with_name(f"{stem}-{number}")
    os.replace(path, target)
    return target


def observe_folders(data_dir: Path) -> None:
    """The owned folders missing before anything made them again (the
    settings make `uploads`, a backup listing makes `backups`), so the
    report can say so."""
    with _lock:
        _start.setdefault("folders_missing", [n for n in OWNED_FOLDERS if not (Path(data_dir) / n).exists()])


def observe_start(db_path: Path) -> None:
    """Whether the database file was there before anything opened it."""
    with _lock:
        _start.setdefault("db_missing", not Path(db_path).exists())


def set_aside_damaged_database(db_path: Path) -> Path:
    """A database SQLite cannot open, with a backup to go back to: kept
    aside with its two sidecars (left beside a good copy they would replay
    the damaged pages onto it), so the app can start and offer the backup."""
    db_path = Path(db_path)
    kept = set_aside(db_path, "damaged")
    for suffix in ("-wal", "-shm"):
        side = db_path.with_name(db_path.name + suffix)
        if side.exists():
            os.replace(side, kept.with_name(kept.name + suffix))
    with _lock:
        _start["damaged_kept_as"] = kept.name
    note(f"The notebook file could not be opened, so it was kept as {kept.name} and a new one started.")
    return kept


def recreate_folders(data_dir: Path) -> list[str]:
    """Each owned folder made again when it is missing. A file standing
    where a folder should be is the person's, so it is reported, not moved."""
    lines = []
    with _lock:
        #: Said once: a later check from Settings does not repeat the start's.
        gone = _start.get("folders_missing") or []
        _start["folders_missing"] = []
    for name in OWNED_FOLDERS:
        folder = Path(data_dir) / name
        if folder.is_dir():
            if name in gone:
                lines.append(f"The {name} folder was missing and was made again, empty.")
            continue
        if folder.exists():
            lines.append(f"{name} is a file, not a folder: move it, and the folder is made at the next start.")
            continue
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            lines.append(f"The {name} folder could not be made: {exc.strerror or 'the disk refused'}.")
            continue
        lines.append(f"The {name} folder was missing and was made again, empty.")
    return lines


def _names(folder: Path) -> set[str] | None:
    try:
        with os.scandir(folder) as found:
            return {item.name for item in found}
    except OSError:
        return None


def _title(content: str | None, private: bool) -> str:
    if private:
        return "A private note"
    first = next((line.strip() for line in (content or "").splitlines() if line.strip()), "")
    return (first[:60] + "…") if len(first) > 60 else (first or "Untitled note")


def missing_files(session, data_dir: Path) -> dict:  # noqa: ANN001  # an SQLAlchemy session
    """Attached files and pictures the database names and the disk lacks.

    Two queries and two directory listings, compared as sets, so the cost is
    the folders' size, not a `stat` per row."""
    from sqlalchemy import select

    from tessellate.core.database import Attachment, Entry, MediaUpload

    found: list[dict] = []
    uploads = _names(Path(data_dir) / "uploads") or set()
    rows = session.execute(
        select(Attachment.id, Attachment.entry_id, Attachment.filename, Attachment.stored_name, Entry.content, Entry.is_private)
        .join(Entry, Entry.id == Attachment.entry_id)
        .where(Entry.is_deleted == False)  # noqa: E712
        .order_by(Attachment.id)
    ).all()
    for attachment_id, entry_id, filename, stored, content, private in rows:
        if stored not in uploads:
            found.append({
                "kind": "attachment", "id": attachment_id, "entry_id": entry_id,
                "filename": filename, "note": _title(content, bool(private)),
            })
    media = _names(Path(data_dir) / "media") or set()
    for media_id, filename, original in session.execute(
        select(MediaUpload.id, MediaUpload.filename, MediaUpload.original_name).order_by(MediaUpload.id)
    ).all():
        if filename not in media:
            found.append({"kind": "media", "id": media_id, "entry_id": None, "filename": original or filename, "note": ""})
    return {"count": len(found), "items": found[:MISSING_LISTED]}


def run(config, session) -> dict:  # noqa: ANN001  # ConfigManager, SQLAlchemy session
    """The check, once at start and again from Settings, About, Health."""
    started = time.perf_counter()
    data_dir = Path(config.data_dir)
    repaired = recreate_folders(data_dir)
    for line in repaired:
        logger.warning("%s", line)
    try:
        missing = missing_files(session, data_dir)
    except Exception:  # noqa: BLE001  # the check reports; it never stops the start
        logger.warning("the attached files could not be checked", exc_info=True)
        missing = {"count": 0, "items": []}
    if missing["count"]:
        logger.warning("%d attached file(s) are missing from the data folder", missing["count"])
    with _lock:
        report = {
            "at": _now().isoformat(),
            "ms": round((time.perf_counter() - started) * 1000, 1),
            "repaired": list(_noted) + repaired,
            "missing_files": missing,
        }
        report["ok"] = not report["repaired"] and not missing["count"]
        _last.clear()
        _last.update(report)
    return dict(report)


def last_report() -> dict:
    with _lock:
        return dict(_last)


def forget_offer() -> None:
    """For a restore or a new account: the next look asks again."""
    with _lock:
        _offers.clear()


def restore_offer(db_path: Path, data_dir: Path, has_user: bool) -> dict | None:
    """The newest backup that holds notes, offered when this notebook has no
    account: the database was deleted, damaged, or its log lost. Never taken
    without the person: the lock screen asks (`POST /backups/restore`).

    Kept per process: the lock screen asks for it more than once, and each
    look opens backup files."""
    if has_user:
        return None
    key = str(Path(db_path).resolve())
    with _lock:
        if key in _offers:
            return _offers[key]
    from tessellate.core import backup

    offer = None
    try:
        candidates = backup.list_backups(Path(data_dir))[:5]
    except OSError:
        candidates = []
    for row in candidates:
        path = backup.backup_path(row["name"], Path(data_dir))
        counts = backup.notebook_counts(path) if path is not None else None
        if counts and (counts["notes"] or counts["documents"]):
            with _lock:
                kept = str(_start.get("damaged_kept_as", ""))
                missing = bool(_start.get("db_missing"))
            offer = {
                "name": row["name"],
                "created_at": row.get("created_at", ""),
                "notes": counts["notes"],
                "documents": counts["documents"],
                "reason": "damaged" if kept else ("missing" if missing else "empty"),
                "kept_as": kept,
            }
            break
    with _lock:
        _offers[key] = offer
    return offer
