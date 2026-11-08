"""Companion catalogue Batch B (INBOX 1696 kk, the owner: "shaking it makes it turn upside down or flail and get dizzy"):
a carried shake (three direction flips inside 0.6 s) leaves the desk figure dizzy after the drop, a figure held by its
feet or shaken is carried upside down, and a long carry goes through three stages. Fake clock and a fake drag, no
Win32; real Windows is unverified."""

from __future__ import annotations

import math
import random

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import extras, faces
from tessellate.core.overlay.engine import Engine, Monitor

SIZE = (100, 120)
FULL = (0, 0, 1920, 1080)
STEP = 0.025


def make() -> Engine:
    e = Engine(SIZE, [Monitor(FULL, 96, FULL, ())], home=(900, 700), rng=random.Random(5), idle_frames=0, now=0.0)
    e.update(0.1)
    return e


def grab_at(e: Engine, t: float, fx: float = 0.5, fy: float = 0.4) -> tuple[int, int]:
    """Press on the figure at a share of its drawn box; returns the pointer."""
    left, top, right, bottom = e._box("stand", False)
    px, py = int(e.x + left + fx * (right - left)), int(e.y + top + fy * (bottom - top))
    e.update(t, event=("down", px, py))
    return px, py


def pull_out(e: Engine, t: float, px: int, py: int) -> tuple[float, int, int]:
    """A first move past the click slop, so the press becomes a carry."""
    py -= 30
    e.update(t, event=("move", px, py))
    assert e.state == "held"
    return t, px, py


def shake(e: Engine, t: float, px: int, py: int, flips: int, stroke: int = 40) -> tuple[float, int, int]:
    """`flips + 1` straight strokes of `stroke` px, a tenth of a second each, back and forth along x."""
    sign = 1
    for _ in range(flips + 1):
        for _i in range(4):
            t += STEP
            px += sign * stroke // 4
            e.update(t, event=("move", px, py))
        sign = -sign
    return t, px, py


def run_after_drop(e: Engine, t: float, px: int, py: int, seconds: float = 12.0) -> list[tuple[float, str, str | None, tuple | None]]:
    """Let go and run on: (time since the drop, state, act, face) at every tick."""
    t += STEP
    e.update(t, event=("up", px, py))
    t0, seen = t, []
    while t < t0 + seconds:
        t += 0.033
        out = e.update(t)
        seen.append((t - t0, e.state, e.act, out.face))
    return seen


def dizzy_ticks(seen: list) -> list:
    return [s for s in seen if s[2] == "dizzy_sway" or (s[3] and s[3][0] == "dizzy")]


def test_three_flips_in_under_a_second_land_dizzy() -> None:
    e = make()
    t, px, py = pull_out(e, 1.0, *grab_at(e, 1.0))
    t, px, py = shake(e, t, px, py, 3)
    assert e.shaken
    seen = run_after_drop(e, t, px, py)
    dizzy = dizzy_ticks(seen)
    assert dizzy, "never dizzy"
    assert any(s[2] == "dizzy_sway" for s in dizzy) and any(s[3] and s[3][0] == "dizzy" for s in dizzy)
    length = max(s[0] for s in dizzy) - min(s[0] for s in dizzy)
    assert 2.0 <= length <= 4.3, length  # 2.5 to 4 s of sway, give or take the ease of its face and one tick each way
    assert not dizzy_ticks(seen[-30:]), "still dizzy at the end"


def test_two_flips_do_not() -> None:
    e = make()
    t, px, py = pull_out(e, 1.0, *grab_at(e, 1.0))
    t, px, py = shake(e, t, px, py, 2)
    assert not e.shaken
    assert not dizzy_ticks(run_after_drop(e, t, px, py))


def test_flips_spread_over_more_than_0_6_seconds_do_not() -> None:
    e = make()
    t, px, py = pull_out(e, 1.0, *grab_at(e, 1.0))
    for _ in range(3):  # a flip every 0.4 s: the same hand, too slowly to be a shake
        t, px, py = shake(e, t, px, py, 1)
        t += 0.4
        e.update(t, event=("move", px, py))
    assert not e.shaken
    assert not dizzy_ticks(run_after_drop(e, t, px, py))


def test_a_shake_is_also_read_up_and_down() -> None:
    e = make()
    t, px, py = pull_out(e, 1.0, *grab_at(e, 1.0))
    sign = 1
    for _ in range(4):
        for _i in range(4):
            t += STEP
            py += sign * 10
            e.update(t, event=("move", px, py))
        sign = -sign
    assert e.shaken


def test_the_dizzy_face_is_drawn_and_a_reduced_figure_is_never_dizzy() -> None:
    assert "dizzy" in faces.EXPRESSIONS and faces.EXPRESSIONS["dizzy"].spiral > 0
    e = make()
    e.reduced = True
    t, px, py = pull_out(e, 1.0, *grab_at(e, 1.0))
    t, px, py = shake(e, t, px, py, 3)
    assert not dizzy_ticks(run_after_drop(e, t, px, py))
    assert extras.DIZZY_FOR == (2.5, 4.0) and extras.SHAKE_FLIPS == 3


# --- B2: carried upside down ----------------------------------------------------------------------------------


def hold(e: Engine, t0: float, seconds: float, step: float = 0.1) -> list[tuple[float, str, eng.Output]]:
    """The pointer rests while the figure is held: every draw (time since the carry began, its stage, the output)."""
    t, seen = t0, []
    while t < t0 + seconds:
        t += step
        out = e.update(t)
        seen.append((t - t0, e.carry_stage, out))
    return seen


def test_held_by_the_feet_it_is_carried_upside_down() -> None:
    e = make()
    t, px, py = pull_out(e, 1.0, *grab_at(e, 1.0, fy=0.92))
    assert e.upside
    out = e.update(t + 0.1)
    assert out.frame == "spin24" and out.angle == math.pi


def test_held_by_the_head_or_body_it_stays_upright() -> None:
    e = make()
    t, px, py = pull_out(e, 1.0, *grab_at(e, 1.0, fy=0.3))
    assert not e.upside
    out = e.update(t + 0.1)
    assert out.frame == "held" and out.angle is None


def test_a_shake_turns_it_over_and_it_stays_over_until_let_go() -> None:
    e = make()
    t, px, py = pull_out(e, 1.0, *grab_at(e, 1.0))
    assert not e.upside
    t, px, py = shake(e, t, px, py, 3)
    assert e.upside
    out = e.update(t + 2.0)
    assert out.frame == "spin24" and out.angle == math.pi
    assert run_after_drop(e, t + 2.0, px, py)
    assert not e.upside and e.update(t + 30.0).angle is None


def test_the_flipped_figure_stays_under_the_pointer_and_on_screen() -> None:
    e = make()
    t, px, py = pull_out(e, 1.0, *grab_at(e, 1.0, fy=0.92))
    e.update(t + 0.05, event=("move", 900, 500))
    e.update(t + 0.1, event=("move", 907, 503))
    w, h = e.size
    # the feet are held, and are now at the top of the turned picture: the pointer is 10 px under the window's top
    assert (e.x, e.y) == (907 - w / 2, 503 - 10)
    e.update(t + 0.2, event=("move", -500, -500))
    assert e.x >= -w / 2 and e.y >= 0
# --- B3: a long carry -----------------------------------------------------------------------------------------


def test_a_carry_held_10_seconds_goes_through_kick_cross_and_sigh_in_order() -> None:
    e = make()
    t, px, py = pull_out(e, 1.0, *grab_at(e, 1.0, fy=0.3))
    seen = [(s, stage, o.pose) for s, stage, o in hold(e, t, 10.0, 0.05)]
    order = []
    for _s, stage, _p in seen:
        if not order or order[-1] != stage:
            order.append(stage)
    assert order == ["", "kick", "cross", "sigh"], order
    starts = {stage: min(s for s, st, _p in seen if st == stage) for stage in ("kick", "cross", "sigh")}
    assert 4.0 <= starts["kick"] <= 4.2 and starts["kick"] < starts["cross"] < starts["sigh"]
    # each stage is seen on the figure: nothing before 4 s, legs swinging, then the arms still, then a breath out
    assert all(p is None for s, st, p in seen if st == "")
    kick = {p for s, st, p in seen if st == "kick"}
    assert len(kick) > 3 and any(p is not None and p[2] != 0 for p in kick)  # a lean back and forth
    cross = {p for s, st, p in seen if st == "cross"}
    assert len(cross) == 1 and None not in cross  # arms crossed: held still, a touch narrower
    sigh = [p for s, st, p in seen if st == "sigh" and p is not None]
    assert sigh and min(p[1] for p in sigh) < 1.0


def test_the_carry_clock_starts_at_the_carry_not_the_press_and_resets_at_the_drop() -> None:
    e = make()
    px, py = grab_at(e, 1.0, fy=0.3)
    e.update(5.0)  # a long press that is not yet a carry
    t, px, py = pull_out(e, 5.0, px, py)
    assert e.carry_stage == ""
    hold(e, t, 4.5)
    assert e.carry_stage == "kick"
    run_after_drop(e, t + 4.5, px, py, 1.0)
    assert e.carry_stage == "" and e.carry_since is None
