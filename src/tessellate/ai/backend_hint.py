"""Answers for a route that only decorates, never waited for (audit 1029 H5, H6).

A probe of something that may be hung (the model backend, `docker info`) is a
second or several on a bad day. A route that paints a greeting, a badge or a
status must not sit behind it. `Latest.get` runs the probe on a thread and
waits `BUDGET` for it: a healthy backend (and every test fake) answers within
that and the answer is current. One that does not is served from its last
answer, or `default` before any, and the probe lands for the next call. One
probe is out at a time.
"""

from __future__ import annotations

import threading
import weakref
from collections.abc import Callable

from tessellate.core import background

#: Long enough for a local backend to answer; short enough for any route.
BUDGET = 0.15


class Latest:
    """The last answer of one kind of probe."""

    def __init__(self, default: object = None) -> None:
        self.value = default
        self.known = False
        self._out: threading.Event | None = None
        self._lock = threading.Lock()

    def get(self, probe: Callable[[], object], budget: float = BUDGET) -> object:
        with self._lock:
            done = self._out
            if done is None:
                done = self._out = threading.Event()
                #: Registered, so the activity list and quit see a probe in flight.
                background.start("backend probe", lambda: self._run(probe, done))
        done.wait(budget)
        return self.value

    def _run(self, probe: Callable[[], object], done: threading.Event) -> None:
        try:
            answer, ok = probe(), True
        except Exception:  # noqa: BLE001  # a probe that raises is a backend that is not there
            answer, ok = None, False
        with self._lock:
            if ok:
                self.value, self.known = answer, True
            self._out = None
        done.set()


_by_provider: "weakref.WeakKeyDictionary[object, Latest]" = weakref.WeakKeyDictionary()
_registry_lock = threading.Lock()


def running(provider) -> bool:  # noqa: ANN001
    """`provider.is_running()` without the wait; False before any answer."""
    with _registry_lock:
        latest = _by_provider.setdefault(provider, Latest(False))
    return bool(latest.get(provider.is_running))
