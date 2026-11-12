"""INBOX 1670, 15:45Z: "nearly every time I throw it no matter how hard, it goes to the top to hang from the top
edge". A thrown floater has no gravity (air drag and a pull to its hover), so any upward part of a throw reached
the ceiling, and the ceiling took hold on any contact. Now the ceiling holds a throw only when it arrives hard and
mostly upward; any other bounces off the top like a side wall and drifts back. A release that is not a throw
(slow, within reach of the top or a title bar) still hangs.

Measured with `tests/overlay_throws_1670.py` (a seeded spread: uniform angle, speed from `THROW_MIN` to
`THROW_MAX`, a release spot across the screen, 200 throws, masculine look; the look does not change a throw):
the share that ended hanging, before and after, was 15.5 to 2.0 percent for a floater and 26.5 to 7.0 for a
walker (a floater is pulled back to its hover, a walker by gravity, so only a hard throw from high up reaches the top). Nothing here runs on Windows."""

from __future__ import annotations

import math

import pytest

from tessellate.core.overlay import engine as eng
from tests.overlay_throws_1670 import spread, throw_once
from tests.test_overlay_ride_1670 import AREA, make

UP = -math.pi / 2


@pytest.mark.parametrize("gait", ["float", "walk"])
def test_a_uniform_spread_of_throws_rarely_ends_hanging(gait: str) -> None:
    got = spread(gait, count=60)
    assert got["hang_share"] < 0.15, got
    # and what hangs is the hard upward throw, never the sideways or downward ones
    assert got["up_hang"] >= got["hang_share"] * got["n"], got


@pytest.mark.parametrize("gait", ["float", "walk"])
def test_a_hard_throw_straight_up_still_hangs_from_the_top(gait: str) -> None:
    # INBOX 1719 (a): past `CEIL_LEAVE` it leaves through the top instead (tests/test_overlay_throw_leave_1719.py), so the
    # hang is the hard throw between the two lines.
    assert throw_once(gait, "masculine", 1, UP, eng.CEIL_LEAVE * 0.95, (900, 300)) == "hang"


@pytest.mark.parametrize("gait", ["float", "walk"])
@pytest.mark.parametrize("speed", [eng.THROW_MIN * 1.2, 700.0, 1000.0])
def test_a_gentle_or_middling_throw_up_to_the_top_bounces_and_does_not_hang(gait: str, speed: float) -> None:
    # released close under the top, so the ceiling is reached even by a gentle throw
    assert throw_once(gait, "masculine", 1, UP, speed, (900, 160)) == "floor"


@pytest.mark.parametrize("gait", ["float", "walk"])
@pytest.mark.parametrize("angle", [0.0, math.pi, math.pi / 2, -math.pi / 6, -5 * math.pi / 6])
def test_a_fast_throw_that_is_not_mostly_upward_does_not_hang(gait: str, angle: float) -> None:
    # sideways, down, and up at 30 degrees off level: none is "mostly upward"
    assert throw_once(gait, "masculine", 1, angle, eng.THROW_MAX, (900, 300)) == "floor"


def test_a_slow_release_near_the_top_still_hangs() -> None:
    e, _s = make("masculine", "float", 2)
    e.set_windows([], 0.0)
    sx, sy = int(e.x + e.size[0] / 2), int(e.y + e.size[1] / 2)
    t = 1.0
    e.update(t, (sx, sy), ("down", sx, sy))
    for i in range(1, 21):  # carried to the top, then a pause: no throw
        t += 0.016
        e.update(t, event=("move", sx, round(sy + (AREA[1] + 20 - sy) * i / 20)))
    for _ in range(10):
        t += 0.05
        e.update(t, event=("move", sx, AREA[1] + 20))
    e.update(t + 0.016, event=("up", sx, AREA[1] + 20))
    for _ in range(300):
        t += 0.016
        e.update(t)
        if e.state == "hang":
            break
    assert e.state == "hang"


def test_a_throw_is_never_a_release_grab() -> None:
    """A fast throw let go with the head right under the top is thrown (and bounced), not grabbed on the spot."""
    e, _s = make("masculine", "float", 2)
    e.set_windows([], 0.0)
    sx, sy = 900, 90
    e.x, e.y = sx - e.size[0] / 2, sy - e.size[1] / 2
    e.update(1.0)
    t = 1.0
    e.update(t, (sx, sy), ("down", sx, sy))
    for i in range(1, 7):
        t += 1.0 / 60.0
        e.update(t, event=("move", sx + i * 30, sy))  # 1,800 px/s sideways
    e.update(t + 1.0 / 60.0, event=("up", sx + 7 * 30, sy))
    assert e.state == "fly"
