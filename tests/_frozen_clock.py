"""A fixed "now" for the reminder tests, injected through the modules' own seams.

Both the reminder routes and the notifier read the app's one UTC clock
(`database.utcnow`), so `pin_clock` pins them with everything else.
"""

from __future__ import annotations

from datetime import datetime, timezone

#: A Saturday at noon UTC; deliberately not the real date, so a test that still
#: reads the real clock disagrees with it and fails loudly.
FIXED_NOW = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


def freeze_reminder_clock(monkeypatch, *, notifier: bool = False) -> datetime:  # noqa: ARG001
    """The suite's one pinned clock at FIXED_NOW (`tests/_clock.pin_clock`): the
    reminder routes read `utcnow` and the notifier reads it through `_utcnow`,
    so one pin covers both (`notifier` is kept for the callers that name it)."""
    from tests._clock import pin_clock

    pin_clock(monkeypatch, FIXED_NOW)
    return FIXED_NOW
