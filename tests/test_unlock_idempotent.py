"""An unlock does not stack another reminder poll (audit 2026-10-05, FE-08).

Every unlock (and any 401 that routes through the lock screen) runs
`startApp()` again, whose `startReminderWatch` added a one-minute interval
and two listeners each time: after four lock and unlock cycles an idle minute
asked `/reminders` five times. The browser half is
`scratchpad/ui-sweeps/fe1005-lockleak.js`; this holds the guard.
"""

from __future__ import annotations

from pathlib import Path

STATUS = Path(__file__).resolve().parents[1] / "frontend" / "js" / "status.js"


def test_the_reminder_watch_is_wired_once():
    text = STATUS.read_text(encoding="utf-8")
    start = text.index("function startReminderWatch(")
    body = text[start : text.index("\n}\n", start)]
    guard = body.index("if (reminderWatchStarted) return;")
    assert guard < body.index("startMinuteTicker(")  # the shared minute tick (S38), once an interval
    assert guard < body.index('addEventListener("focus"')
    assert guard < body.index('addEventListener("visibilitychange"')
    # An unlock still checks at once: the guard comes after the first check.
    assert body.index("checkDueReminders();") < guard
