"""Local database backups.

Copies are made with SQLite's own backup API, so a backup taken while
the app is writing is still consistent. Backups live in
data/backups/, next to the database, never in the cloud, and old
ones are pruned so the folder can't grow forever.
"""

from __future__ import annotations

import logging
import json
import os
import shutil
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from tessellate.core.logbuffer import safe_value

KEEP_BACKUPS = 10
# "Scheduled": a fresh backup is taken at startup when the newest one is
# older than this: boring, reliable, and works for an app that isn't
# running 24/7.
BACKUP_EVERY_HOURS = 24


#: What made a backup, in the words its row shows (INBOX 805, the owner:
#: "the backups need more file info and details"). Kept in a small record
#: beside the file (`<name>.json`), not in the name, so every backup taken
#: before this stays readable and restorable: it just says nothing about
#: where it came from.
ORIGINS: dict[str, str] = {
    "daily": "Automatic daily backup",
    "manual": "Made by you",
    "update": "Before an update",
    "restore": "Before a restore",
}


def _record_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.json")


def _write_record(path: Path, origin: str, checked: bool, **more: str) -> None:
    """Best-effort: a backup without its record is still a backup. `more` is
    where a second copy went (`copied_to`) or why it did not (`copy_error`)."""
    try:
        _record_path(path).write_text(json.dumps({"origin": origin, "checked": checked, **more}), encoding="utf-8")
    except OSError:
        logger.debug("could not write the record beside %s", path.name, exc_info=True)


def _read_record(path: Path) -> dict:
    try:
        data = json.loads(_record_path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def forget_record(path: Path) -> None:
    """Remove a backup's record with it (a delete, a prune)."""
    _record_path(path).unlink(missing_ok=True)


def backups_dir(data_dir: Path) -> Path:
    folder = data_dir / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def backup_path(name: str, data_dir: Path) -> Path | None:
    """The file a backup's name stands for, or None when the name would
    reach outside `backups/`. The name comes from a request, so the check is
    on the real path (links followed), not on the spelling."""
    folder = os.path.realpath(backups_dir(data_dir))
    candidate = os.path.realpath(os.path.join(folder, name))
    if not candidate.startswith(folder + os.sep):
        return None
    return Path(candidate)


def backup_files(data_dir: Path) -> list[Path]:
    """Every file in the backups folder that is actually a backup, newest first.

    **Zero bytes is not a backup, and saying otherwise is how a full disk
    becomes data loss.** Measured on a 80 MB tmpfs filled to 100%: `POST
    /backups` answered 507 (correctly), and left
    `memorymap-20260921-121338.db` behind at zero bytes, because the
    destination was opened by name and the copy then failed. A zero-byte file
    is a *valid empty SQLite database*: `PRAGMA integrity_check` on it
    returns "ok", so it listed as a backup, passed the restore guard, and
    restoring it would have replaced the notebook with nothing.
    `backup_now` no longer creates one (it copies to a temp name and renames
    only on success), and this filter is for the ones already sitting in
    people's folders from before that fix, and for anything else that
    truncates a file underneath us.
    """
    found = []
    for path in _snapshots(backups_dir(data_dir)):
        try:
            if path.stat().st_size > 0:
                found.append(path)
        except OSError:
            # Vanished between the glob and the stat, or unreadable: either
            # way it is not something a restore list should promise.
            continue
    return sorted(found, key=_newest_key, reverse=True)


def _newest_key(path: Path) -> tuple[str, int]:
    """Order by the name's stamp, then its same-second counter: by spelling,
    `...-051358.db` sorts after `...-051358-1.db` (a dot is after a dash),
    which put the older of two same-second backups first, and marked it
    "Latest"."""
    stem = path.name.removesuffix(".db")
    head, _, tail = stem.rpartition("-")
    if tail.isdigit() and len(tail) < 6 and head.count("-") == 2:
        return head, int(tail)
    return stem, 0


def list_backups(data_dir: Path) -> list[dict]:
    """Newest first; the first is `latest`. `origin` and `checked` come from
    the record beside the file, empty and None for a backup taken before
    there were records."""
    entries = []
    for index, path in enumerate(backup_files(data_dir)):
        stat = path.stat()
        record = _read_record(path)
        origin = str(record.get("origin") or "")
        entries.append(
            {
                "name": path.name,
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
                "latest": index == 0,
                "origin": origin,
                "origin_words": ORIGINS.get(origin, ""),
                "checked": True if record.get("checked") is True else None,
                #: Where the second copy went, or why it did not (Settings, Backups).
                "copied_to": str(record.get("copied_to") or ""),
                "copy_error": str(record.get("copy_error") or ""),
            }
        )
    return entries


#: The full-text tables a note's words are tokenised into. Both are FTS5,
#: and FTS5 deletes by writing a marker: the old tokens stay in the segment
#: blobs until a merge rewrites them.
FTS_TABLES = ("entries_fts", "search_index")


def optimize_fts(connection) -> None:  # noqa: ANN001  # SQLAlchemy or sqlite3 connection
    """Merge every FTS5 segment into one, which drops the tokens of deleted
    rows for good (SEC-03, security audit 2026-10-05). Takes a SQLAlchemy
    connection (the live database, `manager.scrub_private_leftovers`) or a
    plain sqlite3 one (a backup copy)."""
    run = getattr(connection, "exec_driver_sql", None) or connection.execute
    for table in FTS_TABLES:
        found = run(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if found:
            run(f"INSERT INTO {table}({table}) VALUES('optimize')")  # noqa: S608  # a fixed name


def strip_leftovers(target: sqlite3.Connection) -> None:
    """Clean a fresh copy of the database before it leaves as a backup: the
    FTS merge above, then VACUUM, which rewrites the file from live rows only,
    so no freed page or stale cell carries a private note's old words
    (SEC-03). For notebooks whose notes went private before the live
    database was scrubbed on the spot; costs about one more copy."""
    optimize_fts(target)
    target.commit()
    target.execute("VACUUM")


def snapshot(db_path: Path, destination: Path) -> None:
    """A consistent, cleaned copy of the live database at `destination`:
    SQLite's backup API (which reads through the WAL, unlike a file copy),
    then `strip_leftovers`."""
    source = sqlite3.connect(db_path)
    try:
        target = sqlite3.connect(destination)
        try:
            source.backup(target)
            #: The copy inherits the live file's WAL mode from its header, so
            #: opening it (the check below, a restore, a second copy) would
            #: leave `-wal` and `-shm` files beside it. A backup is one file:
            #: back to the rollback journal before it is cleaned and closed.
            target.execute("PRAGMA journal_mode=DELETE")
            strip_leftovers(target)
        finally:
            target.close()
    finally:
        source.close()


def copy_dir(data_dir: Path) -> Path | None:
    """The folder each backup is copied to as well (`backup_copy_dir`, Settings,
    Backups), or None. Read from the settings file itself: this module sits
    below the app's config, and the callers are many (the daily backup, Back up
    now, the safety copies before a restore and an update)."""
    try:
        raw = json.loads((Path(data_dir) / "preferences.json").read_text(encoding="utf-8")).get("backup_copy_dir")
    except (OSError, ValueError, AttributeError):
        return None
    return Path(raw) if isinstance(raw, str) and raw.strip() else None


def _copy_aside(destination: Path, target: Path, keep: int) -> None:
    """Put a whole copy of this backup in `target`, then hold that folder to
    `keep` backups. Raises OSError with words a person can read; the caller
    turns that into a note on the backup, never a failed backup. The same
    `.partial` then rename as the backup itself, so a full drive leaves no file
    that looks like a backup."""
    if not target.is_dir():
        raise OSError(f"{target} is not there. Is the drive connected?")
    if not os.access(target, os.W_OK):
        raise OSError(f"{target} cannot be written to.")
    partial = target / f"{destination.name}.partial"
    try:
        shutil.copyfile(destination, partial)
        os.replace(partial, target / destination.name)
    except OSError as exc:
        partial.unlink(missing_ok=True)
        raise OSError(f"could not copy to {target}: {exc.strerror or exc}") from exc
    record = _record_path(destination)
    if record.exists():
        shutil.copyfile(record, target / record.name)
    copies = sorted(
        (p for p in _snapshots(target) if p.is_file() and p.stat().st_size > 0), key=_newest_key, reverse=True
    )
    for old in copies[max(0, keep) :]:
        old.unlink(missing_ok=True)
        _record_path(old).unlink(missing_ok=True)


def backup_now(db_path: Path, data_dir: Path, keep: int = KEEP_BACKUPS, run=None, origin: str = "") -> Path:  # noqa: ANN001
    """Take one consistent snapshot and prune old ones.

    `keep` was a hard-coded 10 until asked about directly ("backup retention
    should be a setting, backups accumulate with no cap the user can see or
    change"). The prune itself was never the gap, this function has called
    `_prune` on every backup since it was written, only that the number was
    fixed in code instead of being a preference. `keep` defaults to the old
    constant so a caller that never heard of the preference keeps behaving
    exactly as before.
    """
    #: `run` is the `jobruns.Run` of the caller, when it has one: the steps
    #: and lines the Background tasks row shows while this works.
    run = run if run is not None else _NoRun()
    aside = copy_dir(data_dir)
    run.plan(["Copy the database", "Check the copy"] + (["Copy to your folder"] if aside else []) + ["Remove old backups"])
    run.say("Copying the database.")
    destination = _free_destination(backups_dir(data_dir), datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
    #: **The backup gets its name only once it is a whole backup.** Copying
    #: straight into `destination` means a copy that fails part-way (a full
    #: disk is the measured case) leaves a file named like a backup holding
    #: part of one, or none of one: see `backup_files` for what that costs.
    #: Same directory, so the rename is atomic and cannot itself run out of
    #: space; `.partial` is outside the `tessellate-*.db` glob, so a stray one
    #: is never listed, restored or counted against retention.
    partial = destination.with_name(f"{destination.name}.partial")
    try:
        snapshot(db_path, partial)
        os.replace(partial, destination)
        run.step(1)
        run.say("Checking the copy.")
        #: Every copy is checked now, not only one with a run to report to,
        #: so every row can say "checked" (INBOX 805).
        try:
            verify_copy(destination)
        except OSError:
            destination.unlink(missing_ok=True)
            raise
        run.step(2)
        more = _second_copy(destination, origin, aside, keep, run)
        _write_record(destination, origin, checked=True, **more)
    except BaseException:
        _discard_partial(partial)
        raise

    removed = prune(data_dir, keep)
    run.step(4 if aside else 3)
    run.say(f"Removed {removed} old backup{'' if removed == 1 else 's'}." if removed else "No old backups to remove.")
    return destination


class _NoRun:
    """A run nobody is watching: every report is dropped."""

    def plan(self, steps) -> None:  # noqa: ANN001
        pass

    def say(self, line: str) -> None:
        pass

    def step(self, number: int) -> None:
        pass


def _snapshots(folder: Path, suffix: str = ".db") -> list[Path]:
    """Snapshots under either name: those made before the rename keep theirs."""
    return [*folder.glob(f"tessellate-*{suffix}"), *folder.glob(f"memorymap-*{suffix}")]  # brand: keep


def _free_destination(folder: Path, stamp: str) -> Path:
    """The backup's path, never one already taken: two backups in the same
    second (e.g. the pre-restore safety copy right after a manual one) must
    never overwrite each other."""
    destination = folder / f"tessellate-{stamp}.db"
    counter = 1
    while destination.exists():
        destination = folder / f"tessellate-{stamp}-{counter}.db"
        counter += 1
    return destination


def _second_copy(destination: Path, origin: str, aside, keep: int, run) -> dict[str, str]:  # noqa: ANN001
    """The copy to the person's own folder, when one is set: what to record about it.
    A second copy that fails is a note on the backup, not a failed backup:
    the one in the data folder is whole and checked."""
    more: dict[str, str] = {}
    if aside is None:
        return more
    run.say(f"Copying to {aside}.")
    _write_record(destination, origin, checked=True)  # the record the copy carries
    try:
        _copy_aside(destination, aside, keep)
        more["copied_to"] = str(aside)
    except OSError as exc:
        logger.warning("the second copy of %s did not go to %s: %s", destination.name, aside, exc)
        more["copy_error"] = str(exc)
    run.step(3)
    run.say(f"Also copied to {aside}." if "copied_to" in more else f"Not copied: {more['copy_error']}")
    return more


def _discard_partial(partial: Path) -> None:
    """Remove what a failed copy left behind. Best-effort: never mask the real
    failure (out of space, usually) with the tidy-up that followed it."""
    for stray in (partial, Path(f"{partial}-wal"), Path(f"{partial}-shm")):
        try:
            stray.unlink(missing_ok=True)
        except OSError:
            pass  # best-effort, as above


def verify_copy(path: Path) -> None:
    """Open the finished copy and run SQLite's quick check, so a backup that
    cannot be read fails now rather than the day it is needed. Raises
    `OSError` (the caller already words that) when the copy is unreadable."""
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        row = connection.execute("PRAGMA quick_check").fetchone()
    except sqlite3.DatabaseError as exc:
        raise OSError(0, "the backup could not be read back") from exc
    finally:
        connection.close()
    if not row or row[0] != "ok":
        raise OSError(0, "the backup did not pass its check")


#: The notebook file's check at start (WORLD_CLASS 25e), kept so the page can
#: ask for it without running it again. `quick_check` rather than the full
#: `integrity_check`: measured on a 5,000-note notebook (scripts/scale_test.py,
#: 6 MB), 30 ms against 55 ms; it reads every page and finds the damage a
#: crash or a bad disk leaves, and skips only matching index entries to rows,
#: which the one-click full check in Settings, Health still does.
#: Keyed by the file's path, so a second notebook in one process (the tests,
#: a restore) never reads another file's answer.
_boot_checks: dict[str, dict] = {}
_boot_check_lock = threading.Lock()


def check_at_boot(db_path: Path) -> dict:
    """Run the quick check once per process and keep its answer.

    Called by the start-up housekeeping and by `GET /backups/integrity`,
    whichever comes first; the second gets the kept answer. A file SQLite
    cannot open at all is a failed check too, never an exception."""
    key = str(Path(db_path).resolve())
    with _boot_check_lock:
        if key in _boot_checks:
            return dict(_boot_checks[key])
        started = time.perf_counter()
        try:
            connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                rows = [str(row[0]) for row in connection.execute("PRAGMA quick_check").fetchmany(5)]
            finally:
                connection.close()
        except sqlite3.DatabaseError as exc:
            #: The driver's words stay in the log: the page gets a fixed
            #: sentence (the route returns this dict as it is).
            logger.error("the notebook file could not be read at start: %s", safe_value(str(exc)))
            rows = ["the file could not be read"]
        ok = rows == ["ok"]
        answer = _boot_checks[key] = {
            "check": "quick_check",
            "ok": ok,
            "result": "ok" if ok else "; ".join(rows)[:500],
            "ms": round((time.perf_counter() - started) * 1000, 1),
            "at": datetime.now(timezone.utc).isoformat(),
        }
        if not ok:
            logger.error("the notebook file failed its check at start: %s", safe_value(answer["result"]))
        return dict(answer)


class DamagedNotebookError(RuntimeError):
    """The notebook file failed its check and the app could not open it."""


def damaged_notebook_words(db_path: Path, data_dir: Path) -> str:
    """What to do when the file cannot be opened at all, so the page that
    would show the notice never loads: said in the log and in the desktop
    launcher's loading window instead. Names the newest backup and the two
    sidecar files, which would replay the damaged file's pages onto a good
    copy if left beside it."""
    answer = check_at_boot(db_path)
    try:
        newest = (list_backups(data_dir) or [None])[0]
    except OSError:
        newest = None
    if newest is None:
        way_back = "There is no local backup; a full backup file saved elsewhere can be restored after a fresh start."
    else:
        way_back = (
            f"Restore the newest backup: with the app closed, move {db_path.name} and any "
            f"{db_path.name}-wal and {db_path.name}-shm beside it somewhere safe, then copy "
            f"{backups_dir(data_dir) / newest['name']} to {db_path}."
        )
    return f"Your notebook file is damaged and could not be opened ({answer['result']}). {way_back}"


def forget_boot_check(db_path: Path) -> None:
    """For a restore, which replaces the file the answer was about."""
    with _boot_check_lock:
        _boot_checks.pop(str(Path(db_path).resolve()), None)


def prune(data_dir: Path, keep: int = KEEP_BACKUPS) -> int:
    """Delete every backup past the newest `keep`. Returns how many were
    removed, so a caller changing the limit can say how much that freed up
    rather than the user having to reload the list to find out."""
    stale = backup_files(data_dir)[max(0, keep) :]
    for path in stale:
        path.unlink(missing_ok=True)
        forget_record(path)
    _sweep_partials(data_dir)
    return len(stale)


#: How long a `.partial` has to sit there before it is assumed abandoned.
#: `backup_now` removes its own on any failure, so the only way one survives
#: is the process dying mid-copy (a kill, a power cut). An hour, rather than
#: "any that exist", because the startup backup and a click on Back up now
#: can overlap, and deleting a copy that is still being written would turn a
#: tidy-up into the bug it exists to prevent.
_PARTIAL_GRACE_SECONDS = 3600


def _sweep_partials(data_dir: Path) -> None:
    now = datetime.now(timezone.utc).timestamp()
    for path in _snapshots(backups_dir(data_dir), ".db.partial"):
        try:
            if now - path.stat().st_mtime > _PARTIAL_GRACE_SECONDS:
                path.unlink(missing_ok=True)
        except OSError:
            # Tidying up is never worth an exception out of a backup.
            continue


def backup_is_due(db_path: Path, data_dir: Path) -> bool:
    """Whether the startup backup should run: there is a database, and no
    backup newer than `BACKUP_EVERY_HOURS`. Split out so the caller can open
    the "last run" record only for a backup that is actually taken (INBOX
    438): a start that skips it is not a run."""
    if not db_path.exists():
        return False
    newest = next(iter(backup_files(data_dir)), None)
    if newest is not None:
        age_hours = (
            datetime.now(timezone.utc)
            - datetime.fromtimestamp(newest.stat().st_mtime, tz=timezone.utc)
        ).total_seconds() / 3600
        if age_hours < BACKUP_EVERY_HOURS:
            return False
    return True


def backup_if_due(db_path: Path, data_dir: Path, keep: int = KEEP_BACKUPS) -> Path | None:
    """Startup hook: back up unless a recent backup already exists."""
    if not backup_is_due(db_path, data_dir):
        return None
    return backup_now(db_path, data_dir, keep, origin="daily")


logger = logging.getLogger(__name__)

#: What the person reads when a backup fails its integrity check; the check's
#: own output goes to the log, where it can be of use to somebody who can act
#: on it.
DAMAGED_BACKUP = (
    "That backup is damaged, so it was not restored. Your current notes "
    "have not been touched."
)


def restore_backup(name: str, db_path: Path, data_dir: Path, keep: int = KEEP_BACKUPS) -> None:
    """Replace the live database with a backup.

    The caller MUST dispose every open engine first and rebuild it after
    (deps.reload_db does both). A safety snapshot of the current state is
    taken before overwriting, so even a restore is undoable."""
    source_path = backup_path(name, data_dir)
    if source_path is None or not source_path.is_file():
        raise FileNotFoundError("That backup could not be found.")
    restore_file(source_path, db_path, data_dir, keep, label=name)


def restore_file(
    source_path: Path, db_path: Path, data_dir: Path, keep: int = KEEP_BACKUPS, label: str | None = None
) -> None:
    """`restore_backup` for a database file wherever it is (a backup's own,
    or one unpacked from an imported zip): the same safety snapshot, the same
    check on a temp copy before the atomic swap."""
    name = label or source_path.name
    if db_path.exists():
        backup_now(db_path, data_dir, keep, origin="restore")  # the pre-restore safety copy

    # Restore into a temp file that sits beside db_path (same filesystem, so
    # the os.replace below is atomic) instead of streaming pages straight
    # into memorymap.db: a crash mid-copy used to be able to leave the live
    # database half-written, with the pre-restore safety copy above as the
    # only way back. The integrity check runs BEFORE the replace, not after:
    # once the temp file has been renamed onto db_path it *is* the live
    # database, so checking it then would only confirm damage already done.
    # Checking first catches a corrupt backup while it is still a throwaway
    # temp file nobody depends on.
    tmp_path = db_path.with_name(f"{db_path.name}.restore-tmp")
    try:
        source = sqlite3.connect(source_path)
        try:
            target = sqlite3.connect(tmp_path)
            try:
                source.backup(target)
            finally:
                target.close()
        finally:
            source.close()

        checker = sqlite3.connect(tmp_path)
        try:
            try:
                row = checker.execute("PRAGMA integrity_check").fetchone()
            except sqlite3.DatabaseError as exc:
                # Some corruption fails inside the check itself rather than
                # coming back as a non-"ok" row; both mean the same thing.
                logger.warning("Backup %s failed its integrity check: %s", safe_value(name, 120), exc)
                raise ValueError(DAMAGED_BACKUP) from exc
        finally:
            checker.close()
        if row is None or row[0] != "ok":
            logger.warning("Backup %s failed its integrity check: %s", safe_value(name, 120), row)
            raise ValueError(DAMAGED_BACKUP)
        #: **"ok" is not the same as "has anything in it."** An empty file is
        #: a valid SQLite database with no tables, and passes the check
        #: above; restoring one replaces the notebook with nothing and the
        #: pre-restore safety copy is the only way back. A real backup of
        #: this app always has tables, so a table count of zero is the one
        #: unambiguous "this is not a notebook" test available here.
        checker = sqlite3.connect(tmp_path)
        try:
            tables = checker.execute(
                "SELECT count(*) FROM sqlite_master WHERE type = 'table'"
            ).fetchone()[0]
        finally:
            checker.close()
        if not tables:
            raise ValueError(
                "That backup is empty, so restoring it would replace your "
                "notebook with nothing. It was most likely written when this "
                "computer was out of disk space."
            )

        os.replace(tmp_path, db_path)
        # The start-up answer was about the file just replaced; the restored
        # copy passed its own check above, so the notice must not outlive it.
        forget_boot_check(db_path)
        # The database runs in WAL mode (database.py), so db_path may still
        # have a -wal/-shm pair from before the restore, holding frames for
        # the database that just got replaced. Left in place they would be
        # replayed onto the new file on its first connection, quietly
        # bringing back rows the restore was meant to remove. The temp
        # file's own sidecars (if the copy created any) are orphaned by the
        # rename under their old name and are cleaned up the same way.
        for stale in (db_path, tmp_path):
            Path(f"{stale}-wal").unlink(missing_ok=True)
            Path(f"{stale}-shm").unlink(missing_ok=True)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        Path(f"{tmp_path}-wal").unlink(missing_ok=True)
        Path(f"{tmp_path}-shm").unlink(missing_ok=True)
        raise
