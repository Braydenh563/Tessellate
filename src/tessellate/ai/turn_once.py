"""One chat turn runs once per turn id (L682, E70).

A send whose answer was lost (a dropped connection, a double click, a retry
by a proxy) posts again with the same `turn_id`; the server then hands back
the first result instead of asking the model a second time and, in agent
mode, repeating the writes. In process and short-lived, like
`ai/consent_store.py`: a restart forgets them, and the turn runs afresh,
which is what a lost server would have done anyway.
"""

from __future__ import annotations

import threading
import time

TTL_SECONDS = 600
MAX_SLOTS = 64
#: A turn marked running this long without finishing is taken to be gone (a closed tab that never read its stream).
RUNNING_STALE_SECONDS = 600


class Slot:
    """One turn id: a lock for the one-shot JSON route, a flag for the stream, and the first result."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.value: object | None = None
        self.running_since: float | None = None
        #: The stream was cut off after some lines went out: its writes may have happened, so it is not run again.
        self.partial = False
        self.at = time.monotonic()


_guard = threading.Lock()
_slots: dict[str, Slot] = {}


def _idle(held: Slot) -> bool:
    return not held.lock.locked() and held.running_since is None


def slot(turn_id: str, caller: str = "") -> Slot:
    """The slot for `turn_id` from `caller` (one device's sign-in), made on first use.

    Old or surplus slots go, oldest first, but never one whose turn is still
    running or waited on: dropping it let a retry run the turn a second time."""
    key = f"{caller}\x00{turn_id}"
    now = time.monotonic()
    with _guard:
        if key in _slots:
            return _slots[key]
        for old in [k for k, s in _slots.items() if now - s.at > TTL_SECONDS and _idle(s)]:
            _slots.pop(old, None)
        surplus = len(_slots) - MAX_SLOTS + 1
        for old in [k for k, s in _slots.items() if _idle(s)][: max(0, surplus)]:
            _slots.pop(old, None)
        return _slots.setdefault(key, Slot())


def begin_stream(held: Slot) -> bool:
    """Mark a streamed turn running; False when the same turn id is already being answered."""
    with _guard:
        since = held.running_since
        if held.partial:
            return False
        if since is not None and time.monotonic() - since < RUNNING_STALE_SECONDS:
            return False
        held.running_since = time.monotonic()
        return True


def end_stream(held: Slot, lines: list[str] | None, *, partial: bool = False) -> None:
    """The streamed turn ended: keep its lines when it finished; mark it when it was cut off partway."""
    with _guard:
        held.running_since = None
        held.partial = held.partial or partial
        if lines is not None:
            held.value = lines


def reset_for_tests() -> None:
    with _guard:
        _slots.clear()
