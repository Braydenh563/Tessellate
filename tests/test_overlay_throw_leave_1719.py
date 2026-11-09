"""INBOX 1719 (a): a throw past `CEIL_LEAVE` leaves through the top (the top side open), stays out of view for a time
that grows with the launch speed (`AWAY_FOR`, capped), then falls back in near where it left and lands. Below the
line the ceiling hang or bounce is unchanged. A seeded sweep on the engine and its fakes with a fixed clock; not real
Windows."""

from __future__ import annotations

import math

import pytest

from tessellate.core.overlay import engine as eng
from tests.overlay_throws_1670 import STEP
from tests.test_overlay_ride_1670 import AREA, WIN, make

UP = -math.pi / 2


def throw_up(gait: str, seed: int, speed: float, at=(900, 300)) -> dict:
    e, _s = make("masculine", gait, seed)
    e.big_ready = e.trip_ready = e.climb_ready = float("inf")
    e.set_windows([WIN], 0.0)
    w, h = e.size
    px, py = min(max(at[0], AREA[0] + w / 2), AREA[2] - w / 2), min(max(at[1], AREA[1] + h / 2), AREA[3] - h / 2)
    n, t = 6, 1.0
    e.x, e.y = px - w / 2, py - h / 2 - UP * 0 + speed * STEP * n
    e.y = min(max(e.y, AREA[1]), AREA[3] - h)
    e.update(t)
    sx, sy = int(e.x + w / 2), int(e.y + h / 2)
    e.update(t, (sx, sy), ("down", sx, sy))
    for i in range(1, n + 1):
        t += STEP
        e.update(t, event=("move", sx, round(sy - speed * STEP * i)))
    t += STEP
    e.update(t, event=("up", sx, round(sy - speed * STEP * (n + 1))))
    t0, away, back_x, left_x, ended, hung = t, 0.0, None, None, None, False
    while t < t0 + 40.0:
        t += 0.016
        out = e.update(t)
        if e.away_until is not None:
            away += 0.016
            left_x = e.x
            assert out.alpha == 0.0
        elif away and back_x is None:
            back_x = e.x
        hung = hung or e.state == "hang"
        if away and e.away_until is None and e.state in ("stand", "sit", "sleep", "land") and e.vx == e.vy == 0:
            ended = e.state
            break
    return {"away": away, "left_x": left_x, "back_x": back_x, "ended": ended, "hung": hung, "e": e}


@pytest.mark.parametrize("gait", ["float", "walk"])
def test_time_away_grows_with_speed_and_is_capped(gait: str) -> None:
    speeds = [eng.CEIL_LEAVE + (eng.THROW_MAX - eng.CEIL_LEAVE) * f / 4 for f in range(5)]
    aways = [throw_up(gait, 3, v)["away"] for v in speeds]
    assert all(a > 0 for a in aways), aways
    assert aways == sorted(aways) and aways[-1] > aways[0] + 1.0, aways
    assert aways[0] >= eng.AWAY_FOR[0] - 0.1 and aways[-1] <= eng.AWAY_FOR[1] + 0.1, aways


@pytest.mark.parametrize("gait", ["float", "walk"])
@pytest.mark.parametrize("seed", range(6))
def test_it_comes_back_near_where_it_left_and_lands(gait: str, seed: int) -> None:
    got = throw_up(gait, seed, eng.THROW_MAX)
    assert got["ended"] in ("stand", "sit", "sleep", "land"), got["ended"]
    assert abs(got["back_x"] - got["left_x"]) < eng.AWAY_DRIFT * got["e"].size[0] + 40
    e = got["e"]
    assert AREA[0] - 1 <= e.x <= AREA[2] - e.size[0] + 1 and e.y <= AREA[3]


def test_deterministic_per_seed() -> None:
    a, b = throw_up("float", 4, 3000.0), throw_up("float", 4, 3000.0)
    assert (a["away"], a["back_x"], a["ended"]) == (b["away"], b["back_x"], b["ended"])


@pytest.mark.parametrize("gait", ["float", "walk"])
def test_below_the_line_nothing_changes(gait: str) -> None:
    got = throw_up(gait, 1, eng.CEIL_CATCH * 1.05)
    assert got["away"] == 0.0
    got = throw_up(gait, 1, 1000.0, at=(900, 160))
    assert got["away"] == 0.0 and not got["hung"]
