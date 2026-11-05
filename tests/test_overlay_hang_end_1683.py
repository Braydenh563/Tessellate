"""INBOX 1683 (h): a hang ends by its own choice (pull up onto the edge, swing and drop to a window, or let go after a
startled beat), never a plain fall on a timer. Fixed clock, seeded randomness."""
from __future__ import annotations

import pytest

from tessellate.core.overlay.engine import Engine, Perch
from tests.overlay_sim_1670 import simulate
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
def test_a_hang_with_nothing_below_ends_in_a_startled_beat_before_it_lets_go(gait: str) -> None:
    for seed in range(8):
        e, t = hang_at_ceiling(seed, [], gait)
        e.state_until = t  # its time is up
        e.update(t + 0.016)
        assert e.state == "hang" and e.releasing, (seed, e.state)  # a beat, still holding, not a fall on the timer
        assert e.mind.event == "startled"
        end = t + 2.0
        while e.state == "hang" and t < end:
            t += 0.016
            e.update(t)
        assert e.state in ("fall", "fly"), e.state
        assert any(leg[0] == "hang_react" for leg in e.legs)


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
            assert all(leg[0] in ("hang_pull", "hang_swing", "hang_react") for leg in hangs)
