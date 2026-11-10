"""Which sessions have opened the private spaces, and for how long (INBOX 1727).

A private space's contents are sealed under the vault key, as a private note
is. This is the second door: even a session holding the key sees nothing of a
private space until it unlocks them with the vault password or the PIN, and
the door shuts again after `idle_minutes` without the person's own input
(the window reports it, `/private-spaces/touch`; the app's own polls do not
count), on lock, and when the window closes. One door for every private space (one vault
password, the owner's answer).

In memory only, like the key: a restart closes every private space.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

#: The owner's answer: ten minutes idle, changeable in Settings.
DEFAULT_IDLE_MINUTES = 10
#: The preference that changes it (Settings, Privacy).
PREFERENCE = "private_space_idle_minutes"

_lock = threading.Lock()
#: Session token to the time it last used them. A request without a token never
#: opens them: one shared "" slot let every tokenless caller in after one opened it
#: (review 5850946759).
_opened: dict[str, float] = {}


#: Where the preference is read from. core/deps.py sets it to its own
#: `get_config`: this module does not import deps, which imports it (a cycle).
config_source: Callable[[], Any] = lambda: None  # noqa: E731  # no config yet: the default


def _now() -> float:
    """Monotonic seconds; a test replaces this to step past the idle window."""
    return time.monotonic()


def idle_minutes() -> int:
    """The preference, clamped to 1..240 minutes."""
    try:
        value = int(config_source().get_preference(PREFERENCE, DEFAULT_IDLE_MINUTES))
    except Exception:  # noqa: BLE001  # no config yet: the default
        value = DEFAULT_IDLE_MINUTES
    return max(1, min(240, value))


def open_for(token: str | None) -> None:
    """This session proved the vault password or the PIN. Stale sessions are
    dropped here too, so the table does not grow with old tokens."""
    if not token:
        return
    now = _now()
    window = idle_minutes() * 60
    with _lock:
        for old in [k for k, seen in _opened.items() if now - seen > window]:
            _opened.pop(old, None)
        _opened[token] = now


def is_open(token: str | None, *, touch: bool = True) -> bool:
    """Whether this session may see the private spaces now. A use within the
    idle window keeps them open (`touch`); one after it closes them."""
    if not token:
        return False
    key = token
    with _lock:
        seen = _opened.get(key)
        if seen is None:
            return False
        now = _now()
        if now - seen > idle_minutes() * 60:
            _opened.pop(key, None)
            return False
        if touch:
            _opened[key] = now
        return True


def opened(token: str | None) -> bool:
    """Whether this session may read the private spaces now: the vault key is
    loaded and it opened them within the idle minutes. Never touches."""
    from tessellate.core import vault

    return vault.key() is not None and is_open(token, touch=False)


def close_for(token: str | None) -> None:
    with _lock:
        _opened.pop(token or "", None)


def close_all() -> None:
    """Lock, a password change, a restore: every private space shuts."""
    with _lock:
        _opened.clear()
