"""The wind-spirit ride (E5, INBOX 1692 n; OPEN.md Tier E): a floater on its way rides a gust.

Motes and streaks stream behind it, a spiral of wind curls round it and unwinds after a turn, and a small eddy settles
at its feet where it comes down. The lean into the way it goes and the trailing wisp are the engine's own and stay (this
is drawn through `Output.prop`, never `Output.fx`, which switches them off). It adds no blink of its own: the engine's
blink at a turn keeps its least gap (`AMBIENT_EVERY`), and a figure under reduced motion, or a walker, gets nothing.

Pure of the clock and of chance: `Wind.view` is told the engine and `now`, and keeps only what it has seen (when a ride
began, which turn it has drawn, when it came down). The pictures are in `props.WIND_SPECS` and `props._gust`, `_spiral`
and `_eddy`.
"""

from __future__ import annotations

from typing import Any

from . import props

#: Motes a second (the phases a second of the gust: the streams already look six times a second).
GUST_FPS = props.WIND_SPECS["gust"].fps
SPIRAL_FPS = props.WIND_SPECS["spiral"].fps
EDDY_FPS = props.WIND_SPECS["eddy"].fps
#: How long the spiral turns after a turn begins, and how long the eddy lasts where it settles (seconds).
SPIRAL_FOR = 0.8
EDDY_FOR = 1.3
#: The share of full speed that is a ride (below it, the figure is easing in or out and the wind is still).
RIDE_PACE = 0.3
#: A ride this long (seconds of flying) is one that settles with an eddy; a hop of the heading does not.
MIN_RIDE = 0.6


def gust_phase(now: float) -> int:
    """The step of the motes at `now`."""
    return int(now * GUST_FPS) % props.WIND_SPECS["gust"].steps


def unwind(u: float) -> int:
    """The size (3 whole, 2, 1) a swirl takes `u` (0 to 1) through its life: it thins as it goes."""
    return 3 if u < 0.34 else 2 if u < 0.67 else 1


class Wind:
    """What one engine's ride has shown so far (one per `Extras`)."""

    def __init__(self) -> None:
        self.since: float | None = None  # when it began to fly this ride
        self.turn_seen = -1e9  # the `turn_started` of the turn the spiral was begun for
        self.turn_at: float | None = None
        self.eddy_at: float | None = None

    def _clear(self) -> None:
        self.since = self.turn_at = self.eddy_at = None

    def view(self, e: Any, now: float) -> tuple[str, int, int] | None:
        """`(name, phase, size)` of the wind to draw now, or None. A floater only, and never under reduced motion."""
        if e.reduced or getattr(e, "gait", "") != "float":
            self._clear()
            return None
        if e.state == "drift":
            self.eddy_at = None
            if self.since is None:
                self.since = now
            if e.turn_to and e.turn_started != self.turn_seen:
                self.turn_seen, self.turn_at = e.turn_started, now
            spiral = self._spiral(now)
            if spiral is not None:
                return spiral
            if e.pace_last >= RIDE_PACE:
                return "gust", gust_phase(now), 3
            return None
        if self.since is not None:
            if now - self.since >= MIN_RIDE:
                self.eddy_at = now
            self.since = None
        spiral = self._spiral(now)  # a turn at the very end still finishes
        if spiral is not None:
            return spiral
        if self.eddy_at is not None:
            age = now - self.eddy_at
            if 0.0 <= age < EDDY_FOR:
                return "eddy", int(age * EDDY_FPS) % props.WIND_SPECS["eddy"].steps, unwind(age / EDDY_FOR)
            self.eddy_at = None
        return None

    def _spiral(self, now: float) -> tuple[str, int, int] | None:
        if self.turn_at is None:
            return None
        age = now - self.turn_at
        if 0.0 <= age < SPIRAL_FOR:
            return "spiral", int(age * SPIRAL_FPS) % props.WIND_SPECS["spiral"].steps, unwind(age / SPIRAL_FOR)
        self.turn_at = None
        return None

    def next_step(self, now: float) -> float | None:
        """Seconds until the picture of a swirl next changes (a step, a size or its end), or None when none is on. The
        gust needs none: a flying figure is drawn at the walk's pace already."""
        marks = []
        for at, span, fps in ((self.turn_at, SPIRAL_FOR, SPIRAL_FPS), (self.eddy_at, EDDY_FOR, EDDY_FPS)):
            if at is None or not 0.0 <= now - at < span:
                continue
            age = now - at
            marks += [(int(age * fps) + 1) / fps - age, span - age]
            marks += [m * span - age for m in (0.34, 0.67) if m * span > age]
        return max(0.016, min(marks)) if marks else None
