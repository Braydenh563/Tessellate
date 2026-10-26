# battery-1025 remaining (INBOX 1351)

Done: 8302eb2 lan-watch waits on the change + hidden pause; d7803a2 perch check armed timer + idle marks; third commit note-changes backoff.

Measured (scratchpad/ui-sweeps/battery.js, untracked; 120 s idle, no model, port 8816): visible requests 22 to 20, timer fires 104 to 37, server CPU 0.64 to 0.49 s; hidden requests 8 to 3, timer fires 90 to 10, CPU 0.52 to 0.38 s; rAF frames 0 both.

Next (not done):
- `/reminders` poll still runs hidden (status.js:609, REMINDER_POLL_MS 60 s); a hidden tab could skip it (visibilitychange already rechecks) unless browser notifications need it.
- `/models/status` still asked once per 2 min hidden and doubles to ceiling visible (status.js:1865); skip when no provider is configured and Ollama is absent only if a "start it" path exists.
- Remaining 60 s intervals: atlas mood (atlas.js:3737), reminders (status.js:609); atlasDrift 35 s timers.
- Server: `core/lanserve.py` / `lanlive.py` CHECK_SECONDS wake and `reminder_notifier` sleeps were read, not profiled.
- is-idle only freezes emblem marks; the bg-art layer and the dashboard art have their own pause (bg-art.js:2145), not tied to idle.
