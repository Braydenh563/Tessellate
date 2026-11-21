"""One fixed clock for a test (CLAUDE.md section 8: tests use a fixed clock, never the real one).

`user_now` and `utcnow` are imported by name into many modules (`from
tessellate.core.config import user_now`), so patching one module left the
others on the real clock: on 2026-11-21 a note dated "21 November" read as
today's and "the 16th" was in the past. `pin_clock` patches the roots and every
loaded module holding them, and `clock.today`, so one call covers the app: the
person's clock, the UTC clock, a row's own stamp (`database.stamp` reads
`utcnow` by name) and the calendar day. `tests/test_fixed_clock_lint.py` keeps
tests on it."""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import datetime, timezone

from tessellate.core import clock, config, database

#: The suite's fixed instant: a Saturday at noon UTC, the day `conftest.SUITE_DAY`
#: and `_frozen_clock.FIXED_NOW` use. A test that builds data relative to "now"
#: builds it from this and pins it, so nothing it asserts moves with the calendar.
SUITE_NOW = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
#: The same instant as this machine's naive wall time (what `datetime.now()` gave).
SUITE_LOCAL = SUITE_NOW.astimezone().replace(tzinfo=None)

_REAL_USER_NOW = config.user_now
_REAL_UTCNOW = database.utcnow


def pin_clock(monkeypatch, now: datetime | Callable[[], datetime]) -> None:  # noqa: ANN001
    """Every clock answers `now` (or `now()`, for a clock a test moves).

    A naive `now` is the person's wall time on this machine's zone; an aware
    one is an instant `user_now` reads in the person's zone. `utcnow` gives
    the same instant in UTC."""

    def moment() -> datetime:
        return now() if callable(now) else now

    def user(settings=None):  # noqa: ANN001, ANN202
        # A naive pin is the wall time itself; an aware one is an instant,
        # read in the person's zone as the real `user_now` reads it.
        at = moment()
        return at if at.tzinfo is None else config.on_users_clock(settings, at, at.tzinfo)

    def utc() -> datetime:
        return moment().astimezone(timezone.utc)

    user.pinned = utc.pinned = True  # type: ignore[attr-defined]

    monkeypatch.setattr(config, "user_now", user)
    monkeypatch.setattr(database, "utcnow", utc)
    monkeypatch.setattr(clock, "today", lambda: moment().date())
    # Every module, the tests' own too: a test that imported `utcnow` by name
    # and calls it reads the pinned clock like the app does.
    # A clock pinned earlier in the same test (an autouse fixture) is replaced.
    for module in list(sys.modules.values()):
        held = getattr(module, "__dict__", {})
        for attr, real, fake in (("user_now", _REAL_USER_NOW, user), ("utcnow", _REAL_UTCNOW, utc)):
            if held.get(attr) is real or getattr(held.get(attr), "pinned", False) is True:
                monkeypatch.setattr(module, attr, fake)


def unpin_late_imports() -> None:
    """Put the real clocks back on a module first imported while a clock was
    pinned (an app module, or a test file collected late): its `from ...
    import user_now` took the pinned function, which monkeypatch never set
    and so never undoes (`conftest._unpin_clock`)."""
    for module in list(sys.modules.values()):
        held = getattr(module, "__dict__", {})
        for attr, real in (("user_now", _REAL_USER_NOW), ("utcnow", _REAL_UTCNOW)):
            if getattr(held.get(attr), "pinned", False) is True:
                setattr(module, attr, real)
