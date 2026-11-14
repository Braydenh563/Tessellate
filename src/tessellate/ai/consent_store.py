"""What a waiting card proposed, kept on the server (`ai/consent.py`).

A typed yes must run what the person was shown and nothing the page says now, so
a card parked in a turn is stored here under a single-use id and the page carries
only the id. The same shape as `core/hellostore` tickets: in process, a short
life, a bounded size, spent when taken (Confirm spends it too, so a yes typed
after a press runs nothing twice)."""

from __future__ import annotations

import hashlib
import hmac
import json
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


#: What a pressed card did (its summary and Undo steps), kept for the same life under its id: a chat
#: reopened later reads the outcome from here, never from what a page says it was.
_results: dict[str, tuple[float, dict]] = {}
#: Spent ids that were turned down (a typed no, Cancel): they reopen as cancelled, never as done.
_declined: dict[str, float] = {}


#: A per-process secret: a call the server handed out (a parked card's tool, an Undo or a redo)
#: carries `sign_call`'s tag, and `/chat/tools/execute` runs only what still matches it (L566).
#: Not persisted on purpose: a restart voids every tag, as it voids every parked card.
_SECRET = secrets.token_bytes(32)


def sign_call(name: str, arguments: dict | None, steps: list | None = None) -> str:
    """The tag for one tool call: HMAC-SHA256 over its name, arguments and batch steps."""
    body = json.dumps([name, arguments or {}, steps or []], sort_keys=True, separators=(",", ":"), default=str)
    return hmac.new(_SECRET, body.encode(), hashlib.sha256).hexdigest()


def signed(call: dict | None) -> dict | None:
    """`call` ({"tool", "arguments", "steps"?}) with its `sig` added; anything else as it came."""
    if not isinstance(call, dict) or not call.get("tool"):
        return call
    return {**call, "sig": sign_call(str(call["tool"]), call.get("arguments"), call.get("steps"))}


def tag_matches(name: str, arguments: dict | None, steps: list | None, sig: str | None) -> bool:
    """Whether `sig` is this server's tag for exactly this call."""
    return bool(sig) and hmac.compare_digest(str(sig), sign_call(name, arguments, steps))


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
        tool = proposal.get("tool")
        if isinstance(tool, dict):  # the parked call is signed as it is parked
            proposal = {**proposal, "tool": {**tool, "sig": sign_call(str(tool.get("name")), tool.get("arguments"))}}
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


def peek(key: str | None) -> dict | None:
    """The proposal under `key` without spending it; None when unknown, spent or too old."""
    with _lock:
        held = _parked.get(key or "")
    return held[1] if held is not None and held[0] > _now() else None


def refusal_for_press(key: str | None, name: str, arguments: dict) -> str:
    """Why Confirm may not run `name` with `arguments` under card `key`, or "" when it may.

    The press is bound to the card (audit 1028 E43): what runs is what the card
    proposed, so a page cannot spend a card on a different action, and a card
    that was answered or has expired runs nothing. No `key` is an Undo or a
    redo of a change that already ran, which the card never covered."""
    if not key:
        return ""
    held = take(key)
    if held is None:
        return "That card is no longer waiting. Ask for it again."
    tool = held.get("tool")
    if not isinstance(tool, dict) or tool.get("name") != name or (tool.get("arguments") or {}) != (arguments or {}):
        return "That card is for a different action."
    if not tag_matches(name, arguments, None, tool.get("sig")):
        return "That card is for a different action."
    return ""


def remember(key: str | None, result: dict) -> dict:
    """Keep `result` (summary, undo, label) under a pressed card's id and hand it back."""
    if key:
        with _lock:
            while len(_results) >= MAX_PARKED * 4:
                _results.pop(next(iter(_results)))
            _results[key] = (_now() + TTL_SECONDS, result)
    return result


def result_of(key: str | None) -> dict | None:
    """What the pressed card `key` did, or None (never pressed, or past its life)."""
    with _lock:
        held = _results.get(key or "")
    return held[1] if held is not None and held[0] > _now() else None


def decline(key: str | None) -> dict | None:
    """`take` for a no: the card is spent and remembered as declined."""
    held = take(key)
    if key:
        with _lock:
            while len(_declined) >= MAX_PARKED * 4:
                _declined.pop(next(iter(_declined)))
            _declined[key] = _now() + TTL_SECONDS
    return held


def was_declined(key: str | None) -> bool:
    with _lock:
        until = _declined.get(key or "")
    return until is not None and until > _now()


def was_spent(key: str | None) -> bool:
    """True when `key` was parked and has been taken since (a press or a typed yes ran it)."""
    with _lock:
        until = _spent.get(key or "")
    return until is not None and until > _now()


def reset_for_tests() -> None:
    with _lock:
        _parked.clear()
        _spent.clear()
        _results.clear()
        _declined.clear()
