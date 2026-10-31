"""Launch work that waits for the first unlock (INBOX 1492).

The owner's lag log: `/auth/unlock` 5072 ms, `/models/status` 3743 ms. Both
answered while the launch's own work (the search model's load, the speller's
lists, the day's housekeeping and backup, the jobs the last run left queued)
was still using the cores and the interpreter, because that work started at
launch and the lock screen can sit open for as long as a person takes to type.
So a launch with a password to give does that work after the first token has
been issued and the answer has gone, not before: `arm()` at launch,
`defer(name, fn)` for each piece, `fire()` where a token is issued
(`routes_auth._issue_token`). A launch with no password (a first run, a test)
is never armed and `defer` runs the piece at once, as it always did.

Leaf module: nothing here imports the app, so the dependency container and the
auth routes can both reach it.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from tessellate.core import background

logger = logging.getLogger("tessellate.afterunlock")

#: How long after the token the deferred work waits, so the answer, the
#: browser's first burst of requests and the first paint go through first.
SETTLE_SECONDS = 1.5

_lock = threading.Lock()
_state = {"armed": False, "fired": False}
_pending: list[tuple[str, Callable[[], None]]] = []


def arm() -> None:
    """The launch has a password: hold the work until someone unlocks."""
    with _lock:
        _state["armed"] = True
        _state["fired"] = False
        _pending.clear()


def armed() -> bool:
    """Whether work is being held (the tests and Settings, Logs read this)."""
    with _lock:
        return _state["armed"] and not _state["fired"]


def defer(name: str, run: Callable[[], None]) -> None:
    """Run `run` after the first unlock; at once when nothing is held."""
    with _lock:
        held = _state["armed"] and not _state["fired"]
        if held:
            _pending.append((name, run))
    if not held:
        run()


def fire() -> None:
    """A token has been issued: release the held work after the settle. Safe
    to call on every unlock; only the first does anything."""
    with _lock:
        if not _state["armed"] or _state["fired"]:
            return
        _state["fired"] = True
        work = list(_pending)
        _pending.clear()
    if work:
        background.start("after-unlock", lambda: _run_all(work))


def _run_all(work: list[tuple[str, Callable[[], None]]]) -> None:
    time.sleep(SETTLE_SECONDS)
    for name, run in work:
        try:
            run()
        except Exception:  # noqa: BLE001  # one piece of launch work must not stop the next
            logger.warning("launch work %s failed after the unlock", name, exc_info=True)
