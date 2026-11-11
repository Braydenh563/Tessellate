"""A landing on the feet resolves to one of three touches by how hard it came down (E6, INBOX 1683 k and x): soft, a
stumble or a roll. Speed and height are one number (v squared is twice g times the drop). Fixed 60 Hz clock, seeded."""

from __future__ import annotations

import math

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import engine_consts as eng  # noqa: E402
from tessellate.core.overlay import landing as ld  # noqa: E402
from tests.overlay_tumble_1670 import STEP, make  # noqa: E402

TAU = 2 * math.pi


def dropped_from(height: float, vx: float = 0.0, seed: int = 3):
    """A walker upright at `height` px above its floor, let go with a sideways `vx`."""
    e, _s = make("masculine", "walk", seed)
    e.big_ready = e.trip_ready = e.climb_ready = math.inf
    e.update(1.0)
    floor = e.floor_y(e.current_monitor())
    e.x, e.y = 800.0, floor - height
    e.update(1.0)
    e._start_fly(vx, 0.0)
    e.angle, e.omega = 0.0, 0.0
    return e, 1.0


def play(e, t: float, secs: float = 6.0):
    """Tick until the figure stands; returns (t, rows of (angle drawn, x, sy of the pose, state))."""
    rows, seen_land = [], False
    for _ in range(int(secs / STEP)):
        t += STEP
        out = e.update(t)
        sy = out.pose[1] if out.pose else 1.0
        rows.append((out.angle if out.angle is not None else 0.0, e.x, sy, e.state))
        seen_land = seen_land or e.state == "land"
        if seen_land and e.state != "land":
            break
    return t, rows


def kind_of(e) -> str:
    return e.touched[0] if e.touched else "none"


def test_the_touch_is_set_by_the_speed_it_comes_down_at() -> None:
    assert ld.touch(ld.SOFT_SPEED - 1, 1.0) == "soft"
    assert ld.touch(ld.SOFT_SPEED + 1, 1.0) == "stumble"
    assert ld.touch(ld.ROLL_SPEED - 1, 1.0) == "stumble"
    assert ld.touch(ld.ROLL_SPEED + 1, 1.0) == "roll"
    # the lines scale with the display: at 2x a fall twice as fast is the same drop
    assert ld.touch(ld.SOFT_SPEED * 2 - 1, 2.0) == "soft"
    assert ld.touch(ld.ROLL_SPEED * 2 + 1, 2.0) == "roll"


def test_the_lines_are_drops_of_about_two_hundred_and_five_hundred_px() -> None:
    def drop(v: float) -> float:
        return v * v / (2 * eng.GRAVITY)

    assert 150 <= drop(ld.SOFT_SPEED) <= 230 and 450 <= drop(ld.ROLL_SPEED) <= 600


@pytest.mark.parametrize(("height", "kind"), [(60, "soft"), (400, "stumble"), (900, "roll")])
def test_a_drop_lands_by_its_height(height: float, kind: str) -> None:
    e, t = dropped_from(height)
    play(e, t)
    assert kind_of(e) == kind, e.touched
    assert e.outcome == "feet"


def test_a_harder_touch_squashes_deeper_and_a_soft_one_barely() -> None:
    depth = {}
    for kind, h in (("soft", 60), ("stumble", 400)):
        e, t = dropped_from(h)
        _t, rows = play(e, t)
        depth[kind] = 1.0 - min(r[2] for r in rows if r[3] == "land")
    assert 0.0 < depth["soft"] < depth["stumble"] <= 0.2, depth


def test_a_stumble_shuffles_on_the_way_it_was_going() -> None:
    e, t = dropped_from(400, vx=120.0)
    x0 = e.x
    play(e, t)
    assert e.x > x0 + 5.0


def test_a_roll_turns_once_forward_at_a_rate_the_eye_can_follow_and_ends_upright() -> None:
    e, t = dropped_from(900, vx=200.0)
    _t, rows = play(e, t)
    angles = [r[0] for r in rows if r[3] in ("fly", "land", "stand")]
    steps = [ld.wrap(b - a) for a, b in zip(angles, angles[1:], strict=False)]
    turned = sum(s for s in steps if abs(s) < 1.0)
    assert 0.85 * TAU <= turned <= 1.15 * TAU, math.degrees(turned)  # one full turn, clockwise (forward right)
    assert max(abs(s) for s in steps) <= math.radians(10.5), math.degrees(max(abs(s) for s in steps))
    assert abs(ld.wrap(angles[-1])) < 0.05 and e.state in ("land", "stand")
    assert e.x > 800.0, "it rolls on the way it was going"


def test_a_roll_the_other_way_turns_the_other_way() -> None:
    e, t = dropped_from(900, vx=-200.0)
    _t, rows = play(e, t)
    angles = [r[0] for r in rows if r[3] in ("fly", "land", "stand")]
    turned = sum(s for s in (ld.wrap(b - a) for a, b in zip(angles, angles[1:], strict=False)) if abs(s) < 1.0)
    assert -1.15 * TAU <= turned <= -0.85 * TAU, math.degrees(turned)


def test_a_seeded_sweep_of_drops_shows_all_three_and_never_a_held_tilt() -> None:
    kinds: dict[str, int] = {}
    for seed in range(60):
        h = 40 + (seed * 37) % 960
        e, t = dropped_from(float(h), vx=((seed % 5) - 2) * 90.0, seed=seed)
        _t, rows = play(e, t)
        kinds[kind_of(e)] = kinds.get(kind_of(e), 0) + 1
        run = 0.0
        flying = [r for r in rows if r[3] == "fly"]
        for a, b in zip(flying, flying[1:], strict=False):
            held = math.radians(15) < abs(ld.wrap(b[0])) < math.radians(165) and abs(ld.wrap(b[0] - a[0])) < math.radians(0.5)
            run = run + STEP if held else 0.0
            assert run < 0.4, (seed, run)
    assert set(kinds) == {"soft", "stumble", "roll"}, kinds
    assert min(kinds.values()) >= 8, kinds


def test_a_fall_off_a_ledge_takes_a_touch_too() -> None:
    e, _s = make("masculine", "walk", 3)
    e.big_ready = e.trip_ready = e.climb_ready = math.inf
    e.update(1.0)
    e.y = e.floor_y(e.current_monitor()) - 40.0
    e.update(1.0)
    e._start_fall(0.0)
    play(e, 1.0)
    assert kind_of(e) == "soft"
