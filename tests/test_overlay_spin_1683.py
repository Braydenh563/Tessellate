"""A thrown companion turns smoothly (INBOX 1683, owner: "its rotating when thrown and while it is falling is still
horrible"). Before: the drawn angle was one of 48 pictures 7.5 degrees apart, so at 60 ticks a second the picture was
held for 2 to 3 ticks (58 to 74 percent of ticks drew nothing new) and then jumped 7.5 or 15 degrees; a bounce swapped the
picture for the startled hop in mid-spin and reversed the rate in one tick. Now the engine hands the runner its true
angle every tick, the rate is capped at what 60 Hz can show (4.2 rad/s, 4 degrees a tick), comes from the throw and the
place the figure was held, and a contact pays its change out over a few ticks. Fixed clock throughout."""

from __future__ import annotations

import math

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import engine as eng  # noqa: E402
from tessellate.core.overlay import sprites  # noqa: E402
from tests.overlay_tumble_1670 import STEP, WIN, _release, make  # noqa: E402


def flight(speed: float, gait: str = "float", look: str = "masculine", angle: float = -0.6, at: tuple[float, float] = (900.0, 600.0), seed: int = 5) -> dict:
    """Release the figure at `speed` and read every tick of the flight: the angle drawn, and the picture name."""
    e, _s = make(look, gait, seed)
    e.big_ready = e.trip_ready = e.climb_ready = float("inf")
    e.set_windows([WIN], 0.0)
    t = _release(e, speed, angle, at)
    drawn: list[float] = []
    names: list[str] = []
    down: list[bool] = []
    for _ in range(60 * 12):
        t += STEP
        out = e.update(t)
        if e.state != "fly":
            break
        if out.angle is not None:
            drawn.append(math.degrees(out.angle))
            names.append(out.frame)
            down.append(e.grounded)
    steps = [abs((b - a + 180.0) % 360.0 - 180.0) for a, b in zip(drawn, drawn[1:])]
    # INBOX 1683 k: the flop onto its back or belly is a landing (tests/test_overlay_landing_1683k.py: no tick over 30
    # degrees); the smoothness asked of the flight is read on the ticks before it touches down
    air = [x for x, a, b in zip(steps, down, down[1:]) if not a and not b]
    return {"drawn": drawn, "names": names, "steps": steps, "air": air, "jerk": [abs(b - a) for a, b in zip(steps, steps[1:])], "engine": e}


@pytest.mark.parametrize("gait", ["float", "walk"])
@pytest.mark.parametrize("speed", [450.0, 900.0, 2500.0])
def test_a_thrown_figure_is_drawn_at_a_new_angle_every_tick_in_small_steps(gait: str, speed: float) -> None:
    f = flight(speed, gait)
    assert len(f["steps"]) > 60
    # measured (soft toss, throw, hard throw, 60 Hz): max step 2.2, 3.7, 3.9 degrees; before 7.5, 7.5, 15
    assert max(f["air"]) <= 4.5
    # no tick holds the angle: before, 58 to 74 percent of ticks repeated the last picture
    assert sum(1 for s in f["steps"] if s == 0.0) / len(f["steps"]) < 0.02


@pytest.mark.parametrize("speed", [450.0, 900.0, 2500.0])
def test_the_turn_changes_gently_from_tick_to_tick(speed: float) -> None:
    f = flight(speed)
    # before: the step itself jumped by 7.5 degrees between ticks
    assert max(f["jerk"]) <= 0.6


def test_a_soft_toss_turns_slowly() -> None:
    f = flight(450.0)
    assert max(f["steps"]) <= 2.5


def test_the_nearest_picture_still_names_the_frame_for_its_box() -> None:
    f = flight(900.0)
    for deg, name in zip(f["drawn"], f["names"]):
        near = round(deg / (360.0 / sprites.SPIN_STEPS)) % sprites.SPIN_STEPS
        assert name == f"spin{near}"


@pytest.mark.parametrize("side,sign", [(-1.0, -1), (1.0, 1)])
def test_where_the_figure_was_held_decides_which_way_it_turns(side: float, sign: int) -> None:
    """Held off-centre and thrown straight down, the hand pulls the near side down: held on the right it turns
    clockwise (positive), on the left anticlockwise."""
    e, _s = make("masculine", "float", 5)
    e.grab = (e.size[0] / 2 + side * e.size[0] * 0.4, e.size[1] / 2)
    omega = e._launch_spin(0.0, 1500.0, 0.0)
    assert omega * sign > 0.3


def test_a_drop_does_not_spin() -> None:
    e, _s = make("masculine", "float", 5)
    assert e._launch_spin(0.0, 0.0, 0.0) == 0.0


def test_the_rate_never_exceeds_what_sixty_hertz_can_show() -> None:
    assert eng.SPIN_OMEGA[1] / 60.0 * 180.0 / math.pi <= 4.1


def test_a_bounce_eases_the_rate_over_ticks_and_never_swaps_the_picture_in_a_spin() -> None:
    """Thrown hard at the left wall: the rate reverses, but no tick changes it by more than a fifth of the cap, and
    the figure is in a spin picture on every tick of the contact (before: the startled hop for 0.3 s mid-turn)."""
    e, _s = make("masculine", "float", 5)
    e.big_ready = e.trip_ready = e.climb_ready = float("inf")
    t = _release(e, 2400.0, math.pi, (300.0, 600.0))
    last, worst, frames = e.omega, 0.0, set()
    for _ in range(90):
        t += STEP
        out = e.update(t)
        if e.state != "fly":
            break
        worst = max(worst, abs(e.omega - last))
        last = e.omega
        frames.add(out.frame.rstrip("0123456789"))
    assert worst <= eng.SPIN_OMEGA[1] / 5
    assert frames == {"spin"}


def test_a_floater_settles_upright_and_ends_in_the_landing_squash() -> None:
    f = flight(900.0)
    e = f["engine"]
    assert e.state == "stand"
    lows = []
    t = e.now
    for _ in range(30):
        t += STEP
        out = e.update(t)
        lows.append(out.pose[1] if out.pose else 1.0)
    assert min(lows) < 0.97  # the squash (SQUASH is 0.1 of the height), and it is back by the end of the window
    assert lows[-1] > min(lows) + 0.03
    assert abs(math.remainder(e.angle, 2 * math.pi)) < 0.06  # upright when it lays down


def test_the_runner_draws_the_true_angle_not_the_nearest_picture() -> None:
    from tests.test_overlay_runner import make as make_runner

    r, _fake, clock, *_ = make_runner()
    assert r.start()
    out = eng.Output("spin3", 500, 400, False, 16, angle=math.radians(33.3))
    r.visible = True
    r._apply(out)
    want = r.sprites.spun_at(math.radians(33.3), r.dpi, False)
    assert r._target is not None and r._target.bgra == want.bgra
    other = eng.Output("spin3", 500, 400, False, 16, angle=math.radians(34.3))
    r._apply(other)
    assert r._target.bgra != want.bgra  # a degree is a new picture; before, 33.3 and 34.3 were both spin4
    r.stop()


def test_spun_at_is_on_the_canvas_of_the_spin_frames_and_keeps_only_a_few() -> None:
    s = sprites.SpriteSet("masculine")
    ref = s.frame("spin0", 96, False)
    for i in range(20):
        f = s.spun_at(math.radians(i * 7.7), 96, False)
        assert (f.width, f.height, f.pad_x, f.pad_y) == (ref.width, ref.height, ref.pad_x, ref.pad_y)
    assert len(s._spun_at) <= sprites.SPUN_KEEP
    assert s.spun_at(0.0, 96, False).bgra == s.spun_at(2 * math.pi, 96, False).bgra


@pytest.mark.parametrize("speed", [200.0, 900.0, 2200.0])
def test_the_figure_is_within_a_degree_of_upright_when_it_is_laid_down(speed: float) -> None:
    """Review of 1683: the stand frame is upright, so any angle left at the hand-over is a visible snap."""
    r = flight(speed)
    e = r["engine"]
    err = abs((math.degrees(e.angle) + 180.0) % 360.0 - 180.0)
    assert e.state != "fly" and err < 1.0, (e.state, err)
