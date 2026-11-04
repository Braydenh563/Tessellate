"""Window, engine and frames joined (BACKLOG 16, O4): the runner on a fake `win32`."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import runner as runner_mod  # noqa: E402
from tessellate.core.overlay import win32 as k  # noqa: E402
from tests._overlay_fake import FakeWin32  # noqa: E402

FRAMES = Path(__file__).resolve().parent.parent / "frontend" / "img" / "desk"


def wait_for(cond: Any, timeout: float = 2.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.005)
    return False


class Clock:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


def make(fake: FakeWin32 | None = None, **kw: Any):
    fake = fake or FakeWin32()
    clicks: list[Any] = []
    settled: list[Any] = []
    clock = Clock()
    kw.setdefault("home", (800, 920))
    r = runner_mod.OverlayRunner(
        w=fake, clock=clock, frames=FRAMES, on_click=lambda *a: clicks.append(a), on_settle=lambda x, y: settled.append((x, y)),
        dispatch=lambda name, fn: fn(), **kw,
    )
    return r, fake, clock, clicks, settled


def test_start_builds_everything_on_the_overlay_thread_and_draws_the_first_frame(caplog) -> None:
    caplog.set_level("INFO", logger=runner_mod.logger.name)
    r, fake, *_ = make()
    assert r.start()
    assert r.engine is not None and r.sprites is not None and fake.layered
    assert fake.layered[0]["flags"] == k.ULW_ALPHA
    assert any("overlay: ready, look=masculine" in rec.getMessage() and "frames=16" in rec.getMessage() for rec in caplog.records)
    assert not r.visible and "ShowWindow" not in fake.names()
    r.stop()


def test_missing_frames_fail_the_start_so_the_card_window_is_used(tmp_path) -> None:
    fake = FakeWin32()
    r = runner_mod.OverlayRunner(w=fake, frames=tmp_path, dispatch=lambda n, f: f())
    assert r.start() is False
    assert r.host is None


def test_a_missing_monitor_list_fails_the_start() -> None:
    fake = FakeWin32()
    fake.monitor_list = []
    r = runner_mod.OverlayRunner(w=fake, frames=FRAMES, dispatch=lambda n, f: f())
    assert r.start() is False


def test_show_draws_the_window_and_ticks_start_walking() -> None:
    r, fake, clock, *_ = make()
    assert r.start()
    r.show()
    assert wait_for(lambda: "ShowWindow" in fake.names())
    assert wait_for(lambda: fake.timers.get(1) is not None)  # a tick was asked for
    before = len(fake.layered)
    for _ in range(40):
        clock.t += 0.033
        fake.post(k.WM_TIMER)
        time.sleep(0.002)
    r.engine._enter("walk", clock.t)
    r.engine.facing = 1
    for _ in range(40):
        clock.t += 0.033
        fake.post(k.WM_TIMER)
    assert wait_for(lambda: len(fake.layered) > before + 3 or any(fn == "SetWindowPos" for _, fn, _ in fake.calls))
    r.stop()


def test_a_click_on_the_figure_is_handed_to_a_worker_with_its_rect() -> None:
    r, fake, clock, clicks, _ = make()
    assert r.start()
    r.show()
    fake.cursor = (850, 950)
    fake.post(k.WM_LBUTTONDOWN)
    fake.post(k.WM_LBUTTONUP)
    assert wait_for(lambda: clicks)
    kind, rect, dpi = clicks[0]
    assert kind == "left" and dpi == 96 and rect[2] > 20 and rect[3] > 20
    r.stop()


def test_a_drop_reports_where_it_settled() -> None:
    r, fake, clock, clicks, settled = make()
    assert r.start()
    r.show()
    fake.cursor = (850, 950)
    fake.post(k.WM_LBUTTONDOWN)
    assert wait_for(lambda: r.engine.state == "pressed")
    fake.cursor = (900, 950)
    fake.post(k.WM_MOUSEMOVE)
    assert wait_for(lambda: r.engine.state == "held")
    fake.post(k.WM_LBUTTONUP)
    assert wait_for(lambda: settled)
    assert not clicks
    r.stop()


def test_fullscreen_hides_it_and_leaving_shows_it_again(caplog) -> None:
    caplog.set_level("INFO", logger=runner_mod.logger.name)
    r, fake, clock, *_ = make()
    assert r.start()
    r.show()
    assert wait_for(lambda: r.host.visible)
    fake.notification = k.QUNS_D3D_FULL_SCREEN
    clock.t += 5
    fake.post(k.WM_TIMER)
    assert wait_for(lambda: r.busy)
    assert wait_for(lambda: not r.host.visible)
    assert fake.timers[1] == 2000
    fake.notification = 5
    clock.t += 3
    fake.post(k.WM_TIMER)
    assert wait_for(lambda: not r.busy and r.host.visible)
    assert any("shown again" in rec.getMessage() for rec in caplog.records)
    r.stop()


def test_suspend_pauses_and_resume_continues_without_a_jump() -> None:
    r, fake, clock, *_ = make()
    assert r.start()
    r.show()
    r.engine._enter("walk", clock.t)
    r.engine.facing = 1
    fake.post(k.WM_POWERBROADCAST, k.PBT_APMSUSPEND)
    assert wait_for(lambda: r.paused)
    x = r.engine.x
    clock.t += 3600
    fake.post(k.WM_TIMER)
    time.sleep(0.05)
    assert r.engine.x == x
    fake.post(k.WM_POWERBROADCAST, k.PBT_APMRESUMEAUTOMATIC)
    assert wait_for(lambda: not r.paused)
    assert wait_for(lambda: abs(r.engine.x - x) < 10)
    r.stop()


def test_a_display_change_rereads_monitors_and_rescales_the_frames() -> None:
    r, fake, clock, *_ = make()
    assert r.start()
    r.show()
    first = r.sprites.size(96)
    fake.monitor_list = [((0, 0, 2560, 1400), 192)]
    fake.post(k.WM_DISPLAYCHANGE)
    assert wait_for(lambda: r.dpi == 192)
    assert r.engine.size == r.sprites.size(192) != first
    assert wait_for(lambda: fake.layered[-1]["size"] == r.sprites.size(192))
    assert r.engine.y == 1400 - r.engine.size[1]
    r.stop()


def test_reduced_motion_follows_the_system_animation_setting() -> None:
    fake = FakeWin32()
    fake.animations = 0
    r, *_ = make(fake)
    assert r.start()
    assert r.engine.reduced and r.engine.update(101.0).frame == "sit"
    r.stop()


def test_hide_and_stop() -> None:
    r, fake, *_ = make()
    assert r.start()
    r.show()
    assert wait_for(lambda: r.host.visible)
    r.hide()
    assert wait_for(lambda: not r.host.visible)
    host = r.host
    r.stop()
    assert r.host is None and not host.alive


def test_a_thread_that_dies_after_a_good_start_is_reported_once_and_a_stop_is_not() -> None:
    died: list[int] = []
    r, fake, *_ = make(on_died=lambda: died.append(1))
    assert r.start()
    fake.post(k.WM_QUIT)
    assert wait_for(lambda: died)
    assert died == [1]
    r.stop()
    r2, _fake2, *_ = make(on_died=lambda: died.append(2))
    assert r2.start()
    r2.stop()
    time.sleep(0.05)
    assert died == [1]
