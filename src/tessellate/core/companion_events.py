"""What the notebook did, as kinds and times only, for the desk companion to react to (W31, compalive-1109).

The in-app companion answers nine things the page sees: the graph laid out, a long note opened, a note binned, a private
note opened, a remark said, a reminder due, a search that found something, a search that found nothing, and the note count
passing a round number (P7, Brief 88 N10). The desk companion
(`core/overlay`) runs in this process and cannot see the page, so the server notes the same nine here as it serves them
and the overlay reads what is new on its existing screen poll (`screenwatch.ScreenWatch`, every 2 s, never on a fall tick).

Nothing but a kind and a time is kept: no title, no text, no note id, no query. A private note is only ever the generic
`private_note` (its length and its binning are not hinted at either). There is no route that serves this ring; the overlay
calls `since` in-process, so an overlay in another process, or none, sees nothing and loses nothing."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable

#: The kinds the ring will hold; anything else is refused, so a caller cannot leak text by passing it as a kind.
KINDS = frozenset({"graph_laid", "long_note", "note_binned", "private_note", "remark", "reminder_bell", "search_found", "search_nothing", "note_milestone"})
#: How many are kept; an overlay that polls every 2 s never falls behind it.
RING = 64
#: Seconds before the same kind is noted again (the server is called more often than a person would see a reaction).
GAP: dict[str, float] = {
    "graph_laid": 60.0,
    "long_note": 5.0,
    "note_binned": 3.0,
    "private_note": 5.0,
    "remark": 600.0,
    "reminder_bell": 1.0,
    "search_found": 5.0,
    "search_nothing": 5.0,
    "note_milestone": 3600.0,
}
#: The note counts that are cheered (the app's `NMB_MILESTONES`, avatars.js): these, then every thousand.
MILESTONES = (10, 25, 50, 100, 250, 500)
#: An event older than this is not news to a figure that was sitting, asleep or hidden when it happened.
STALE = 20.0
#: As in the app (`NMB_MIND.saw`): a find counts only within this many seconds of a miss.
FOUND_AFTER_MISS = 30.0

clock: Callable[[], float] = time.time

_lock = threading.Lock()
_ring: deque[dict] = deque(maxlen=RING)
_last_id = 0
_last_at: dict[str, float] = {}
_MISS = "_miss"  # the last empty search, kept in _last_at so it is read and set under the lock


def reset() -> None:
    """Empty the ring (tests)."""
    global _last_id
    with _lock:
        _ring.clear()
        _last_at.clear()
        _last_id = 0


def record(kind: str, now: float | None = None) -> int:
    """Note that `kind` happened. The new id, or 0 when the kind is unknown or the same kind was noted inside its gap.
    Never raises: a route calls it on the way out."""
    global _last_id
    if kind not in KINDS:
        return 0
    at = clock() if now is None else now
    with _lock:
        if at - _last_at.get(kind, -1e9) < GAP.get(kind, 0.0):
            return 0
        _last_at[kind] = at
        _last_id += 1
        _ring.append({"id": _last_id, "kind": kind, "at": at})
        return _last_id


def counted(total: int, now: float | None = None) -> int:
    """A note was made and the notebook now holds `total`: a round number is a cheer (`note_milestone`). The id, or 0."""
    if total in MILESTONES or (total >= 1000 and total % 1000 == 0):
        return record("note_milestone", now)
    return 0


def searched(found: bool, now: float | None = None) -> None:
    """A search answered: nothing is a puzzled look; a find is a nod only within `FOUND_AFTER_MISS` s of a miss (as the app's)."""
    at = clock() if now is None else now
    with _lock:
        if found:
            nod = at - _last_at.pop(_MISS, -1e9) <= FOUND_AFTER_MISS
        else:
            _last_at[_MISS] = at
    if not found:
        record("search_nothing", at)
    elif nod:
        record("search_found", at)


def latest() -> int:
    """The newest id (0 when none has been noted)."""
    with _lock:
        return _last_id


def since(last_id: int, now: float | None = None) -> list[dict]:
    """What was noted after `last_id` and is not stale, oldest first: each `{"id", "kind", "at"}` and nothing else."""
    at = clock() if now is None else now
    with _lock:
        return [dict(row) for row in _ring if row["id"] > last_id and at - row["at"] <= STALE]
