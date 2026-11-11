"""What a waiting card proposed, kept on the server (`ai/consent.py`).

A typed yes must run what the person was shown and nothing the page says now, so
a card parked in a turn is stored here under a single-use id and the page carries
only the id. The same shape as `core/hellostore` tickets: in process, a short
life, a bounded size, spent when taken (Confirm spends it too, so a yes typed
after a press runs nothing twice)."""

from __future__ import annotations

import secrets
import threading
import time

TTL_SECONDS = 1800
MAX_PARKED = 64

_lock = threading.Lock()
_parked: dict[str, tuple[float, dict]] = {}
#: Ids already spent, kept for the same life: an expired id and a spent one both find nothing in
#: `_parked`, but only the spent one must not run again from the steps a page sends.
_spent: dict[str, float] = {}


def _now() -> float:
    return time.monotonic()


def park(proposal: dict) -> str:
    """Keep `proposal` (label, steps, skipped, tool, wording) and return its id."""
    now = _now()
    with _lock:
        for key in [k for k, (until, _p) in _parked.items() if until <= now]:
            _parked.pop(key, None)
        while len(_parked) >= MAX_PARKED:
            _parked.pop(next(iter(_parked)))
        key = secrets.token_urlsafe(12)
        _parked[key] = (now + TTL_SECONDS, proposal)
    return key


def take(key: str | None) -> dict | None:
    """The proposal under `key`, once; None when unknown, spent or too old."""
    with _lock:
        held = _parked.pop(key or "", None)
        if held is not None:
            while len(_spent) >= MAX_PARKED * 4:
                _spent.pop(next(iter(_spent)))
            _spent[key] = _now() + TTL_SECONDS
    if held is None or held[0] <= _now():
        return None
    return held[1]


def was_spent(key: str | None) -> bool:
    """True when `key` was parked and has been taken since (a press or a typed yes ran it)."""
    with _lock:
        until = _spent.get(key or "")
    return until is not None and until > _now()


def reset_for_tests() -> None:
    with _lock:
        _parked.clear()
        _spent.clear()
