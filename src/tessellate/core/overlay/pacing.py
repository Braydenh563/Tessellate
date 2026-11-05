"""When the host next wakes the engine while the figure moves (INBOX 1670, 14:14Z: "very framey").

`SetTimer` fires on the system tick, 15.625 ms, so the engine's 33 ms ask came out as 31 or 47 ms:
the same walk speed drawn in steps of 1.7 and 2.6 px, alternating. A moving figure is instead woken
on a fixed 60 Hz grid, one deadline per display frame; the host waits for each with the lightest
thing the platform has (Windows: a high-resolution waitable timer, a kernel timer that costs nothing
between deadlines and holds about half a millisecond; Linux: the `select` timeout, already in ms).
`DwmFlush` would lock to the real refresh but blocks the message thread and returns at once where the
compositor is off (a remote session), which turns it into a busy loop; `timeBeginPeriod(1)` raises the
whole machine's tick for as long as it is held. Pure here: no clock of its own, so tests drive it.

The grid is anchored at the first paced wake and kept, so a late tick shifts nothing after it; a
tick that ran long skips the missed lines instead of firing a burst to catch up. A wake longer than
`PACED_AT_MS` (a resting figure) is not paced: it is the engine's own time, as before."""

from __future__ import annotations

import math

FRAME_S = 1.0 / 60.0
#: An ask from `PACED_FROM_MS` to `NEXT_FRAME_MS` is "the next frame" (the engine's move tick is 16 ms);
#: shorter is "now" (the runner's wake of 1 ms after a show). An ask up to `PACED_AT_MS` is an animation's own
#: step (a tail settling, a pose easing, a hang's swing, an act): it also lands on a grid line, the first at or
#: after its time (INBOX 1683: on `SetTimer` these came out as 31 or 47 ms and 62 ms, mean 60 ms, p95 109 ms, std 25 ms,
#: the wisps and the tail at about 16 frames a second and uneven). Longer is a rest's slow ask and keeps `SetTimer`.
PACED_FROM_MS = 12
NEXT_FRAME_MS = 20
PACED_AT_MS = 100
#: A deadline closer than this to now waits for the line after: the tick that just ran is not a frame early.
GUARD_S = 0.004


class Pacer:
    def __init__(self, period: float = FRAME_S) -> None:
        self.period = period
        self.anchor: float | None = None

    def paced(self, wake_ms: int) -> bool:
        return PACED_FROM_MS <= int(wake_ms) <= PACED_AT_MS

    def reset(self) -> None:
        self.anchor = None

    def next(self, now: float, wake_ms: int) -> float:
        """The time (the caller's monotonic seconds) to wake at: a grid line for a paced ask, now plus the ask otherwise."""
        if not self.paced(wake_ms):
            self.anchor = None
            return now + max(0, int(wake_ms)) / 1000.0
        if self.anchor is None:
            self.anchor = now
        if int(wake_ms) <= NEXT_FRAME_MS:
            lines = int((now + GUARD_S - self.anchor) // self.period) + 1
        else:  # the first line at or after the ask (a millisecond of slack so 33 ms is two lines, not three)
            lines = max(1, math.ceil((now + int(wake_ms) / 1000.0 - 0.001 - self.anchor) / self.period))
        return self.anchor + lines * self.period
