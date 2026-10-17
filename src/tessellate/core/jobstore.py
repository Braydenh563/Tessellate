"""The durable half of the job runtime (WORLD_CLASS_PLAN B2).

`core/jobs.py` is the bounded pool: lanes, widths, dedupe, the panel's rows.
It forgot everything when the process ended, which its docstring defended
("every job re-derives its result from a row that is already committed, so
the next launch can redo it"). Nothing did redo it: a folder of 200 pictures
dropped on the app, then a quit, left 150 of them without their text until
each was saved again by hand. This module is what makes the next launch
redo it.

**The shape.** A `jobs` row per queued piece of work (`DurableJob`):

- `record` writes the row when the pool queues a job whose kind has a
  handler here and whose arguments are plain data. The pool still runs the
  function object it was handed; the row is only the memory of it.
- `lease` is the worker's claim, one atomic UPDATE from `queued` to
  `running` carrying this process's `owner` token and a `lease_until`. A
  heartbeat thread renews every lease this process holds while it holds
  any, and stops when it holds none, so an idle app runs no extra thread.
- `finish` records the ending: `done`, `failed` with its reason.
- `resume`, at launch, queues again every `queued` row and every `running`
  row whose lease has lapsed (its process is gone). A lease still valid and
  owned elsewhere is a live second server on the same file (a direct
  uvicorn start skips `core/instance_lock.py`): it is left alone and looked
  at again when the lease would have run out, which is what a lease is for.

**Handlers are named, never pickled.** `HANDLERS` maps a kind to
"module:function". A row holds the kind and JSON arguments, so a notebook
cannot be made to run code by editing its database, and a function that was
renamed fails one job with a sentence rather than the launch. A job queued
with any other function (a test's stand-in, a lambda) runs exactly as
before and is simply not remembered: `durable_kind` compares the function's
own dotted name with the table's.

**A poison job stops.** A row is tried at most `MAX_ATTEMPTS` times. A job
that takes the process down with it (a native crash in Tesseract) would
otherwise crash every launch after it, which is the one way durability can
make an app worse than forgetting.

**Cancel** stops a queued job (the row goes to `cancelled` and the worker's
lease then fails). A running job is not interrupted, for the reason
`core/bgtasks.py` gives: Python cannot stop a thread safely, and the work
writes to a notebook someone cares about. The answer says so.

**Bookkeeping never breaks the job**, the rule `core/jobruns.py` set: every
write here is wrapped, and a failure costs the durability of one job, never
the job. With no app database (a script, most tests) nothing is recorded.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger("tessellate.jobstore")

#: kind -> "module:function". The handler must be idempotent: a resumed job
#: may repeat work a killed process had half done. Each of these checks its
#: stored result first (the "once per picture" guards), which is why these
#: and not every kind the pool runs.
HANDLERS: dict[str, str] = {
    "ocr": "tessellate.core.ocr:extract_and_store",
    "caption": "tessellate.ai.captioning:caption_and_store",
    "vision": "tessellate.ai.vision_ocr:vision_ocr_and_store",
    "vision-pdf": "tessellate.ai.vision_ocr:pdf_vision_ocr_and_store",
    "document": "tessellate.ai.docreader:read_document_and_store",
    "file-entry": "tessellate.api.routes_entries:_file_entry_in_background",
    #: Resumes where it stopped: staged vectors for the same target are kept.
    "embed-switch": "tessellate.core.embedswitch:run",
    #: Tidy's link reason pass (INBOX 691): idempotent, a named link no
    #: longer matches, so a resumed pass repeats nothing.
    "tidy-link-reasons": "tessellate.entry.tidy:respecify_all",
    #: Brief 9, the rest of B2. Each looks up the app's own state when it
    #: runs and is safe to repeat: a re-index replaces each vector, a pull
    #: keeps the layers Ollama already has, a scheduled pass (a backup, the
    #: embedding backfill, the scores, housekeeping) does its whole job
    #: again, and an autonomous pass re-reads its master switch first.
    "reindex": "tessellate.ai.model_manager:reindex_notebook",
    "pull": "tessellate.ai.model_manager:pull_model",
    "pass": "tessellate.core.passes:run_pass",
    "autonomous": "tessellate.ai.autonomous:run_pass",
    #: A chosen folder of notes. Its runner skips a file by path and text
    #: hash, so a resumed job finishes the folder rather than doubling it.
    "import": "tessellate.api.routes_settings:_run_directory_import",
}

#: A lease lasts this long without a heartbeat. Long enough that a busy
#: SQLite file delaying one renewal does not hand a live job to a second
#: worker; short enough that a killed job is picked up within half a minute
#: by a launch that found its lease still standing.
LEASE_SECONDS = 30.0
HEARTBEAT_SECONDS = LEASE_SECONDS / 3

#: Tries per row, the first included. Three: one kill is a quit, two is bad
#: luck, three is the job.
MAX_ATTEMPTS = 3

#: Finished rows kept for the panel and `GET /jobs`: a week, at most this
#: many. Pruned at launch, not per job, so finishing stays one UPDATE.
KEEP_FINISHED_DAYS = 7
KEEP_FINISHED_ROWS = 500

ACTIVE_STATES = ("queued", "running")

#: This process's name on the rows it leases. The pid for a person reading
#: the table, a random tail because pids are reused.
OWNER = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"

_MAX_TEXT = 300


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clip(text: object) -> str:
    one_line = " ".join(str(text or "").split())
    return one_line if len(one_line) <= _MAX_TEXT else one_line[: _MAX_TEXT - 1] + "…"


def _database(db):  # noqa: ANN001, ANN202
    """The caller's database, else the app's own, else None. Through
    `jobruns`, which `core/deps.py` already tells where the database is;
    importing `deps` here would close the cycle `jobruns` documents."""
    from tessellate.core import jobruns

    return jobruns.peek_database(db)


def peek_db(db=None):  # noqa: ANN001, ANN201
    """Public `_database`, for the pool."""
    return _database(db)


# -- change notification, for `/jobs/stream` ---------------------------------

_version = 0
_version_lock = threading.Lock()


def _changed() -> None:
    global _version
    with _version_lock:
        _version += 1


def version() -> int:
    """Bumped on every write here. The stream compares it, rather than
    re-reading the table on a timer, so an idle panel costs no queries."""
    with _version_lock:
        return _version


# -- payloads -----------------------------------------------------------------


class NotDurable(ValueError):
    """The arguments are not plain data, so the job cannot be remembered."""


def _encode(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return {"__path__": str(value)}
    if isinstance(value, (list, tuple)):
        return [_encode(item) for item in value]
    raise NotDurable(type(value).__name__)


def _decode(value: object) -> object:
    if isinstance(value, dict) and set(value) == {"__path__"}:
        return Path(value["__path__"])
    if isinstance(value, list):
        return [_decode(item) for item in value]
    return value


def _as_key(value: object) -> object:
    """A dedupe key back from JSON: lists were tuples (a list is not
    hashable, and the pool compares keys with `==` against tuples)."""
    if isinstance(value, list):
        return tuple(_as_key(item) for item in value)
    return value


def encode_payload(args: tuple, kwargs: dict) -> str:
    return json.dumps({"args": [_encode(a) for a in args], "kwargs": {k: _encode(v) for k, v in kwargs.items()}})


def decode_payload(text: str) -> tuple[tuple, dict]:
    data = json.loads(text or "{}")
    args = tuple(_decode(a) for a in data.get("args") or [])
    kwargs = {str(k): _decode(v) for k, v in (data.get("kwargs") or {}).items()}
    return args, kwargs


# -- handlers -----------------------------------------------------------------


def register(kind: str, target: str) -> None:
    """Name a handler for `kind`. For a script or a test; the app's own
    kinds are the table above."""
    HANDLERS[kind] = target


def _dotted(func: object) -> str:
    return f"{getattr(func, '__module__', '')}:{getattr(func, '__qualname__', '')}"


def durable_kind(kind: str, func: object) -> bool:
    """True when `func` is the handler named for `kind`, so a resumed row
    would run the same code the pool was handed."""
    target = HANDLERS.get(kind)
    return bool(target) and _dotted(func) == target


def resolve(kind: str):  # noqa: ANN201
    """The handler function for `kind`, imported by name."""
    target = HANDLERS.get(kind)
    if not target or ":" not in target:
        raise LookupError(f"no handler for {kind!r}")
    module_name, _, attr = target.partition(":")
    obj = importlib.import_module(module_name)
    for part in attr.split("."):
        obj = getattr(obj, part)
    return obj


# -- the writes ---------------------------------------------------------------


def record(kind: str, args: tuple, kwargs: dict, name: str = "", dedupe_key: object = None, db=None) -> int | None:  # noqa: ANN001
    """Remember a queued job. Returns its row id, or None when it is not
    remembered (no database, arguments that are not data, a failed write)."""
    db = _database(db)
    if db is None:
        return None
    try:
        payload = encode_payload(args, kwargs)
        key = json.dumps(_encode(dedupe_key)) if dedupe_key is not None else None
    except (NotDurable, TypeError, ValueError):
        return None
    try:
        from tessellate.core.database import DurableJob

        with db.session() as session:
            row = DurableJob(kind=kind, name=_clip(name)[:200], payload=payload, dedupe_key=key, state="queued")
            session.add(row)
            session.commit()
            job_id = int(row.id)
        _changed()
        return job_id
    except Exception:  # noqa: BLE001  # bookkeeping must never break the job
        logger.debug("could not record a %s job", kind, exc_info=True)
        return None


def lease(job_id: int, db=None) -> bool:  # noqa: ANN001
    """Claim a queued row for this process. False when it was cancelled,
    already finished, or claimed by someone else: the worker then skips it.
    True too when the bookkeeping itself failed, because a job that cannot
    be recorded still runs (the module's one rule)."""
    db = _database(db)
    if db is None:
        return True
    try:
        from sqlalchemy import update

        from tessellate.core.database import DurableJob

        now = _now()
        with db.session() as session:
            claimed = session.execute(
                update(DurableJob)
                .where(DurableJob.id == job_id, DurableJob.state == "queued")
                .values(
                    state="running",
                    owner=OWNER,
                    lease_until=now + timedelta(seconds=LEASE_SECONDS),
                    heartbeat=now,
                    started_at=now,
                    attempts=DurableJob.attempts + 1,
                )
            ).rowcount
            session.commit()
        if not claimed:
            return False
        _hold(job_id, db)
        _changed()
        return True
    except Exception:  # noqa: BLE001
        logger.debug("could not lease job %s", job_id, exc_info=True)
        return True


def finish(job_id: int, error: str = "", result: str = "", db=None) -> None:  # noqa: ANN001
    """Record the ending of a job this process leased."""
    db = _database(db)
    _release(job_id)
    if db is None:
        return
    try:
        from sqlalchemy import update

        from tessellate.core.database import DurableJob

        with db.session() as session:
            session.execute(
                update(DurableJob)
                .where(DurableJob.id == job_id, DurableJob.owner == OWNER, DurableJob.state == "running")
                .values(
                    state="failed" if error else "done",
                    error=_clip(error),
                    result=_clip(result),
                    finished_at=_now(),
                    lease_until=None,
                )
            )
            session.commit()
        _changed()
    except Exception:  # noqa: BLE001
        logger.debug("could not record the end of job %s", job_id, exc_info=True)


def supersede(job_id: int, db=None) -> None:  # noqa: ANN001
    """Close a queued row whose work an identical job already in hand will
    do (the pool's dedupe matched it)."""
    db = _database(db)
    if db is None:
        return
    try:
        from sqlalchemy import update

        from tessellate.core.database import DurableJob

        with db.session() as session:
            session.execute(
                update(DurableJob)
                .where(DurableJob.id == job_id, DurableJob.state == "queued")
                .values(state="done", result="Done by an identical job.", finished_at=_now())
            )
            session.commit()
        _changed()
    except Exception:  # noqa: BLE001
        logger.debug("could not close job %s", job_id, exc_info=True)


def cancel(job_id: int, db=None) -> tuple[bool, str]:  # noqa: ANN001
    """Stop a queued job. (stopped, sentence); never raises."""
    db = _database(db)
    if db is None:
        return False, "No job with that number."
    try:
        from sqlalchemy import update

        from tessellate.core.database import DurableJob

        with db.session() as session:
            row = session.get(DurableJob, job_id)
            if row is None:
                return False, "No job with that number."
            if row.state == "running":
                return False, "It is already running and will finish: a running job is not interrupted."
            if row.state != "queued":
                return False, "It had already finished."
            stopped = session.execute(
                update(DurableJob)
                .where(DurableJob.id == job_id, DurableJob.state == "queued")
                .values(state="cancelled", finished_at=_now())
            ).rowcount
            session.commit()
        if not stopped:
            return False, "It started just now and will finish."
        _changed()
        _forget(job_id)
        return True, "Stopped before it started."
    except Exception:  # noqa: BLE001
        logger.warning("could not cancel a job", exc_info=True)
        return False, "Couldn't stop that job, see Settings → Logs."


def cancel_queued(kind: str, name: str = "", db=None) -> int:  # noqa: ANN001
    """Cancel every queued row of `kind` (and `name`, when given): the
    activity panel's Quit on a queued pool row, which knows a kind and a
    name, not a row id. Returns how many stopped."""
    db = _database(db)
    if db is None:
        return 0
    try:
        from sqlalchemy import select

        from tessellate.core.database import DurableJob

        with db.session() as session:
            query = select(DurableJob.id).where(DurableJob.kind == kind, DurableJob.state == "queued")
            if name:
                query = query.where(DurableJob.name == name)
            ids = list(session.scalars(query))
    except Exception:  # noqa: BLE001
        logger.debug("could not read the queued jobs of one kind", exc_info=True)
        return 0
    return sum(1 for job_id in ids if cancel(job_id, db=db)[0])


#: The pool's "drop this queued job from memory", set by `core/jobs.py`
#: (`set_forget`). A hook rather than an import: the pool imports this
#: module, and the reverse edge would be a cycle
#: (`tests/test_no_import_cycles.py`).
_forget = lambda job_id: None  # noqa: E731


def set_forget(callback) -> None:  # noqa: ANN001
    global _forget
    _forget = callback


# -- the heartbeat ------------------------------------------------------------

_held: dict[int, object] = {}
_held_lock = threading.Lock()
# The heartbeat thread while it runs, in a container rather than a module
# global so it is set and read without `global`.
_beater: dict = {"thread": None}
#: Starts `_beat` on a thread and returns it. `core/jobs.py` sets it when it
#: loads, so the one module that starts threads for jobs is the pool's own
#: (tests/test_flaw_class_lints.py, THREAD_SITES); until then, nothing beats.
start_beater = None


def _hold(job_id: int, db) -> None:  # noqa: ANN001
    with _held_lock:
        _held[job_id] = db
        thread = _beater["thread"]
        if start_beater is not None and (thread is None or not thread.is_alive()):
            _beater["thread"] = start_beater(_beat)


def _release(job_id: int) -> None:
    with _held_lock:
        _held.pop(job_id, None)


def held() -> list[int]:
    with _held_lock:
        return sorted(_held)


def _beat() -> None:
    """Renew every lease this process holds; end when it holds none."""
    while True:
        time.sleep(HEARTBEAT_SECONDS)
        with _held_lock:
            if not _held:
                _beater["thread"] = None
                return
            by_db: dict[int, tuple[object, list[int]]] = {}
            for job_id, db in _held.items():
                by_db.setdefault(id(db), (db, []))[1].append(job_id)
        for db, ids in by_db.values():
            renew(ids, db=db)


def renew(ids: list[int], db=None) -> int:  # noqa: ANN001
    """Push the lease of `ids` forward. Returns how many rows it touched."""
    db = _database(db)
    if db is None or not ids:
        return 0
    try:
        from sqlalchemy import update

        from tessellate.core.database import DurableJob

        now = _now()
        with db.session() as session:
            touched = session.execute(
                update(DurableJob)
                .where(DurableJob.id.in_(ids), DurableJob.owner == OWNER, DurableJob.state == "running")
                .values(heartbeat=now, lease_until=now + timedelta(seconds=LEASE_SECONDS))
            ).rowcount
            session.commit()
        return int(touched or 0)
    except Exception:  # noqa: BLE001
        logger.debug("could not renew job leases", exc_info=True)
        return 0


# -- launch -------------------------------------------------------------------


def resume(db=None, enqueue=None) -> dict:  # noqa: ANN001
    """Queue again what a closed or killed process left. Called once at launch.

    `enqueue(kind, func, args, kwargs, name, dedupe_key, job_id)` is the
    pool's own resubmission (`jobs.resume` passes `jobs.resubmit`), passed
    in so this module never names the pool. Returns counts by outcome.
    """
    db = _database(db)
    counts = {"resumed": 0, "gave_up": 0, "waiting": 0, "unknown": 0}
    if db is None or enqueue is None:
        return counts
    try:
        from sqlalchemy import select, update

        from tessellate.core.database import DurableJob

        now = _now()
        later: float | None = None
        to_run: list[tuple[int, str, str, str, str | None]] = []
        with db.session() as session:
            rows = list(session.scalars(select(DurableJob).where(DurableJob.state.in_(ACTIVE_STATES)).order_by(DurableJob.id)))
            for row in rows:
                if row.state == "running":
                    lease_until = row.lease_until
                    if lease_until is not None and lease_until.tzinfo is None:
                        lease_until = lease_until.replace(tzinfo=timezone.utc)
                    if row.owner == OWNER:
                        continue  # this process's own, still working
                    if lease_until is not None and lease_until > now:
                        wait = (lease_until - now).total_seconds()
                        later = wait if later is None else min(later, wait)
                        counts["waiting"] += 1
                        continue
                if (row.attempts or 0) >= MAX_ATTEMPTS:
                    session.execute(
                        update(DurableJob)
                        .where(DurableJob.id == row.id)
                        .values(
                            state="failed",
                            finished_at=now,
                            lease_until=None,
                            error=f"Stopped {row.attempts} times before it finished, so it was not tried again.",
                        )
                    )
                    counts["gave_up"] += 1
                    continue
                if row.kind not in HANDLERS:
                    session.execute(
                        update(DurableJob)
                        .where(DurableJob.id == row.id)
                        .values(state="failed", finished_at=now, lease_until=None, error="This version of the app no longer runs that kind of job.")
                    )
                    counts["unknown"] += 1
                    continue
                session.execute(
                    update(DurableJob)
                    .where(DurableJob.id == row.id)
                    .values(state="queued", owner="", lease_until=None)
                )
                to_run.append((int(row.id), row.kind, row.payload, row.name or "", row.dedupe_key))
            session.commit()
        if counts["gave_up"] or counts["unknown"] or to_run:
            _changed()
        for job_id, kind, payload, name, key in to_run:
            try:
                func = resolve(kind)
                args, kwargs = decode_payload(payload)
                dedupe = _as_key(json.loads(key)) if key else None
            except Exception:  # noqa: BLE001  # one bad row fails alone
                #: The row is shown in Background jobs, so it says what
                #: happened in a sentence; the exception (a decoder's words,
                #: a payload fragment) goes to the log with its traceback.
                logger.warning("could not resume job %s (%s)", job_id, kind, exc_info=True)
                _fail_unrun(job_id, "Could not be resumed after the app restarted.", db)
                continue
            enqueue(kind, func, args, kwargs, name, dedupe, job_id)
            counts["resumed"] += 1
        if later is not None:
            _schedule(later + 1.0, db, enqueue)
        if counts["resumed"] or counts["gave_up"]:
            logger.info(
                "background jobs from the last run: %d resumed, %d given up",
                counts["resumed"],
                counts["gave_up"],
            )
    except Exception:  # noqa: BLE001  # a launch never fails on its job list
        logger.warning("could not resume background jobs", exc_info=True)
    return counts


_timer: threading.Timer | None = None
_timer_lock = threading.Lock()


def _schedule(delay: float, db, enqueue) -> None:  # noqa: ANN001
    """Look again when a standing lease would have run out. One timer at a
    time; `stop` cancels it, so a closed app never resumes into its own
    shut-down pool (or, in the test process, into the next test's)."""
    global _timer
    with _timer_lock:
        if _timer is not None:
            _timer.cancel()
        _timer = threading.Timer(delay, resume, kwargs={"db": db, "enqueue": enqueue})
        _timer.daemon = True
        _timer.start()


def stop() -> None:
    """Called with the pool's shutdown: cancel a pending look-again."""
    global _timer
    with _timer_lock:
        if _timer is not None:
            _timer.cancel()
            _timer = None


def _fail_unrun(job_id: int, reason: str, db) -> None:  # noqa: ANN001
    try:
        from sqlalchemy import update

        from tessellate.core.database import DurableJob

        with db.session() as session:
            session.execute(
                update(DurableJob)
                .where(DurableJob.id == job_id)
                .values(state="failed", finished_at=_now(), error=_clip(reason))
            )
            session.commit()
        _changed()
    except Exception:  # noqa: BLE001
        logger.debug("could not mark job %s failed", job_id, exc_info=True)


def prune(db=None) -> int:  # noqa: ANN001
    """Drop finished rows older than a week, and past the newest
    `KEEP_FINISHED_ROWS`. Returns how many went."""
    db = _database(db)
    if db is None:
        return 0
    try:
        from sqlalchemy import delete, select

        from tessellate.core.database import DurableJob

        cutoff = _now() - timedelta(days=KEEP_FINISHED_DAYS)
        finished = DurableJob.state.notin_(ACTIVE_STATES)
        with db.session() as session:
            gone = session.execute(delete(DurableJob).where(finished, DurableJob.finished_at < cutoff)).rowcount or 0
            extra = list(
                session.scalars(
                    select(DurableJob.id).where(finished).order_by(DurableJob.id.desc()).offset(KEEP_FINISHED_ROWS)
                )
            )
            if extra:
                gone += session.execute(delete(DurableJob).where(DurableJob.id.in_(extra))).rowcount or 0
            session.commit()
        return int(gone)
    except Exception:  # noqa: BLE001
        logger.debug("could not prune finished jobs", exc_info=True)
        return 0


# -- reading ------------------------------------------------------------------


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def list_jobs(db=None, limit: int = 50, labels: dict[str, str] | None = None) -> list[dict]:  # noqa: ANN001
    """The work in hand first (oldest first, the order it will run), then
    the most recent endings, at most `limit` rows in all. `labels` is the
    pool's wording per kind (`jobs.LABELS`)."""
    db = _database(db)
    if db is None:
        return []
    labels = labels or {}
    try:
        from sqlalchemy import select

        from tessellate.core.database import DurableJob

        with db.session() as session:
            active = list(
                session.scalars(
                    select(DurableJob).where(DurableJob.state.in_(ACTIVE_STATES)).order_by(DurableJob.id).limit(limit)
                )
            )
            room = max(0, limit - len(active))
            ended = (
                list(
                    session.scalars(
                        select(DurableJob)
                        .where(DurableJob.state.notin_(ACTIVE_STATES))
                        .order_by(DurableJob.id.desc())
                        .limit(room)
                    )
                )
                if room
                else []
            )
            return [
                {
                    "id": row.id,
                    "kind": row.kind,
                    "label": labels.get(row.kind, "Background job"),
                    "name": row.name or "",
                    "state": row.state,
                    "attempts": row.attempts or 0,
                    "created_at": _iso(row.created_at),
                    "started_at": _iso(row.started_at),
                    "finished_at": _iso(row.finished_at),
                    "result": row.result or "",
                    "error": row.error or "",
                }
                for row in active + ended
            ]
    except Exception:  # noqa: BLE001
        logger.debug("could not list jobs", exc_info=True)
        return []
