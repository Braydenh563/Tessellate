"""Roam over window tops and carry a reminder (owner, 2026-11-04) on a fake clock
with seeded randomness. Nothing here touches Win32: the engine is given the top
edges a scan found."""

from __future__ import annotations

import math

import pytest

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay.engine import Engine, Monitor, Perch
from tests.test_overlay_moves import FLOOR, SIZE, make, step

WIN = Perch(11, 400, 700, 1200)  # top edge at y 700: 100 px above the figure's feet


def to_state(e: Engine, t: float, state: str, limit: float = 30.0, dt: float = 0.016):
    end = t + limit
    while t < end and e.state != state:
        t += dt
        e.update(t)
    return t


def climb(e: Engine, t: float = 1.0, win: Perch = WIN) -> float:
    e.climb_ready = 0.0
    e.set_windows([win], t)
    e.update(t)
    e._perform("climb", t)
    return to_state(e, t, "land", 40.0)


# --- walkers hop up, walk along it and come down -----------------------------------------------

def test_a_walker_walks_under_a_window_leaps_onto_its_top_and_stands_there() -> None:
    e = make(seed=3)
    t = climb(e)
    assert e.state == "land" and e.perch == WIN
    assert e.y == WIN.top - SIZE[1] and WIN.left <= e.x + SIZE[0] / 2 < WIN.right
    t, outs = step(e, t, 0.5)
    assert e.state == "stand" and outs[-1].y == WIN.top - SIZE[1]


def test_it_walks_along_the_top_and_hops_or_falls_off_its_end() -> None:
    e = make(seed=3)
    t = climb(e)
    e.perch_until = math.inf  # stay until the end of the edge
    e._enter("walk", t)
    seen_y = set()
    for _ in range(4000):
        t += 0.033
        e.update(t)
        if e.state == "walk":
            seen_y.add(round(e.y))
            e.state_until = math.inf
        if e.state in ("fall", "fly"):
            break
    assert seen_y == {WIN.top - SIZE[1]}  # level while on it
    assert e.state == "fall" and e.perch is None
    to_state(e, t, "land", 5.0)
    assert e.y == FLOOR


def test_it_comes_down_after_its_time_on_a_window() -> None:
    e = make(seed=5)
    t = climb(e)
    t = to_state(e, t, "stand", 2.0)
    e.perch_until = t
    e.state_until = t
    t, _ = step(e, t, 6.0)
    assert e.perch is None and e.y == FLOOR


@pytest.mark.parametrize("change", ["closed", "minimised", "moved_away", "lower"])
def test_it_falls_when_its_window_goes_or_moves_out_from_under_it(change: str) -> None:
    e = make(seed=3)
    t = climb(e)
    t = to_state(e, t, "stand", 2.0)
    new = {
        "closed": [], "minimised": [],  # a minimised window is not in the scan
        "moved_away": [Perch(11, 1500, 700, 1900)],
        "lower": [Perch(11, 400, 800, 1200)],
    }[change]
    e.set_windows(new, t)
    assert e.perch is None and e.state == "fall"
    t, _ = step(e, t, 3.0)
    assert e.y == FLOOR and e.state in ("land", "stand")


def test_a_window_moved_up_takes_it_with_a_hop() -> None:
    e = make(seed=3)
    t = climb(e)
    t = to_state(e, t, "stand", 2.0)
    e.set_windows([Perch(11, e.perch.left, 600, e.perch.right)], t)
    assert e.state == "hop" and e.perch.top == 600
    t, _ = step(e, t, 1.0)
    assert e.y == 600 - SIZE[1]


# --- calm ---------------------------------------------------------------------------------------

def test_a_climb_is_only_chosen_when_it_is_calm_and_due() -> None:
    e = make(seed=3)
    e.set_windows([WIN], 0.0)
    assert not e._can_climb(1.0)  # the first one waits CLIMB_FIRST
    assert e._can_climb(eng.CLIMB_FIRST + 1)
    e.quiet = True
    assert not e._can_climb(eng.CLIMB_FIRST + 1)  # typing or presenting
    e.quiet = False
    e.roam_windows = False
    assert not e._can_climb(eng.CLIMB_FIRST + 1)  # switched off in the menu
    e.roam_windows = True
    still = make(seed=3, reduced=True)
    still.set_windows([WIN], 0.0)
    assert not still._can_climb(eng.CLIMB_FIRST + 1)  # the still state never roams


def test_a_window_too_low_or_too_narrow_or_off_screen_is_not_a_place_to_go() -> None:
    e = make(seed=3)
    e.climb_ready = 0.0
    e.set_windows([Perch(1, 400, FLOOR + 100 - 20, 1200), Perch(2, 400, 700, 450), Perch(3, 400, 60, 1200)], 1.0)
    assert e._candidates() == []  # near the floor, 50 wide, and the figure would stand above the screen


def test_one_climb_every_few_minutes_at_most_and_never_asleep() -> None:
    e = make(seed=3)
    t = climb(e)
    assert e.climb_ready >= t - 40 + eng.CLIMB_EVERY[0] - 1
    e.climb_ready, e.last_active = 0.0, -1000.0
    sleeper = make(seed=3)
    sleeper.set_windows([WIN], 0.0)
    sleeper._enter("sleep", 5.0)
    for _ in range(200):
        sleeper.update(500.0 + _ * 0.5)
        assert sleeper.state in ("sleep", "stand", "sit")
    assert sleeper.perch is None


def test_a_picked_up_figure_is_off_the_window() -> None:
    e = make(seed=3)
    t = climb(e)
    px, py = int(e.x + 10), int(e.y + 10)
    e.update(t + 0.1, event=("down", px, py))
    e.update(t + 0.12, event=("move", px + 40, py - 40))
    assert e.perch is None and e.state == "held"


def test_an_ambient_run_climbs_when_windows_are_there_and_stays_off_when_none() -> None:
    def climbs(windows) -> int:
        e = make(seed=11)
        e.set_windows(windows, 0.0)
        t, n, prev = 0.0, 0, None
        out = e.update(t)
        while t < 40 * 60:
            t += (out.wake_ms or 1000) / 1000.0
            out = e.update(t, event=("move", 0, 0)) if int(t) % 25 == 0 else e.update(t)
            if e.perch is not None and prev is None:
                n += 1
            prev = e.perch
            e.set_windows(windows, t)
        return n

    assert climbs([]) == 0
    got = climbs([WIN])
    assert 2 <= got <= 40 * 60 / eng.CLIMB_EVERY[0] + 1


# --- Atlas floats down onto it ------------------------------------------------------------------

def test_a_floater_floats_down_onto_a_window_top_and_drifts_off_when_it_closes() -> None:
    e = make(seed=3, gait="float")
    e.climb_ready = 0.0
    e.set_windows([WIN], 1.0)
    e.update(1.0)
    e._perform("climb", 1.0)
    assert e.state == "drift"
    t = to_state(e, 1.0, "stand", 60.0)
    assert e.perch == WIN and e.state == "stand"
    assert e.y == WIN.top - SIZE[1]  # on it, not hovering above it
    e.set_windows([], t)
    assert e.perch is None and e.state == "fly"
    t, _ = step(e, t, 6.0)
    # Back in the air and travelling again (INBOX 1658: a floater rests only a moment).
    assert e.state in ("stand", "drift") and e.y <= e.ground_y() + 5


# --- a reminder's card --------------------------------------------------------------------------

def card_to_wait(e: Engine, pointer=(600, 900), t: float = 1.0):
    e.update(t, pointer)
    e.bring_card("r7", t)
    t = to_state_p(e, t, "card", pointer)
    return t


def to_state_p(e: Engine, t: float, state: str, pointer, limit: float = 60.0) -> float:
    end = t + limit
    while t < end and e.state != state:
        t += 0.033
        e.update(t, pointer)
    return t


def test_a_due_reminder_is_fetched_to_the_floor_beside_the_pointer_and_waits_holding_a_card() -> None:
    e = make(seed=3, home=(1500, FLOOR))
    t = card_to_wait(e, pointer=(500, 600))
    assert e.state == "card" and e.card == "r7"
    assert e.y == FLOOR  # on the floor
    assert abs((e.x + SIZE[0] / 2) - 500) < SIZE[0] * 2  # beside the pointer
    frames = set()
    for i in range(40):
        frames.add(e.update(t + i * 0.1, (500, 600)).frame)
    assert frames == {"card0", "card1"}


def test_walking_with_a_card_draws_the_card_frames() -> None:
    e = make(seed=3, home=(1500, FLOOR))
    e.update(1.0, (500, 600))
    e.bring_card("r7", 1.0)
    frames = set()
    t = 1.0
    while e.state != "card" and t < 60:
        t += 0.033
        out = e.update(t, (500, 600))
        if e.state == "walk":
            frames.add(out.frame)
    assert frames and frames <= {"card0", "card1"}


def test_a_click_on_the_card_reports_its_reminder_and_sets_it_down() -> None:
    e = make(seed=3, home=(1500, FLOOR))
    t = card_to_wait(e, pointer=(500, 600))
    px, py = int(e.x + SIZE[0] / 2), int(e.y + SIZE[1] / 2)
    e.update(t + 0.1, (px, py), ("down", px, py))
    out = e.update(t + 0.2, (px, py), ("up", px, py))
    assert out.card == "r7" and out.click is None  # the reminder, not the quick menu
    assert e.card is None
    assert e.update(t + 0.3).card is None  # reported once


def test_an_ignored_card_is_set_down_after_two_minutes() -> None:
    e = make(seed=3, home=(1500, FLOOR))
    t = card_to_wait(e, pointer=(500, 600))
    assert eng.CARD_FOR == 120.0
    e.update(t + 119, (500, 600))
    assert e.card == "r7"
    out = e.update(t + 121, (500, 600))
    assert e.card is None and e.state == "stand" and out.card is None


def test_reminders_queue_and_come_one_at_a_time() -> None:
    e = make(seed=3, home=(1500, FLOOR))
    e.update(1.0, (500, 600))
    e.bring_card("a", 1.0)
    e.bring_card("b", 1.0)
    t = to_state_p(e, 1.0, "card", (500, 600))
    assert e.card == "a" and e.card_queue == ["b"]
    px, py = int(e.x + 50), int(e.y + 60)
    e.update(t + 0.1, (px, py), ("down", px, py))
    assert e.update(t + 0.2, (px, py), ("up", px, py)).card == "a"
    to_state_p(e, t + 0.2, "card", (500, 600))
    assert e.card == "b" and e.card_queue == []


def test_the_card_goes_to_the_pointers_monitor_even_with_one_left_of_the_primary() -> None:
    left = Monitor((-1920, 0, 0, 1040), 96)
    primary = Monitor((0, 0, 1920, 1040), 96)
    e = make([primary, left], seed=3, home=(1000, FLOOR))
    e.update(1.0, (-800, 500))
    e.bring_card("r1", 1.0)
    to_state_p(e, 1.0, "card", (-800, 500))
    assert e.state == "card" and -1920 <= e.x <= -SIZE[0]
    assert e.current_monitor() is left


def test_a_still_figure_holds_the_card_where_it_sits_and_it_runs_out() -> None:
    e = make(seed=3, reduced=True, home=(1000, FLOOR))
    e.update(1.0, (500, 600))
    e.bring_card("r7", 1.0)
    out = e.update(1.1, (500, 600))
    assert e.state == "card" and e.x == 1000 and out.frame.startswith("card")
    assert out.wake_ms is not None  # it still swaps and runs out
    e.update(1.2 + eng.CARD_FOR, (500, 600))
    assert e.card is None


def test_a_walker_on_a_window_comes_down_for_a_reminder() -> None:
    e = make(seed=3)
    t = climb(e)
    e.perch_until = math.inf
    e.update(t + 0.5, (300, 800))
    e.bring_card("r7", t + 0.5)
    to_state_p(e, t + 0.5, "card", (300, 800))
    assert e.perch is None and e.y == FLOOR
