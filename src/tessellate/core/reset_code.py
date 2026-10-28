"""The six-digit code that stands in for a password at "I don't have it" (INBOX 1424, audit 1028 K1).

`POST /auth/reset` once took only a typed word, so any program on this
computer could seal every private note. Now the reset is requested first: the
server makes a code and prints it to its own terminal, where only someone who
can see this computer's server output can read it. The request answer never
carries it, and it is not written to the log buffer Settings, Logs shows (a
locked notebook has no one to open that page, and an unlocked one on the
network could read it).

One code is live at a time; asking again replaces it. It lasts ten minutes,
is stored only as a keyed hash, is compared in constant time, dies on first
success, and dies after five wrong tries (the login throttle counts the same
tries, so asking for a fresh code does not reset the guessing).
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

_lock = threading.Lock()
#: Replaced by tests with a fixed clock; never read the wall clock directly.
_now = time.time


@dataclass
class _Live:
    salt: bytes
    digest: bytes
    expires: float
    wrong: int = 0


_live: _Live | None = None


def _hash(salt: bytes, code: str) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), salt, 100_000)


def _forget() -> None:
    global _live
    _live = None


register_cache_reset(_forget)


def issue() -> int:
    """Make a code, print it to the terminal, keep only its hash. Returns the lifetime in seconds."""
    global _live
    code = f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"
    salt = secrets.token_bytes(16)
    with _lock:
        _live = _Live(salt=salt, digest=_hash(salt, code), expires=_now() + TTL_SECONDS)
    print(  # noqa: T201  # the terminal is the point: only whoever sees this computer's server output may read the code
        f"\nTessellate password reset code: {code}\n"
        f"It works for {TTL_SECONDS // 60} minutes. If you did not ask for it, ignore it.\n",
        file=sys.stderr,
        flush=True,
    )
    return TTL_SECONDS


def check(typed: str) -> bool:
    """True once, for the live code. Wrong tries are counted; the fifth kills the code."""
    global _live
    shape_ok = isinstance(typed, str) and len(typed.strip()) == CODE_DIGITS and typed.strip().isascii() and typed.strip().isdigit()
    candidate = typed.strip() if shape_ok else "-" * CODE_DIGITS
    with _lock:
        live = _live
        if live is None:
            return False
        if _now() >= live.expires:
            _live = None
            return False
        ok = hmac.compare_digest(_hash(live.salt, candidate), live.digest) and shape_ok
        if ok:
            _live = None
            return True
        live.wrong += 1
        if live.wrong >= MAX_WRONG:
            _live = None
        return False
