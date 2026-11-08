"""The desk size handle after its independent review (INBOX 1683 r, 1692 h): a pull is not undone by a sync, the figure
is held still for it, a lost release ends it, a dpi change ends it, the handle stays on screen and on the figure, and a
drag of the figure shows no handle. Fake `win32`, fixed clock; real Windows and X11 are not measured here."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import sizing  # noqa: E402
from tessellate.core.overlay.sprites import Frame, premultiplied_bgra  # noqa: E402
from tests.test_overlay_roam_runner import started, tick  # noqa: E402
from tests.test_overlay_size_1107 import over_figure, show_handle, stand  # noqa: E402


def press_handle(r, clock):
    rect = show_handle(r, clock)
    hx, hy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
    r._on_event("down", hx, hy)
    return hx, hy


def pull_out(r, clock, hx, hy, n=12):
    for i in range(1, n + 1):
        clock.t += 0.01
        r._on_event("move", hx + i * 4, hy - i * 4)


def test_a_sync_during_or_just_after_a_pull_does_not_walk_the_size_back() -> None:
    r, fake, clock, _ = started(reduced=True)
    saved = []
    r.on_size = saved.append
    stand(r, clock)
    hx, hy = press_handle(r, clock)
    pull_out(r, clock, hx, hy)
    pulled = r.scale
    assert pulled > 1.0
    r.set_scale(1.0)  # the page still has the old size mid-pull
    assert r._goal is None and r.scale == pulled
    r._on_event("up", hx + 48, hy - 48)
    assert saved == [pulled]
    r.set_scale(1.0)  # a sync before the write-back reached the page
    tick(r, clock, 0.05, 5)
    assert r.scale == pulled and r._goal is None
    r.set_scale(pulled)  # the page caught up
    clock.t += sizing.PENDING_S + 1
    r.set_scale(1.0)  # a real change from Appearance, later
    assert r._goal == 1.0
    r.stop()


def test_a_press_on_the_handle_drops_a_size_the_figure_was_easing_to() -> None:
    r, fake, clock, _ = started()
    stand(r, clock)
    r._goal = 1.6
    press_handle(r, clock)
    assert r._goal is None
    r.stop()


def test_the_engine_is_held_still_for_the_whole_pull_and_goes_on_after() -> None:
    r, fake, clock, _ = started(reduced=True)
    e = stand(r, clock)
    calls = []
    real = e.update
    e.update = lambda *a, **k: (calls.append(a), real(*a, **k))[1]
    hx, hy = press_handle(r, clock)
    calls.clear()  # the hover move before the press was the engine's
    at = (e.state, e.now)  # the resize itself moves x and y (feet kept), nothing else does
    pull_out(r, clock, hx, hy)
    tick(r, clock, 0.1, 10)
    assert calls == [] and (e.state, e.now) == at
    r._on_event("up", hx + 48, hy - 48)
    clock.t += 0.05
    tick(r, clock, 0.05)
    assert calls and e.now == pytest.approx(clock.t)  # time was not caught up, it went on from the release
    r.stop()


def test_a_press_after_a_resize_knows_the_figure_hangs_or_stands() -> None:
    r, fake, clock, _ = started(reduced=True)
    stand(r, clock)
    show_handle(r, clock)
    r._last_key = None  # what a resize leaves until the next picture
    r._shown = ("hang", False)
    rect = r._hit_screen()
    box = r.drawn_rect(*r._last_pos)
    r._on_event("down", (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2)
    assert r._sizing is not None and r._sizing["origin"][1] == box[1]  # hands on the top edge, not the feet
    r.stop()


def test_a_release_that_never_comes_ends_the_pull_and_keeps_what_was_pulled() -> None:
    r, fake, clock, _ = started(reduced=True)
    saved = []
    r.on_size = saved.append
    stand(r, clock)
    hx, hy = press_handle(r, clock)
    assert r._handle_wake(None, True, clock.t) <= 1000  # ticks go on to notice
    pull_out(r, clock, hx, hy)
    pulled = r.scale
    clock.t += sizing.PULL_IDLE_S + 1
    r._system("tick", clock.t, (900, 300))
    assert r._sizing is None and saved == [pulled]
    r.stop()


def test_a_pull_that_never_moved_and_never_ended_saves_nothing() -> None:
    r, fake, clock, _ = started(reduced=True)
    saved = []
    r.on_size = saved.append
    stand(r, clock)
    press_handle(r, clock)
    clock.t += sizing.PULL_IDLE_S + 1
    r._system("tick", clock.t, (900, 300))
    assert r._sizing is None and saved == []
    r.stop()


def test_a_display_change_to_another_dpi_ends_the_pull() -> None:
    r, fake, clock, _ = started(reduced=True)
    saved = []
    r.on_size = saved.append
    stand(r, clock)
    hx, hy = press_handle(r, clock)
    pull_out(r, clock, hx, hy)
    fake.monitor_list = [((0, 0, 2560, 1400), 192)]
    r._system("display", clock.t, (900, 300))
    assert r._sizing is None and len(saved) == 1
    r.stop()


def test_a_drag_of_the_figure_leaves_no_handle_behind() -> None:
    r, fake, clock, _ = started(reduced=True)
    stand(r, clock)
    show_handle(r, clock)
    px, py = over_figure(r)
    r._on_event("down", px, py)
    for i in range(1, 8):
        clock.t += 0.02
        r._on_event("move", px + i * 5, py)
    r._on_event("up", px + 35, py)
    tick(r, clock, 0.05, 3, pointer=(px + 35, py))
    assert r._hit is None and r._hit_screen() is None  # hover only: a release is not a hover
    clock.t += 0.05
    r._on_event("move", px + 36, py)  # until the pointer moves again over it
    assert r._hover_until > clock.t
    r.stop()


def test_at_the_right_edge_the_handle_flips_to_the_left_corner_inside_the_screen(monkeypatch) -> None:
    monkeypatch.setattr(sizing, "HIT_PX", 60)  # a handle the frame's margin cannot hold, so the canvas must grow
    r, fake, clock, _ = started(reduced=True)
    e = stand(r, clock)
    area = e.current_monitor().area
    e.x = area[2] - e.size[0]
    e._place_on_floor()
    tick(r, clock, 0.05, 20, pointer=(5, 5))
    show_handle(r, clock)
    t, at = r._target, r._last_pos
    assert at[0] - t.pad_x + t.width <= area[2]  # the grown window is still on the monitor
    # Intent moved (INBOX 1692 h): the handle hangs by the figure's solid corner, not its drawn box, whose faint nebula
    # stream can reach 10 px further left than the head (measured 29 against 39 at 96 dpi): the handle is left of the corner.
    base = r.sprites.frame(r._shown[0], r._fdpi(), r._shown[1])
    assert r._hit[2] <= sizing.corner_box(base, False)[0] + (t.pad_x - base.pad_x)  # on the figure's left corner
    r.stop()
    r, fake, clock, _ = started(reduced=True)
    stand(r, clock)
    show_handle(r, clock)
    # Intent moved (INBOX 1692, 2026-11-08): the ring hangs by the head, which can lie inside the drawn box's right
    # edge (a tail swirl widens it); mid-screen it still stays on the right side.
    assert r._hit[0] >= (r._target.box[0] + r._target.box[2]) / 2  # mid-screen it stays on the right
    r.stop()


def test_the_handle_sits_on_the_solid_corner_not_on_a_faint_halo() -> None:
    """INBOX 1692 h: the dot was 120 px from the figure. A faint glow past the figure (alpha above the hit floor
    but nearly clear) must not move the handle: it is anchored to the figure's solid corner."""
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 20, 270, 290), fill=(99, 99, 99, 20))  # the halo
    draw.rectangle((100, 120, 180, 260), fill=(200, 100, 50, 255))  # the figure
    frame = Frame(300, 300, premultiplied_bgra(image), 0, 0, (40, 20, 271, 291))
    box = sizing.solid_box(frame)
    assert box == (100, 120, 181, 261)
    hit = sizing.hit_box(box, False, 96)
    drawn, hit = sizing.with_handle(frame, hit, False)
    sx, sy = 181 + drawn.pad_x, 120 + drawn.pad_y  # the figure's corner in the grown canvas
    assert 0 <= hit[0] - sx <= 16, (hit, sx)
    assert 0 <= sy - hit[3] <= 16, (hit, sy)
