"""INBOX 1670, row A: hang anywhere along the top, feet on the work area's bottom, no frame cut on a
ride, no jolt or flicker. Measured on the shipped frames' alpha (`SpriteSet.metrics`), with the real
engine and a fixed clock; nothing here runs on Windows."""

from __future__ import annotations

import math
import random

import pytest

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay.engine import Engine, Monitor, Perch
from tessellate.core.overlay.sprites import FRAME_NAMES, IDLE_COUNT, SpriteSet

AREA = (0, 0, 1920, 1040)
ONE = [Monitor(AREA, 96)]
LOOKS = ("masculine", "feminine")
WIN = Perch(11, 500, 300, 1100)
#: Frames a figure shows while it stands, sits, sleeps, waves, lands, walks or holds a card.
#: Intent moved (W31 E2): the legs-over-the-edge pictures (`dangle`, `kick0`, `kick1`) and the one-handed hang hang below their line on purpose: a
#: dangle is seated on the window's top with its hem under it, so its lowest row is not the floor (tests/test_overlay_desk_acts_1710.py pins the seat).
#: Every hang grips a window edge, not the floor: `hang_sloth` and `hang_feet` (L-ui-modernisation-10) with the rest.
RESTING = tuple(n for n in FRAME_NAMES if not n.startswith("hang") and n not in ("tumble", "fall", "hop", "held", "dangle", "kick0", "kick1"))


_METRICS: dict[tuple[str, str], dict] = {}


def shared_metrics(s: SpriteSet, look: str) -> dict:
    """The shipped frames' drawn boxes at 96 dpi, built once per process: `SpriteSet.metrics` renders every frame in both
    mirrors (0.7 s) and the frames never change, yet each of a few hundred `make()` calls rebuilt them. The set keeps the
    shared result as its own, so a later `s.metrics(96)` in a test reads the same boxes without another build."""
    key = (look, str(s.directory))
    boxes = _METRICS.get(key)
    if boxes is None:
        boxes = _METRICS[key] = s.metrics(96)
    else:
        s._metrics, s._metrics_base = {96: boxes}, (s.size(96), boxes)
    return boxes


def make(look: str = "masculine", gait: str = "float", seed: int = 2, plain: bool = False) -> tuple[Engine, SpriteSet]:
    s = SpriteSet(look)
    size = s.size(96)
    e = Engine(
        size, ONE, rng=random.Random(seed), gait=gait, hang_top=s.top_share("hang"), idle_frames=IDLE_COUNT,
        home=(900, AREA[3] - size[1]),
    )
    e.set_metrics(shared_metrics(s, look))
    e.climb_ready = math.inf
    e.big_ready = math.inf
    e.plain_legs = plain  # True: every leg is the plain walk or drift (the older tests); False: the full repertoire
    return e, s


def drag(e: Engine, to: tuple[int, int], t: float = 1.0, release: bool = True) -> float:
    """Press the figure, walk the pointer to `to` in small steps, hold still, let go."""
    sx, sy = int(e.x + e.size[0] / 2), int(e.y + e.size[1] / 2)
    e.update(t, (sx, sy), ("down", sx, sy))
    for i in range(1, 21):
        t += 0.016
        e.update(t, event=("move", round(sx + (to[0] - sx) * i / 20), round(sy + (to[1] - sy) * i / 20)))
    for _ in range(10):  # a pause: no throw
        t += 0.05
        e.update(t, event=("move", to[0], to[1]))
    if release:
        t += 0.016
        e.update(t, event=("up", to[0], to[1]))
    return t


def run_until(e: Engine, state: str, t: float, limit: float = 4.0) -> float:
    end = t + limit
    while e.state != state and t < end:
        t += 0.016
        e.update(t)
    return t


def feet(e: Engine, s: SpriteSet, out: eng.Output) -> float:
    """The y of the lowest drawn row of what `out` draws."""
    return out.y + s.metrics(96)[(out.frame, out.flip)][3]


# --- (1) a drag released near the top takes hold -------------------------------------------

@pytest.mark.parametrize("gait", ["walk", "float"])
@pytest.mark.parametrize("x", [120, 960, 1790])
def test_a_drag_released_near_the_top_edge_hangs_anywhere_along_it(gait: str, x: int) -> None:
    e, _s = make(gait=gait)
    t = drag(e, (x, 30))
    run_until(e, "hang", t)
    assert e.state == "hang"
    assert e.y + e.hang_top * e.size[1] == pytest.approx(0.0, abs=1.0)
    assert e.hang_on is None


def test_a_drag_released_under_a_title_bar_hangs_from_that_window() -> None:
    e, _s = make()
    e.set_windows([WIN], 0.5)
    edge = WIN.top + eng.TITLE_BAR
    t = drag(e, (800, edge + 20))
    run_until(e, "hang", t)
    assert e.state == "hang" and e.hang_on is not None and e.hang_on.key == WIN.key
    assert e.y + e.hang_top * e.size[1] == pytest.approx(edge, abs=1.0)


def test_a_drag_released_beside_the_window_or_in_the_middle_of_the_screen_still_falls() -> None:
    e, _s = make()
    e.set_windows([WIN], 0.5)
    t = drag(e, (1500, WIN.top + eng.TITLE_BAR + 20))
    run_until(e, "stand", t, limit=8.0)
    assert e.state != "hang" and e.hang_on is None
    e2, _ = make()
    t = drag(e2, (960, 500))
    run_until(e2, "stand", t, limit=8.0)
    assert e2.state != "hang"


# --- (2) the feet sit on the work area's bottom ----------------------------------------------

@pytest.mark.parametrize("look", LOOKS)
def test_the_lowest_drawn_row_of_every_resting_frame_is_on_the_work_areas_bottom(look: str) -> None:
    e, s = make(look)
    worst = 0.0
    for name in RESTING:
        for flip in (False, True):
            e.facing = -1 if flip else 1
            e._frame = lambda _now, n=name: n  # type: ignore[method-assign]
            e._place_on_floor()
            e.state = "stand"
            out = e._output(0.0)
            gap = AREA[3] - feet(e, s, out)
            # Intent moved (INBOX 1670, 16:40Z: "it randomly jitters up and down"): the walk and drift cycle is drawn
            # on the stand's line, so a frame whose tail dips (feminine walk3 to walk7, up to 4 px) goes below the bar
            # by that much rather than hopping the window with every step; the rest are within 2 px as before.
            bound = 4 if name.startswith("walk") or name == "wave" else 2
            worst = max(worst, abs(gap) if bound == 2 else 0)
            assert abs(gap) <= bound, (look, name, flip, gap)
    assert worst <= 2


@pytest.mark.parametrize("look", LOOKS)
def test_a_floaters_rest_line_is_just_above_the_bottom_not_a_figure_up(look: str) -> None:
    for seed in range(8):
        e, s = make(look, "float", seed)
        out = e._output(0.0)
        assert 0 <= AREA[3] - feet(e, s, out) <= 3
        assert AREA[3] - feet(e, s, out) < 0.05 * e.size[1]


# --- (3) no frame is cut on a ride ------------------------------------------------------------

def ride(look: str, gait: str, seed: int, ticks: int = 2000) -> dict[str, float]:
    """Drag and throw about, seeded, 2,000 ticks; the worst a drawn box leaves the work area, per side."""
    e, s = make(look, gait, seed)
    boxes = s.metrics(96)
    r, t = random.Random(seed + 99), 0.0
    px = py = 0
    down, tgt = False, (0, 0)
    worst = {"left": 0.0, "right": 0.0, "top": 0.0, "bottom": 0.0}
    for _ in range(ticks):
        t += 0.016
        ev = None
        if not down and r.random() < 0.01:
            px, py = int(e.x + e.size[0] / 2), int(e.y + e.size[1] / 2)
            ev, down = ("down", px, py), True
            tgt = (r.choice([-200, 0, 960, 1900, 2100]), r.choice([-100, 0, 300, 1000, 1100]))
        elif down:
            px, py = int(px + (tgt[0] - px) * 0.2), int(py + (tgt[1] - py) * 0.2)
            if r.random() < 0.06:
                ev, down = ("up", px, py), False
            else:
                ev = ("move", px, py)
        o = e.update(t, (px, py), ev)
        # Intent moved (INBOX 1719 a): a throw past the leave line goes off the top on purpose (out through it, then
        # alpha 0 while away, then falling back in through it), so those frames are skipped like a clipped one; every other
        # throw still counts. The way back in is the flight `_return_top` launched (`AWAY_FALL`).
        back = e.state == "fly" and e.launch[1] == eng.AWAY_FALL * e._scale()
        if o.clip or o.alpha == 0 or e.away_until is not None or back or (e.state == "fly" and e._leaves()):
            continue
        left, top, right, bottom = boxes[(o.frame, o.flip)]
        worst["left"] = max(worst["left"], AREA[0] - (o.x + left))
        worst["top"] = max(worst["top"], AREA[1] - (o.y + top))
        worst["right"] = max(worst["right"], o.x + right - AREA[2])
        worst["bottom"] = max(worst["bottom"], o.y + bottom - AREA[3])
    return worst


@pytest.mark.parametrize("look", LOOKS)
@pytest.mark.parametrize("gait", ["walk", "float"])
def test_no_frame_is_cut_on_a_ride_over_a_seeded_run(look: str, gait: str) -> None:
    for seed in range(3):
        worst = ride(look, gait, seed)
        assert worst["left"] <= 0 and worst["right"] <= 0 and worst["top"] <= 0, (seed, worst)
        # Intent moved (INBOX 1670, 16:40Z: the window hopped with the tail): the walk cycle is drawn on the stand's
        # line, so the feminine tail dips up to 4 px under the bar on a few frames rather than moving the window.
        assert worst["bottom"] <= 4.5, (seed, worst)


# --- (4) no jolt, no flicker -------------------------------------------------------------------

def free_run(look: str, gait: str, seed: int, ticks: int = 3000):
    e, s = make(look, gait, seed)
    e.big_ready = 20.0
    t, o, rows = 0.0, e.update(0.0), []
    for _ in range(ticks):
        t += min(0.5, max(0.016, (o.wake_ms or 500) / 1000.0))
        before = o
        o = e.update(t)
        rows.append((t, e.state, before, o))
    return e, s, rows


#: What each planted state may move at, px per second at 96 dpi; the bob and the sway are the
#: 14 that a still state has.
SPEED = {"walk": eng.WALK_SPEED + 14, "drift": eng.FLOAT_SPEED + 14, "fall": 1500.0}
PLANTED = ("stand", "sit", "sleep", "wave", "notice", "startle", "land", "walk", "drift", "card")


@pytest.mark.parametrize("look", LOOKS)
@pytest.mark.parametrize("gait", ["walk", "float"])
def test_no_frame_to_frame_jump_over_one_and_a_half_times_the_states_speed(look: str, gait: str) -> None:
    worst = 0.0
    for seed in range(3):
        e, s, rows = free_run(look, gait, seed)
        boxes, last_t, was = s.metrics(96), 0.0, "stand"
        for t, state, before, o in rows:
            moving, was = was, state  # the step that ends a walk is still a walk's step
            if state not in PLANTED:
                continue
            # the figure's place: its feet line, and its middle (the mirror shift is not motion)
            fy = lambda q: q.y + boxes[(q.frame, q.flip)][3]  # noqa: E731
            fx = lambda q: q.x - e._flip_dx(q.frame, q.flip)  # noqa: E731
            if before.frame.startswith(("spin", "hang")):
                continue
            jump = math.hypot(fx(o) - fx(before), fy(o) - fy(before))
            dt = min(t - last_t, 0.1)
            last_t = t
            limit = 1.5 * max(SPEED.get(state, 14.0), SPEED.get(moving, 14.0)) * max(dt, 0.033) + 1.0
            worst = max(worst, jump / limit)
            assert jump <= limit, (look, gait, seed, round(t, 2), state, before.frame, o.frame, round(jump, 1))
    assert worst <= 1.0


@pytest.mark.parametrize("look", LOOKS)
def test_the_bob_is_eased_in_and_out_not_snapped_between_states(look: str) -> None:
    e, s = make(look, "float")
    boxes = s.metrics(96)
    e._enter("stand", 0.0)
    e.state_until = math.inf  # stays standing, bobbing, until it is sat down
    feet_y, t, o = [], 0.0, e.update(0.0)
    for i in range(400):
        t += 0.016
        if i == 200:
            e._enter("sit", t)
        o = e.update(t)
        feet_y.append(o.y + boxes[(o.frame, o.flip)][3])
    steps = [abs(b - a) for a, b in zip(feet_y, feet_y[1:])]
    assert max(steps) <= 1.6, max(steps)  # the bob's own speed, never its height
    assert abs(feet_y[-1] - AREA[3]) <= 2  # and it ends planted


@pytest.mark.parametrize("look", LOOKS)
def test_a_rise_to_a_hang_is_one_smooth_path_of_what_is_drawn_and_never_leaves_the_screen(look: str) -> None:
    for gait in ("walk", "float"):
        e, s = make(look, gait)
        boxes = s.metrics(96)
        t = drag(e, (960, 40))
        ys = []
        while e.state != "hang" and t < 6:
            t += 0.033
            o = e.update(t)
            ys.append(o.y)
            assert o.y + boxes[(o.frame, o.flip)][1] >= -1, (gait, o.frame, o.y)
        steps = [abs(b - a) for a, b in zip(ys, ys[1:])]
        assert steps and max(steps) <= 1.5 * (abs(ys[0] - ys[-1]) + 60) / eng.RISE_FOR * 1.5 * 0.033 + 2, max(steps)


@pytest.mark.parametrize("look", LOOKS)
def test_letting_go_of_a_hang_drops_it_with_all_of_it_on_screen_and_does_not_catch_it_again(look: str) -> None:
    for gait in ("walk", "float"):
        e, s = make(look, gait)
        boxes = s.metrics(96)
        t = run_until(e, "hang", drag(e, (960, 30)))
        e._let_go()
        top = 1e9
        for i in range(60):
            t += 0.016
            o = e.update(t)
            top = min(top, o.y + boxes[(o.frame, o.flip)][1])
        assert e.state not in ("hang", "rise"), (gait, e.state)
        assert top >= -1, (gait, top)


@pytest.mark.parametrize("look", LOOKS)
def test_a_figure_that_stands_still_is_not_moved_or_resized(look: str) -> None:
    for gait in ("walk", "float"):
        e, _s = make(look, gait)
        e.reduced = True
        e._enter("sit", 0.0)
        seen = {(o.x, o.y, o.frame, o.flip, o.clip) for o in (e.update(0.1 * i) for i in range(1, 200))}
        assert len(seen) == 1


@pytest.mark.parametrize("look", LOOKS)
def test_no_state_flip_flops_inside_200_ms_with_the_pointer_about(look: str) -> None:
    for gait in ("walk", "float"):
        for seed in range(3):
            e, _s = make(look, gait, seed)
            r, t, o = random.Random(seed), 0.0, e.update(0.0)
            log: list[tuple[float, str]] = []
            ptr = (900, 900)
            for _ in range(4000):
                t += min(0.5, max(0.016, (o.wake_ms or 500) / 1000.0))
                ptr = (int(ptr[0] + r.uniform(-60, 60)), int(ptr[1] + r.uniform(-40, 40)))
                o = e.update(t, ptr)
                if not log or log[-1][1] != e.state:
                    log.append((t, e.state))
            flips = [
                (a, b, c) for (ta, a), (tb, b), (tc, c) in zip(log, log[1:], log[2:]) if tc - ta < 0.2 and a == c and a != b
            ]
            assert not flips, (look, gait, seed, flips[:3])


# --- review round: the apex of a vertical throw, and sharper flicker bars ---------------------

def _fly_log(look: str, gait: str, vx: float, vy: float, ticks: int = 400) -> list[tuple[str, tuple[int, int], tuple[float, float]]]:
    """Throw from mid-screen and record (frame, window size, y) at 60 fps until it lands or hangs."""
    e, s = make(look, gait)
    e.y = 600.0
    e._start_fly(vx, vy)
    t, rows = 0.0, []
    for _ in range(ticks):
        t += 1 / 60
        o = e.update(t)
        if e.state not in ("fly", "hop"):
            break
        rows.append((o.frame, e.size, (o.x, o.y)))
    return rows


@pytest.mark.parametrize("look", LOOKS)
@pytest.mark.parametrize("gait", ["walk", "float"])
@pytest.mark.parametrize("vx", [0.0, 40.0, -300.0])
def test_a_straight_up_throw_tumbles_through_the_apex_without_flipping_to_the_held_pose(look, gait, vx) -> None:
    rows = _fly_log(look, gait, vx, -1100.0)
    kinds = ["spin" if f.startswith("spin") else f for f, _s, _p in rows]
    # a held run between two tumbles, however short, is the flip (and it resizes the window)
    flips = [i for i in range(1, len(kinds) - 1) if kinds[i] == "held" and "spin" in kinds[:i] and "spin" in kinds[i:]]
    assert not flips, (look, gait, vx, flips[:3])


@pytest.mark.parametrize("look", LOOKS)
def test_no_state_flip_flops_inside_200_ms_sampled_every_frame_not_every_wake(look: str) -> None:
    # the wake can be 500 ms, which cannot see a flip; sample at 60 fps with the pointer about
    for gait in ("walk", "float"):
        for seed in range(4):
            e, _s = make(look, gait, seed)
            r, t, ptr = random.Random(seed), 0.0, (900, 900)
            log: list[tuple[float, str]] = []
            for i in range(6000):
                t += 1 / 60
                if i % 20 == 0:
                    ptr = (int(ptr[0] + r.uniform(-90, 90)), int(ptr[1] + r.uniform(-60, 60)))
                e.update(t, ptr)
                if not log or log[-1][1] != e.state:
                    log.append((t, e.state))
            flips = [(a, b, c) for (ta, a), (tb, b), (tc, c) in zip(log, log[1:], log[2:]) if tc - ta < 0.2 and a == c and a != b]
            assert not flips, (look, gait, seed, flips[:3])


@pytest.mark.parametrize("look", LOOKS)
def test_a_thrown_figure_never_swaps_between_tumble_and_held_pose_inside_300_ms(look: str) -> None:
    # frame size follows the frame: a spin frame is a bigger canvas, so a swap is a resize
    for gait in ("walk", "float"):
        for seed in range(6):
            e, _s = make(look, gait, seed)
            r, t, kinds = random.Random(seed), 0.0, []
            for i in range(5000):
                t += 1 / 60
                if e.state in ("stand", "sit", "walk", "drift") and i % 120 == 0:
                    sx, sy = int(e.x + e.size[0] / 2), int(e.y + e.size[1] / 2)
                    e.update(t, (sx, sy), ("down", sx, sy))
                    for k in range(1, 5):
                        t += 0.016
                        e.update(t, event=("move", sx + k * int(r.uniform(-90, 90)), sy + k * int(r.uniform(-90, 10))))
                    t += 0.016
                    e.update(t, event=("up", sx, sy))
                o = e.update(t)
                kinds.append((t, "spin" if o.frame.startswith("spin") else (o.frame if e.state == "fly" else "other")))
            for j in range(1, len(kinds) - 1):
                ta, a = kinds[j - 1]
                if a == "spin" and kinds[j][1] == "held":
                    # the next picture that is not the held pose: a swap back is a spin straight after it (a new
                    # throw after the figure has settled is another flight, with a stand between; 16:40Z intent kept)
                    back = next(((tb, b) for tb, b in kinds[j:] if b != "held"), (None, None))
                    back = back[0] if back[1] == "spin" else None
                    assert back is None or back - ta >= 0.3, (look, gait, seed, round(ta, 2), round(back - ta, 2))


@pytest.mark.parametrize("look", LOOKS)
def test_a_resting_floater_keeps_its_window_still(look: str) -> None:
    # Intent moved (INBOX 1670, 16:40Z: "it randomly jitters up and down"): it was "a bobbing floater moves only at
    # the bob's speed". There is no bob now: standing, the window does not move by a pixel, and the feet stay within
    # 2 px of the bar through the idle cycle, its blinks and its looks.
    e, s = make(look, "float")
    boxes = s.metrics(96)
    e._enter("stand", 0.0)
    e.state_until = math.inf
    e.last_active = math.inf
    t, first, gaps, places = 0.0, e.update(0.0), [], set()
    for _ in range(1500):
        t += 1 / 60
        o = e.update(t)
        places.add((o.x, o.y))
        gaps.append(AREA[3] - (o.y + boxes[(o.frame, o.flip)][3]))
    assert len(places) == 1, places
    assert first.x == o.x and first.y == o.y
    assert min(gaps) >= -1.5, min(gaps)
    assert max(gaps) <= eng.HOVER[1] + 2.0, max(gaps)  # within 2 px of the bar at rest
