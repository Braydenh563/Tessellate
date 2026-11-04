"""Throw, float, hang and peek (owner, 2026-11-04) on a fake clock with seeded randomness."""

from __future__ import annotations

import math
import random

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay.engine import Engine, Monitor

SIZE = (100, 120)
ONE = [Monitor((0, 0, 1920, 1040), 96)]
FLOOR = 1040 - 120


def make(monitors=None, seed=7, **kw) -> Engine:
    kw.setdefault("home", (800, FLOOR))
    return Engine(SIZE, monitors or ONE, rng=random.Random(seed), **kw)


def throw(e: Engine, to=(1500, 500), start=(850, 950), t0=1.0, gap=0.016, steps=4):
    """Carry along a straight line at a steady pace, release at the end."""
    e.update(t0, event=("down", *start))
    t = t0
    for i in range(1, steps + 1):
        t = t0 + gap * i
        px = start[0] + (to[0] - start[0]) * i / steps
        py = start[1] + (to[1] - start[1]) * i / steps
        e.update(t, event=("move", int(px), int(py)))
    return e.update(t + 0.001, event=("up", *to)), t + 0.001


def step(e: Engine, t: float, seconds: float, dt: float = 0.016):
    end, outs = t + seconds, []
    while t < end:
        t += dt
        outs.append(e.update(t))
    return t, outs


# --- throw ---------------------------------------------------------------------------

def test_a_quick_release_leaves_with_the_pointers_velocity_and_spins() -> None:
    e = make()
    out, t = throw(e, to=(1450, 450))
    assert e.state == "fly" and out.frame.startswith("spin") and e.vx > 0 and e.vy < 0
    t, outs = step(e, t, 0.6)
    assert len({o.frame for o in outs if o.frame.startswith("spin")}) >= 3
    assert all(o.wake_ms == eng.TICK_FALL_MS for o in outs if e.state == "fly")


def test_a_throw_is_clamped_and_a_slow_release_is_a_plain_drop() -> None:
    e = make()
    throw(e, to=(1900, 50), gap=0.001)
    assert math.hypot(e.vx, e.vy) <= eng.THROW_MAX * 1.001
    slow = make()
    slow.update(1.0, event=("down", 850, 950))
    slow.update(1.01, event=("move", 1010, 300))
    out = slow.update(1.6, event=("up", 1010, 300))
    assert slow.state == "fall" and out.frame == "fall" and slow.vx == 0
    gentle = make()
    gentle.update(1.0, event=("down", 850, 950))
    gentle.update(1.05, event=("move", 860, 940))
    gentle.update(1.1, event=("up", 865, 935))  # 10 px in 50 ms: under THROW_MIN
    assert gentle.state == "fall"


def test_the_throw_threshold_scales_with_dpi() -> None:
    px_per_s = eng.THROW_MIN * 1.5  # a throw at 96 dpi, under the line at 192

    def release(monitor):
        e = make([monitor], home=(800, monitor.area[3] - 120))
        e.update(1.0, event=("down", 850, monitor.area[3] - 60))
        e.update(1.01, event=("move", 850, 400))
        e.update(1.5, event=("move", 850, 400))
        e.update(1.55, event=("up", 850 + int(px_per_s * 0.05), 400))
        return e.state

    assert release(Monitor((0, 0, 1920, 1040), 96)) == "fly"
    assert release(Monitor((0, 0, 3840, 2080), 192)) == "fall"


def test_a_thrown_walker_flies_under_gravity_and_lands_on_the_floor() -> None:
    e = make()
    out, t = throw(e, to=(1100, 500), start=(850, 600))
    t, outs = step(e, t, 4.0)
    assert any(o.settled for o in outs)
    assert outs[-1].y == FLOOR
    assert "fall" not in {o.frame for o in outs}
    land = next(o for o in outs if o.settled)
    assert land.frame == "land" and 0 <= land.x <= 1920 - 100


def test_a_throw_bounces_off_the_wall_with_damping_and_a_short_startle() -> None:
    e = make()
    throw(e, to=(1800, 600), start=(850, 950))
    assert e.state == "fly" and e.vx > 0
    t, bonk, vx_in, vx_out = 1.1, None, None, None
    while t < 3.0:
        before = e.vx
        t += 0.016
        out = e.update(t)
        if out.frame == "hop" and bonk is None:
            bonk, vx_in, vx_out = t, before, e.vx
    assert bonk is not None and vx_in > 0 > vx_out
    assert abs(vx_out) <= abs(vx_in) * eng.BOUNCE_DAMP * 1.2
    assert e.x <= 1920 - 100


def test_a_throw_that_hits_the_ceiling_hangs_then_lets_go_and_falls() -> None:
    e = make()
    out, t = throw(e, to=(900, 100), start=(850, 600))
    seen, frames = False, []
    while t < 40 and not (seen and e.state in ("land", "stand")):
        t += 0.016
        out = e.update(t)
        frames.append(out.frame)
        if e.state == "hang":
            seen = True
            assert out.y == 0 and out.frame == "hang"
    assert seen and "fall" in frames
    assert e.y == FLOOR


def test_a_dropped_hang_click_lets_go() -> None:
    e = make()
    e.y = 0.0
    e._enter("hang", 1.0)
    e.update(1.0)
    e.update(1.1, event=("down", 850, 20))
    out = e.update(1.2, event=("up", 850, 20))
    assert out.click == "left" and e.state == "fall"


# --- float -----------------------------------------------------------------------------

def test_a_floater_rests_a_hand_above_the_floor_not_a_figure_up() -> None:
    # Intent moved (INBOX 1670: "it still sits like 20px above the bottom bar"): was 24 to 80 px
    # (INBOX 1658); the rest line is now 1 to 2 px, and the bob lifts it from there.
    for seed in range(8):
        e = make(seed=seed, gait="float")
        assert eng.HOVER[0] <= e.floor_y() - e.y <= eng.HOVER[1]
        assert e.y == e.ground_y()


def test_a_floater_drifts_across_the_width_and_a_band_above_its_rest_line_not_the_whole_height() -> None:
    e = make(gait="float", seed=3)
    e.big_ready = math.inf
    ys, xs, frames, t = [], [], set(), 0.0
    for _ in range(4000):  # 4 minutes at 60 ms
        t += 0.06
        o = e.update(t)
        ys.append(o.y), xs.append(o.x), frames.add(o.frame)
        assert 0 <= o.x <= 1920 - 100 and 0 <= o.y <= FLOOR
    # INBOX 1663 ("wayyy to high"): the height it uses is about its own, no more.
    # Intent moved (INBOX 1670, a buddy): it stays near home on the rest line, in a band no higher
    # than its own, and walks a few steps, not across the width.
    assert max(ys) - min(ys) <= eng.FLOAT_BAND * e.size[1] + eng.HOVER[1] + eng.BOB + 2
    assert 20 < max(xs) - min(xs) <= 2 * eng.STROLL + 20
    assert {"walk0", "walk3"} & frames


def test_a_floater_curves_and_never_walks_on_a_floor() -> None:
    e = make(gait="float", seed=5)
    e.big_ready = math.inf
    e.goal, e.then, e.trip = (1500.0, e.y - 80.0), "stand", True
    e._enter("drift", 0.0)
    e.goal, e.trip, e.state_until = (1500.0, e.y - 80.0), True, 1e9
    e.heading = 2.2  # pointing away from the goal: it must turn round in a curve
    heads, t = [], 0.0
    for _ in range(300):
        t += 0.033
        e.update(t)
        heads.append(e.heading)
    turned = sum(abs((b - a + math.pi) % (2 * math.pi) - math.pi) for a, b in zip(heads, heads[1:]))
    assert turned > 0.3  # the path bends


def test_a_thrown_floater_slows_by_drag_and_drifts_back_to_its_hover_height() -> None:
    e = make(gait="float")
    out, t = throw(e, to=(1500, 300), start=(850, 600))
    speeds, frames, settled = [], set(), False
    while t < 20 and e.state == "fly":
        t += 0.016
        o = e.update(t)
        frames.add(o.frame)
        speeds.append(math.hypot(e.vx, e.vy))
        settled = settled or o.settled
    assert speeds[-1] < speeds[0] * 0.2
    assert "fall" not in frames and "land" not in frames
    assert e.state == "stand" and settled
    assert abs(e.y - e.ground_y()) < 1 and eng.HOVER[0] <= e.floor_y() - e.y <= eng.HOVER[1]  # rest line moved, INBOX 1670


def test_a_floater_let_go_gently_does_not_fall_hard() -> None:
    e = make(gait="float")
    e.update(1.0, event=("down", 850, 400))
    e.update(1.01, event=("move", 850, 300))
    e.update(1.6, event=("up", 850, 300))
    assert e.state == "fly"
    t, vmax = 1.6, 0.0
    while e.state == "fly" and t < 30:
        t += 0.016
        e.update(t)
        vmax = max(vmax, e.vy)
    assert vmax < 400  # a walker would be at GRAVITY * time
    assert e.state == "stand"


def test_the_walker_stays_on_the_floor_when_big_acts_are_off() -> None:
    e = make(seed=11)
    e.big_ready = math.inf
    t = 0.0
    for _ in range(6000):
        t += 0.05
        o = e.update(t)
        assert o.y == FLOOR, (t, e.state)


# --- hang ---------------------------------------------------------------------------------

def test_a_walker_climbs_to_the_top_hangs_still_and_falls_back() -> None:
    e = make()
    e._perform("hang", 1.0)
    assert e.state == "rise"
    t, outs = step(e, 1.0, 1.2)
    assert e.state == "hang" and outs[-1].y == 0 and outs[-1].frame == "hang"
    t, outs = step(e, t, 6.0)
    assert len({o.x for o in outs if e.state == "hang"}) == 1  # INBOX 1663: it holds still
    t, outs = step(e, t, 12.0)
    assert any(o.frame == "fall" for o in outs) and outs[-1].y == FLOOR


def test_a_floater_floats_up_to_hang_from_the_top_edge() -> None:
    e = make(gait="float", seed=2)
    e._perform("hang", 1.0)
    assert e.state in ("crouch", "drift")  # a long trip starts with a short crouch
    t, outs = step(e, 1.0, 60.0, 0.033)
    assert any(e.state == "hang" or o.frame == "hang" for o in outs)
    assert min(o.y for o in outs) == 0


# --- peek -----------------------------------------------------------------------------------

def peek(e: Engine, edge: str, t0=1.0):
    e._go((e.x if edge == "bottom" else (0 if edge == "left" else 1920 - 100), e.floor_y()), f"peek_{edge}", t0)
    t, outs = step(e, t0, 45.0, 0.033)
    return t, outs


def test_peeking_from_the_bottom_clips_the_hidden_rows_and_never_shows_below_the_work_area() -> None:
    e = make()
    t, outs = peek(e, "bottom")
    clipped = [o for o in outs if o.clip]
    assert clipped
    for o in clipped:
        left, top, right, bottom = o.clip
        assert (left, top, right) == (0, 0, 100)
        assert o.y + bottom <= 1040 + 1  # the visible rows end at the taskbar's top
    head = min(o.clip[3] for o in clipped if o.clip[3] > 0)
    assert head <= 120 * (1 - eng.PEEK_HEAD) + 2
    assert any(o.clip[3] == 0 for o in clipped)  # it ducks out of sight
    assert outs[-1].clip is None and outs[-1].y == FLOOR


def test_a_peek_asks_for_ticks_while_it_moves_and_a_click_brings_it_out() -> None:
    e = make()
    t, _ = step(e, 1.0, 0.0)
    e._go((e.x, e.floor_y()), "peek_bottom", 1.0)
    t, outs = step(e, 1.0, 1.5, 0.033)
    assert e.state == "peek" and outs[-1].wake_ms == eng.TICK_WALK_MS
    e.update(t + 0.01, event=("down", 850, 1030))
    out = e.update(t + 0.05, event=("up", 850, 1030))
    assert out.click == "left" and e.state == "emerge"
    t2, outs = step(e, t + 0.05, 1.0, 0.033)
    assert outs[-1].clip is None and e.state in ("stand", "wave")
    assert e.sink == 0


def test_a_peek_from_a_side_edge_clips_columns_and_only_at_real_screen_edges() -> None:
    e = make(home=(1000, FLOOR))
    t, outs = peek(e, "left")
    cut = [o for o in outs if o.clip]
    assert cut and all(o.x + o.clip[0] >= 0 for o in cut)  # nothing visible past the screen edge
    assert all((o.clip[1], o.clip[3]) == (0, 120) for o in cut)
    assert max(o.clip[0] for o in cut) >= 100 * eng.PEEK_SIDE - 1  # the columns are cut
    two = [Monitor((0, 0, 1920, 1040), 96), Monitor((1920, 0, 3840, 1040), 96)]
    e2 = make(two, home=(1000, FLOOR))
    assert e2._open_side(e2.monitors[0], "left") and not e2._open_side(e2.monitors[0], "right")
    assert e2._open_side(e2.monitors[1], "right") and not e2._open_side(e2.monitors[1], "left")


def test_the_right_edge_peek_clips_the_right_columns() -> None:
    e = make(home=(1000, FLOOR))
    t, outs = peek(e, "right")
    cut = [o for o in outs if o.clip]
    assert cut and all(o.clip[0] == 0 and o.clip[2] <= 100 for o in cut)
    assert all(o.x + o.clip[2] <= 1920 + 1 for o in cut)


# --- the mix ------------------------------------------------------------------------------------

def run_acts(e: Engine, minutes: float):
    """Follow the engine's own wakes; record when each big act starts."""
    t, acts, prev = 0.0, [], e.state
    out = e.update(t)
    while t < minutes * 60:
        t += (out.wake_ms or 1000) / 1000.0
        # The person brushes it now and then, so it is not asleep for good.
        out = e.update(t, event=("move", 0, 0)) if int(t) % 25 == 0 else e.update(t)
        if e.state != prev and e.state in ("hang", "peek"):
            acts.append((t, e.state))
        prev = e.state
    return acts


def test_big_acts_are_minutes_apart_and_all_the_acts_are_in_one_table() -> None:
    assert set(eng.ACTS) == {"idle", "stroll", "trip", "sleep", "hang", "peek"}
    for gait in ("walk", "float"):
        acts = run_acts(make(seed=4, gait=gait), 180)
        assert len(acts) >= 3, acts
        gaps = [b[0] - a[0] for a, b in zip(acts, acts[1:])]
        assert min(gaps) >= eng.BIG_EVERY[0] - 1, gaps


def test_nothing_but_standing_while_the_person_is_busy() -> None:
    e = make()
    e.quiet = True
    states, t = set(), 0.0
    out = e.update(t)
    while t < 600:
        t += (out.wake_ms or 1000) / 1000.0
        out = e.update(t, (0, 0))
        states.add(e.state)
    assert states <= {"stand", "sit", "sleep"}


def test_the_still_state_never_throws_hangs_or_peeks() -> None:
    e = make(reduced=True)
    e.update(1.0, event=("down", 850, 950))
    e.update(1.01, event=("move", 1500, 300))
    out = e.update(1.02, event=("up", 1500, 300))
    assert out.frame == "sit" and out.y == FLOOR and out.settled
    assert not run_acts(make(reduced=True), 30)


def test_a_moving_floater_asks_for_ticks_and_a_resting_one_asks_for_none() -> None:
    e = make(gait="float", seed=1)
    e._enter("drift", 0.0)
    assert e.update(0.1).wake_ms == eng.TICK_WALK_MS
    r = make(gait="float", reduced=True)
    assert r.update(0.1).wake_ms is None


# --- grabbing a figure that is drawn away from where it is (review2, low) -------------------

def test_grabbing_a_peeking_figure_moves_it_by_the_pointer_not_by_its_sink() -> None:
    e = make()
    e._go((e.x, e.floor_y()), "peek_bottom", 1.0)
    t = 1.0
    while e.sink < 0.3 and t < 20:
        t += 0.016
        e.update(t)
    assert e.state == "peek" and e.sink >= 0.3
    x0, y0 = e.x, e.y
    e.update(t + 0.01, event=("down", int(x0) + 50, int(y0) + 20))
    e.update(t + 0.02, event=("move", int(x0) + 60, int(y0) + 20))
    assert (e.x, e.y) == (x0 + 10, y0)  # the pointer's own 10 px, no jump by the sunk rows


def test_grabbing_a_hang_moves_it_by_the_pointer() -> None:
    e = make()
    e.update(1.0)
    e._enter("hang", 1.0)
    e.x, e.y = 800.0, 0.0
    t = 1.4
    e.update(t)
    x0, y0 = e.x, e.y
    e.update(t + 0.01, event=("down", 850, 20))
    e.update(t + 0.02, event=("move", 860, 20))
    assert (e.x, e.y) == (x0 + 10, y0)


def test_nothing_is_clipped_unless_the_hidden_part_is_past_the_work_areas_edge() -> None:
    """INBOX 1663 ("cut in half"): across seeded runs at several dpi and on mixed monitors, every
    tick with a clip hides only a strip that lies outside the monitor's work area, in the same
    physical space the window is placed in; and an unclipped window sits fully inside it."""
    layouts = [
        ([Monitor((0, 0, 1920, 1040), 96)], (156, 178)),
        ([Monitor((0, 0, 1920, 1040), 120)], (194, 222)),
        ([Monitor((0, 0, 1920, 1040), 144)], (233, 266)),
        ([Monitor((0, 0, 1920, 1040), 144), Monitor((1920, 0, 3840, 1040), 96)], (233, 266)),
    ]
    clipped_ticks = 0
    for monitors, size in layouts:
        for seed in (1, 2, 3):
            e = Engine(size, monitors, rng=random.Random(seed), home=(800, 600), gait="float")
            t = 0.0
            for _ in range(6000):
                t += 0.1
                o = e.update(t)
                m = e.current_monitor()
                left, top, right, bottom = m.area
                w, h = size
                if o.clip is None or o.clip == (0, 0, w, h):  # a full clip hides nothing
                    assert left <= o.x and o.x + w <= right and top <= o.y and o.y + h <= bottom, (seed, e.state, o)
                    continue
                clipped_ticks += 1
                cl, ct, cr, cb = o.clip
                hidden = [(o.x, o.y, o.x + cl, o.y + h)] if cl > 0 else []
                hidden += [(o.x + cr, o.y, o.x + w, o.y + h)] if cr < w else []
                hidden += [(o.x, o.y + cb, o.x + w, o.y + h)] if cb < h else []
                assert hidden, (seed, o)
                for hx0, hy0, hx1, hy1 in hidden:
                    outside = hx1 <= left or hx0 >= right or hy0 >= bottom or hy1 <= top
                    assert outside, (seed, e.state, o, m.area)
    assert clipped_ticks > 0  # the runs do include peeks, so the check is not vacuous
