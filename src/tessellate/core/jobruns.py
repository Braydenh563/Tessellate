"""When each kind of job last ran, and how it went (INBOX 438).

The owner: "there should be timestamps and success status for when various
things were last ran like the search reindexing etc." Before this, three
partial answers existed and none of them was that:

- `core/taskhistory.py` remembers what *stopped* since the app started, in
  memory, as a ring. It forgets on restart, which is the right lifetime for a
  "what happened while I was here" list and the wrong one for "when did my
  notes last get backed up". Nobody checks that on the day it happened.
- `backup.list_backups` has file times, which says a backup exists but not
  that last night's failed.
- `reindex_status` is the live job, gone on restart, and `None` before the
  first run.

So this keeps **one row per job kind**, in the database (`JobRun`), written
from one place. Every job reports through `job_run`:

    with job_run("reindex") as run:
        ...
        run.result = "indexed 412 notes"

An exception leaving the block marks the run failed with the exception's
message and then propagates it: bookkeeping never swallows a job's error.
`run.cancel("stopped after 3 of 9")` records a stop that is not a failure.

**Bookkeeping must never break the job.** Every write here is wrapped: a
locked database or a missing table costs the line "Last run" and nothing
else. That is also why it reads `deps.peek_db()` and never `get_db()`: a
helper run without an app (a test, a script) records nothing rather than
creating a data directory to hold its note.

**Overlapping runs of one kind** (two imports at once): an older run
finishing while a newer one is still going leaves the row saying "running",
because that is true; once nothing is running, the last to finish is the last
run.
"""

from __future__ import annotations

import itertools
import logging
import threading
import time
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("tessellate.jobruns")

#: The kinds this app records, with the words the UI uses. The order is the
#: order of the Background jobs overview. A kind outside this table is still
#: recorded and listed (labelled by its own name): the table is for wording,
#: never a gate.
KINDS: dict[str, str] = {
    "reindex": "Search index rebuild",
    "embeddings-backfill": "Embeddings backfill",
    "backup": "Backup",
    "duplicate-scan": "Duplicate scan",
    "import": "Import",
    #: The whole notebook as a markdown folder (WORLD_CLASS 25b).
    "export": "Notebook export",
    "night-shift": "Night shift",
    "model-bench": "Model bench",
    "autonomous": "Autonomous optimisation",
    "resurface": "Resurfacing",
    "link-reasons": "Link reasons",
    #: INBOX 691: a Tidy review applied, or the link reason pass.
    "tidy": "Tidy",
    "filing": "Filing re-evaluation",
    "ocr": "Reading text from images",
    "caption": "Image captions",
    "model-download": "Model download",
    "embedding-model": "Embedding model download",
    #: The search model fetched or fixed by the app itself on a load that
    #: found it missing or broken (INBOX 1289).
    "embedding-fix": "Search model fix",
    "embed-switch": "Embedding model switch",
    "maintenance": "Housekeeping",
    #: Notes saved before written-out dates were read (`entry/redate.py`).
    "redate": "Reading dates in notes",
    "extra": "Package install",
    "searxng": "SearXNG setup",
}

#: Longest result or error kept: the column is 400 and a line is a line.
_MAX_TEXT = 300


def _clip(text: object) -> str:
    one_line = " ".join(str(text or "").split())
    return one_line if len(one_line) <= _MAX_TEXT else one_line[: _MAX_TEXT - 1] + "…"


def _failure_reason(exc: BaseException) -> str:
    """The short worded reason an exception leaves on the last-run line.

    An `OSError`'s `str()` is "[Errno 28] No space left on device: '/home/x/
    backups/memorymap-...db'": the person's own path and an errno, on a line
    meant for a sentence. Its `strerror` is the sentence ("No space left on
    device"), so that is what is kept; the full text stays in the log.
    """
    if isinstance(exc, OSError) and exc.strerror:
        return str(exc.strerror)
    return str(exc) or type(exc).__name__


#: Where the app's own database comes from when a caller does not hold one.
#: `core/deps.py` sets it at import. Not an import of `deps` from here:
#: `deps` reaches the AI modules, and the AI modules record their jobs, so the
#: name would close a cycle (`tests/test_no_import_cycles.py`). Until it is
#: set, and in a process with no app, nothing is recorded.
_peek_db = lambda: None  # noqa: E731


def set_database_source(peek) -> None:  # noqa: ANN001
    """Called once by `core/deps.py`: a zero-argument callable returning the
    app's `DatabaseManager`, or None when it has not been created."""
    global _peek_db
    _peek_db = peek


def _database(db):  # noqa: ANN001, ANN202
    return db if db is not None else _peek_db()


def peek_database(db=None):  # noqa: ANN001, ANN201
    """`db` if given, else the app's database if it has one, else None.
    Public for `core/jobstore.py`, which records through the same source."""
    return _database(db)


#: Lines a running job keeps for its row's "What it's doing" fold.
LOG_LINES = 50

#: Finished runs the ledger keeps, with their lines (INBOX 805, the owner:
#: "all things that use the ai or composer and all background processes need
#: to be logged ... with their individual logs and process lines"). Process
#: memory, like `taskhistory`: "what ran while the app was open". A ring, so
#: a busy day of chat answers cannot grow it.
FINISHED_KEEP = 60

#: Two runs of one kind and title ending this close together are one row
#: with a count ("Updating a note's search vector, 12 times"), so a bulk
#: upload's 200 small jobs do not push the morning's backup out of the ring.
MERGE_WITHIN_S = 120.0

#: Who started a run, in the words the panel shows.
ORIGINS: dict[str, str] = {
    "you": "you started it",
    "schedule": "on its schedule",
    "start-up": "at start-up",
    "app": "the app",
}

_finished: deque[dict] = deque(maxlen=FINISHED_KEEP)
_ids = itertools.count(1)
#: Bumped on every start, line and finish, for `/jobs/stream` (the panel's
#: lines are live without a second poll).
_version = 0
_origin = threading.local()


def _bump() -> None:
    global _version
    _version += 1


def version() -> int:
    return _version


@contextmanager
def started_by(origin: str):  # noqa: ANN201
    """Runs opened on this thread inside the block say who started them,
    without an `origin=` at every call (a pool job runs a pass that opens
    its own run three calls down)."""
    before = getattr(_origin, "value", "")
    _origin.value = origin
    try:
        yield
    finally:
        _origin.value = before


def finished(limit: int = FINISHED_KEEP) -> list[dict]:
    """Finished runs, newest first, each with its lines."""
    with _live_lock:
        return [dict(item) for item in list(_finished)[-limit:][::-1]]


def clear_finished() -> None:
    """The history's Clear, and between tests."""
    with _live_lock:
        _finished.clear()
    _bump()

#: Runs that have started and not finished, for `live()` (INBOX 1006: the
#: owner asked for "actual progress feedback and a log" on the background
#: passes, which ran without ever appearing in `/tasks`). Process memory only:
#: a restart ends the runs, and `mark_interrupted` settles their rows.
_live: list["Run"] = []
_live_lock = threading.Lock()

#: The scheduled passes someone pressed Stop on (`core/passes.py` adds and
#: clears; a pass's own loop reads it between steps). Here, below both, so
#: `ai/embeddings.py` can read it without importing the module that imports it.
stop_asked: set[str] = set()


def clear_live() -> None:
    """Tests only: forget the runs in flight. A test that clears the activity
    registry (`activity.clear`) would otherwise leave each listed job's run
    here, and `/tasks` in the next test on the worker would list it."""
    with _live_lock:
        _live.clear()
    _bump()


def live() -> list[dict]:
    """Every run in flight as a `/tasks`-shaped dict, oldest first."""
    with _live_lock:
        runs = list(_live)
    return [run.snapshot() for run in runs]


def current(kind: str) -> "Run":
    """The newest run of `kind` in flight, so deep code (the night pass's loop,
    the embeddings batch) can report without a `run` threaded through every
    signature. With none running it answers a throwaway handle that records
    nothing, so a caller never checks."""
    with _live_lock:
        for run in reversed(_live):
            if run.kind == kind:
                return run
    return Run(kind, None)


class Run:
    """The handle `job_run` yields. Set `result`; call `cancel` for a stop.

    While it runs, `step`, `plan` and `say` feed the Background tasks row:
    a bar, named steps and a short plain-sentence log. Say what is being
    done in words; never put exception text in a line (it reaches the screen,
    and a traceback belongs in the server log).
    """

    def __init__(
        self,
        kind: str,
        db,  # noqa: ANN001  # DatabaseManager or None
        *,
        title: str = "",
        origin: str = "",
        ledger: bool = True,
    ) -> None:
        self.kind = kind
        self.id = f"run-{next(_ids)}"
        #: The plain words for this one run ("Answering 'what is a mouse'"),
        #: where the kind's label says only what sort of job it is.
        self.title = _clip(title) or KINDS.get(kind, kind)
        self.origin = origin or getattr(_origin, "value", "")
        #: False for a run seen only at its end (`note_finished`): its
        #: ending is already in `taskhistory`, and the ledger would list it twice.
        self._ledger = ledger
        self._ledgered = False
        #: True when another row on the running list already shows this
        #: run (a pool job's): `/tasks` then adds its lines, not a second row.
        self.listed = False
        self.result = ""
        self.started_at = datetime.now(timezone.utc)
        self._t0 = time.monotonic()
        self._db = db
        self._status = "ok"
        self._error = ""
        self._skipped = False
        self._finished = False
        #: What the row said before this run began, for `skip`.
        self._before: dict | None = None
        self._started_epoch = time.time()
        self._done = 0
        self._total = 0
        self._what = ""
        self._plan: list[str] = []
        #: (when, words): the time is what makes a line a process line.
        self._log: deque[tuple[float, str]] = deque(maxlen=LOG_LINES)

    # -- live progress ---------------------------------------------------------

    def plan(self, labels: list[str]) -> None:
        """Name the steps up front; `step(done)` then marks them off."""
        self._plan = [str(label) for label in labels]
        self._total = len(self._plan)

    def step(self, done: int, total: int | None = None, what: str = "") -> None:
        """`done` of `total` finished (total omitted: the plan's length, or
        unchanged). `what` names the thing in hand, e.g. "Embedding notes"."""
        self._done = max(0, int(done))
        if total is not None:
            self._total = max(0, int(total))
        if what:
            self._what = what

    def say(self, line: object) -> None:
        """Add one plain sentence to the log; only the last `LOG_LINES` stay."""
        text = _clip(line)
        if text:
            self._log.append((time.time(), text))
            logger.info("[%s] %s", self.id, text)
            _bump()

    def lines(self) -> list[dict]:
        return [{"at": at, "text": text} for at, text in list(self._log)]

    def snapshot(self) -> dict:
        total = self._total
        done = min(self._done, total) if total else self._done
        progress = max(0.0, min(1.0, done / total)) if total else None
        if total:
            counts = f"{done} of {total}"
            detail = f"{self._what}: {counts}" if self._what else counts
        else:
            detail = self._what
        steps = [
            {
                "label": label,
                "outcome": "completed" if i < done else "running" if i == done else "queued",
                "word": "working" if i == done else "",
            }
            for i, label in enumerate(self._plan)
        ]
        return {
            "id": self.id,
            "kind": self.kind,
            "label": KINDS.get(self.kind, self.kind),
            "title": self.title,
            "origin": self.origin,
            "started": self._started_epoch,
            "progress": progress,
            "detail": detail,
            "log": [text for _, text in list(self._log)],
            "lines": self.lines(),
            "listed": self.listed,
            "steps": steps,
        }

    def skip(self) -> None:
        """This was not a run after all (the switch is off, nothing was due):
        put the row back as it was. The start was written first so a running
        job shows as running; a no-op must not overwrite the last real run."""
        self._skipped = True

    def cancel(self, detail: str = "") -> None:
        """Record a stop the person asked for. Not a failure, never red."""
        self._status = "cancelled"
        self.result = detail or self.result

    def fail(self, reason: object) -> None:
        """Record a failure the job handled itself (it returned an error
        value instead of raising), so the reason still reaches the screen."""
        self._status = "failed"
        self._error = _clip(reason) or "It stopped without saying why."

    # -- the two writes -------------------------------------------------------

    def start(self) -> None:
        with _live_lock:
            if self not in _live:
                _live.append(self)
        _bump()
        #: In the app log under its run id, so Settings, Logs can show this
        #: run's lines (the Logs button filters on "[run-12]").
        logger.info("[%s] %s started", self.id, str(self.title).replace("\r", " ").replace("\n", " "))
        if self._db is None:
            return
        try:
            from tessellate.core.database import JobRun

            with self._db.session() as session:
                row = session.get(JobRun, self.kind)
                if row is None:
                    row = JobRun(kind=self.kind)
                    session.add(row)
                else:
                    self._before = {
                        "started_at": row.started_at, "finished_at": row.finished_at,
                        "status": row.status, "result": row.result, "error": row.error,
                        "duration_ms": row.duration_ms,
                    }
                row.started_at = self.started_at
                row.finished_at = None
                row.status = "running"
                row.result = ""
                row.error = ""
                row.duration_ms = None
                session.commit()
        except Exception:  # noqa: BLE001  # bookkeeping must never break the job
            logger.debug("could not record the start of %r", self.kind, exc_info=True)

    def finish(self) -> None:
        """Write the ending. Idempotent: the second call is a no-op, so a
        caller that finishes by hand can still sit inside a `finally`."""
        with _live_lock:
            if self in _live:
                _live.remove(self)
        self._to_ledger()
        if not self._skipped and not self._finished:
            logger.info("[%s] %s %s", self.id, self.title, "failed" if self._status == "failed" else "finished")
        if self._db is None or self._finished:
            return
        self._finished = True
        try:
            from tessellate.core.database import JobRun

            with self._db.session() as session:
                row = session.get(JobRun, self.kind)
                if self._skipped:
                    self._undo_skipped(session, row)
                    return
                if row is None:
                    row = JobRun(kind=self.kind, started_at=self.started_at)
                    session.add(row)
                elif (
                    row.status == "running"
                    and row.started_at is not None
                    and row.started_at > self.started_at
                ):
                    return  # a newer run is still going and owns the row
                self._write_ending(row)
                session.commit()
        except Exception:  # noqa: BLE001  # see start
            logger.debug("could not record the end of %r", self.kind, exc_info=True)


    def _undo_skipped(self, session, row) -> None:  # noqa: ANN001
        """A skipped run was never a run: put the row back as it was."""
        if row is not None and row.started_at == self.started_at:
            if self._before is None:
                session.delete(row)
            else:
                for name, value in self._before.items():
                    setattr(row, name, value)
            session.commit()

    def _write_ending(self, row) -> None:  # noqa: ANN001
        row.started_at = self.started_at
        row.finished_at = datetime.now(timezone.utc)
        row.status = self._status
        row.result = _clip(self.result) if self._status != "failed" else ""
        row.error = self._error
        row.duration_ms = round((time.monotonic() - self._t0) * 1000, 1)

    def _to_ledger(self) -> None:
        """Keep the ending, with its lines, in the finished ring. Once."""
        _bump()
        if not self._ledger or self._skipped or self._ledgered:
            return
        self._ledgered = True
        outcome = {"failed": "failed", "cancelled": "cancelled"}.get(self._status, "completed")
        ended = time.time()
        entry = {
            "run_id": self.id,
            "kind": self.kind,
            "name": "",
            "label": self.title,
            "title": self.title,
            "origin": self.origin,
            "outcome": outcome,
            "detail": self._error if outcome == "failed" else _clip(self.result),
            "started": self._started_epoch,
            "ended": ended,
            "at": datetime.fromtimestamp(ended, timezone.utc).isoformat(),
            "duration_ms": round((time.monotonic() - self._t0) * 1000, 1),
            "lines": self.lines(),
            "count": 1,
        }
        with _live_lock:
            last = _finished[-1] if _finished else None
            if (
                last is not None
                and last["kind"] == entry["kind"]
                and last["title"] == entry["title"]
                and last["outcome"] == entry["outcome"] == "completed"
                and entry["ended"] - last["ended"] <= MERGE_WITHIN_S
            ):
                entry["count"] = last["count"] + 1
                _finished.pop()
            _finished.append(entry)


def merged_history(entries: list[dict], limit: int = FINISHED_KEEP) -> list[dict]:
    """`taskhistory`'s endings and the ledger's, newest first, one row per run.

    A job that records its own ending in `taskhistory` (a re-index, the
    autonomous pass) and also opens a run would be listed twice; the ledger's
    lines and origin go onto the history row instead.
    """
    ledger = finished()
    out: list[dict] = []
    for item in entries:
        row = dict(item)
        try:
            at = datetime.fromisoformat(str(row.get("at"))).timestamp()
        except ValueError:
            at = 0.0
        twin = next(
            (run for run in ledger if run["kind"] == row.get("kind") and abs(run["ended"] - at) <= 5.0),
            None,
        )
        if twin is not None:
            ledger.remove(twin)
            row.update({key: twin[key] for key in ("run_id", "origin", "lines", "started", "count")})
        row.setdefault("ended", at)
        out.append(row)
    out.extend(ledger)
    out.sort(key=lambda row: row.get("ended") or 0.0, reverse=True)
    return out[:limit]


def begin(kind: str, db=None, *, title: str = "", origin: str = "") -> Run:  # noqa: ANN001
    """Start a run you will `finish()` yourself, for a job whose body is too
    long to indent into a `with` (a route that already has three try blocks).
    The caller owns calling `finish()` on every way out."""
    run = Run(kind, _database(db), title=title, origin=origin)
    run.start()
    return run


@contextmanager
def job_run(kind: str, db=None, *, title: str = "", origin: str = "", persist: bool = True):  # noqa: ANN001, ANN201
    """Record one run of `kind`: started now, finished when the block leaves.

    `db` is only for a caller that already holds the `DatabaseManager`
    (a worker thread); everyone else gets the app's own, if it has one.
    `persist=False` keeps the run in the live list and the ledger only: a
    chat answer is a run worth seeing, not a "last run" row per kind.
    """
    run = Run(kind, _database(db) if persist else None, title=title, origin=origin)
    run.start()
    try:
        yield run
    except BaseException as exc:
        # GeneratorExit and KeyboardInterrupt are not "failed", but nothing
        # may leave the row saying "running" forever either.
        run.fail(_failure_reason(exc))
        run.finish()
        raise
    run.finish()


def note_finished(
    kind: str,
    outcome: str,
    detail: str = "",
    duration_ms: float | None = None,
    db=None,  # noqa: ANN001
) -> None:
    """Record a run that was only seen at its end.

    For the jobs that already report their ending to `taskhistory` and have
    no single place where they begin (a model download, a pip install):
    `taskhistory.record` calls this for those kinds, so the history ring and
    the last-run record cannot disagree about whether something worked.
    `outcome` is taskhistory's vocabulary: completed, failed, cancelled.
    """
    run = Run(kind, _database(db), ledger=False)
    if isinstance(duration_ms, (int, float)) and duration_ms >= 0:
        run.started_at = datetime.now(timezone.utc) - timedelta(milliseconds=duration_ms)
        run._t0 = time.monotonic() - duration_ms / 1000
    if outcome == "failed":
        run.fail(detail or "Failed.")
    elif outcome == "cancelled":
        run.cancel(detail)
    else:
        run.result = detail
    run.finish()


def mark_interrupted(db=None) -> int:  # noqa: ANN001
    """At startup: a row still "running" belongs to a process that is gone.

    Without this a job killed with the app would say "Running…" for ever,
    the one state the screen could never correct on its own.
    """
    db = _database(db)
    if db is None:
        return 0
    try:
        from sqlalchemy import select

        from tessellate.core.database import JobRun

        with db.session() as session:
            rows = list(session.scalars(select(JobRun).where(JobRun.status == "running")))
            for row in rows:
                row.status = "failed"
                row.error = "The app closed before this finished."
                # No `finished_at`: nobody knows when it ended, and stamping the
                # start-up time made "Last run 26 min ago" of a run from days
                # before (B66). The line then reads the run's own start.
            session.commit()
            return len(rows)
    except Exception:  # noqa: BLE001
        logger.debug("could not mark interrupted jobs", exc_info=True)
        return 0


def last_runs(db=None) -> list[dict]:  # noqa: ANN001
    """Every recorded kind, in the overview's order, plus the kinds this app
    can run but has not yet (`ran: false`), so the screen can say "Not run
    yet" rather than leave a gap that looks like a missing feature."""
    db = _database(db)
    seen: dict[str, dict] = {}
    if db is not None:
        try:
            from sqlalchemy import select

            from tessellate.core.database import JobRun

            with db.session() as session:
                for row in session.scalars(select(JobRun)):
                    seen[row.kind] = {
                        "kind": row.kind,
                        "label": KINDS.get(row.kind, row.kind),
                        "ran": True,
                        "status": row.status,
                        "started_at": row.started_at.isoformat() if row.started_at else None,
                        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                        "result": row.result or "",
                        "error": row.error or "",
                        "duration_ms": row.duration_ms,
                    }
        except Exception:  # noqa: BLE001
            logger.debug("could not read the job records", exc_info=True)
    out: list[dict] = []
    for kind, label in KINDS.items():
        out.append(
            seen.pop(kind)
            if kind in seen
            else {
                "kind": kind, "label": label, "ran": False, "status": "never",
                "started_at": None, "finished_at": None, "result": "", "error": "",
                "duration_ms": None,
            }
        )
    out.extend(seen.values())
    return out


def describe_night_pass(run: "Run", outcome: dict) -> None:
    """Put a night-shift pass's counts on its run record. `facts.run` answers
    `{"paused": true}` when the switch is off, which is not a run."""
    if outcome.get("paused"):
        run.skip()
        return
    scanned = int(outcome.get("scanned") or 0)
    derived = int(outcome.get("derived") or 0)
    run.result = (
        f"read {scanned} note{'' if scanned == 1 else 's'}, "
        f"found {derived} fact{'' if derived == 1 else 's'}"
    )
    if outcome.get("stopped_reason") == "budget":
        run.result += " (stopped at its budget)"
