"""L152 (D5, A2): presence spells on a window's top at an edge spot, and the far-move sweep with its counts. Fixed clock, seeded."""

from __future__ import annotations

import random

import pytest

from tessellate.core.overlay import presence as pr
from tessellate.core.overlay.engine import Perch
from tests.test_overlay_moves import FLOOR, SIZE, make, step
from tests.test_overlay_roam import WIN, climb, to_state


def perched(seed: int = 3, hour: int = 20):
    e = make(seed=seed)
    t = climb(e)
    e.hour = hour
    t, _ = step(e, t, 0.6)
    assert e.perch == WIN
    return e, t


def test_the_edge_spot_is_inside_the_top_and_nearer_the_end_it_is_toward() -> None:
    lo = pr.perch_edge_x(400, 1200, 100, 1.0, 410)
    hi = pr.perch_edge_x(400, 1200, 100, 1.0, 1190)
    assert lo == 400 + pr.PERCH_EDGE_IN and hi == 1200 - 100 - pr.PERCH_EDGE_IN
    assert pr.perch_edge_x(400, 480, 100, 1.0, 0) == 390  # a top barely wider than the figure: the middle


def test_a_perch_spell_is_only_one_a_top_can_hold() -> None:
    rng = random.Random(5)
    for hour in range(24):
        for _ in range(40):
            got = pr.pick_perch_spell(rng, hour, "content", [])
            assert got is None or got in pr.PERCH_SPELLS
    assert pr.pick_perch_spell(rng, 4, "content", []) is None  # no spell on a top suits four in the morning
    assert {pr.pick_perch_spell(rng, 20, "curious", []) for _ in range(80)} >= {"fish", "stars"}


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_a_walker_on_a_window_does_its_spell_up_there_at_an_edge_spot(seed: int) -> None:
    e, t = perched(seed)
    e._begin_spell(t)
    assert e.spell is not None and e.spell["name"] in pr.PERCH_SPELLS
    t = to_state(e, t, "act", 20.0)
    assert e.state == "act" and e.act == e.spell["act"] and e.perch == WIN
    assert e.y == WIN.top - SIZE[1]  # on the top, not the floor
    inset = pr.PERCH_EDGE_IN * e._scale()
    assert abs(e.x - (WIN.left + inset)) < 1.5 or abs(e.x - (WIN.right - SIZE[0] - inset)) < 1.5
    assert e.perch_until >= t + e.spell["len"] - 1.0, "the perch is kept for the whole spell"
    assert e.perch_spells == 1


def test_the_perch_outlasts_the_spell_and_it_comes_down_after() -> None:
    e, t = perched(2)
    e._begin_spell(t)
    end = e.perch_until
    t = to_state(e, t, "act", 20.0)
    while t < end - 2.0:
        t += 0.5
        e.update(t)
        assert e.perch == WIN, "still up on the window while the spell runs"
    for _ in range(1200):
        t += 0.25
        e.update(t)
    assert e.perch is None and e.y == FLOOR


def test_a_floater_keeps_its_spell_on_the_floor() -> None:
    e = make(seed=3, gait="float")
    e.perch = WIN
    e.hour = 20
    assert not e._perch_spell_ok()
    assert not e._perch_spell(1.0)


def test_the_floor_spell_is_unchanged_when_no_perch_spell_suits_the_hour() -> None:
    e, t = perched(3, hour=4)
    assert e._perch_spell(t) is False and e.perch_spells == 0


def test_a_window_the_spell_sits_on_is_gone_then_it_drops_to_the_floor() -> None:
    e, t = perched(3)
    e._begin_spell(t)
    t = to_state(e, t, "act", 20.0)
    e.set_windows([Perch(99, 0, 100, 10)], t)
    for _ in range(400):
        t += 0.05
        e.update(t)
    assert e.perch is None


# --- A2: the far-move sweep and the counts -------------------------------------------------------------------------------

LEGS = [(100.0, 1700.0), (1700.0, 160.0), (300.0, 1100.0), (1500.0, 700.0), (120.0, 1800.0), (1800.0, 140.0)]


def far_leg(seed: int, gait: str, start: float, goal: float):
    """One far move across the screen from `start` to `goal`, frame by frame: (engine, the largest step the drawn figure took
    between two frames outside a vanish, whether it arrived, the seconds it took)."""
    e = make(seed=seed, gait=gait)
    e.plain_legs = False
    e.x = start
    e._place_on_floor()
    e.hour = 14
    t = 1.0
    e.update(t)
    legs0 = len(e.legs)
    e._go((goal, e.ground_y()), "stand", t)
    if e.pending is not None:  # the leg may have moved the goal (out of the middle third, clear of the edges): arrive at that
        goal = e.pending[0][0]
    prev, worst, began = None, 0.0, t
    for _ in range(2000):
        t += 0.016
        out = e.update(t)
        if prev is not None and e.state != "warp" and prev[1] != "warp":
            worst = max(worst, abs(out.x - prev[0]))
        prev = (out.x, e.state)
        if e.state == "stand" and t - began > 0.5 and e.pending is None and e.warp is None:
            break
    if len(e.legs) > legs0:
        goal = e.legs[-1][2]  # a warp leg names where it came down
    return e, worst, abs(e.x - goal), t - began


@pytest.mark.parametrize("gait", ["walk", "float"])
def test_every_far_move_arrives_and_none_jumps_between_two_frames(gait: str) -> None:
    worst_step, slowest, kinds = 0.0, 0.0, set()
    for seed in range(1, 9):
        for start, goal in LEGS:
            e, worst, miss, took = far_leg(seed, gait, start, goal)
            kinds.update(e.modes)
            worst_step, slowest = max(worst_step, worst), max(slowest, took)
            assert miss <= 24.0, (gait, seed, start, goal, miss, e.modes)  # out_of_middle may move a goal that lies in the middle third
    assert worst_step <= 60.0, worst_step  # a step between two frames is a few px of the stride, never a jump
    assert slowest < 20.0, slowest  # a plain walk across most of the screen is the slowest, about 14 s measured
    assert len(kinds) >= 4, kinds


def test_the_far_moves_are_counted_by_kind_and_none_is_used_twice_running() -> None:
    e = make(seed=11, gait="float")
    e.plain_legs = False
    t = 1.0
    e.update(t)
    for i in range(120):
        e.x = 100.0 if i % 2 == 0 else 1700.0
        e._place_on_floor()
        e.warp, e.pending = None, None
        e._enter("stand", t)
        e._go((1700.0 if i % 2 == 0 else 100.0, e.ground_y()), "stand", t)
        for _ in range(900):
            t += 0.016
            e.update(t)
            if e.state == "stand" and e.warp is None and e.pending is None:
                break
    counts = e.warp_counts()
    assert sum(counts.values()) == len(e.modes) and len(counts) >= 4, counts
    assert all(a != b for a, b in zip(e.modes, e.modes[1:])), "a way of moving is never used twice running"
    assert set(counts) <= set(__import__("tessellate.core.overlay.travel", fromlist=["MODES"]).MODES)


def test_the_runner_logs_the_counts_when_it_stops(caplog) -> None:
    import logging
    from types import SimpleNamespace

    from tessellate.core.overlay.runner import OverlayRunner

    r = OverlayRunner.__new__(OverlayRunner)
    r.engine = SimpleNamespace(warp_counts=lambda: {"walk": 3, "portal": 1}, perch_spells=2)
    r.host, r.visible, r._stopped = None, True, False
    with caplog.at_level(logging.INFO):
        r.stop()
    assert any("far moves by kind" in m and "portal" in m and "perch spells 2" in m for m in caplog.messages)
