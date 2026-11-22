"""Interactive model calls go first (audit 2026-10-05, ARCH-09).

A local model runner serves one request at a time. The background work that
calls it (the night pass, entity extraction, captions, vision reading, a
background filing) used to start its next call whenever it was ready, so a chat
turn asked while an import of two hundred pictures was being captioned waited
behind as many of those calls as reached the runner first, with nothing on
screen to say why.

**Priority, not exclusion.** This is a counter of interactive calls in flight
(a chat turn holds it for its whole stream) and a wait for background work to
take *between* its calls: background work yields until no interactive call is
running, so a person waits at most for the one background call already in
flight. Nothing here holds a lock across a model call, so there is nothing to
deadlock: an interactive call never waits on this module, and a background
call that waits gives up after `MAX_YIELD_SECONDS` rather than starving.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

#: The longest a background call waits for interactive ones to finish before
#: going anyway: a chat left streaming must not stop the night pass for ever.
MAX_YIELD_SECONDS = 120.0

_condition = threading.Condition()
_interactive = 0


@contextmanager
def interactive() -> Iterator[None]:
    """Mark an interactive model call (a chat turn) as in flight."""
    global _interactive
    with _condition:
        _interactive += 1
    try:
        yield
    finally:
        with _condition:
            _interactive -= 1
            _condition.notify_all()


def busy() -> bool:
    """Is an interactive call in flight right now?"""
    with _condition:
        return _interactive > 0


def yield_to_interactive(timeout: float = MAX_YIELD_SECONDS, stop: threading.Event | None = None) -> bool:
    """Wait, before a background model call, until no interactive call is in
    flight. True when the way is clear, False when it gave up (`timeout`, or
    `stop` set) and the caller goes ahead anyway."""
    with _condition:
        if stop is None:
            return _condition.wait_for(lambda: _interactive == 0, timeout=timeout)
        remaining = timeout
        while _interactive > 0 and remaining > 0 and not stop.is_set():
            step = min(0.5, remaining)
            _condition.wait(step)
            remaining -= step
        return _interactive == 0
