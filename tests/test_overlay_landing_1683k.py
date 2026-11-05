"""A thrown desk companion lands by outcome, never a held tilt or a snap (INBOX 1683 k). The owner: "when I throw the
desktop companion and it rotates it doesnt perfectly land on its feet it often lands on its head and just stays at a 45
degree angle for a couple seconds before it instant resets, I want it to either land on its feet, land on its back or
stomach and like skid or smth or fall off, can it flail?? can it smack into the screen edge and slide down or
potentially go through it and come out the other side?? if it is skidding down a surface can it scrabble for purchase??"

Measured over 200 seeded throws per gait (tests/overlay_landing_1683k.py, fixed 60 Hz clock), walker, before to after:
all 200 on the feet to 70 feet, 64 belly, 13 back (the rest after a wall slide or pass through); the longest held tilt
1.57 s to 0.20 s; drawn-angle jumps over 30 degrees 2 to 0. A floater: tilt 0.78 s to 0.32 s, snaps 3 to 0. These
tests read single cases, forced, so each is quick."""

from __future__ import annotations

import math

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import engine as eng  # noqa: E402
from tessellate.core.overlay import landing as ld  # noqa: E402
from tests.overlay_tumble_1670 import STEP, make  # noqa: E402
from tests.test_overlay_ride_1670 import AREA  # noqa: E402


def dropped(angle: float, omega: float = 0.0, vx: float = 0.0, facing: int = 1, y: float = 600.0, seed: int = 3):
    """A walker let go at `y` tilted `angle`, falling straight (plus `vx`): the engine and the clock."""
    e, _s = make("masculine", "walk", seed)
    e.big_ready = e.trip_ready = e.climb_ready = math.inf
    e.x, e.y = 800.0, y
    e.update(1.0)
    e._start_fly(vx, 0.0)
    e.angle, e.omega, e.facing = angle, omega, facing
    return e, 1.0


def run(e, t: float, secs: float, until=None):
    """Tick `secs`; returns (t, [(angle drawn, frame)])"""
    seen = []
    for _ in range(int(secs / STEP)):
        t += STEP
        out = e.update(t)
        seen.append((out.angle, out.frame, e.state))
        if until and until(e):
            break
    return t, seen


def test_decide_feet_near_upright_and_down_past_forty_degrees() -> None:
    assert ld.decide(0.5, 0.0, 1)[0] == "feet"
    assert ld.decide(-0.69, 0.0, -1)[0] == "feet"
    # a quarter turn clockwise facing right is the belly, facing left the back; the mirror is the other
    assert ld.decide(1.5, 0.0, 1) == ("belly", ld.QUARTER)
    assert ld.decide(1.5, 0.0, -1) == ("back", ld.QUARTER)
    assert ld.decide(-1.5, 0.0, 1) == ("back", -ld.QUARTER)
    # head first it is not stable: it topples the way it was turning
    assert ld.decide(math.pi, 1.0, 1)[1] == ld.QUARTER
    assert ld.decide(math.pi, -1.0, 1)[1] == -ld.QUARTER


@pytest.mark.parametrize("angle", [1.4, -1.4, 2.8, -2.8, 3.1])
def test_a_body_that_lands_tilted_lies_down_skids_and_gets_up_without_a_snap(angle: float) -> None:
    e, t = dropped(angle, vx=900.0, y=800.0)
    x0 = e.x
    t, seen = run(e, t, 2.0, until=lambda en: en.lying)
    assert e.lying and e.outcome in ("belly", "back")
    assert abs(ld.wrap(e.angle - e.lie_goal)) < 0.1  # a quarter turn, not a held 45
    assert e.x - x0 > 30  # it skidded
    # lying on the floor, not above it: the drawn box rests on the work area's bottom
    bottom = e.y + e._ride_box(e._fly_frame())[3]
    assert AREA[3] - 3 <= bottom <= AREA[3] + 1, bottom
    t, seen2 = run(e, t, 4.0, until=lambda en: en.state != "fly")
    assert e.state in ("act", "stand", "land")  # got up and shook it off
    angles = [a for a, f, _s in seen + seen2 if a is not None]
    steps = [abs(ld.wrap(b - a)) for a, b in zip(angles, angles[1:])]
    assert max(steps) < math.radians(30)


def test_a_landing_near_upright_stays_on_the_feet() -> None:
    e, t = dropped(0.4, y=800.0)
    t, _seen = run(e, t, 4.0, until=lambda en: en.state != "fly")
    assert e.outcome == "feet" and e.lie_goal is None and not e.lying
    assert e.state in ("land", "stand")


def test_no_tilt_is_held_for_long_on_the_floor() -> None:
    """The owner's 45 degrees for a couple of seconds: a body 35 degrees over the feet rights itself in well under a second;
    one at 45 degrees goes down to a quarter turn (`test_a_body_that_lands_tilted...`), it does not hold the 45."""
    e, t = dropped(0.6, y=800.0)
    held, longest = 0.0, 0.0
    for _ in range(int(4.0 / STEP)):
        t += STEP
        e.update(t)
        if e.state != "fly":
            break
        held = held + STEP if e.grounded and abs(ld.wrap(e.angle)) > 0.17 and abs(e.omega) < 0.2 else 0.0
        longest = max(longest, held)
    assert longest < 0.2, longest


def test_a_hard_wall_smack_can_stick_and_slide_down_scrabbling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ld, "smack", lambda speed, scale, rng: "slide")
    e, t = dropped(0.0, vx=-2600.0, y=400.0)
    e.x = 300.0
    t, seen = run(e, t, 0.6, until=lambda en: en.wall != 0)
    assert e.wall == -1 and e.outcome == "slide" and e.vx == 0.0
    ux0 = e._ride_limits("fly")[0]
    wobbled, vys = 0.0, []
    for _ in range(60):
        t += STEP
        e.update(t)
        if e.grounded:
            break
        assert e.x == pytest.approx(ux0)
        wobbled = max(wobbled, abs(e.wob))
        vys.append(e.vy)
    assert wobbled > 0.04  # it scrabbles
    assert max(vys) <= ld.WALL_SLIDE * e._scale() + 1  # and slides at a crawl, not a fall
    t, _ = run(e, t, 6.0, until=lambda en: en.state != "fly")
    assert e.state != "fly" and e.wall == 0


def test_a_harder_smack_can_pass_through_and_come_out_the_other_side(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ld, "smack", lambda speed, scale, rng: "through")
    e, t = dropped(0.0, vx=-2600.0, y=300.0)
    e.x = 200.0
    t, _ = run(e, t, 0.6, until=lambda en: en.outcome == "through")
    assert e.outcome == "through" and e.vx < -1500  # still going the way it was
    assert e.x > AREA[2] - 400  # out of the right edge's side now


def test_a_soft_hit_and_a_floater_still_bounce(monkeypatch: pytest.MonkeyPatch) -> None:
    assert ld.smack(300.0, 1.0, __import__("random").Random(1)) == "bounce"
    monkeypatch.setattr(ld, "smack", lambda *_a: pytest.fail("a floater does not smack"))
    e, _s = make("masculine", "float", 3)
    e.x = 100.0
    e.update(1.0)
    e._start_fly(-2500.0, 0.0)
    t, _ = run(e, 1.0, 0.5)
    assert e.wall == 0 and e.vx > 0


def test_a_long_drop_flails_gently() -> None:
    e, t = dropped(0.0, y=40.0)
    e.omega = 0.0
    wobbles, drawn = [], []
    for _ in range(int(0.9 / STEP)):
        t += STEP
        out = e.update(t)
        if e.grounded:
            break
        wobbles.append(e.wob)
        if out.angle is not None:
            drawn.append(out.angle)
    assert max(abs(w) for w in wobbles) > 0.05
    assert max(abs(ld.wrap(b - a)) for a, b in zip(drawn, drawn[1:])) < math.radians(4.5)


def test_a_tumbling_body_cannot_take_hold_of_the_ceiling() -> None:
    """Taking hold zeroes the angle: from head over heels that was a snap of up to 180 degrees."""
    e, t = dropped(2.5, vx=0.0, y=300.0)
    e.vy = -2200.0
    e.launch = (0.0, -2200.0)
    t, _ = run(e, t, 0.5)
    assert e.state != "hang"
    e2, t2 = dropped(0.1, vx=0.0, y=300.0)
    e2.vy = -2200.0
    e2.launch = (0.0, -2200.0)
    t2, _ = run(e2, t2, 0.8, until=lambda en: en.state in ("hang", "rise"))
    assert e2.state in ("hang", "rise")


def test_the_ceiling_and_wall_constants_are_not_loosened() -> None:
    assert eng.CEIL_TILT < math.radians(30)
