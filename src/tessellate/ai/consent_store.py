"""What a waiting card proposed, kept on the server (`ai/consent.py`).

A typed yes must run what the person was shown and nothing the page says now, so
a card parked in a turn is stored here under a single-use id and the page carries
only the id. The same shape as `core/hellostore` tickets: in process, a short
life, a bounded size, spent when taken (Confirm spends it too, so a yes typed
after a press runs nothing twice)."""

from __future__ import annotations

import json
import logging
import os
import secrets
import threading
import time
from pathlib import Path

_logger = logging.getLogger(__name__)

TTL_SECONDS = 1800
MAX_PARKED = 64

_lock = threading.RLock()
_parked: dict[str, tuple[float, dict]] = {}
#: Ids already spent, kept for the same life: an expired id and a spent one both find nothing in
#: `_parked`, but only the spent one must not run again from the steps a page sends.
_spent: dict[str, float] = {}


#: What a pressed card did (its summary and Undo steps), kept for the same life under its id: a chat
#: reopened later reads the outcome from here, never from what a page says it was.
_results: dict[str, tuple[float, dict]] = {}
#: Spent ids that were turned down (a typed no, Cancel): they reopen as cancelled, never as done.
_declined: dict[str, float] = {}


#: The last pressed card's label and Undo steps: what "undo that" says back for an act whose old value is
#: not in its sentence (a rename's old title, a move's old category; L-chat-29). One person, one chat.
_latest: tuple[float, str, list[dict]] | None = None


#: Kept past a restart and past the next act (L-chat-33): for each rename or move the card ran, the note's
#: id and the title and category it had, newest last. Only that, never the body, in a file beside the
#: database (a private note is never touched from Chat), so "undo the rename of X" finds its own old value.
LOG_MAX = 12
LOG_DAYS = 3


def _log_path() -> Path:
    from tessellate.core.config import resolved_data_dir

    return resolved_data_dir() / "chat_undo.json"


def _read_log() -> list[dict]:
    try:
        rows = json.loads(_log_path().read_text("utf-8"))
    except (OSError, ValueError):
        return []
    cutoff = time.time() - LOG_DAYS * 86400
    return [r for r in rows if isinstance(r, dict) and isinstance(r.get("at"), (int, float)) and r["at"] > cutoff] if isinstance(rows, list) else []


def log_undo(undo: list[dict] | None, title: str) -> None:
    """Add the note a rename or move changed (from the `edit_note` Undo step) to the on-disk log."""
    from tessellate.ai.composer_frame import note_title  # the name reader itself: commands would close an import cycle

    rows = []
    for step in undo or []:
        args = step.get("arguments") or {}
        if step.get("name") == "edit_note" and args.get("note_id"):
            rows.append({"at": time.time(), "note_id": args["note_id"], "title": note_title(str(args.get("content") or ""), size=120), "category": args.get("category") or "", "label": title})
    if not rows:
        return
    with _lock:
        keep = (_read_log() + rows)[-LOG_MAX:]
        path = _log_path()
        tmp = path.with_name(path.name + ".tmp")
        try:
            #: Born 0600 and swapped in whole: never readable by others, never half-written.
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(keep))
            os.replace(tmp, path)
        except OSError:
            tmp.unlink(missing_ok=True)  # a log that cannot be written only costs the undo-by-sentence of older acts


def undo_log() -> list[dict]:
    """The renames and moves kept on disk, newest first (the last card's in-process steps are not needed here)."""
    with _lock:
        return list(reversed(_read_log()))


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
    return ""


def remember(key: str | None, result: dict) -> dict:
    """Keep `result` (summary, undo, label) under a pressed card's id and hand it back."""
    if key:
        with _lock:
            while len(_results) >= MAX_PARKED * 4:
                _results.pop(next(iter(_results)))
            _results[key] = (_now() + TTL_SECONDS, result)
    return result


def note_latest(label: str, undo: list[dict] | None) -> None:
    """Keep the Undo steps of the card just run, for the sentence that takes it back."""
    global _latest  # noqa: PLW0603
    with _lock:
        _latest = (_now() + TTL_SECONDS, label, list(undo or []))


def take_latest() -> tuple[str, list[dict]]:
    """(label, Undo steps) of the last card run, once: a second ask finds nothing to take back."""
    global _latest  # noqa: PLW0603
    with _lock:
        held, _latest = _latest, None
    return (held[1], held[2]) if held is not None and held[0] > _now() and held[2] else ("", [])


def latest_undo() -> list[dict]:
    """The Undo steps of the last card run, or [] when none or past its life."""
    with _lock:
        held = _latest
    return held[2] if held is not None and held[0] > _now() else []


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
    global _latest  # noqa: PLW0603
    with _lock:
        _latest = None
        try:
            _log_path().unlink()
        except (OSError, ImportError):
            #: No log file yet (or no data dir in this test): nothing to clear.
            _logger.debug("consent log not cleared", exc_info=True)
        _parked.clear()
        _spent.clear()
        _results.clear()
        _declined.clear()
