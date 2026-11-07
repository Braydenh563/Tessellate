"""The desk size handle (INBOX 1683 r, "I cant resize the desktop companion like I can on the in-app one"):
the figure's size follows the app's 0.7 to 1.6, a handle on hover pulls it, a double press resets it,
the window is resized once per step and the frame cache stays small. Fake `win32`, fixed clock; real
Windows and X11 behaviour is not measured here."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import sizing  # noqa: E402
from tessellate.core.overlay import sprites  # noqa: E402
from tests.test_overlay_roam_runner import started, tick  # noqa: E402
from tests.test_overlay_runner import FRAMES  # noqa: E402


def stand(r, clock):
    r.paused = False
    """Still, on the floor, with the pointer over it so the handle shows."""
    e = r.engine
    e.state, e.goal = "stand", None
    e.last_active = clock.t
    tick(r, clock, 0.05, 20, pointer=(5, 5))
    e.state = "stand"
    return e


def over_figure(r):
    x, y, w, h = r.drawn_rect(r.engine.x, r.engine.y, "stand", False)
    return int(x + w / 2), int(y + h / 2)


def show_handle(r, clock):
    px, py = over_figure(r)
    clock.t += 0.05
    r._on_event("move", px, py)
    return r._hit_screen()


def test_the_figure_box_follows_the_apps_ratio_at_every_step() -> None:
    s = sprites.SpriteSet("masculine", FRAMES)
    base = s.frame("stand", round(96 * 1.0), False).box
    base_w = base[2] - base[0]
    worst = 0.0
    for step in (0.7, 0.8, 1.0, 1.3, 1.6):
        f = s.frame("stand", round(96 * step), False)
        worst = max(worst, abs((f.box[2] - f.box[0]) / base_w / step - 1))
    assert worst < 0.02, worst


def test_a_pull_is_the_apps_formula_and_clamped_to_its_range() -> None:
    assert sizing.pulled(1.0, 50, 150, 96) == pytest.approx(2.0)
    assert sizing.clamp(9) == 1.6 and sizing.clamp(0.1) == 0.7 and sizing.clamp("x") == 1.0
    assert sizing.clamp(1.0237) == 1.05 or sizing.clamp(1.0237) == 1.0


@pytest.mark.parametrize("hanging", [False, True])
def test_the_hit_box_is_at_least_24_px_inside_the_canvas_and_off_the_corner(hanging) -> None:
    s = sprites.SpriteSet("masculine", FRAMES)
    for dpi in (96, 144, 192):
        f = s.frame("hang" if hanging else "stand", dpi, False)
        hit = sizing.hit_box(f.box, hanging, dpi)
        drawn, hit = sizing.with_handle(f, hit, False)
        assert hit[2] - hit[0] >= 24 and hit[3] - hit[1] >= 24
        assert 0 <= hit[0] and hit[2] <= drawn.width and 0 <= hit[1] and hit[3] <= drawn.height  # inside the window
        alpha = drawn.bgra[3::4]
        assert all(alpha[y * drawn.width + x] >= sprites.ALPHA_FLOOR for y in (hit[1], hit[3] - 1) for x in (hit[0], hit[2] - 1))
        gap = round(2 * dpi / 96)
        assert hit[0] - drawn.box[2] == gap  # off the figure's corner by 2 px (scaled)
        assert (hit[1] - drawn.box[3] == gap) if hanging else (drawn.box[1] - hit[3] == gap)  # bottom right hanging, top right standing


def test_a_drag_resizes_the_window_once_per_step_and_keeps_the_cache_small() -> None:
    r, fake, clock, _ = started(reduced=True)  # no bob: the feet are a number
    e = stand(r, clock)
    rect = show_handle(r, clock)
    assert rect is not None and rect[2] - rect[0] >= 24 and rect[3] - rect[1] >= 24
    hx, hy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
    x0, y0, w0, h0 = r.drawn_rect(e.x, e.y, "stand", False)
    feet = (x0 + w0 / 2, y0 + h0 + e._dy("stand"))  # the engine draws the figure its rest margin lower, so the soles are on the floor
    r._on_event("down", hx, hy)
    assert r._sizing is not None
    before, steps = r.resizes, set()
    for i in range(1, 61):  # 60 pointer moves out along the diagonal
        clock.t += 0.01
        r._on_event("move", hx + i * 4, hy - i * 4)
        steps.add(r.scale)
    r._on_event("up", hx + 240, hy - 240)
    assert r.scale == 1.6, r.scale  # clamped at the app's largest
    assert r.resizes - before == len(steps), (r.resizes - before, len(steps))
    assert r.resizes - before <= round((1.6 - 1.0) / sizing.STEP)  # one per step, never one per pixel
    assert len(r.sprites._cache) <= 50 and {k[1] for k in r.sprites._cache} <= {r._fdpi()}
    tick(r, clock, 0.05, 3)
    x1, y1, w1, h1 = r.drawn_rect(e.x, e.y, "stand", False)
    assert w1 / w0 == pytest.approx(1.6, rel=0.02)
    assert abs((x1 + w1 / 2) - feet[0]) <= 2 and abs((y1 + h1 + e._dy("stand")) - feet[1]) <= 2  # the feet stay where they were
    r.stop()


def test_a_double_press_eases_back_to_medium_and_reports_the_size() -> None:
    r, fake, clock, _ = started()
    saved = []
    r.on_size = saved.append
    r.scale = 1.3
    r._set_scale(1.3)
    stand(r, clock)
    rect = show_handle(r, clock)
    hx, hy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
    r._on_event("down", hx, hy)
    r._on_event("up", hx, hy)
    assert r.scale == 1.3 and saved == []  # one press that never pulled keeps the size
    clock.t += 0.2
    r._on_event("down", hx, hy)
    assert r._goal == 1.0
    seen = []
    for _ in range(12):
        tick(r, clock, 0.02)
        seen.append(r.scale)
    assert seen[-1] == 1.0 and r.scale == 1.0 and r.resizes >= 6  # eased in steps, not jumped
    assert all(abs(a - b) <= sizing.STEP + 1e-9 for a, b in zip(seen, seen[1:]))
    assert saved == [1.0]
    r.stop()


def test_the_handle_goes_when_the_pointer_has_gone_and_clear_pixels_stay_click_through() -> None:
    r, fake, clock, _ = started()
    stand(r, clock)
    assert show_handle(r, clock) is not None
    clock.t += sizing.SHOW_S + 0.5
    tick(r, clock, 0.1)
    assert r._hit is None
    r.stop()


def test_the_scale_comes_from_the_apps_size_and_a_new_one_is_eased_to() -> None:
    r, fake, clock, _ = started(scale=0.8)
    assert r.scale == 0.8 and r._fdpi() == round(96 * 0.8)
    r.set_scale(1.6)
    assert r._goal == 1.6
    r.stop()


def test_a_hanging_figure_keeps_its_hands_on_the_edge_through_every_size() -> None:
    from tests.test_overlay_hang import SHARE, SIZE, make as hang_engine, run_to

    e = hang_engine()
    e._perform("hang", 1.0)
    run_to(e, "hang")
    centre = e.x + SIZE[0] / 2
    for scale in (1.3, 1.6, 0.7, 1.0):
        size = (round(SIZE[0] * scale), round(SIZE[1] * scale))
        e.resize(size, {})
        assert e.size == size and e.y + SHARE * size[1] == pytest.approx(0.0, abs=0.01)  # hands on the top of the work area
        assert e.x + size[0] / 2 == pytest.approx(centre, abs=1)
