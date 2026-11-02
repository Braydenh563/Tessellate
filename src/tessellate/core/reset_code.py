"""The six-digit code that stands in for a password at "I don't have it" (INBOX 1424, audit 1028 K1).

`POST /auth/reset` once took only a typed word, so any program on this
computer could seal every private note. Now the reset is requested first: the
server makes a code and prints it to its own terminal, where only someone who
can see this computer's server output can read it. The request answer never
carries it, and it is not written to the log buffer Settings, Logs shows (a
locked notebook has no one to open that page, and an unlocked one on the
network could read it).

At most two codes are live: asking again adds a second one and leaves the
first working, so a program looping on the request cannot kill the code the
owner is typing; a third ask inside `MIN_INTERVAL` seconds is refused
(`TooSoon`). Each lasts ten minutes with its own salt and wrong-try count, is
stored only as a keyed hash, is compared in constant time, and a correct one
consumes them all. A wrong try counts against every live code and dies after
five (the login throttle counts the same tries, so asking for a fresh code
does not reset the guessing).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sys
import threading
import time
from dataclasses import dataclass

from tessellate.core.deps import register_cache_reset

TTL_SECONDS = 600
MAX_WRONG = 5
CODE_DIGITS = 6
MAX_LIVE = 2
MIN_INTERVAL = 30

_lock = threading.Lock()
#: Replaced by tests with a fixed clock; never read the wall clock directly.
_now = time.time


@dataclass
class _Live:
    salt: bytes
    digest: bytes
    expires: float
    wrong: int = 0


class TooSoon(Exception):
    """A code was printed less than `MIN_INTERVAL` seconds ago."""

    def __init__(self, retry_after: int) -> None:
        super().__init__(retry_after)
        self.retry_after = retry_after


#: The live codes (oldest first) and when one was last made, kept in a holder
#: rather than rebound globals so every write is a visible use of one object.
_state: dict = {"live": [], "last": None}


def _hash(salt: bytes, code: str) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), salt, 100_000)


def _forget() -> None:
    _state["live"] = []
    _state["last"] = None


register_cache_reset(_forget)


def stderr_is_terminal() -> bool:
    """Where the code goes: "terminal" when stderr is a TTY, else "log" (desktop or tee'd launch)."""
    try:
        return bool(sys.stderr and sys.stderr.isatty())
    except (AttributeError, ValueError, OSError):
        return False


def issue() -> int:
    """Make a code, print it to stderr, keep only its hash. Returns the lifetime in seconds.

    Raises `TooSoon` inside `MIN_INTERVAL` of the last one. The oldest code is
    dropped only when a third would make more than `MAX_LIVE`.
    """
    with _lock:
        now = _now()
        last = _state["last"]
        if last is not None and now - last < MIN_INTERVAL:
            raise TooSoon(max(1, int(MIN_INTERVAL - (now - last)) + 1))
        _state["last"] = now
    code = f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"
    salt = secrets.token_bytes(16)
    fresh = _Live(salt=salt, digest=_hash(salt, code), expires=now + TTL_SECONDS)
    with _lock:
        _state["live"] = [c for c in _state["live"] if c.expires > now][-(MAX_LIVE - 1) :] + [fresh]
    print(  # noqa: T201  # stderr is the point: only whoever sees this computer's server output may read the code
        f"\nTessellate password reset code: {code}\n"
        f"It works for {TTL_SECONDS // 60} minutes. If you did not ask for it, ignore it.\n",
        file=sys.stderr,
        flush=True,
    )
    return TTL_SECONDS


def check(typed: str) -> bool:
    """True once, for the live code. Wrong tries are counted; the fifth kills the code."""
    shape_ok = isinstance(typed, str) and len(typed.strip()) == CODE_DIGITS and typed.strip().isascii() and typed.strip().isdigit()
    candidate = typed.strip() if shape_ok else "-" * CODE_DIGITS
    with _lock:
        now = _now()
        live = [c for c in _state["live"] if c.expires > now]
        _state["live"] = live
        matched = False
        for c in live:
            if hmac.compare_digest(_hash(c.salt, candidate), c.digest):
                matched = True
        if matched and shape_ok:
            _state["live"] = []
            return True
        for c in live:
            c.wrong += 1
        _state["live"] = [c for c in live if c.wrong < MAX_WRONG]
        return False
