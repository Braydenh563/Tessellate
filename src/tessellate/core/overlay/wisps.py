"""Where the body is in its breath, for the lower body (INBOX 1683 a, 1696 w: "organic or natural subtle movement with the
lower body wisps and the nebula streams"). The in-app hem and streams rise and settle with the torso's swell; on the desk the
wisps are a warp of the shipped frame, so `behaviour.Flow.view` takes the breath's phase (0 to 1, 0.5 the fullest chest) and
lifts each strand a beat after the chest, the wave running outward. This reads the engine's own clocks and changes none of
them: no extra wake, no extra picture (the flow view is already redrawn at rest every `FLOW_TICK_MS`)."""

from __future__ import annotations

import math


def phase(state: str, frame: str, now: float, rest_period: float | None, idle_frames: int, drift_s: float) -> float | None:
    """The breath phase of the figure at `now`, or None where the pose carries no breath (walking, thrown, held).

    A sit or a sleep breathes on `rest_period` (the engine's `_rest_life()[0]`), the same clock as its swell
    `(1 - cos(2 pi t / period)) / 2`; a stand's breath is baked in its idle cycle, so the picture's index is the phase; a
    drifting floater breathes on `drift_s`."""
    if rest_period:
        return (now / rest_period) % 1.0
    if state == "stand" and frame.startswith("idle") and idle_frames > 0 and frame[4:].isdigit():
        return int(frame[4:]) / idle_frames
    if state == "drift":
        return (now / drift_s) % 1.0
    return None


def lift(breath: float, delay: float) -> float:
    """The strand's rise, -1 (lifted, a beat after the fullest chest) to 1 (settled), `delay` of a cycle late."""
    return math.cos(math.tau * (breath - 0.5 - delay)) * -1.0
