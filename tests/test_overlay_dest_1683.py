"""INBOX 1683 (w), the engine's half: on the owner's desktop (a maximised window, the taskbar, one floating window,
1920x1080 at 150%) the figure goes to a title bar, a bottom edge or the work area's top to hang, to the floating
window's top, or along the floor, and no kind comes three times running. Before this: floor 54%, window 46%, hang 0%
(and with only a maximised window and the taskbar, floor 100%), seeded, 200 trips. Fixed clock; real Windows is
unverified."""
from __future__ import annotations

import random
from collections import Counter

import pytest

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay.engine import Engine, Monitor, Perch

M = Monitor((0, 0, 1920, 1032), 144)  # the work area of 1920x1080 with a 48 px taskbar, at 150%
SIZE = (150, 180)
FLOOR = 1032 - SIZE[1]
TASKBAR = Perch(2, 0, 1032, 1920)  # the one perch the owner's log listed: it is the floor itself
FLOATING = Perch(3, 500, 400, 1300)
MAX_BAR = Perch(1, 0, 0, 1920, "bar")
BOTTOM = Perch(-3, 500, 700, 1300, "bottom")


def make(seed: int = 1, gait: str = "walk", windows=(), hangs=(), roam_windows: bool = True) -> Engine:
    e = Engine(SIZE, [M], rng=random.Random(seed), home=(800, FLOOR), hang_top=0.2, gait=gait)
    e.plain_legs = True
    e.roam, e.roam_windows = True, roam_windows
    e.set_windows(list(windows), 0.0, list(hangs))
    return e


def kind_of(e: Engine) -> str:
    return "hang" if (e.then in ("hang", "hangleap") or e.hang_on is not None) else "window" if e.target is not None else "floor"


def trips(mix: str, n: int = 200, seed: int = 1, **kw) -> list[str]:
    wins = {"all": [TASKBAR, FLOATING], "owner": [TASKBAR]}[mix]
    hangs = {"all": [MAX_BAR, BOTTOM], "owner": [MAX_BAR]}[mix]
    e = make(seed, windows=wins, hangs=hangs, **kw)
    out, now = [], 0.0
    for i in range(n):
        now += random.Random(i).uniform(*eng.TRIP_EVERY)  # the real cadence: a hang is a big act, minutes apart
        e.state, e.then, e.perch, e.target, e.hang_on, e.goal = "stand", "stand", None, None, None, None
        e.x, e.y = random.Random(i).uniform(100, 1600), FLOOR
        e.pointer, e.greet_pending, e.climb_ready, e.trip_ready = (900, 500), False, 0.0, 0.0
        e.last_active = now
        e.mind.needs["rest"] = 0.2
        e._start_trip(now)
        out.append(kind_of(e))
    return out


def share(kinds: list[str]) -> dict[str, float]:
    c = Counter(kinds)
    return {k: c[k] / len(kinds) for k in ("floor", "window", "hang")}


def test_with_the_owners_mix_every_kind_of_destination_has_a_floor() -> None:
    s = share(trips("all"))
    assert s["floor"] >= 0.25 and s["window"] >= 0.2 and s["hang"] >= 0.15, s  # measured 38 / 33 / 29 (floor / window / hang); was 54 / 46 / 0


def test_with_a_maximised_window_and_the_taskbar_it_hangs_as_often_as_it_stays_low() -> None:
    s = share(trips("owner"))
    assert s["window"] == 0 and s["floor"] >= 0.3 and s["hang"] >= 0.25, s  # measured floor 58, hang 42; was floor 100, hang 0


@pytest.mark.parametrize("mix", ["all", "owner"])
def test_no_destination_comes_three_times_in_a_row(mix: str) -> None:
    for seed in range(5):
        kinds = trips(mix, seed=seed)
        assert not any(a == b == c for a, b, c in zip(kinds, kinds[1:], kinds[2:])), (seed, kinds)


@pytest.mark.parametrize("gait", ["walk", "float"])
def test_with_roam_over_windows_off_it_stays_off_the_windows(gait: str) -> None:
    # Intent moved (INBOX 1696 k, the owner 2026-11-08: "now its not even hanging from the top of my screen"): the
    # screen's top is not a window, so with the windows option off a trip is the floor or a hang from the screen's top
    # (`_hang_spots` is empty without the option, so no window bar is taken), never a window.
    kinds = set(trips("all", roam_windows=False, gait=gait))
    assert "window" not in kinds and kinds <= {"floor", "hang"}, kinds


def test_a_reduced_or_busy_figure_takes_no_trip_at_all() -> None:
    e = make(windows=[TASKBAR, FLOATING], hangs=[MAX_BAR, BOTTOM])
    e.trip_ready = 0.0
    e.reduced = True
    assert not e._trip_ok(1000.0)
    e.reduced, e.quiet = False, True
    assert not e._trip_ok(1000.0)


@pytest.mark.parametrize("gait", ["walk", "float"])
@pytest.mark.parametrize("spot", [BOTTOM, MAX_BAR, FLOATING])
def test_it_hangs_from_a_bottom_edge_a_maximised_title_bar_or_a_title_bar(gait: str, spot: Perch) -> None:
    wins = [FLOATING] if spot is FLOATING else []
    for seed in range(40):
        e = make(seed, gait, wins, [] if spot is FLOATING else [spot])
        e._perform("hang", 1.0)
        if e.hang_on is not None and e.hang_on.key == spot.key:
            break
    else:
        raise AssertionError("no seed chose it")
    t = 1.0
    while e.state != "hang" and t < 60:
        t += 0.016
        e.update(t)
    assert e.state == "hang" and e.hang_on.key == spot.key
    grip = spot.top + (eng.TITLE_BAR * 1.5 if spot.kind == "top" else 0.0)  # 1721 b: a maximised bar is gripped at its top edge
    assert e.y + e._lift() == pytest.approx(grip)  # the hands are on the edge
    centre = e.x + SIZE[0] / 2
    assert spot.left <= centre <= spot.right


def test_a_walker_far_from_a_spot_walks_under_it_first() -> None:
    for seed in range(40):
        e = make(seed, "walk", [], [BOTTOM])
        e.x = 20.0
        e._perform("hang", 1.0)
        if e.hang_on is not None or e.then == "hangleap":
            break
    assert e.state in ("walk", "crouch") and e.then == "hangleap"
    t = 1.0
    while e.state != "hang" and t < 90:
        t += 0.016
        e.update(t)
    assert e.state == "hang" and e.hang_on.key == BOTTOM.key


def test_a_hang_from_a_bottom_edge_ends_by_letting_go_never_by_pulling_up_onto_it() -> None:
    ends = Counter()
    for seed in range(12):
        e = make(seed, "float", [], [BOTTOM])
        e.hang_on = BOTTOM
        e.x, e.y = 800.0, BOTTOM.top - e._lift()
        e._enter("hang", 10.0)
        e.hang_on = BOTTOM
        e.set_windows([], 10.0, [BOTTOM])
        t = 10.0
        while e.state == "hang" and t < 400:
            t += 0.05
            e.update(t)
        assert e.state != "hang" and e.hang_on is None
        ends[e.state] += 1
        assert e.perch is None
    assert sum(ends.values()) == 12


def test_a_hang_on_a_window_that_closes_lets_go() -> None:
    e = make(2, "float", [], [BOTTOM])
    e.x, e.y = 800.0, BOTTOM.top - e._lift()
    e._enter("hang", 10.0)
    e.hang_on = BOTTOM
    e.set_windows([], 11.0, [])
    assert e.state != "hang" and e.hang_on is None


def test_the_trip_table_is_the_floor_the_window_and_the_hang_and_each_has_a_weight() -> None:
    e = make(windows=[TASKBAR, FLOATING], hangs=[MAX_BAR, BOTTOM])
    e.pointer = (900, 500)
    assert eng.HANG_TRIP_WEIGHT > 0
    assert {"floor", "window", "hang"} == {k for k, _n, _w in e._trip_table(1e6)}
    assert "hang" not in {k for k, _n, _w in e._trip_table(0.0)}  # not before the big acts' spacing is up
