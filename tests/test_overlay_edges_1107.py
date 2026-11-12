"""INBOX 1683 y, 1692 a: the screen edges model. Every bar along a monitor's edges (a taskbar on any of four sides,
a secondary taskbar, a docked appbar or sidebar), shown or not, and the floor, ceiling and sides that follow. Fake
win32 and a fake clock: real Windows is unverified."""

from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import engine as eng  # noqa: E402
from tessellate.core.overlay import runner  # noqa: E402
from tessellate.core.overlay import win32 as k  # noqa: E402
from tests._overlay_fake import FakeWin32  # noqa: E402

FULL = (0, 0, 1920, 1080)
TRAY = 9001

#: (edge, ABE number, the taskbar's rectangle, the work area it leaves)
SIDES = {
    "bottom": (3, (0, 1040, 1920, 1080), (0, 0, 1920, 1040)),
    "top": (1, (0, 0, 1920, 40), (0, 40, 1920, 1080)),
    "left": (0, (0, 0, 60, 1080), (60, 0, 1920, 1080)),
    "right": (2, (1860, 0, 1920, 1080), (0, 0, 1860, 1080)),
}


def make(side: str = "bottom", *, visible: bool = True, autohide: bool = False, tell: bool = True, work: tuple | None = None) -> FakeWin32:
    fake = FakeWin32()
    edge, rect, area = SIDES[side][0], SIDES[side][1], work or SIDES[side][2]
    fake.monitor_list = [(area, 96)]
    fake.monitor_full = [FULL]
    win = {"rect": rect, "title": "tray", "visible": visible, "autohide": autohide}
    if tell:
        win["edge"] = edge
    fake.window_list[TRAY] = win
    return fake


@pytest.mark.parametrize("side", list(SIDES))
def test_a_shown_taskbar_on_each_of_four_edges_is_a_bar_and_keeps_its_strip(side: str) -> None:
    fake = make(side)
    found = k.bars(fake)
    assert found == [k.BarInfo(side, SIDES[side][1], True, False, True, False)] and found[0].shown
    mon = k.monitors_full(fake)[0]
    assert mon.area == SIDES[side][2] and mon.screen == FULL and mon.bars == tuple(found)


@pytest.mark.parametrize("side", list(SIDES))
def test_the_edge_is_read_from_the_shapes_when_the_shell_does_not_say(side: str) -> None:
    assert [b.edge for b in k.bars(make(side, tell=False))] == [side]


@pytest.mark.parametrize("side", list(SIDES))
def test_a_hidden_taskbar_gives_its_strip_back_on_its_own_edge(side: str) -> None:
    fake = make(side, visible=False)
    (bar,) = k.bars(fake)
    assert bar.edge == side and not bar.visible and not bar.shown
    assert k.monitors_full(fake)[0].area == FULL


@pytest.mark.parametrize("side", list(SIDES))
def test_an_auto_hidden_taskbar_gives_its_strip_back_on_its_own_edge(side: str) -> None:
    fake = make(side, autohide=True)
    (bar,) = k.bars(fake)
    assert bar.autohide and not bar.shown
    assert k.monitors_full(fake)[0].area == FULL


def test_an_auto_hidden_taskbar_resting_half_off_the_screen_still_belongs_to_the_monitor() -> None:
    fake = make("bottom", autohide=True)
    fake.window_list[TRAY]["rect"] = (0, 1078, 1920, 1118)  # all but two pixels below the edge
    (bar,) = k.bars(fake)
    assert bar.edge == "bottom" and k.monitors_full(fake)[0].area == FULL


def test_a_docked_sidebar_is_a_bar_that_is_not_a_taskbar_and_keeps_its_strip() -> None:
    work = (100, 0, 1920, 1040)  # a taskbar along the bottom (40) and a sidebar down the left (100)
    fake = make("bottom", work=work)
    side = next(b for b in k.bars(fake) if b.edge == "left")
    assert side.rect == (0, 0, 100, 1080) and not side.taskbar and side.shown
    mon = k.monitors_full(fake)[0]
    assert mon.area == work and {b.edge for b in mon.bars} == {"bottom", "left"}


def test_no_taskbar_window_at_all_is_a_gone_taskbar_at_the_bottom_and_a_sidebar_stays() -> None:
    fake = make("bottom", work=(100, 0, 1920, 1040))
    del fake.window_list[TRAY]
    mon = k.monitors_full(fake)[0]
    assert mon.area == (100, 0, 1920, 1080)
    assert {(b.edge, b.shown) for b in mon.bars} == {("bottom", False), ("left", True)}


def test_a_full_screen_program_in_front_hides_every_bar_whatever_they_are_set_to() -> None:
    fake = make("bottom")
    fake.window_list[5000] = {"rect": FULL, "title": "Game"}
    fake.foreground = 5000
    (bar,) = k.bars(fake)
    assert bar.covered and not bar.shown
    assert k.monitors_full(fake)[0].area == FULL


def test_a_maximised_window_or_the_desktop_in_front_covers_nothing() -> None:
    fake = make("bottom")
    fake.window_list[5000] = {"rect": (0, 0, 1920, 1040), "title": "Editor", "zoomed": True}
    fake.foreground = 5000
    assert k.monitors_full(fake)[0].area == (0, 0, 1920, 1040)
    fake.window_list[5001] = {"rect": FULL, "title": "Program Manager", "cls": "Progman"}  # the desktop is clicked
    fake.foreground = 5001
    assert k.monitors_full(fake)[0].area == (0, 0, 1920, 1040)


def test_a_secondary_taskbar_belongs_to_its_own_monitor() -> None:
    fake = make("bottom")
    fake.monitor_list = [((0, 0, 1920, 1040), 96), ((1920, 0, 3840, 1040), 96)]
    fake.monitor_full = [FULL, (1920, 0, 3840, 1080)]
    fake.window_list[9002] = {"rect": (1920, 1040, 3840, 1080), "title": "tray 2", "cls": "Shell_SecondaryTrayWnd", "edge": 3}
    first, second = k.monitors_full(fake)
    assert [b.rect for b in first.bars] == [(0, 1040, 1920, 1080)]
    assert [b.rect for b in second.bars] == [(1920, 1040, 3840, 1080)]
    fake.window_list[9002]["autohide"] = True  # only the second one hides itself
    first, second = k.monitors_full(fake)
    assert first.area[3] == 1040 and second.area[3] == 1080


def test_a_monitor_the_shell_cannot_describe_has_no_bars_and_keeps_its_work_area() -> None:
    fake = make("bottom")
    fake.monitor_full = [(0, 0, 0, 0)]
    mon = k.monitors_full(fake)[0]
    assert mon.bars == () and mon.area == SIDES["bottom"][2]


def test_the_runner_hands_the_engine_the_bars_and_the_whole_screen() -> None:
    fake = make("left", work=(60, 0, 1920, 1000))
    (mon, *rest) = runner.read_layout(k, fake)
    assert not rest and mon.screen == FULL and mon.area == (60, 0, 1920, 1000)
    assert {(b.edge, b.shown) for b in mon.bars} == {("left", True), ("bottom", True)}
    assert mon.bar("left") is not None and mon.bar("top") is None and mon.full() == FULL


def test_a_backend_without_bars_gives_the_play_area_alone() -> None:
    backend = SimpleNamespace(monitors=lambda _w: [((0, 0, 100, 100), 96)])
    assert runner.read_layout(backend, None) == [eng.Monitor((0, 0, 100, 100), 96)]


def test_the_runner_notices_a_bar_that_moved_though_the_work_area_did_not() -> None:
    fake = make("bottom")
    refreshed: list[int] = []
    me = SimpleNamespace(
        k=k, w=fake, monitors=runner.read_layout(k, fake), _next_taskbar=0.0, _bars_key=None, _refresh_monitors=lambda: refreshed.append(1),
    )
    watch = runner.OverlayRunner._watch_taskbar
    watch(me, 10.0)  # the first read only records
    assert refreshed == []
    fake.window_list[TRAY]["rect"] = (0, 1036, 1920, 1080)
    watch(me, 10.0 + runner.TASKBAR_EVERY)
    assert refreshed == [1]


def test_the_hosts_taskbar_event_reads_the_screen_again() -> None:
    refreshed: list[int] = []
    engine = SimpleNamespace(update=lambda now, pointer: "out")
    me = SimpleNamespace(engine=engine, _refresh_monitors=lambda: refreshed.append(1), _apply=lambda out: out)
    assert runner.OverlayRunner._system(me, "taskbar", 1.0, (0, 0)) == "out" and refreshed == [1]


# --- the engine: the floor follows the bars ---------------------------------------------------------------------------

SIZE = (100, 120)
BAR = eng.Bar("bottom", (0, 1040, 1920, 1080), True)
WITH = eng.Monitor((0, 0, 1920, 1040), 96, FULL, (BAR,))
WITHOUT = eng.Monitor((0, 0, 1920, 1080), 96, FULL, (BAR._replace(shown=False),))


def standing(monitor: eng.Monitor, gait: str = "walk") -> eng.Engine:
    e = eng.Engine(SIZE, [monitor], home=(800, 920), rng=random.Random(7), idle_frames=0, gait=gait, now=0.0)
    e.update(0.1)
    return e


def test_the_floor_is_the_top_of_a_shown_bottom_bar_else_the_bottom_of_the_screen() -> None:
    assert standing(WITH).floor_y() == 1040 - 120
    assert standing(WITHOUT).floor_y() == 1080 - 120


@pytest.mark.parametrize("gait", ["walk", "float"])
def test_a_figure_standing_when_the_taskbar_hides_falls_to_the_new_floor_and_does_not_snap(gait: str) -> None:
    e = standing(WITH, gait)
    y0 = e.y
    e.set_monitors([WITHOUT])
    assert e.state in ("fall", "fly") and e.y == y0  # not moved by the change itself
    ys, t = [], 0.1
    while t < 3.0:
        t += 0.033
        out = e.update(t)
        ys.append(out.y)
    assert e.state in ("land", "stand", "act", "sit", "walk", "look") and e.y == e.ground_y()
    assert e.ground_y() > y0 + 30 and e.floor_y() == 1080 - 120
    steps = [b - a for a, b in zip(ys, ys[1:])]
    assert min(steps) >= -1.0 and max(steps) < 60  # a fall in several draws, never one jump


def test_a_figure_standing_when_a_taskbar_appears_is_lifted_to_the_new_floor() -> None:
    e = standing(WITHOUT)
    e.set_monitors([WITH])
    assert e.state == "stand" and e.y == 1040 - 120


def test_a_new_resolution_plants_the_figure_on_the_new_floor_without_a_fall() -> None:
    e = standing(WITH)
    e.set_monitors([eng.Monitor((0, 0, 2560, 1400), 96, (0, 0, 2560, 1440), ())])
    assert e.state == "stand" and e.y == 1400 - 120


def test_a_figure_on_a_window_does_not_fall_when_the_taskbar_hides() -> None:
    e = standing(WITH)
    e.set_windows([eng.Perch(7, 600, 500, 1000)], 0.2)
    e.perch = eng.Perch(7, 600, 500, 1000)
    e.y = e.floor_y()
    e.set_monitors([WITHOUT])
    assert e.state != "fall" and e.y == 500 - 120
