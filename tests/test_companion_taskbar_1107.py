"""Research T1 (INBOX 1692 a): the floor is the bottom of the screen when the taskbar is hidden or set to
auto-hide, not a taskbar's height above it. The work area still reserves the strip when a hider tool only hides
the window, so the shell is asked (ABM_GETSTATE, Shell_TrayWnd). Fake win32, no real taskbar."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import win32 as k  # noqa: E402
from tests._overlay_fake import FakeWin32  # noqa: E402

FULL = (0, 0, 1920, 1080)
WORK = (0, 0, 1920, 1040)  # a 40 px taskbar along the bottom
TRAY = 9001


def make(tray: dict | None = None, autohide: bool = False, work: tuple = WORK) -> FakeWin32:
    fake = FakeWin32()
    fake.monitor_list = [(work, 96)]
    fake.monitor_full = [FULL]
    fake.autohide = autohide
    if tray is not None:
        fake.window_list[TRAY] = tray
    return fake


def bottoms(fake: FakeWin32) -> list[int]:
    return [area[3] for area, _dpi in k.monitors(fake)]


def test_a_visible_taskbar_keeps_the_work_area() -> None:
    assert bottoms(make({"rect": (0, 1040, 1920, 1080), "title": "tray"})) == [1040]


def test_a_taskbar_set_to_auto_hide_gives_the_floor_back() -> None:
    assert bottoms(make({"rect": (0, 1040, 1920, 1080), "title": "tray"}, autohide=True)) == [1080]


def test_a_taskbar_hidden_by_a_tool_gives_the_floor_back_while_the_strip_is_still_reserved() -> None:
    assert bottoms(make({"rect": (0, 1040, 1920, 1080), "title": "tray", "visible": False})) == [1080]


def test_no_taskbar_window_at_all_frees_the_bottom_strip_only() -> None:
    assert [a for a, _d in k.monitors(make(None))] == [(0, 0, 1920, 1080)]


def test_a_hidden_side_taskbar_frees_its_own_side_and_a_dock_elsewhere_stays() -> None:
    work = (60, 0, 1920, 1000)  # a taskbar down the left (60 px) and a dock along the bottom (80 px)
    area = k.monitors(make({"rect": (0, 0, 60, 1080), "title": "tray", "visible": False}, work=work))[0][0]
    assert area == (0, 0, 1920, 1000)


def test_a_monitor_the_shell_cannot_describe_is_left_alone() -> None:
    fake = make({"rect": (0, 1040, 1920, 1080), "title": "tray", "visible": False})
    fake.monitor_full = [(0, 0, 0, 0)]
    assert bottoms(fake) == [1040]


def test_the_runner_reads_the_work_areas_again_every_few_seconds_and_refreshes_only_on_a_change() -> None:
    from types import SimpleNamespace

    from tessellate.core.overlay import engine as eng
    from tessellate.core.overlay import runner

    fake = make({"rect": (0, 1040, 1920, 1080), "title": "tray"})
    refreshed: list[int] = []
    me = SimpleNamespace(
        k=k, w=fake, monitors=[eng.Monitor(WORK, 96)], _next_taskbar=0.0, _refresh_monitors=lambda: refreshed.append(1),
    )
    watch = runner.OverlayRunner._watch_taskbar
    watch(me, 10.0)
    assert refreshed == []  # nothing changed
    fake.window_list[TRAY]["visible"] = False  # a hider tool hides the taskbar
    watch(me, 12.0)
    assert refreshed == []  # read again only every TASKBAR_EVERY
    watch(me, 10.0 + runner.TASKBAR_EVERY)
    assert refreshed == [1]
