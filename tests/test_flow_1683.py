"""The wisps and the nebula streams move all the time (INBOX 1683 c, the owner: "I still dont see much organic or
natural subtle movement with the lower body whisps and the nebular streams"). Measured on the pure `Flow`, the
sprite warp and the engine, all on a fixed clock: nothing here reads the real one, and nothing runs on Windows."""

from __future__ import annotations

import math

import numpy as np
import pytest

from tessellate.core.overlay import behaviour as bh
from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import sprites
from tests.test_overlay_ride_1670 import make

LOOKS = ("masculine", "feminine")
STEP = 0.05


def tips(flow: bh.Flow, seconds: float, calm: bool = False, start: float = 0.0) -> np.ndarray:
    """Each strand's tip, px, every `STEP` seconds: rows are strands."""
    n = int(seconds / STEP)
    return np.array([[flow.sway(i, start + k * STEP + flow.t0, calm) for k in range(n)] for i in range(bh.FLOW_BANDS)])


def rises(flow: bh.Flow, seconds: float, calm: bool = False) -> np.ndarray:
    n = int(seconds / STEP)
    return np.array([[flow.rise(i, k * STEP + flow.t0, calm) for k in range(n)] for i in range(bh.FLOW_BANDS)])


def spectrum(series: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Magnitude of each strand's spectrum, Hann-windowed (a sum of sines that is not a whole number of periods leaks)."""
    centred = (series - series.mean(axis=1, keepdims=True)) * np.hanning(series.shape[1])
    return np.abs(np.fft.rfft(centred, axis=1)), np.fft.rfftfreq(series.shape[1], STEP)


def test_no_strand_is_still_for_a_second_at_rest():
    flow = bh.Flow()
    x, y = tips(flow, 120.0), rises(flow, 120.0)
    path = np.cumsum(np.hypot(np.diff(x, axis=1), np.diff(y, axis=1)), axis=1)
    window = int(1.0 / STEP)
    worst = min(float(path[i, k + window] - path[i, k]) for i in range(bh.FLOW_BANDS) for k in range(0, path.shape[1] - window - 1))
    # measured 0.15 px (the quietest strand, its quietest second in 120 s); the sprite warp's step is an eighth
    assert worst >= 0.125


def test_no_period_is_under_four_seconds_and_nothing_is_a_pure_loop():
    flow = bh.Flow()
    for octaves in flow.bands:
        assert min(p for p, _ in octaves) > 4.0
    series = tips(flow, 240.0)
    mag, freqs = spectrum(series)
    # nothing but a trace above 1/4 Hz (the wander adds a few thousandths of a hertz to the fastest octave)
    assert mag[:, freqs > 0.25].max() < 0.02 * mag.max()
    # no strand returns to itself: its autocorrelation at 4 to 100 s stays well under 1 (a loop would reach 1)
    for row in series:
        ac = np.correlate(row, row, "full")[row.size - 1:] / np.dot(row, row)
        assert ac[int(4 / STEP):int(100 / STEP)].max() < 0.92


def test_the_strands_are_not_in_phase():
    series = tips(bh.Flow(), 120.0)
    corr = np.corrcoef(series)
    off = corr[~np.eye(bh.FLOW_BANDS, dtype=bool)]
    assert np.abs(off).max() < 0.6, np.abs(off).max()


def test_the_sway_is_bounded_and_the_outer_streams_sway_most():
    flow = bh.Flow()
    series = tips(flow, 120.0)
    assert np.abs(series).max() <= bh.FLOW_TIP + 1e-9
    assert flow.reach(0) > flow.reach(bh.FLOW_BANDS // 2) and flow.reach(bh.FLOW_BANDS - 1) > flow.reach(bh.FLOW_BANDS // 2)


def test_reduced_motion_is_a_slow_drift_only():
    flow = bh.Flow()
    calm, lively = tips(flow, 240.0, calm=True), tips(flow, 240.0)
    assert np.abs(calm).max() <= 0.5 * np.abs(lively).max() + 0.05
    mag, freqs = spectrum(calm)
    assert mag[:, freqs > 1 / 10.0].max() < 0.02 * mag.max()  # nothing faster than a 10 s period (the octaves are 11 s and up)
    assert np.ptp(calm[:, : int(8 / STEP)], axis=1).min() > 0.0  # but it does drift


def _follow(vx: float = 0.0, vy: float = 0.0, move: float = 1.0, total: float = 4.0, ease: float = 0.4) -> tuple[list[float], list[float]]:
    """The mean strand follow-through (px) when the body goes at (vx, vy) px/s for `move` seconds, then stops,
    sampled every 1/60 s: (x, y)."""
    flow = bh.Flow()
    xs, ys = [], []
    for k in range(int(total * 60)):
        t = k / 60
        on = t < move
        # a start and a stop are eased, as the engine's pace is
        ramp = min(1.0, t / ease) if on else max(0.0, 1.0 - (t - move) / ease)
        flow.step(1 / 60, vx * ramp, vy * ramp)
        xs.append(sum(p[0] for p in flow.pos) / bh.FLOW_BANDS)
        ys.append(sum(p[1] for p in flow.pos) / bh.FLOW_BANDS)
    return xs, ys


def test_the_streams_trail_a_move_and_drift_on_after_a_stop():
    xs, _ = _follow(vx=250.0)
    stop = 84  # the body's last step (1.0 s of going, 0.4 s easing out)
    assert min(xs[:stop]) < -2.0, "it streams back behind a start"
    assert min(xs[30:stop - 8]) < -1.0, "and trails for as long as it goes"
    after = xs[stop:]
    peak = max(after)
    assert peak > 0.5, "the stop swings past"
    assert abs(xs[stop + 15] - xs[stop]) > 0.3, "it is still moving a quarter second after the body halted"
    settled = max(i for i, v in enumerate(after) if abs(v) > 0.3) / 60
    assert 0.2 < settled < 2.0, settled  # and comes to rest within a couple of seconds
    assert all(abs(v) < 0.3 for v in xs[-30:]), "it comes to rest"
    assert max(abs(v) for v in xs) <= bh.FLOW_MAX


def test_the_streams_trail_down_when_it_floats_up():
    _, ys = _follow(vy=-200.0)
    assert max(ys) > 1.0, "floating up (screen y falls) the strands stream back down"
    assert all(abs(v) < 0.3 for v in ys[-30:])


def test_a_flow_view_is_hashable_small_integers_and_a_still_one_is_the_same():
    flow = bh.Flow()
    a, b = flow.view(10.0), flow.view(10.0)
    assert a == b and all(isinstance(v, int) for v in a) and len(a) == bh.FLOW_BANDS * sprites.FLOW_FIELDS
    assert flow.view(10.0) != flow.view(12.0)
    assert bh.FLOW_Q == sprites.FLOW_Q


@pytest.mark.parametrize("look", LOOKS)
def test_the_head_and_the_torso_stay_put_and_the_lower_body_moves(look):
    s = sprites.SpriteSet(look)
    plain = s.frame("stand", 192, False)
    view = bh.Flow().view(31.7)
    moved = s.posed("stand", 192, False, (1.0, 1.0, 0.0, 0.0), view)
    assert moved.bgra != plain.bgra
    left, top, right, bottom = plain.box
    waist = top + (bottom - top) * sprites.FLOW_WAIST
    mid, half = (left + right) / 2, (right - left) / 2
    stride = plain.width * 4
    # the head and the torso's middle (above the waist, inside the core) keep their pixels: the sparkle is gated
    # below the waist and to the outer streams
    core = int(half * sprites.FLOW_CORE[0] * 0.8)
    for y in range(top, int(waist) - 2):
        a = plain.bgra[y * stride + int(mid - core) * 4:y * stride + int(mid + core) * 4]
        b = moved.bgra[y * stride + int(mid - core) * 4:y * stride + int(mid + core) * 4]
        # the mesh's bilinear pass alone moves a pixel by up to 12 of 255 (the existing pose warp too: measured 8 to 12)
        assert max(abs(i - j) for i, j in zip(a, b)) <= 16, y
    low = slice(int(waist + 10) * stride, bottom * stride)
    assert plain.bgra[low] != moved.bgra[low]


def test_no_part_of_the_lower_body_turns_over_four_degrees_off_the_torso():
    """INBOX 615 and 619: its worst, every strand's tip and middle at the largest the flow can make them."""
    s = sprites.SpriteSet("feminine")
    base = s.frame("stand", 192, False)
    left, top, right, bottom = base.box
    scale = base.width / s._load("stand").size[0]
    worst = tuple(v for _ in range(bh.FLOW_BANDS) for v in (round(bh.FLOW_TIP * bh.FLOW_Q), round(bh.FLOW_TIP * 0.65 * bh.FLOW_Q), round(bh.FLOW_RISE * bh.FLOW_Q), 0, 10))
    rows = [round(i * base.height / sprites.POSE_STRIPS) for i in range(sprites.POSE_STRIPS)] + [base.height]
    edges = [0.0] + [float(round(left + (right - left) * j / bh.FLOW_BANDS)) for j in range(1, bh.FLOW_BANDS)] + [float(base.width)]
    field = sprites.flow_offsets(worst, edges, rows, (left, top, right, bottom), scale)
    waist = top + (bottom - top) * sprites.FLOW_WAIST
    hem = max(j for j, y in enumerate(rows) if y <= bottom)
    start = min(j for j, y in enumerate(rows) if y > waist)
    angle = 0.0
    for col in range(len(edges)):
        for row in range(start, hem + 1):
            dx = field[row][col][0] - field[start - 1][col][0]
            run = rows[row] - rows[start - 1]
            angle = max(angle, math.degrees(math.atan2(abs(dx), run)))
    assert angle < 4.0, angle


@pytest.mark.parametrize("look", LOOKS)
def test_the_picture_cost_stays_inside_the_calm_budget(look):
    """Measured on the box (5 to 6 ms at 96 and 192 dpi); the bound is far over that so a slow runner does not
    flake, and under what a 10 a second tick could ever make a core feel."""
    import time

    s = sprites.SpriteSet(look)
    flow = bh.Flow()
    s.posed("stand", 192, False, (1.0, 1.0, 0.0, 0.0), flow.view(1.0))
    began = time.perf_counter()
    for k in range(10):
        s.posed("stand", 192, False, (1.0, 1.0, 0.0, 0.0), flow.view(2.0 + k * 0.7))
    assert (time.perf_counter() - began) / 10 < 0.05


def test_a_flow_is_never_asked_of_a_spin_frame():
    s = sprites.SpriteSet("masculine")
    spin = sprites.SPIN_FRAMES[5]
    assert s.posed(spin, 96, False, (1.0, 1.0, 0.0, 0.0), bh.Flow().view(5.0)) is s.frame(spin, 96, False)


# --- the engine ---------------------------------------------------------------------------------------------


def _at_rest(look: str = "masculine", seconds: float = 12.0, state: str | None = None) -> list[eng.Output]:
    e, _ = make(look)
    out, t = [], 1.0
    if state:
        e._enter(state, t)
    while t < 1.0 + seconds:
        o = e.update(t)
        out.append(o)
        t += max(0.03, (o.wake_ms or 1000) / 1000.0)
    return out


@pytest.mark.parametrize("state", [None, "sit", "sleep"])
def test_the_engine_redraws_at_rest_so_the_streams_never_stop(state):
    out = _at_rest(state=state)
    # Intent moved (deskframes-1108): a spell act (a drawn rune, `FLOW_SPELL_MS`) ticks at its own 300 ms, and with the new
    # frame sizes the seeded run reaches one; the bound is the slowest tick the engine has at rest, still under a second.
    slowest = eng.FLOW_SLEEP_MS if state == "sleep" else eng.FLOW_SPELL_MS
    assert all(o.wake_ms is not None and o.wake_ms <= slowest for o in out), "a wake is never later than the streams' tick"
    # Intent moved (deskframes-1108): a warp's picture is an effect (`Output.fx`) that takes no flow by design (the seeded
    # run now reaches one at 7.4 s), so the streams are asked of every other picture.
    out = [o for o in out if o.fx is None]
    views = [o.flow for o in out]
    assert all(v is not None for v in views)
    # a 1 s window always holds more than one distinct picture of the streams
    stamps, t = [], 1.0
    for o in out:
        stamps.append(t)
        t += max(0.03, (o.wake_ms or 1000) / 1000.0)
    for k, t0 in enumerate(stamps):
        window = {v for v, t1 in zip(views[k:], stamps[k:]) if t1 < t0 + 1.0}
        if t0 + 1.0 <= stamps[-1]:
            assert len(window) > 1, t0


def test_reduced_motion_ticks_once_a_second_and_drifts_slowly():
    e, _ = make()
    e.reduced = True
    o = e.update(5.0)
    assert o.wake_ms == eng.FLOW_CALM_MS
    assert o.flow is not None and any(o.flow)
    tips_ = [o.flow[k * sprites.FLOW_FIELDS] for k in range(bh.FLOW_BANDS)]
    assert max(abs(v) for v in tips_) <= round(bh.FLOW_TIP * bh.FLOW_CALM_AMP * bh.FLOW_Q)


def test_a_move_throws_the_streams_and_they_settle_after_the_stop():
    e, _ = make()
    t = 1.0
    for _ in range(40):
        e.update(t)
        t += 0.05
    start = e.x
    # push the window by hand at 250 px/s for a second, as a walk would, then stop
    for k in range(60):
        e.x += 250 / 60
        e._follow_through(t, 1 / 60)
        t += 1 / 60
    during = max(abs(p[0]) for p in e.flow.pos)
    assert during > 1.0 and e.x > start
    for _ in range(240):
        e._follow_through(t, 1 / 60)
        t += 1 / 60
    assert e.flow.settled()


# --- review of 1683: a drag or a throw must not build a warped picture a frame ----------------------------


@pytest.mark.parametrize("look", LOOKS)
def test_a_drag_and_a_throw_keep_one_flow_so_no_warp_is_built_a_frame(look):
    e, _ = make(look)
    t = 1.0
    for _ in range(60):  # let the streams be mid-sway before the grab
        e.update(t)
        t += 0.05
    sx, sy = int(e.x + e.size[0] / 2), int(e.y + e.size[1] / 2)
    outs = [e.update(t, (sx, sy), ("down", sx, sy))]
    for i in range(1, 60):
        t += 0.016
        outs.append(e.update(t, event=("move", sx + i * 9, sy - i * 4)))
    for _ in range(12):  # a fast last stretch, then let go: a throw
        t += 0.016
        outs.append(e.update(t, event=("move", sx + 700 + 40 * _, sy - 300)))
    t += 0.016
    outs.append(e.update(t, event=("up", sx + 1100, sy - 300)))
    for _ in range(120):
        t += 0.016
        outs.append(e.update(t))
    airborne = [o for o in outs if o.frame.startswith("spin") or e.state in ("held",)]
    in_motion = [o for o in outs if o.frame.startswith("spin") or o.frame in ("held", "fall", "hop")]
    assert in_motion, "the drag or the throw drew no motion frame"
    assert len({o.flow for o in in_motion}) <= 2, "a flowed picture per frame is a warp per frame"
    assert not [o for o in airborne if o.frame.startswith("spin") and o.flow is not None]
