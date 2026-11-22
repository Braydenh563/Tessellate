"""INBOX 1670, 17:05Z: "the way that the desktop companion rotates in the air is not realistic at all, it like
rotates by 45 degrees each time and at 1 second intervals". The tumble was eight pictures 45 degrees apart,
turned at a rate that followed the flight's current speed, so as a throw slowed each picture stood for most of a
second. Now the angle is continuous (48 pictures of 7.5 degrees, built when first needed), the turn rate is set at
the release and fades by its own drag, a contact changes it, and the figure rights itself with an eased turn.
Measured on the engine and its fakes with a fixed clock (`tests/overlay_tumble_1670.py`); nothing here ran on
Windows.

Before (same measurement, 12 throws, floater and walker, 500 to 3000 px/s, straight and curled): the picture
changed by 45 degrees every time (135 and 180 for a fast walker), and one picture stood up to 0.86 s."""

from __future__ import annotations

import math

import pytest

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import sprites
from tests.overlay_tumble_1670 import _release, tumble
from tests.test_overlay_ride_1670 import make

RUNS = [(g, v, c) for g in ("float", "walk") for v in (500, 1500, 3000) for c in (0.0, 0.25)]


def test_the_tumble_is_forty_eight_steps_in_both_modules() -> None:
    assert eng.SPIN_STEPS == sprites.SPIN_STEPS == 48


@pytest.mark.parametrize("gait,speed,curl", RUNS)
def test_no_step_over_fifteen_degrees_and_a_frame_a_display_tick(gait: str, speed: int, curl: float) -> None:
    m = tumble(gait, speed=speed, curl=curl)
    print(gait, speed, curl, m)
    assert m["ticks"] > 20, m
    assert m["turn"] <= 15.0, m  # was 45 every time
    assert 13 <= m["wake_min"] and m["wake_max"] <= 20, m  # 16.7 ms plus or minus 3


@pytest.mark.parametrize("gait,speed,curl", RUNS)
def test_the_turn_rate_is_continuous_and_ends_upright(gait: str, speed: int, curl: float) -> None:
    m = tumble(gait, speed=speed, curl=curl)
    # no tick changes the rate by more than 30 percent of max(the rate, 2 rad/s), a contact aside (a bounce
    # shows the startled frame, the rate is allowed to change there; the righting spring is ramped in)
    assert m["jump"] <= 0.30, m
    assert m["state_end"] in ("stand", "land", "act"), m  # laid down upright (a fall onto its back ends in a shake-off act), never left tilted


@pytest.mark.parametrize("gait", ["float", "walk"])
def test_the_turn_rate_is_set_at_the_release_not_by_the_flight_speed(gait: str) -> None:
    slow, hard = {}, {}
    for into, speed in ((slow, 500.0), (hard, 3000.0)):
        e, _s = make("masculine", gait, 5)
        e.big_ready = e.trip_ready = e.climb_ready = math.inf
        t = _release(e, speed, -0.2, (900.0, 600.0))
        into["start"] = abs(e.omega)
        e.vx, e.vy = 0.0, 0.0  # the flight stopped dead: the old rule stopped the spin with it
        for _ in range(10):
            t += 1 / 60
            e.update(t)
        into["after"] = abs(e.omega)
    assert hard["start"] > slow["start"] > 0.0  # a harder throw turns faster
    assert 0.8 * hard["start"] * math.exp(-eng.SPIN_DRAG * 10 / 60) <= hard["after"] <= hard["start"]  # its own drag only


def test_a_curling_throw_turns_against_a_straight_one_the_other_way() -> None:
    def omega(curl: float) -> float:
        e, _s = make("masculine", "float", 5)
        e.big_ready = e.trip_ready = e.climb_ready = math.inf
        _release(e, 1000.0, 0.0, (900.0, 600.0), curl)
        return e.omega

    assert omega(0.0) > 0 and omega(-0.4) < omega(0.0)  # a counter-clockwise curl takes from it
    # Re-registered (L150): at 0.4 rad a step the six steps turn the path 2.4 rad, so the throw ends leftward and its
    # sign flips (0.4 gave 2.83 against 2.87 straight on the new 145 px figure; 0.2 gives 3.22), so the clockwise curl
    # is the gentle one that is still a rightward throw.
    assert omega(0.2) > omega(0.0)  # a clockwise curl adds to a rightward throw's turn


def test_a_wall_bounce_changes_the_turn_and_a_slow_flight_rights_itself_eased() -> None:
    e, _s = make("masculine", "float", 5)
    e.omega, e.angle = 8.0, 1.0
    e._spin_contact(1.0)
    # intent kept, how it happens moved (INBOX 1683): the reversal is paid out over a few ticks, not taken in one
    for _ in range(90):
        e._spin(1 / 60, 1000.0)
    assert e.omega < 0, "a bounce reverses it"
    e.angle = 1.0
    e.omega, e.angle, e.right_t = 0.0, math.pi * 0.9, 0.0  # nearly upside down, the flight slow
    path, t = [], 0.0
    for _ in range(300):
        e._spin(1 / 60, 0.0)
        path.append(e.angle)
        t += 1 / 60
    steps = [abs(b - a) for a, b in zip(path, path[1:])]
    assert max(steps) * 180 / math.pi <= 4.0, "an eased turn: never a snap"
    assert e._righted() and abs(path[-1] - 2 * math.pi) < 0.1 or abs(path[-1]) < 0.1
