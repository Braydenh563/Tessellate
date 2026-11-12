"""The registry of named background workers (WORLD_CLASS_PLAN 26.2, decision 58).

`jobs.thread` lists a thread while it runs; `jobruns` books work with
progress. What had no home was a long-lived worker with its own start and
stop (the reminder notifier, a watcher): something quitting the app must be
able to name, stop and ask about, in one place, before the pool's deadline
starts counting.

    background.register("reminder-notifier", stop=notifier.stop)
    background.stop_all()          # first thing at quit: every stop is a flag set

A worker is one name with a `stop`, and optionally a `start` that makes
`start(name)` re-runnable. `stop` must only signal (set an event, close a
socket): `stop_all` never waits, because the point is to tell every worker at
once, then let the pool's single deadline cover them all.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger("tessellate.background")

_lock = threading.Lock()


@dataclass
class Worker:
    name: str
    stop: Callable[[], object]
    start: Callable[[], object] | None = None
    started_at: float | None = None
    running: bool = False


_workers: dict[str, Worker] = {}


def register(
    name: str,
    *,
    stop: Callable[[], object],
    start: Callable[[], object] | None = None,
    running: bool = True,
) -> Worker:
    """Name a worker. `running=True` records one already started by the caller;
    registering a name again replaces it (a restart of the same worker)."""
    worker = Worker(name, stop, start, time.time() if running else None, running)
    with _lock:
        _workers[name] = worker
    return worker


def unregister(name: str) -> None:
    with _lock:
        _workers.pop(name, None)


def start(name: str) -> bool:
    """Start a registered worker that has a `start` and is not running; True if it started."""
    with _lock:
        worker = _workers.get(name)
    if worker is None or worker.start is None or worker.running:
        return False
    worker.start()
    worker.running = True
    worker.started_at = time.time()
    return True


def stop(name: str) -> bool:
    """Signal one worker to stop; True if it was running. Never raises."""
    with _lock:
        worker = _workers.get(name)
    if worker is None or not worker.running:
        return False
    worker.running = False
    try:
        worker.stop()
    except Exception as exc:  # noqa: BLE001  # one stuck stopper must not keep the others running
        logger.warning("could not stop %s: %s", name, exc)
    return True


def stop_all() -> list[str]:
    """Signal every running worker at once (no waiting); the names asked."""
    with _lock:
        names = list(_workers)
    return [name for name in names if stop(name)]


def status() -> list[dict]:
    """Name, running and seconds up for each registered worker."""
    now = time.time()
    with _lock:
        workers = list(_workers.values())
    return [
        {
            "name": w.name,
            "running": w.running,
            "seconds": round(now - w.started_at, 1) if w.running and w.started_at else 0.0,
        }
        for w in workers
    ]
