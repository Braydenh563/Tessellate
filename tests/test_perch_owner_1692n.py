"""INBOX 1692 n: "it cant sit on windows". The owner's log listed 11 windows and 0 standable top edges on a
2560x1440 screen at 150%, with a normal browser at about 190 px from the top. A full-monitor layered tool window
(an animated wallpaper) must not cut every edge, a tool window that asks for a taskbar button is a real window,
the window-sized overlay with headroom above its figure must not rule out a window near the top, and the log says
why each edge was dropped. Fake win32, fake clock."""

from __future__ import annotations

import os
import random
from collections import Counter

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import engine as eng  # noqa: E402
from tessellate.core.overlay import perches  # noqa: E402
from tessellate.core.overlay import win32 as k  # noqa: E402
from tests._overlay_fake import FakeWin32  # noqa: E402

MON = (0, 0, 2560, 1440)
TOOL = k.WS_EX_TOOLWINDOW
LAYERED = k.WS_EX_LAYERED
APP = 0x00040000  # WS_EX_APPWINDOW


def owner_list() -> dict:
    wins: dict = {
        1: {"rect": (0, 0, 2560, 1440), "title": "Wallpaper", "ex": TOOL | LAYERED},  # full-monitor layered tool window
        2: {"rect": (150, 190, 2400, 1300), "title": "Browser"},
    }
    for i in range(3, 12):  # nine small tool windows far from the browser's top edge
        wins[i] = {"rect": (10 * i, 1350, 10 * i + 8, 1400), "title": "t", "ex": TOOL}
    return wins


def test_a_full_monitor_layered_tool_window_does_not_cut_the_edges_below_it() -> None:
    fake = FakeWin32()
    fake.window_list = {1: owner_list()[1], 2: owner_list()[2]}  # the wallpaper is topmost in z-order
    wins = k.windows(fake, os.getpid(), None, [MON])
    assert [w.key for w in wins] == [1, 2] and not wins[0].solid and wins[1].solid
    assert [p.key for p in perches.top_edges(wins, 200)] == [2]


def test_the_owner_list_has_one_standable_top() -> None:
    fake = FakeWin32()
    fake.window_list = owner_list()
    tally: Counter = Counter()
    wins = k.windows(fake, os.getpid(), None, [MON], tally)
    assert len(wins) == 11
    edges = perches.top_edges(wins, 200, Counter())
    assert [p.key for p in edges] == [2]
    assert tally["perch"] == 1 and tally["tool window"] == 10


def test_a_small_tool_window_still_hides_the_top_it_sits_over() -> None:
    wins = [k.WinInfo(1, (400, 150, 900, 400), False), k.WinInfo(2, (150, 190, 2400, 1300), True)]
    drops: Counter = Counter()
    assert perches.top_edges(wins, 200, drops)[0].left == 900
    covered = [k.WinInfo(1, (100, 150, 2500, 400), False), k.WinInfo(2, (150, 190, 2400, 1300), True)]
    assert perches.top_edges(covered, 200, drops) == [] and drops["covered by a tool window"] == 1


def test_a_narrow_window_is_counted_too() -> None:
    drops: Counter = Counter()
    perches.top_edges([k.WinInfo(2, (150, 190, 250, 1300), True)], 200, drops)
    assert drops["too narrow"] == 1


def test_a_tool_window_with_a_taskbar_button_is_a_real_window() -> None:
    fake = FakeWin32()
    fake.window_list = {5: {"rect": (150, 190, 2400, 1300), "title": "Electron", "ex": TOOL | APP}}
    assert [w.perch for w in k.windows(fake, os.getpid(), None, [MON])] == [True]


def make_engine() -> eng.Engine:
    e = eng.Engine((300, 360), [eng.Monitor((0, 0, 2560, 1400), 144)], rng=random.Random(7), idle_frames=0, home=(800, 1000))
    e.set_metrics({("stand", False): (60.0, 120.0, 240.0, 350.0), ("stand", True): (60.0, 120.0, 240.0, 350.0)})
    e.update(0.1)
    return e


def test_a_window_near_the_top_is_worth_the_trip_by_the_drawn_figure_not_the_overlay_window() -> None:
    e = make_engine()
    e.set_windows([eng.Perch(2, 150, 300, 2400)], 0.2)
    assert [p.key for p in e._candidates()] == [2]  # 300 - 360 < 0 by the window; the figure's top is at 300 - 360 + 120


def test_a_window_too_close_to_the_top_for_the_figure_is_still_refused_and_counted() -> None:
    e = make_engine()
    e.set_windows([eng.Perch(2, 150, 100, 2400), eng.Perch(3, 150, 1390, 2400), eng.Perch(4, 150, 600, 200)], 0.2)
    drops: Counter = Counter()
    assert e._candidates(drops) == []
    assert drops["too close to the top"] == 1 and drops["too near the floor"] == 1 and drops["too narrow"] == 1


def run_until(e: eng.Engine, t0: float, seconds: float, step: float = 0.05):
    t = t0
    while t < t0 + seconds:
        t += step
        e.update(t)
    return t


def test_a_new_window_top_is_gone_to_within_a_few_seconds_not_after_the_first_forty() -> None:
    e = make_engine()
    t = run_until(e, 0.1, 0.9)  # a stand, well inside CLIMB_FIRST
    e.set_windows([eng.Perch(2, 150, 700, 2400)], t)
    assert any("new window top" in n for n in e.notes)
    run_until(e, t, eng.CLIMB_SOON + 6.0)
    assert any("eager climb: chosen" in n for n in e.notes)
    assert e.target is not None or e.perch is not None or e.state in ("warp", "walk", "fly", "crouch", "rise", "land", "drift", "climb")
    assert e.state != "stand" or e.perch is not None


def test_an_eager_trip_that_cannot_happen_says_why_and_the_next_one_waits() -> None:
    e = make_engine()
    t = run_until(e, 0.1, 0.5)
    e.set_windows([eng.Perch(2, 150, 700, 2400)], t)
    e.set_windows([], t + 0.5)  # the window went before its time
    run_until(e, t + 0.5, eng.CLIMB_SOON + 3.0)
    assert any(n.startswith("eager climb skipped") for n in e.notes)
    assert e.perch is None


def test_a_title_bar_alone_is_an_eager_hang() -> None:
    e = make_engine()
    t = run_until(e, 0.1, 0.5)
    e.set_windows([], t, [eng.Perch(5, 0, 0, 2560, "bar")])
    assert any("title bar" in n for n in e.notes)
    run_until(e, t, eng.CLIMB_SOON + 3.0)
    assert any("eager hang: chosen" in n for n in e.notes)


def test_the_answers_to_a_new_window_and_a_switched_app_are_big_enough_to_see() -> None:
    from tessellate.core.overlay import behaviour as bh
    from tessellate.core.overlay import extras

    extras.register()
    assert bh.AMPLITUDE["glance_window"] >= 0.07 and bh.AMPLITUDE["glance_screen"] >= 0.05
