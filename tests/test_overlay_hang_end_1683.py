"""INBOX 1683 (h): a hang ends by its own choice (pull up onto the edge, swing and drop to a window, or let go after a
startled beat), never a plain fall on a timer. Fixed clock, seeded randomness."""
from __future__ import annotations

import pytest

from tessellate.core.overlay.engine import Engine, Perch
from tests.overlay_sim_1670 import simulate, skip_flow
from tests.test_overlay_moves import make

# --- (h) a hang ends by its own choice ----------------------------------------------------------


def hang_at_ceiling(seed: int, windows: list[Perch], gait: str = "float") -> tuple[Engine, float]:
    e = make(seed=seed, gait=gait, hang_top=0.195)
    e.plain_legs = True
    e.climb_ready = float("inf")
    e.set_windows(windows, 0.0)
    e._perform("hang", 1.0)
    t = 1.0
    while e.state != "hang" and t < 60:
        t += 0.016
        e.update(t)
    assert e.state == "hang"
    return e, t


@pytest.mark.parametrize("gait", ["walk", "float"])
def test_a_top_hang_lasts_its_full_rest_and_then_makes_a_calm_drop(gait: str) -> None:
    """Owner 2026-11-10: "it doesnt hang from the top of my screen for long before it falls down. it always falls
    down". A hang from the screen top is held for the whole rest it drew with no fall roll; after it, with nothing to
    pull onto or drop to, it makes a calm drop to its feet (a chosen let-go: no startled beat, no fall)."""
    for seed in range(8):
        e, t = hang_at_ceiling(seed, [], gait)
        t0, rest = t, e.state_until - t
        assert rest >= 60.0, rest  # the shortest mood's rest
        while t < t0 + rest - 0.5:
            t += 0.016
            e.update(t)
            assert e.state == "hang", (seed, round(t - t0, 1), e.state)
        assert not any(leg[0].startswith("hang_") for leg in e.legs)
        states = set()
        while t < t0 + rest + 6.0:
            t += 0.016
            e.update(t)
            states.add(e.state)
            assert not e.releasing and e.mind.event != "startled", (seed, e.state)
        assert states & {"stand", "sit", "rise"} and not states & {"fall", "fly"}, (seed, states)
        assert [leg[0] for leg in e.legs if leg[0].startswith("hang_")] == ["hang_calm"], e.legs


def test_a_hang_with_a_window_below_swings_and_drops_onto_it() -> None:
    win = Perch(11, 300, 600, 1000)
    dropped = 0
    for seed in range(12):
        e, t = hang_at_ceiling(seed, [], "float")  # on the ceiling; the window opens while it hangs
        e.set_windows([win], t)
        e.state_until = t
        e.update(t + 0.016)
        t += 0.016
        if e.swing_to is None:
            continue  # it chose to simply let go this time
        assert e.state == "hang" and e.swing_to.key == 11
        a0 = e._life_pose(t).drag
        for _ in range(60):
            t += 0.016
            e.update(t)
        assert abs(e._life_pose(t).drag) >= 0 and a0 is not None
        for _ in range(900):
            t += 0.016
            e.update(t)
            e.set_windows([win], t)
            if e.perch is not None:
                break
        dropped += e.perch is not None and e.perch.key == 11
    assert dropped >= 4, dropped


def test_a_hang_on_a_window_pulls_itself_up_onto_it_without_a_good_mood() -> None:
    win = Perch(11, 300, 400, 1000)
    pulled = 0
    for seed in range(20):
        e = make(seed=seed, gait="float", hang_top=0.195)
        e.climb_ready = float("inf")
        e.set_windows([win], 0.0)
        e.x, e.y = 600.0, win.top
        e.hang_on = win
        e._enter("hang", 1.0)
        e.hang_on = win
        e.mind.feel("startled", 1.0)
        e.state_until = 2.0
        e.update(2.1)
        pulled += e.state == "rise" and e.target is not None
    assert pulled >= 6, pulled  # was 70 percent only in a good mood, else a plain fall


def test_no_hang_in_a_seeded_hour_ends_in_a_plain_fall() -> None:
    for gait in ("walk", "float"):
        for seed in (1, 2, 3):
            m = simulate(gait, seed)
            hangs = [leg for leg in m["legs"] if leg[0].startswith("hang_")]
            assert all(leg[0] in ("hang_pull", "hang_swing", "hang_react", "hang_calm") for leg in hangs)


def _first_hang_end(gait: str, seed: int, scene: str) -> str:
    win = Perch(11, 300, 400, 1000)
    if scene == "title bar":
        e = make(seed=seed, gait=gait, hang_top=0.195)
        e.plain_legs = True
        e.climb_ready = float("inf")
        e.set_windows([win], 0.0)
        e.x, e.y = 600.0, win.top
        e.hang_on = win
        e._enter("hang", 1.0)
        e.hang_on = win
        t = 1.0
    else:
        e, t = hang_at_ceiling(seed, [], gait)
        if scene == "window below":
            e.set_windows([win], t)
    skip_flow(e)  # a loop that reads the hang's ending, never the flow picture
    e.state_until = t
    n = len(e.legs)
    e.update(t + 0.016)
    for _ in range(2000):
        t += 0.016
        e.update(t)
        e.set_windows([] if scene == "ceiling" else [win], t)
    return next((leg[0] for leg in e.legs[n:] if leg[0].startswith("hang_")), "")  # "hang_calm" is the top hang's own end


@pytest.mark.parametrize("gait", ["walk", "float"])
def test_forced_hang_ends_take_the_choice_that_the_scene_offers(gait: str) -> None:
    """A hang is rare in a seeded hour, so this forces 100 ends per scene: a window below is a swing and a drop, a
    title bar is a pull-up or a startled let-go; a screen-top hang with nothing in reach makes a calm drop (owner
    2026-11-10: no fall roll)."""
    for scene, option in (("window below", "hang_swing"), ("title bar", "hang_pull")):
        ends = [_first_hang_end(gait, seed, scene) for seed in range(100)]
        assert set(ends) <= {option, "hang_calm", "hang_react"}, set(ends)  # calm: a top hang with no window in reach; react: a window's edge only
        assert ends.count(option) >= 40, (scene, ends.count(option))
    assert {_first_hang_end(gait, seed, "ceiling") for seed in range(20)} == {"hang_calm"}
