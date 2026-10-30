"""One bounded pool for the background work an upload starts.

**The finding this replaces** (WORLD_CLASS_PLAN A3, and section 4's B2 in
smaller form): every upload spawned up to three `threading.Thread`s of its
own, plus a document read, and nothing anywhere counted them. Fourteen
`Thread(` sites, no semaphore, no queue, no pool. A folder of 200 pictures
was therefore 600 threads, all of them arriving at one Tesseract binary and
one local model at the same moment, and the failure it produces is not a
crash: it is a machine that stops answering while every job makes a little
progress, plus 200 SQLAlchemy sessions opened at once against one SQLite
file. Unbounded concurrency against a single-threaded resource is slower
than a queue, not faster.

**Two lanes, not one queue and not a lane per kind.** The two resources
behave differently enough that one width is wrong for both:

- `cpu`: Tesseract and the document extractors. Real parallelism helps, up
  to the core count, and past four the returns stop mattering on the kind of
  machine this app runs on while the memory does not.
- `model`: every call into the local model (captions, vision OCR, the
  entry filer). **One worker, deliberately.** A local model serves one
  request at a time; two concurrent calls interleave into one slower pair,
  and on a small machine the second load can fail outright for memory.

A kind nobody mapped lands on the default lane rather than vanishing, which
is the failure mode a `KeyError` here would have: a caption that is silently
never taken.

**Durable since B2** (`core/jobstore.py`): a job whose kind has a named
handler there and whose arguments are plain data is also written to the
`jobs` table when it is queued, leased when a worker takes it, and closed
when it ends. What follows about dropping still holds for this process's
memory; the row is what the next launch reads to run it again.

**Why jobs are dropped at shutdown rather than drained.** `shutdown` has a
deadline because a shutdown that waits is the hang it exists to prevent
(`core/bgtasks.py`'s docstring makes the same argument for cancellation).
Nothing here is lost by dropping it: every job re-derives its result from a
row that is already committed, so the next launch can redo it, and a caption
that never arrives is a missing caption rather than a corrupt notebook. The
job in flight is not interrupted, for the same reason `bgtasks` never kills a
thread: Python cannot do it safely and the work writes to a notebook the
user cares about. Workers are daemons, so the process still exits on time;
`shutdown` returns False to say plainly that one was still running.

**The activity panel needs no new frontend.** `pending()` returns rows in
`/tasks`'s shape (`routes_tasks.collect`), so queued and running jobs appear
in the panel that already lists the readings `core/filejobs.py` announces.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
import time
from collections.abc import Callable

from tessellate.core import jobruns, jobstore, model_gate, origin

logger = logging.getLogger("tessellate.jobs")


def _cpu_width() -> int:
    """Workers for the Tesseract and extractor lane.

    Capped at four: past that the contention on one SQLite file and the
    memory each Tesseract process holds cost more than the extra parallelism
    returns, and this app runs on laptops.
    """
    return max(1, min(4, os.cpu_count() or 1))


#: Lane -> how many workers it gets. `model` is 1 on purpose; see the module
#: docstring. Read by `tests/test_jobs_pool.py`, which fails if it grows.
#:
#: `install` is one wide for the reason `model` is: two pips against one
#: environment is a way to corrupt it (`core/extras.py`). Its own lane rather
#: than the `cpu` one, because an install can take minutes and a laptop with
#: one core would otherwise read no picture until pip had finished.
#:
#: `notify` holds the desktop reminder notifier's loop (`core/reminder_notifier.py`),
#: which runs for the life of the process: a lane of its own, so it never
#: takes a worker a reading or a filing is waiting for.
#:
#: `download` holds model pulls (Brief 9): network-bound, minutes long, two
#: at once so a second model is not stuck behind a large first one, and no
#: more, because a third only splits the same connection three ways.
#:
#: `agent` holds the autonomous pass (Brief 9): it can run for many minutes
#: of model calls, and on `batch` a re-index someone asked for would wait
#: behind a pass nobody is watching. One wide: two passes would edit the
#: same notes.
LANE_WIDTHS: dict[str, int] = {
    "cpu": _cpu_width(), "model": 1, "batch": 1, "install": 1, "notify": 1, "download": 2, "agent": 1,
}

#: The lane each job kind belongs on. A kind missing from here lands on
#: `DEFAULT_LANE` with a debug line rather than raising.
KIND_LANES: dict[str, str] = {
    "ocr": "cpu",
    "document": "cpu",
    "caption": "model",
    "vision": "model",
    "vision-pdf": "model",
    "file-entry": "model",
    #: An edited note's new vector (routes_entries `_queue_embedding`).
    "embed-entry": "model",
    "maintenance": "cpu",
    "bench": "model",
    #: Loading the search model on a pause in typing (`search_manager.warm`).
    #: Not `model`: that lane is one wide, and a first launch's load (a
    #: download on a fresh install) held the first note's filing behind it
    #: for longer than the 20 s the E2E first-run spec waits (2026-10-06,
    #: reproduced with a 40 s stand-in load). Filing with nothing filed
    #: yet needs no vectors, so nothing on `model` should wait for this.
    "warm": "batch",
    # F7, the threads onto the pool (2026-10-05). A whole-notebook pass gets a
    # lane of its own: on `model` it would hold every caption and every new
    # note's filing until it finished, which is minutes on a large notebook.
    "reindex": "batch",
    # Asking the model server what a model can do: a short HTTP call, no
    # model loaded, so it waits behind nothing on the I/O-shaped lane.
    "model-info": "cpu",
    #: Installing, removing or reinstalling optional extras, one package or
    #: a bundle (`core/extras.py`, INBOX 595).
    "extras": "install",
    #: Changing the embedding model (`core/embedswitch.py`, INBOX 700): the
    #: re-index's lane, for the re-index's reason.
    "embed-switch": "batch",
    #: A scheduled pass started by hand (`core/passes.py`, INBOX 713).
    "pass": "batch",
    #: Tidy's whole-notebook link reason pass (INBOX 691): no model, but a
    #: notebook-wide walk, so it waits behind nothing a person is waiting on.
    "tidy-link-reasons": "batch",
    #: Reading the dates in notes saved before `timewords` read written-out
    #: ones (`entry/redate.py`): a notebook-wide walk, once.
    "redate": "batch",
    #: The reminder notifier's loop (`core/reminder_notifier.py`).
    "reminder-notifier": "notify",
    #: Brief 9: a model download, and an autonomous pass (see the lanes).
    "pull": "download",
    "autonomous": "agent",
    #: A chosen folder of notes: a notebook-wide write, nothing a person
    #: waits behind (`routes_settings._run_directory_import`).
    "import": "batch",
}

DEFAULT_LANE = "cpu"

#: How many waiting jobs of one kind `pending()` lists by name before it
#: counts the rest in one row (19.5: a dropped folder of 2,000 pictures made
#: every activity-panel poll 2,000 rows). The queue itself is not bounded:
#: measured, an enqueue costs 53 microseconds and a queued job 484
#: bytes, and refusing work would lose a reading the person asked for.
PENDING_ROWS_PER_KIND = 10

#: Kinds that are the app's own housekeeping, not something the person asked
#: for: the privacy ledger's flush (`core/egress.py`) queues one within a
#: second of any connection that leaves this computer, and a row in the
#: activity panel for it would be noise that says nothing they can act on.
#:
#: `extras` is quiet for another reason: `routes_tasks.collect` already draws
#: an install as its own row, with pip's step and log, and a second generic
#: "Background job" row for the same install would say the same thing twice.
#:
#: `pull` and `autonomous` (Brief 9) have their own rows too
#: (`model_manager.pull_statuses`, `autonomous.is_running`).
QUIET_KINDS = frozenset({
    "ledger", "maintenance", "warm", "model-info", "reindex", "extras", "embed-switch", "reminder-notifier",
    "pull", "autonomous",
})

#: Pool kinds whose work opens its own `jobruns` run or reports its own
#: ending (a pass, the bench, a re-index), or never ends (the reminder
#: loop): the pool does not open a second ledger run around them.
OWN_RUN_KINDS = frozenset({
    "pass", "maintenance", "bench", "tidy-link-reasons", "redate", "reindex", "embed-switch", "extras",
    "reminder-notifier", "ledger", "pull", "autonomous", "import",
})

#: Where a pool kind's ending is recorded in `taskhistory` under another
#: name, the ledger uses that name, so the history lists the run once.
LEDGER_KINDS = {"vision": "vision_ocr", "vision-pdf": "vision_ocr"}


def _ledger_run(job: "_Job"):  # noqa: ANN202
    """The process ledger's run for one pool job (INBOX 805), or None."""
    if job.kind in OWN_RUN_KINDS:
        return None
    label = LABELS.get(job.kind, job.kind.replace("-", " ").capitalize())
    run = jobruns.Run(LEDGER_KINDS.get(job.kind, job.kind), None, title=f"{label}: {job.name}" if job.name else label)
    #: Its row on the running list is the pool's own; the run adds lines.
    run.listed = True
    run.start()
    return run


def _start_heartbeat(target):  # noqa: ANN001, ANN202
    """The durable store's lease heartbeat (`jobstore._beat`), started here so
    job threads have one home. It ends itself once no lease is held."""
    beater = threading.Thread(target=target, name="mm-job-heartbeat", daemon=True)
    beater.start()
    return beater


jobstore.start_beater = _start_heartbeat

#: What the activity panel calls each kind. Sentence case, no exclamation:
#: standing order 6.
LABELS: dict[str, str] = {
    "ocr": "Reading text from an image",
    "document": "Reading an attached document",
    "caption": "Describing an image",
    "vision": "Reading an image with the vision model",
    "vision-pdf": "Reading a scan with the vision model",
    "file-entry": "Filing a note",
    "warm-filing": "Warming up the filing model",
    #: "Warm: warm the spelling lists" said the kind twice (audit 1030 Y7).
    "warm": "Warming up",
    #: INBOX 696: a "Background job" row says nothing a person can read.
    "embed-entry": "Updating a note's search vector",
    "bench": "Timing a model",
    "pass": "Running a scheduled pass",
    "tidy-link-reasons": "Naming link reasons",
    "redate": "Reading dates in notes",
    "pull": "Downloading a model",
    "autonomous": "Autonomous pass",
    "import": "Importing a folder of notes",
}


class _Job:
    """One queued piece of work. A plain object rather than a dataclass so
    `__slots__` keeps 200 of them cheap during a bulk upload."""

    __slots__ = (
        "seq", "kind", "func", "args", "kwargs", "name", "queued_at", "started_at", "dedupe_key", "durable_id", "durable_db",
        "another_device",
    )

    def __init__(
        self,
        seq: int,
        kind: str,
        func: Callable[..., object],
        args: tuple,
        kwargs: dict,
        name: str,
    ) -> None:
        self.seq = seq
        self.kind = kind
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.name = name
        self.dedupe_key: object = None
        #: The `jobs` row behind this job (`core/jobstore.py`), or None for
        #: a job only this process knows about.
        self.durable_id: int | None = None
        self.durable_db: object = None
        self.queued_at = time.time()
        #: When a worker took it, for the panel's elapsed time (INBOX 696):
        #: a running row counts from here, a waiting one from `queued_at`.
        self.started_at = 0.0
        #: Queued while serving another device (core/origin.py): the job runs
        #: as that device, so it cannot start an install on this computer.
        self.another_device = origin.from_another_device()


class Pool:
    """A fixed set of daemon workers per lane, fed by one queue per lane.

    Instantiable so the tests can pin a width rather than measure against
    whatever the sandbox's core count happens to be; the app uses the module
    singleton below.
    """

    def __init__(
        self,
        widths: dict[str, int] | None = None,
        kind_lanes: dict[str, str] | None = None,
    ) -> None:
        self._widths = {lane: max(1, int(width)) for lane, width in (widths or LANE_WIDTHS).items()}
        if not self._widths:  # pragma: no cover - defensive
            self._widths = {DEFAULT_LANE: 1}
        self._kind_lanes = dict(kind_lanes if kind_lanes is not None else KIND_LANES)
        self._default_lane = DEFAULT_LANE if DEFAULT_LANE in self._widths else next(iter(self._widths))
        self._queues: dict[str, queue.Queue] = {lane: queue.Queue() for lane in self._widths}
        self._lock = threading.Lock()
        self._workers: list[threading.Thread] = []
        self._queued: dict[int, _Job] = {}
        self._running: dict[int, _Job] = {}
        self._seq = 0
        self._started = False
        self._stopping = threading.Event()

    # -- starting -----------------------------------------------------------

    def start(self) -> None:
        """Bring the workers up. Idempotent, and called by `enqueue`, so a
        test or a script that never enqueues never starts a thread at all."""
        with self._lock:
            if self._started or self._stopping.is_set():
                return
            self._started = True
            for lane, width in self._widths.items():
                for index in range(width):
                    worker = threading.Thread(
                        target=self._work,
                        args=(lane,),
                        name=f"mm-job-{lane}-{index}",
                        daemon=True,
                    )
                    self._workers.append(worker)
                    worker.start()

    # -- enqueueing ---------------------------------------------------------

    def lane_for(self, kind: str) -> str:
        lane = self._kind_lanes.get(kind)
        if lane is None or lane not in self._queues:
            logger.debug("job kind %r has no lane; using %s", kind, self._default_lane)
            return self._default_lane
        return lane

    def enqueue(
        self,
        kind: str,
        func: Callable[..., object],
        *args: object,
        name: str = "",
        dedupe_key: object = None,
        **kwargs: object,
    ) -> int:
        """Queue `func(*args, **kwargs)` on `kind`'s lane. Returns the job id.

        Never raises for a full queue (the queues are unbounded) and never
        blocks the caller, which is the whole contract the `*_in_background`
        helpers had and kept.

        **`dedupe_key`: one job per thing in flight.** The readers are
        write-once only once a result is stored, so two commits of the same
        picture in quick succession (a note saved while the board it came
        from saves too) queued two captions and two reads before either had
        written anything (owner: "like 4 agent processes started ... the
        vision captioning and ocr should only happen each once"). A job whose
        key matches one queued or running is not queued again; the existing
        job's id is returned.
        """
        return self._submit(kind, func, tuple(args), dict(kwargs), name, dedupe_key, None, None)

    def resubmit(
        self,
        kind: str,
        func: Callable[..., object],
        args: tuple,
        kwargs: dict,
        name: str,
        dedupe_key: object,
        durable_id: int,
        durable_db: object = None,
    ) -> int:
        """Queue a job a previous process left in the `jobs` table: the
        row exists already, so nothing new is recorded."""
        return self._submit(kind, func, tuple(args), dict(kwargs), name, dedupe_key, durable_id, durable_db)

    def _submit(
        self,
        kind: str,
        func: Callable[..., object],
        args: tuple,
        kwargs: dict,
        name: str,
        dedupe_key: object,
        durable_id: int | None,
        durable_db: object,
    ) -> int:
        lane = self.lane_for(kind)
        self.start()
        with self._lock:
            if self._stopping.is_set():
                logger.debug("dropping a %s job: the pool is shutting down", kind)
                return 0
            duplicate = None
            if dedupe_key is not None:
                for existing in (*self._running.values(), *self._queued.values()):
                    if existing.dedupe_key == dedupe_key:
                        duplicate = existing
                        break
            if duplicate is None:
                self._seq += 1
                job = _Job(self._seq, kind, func, args, kwargs, name)
                job.dedupe_key = dedupe_key
                self._queued[job.seq] = job
        if duplicate is not None:
            # A resumed row whose work is already in hand here: close it, or
            # it would stay queued and be resumed again every launch.
            if durable_id is not None and duplicate.durable_id != durable_id:
                jobstore.supersede(durable_id, db=durable_db)
            return duplicate.seq
        # Recorded outside the lock (a database write), and before the job
        # is on its lane, so a worker never sees a job whose row is not yet
        # written. Only a known handler with plain-data arguments is kept.
        if durable_id is None and jobstore.durable_kind(kind, func):
            durable_db = jobstore.peek_db()
            durable_id = jobstore.record(kind, args, kwargs, name=name, dedupe_key=dedupe_key, db=durable_db)
        job.durable_id = durable_id
        job.durable_db = durable_db
        self._queues[lane].put(job)
        return job.seq

    def forget(self, durable_id: int) -> bool:
        """Drop the queued job behind `durable_id` from memory (its row was
        cancelled). The worker would skip it anyway, its lease failing; this
        takes it off the panel now rather than when its turn comes."""
        with self._lock:
            for seq, job in list(self._queued.items()):
                if job.durable_id == durable_id:
                    del self._queued[seq]
                    return True
        return False

    # -- the worker ---------------------------------------------------------

    def _work(self, lane: str) -> None:
        work_queue = self._queues[lane]
        while True:
            job = work_queue.get()
            try:
                if job is None:
                    return
                if lane == "model":
                    # A chat turn in flight goes first (`core/model_gate.py`,
                    # ARCH-09): the job stays queued until it is done.
                    model_gate.yield_to_interactive(stop=self._stopping)
                with self._lock:
                    self._queued.pop(job.seq, None)
                    if self._stopping.is_set():
                        # Drained, not run: this is what makes shutdown fast
                        # with a long queue behind it. A durable job's row
                        # stays queued, so the next launch runs it.
                        continue
                    job.started_at = time.time()
                    self._running[job.seq] = job
                # A remembered job is claimed first: a row cancelled while it
                # waited, or claimed by another server on the same file,
                # is not run.
                if job.durable_id is not None and not jobstore.lease(job.durable_id, db=job.durable_db):
                    with self._lock:
                        self._running.pop(job.seq, None)
                    continue
                error = ""
                run = _ledger_run(job)
                try:
                    with origin.acting_for(job.another_device), jobruns.bound(run):
                        job.func(*job.args, **job.kwargs)
                except Exception as exc:
                    # One bad job used to be one dead thread and no record.
                    # `exc_info` because the stack is the whole value here:
                    # these run with no request to attach an error to.
                    logger.warning("background %s job failed", job.kind, exc_info=True)
                    error = str(exc) or type(exc).__name__
                    if run is not None:
                        run.fail(error)
                except BaseException:
                    #: A stop from outside the job (a shutdown): not a failure,
                    #: and never left saying "running" (B77).
                    if run is not None:
                        run.cancel("stopped before it finished")
                    raise
                finally:
                    if run is not None:
                        run.finish()
                    with self._lock:
                        self._running.pop(job.seq, None)
                    if job.durable_id is not None:
                        jobstore.finish(job.durable_id, error=error, db=job.durable_db)
            finally:
                work_queue.task_done()

    # -- reporting ----------------------------------------------------------

    def queued_count(self) -> int:
        with self._lock:
            return len(self._queued)

    def running_count(self) -> int:
        with self._lock:
            return len(self._running)

    def pending(self) -> list[dict]:
        """Queued and running jobs as `/tasks` rows, oldest first.

        Oldest first for the same reason `filejobs.running` is: the panel
        reads as a queue, and the job someone is wondering about is the one
        that has been waiting longest.
        """
        with self._lock:
            jobs = sorted(
                (job for job in (*self._running.values(), *self._queued.values()) if job.kind not in QUIET_KINDS),
                key=lambda job: job.seq,
            )
            running = set(self._running)
        rows = []
        #: Back-pressure on the panel (19.5): the running jobs, the next few
        #: waiting of each kind, then one row per kind with the rest counted.
        shown: dict[str, int] = {}
        hidden: dict[str, int] = {}
        for job in jobs:
            #: A pass's row is named for the pass ("Night shift").
            label = job.name if job.kind == "pass" and job.name else LABELS.get(job.kind, "Background job")
            waiting = job.seq not in running
            if waiting:
                shown[job.kind] = shown.get(job.kind, 0) + 1
                if shown[job.kind] > PENDING_ROWS_PER_KIND:
                    hidden[job.kind] = hidden.get(job.kind, 0) + 1
                    continue
            rows.append(
                {
                    "kind": f"job-{job.kind}",
                    "name": job.name,
                    "label": label,
                    "detail": f"{job.name} (queued)" if waiting and job.name else (job.name or ("queued" if waiting else "")),
                    #: A single model call reports no progress, and a queued
                    #: job has made none: `None` is the panel's own
                    #: "running, no percentage" state and the truth here.
                    "progress": None,
                    "log": [],
                    "queued": waiting,
                    "started": job.queued_at if waiting else (job.started_at or job.queued_at),
                    #: The `jobs` row, for `/jobs/{id}/cancel`; None when
                    #: this process alone knows the job.
                    "job_id": job.durable_id,
                }
            )
        for kind, count in hidden.items():
            rows.append(
                {
                    "kind": f"job-{kind}",
                    "name": "",
                    "label": LABELS.get(kind, "Background job"),
                    "detail": f"{count:,} more queued",
                    "progress": None,
                    "log": [],
                    "queued": True,
                    "job_id": None,
                    "more": count,
                }
            )
        return rows

    # -- stopping -----------------------------------------------------------

    def shutdown(self, deadline: float = 5.0) -> bool:
        """Stop taking work, drop what is queued, join the workers.

        Returns True when every worker stopped inside `deadline`. False means
        one was inside a job (a model call that cannot be interrupted); the
        workers are daemons, so the process exits regardless, and the answer
        is False rather than a longer wait because a slow quit is the bug
        this deadline exists for.
        """
        self._stopping.set()
        with self._lock:
            workers = list(self._workers)
            dropped = len(self._queued)
            self._queued.clear()
            started = self._started
        if not started:
            return True
        for lane, work_queue in self._queues.items():
            for _ in range(self._widths[lane]):
                work_queue.put(None)
        ends = time.monotonic() + max(0.0, deadline)
        for worker in workers:
            worker.join(max(0.0, ends - time.monotonic()))
        alive = [worker.name for worker in workers if worker.is_alive()]
        if dropped or alive:
            logger.info(
                "background pool stopped: %d job(s) dropped, %d worker(s) still busy%s",
                dropped,
                len(alive),
                f" ({', '.join(alive)})" if alive else "",
            )
        return not alive


# -- the app's one pool -------------------------------------------------------

_default: Pool | None = None
_default_lock = threading.Lock()


def pool() -> Pool:
    """The process's pool, made on first use.

    Lazy rather than built at import: `create_app()` is called by hundreds of
    tests, and a module that starts threads at import time makes every one of
    them pay for workers it never uses.
    """
    global _default
    with _default_lock:
        if _default is None:
            _default = Pool()
        return _default


def enqueue(
    kind: str,
    func: Callable[..., object],
    *args: object,
    name: str = "",
    dedupe_key: object = None,
    **kwargs: object,
) -> int:
    return pool().enqueue(kind, func, *args, name=name, dedupe_key=dedupe_key, **kwargs)


def pending() -> list[dict]:
    return pool().pending()


def resubmit(kind, func, args, kwargs, name, dedupe_key, durable_id, durable_db=None) -> int:  # noqa: ANN001
    return pool().resubmit(kind, func, args, kwargs, name, dedupe_key, durable_id, durable_db)


def forget(durable_id: int) -> bool:
    """Drop a cancelled row's job from the queue, if this process has one.
    Reads the singleton without making one: no pool, nothing queued."""
    with _default_lock:
        current = _default
    return current.forget(durable_id) if current is not None else False


def resume(db=None) -> dict:  # noqa: ANN001
    """At launch: prune old endings, then queue again what the last run
    left (`jobstore.resume`). Never raises."""
    jobstore.prune(db=db)
    database = jobstore.peek_db(db)

    def again(kind, func, args, kwargs, name, dedupe_key, durable_id):  # noqa: ANN001, ANN202
        return resubmit(kind, func, args, kwargs, name, dedupe_key, durable_id, database)

    return jobstore.resume(db=database, enqueue=again)


jobstore.set_forget(forget)


def shutdown(deadline: float = 5.0) -> bool:
    """Called from the app's lifespan. Never raises: a shutdown handler that
    throws leaves the rest of the teardown unrun.

    The singleton is dropped as well as stopped, so the next `pool()` builds a
    fresh one. That matters in exactly one place and it is not production: a
    test process creates and tears down many apps, and a pool left in its
    stopped state would silently drop every job of every app after the first,
    which is the "feature that never ran once" shape (CLAUDE.md section 6).
    """
    global _default
    jobstore.stop()
    with _default_lock:
        current = _default
        _default = None
    if current is None:
        return True
    try:
        return current.shutdown(deadline=deadline)
    except Exception:  # noqa: BLE001  # a failed teardown must not stop the rest
        logger.warning("the background pool did not shut down cleanly", exc_info=True)
        return False
