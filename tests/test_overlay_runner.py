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
    assert any("overlay: ready, look=masculine" in rec.getMessage() and f"frames={len(runner_mod.sprites.FRAME_NAMES)}" in rec.getMessage() for rec in caplog.records)
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
    assert r.engine.y == r.engine.ground_y() == 1400 - r.engine.size[1] - r.engine.hover * 2
    r.stop()


def test_reduced_motion_follows_the_system_animation_setting() -> None:
    fake = FakeWin32()
    fake.animations = 0
    r, *_ = make(fake)
    assert r.start()
    assert r.engine.reduced and r.engine.update(101.0).frame == "sit"
    r.stop()


def test_the_apps_answer_beats_the_windows_flag_and_no_answer_falls_back_to_it() -> None:
    fake = FakeWin32()
    fake.animations = 0
    r, *_ = make(fake, reduced=False)  # the app says it may move
    assert r.start() and not r.engine.reduced
    r.stop()
    fake = FakeWin32()
    r, *_ = make(fake, reduced=True, reduced_reason="app")
    assert r.start() and r.engine.reduced and r.reduced_reason == "app"
    r.stop()
    fake = FakeWin32()
    fake.animations = 0
    r, *_ = make(fake)  # None: no answer
    assert r.start() and r.engine.reduced and r.reduced_reason == "os"
    r.stop()


def _pump(r, fake, clock, seconds: float, until=None) -> float:
    """Fire the timer the overlay asked for, in fake time: each WM_TIMER is posted
    after the clock moved by the asked-for wait. Returns the fake seconds used."""
    used = 0.0
    while used < seconds:
        if not wait_for(lambda: fake.timers.get(1) is not None, 0.5):
            break
        ms = fake.timers.pop(1)
        clock.t += ms / 1000
        used += ms / 1000
        fake.post(k.WM_TIMER)
        time.sleep(0.01)
        if until and until():
            break
    return used


def test_a_moving_figure_keeps_asking_for_ticks_and_changes_frame_or_place() -> None:
    """Owner report 2026-11-04 (a, b): rule out that the moving path is also stuck.
    After start and show the host must be asked for a wake, and each answer must
    ask for the next, so within a few fake seconds the figure blinks, looks or walks."""
    r, fake, clock, *_ = make(reduced=False)
    assert r.start()
    r.show()
    assert wait_for(lambda: r.host.visible)
    seen = {r._last_key}
    places = {r._last_pos}
    _pump(r, fake, clock, 60.0, until=lambda: len({key[0] for key in seen if key}) > 1 or len(places) > 1)
    seen.add(r._last_key)
    places.add(r._last_pos)
    assert len({key[0] for key in seen if key}) > 1 or len(places) > 1, (seen, places)
    r.stop()


def test_a_drop_in_mid_air_falls_with_ticks_to_the_floor() -> None:
    r, fake, clock, clicks, settled = make(reduced=False)
    assert r.start()
    r.show()
    assert wait_for(lambda: r.host.visible)
    fake.cursor = (850, 950)
    fake.post(k.WM_LBUTTONDOWN)
    assert wait_for(lambda: r.engine.state == "pressed")
    fake.cursor = (900, 300)
    fake.post(k.WM_MOUSEMOVE)
    assert wait_for(lambda: r.engine.state == "held")
    fake.post(k.WM_LBUTTONUP)
    assert wait_for(lambda: r.engine.state in ("fall", "fly"))
    assert wait_for(lambda: fake.timers.get(1) is not None)  # a fall asks for ticks
    _pump(r, fake, clock, 10.0, until=lambda: bool(settled))
    assert settled and abs(r.engine.y - r.engine.ground_y()) < 1  # Atlas hovers: its rest height
    r.stop()


def test_a_still_figure_dropped_in_mid_air_is_on_the_floor_at_once() -> None:
    r, fake, clock, clicks, settled = make(reduced=True, reduced_reason="setting")
    assert r.start()
    r.show()
    assert wait_for(lambda: r.host.visible)
    fake.cursor = (850, 950)
    fake.post(k.WM_LBUTTONDOWN)
    assert wait_for(lambda: r.engine.state == "pressed")
    fake.cursor = (900, 300)
    fake.post(k.WM_MOUSEMOVE)
    assert wait_for(lambda: r.engine.state == "held")
    fake.post(k.WM_LBUTTONUP)
    assert wait_for(lambda: settled)
    assert r.engine.y == r.engine.ground_y() and abs(settled[0][1] - r.engine.ground_y()) < 1
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


def test_a_stop_before_the_thread_reports_its_end_is_never_a_death() -> None:
    died: list[int] = []
    r, *_ = make(on_died=lambda: died.append(1))
    r.stop()
    r._exited()
    time.sleep(0.05)
    assert died == []


def test_a_thrown_figure_is_drawn_rotated_on_a_bigger_canvas_and_a_peek_is_drawn_clipped() -> None:
    r, fake, clock, *_ = make(reduced=False)
    assert r.start()
    r.show()
    assert wait_for(lambda: r.host.visible)
    assert r.engine.gait == "float"  # Atlas
    r.paused = True  # the test drives the engine itself, not the window's timer
    engine = r.engine
    w, h = r.sprites.size(96)
    engine.y = 100.0
    engine._enter("fly", clock.t)
    engine.vx, engine.vy = 300.0, 0.0  # INBOX 1670: a figure under FLY_SPIN_MIN stops tumbling, so it needs some speed
    engine.angle = 1.0
    r._apply(engine.update(clock.t + 0.01))
    side = r.sprites.frame("spin1", 96)
    assert r._last_key[0].startswith("spin") and side.width > w
    assert wait_for(lambda: fake.layered[-1]["size"] == (side.width, side.height))
    # sunk behind the bottom edge: the hidden rows are drawn clear
    engine._enter("peek", clock.t)
    engine.peek_edge, engine.sink_max, engine.peek_started = "bottom", 0.65, clock.t - 1.5
    engine.y = engine.floor_y()
    out = engine.update(clock.t + 0.02)
    r._apply(out)
    # the window is drawn its foot offset lower (INBOX 1670), so the cut is that much higher
    assert out.clip == (0, 0, w, h - round(0.65 * h) - round(engine._dy(out.frame))) and r._last_key[3] == out.clip
    r.stop()


def test_typing_keeps_the_engine_quiet_and_an_unknown_input_age_does_not() -> None:
    r, fake, clock, *_ = make(reduced=False)
    assert r.start()
    r.show()
    assert wait_for(lambda: r.host.visible)
    assert r.engine.quiet is False  # the fake cannot say: not quiet
    fake.last_input = (10_000, 9_000)  # tick, last input: 1 s ago
    clock.t += 5
    r._next_busy_check = 0.0
    r._busy_gate(clock.t)
    assert r.engine.quiet is True
    fake.last_input = (10_000, 1_000)
    r._next_busy_check = 0.0
    r._busy_gate(clock.t)
    assert r.engine.quiet is False
    r.stop()


def test_the_engine_is_given_the_hang_frames_measured_top_margin() -> None:
    r, *_ = make()
    assert r.start()
    try:
        assert r.engine.hang_top == pytest.approx(r.sprites.top_share("hang")) and 0.1 < r.engine.hang_top < 0.3
    finally:
        r.stop()


def test_the_click_rect_is_the_figures_drawn_box_not_the_window() -> None:
    """INBOX 1663: the quick panel sat 30 to 160 px from the figure because it was placed from
    the window cell, whose transparent margin varies by pose and mirror."""
    r, fake, clock, clicks, _ = make(look="feminine")
    assert r.start()
    spr = r.sprites
    cell = spr.size(96)
    for flip in (False, True):
        x, y, w, h = r.drawn_rect(1000, 500, "stand", flip)
        f = spr.frame("stand", 96, flip)
        assert (w, h) == (f.box[2] - f.box[0], f.box[3] - f.box[1])
        assert (x - 1000, y - 500) == (f.box[0], f.box[1])
        assert w < cell[0] * 0.75 and x + w <= 1000 + cell[0]
    left = r.drawn_rect(1000, 500, "stand", False)[0] - 1000
    right = r.drawn_rect(1000, 500, "stand", True)[0] - 1000
    assert left != right  # the margin really swings with the mirror
    r.stop()


def test_a_moving_mouse_is_not_typing() -> None:
    # INBOX 1670: GetLastInputInfo counts mouse moves, so a person using the mouse
    # kept the figure "typing-quiet" and it never travelled.
    r, fake, clock, *_ = make(reduced=False)
    assert r.start()
    r.show()
    assert wait_for(lambda: r.host.visible)
    fake.last_input = (10_000, 9_000)  # an input 1 s ago
    clock.t += 5
    r._next_busy_check = 0.0
    r._busy_gate(clock.t, (100, 100))
    r._next_busy_check = 0.0
    clock.t += 0.5
    r._busy_gate(clock.t, (180, 140))  # the pointer moved: that input was the mouse
    assert r.engine.quiet is False
    r._next_busy_check = 0.0
    clock.t += 3
    r._busy_gate(clock.t, (180, 140))  # still pointer, a fresh input: a key
    assert r.engine.quiet is True
    r.stop()
