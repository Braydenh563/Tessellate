"""The registry of background threads that are not jobs (WORLD_CLASS_PLAN 26.2, decision 58).

A thread nobody can list or stop is the bug behind "the app would not quit"
and "a second embedding pass started under the first". Work with progress goes
through `jobruns`; a one-shot or a watcher that does not fits here instead:
`start(name, target, stop=...)` runs `target` on a daemon thread and keeps
`(name, started, stop)` until it returns, so the Tasks panel and a shutdown can
ask what is running and ask it to stop.

`stop` is optional on purpose: a thread that ends by itself within seconds
(a DNS probe) has nothing to stop. A long-lived one names how it stops.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger("tessellate.background")


@dataclass
class Entry:
    name: str
    started: float
    stop: Callable[[], None] | None
    thread: threading.Thread


_lock = threading.Lock()
_entries: dict[int, Entry] = {}


def start(name: str, target: Callable[[], None], stop: Callable[[], None] | None = None) -> threading.Thread:
    """Run `target` on a named daemon thread and register it until it returns."""

    def run() -> None:
        try:
            target()
        finally:
            with _lock:
                _entries.pop(threading.get_ident(), None)

    thread = threading.Thread(target=run, name=name, daemon=True)
    thread.start()
    with _lock:
        # Registered after the start so the key is the live thread's id; a
        # target that has already finished simply never appears.
        if thread.is_alive():
            _entries[thread.ident] = Entry(name, time.time(), stop, thread)
    return thread


def running() -> list[dict]:
    """What is running now: name, seconds up, and whether it can be stopped."""
    now = time.time()
    with _lock:
        return [
            {"name": e.name, "seconds": round(now - e.started, 1), "stoppable": e.stop is not None}
            for e in _entries.values()
            if e.thread.is_alive()
        ]


def stop_all() -> list[str]:
    """Ask every registered thread that can stop to do so; the names asked."""
    with _lock:
        todo = [e for e in _entries.values() if e.stop is not None]
    asked = []
    for entry in todo:
        try:
            entry.stop()
            asked.append(entry.name)
        except Exception:  # noqa: BLE001  # one stuck stopper must not keep the others running
            logger.warning("could not stop %s", entry.name, exc_info=True)
    return asked


def join_all(timeout: float = 5.0) -> None:
    """Wait up to `timeout` seconds for the registered one-shot threads (those
    with no `stop`, which end by themselves) to finish: a test that tears the
    app state down must not leave one to rebuild it (and a `./data` folder)
    from the thread. A long-lived watcher names its own stop and is skipped."""
    deadline = time.time() + timeout
    with _lock:
        threads = [e.thread for e in _entries.values() if e.stop is None]
    for thread in threads:
        thread.join(max(0.0, deadline - time.time()))
