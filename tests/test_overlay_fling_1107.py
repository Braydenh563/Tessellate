"""INBOX 1683 x, ledger N6: a window dragged out from under the figure throws it off. Above a speed derived from the throw
constants it is flung with a flail; a lying, sitting, napping or prop figure slides or tips off at a lower one; below
those it stays on and rides. After the fall: the landing outcome, or a poof or a portal to somewhere safe, then a
worried or miffed face for two to four seconds. Fake clock, no Win32; real Windows is unverified."""

from __future__ import annotations

import random
from collections import Counter

import pytest

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import extras
from tessellate.core.overlay.engine import Engine, Monitor, Perch

SIZE = (100, 120)
FULL = (0, 0, 1920, 1080)
TOP = Perch(1, 800, 600, 1300)
DT = 0.25  # the scan that follows a window


def make(seed: int = 5, **kw) -> Engine:
    kw.setdefault("hang_top", 0.2)
    e = Engine(SIZE, [Monitor(FULL, 96, FULL, ())], home=(900, 700), rng=random.Random(seed), idle_frames=0, now=0.0, **kw)
    e.update(0.1)
    return e


def on_top(state: str = "stand", seed: int = 5, act: str | None = None, **kw) -> Engine:
    e = make(seed, **kw)
    e.set_windows([TOP], 0.2)
    e.perch, e.perch_until = TOP, 1e9
    e.x, e.y = 900.0, float(TOP.top - SIZE[1])
    if state == "act":
        e._enter("act", e.now)
        e.act, e.act_started, e.act_len = act, e.now, 1e6
    elif state != "stand":
        e._enter(state, e.now)
    e.update(0.3)
    e.set_windows([TOP], 1.0)  # the window as it was, a scan before it moves
    assert e.perch == TOP and e.state == state
    return e


def drag(e: Engine, speed: float, dx_sign: int = 1, dy: int = 0, dt: float = DT) -> None:
    """The next scan finds the window `speed` logical px per second away, along x (and `dy` px down)."""
    dx = round(dx_sign * speed * dt * e._scale())
    e.set_windows([Perch(1, TOP.left + dx, TOP.top + dy, TOP.right + dx)], 1.0 + dt)


# --- thresholds ----------------------------------------------------------------------------------------------------

def test_the_speeds_come_from_the_throw_constants() -> None:
    assert eng.FLING_SPEED == 2 * eng.THROW_MIN and eng.SLIP_SPEED == eng.THROW_MIN / 2 < eng.FLING_SPEED < eng.THROW_MAX


def test_a_window_moved_slower_than_the_fling_speed_carries_a_standing_figure_with_it() -> None:
    e = on_top()
    x0 = e.x
    drag(e, eng.FLING_SPEED * 0.9)
    assert e.state == "stand" and e.perch is not None and e.x > x0 + 100


def test_a_window_moved_faster_than_the_fling_speed_throws_a_standing_figure_off() -> None:
    e = on_top()
    drag(e, eng.FLING_SPEED * 1.1)
    assert e.state in ("fly", "warp") and e.perch is None and e.last_fling in ("fall", "puff", "portal")


def test_the_throw_follows_the_window_and_leaves_with_a_flail() -> None:
    for sign in (1, -1):
        e = on_top(seed=11)
        e.rng = random.Random(3)  # a seed that falls rather than escapes (the mix is measured below)
        e._escape_roll = lambda: False  # type: ignore[method-assign]
        drag(e, eng.FLING_SPEED * 1.5, sign)
        assert e.state == "fly" and e.vx * sign > 0 and e.vy < 0
        assert e.flail_until > e.now
        t, flailed = e.now, False
        while e.state == "fly" and t < 10:
            t += 0.033
            e.update(t)
            flailed = flailed or abs(e.wob) > 0.02
        assert flailed


def test_the_speed_is_clamped_to_the_throw_maximum() -> None:
    e = on_top()
    e._escape_roll = lambda: False  # type: ignore[method-assign]
    drag(e, eng.THROW_MAX * 3)
    assert e.state == "fly" and (e.vx**2 + e.vy**2) ** 0.5 <= eng.THROW_MAX * 1.001


def test_a_window_that_was_resized_not_moved_throws_nothing() -> None:
    e = on_top()
    e.set_windows([Perch(1, 800, 600, 1900)], 1.0 + DT)  # its right edge went a long way: a resize
    assert e.state == "stand" and e.perch is not None


@pytest.mark.parametrize("state, act", [("sit", None), ("sleep", None), ("act", next(iter(extras.props.PROP_ACTS)))])
def test_a_figure_lying_sitting_napping_or_on_a_prop_slides_or_tips_off_at_a_lower_speed(state: str, act) -> None:
    speed = (eng.SLIP_SPEED + eng.FLING_SPEED) / 2
    e = on_top(state, act=act)
    drag(e, eng.SLIP_SPEED * 0.8)
    assert e.state == state and e.perch is not None  # under the slip speed it stays anchored
    e = on_top(state, act=act)
    drag(e, speed)
    assert e.state == "fall" and e.perch is None and e.last_fling in ("slide", "tip")


def test_a_standing_figure_at_the_slip_speed_stays_anchored() -> None:
    e = on_top()
    drag(e, (eng.SLIP_SPEED + eng.FLING_SPEED) / 2)
    assert e.state == "stand" and e.perch is not None


def test_a_sleeper_is_still_flung_by_a_hard_drag() -> None:
    e = on_top("sleep")
    e._escape_roll = lambda: False  # type: ignore[method-assign]
    drag(e, eng.FLING_SPEED * 1.2)
    assert e.state == "fly"


def test_reduced_motion_rides_the_window_and_is_never_flung() -> None:
    e = on_top("sit", reduced=True)
    drag(e, eng.THROW_MAX)
    assert e.state != "fly" and e.state != "fall"


# --- the outcome ---------------------------------------------------------------------------------------------------

def test_the_outcome_mix_over_a_hundred_seeded_flings() -> None:
    mix: Counter = Counter()
    for seed in range(100):
        e = on_top(seed=seed)
        drag(e, eng.FLING_SPEED * 1.5)
        mix[e.last_fling] += 1
    assert sum(mix.values()) == 100 and set(mix) == {"fall", "puff", "portal"}, mix
    assert 40 <= mix["fall"] <= 80 and mix["puff"] >= 5 and mix["portal"] >= 5, mix
    assert mix == Counter({"fall": mix["fall"], "puff": mix["puff"], "portal": mix["portal"]})
    # the same seeds give the same mix: nothing here reads the real clock
    again: Counter = Counter()
    for seed in range(100):
        e = on_top(seed=seed)
        drag(e, eng.FLING_SPEED * 1.5)
        again[e.last_fling] += 1
    assert again == mix


@pytest.mark.parametrize("mode", ["puff", "portal"])
def test_an_escape_pops_to_a_place_away_from_the_window_and_stands(mode: str) -> None:
    e = on_top()
    e._escape_roll = lambda: mode  # type: ignore[method-assign]
    drag(e, eng.FLING_SPEED * 1.5)
    assert e.state == "warp" and e.warp["kind"] == mode and e.last_fling == mode
    t = e.now
    while e.state == "warp" and t < 10:
        t += 0.033
        e.update(t)
    assert e.state in ("stand", "land", "act")
    cx = e.x + SIZE[0] / 2
    assert not (TOP.left - 200 <= cx <= TOP.right + 200) or e.perch is not None


def test_an_escape_prefers_another_window_top_when_there_is_one() -> None:
    e = on_top()
    other = Perch(2, 100, 500, 600)
    e._escape_roll = lambda: "portal"  # type: ignore[method-assign]
    e.set_windows([TOP, other], 1.0)
    e.set_windows([Perch(1, 800 + 400, 600, 1300 + 400), other], 1.0 + DT)
    assert e.state == "warp" and e.target is not None and e.target.key == 2
    t = e.now
    while e.state == "warp" and t < 10:
        t += 0.033
        e.update(t)
    assert e.perch is not None and e.perch.key == 2


# --- the face after ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("escape", [False, "puff"])
def test_a_worried_or_miffed_face_for_two_to_four_seconds_after_the_fall(escape) -> None:
    e = on_top(seed=8)
    e._escape_roll = lambda: escape  # type: ignore[method-assign]
    drag(e, eng.FLING_SPEED * 1.5)
    t, seen = e.now, None
    while t < 40:
        t += 0.033
        e.update(t)
        if e.state in ("stand", "land", "act") and e.ex.over is not None and seen is None:
            seen = (t, e.ex.over)
        if seen and e.ex.over is None:
            break
    assert seen is not None
    start, (kind, began, length) = seen
    assert kind in ("worried", "miffed") and 2.0 <= length <= 4.0 and began <= start
    assert e.ex.over is None


def test_the_face_is_drawn_while_it_lasts() -> None:
    e = on_top(seed=8)
    e._escape_roll = lambda: False  # type: ignore[method-assign]
    drag(e, eng.FLING_SPEED * 1.5)
    t, faces = e.now, set()
    while t < 40:
        t += 0.033
        out = e.update(t)
        if out.face and out.face[0] in ("worried", "miffed"):
            faces.add(out.face[0])
        if faces and e.ex.over is None:
            break
    assert faces


def test_a_pick_up_before_it_lands_forgets_the_face() -> None:
    e = on_top(seed=8)
    e._escape_roll = lambda: False  # type: ignore[method-assign]
    drag(e, eng.FLING_SPEED * 1.5)
    e._enter("held", e.now)
    assert e.flung is None


def test_the_face_kinds_exist() -> None:
    from tessellate.core.overlay import faces

    assert {"worried", "miffed"} <= set(faces.EXPRESSIONS) and extras.FACE_STATES
