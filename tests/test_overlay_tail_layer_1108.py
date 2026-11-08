"""Desk companion: the tail as a layer (atlascat-1108 C1, INBOX 1696 w: "the tail is framed in that it isnt a smooth
animation"). `tail.curl`, `tail.wrap`, `tail.wag`, `tail.droop` and `tail.stiff` are drawn per tick over the body frame
(`sprites.SpriteSet.tailed`), eased between poses at the display rate. Fixed clock: every time here is passed in."""

from __future__ import annotations

import time

import pytest

from tessellate.core.overlay import behaviour as bh
from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import sprites as sp
from tests.test_overlay_ride_1670 import make

POSES = ("curl", "wrap", "wag", "droop", "stiff")
STEP = 1 / 30


def settled(name: str, seconds: float = 8.0, start: float = 100.0) -> tuple[bh.TailLayer, float, tuple[int, ...]]:
    """A layer driven at 30 a second into pose `name` until it is held; returns it, the time and the last view."""
    layer = bh.TailLayer()
    layer.name, layer.until = name, 1e9
    t, view = start, ()
    while t < start + seconds:
        view = layer.view(t)
        t += STEP
    return layer, t, view


@pytest.fixture(scope="module")
def spr() -> sp.SpriteSet:
    return sp.SpriteSet("masculine")


def test_the_catalogue_poses_are_the_rigs() -> None:
    for name in POSES:
        assert name in bh.TAIL_POSES
    assert bh.TAIL_POSES["curl"][0] == -1.3 and bh.TAIL_POSES["wrap"][0] == 1.1
    assert bh.TAIL_POSES["wag"][2] == 0.66 and bh.TAIL_POSES["droop"][0] == 0.6 and bh.TAIL_POSES["stiff"][0] == -0.12


def test_each_pose_changes_the_tails_drawn_points() -> None:
    held = {name: tuple(bh.tail_points(bh.TAIL_POSES[name], 0.0, 0.0)) for name in (*POSES, "sway")}
    for a in held:
        for b in held:
            if a < b:
                assert held[a] != held[b], (a, b)
    # the tip's end is where a pose differs most: a curl lifts it, a wrap carries it down
    assert held["curl"][-1][1] < held["sway"][-1][1] < held["wrap"][-1][1]


def test_each_pose_moves_the_tail_off_the_shipped_shape(spr: sp.SpriteSet) -> None:
    base = spr.frame("idle3", 192, False)
    drawn = {}
    for name in POSES:
        _, _, view = settled(name)
        assert any(view), name
        frame = spr.tailed(base, "idle3", 192, False, view)
        assert frame.bgra != base.bgra, name
        drawn[name] = frame.bgra
    assert len(set(drawn.values())) == len(POSES), "no two poses draw the same tail"


def test_the_body_frame_is_unchanged(spr: sp.SpriteSet) -> None:
    for flip in (False, True):
        base = spr.frame("idle3", 192, flip)
        before = bytes(base.bgra)
        _, _, view = settled("curl")
        frame = spr.tailed(base, "idle3", 192, flip, view)
        assert base.bgra == before, "the cached body frame is not touched"
        w, h = base.width, base.height
        x0, y0, x1, y1 = sp.SpriteSet._tail_region(w, h, flip)
        for y in range(h):
            row_a, row_b = base.bgra[y * w * 4:(y + 1) * w * 4], frame.bgra[y * w * 4:(y + 1) * w * 4]
            if y0 <= y < y1:
                assert row_a[:x0 * 4] == row_b[:x0 * 4] and row_a[x1 * 4:] == row_b[x1 * 4:], (flip, y)
            else:
                assert row_a == row_b, (flip, y)


def test_the_head_and_torso_are_outside_the_tails_region(spr: sp.SpriteSet) -> None:
    w, h = spr.size(192)
    for flip in (False, True):
        x0, y0, x1, y1 = sp.SpriteSet._tail_region(w, h, flip)
        assert y0 > 0.5 * h, "below the waist"
        assert (x1 - x0) < 0.5 * w


def test_a_frame_without_a_layered_tail_is_returned_as_it_is(spr: sp.SpriteSet) -> None:
    _, _, view = settled("curl")
    walk = spr.frame("walk3", 192, False)
    assert spr.tailed(walk, "walk3", 192, False, view) is walk
    stand = spr.frame("stand", 192, False)
    assert spr.tailed(stand, "stand", 192, False, None) is stand
    assert spr.tailed(stand, "stand", 192, False, (0,) * 12) is stand


def test_a_pose_change_eases_over_several_ticks() -> None:
    layer, t, before = settled("sway")
    layer.name = "curl"
    views = []
    for _ in range(int(3.0 / STEP)):
        t += STEP
        views.append(layer.view(t))
    tips = [v[-1] for v in views]  # the tip's vertical move, 1/8 px
    # it starts where the last pose was and ends at the new one's, through many distinct steps, none of them a jump
    steps = [abs(b - a) for a, b in zip(tips, tips[1:])]
    assert len({round(x / 8) for x in tips}) >= 8, "several ticks of the move, not one"
    assert max(steps) < 0.25 * abs(tips[-1] - tips[0]) + 16, (max(steps), tips[0], tips[-1])
    assert tips[-1] < tips[0] - 100, "the curl lifted the tip well clear of the sway's"


def test_the_tail_never_holds_still_for_half_a_second() -> None:
    for name in ("sway", *POSES):
        layer, t, _ = settled(name, 2.0)
        views = []
        for _ in range(60):
            views.append(layer.view(t))
            t += STEP
        for k in range(0, 60 - 15):
            assert len(set(views[k:k + 15])) > 1, (name, k)


def test_the_engine_draws_the_tail_at_the_display_rate_not_the_cycles() -> None:
    e, _ = make()
    t, seen, wakes = 1.0, [], []
    for _ in range(90):
        o = e.update(t)
        seen.append((t, o.frame, o.tail))
        wakes.append(o.wake_ms)
        t += max(0.03, (o.wake_ms or 1000) / 1000.0)
    assert e.state == "stand"
    assert all(w is not None and w <= eng.TAIL_LAYER_MS for w in wakes)
    span = seen[-1][0] - seen[0][0]
    frames = len({f for _, f, _ in seen})
    tails = len({v for _, _, v in seen})
    assert tails > 4 * frames, ("the tail's pictures outnumber the 6 a second cycle's", tails, frames)
    assert span > 2.0 and len(seen) / span >= 25, (len(seen), span)


def test_no_layer_for_a_walker_a_reduced_figure_or_a_held_one() -> None:
    e, _ = make(gait="walk")
    assert e.update(1.0).tail is None
    e, _ = make()
    e.reduced = True
    assert e.update(1.0).tail is None
    e, _ = make()
    e._enter("sleep", 1.0)
    assert e.update(1.1).tail is None


def test_the_moods_pick_the_poses() -> None:
    layer = bh.TailLayer()
    for mood, pose in (("happy", "wag"), ("sleepy", "droop"), ("startled", "stiff")):
        layer.until = 0.0
        layer.choose("stand", mood, 10.0)
        assert layer.name == pose, mood
    picked = set()
    for k in range(60):
        layer.until = 0.0
        layer.choose("sit", "calm", 100.0 + k * 10)
        picked.add(layer.name)
    assert picked <= {"wrap", "sway", "curl"} and len(picked) >= 2


def test_a_tick_costs_under_eight_ms_at_dpi_192(spr: sp.SpriteSet) -> None:
    """The per-tick build of the tail layer over a cached body frame, on the real clock for the cost only (a ceiling far
    above the measured 1.3 ms, so a slow machine does not flake it)."""
    base = spr.frame("idle3", 192, False)
    layer = bh.TailLayer()
    spr.tailed(base, "idle3", 192, False, layer.view(10.0))  # the first one builds the source and the mask
    t0 = time.perf_counter()
    for k in range(40):
        spr.tailed(base, "idle3", 192, False, layer.view(10.0 + k * STEP))
    assert (time.perf_counter() - t0) / 40 < 0.008
