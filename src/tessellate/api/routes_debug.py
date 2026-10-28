"""`GET /debug/health`, observability that costs nothing (PLAN.md B9).

Every number here already exists somewhere: `routes_tasks.collect()` already
builds the running-jobs list, `taskhistory` already remembers how each job
ended, `logbuffer` already tails the app log. This route is deliberately not
a new subsystem, just a single cheap read across the ones that exist,
because the thing being asked for is a page that answers "is this notebook
okay" in one glance: a support-bundle-sized diagnostic would defeat that.

**The <20ms budget is the whole design constraint.** Every count below is a
`COUNT(*)` filtered only by an indexed `workspace_id` (`WorkspaceMixin`
gives every one of these tables that index), nothing here does the thing
`support_bundle` can afford to (`entries_deleted`, `entries_private`, a
second query per flag): those extra WHERE clauses are still full scans of
the same rows without a matching composite index, and irrelevant to "is
this notebook alive", so they were deliberately left out of this endpoint
and left in that one, which has no latency budget at all.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate import __version__
from tessellate.api import routes_tasks
from tessellate.core import deps, jobs, logbuffer, taskhistory
from tessellate.core.database import Attachment, Document, Entry, MediaUpload, Reminder
from tessellate.core.deps import get_session

router = APIRouter(prefix="/debug", tags=["debug"])

#: How many recent error/warning lines to surface, enough to see whether
#: something is actively wrong without turning this into the Logs viewer
#: (which already exists, and pages).
ERROR_TAIL = 20

#: The levels a person means by "errors" here. `logbuffer` also carries INFO
#: and DEBUG lines, which would drown the two levels anyone actually opens
#: this page to check for.
_ERROR_LEVELS = frozenset({"ERROR", "WARNING"})


def shown_path(path) -> str:  # noqa: ANN001  # a Path or a str
    """Where a folder is, said without the server's absolute path.

    WORLD_CLASS_PLAN §12, Brief 15 (INBOX 310): this route handed back the
    full `data_dir` and database path. Harmless behind the unlock gate on
    localhost; for anyone holding a token once other devices can connect, a
    map of the server's disk with the account name in it. Settings, About
    only needs to say where the notebook lives, so a folder under home is
    `~/...` and anything else is its own name after an ellipsis.
    """
    folder = Path(path)
    try:
        resolved = folder.resolve()
        home = Path.home().resolve()
    except (OSError, RuntimeError):
        return "\u2026" + os.sep + folder.name
    if resolved == home:
        return "~"
    if resolved.is_relative_to(home):
        return "~" + os.sep + str(resolved.relative_to(home))
    return "\u2026" + os.sep + folder.name


def _db_name(config) -> str:  # noqa: ANN001
    """The database file relative to the data folder, never absolute."""
    try:
        return str(Path(config.db_path).resolve().relative_to(Path(config.data_dir).resolve()))
    except (OSError, ValueError):
        return Path(config.db_path).name


@router.get("/health")
def debug_health(session: Session = Depends(get_session)) -> dict:
    """One page's worth of "is this notebook okay", Settings › About reads
    this to draw its Health block, and it is meant to be safe to hit from a
    bug report too: nothing here is note content, nothing here writes.
    """
    config = deps.get_config()
    try:
        db_size_bytes = config.db_path.stat().st_size
    except OSError:
        # A brand new notebook, or a data dir moved out from under the
        # process: 0 is the honest answer, not a 500 over a stat() call.
        db_size_bytes = 0

    live = Entry.is_deleted == False  # noqa: E712
    counts = {
        # Every live row, boards and drafts included: the database's own
        # number, kept for anything that already reads it.
        "entries": session.scalar(select(func.count(Entry.id)).where(live)) or 0,
        #: **The three kinds a person would count separately.** Settings,
        #: About said "96 notes" for a notebook whose dashboard said 44: the
        #: other 52 were 50 boards and maps (an Entry with `is_board`) and 2
        #: drafts. The same split the dashboard's own figure uses
        #: (routes_insights.py), so the two can never disagree again.
        "notes": session.scalar(
            select(func.count(Entry.id)).where(
                live, Entry.is_board == False, Entry.is_draft == False  # noqa: E712
            )
        )
        or 0,
        "drafts": session.scalar(
            select(func.count(Entry.id)).where(
                live, Entry.is_board == False, Entry.is_draft == True  # noqa: E712
            )
        )
        or 0,
        "boards": session.scalar(
            select(func.count(Entry.id)).where(live, Entry.is_board == True)  # noqa: E712
        )
        or 0,
        "documents": session.scalar(select(func.count(Document.id))) or 0,
        "media": session.scalar(select(func.count(MediaUpload.id))) or 0,
        "attachments": session.scalar(select(func.count(Attachment.id))) or 0,
        "reminders": session.scalar(select(func.count(Reminder.id))) or 0,
    }

    running_jobs = routes_tasks.collect()
    error_lines = [
        record
        for record in logbuffer.recent(limit=logbuffer.MAX_RECORDS)
        if record.get("level") in _ERROR_LEVELS
    ][-ERROR_TAIL:]

    return {
        "app_version": __version__,
        "data_dir": shown_path(config.data_dir),
        "db": {"path": _db_name(config), "size_bytes": db_size_bytes},
        "counts": counts,
        # A "more queued" row (`jobs.pending`) stands for that many jobs.
        "jobs": {
            "queue_depth": sum(int(row.get("more") or 1) for row in running_jobs),
            "running": running_jobs,
        },
        "latency_ms_by_kind": taskhistory.latency_percentiles(),
        "recent_errors": error_lines,
        "trust": _trust(config, error_lines),
    }


#: The last integrity check, so the page can say when it last ran without
#: running it again (a full `PRAGMA integrity_check` reads every page).
_last_integrity: dict = {"at": None, "ok": None, "result": "", "index": {}}


def _dir_bytes(path: Path, deadline: float | None = None) -> tuple[int, bool]:
    """`(bytes, complete)`: the folder's size, stopping at `deadline` (a
    `time.monotonic()` value) with what was counted so far."""
    total = 0
    for root, _dirs, files in os.walk(path):
        if deadline is not None and time.monotonic() > deadline:
            return total, False
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                continue
    return total, True


#: **The folder's size is measured once in a while, not on every read**
#: (INBOX 1426 L1: `/debug/health` took 10.9s the moment Settings opened). It
#: walks every file under the data folder, which on Windows with thousands of
#: uploads and caches, each stat checked by the virus scanner, is seconds.
#: A figure under `DIR_BYTES_TTL` old is served as it is; an older one is
#: served too, and measured again on a thread of the pool; the very first ask
#: walks for at most `DIR_BYTES_FIRST_BUDGET`, then answers with what it
#: counted and `data_dir_bytes_partial`, the walk finishing behind it.
DIR_BYTES_TTL = 120.0
DIR_BYTES_FIRST_BUDGET = 1.0
_dir_cache: dict = {"bytes": None, "at": 0.0, "walking": False, "partial": False, "path": ""}
_dir_lock = threading.Lock()


def _measure_dir_in_background(path: Path) -> None:
    try:
        total, _ = _dir_bytes(path)
        with _dir_lock:
            _dir_cache.update({"bytes": total, "at": time.monotonic(), "partial": False, "path": str(path)})
    finally:
        with _dir_lock:
            _dir_cache["walking"] = False


def _data_dir_size(path: Path) -> tuple[int, bool]:
    """`(bytes, partial)` for the Health page; see `DIR_BYTES_TTL`."""
    now = time.monotonic()
    with _dir_lock:
        same = _dir_cache["path"] == str(path)
        known = _dir_cache["bytes"] if same else None
        partial = bool(_dir_cache["partial"]) if same else False
        if known is not None and not partial and now - _dir_cache["at"] < DIR_BYTES_TTL:
            return known, False
        start = not _dir_cache["walking"]
        if start:
            _dir_cache["walking"] = True
    if known is not None:
        # Stale, or a first partial count still being finished: serve it.
        if start:
            _queue_dir_walk(path)
        return known, partial
    if not start:
        return 0, True  # another ask is walking it for the first time
    # Nothing measured yet: walk here, briefly, so a small notebook still
    # answers with its real size on the first ask.
    total, complete = _dir_bytes(path, deadline=time.monotonic() + DIR_BYTES_FIRST_BUDGET)
    if complete:
        with _dir_lock:
            _dir_cache.update({"bytes": total, "at": time.monotonic(), "partial": False, "path": str(path), "walking": False})
        return total, False
    with _dir_lock:
        _dir_cache.update({"bytes": total, "partial": True, "path": str(path), "at": 0.0})
    _queue_dir_walk(path)
    return total, True


def _queue_dir_walk(path: Path) -> None:
    try:
        jobs.enqueue("maintenance", _measure_dir_in_background, path, name="measure the notebook folder")
    except Exception:  # noqa: BLE001  # the figure stays as it was; the next ask tries again
        with _dir_lock:
            _dir_cache["walking"] = False


def _trust(config, error_lines: list[dict]) -> dict:  # noqa: ANN001
    """Rule 14's fields (WORLD_CLASS_PLAN 28.1), each present and dated:
    when it was last true, or None where it never was."""
    from datetime import datetime, timezone

    from tessellate.core import backup

    try:
        newest = (backup.list_backups(config.data_dir) or [None])[0]
    except OSError:
        newest = None
    last_error = error_lines[-1] if error_lines else None
    data_dir_bytes, data_dir_partial = _data_dir_size(Path(config.data_dir))
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "last_backup": {"at": newest["created_at"], "name": newest["name"]} if newest else {"at": None, "name": ""},
        "last_error": {"at": last_error.get("time"), "line": str(last_error.get("message", ""))[:300]} if last_error else {"at": None, "line": ""},
        "running": routes_tasks.activity_rows(),
        "data_dir_bytes": data_dir_bytes,
        "data_dir_bytes_partial": data_dir_partial,
        "integrity": dict(_last_integrity),
    }


@router.post("/health/integrity")
def integrity_check(session: Session = Depends(get_session)) -> dict:
    """The integrity check in one click: SQLite's own `integrity_check` and
    the search index's rows per kind beside the notebook's own counts."""
    from datetime import datetime, timezone

    from sqlalchemy import text

    from tessellate.search import engine

    rows = [str(row[0]) for row in session.execute(text("PRAGMA integrity_check")).fetchall()]
    try:
        index = engine.stats(session).get("index", {})
    except Exception:  # noqa: BLE001  # an unreadable index is a finding, not a 500
        index = {}
    notes = session.scalar(
        select(func.count(Entry.id)).where(Entry.is_deleted == False, Entry.is_board == False, Entry.is_draft == False)  # noqa: E712
    ) or 0
    result = {
        "at": datetime.now(timezone.utc).isoformat(),
        "ok": rows == ["ok"],
        "result": "ok" if rows == ["ok"] else "; ".join(rows[:5]),
        "index": {"notes": notes, **{str(k): v for k, v in (index.items() if isinstance(index, dict) else [])}},
    }
    _last_integrity.update(result)
    return result
