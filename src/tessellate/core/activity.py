"""The `jobs` service: one registry of what is running now (WORLD_CLASS_PLAN
28.1 rule 5, decision 70).

The owner, 2026-10-10: background work must be "visible and stoppable". Most
long jobs already announce themselves somewhere: `routes_tasks.collect()`
assembles the re-index, model pulls, installs, captions and page reads from
their own state, and `jobruns.job_run` books every pass, backup and import.
What had no home was the work a request does while the person waits on it (a
chat answer streaming, a document's AI pass) and a single Stop for all of it.

So this module holds the rest, in memory and for this process only:

    with activity.track("generation", "Answering in Chat") as job:
        for piece in stream:
            if job.stopped:
                break

`jobruns.Run` registers itself here on start, so every `job_run` kind is
listed without its caller knowing; `GET /activity` merges this list with
`collect()`'s rows and `POST /activity/{id}/stop` reaches either.

**Stop is cooperative**, as `core/bgtasks.py` argues: a flag the job reads at
its next boundary, plus an optional `on_stop` for a job that can be cut from
outside (a subprocess, an HTTP stream). Nothing here kills a thread.
"""

from __future__ import annotations

import itertools
import json
import logging
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager, nullcontext

from tessellate.core import private_turn

_lock = threading.Lock()
_ids = itertools.count(1)
_jobs: dict[str, Job] = {}
#: Jobs that ended with a page to show (an import's report), for the panel's
#: finished lines. Few and short-lived: the page itself is kept elsewhere.
_recent: list[dict] = []
RECENT_KEEP = 5
RECENT_SECONDS = 30 * 60


class StopEvent(threading.Event):
    """A stop flag that can also wake a call blocked on the network.

    `set()` runs the registered hooks, so a model request waiting for its first
    token (prefill, when no chunk arrives to check the flag against) is cut the
    moment Stop or a closed browser tab sets it, not when the model finishes."""

    def __init__(self) -> None:
        super().__init__()
        self._hooks: list[Callable[[], object]] = []
        self._hook_lock = threading.Lock()

    def set(self) -> None:
        super().set()
        with self._hook_lock:
            hooks, self._hooks = self._hooks, []
        for hook in hooks:
            try:
                hook()
            except Exception as exc:  # noqa: BLE001 - a failed close must not stop the others
                logging.getLogger("tessellate.activity").debug("stop: a close hook failed: %s", exc)

    def add_hook(self, hook: Callable[[], object]) -> Callable[[], None]:
        """Run `hook` when set (now, if already set); returns the remover."""
        if self.is_set():
            hook()
            return lambda: None
        with self._hook_lock:
            self._hooks.append(hook)

        def remove() -> None:
            with self._hook_lock:
                if hook in self._hooks:
                    self._hooks.remove(hook)

        return remove


class Job:
    """One running piece of work, as the Activity panel shows it."""

    def __init__(
        self,
        kind: str,
        label: str,
        on_stop: Callable[[], object] | None,
        stoppable: bool,
        lease: float | None = None,
        stop_event: threading.Event | None = None,
    ) -> None:
        self.id = f"job-{next(_ids)}"
        self.kind = kind
        self.label = label
        self.detail = ""
        self.progress: float | None = None
        self.started = time.time()
        self.on_stop = on_stop
        self.stoppable = stoppable or on_stop is not None
        #: Shared with the work it tracks when that work must see Stop mid-call
        #: (a skill run's budget, `ai/budget.py`), not only at its next yield.
        self._stop = stop_event or StopEvent()
        #: A job run somewhere else (a code run in the browser's sandbox)
        #: holds a lease it renews with `touch`; one not renewed in time is
        #: gone, so a closed tab does not leave a row that never ends.
        self.lease = lease
        self.beat = time.monotonic()
        #: The id of a page that says how it went (`/import/reports/{id}`);
        #: set before the job finishes and it is kept as a finished line.
        self.report: str | None = None
        self.result = ""
        #: Its run in the process ledger (`jobruns`, INBOX 805): the title,
        #: who started it and its timed lines, kept after it ends.
        self.run = None

    @property
    def expired(self) -> bool:
        return self.lease is not None and time.monotonic() - self.beat > self.lease

    def touch(self) -> None:
        self.beat = time.monotonic()

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    def update(self, done: int | None = None, total: int | None = None, detail: str | None = None) -> None:
        if done is not None and total:
            self.progress = max(0.0, min(1.0, done / total))
        if detail is not None:
            self.detail = detail[:200]

    def request_stop(self) -> tuple[bool, str]:
        if not self.stoppable:
            return False, "This job cannot be stopped part way; it will finish on its own."
        self._stop.set()
        if self.on_stop is not None:
            try:
                self.on_stop()
            except Exception:  # noqa: BLE001  # a failed stop is a message, not a 500
                return True, "Asked it to stop; it will end at its next step."
        return True, f"Stopping {self.label.lower()}."

    def row(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "label": self.label,
            "detail": self.detail,
            "progress": self.progress,
            "started": self.started,
            "stoppable": self.stoppable,
            "queued": False,
            "report": self.report,
            #: The ledger run's title and lines (INBOX 805), for the row's fold.
            "title": self.run.title if self.run is not None else self.label,
            "run_id": self.run.id if self.run is not None else "",
            "lines": self.run.lines() if self.run is not None else [],
        }


def start(
    kind: str,
    label: str,
    *,
    on_stop: Callable[[], object] | None = None,
    stoppable: bool = False,
    lease: float | None = None,
    title: str = "",
    ledger: bool = True,
    stop_event: threading.Event | None = None,
) -> Job:
    """`ledger=False` for a job that already opens its own `jobruns` run
    (an import), so the ledger lists it once."""
    job = Job(kind, label, on_stop, stoppable, lease, stop_event)
    if ledger:
        from tessellate.core import jobruns

        #: No database: a chat answer is a run to see, not a "last run" row.
        job.run = jobruns.Run(kind, None, title=title or label, origin="you")
        job.run.start()
    with _lock:
        _prune()
        _jobs[job.id] = job
    return job


def _prune() -> None:
    """Drop the leased jobs nobody renewed. Called with `_lock` held."""
    for job_id in [job_id for job_id, job in _jobs.items() if job.expired]:
        del _jobs[job_id]


def count(kind: str) -> int:
    with _lock:
        _prune()
        return sum(1 for job in _jobs.values() if job.kind == kind)


def finish(job: Job | None) -> None:
    if job is None:
        return
    if job.run is not None:
        if job.stopped:
            job.run.cancel("stopped")
        elif job.result:
            job.run.result = job.result
        job.run.finish()
    with _lock:
        _jobs.pop(job.id, None)
        if job.report:
            _recent.append({**job.row(), "detail": job.result or job.detail, "progress": 1.0, "stoppable": False,
                            "finished": time.time()})
            del _recent[:-RECENT_KEEP]


def recent() -> list[dict]:
    """The finished lines still worth showing, newest first."""
    cutoff = time.time() - RECENT_SECONDS
    with _lock:
        return [row for row in reversed(_recent) if row["finished"] >= cutoff]


@contextmanager
def track(
    kind: str,
    label: str,
    *,
    on_stop: Callable[[], object] | None = None,
    stoppable: bool = True,
    title: str = "",
    ledger: bool = True,
    stop_event: threading.Event | None = None,
    bind_thread: bool = True,
) -> Iterator[Job]:
    """Register for the length of the block. `stoppable` defaults to True
    because a block that loops is expected to read `job.stopped`."""
    job = start(kind, label, on_stop=on_stop, stoppable=stoppable, title=title, ledger=ledger, stop_event=stop_event)
    try:
        #: Not across a generator's yields (`tracked_stream` binds per step):
        #: a thread-local left set there would leak into the next request.
        with bind(job) if bind_thread else nullcontext():
            yield job
    except GeneratorExit:
        #: The reader went (a closed tab, a new question): a stop, not a failure.
        if job.run is not None:
            job.run.cancel("closed before it finished")
        raise
    except Exception as exc:
        if job.run is not None:
            job.run.fail(str(exc) or type(exc).__name__)
        raise
    finally:
        finish(job)


#: The job whose stream this thread is advancing right now. A streamed run is a
#: sync generator, advanced one `next()` at a time on whichever worker thread
#: the server picks, and one `next()` can hold a model call and the writes that
#: follow it. Stop only lands between yields, so a call that returned after
#: Stop would still write; `current_stopped` lets the one door writes go
#: through (`tools.execute_tool`) see that Stop came in meanwhile.
_bound = threading.local()


@contextmanager
def bind(job: Job) -> Iterator[None]:
    """Make `job` this thread's current job for the length of the block."""
    from tessellate.core import jobruns

    previous = getattr(_bound, "job", None)
    _bound.job = job
    try:
        #: Its run too, so a model call inside the step adds its lines there.
        with jobruns.bound(job.run):
            yield
    finally:
        _bound.job = previous


def stop_aware(response, items: Iterator) -> Iterator:  # noqa: ANN001
    """`items`, read from the streamed HTTP `response`, ended when the job this
    thread is advancing is stopped (Stop pressed, or the browser went away).

    The check runs between chunks; the hook closes the connection so a read
    blocked before the first token ends too, and the upstream model stops
    generating instead of finishing a turn nobody is waiting for."""
    job = getattr(_bound, "job", None)
    event = getattr(job, "_stop", None)
    if event is None:
        yield from items
        return

    def cut() -> None:
        sock = None
        try:
            sock = response.raw._fp.fp.raw._sock  # the live socket, if this is a plain one
        except AttributeError:
            pass  # not a plain socket: close() below is all there is
        if sock is not None:
            try:
                sock.shutdown(2)
            except OSError:
                pass  # already closed by the other side: nothing left to cut
        response.close()

    remove = event.add_hook(cut) if hasattr(event, "add_hook") else (lambda: None)
    try:
        for item in items:
            if event.is_set():
                break
            yield item
    except Exception:
        if not event.is_set():
            raise
    finally:
        remove()
        if event.is_set():
            response.close()


def current_stop_event() -> StopEvent | None:
    """The stop flag of the job this thread is advancing, if it has one that
    can wake a blocked call (`StopEvent`)."""
    event = getattr(getattr(_bound, "job", None), "_stop", None)
    return event if isinstance(event, StopEvent) else None


def current_stopped() -> bool:
    """Whether the job this thread is advancing has been asked to stop."""
    job = getattr(_bound, "job", None)
    return bool(job is not None and job.stopped)


def tracked_stream(
    kind: str, label: str, lines: Iterator, *, title: str = "", stop_event: threading.Event | None = None
) -> Iterator:
    """A streamed response that shows in Activity and ends on Stop.

    Closing the inner generator runs its `finally`, which is what closes the
    HTTP stream to the model, so the runner stops generating too. Each line
    the stream sends is read by a `StreamNarrator`, so the run's log says
    what the answer did (searched, called a tool, wrote) in words."""
    with track(kind, label, title=title, stop_event=stop_event, bind_thread=False) as job:
        narrator = StreamNarrator()
        try:
            source = iter(lines)
            while True:
                with bind(job):  # the step that follows may write; Stop must reach it
                    try:
                        line = next(source)
                    except StopIteration:
                        break
                said = narrator(line)
                if said and job.run is not None:
                    job.run.say(said)
                yield line
                if job.stopped:
                    break
        finally:
            close = getattr(lines, "close", None)
            if close is not None:
                close()
            job.result = narrator.summary()


#: Longest argument value a log line quotes; a pasted page is not a line.
_ARG_CHARS = 60


def tool_arguments_in_words(arguments: object) -> str:
    """`{"query": "gaming mouse?\\", "limit": 5}` as `query "gaming mouse?", limit 5`.

    Empty values are left out, a stray backslash or quote a small model
    leaves on a value is trimmed, and a long value is cut: the line says
    what was asked for, not the payload."""
    if not isinstance(arguments, dict) or not arguments:
        return "no arguments"
    parts = []
    for key, value in arguments.items():
        if value in (None, "", [], {}):
            continue
        if isinstance(value, (list, tuple)):
            value = ", ".join(str(v) for v in list(value)[:3]) + (" and more" if len(value) > 3 else "")
        text = " ".join(str(value).replace("\\", " ").split()).strip("'\" ")
        if len(text) > _ARG_CHARS:
            text = text[: _ARG_CHARS - 1] + "…"
        parts.append(f'{key} "{text}"' if isinstance(value, str) else f"{key} {text}")
    return ", ".join(parts) or "no arguments"


def _no_icon(text: object) -> str:
    """A label that starts with an icon token (`ph:warning Search`) without it."""
    words = str(text or "").split(" ", 1)
    return words[1] if len(words) == 2 and words[0].startswith("ph:") else str(text or "")


class StreamNarrator:
    """Turns one answer's NDJSON events into the run's log lines.

    Only the events that are a step get a line (searching, what was found,
    each tool call, writing, done); the hundreds of answer deltas are one
    "Writing the answer" and a word count at the end."""

    def __init__(self) -> None:
        self.chars = 0
        self.text = ""
        self.tools = 0
        self.failed = 0
        self.thought = False

    def __call__(self, line: object) -> str:
        try:
            event = json.loads(line) if isinstance(line, (str, bytes)) else None
        except ValueError:
            return ""
        if not isinstance(event, dict):
            return ""
        kind = event.get("type")
        handler = self._HANDLERS.get(kind) if isinstance(kind, str) else None
        return handler(self, event) if handler else ""

    def _status_line(self, event: dict) -> str:
        stage = str(event.get("stage") or "")
        return "Searching your notes." if stage == "searching" else stage.replace("_", " ").capitalize()

    def _text_line(self, event: dict) -> str:
        #: A plan's steps are written from the person's own words.
        return "" if private_turn.active() else str(event.get("text") or "")

    def _web_line(self, event: dict) -> str:
        pages = len(event.get("sources") or [])
        return f"Read {pages} web page{'' if pages == 1 else 's'}."

    def _done_line(self, event: dict) -> str:
        return f"Done: {self.summary()}."

    def _found_line(self, event: dict) -> str:
        found = len(event.get("raw_results") or [])
        mode = event.get("search_mode") or "search"
        lines = [f"Found {found} note{'' if found == 1 else 's'} ({mode})."]
        if event.get("composed"):
            lines.append("Composing the answer from your notes, no model.")
        elif event.get("answered_by"):
            lines.append(f"Answering with {event['answered_by']}.")
        return " ".join(lines)

    def _tool_line(self, event: dict) -> str:
        self.tools += 1
        name = event.get("tool") or _no_icon(event.get("label")) or "a tool"
        #: A private chat's log names the tool and never what it was asked or
        #: why it failed: both quote the question's words.
        if event.get("ok") is False:
            self.failed += 1
            return f"{name} did not run." if private_turn.active() else f"{name} did not run: {event.get('error') or 'no reason given'}."
        return f"Called {name}." if private_turn.active() else f"Called {name}: {tool_arguments_in_words(event.get('arguments'))}."

    def _thinking_line(self, event: dict) -> str:
        first = not self.thought
        self.thought = True
        return "Thinking." if first else ""

    def _item_line(self, event: dict) -> str:
        reason = "" if private_turn.active() else " ".join(str(event.get("reason") or "").split())[:_ARG_CHARS].rstrip(".")
        return f"Suggested a change: {reason}." if reason else "Suggested a change."

    def _answer_line(self, event: dict) -> str:
        #: Chat sends `delta`; the Guide and drafting send `text` (OPEN row 553).
        delta = str(event.get("delta") or event.get("text") or "")
        first = self.chars == 0 and bool(delta)
        self.chars += len(delta)
        if len(self.text) < 20000:
            self.text += delta
        return "Writing the answer." if first else ""

    _HANDLERS = {
        "status": _status_line,
        "meta": _found_line,
        "tool": _tool_line,
        "plan": _text_line,
        "step": _text_line,
        "web_sources": _web_line,
        "answer": _answer_line,
        "delta": _answer_line,
        "thinking": _thinking_line,
        "item": _item_line,
        "done": _done_line,
    }

    def summary(self) -> str:
        words = len(self.text.split())
        said = f"{words} word{'' if words == 1 else 's'}"
        if self.tools:
            said += f", {self.tools} tool call{'' if self.tools == 1 else 's'}"
        if self.failed:
            said += f" ({self.failed} did not run)"
        return said


def get(job_id: str) -> Job | None:
    with _lock:
        _prune()
        return _jobs.get(job_id)


def stop(job_id: str) -> tuple[bool, str]:
    job = get(job_id)
    if job is None:
        return False, "That job has already finished."
    return job.request_stop()


def stop_kind(kind: str) -> int:
    """Stop every job of one kind (every generation, before the model is
    unloaded). Returns how many were asked."""
    with _lock:
        jobs = [job for job in _jobs.values() if job.kind == kind]
    return sum(1 for job in jobs if job.request_stop()[0])


def snapshot() -> list[dict]:
    with _lock:
        _prune()
        return [job.row() for job in sorted(_jobs.values(), key=lambda j: -j.started)]


def clear() -> None:
    """Tests only: the registry is process-global, like `taskhistory`."""
    from tessellate.core import jobruns

    with _lock:
        _jobs.clear()
        _recent.clear()
    jobruns.clear_live()
