"""The chat stream steps running in worker threads, so the database is never
closed under one (L-world-class-892).

`chat_agent.stop_when_gone` runs each step of a stream (the agent's next event,
which reads the notebook) on the threadpool. When the client goes, the
generator is cancelled but the step already in its thread runs on. A quit, a
backup restore or a test's teardown then disposed the engine while that step
was inside a query: SQLite segfaulted the whole process (CI leg 1 on
586b5282, `relation_types.kinds` under `_fit_toolboxes`).

Each step is listed while it runs; `drain` sets every listed stream's stop (so
the model call ends early) and waits, bounded, for the steps to return. Call it
before anything disposes the engine.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager

_lock = threading.Lock()
_running: dict[int, tuple[object, threading.Event]] = {}


@contextmanager
def running(stop):  # noqa: ANN001, ANN201 - the stream's StopEvent
    """List the step in this block as running until it returns."""
    finished = threading.Event()
    key = id(finished)
    with _lock:
        _running[key] = (stop, finished)
    try:
        yield
    finally:
        with _lock:
            _running.pop(key, None)
        finished.set()


def in_flight() -> int:
    with _lock:
        return len(_running)


def drain(timeout: float = 5.0) -> bool:
    """Stop every running step's stream and wait for the steps; True if none is left."""
    with _lock:
        steps = list(_running.values())
    for stop, _finished in steps:
        if stop is not None:
            stop.set()
    deadline = time.monotonic() + timeout
    for _stop, finished in steps:
        if not finished.wait(max(0.0, deadline - time.monotonic())):
            return False
    return True
