"""Desk companion: the nine tail poses of atlascat-1108 C2 and C3 (`tail.hook`, `tail.coil_hold`, `tail.thump`,
`tail.shiver`, `tail.tuck`, `tail.loop8`, `tail.tip_twitch`, `tail.balance`, `tail.pillow`), each drawn by the tail layer
and each picked by a trigger (a mood, a place or a reaction), never only a table row. Fixed clock: every time is passed in."""

from __future__ import annotations

import pytest

from tessellate.core.overlay import behaviour as bh
from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import sprites as sp
from tests.test_overlay_ride_1670 import make
from tests.test_overlay_tail_layer_1108 import STEP, settled

NEW = ("hook", "coil_hold", "thump", "shiver", "tuck", "loop8", "tip_twitch", "balance", "pillow")


@pytest.fixture(scope="module")
def spr() -> sp.SpriteSet:
    return sp.SpriteSet("masculine")


def picks(state: str, mood: str, n: int = 80) -> set[str]:
    layer, out = bh.TailLayer(), set()
    for k in range(n):
        layer.until = 0.0
        layer.choose(state, mood, 100.0 + k * 10)
        out.add(layer.name)
    return out


def test_the_new_poses_are_in_the_table_with_the_rigs_numbers() -> None:
    for name in NEW:
        assert name in bh.TAIL_POSES and len(bh.TAIL_POSES[name]) == 6, name
    assert bh.TAIL_POSES["hook"][:2] == (-0.9, 0.1) and bh.TAIL_POSES["hook"][4] == 1.4
    assert bh.TAIL_POSES["thump"][2] == 1.4 and bh.TAIL_POSES["shiver"][2] == 0.12 and bh.TAIL_POSES["tip_twitch"][5] == 6.0


def test_each_new_pose_draws_a_tail_of_its_own() -> None:
    held = {name: tuple(bh.tail_points(bh.TAIL_POSES[name], 0.0, 0.0)) for name in (*NEW, "sway", "curl", "wrap", "droop")}
    for a in held:
        for b in held:
            if a < b:
                assert held[a] != held[b], (a, b)
    assert held["hook"][-1][1] < held["hook"][-3][1], "the hook's tip turns back up past its middle (a question mark)"
    assert held["pillow"][-1][1] > held["sway"][-1][1], "curled under, lower than the sway"


def test_a_tip_twitch_moves_only_the_tip() -> None:
    twitch = list(bh.TAIL_POSES["tip_twitch"])
    near, tip = [], []
    for ph in (0.0, 1.0, 2.0, 3.0, 4.0, 5.0):
        pts = bh.tail_points(tuple(twitch), ph, ph * 0.6)
        flat = bh.tail_points(tuple(twitch), 0.0, 0.0)
        near.append(abs(pts[1][1] - flat[1][1]))
        tip.append(abs(pts[-1][1] - flat[-1][1]))
    assert max(tip) > 8 * max(near), (max(near), max(tip))


def test_each_new_pose_moves_the_tail_off_the_shipped_shape(spr: sp.SpriteSet) -> None:
    base = spr.frame("idle3", 192, False)
    drawn = {}
    for name in NEW:
        _, _, view = settled(name)
        assert any(view), name
        frame = spr.tailed(base, "idle3", 192, False, view)
        assert frame.bgra != base.bgra, name
        drawn[name] = frame.bgra
    assert len(set(drawn.values())) == len(NEW)


def test_a_shiver_is_fast_and_small_and_never_still() -> None:
    layer, t, _ = settled("shiver", 2.0)
    views = []
    for _ in range(30):
        views.append(layer.view(t))
        t += STEP
    assert len(set(views)) >= 20, "a new picture almost every tick"
    tips = [v[-1] for v in views]
    assert max(tips) - min(tips) < 8 * 40, "a tremble, not a swing"


@pytest.mark.parametrize(
    ("state", "mood", "pose"),
    [
        ("stand", "curious", "hook"), ("stand", "bored", "thump"), ("stand", "sad", "tuck"), ("stand", "playful", "loop8"),
        ("perch", "calm", "balance"), ("lounge", "calm", "coil_hold"), ("sit", "sleepy", "pillow"), ("stand", "calm", "tip_twitch"),
    ],
)
def test_the_trigger_picks_the_pose(state: str, mood: str, pose: str) -> None:
    assert pose in picks(state, mood), (state, mood)


def test_a_start_holds_stiff_then_shivers() -> None:
    layer = bh.TailLayer()
    seen = []
    for k in range(4):
        layer.until = 0.0
        layer.choose("stand", "startled", 10.0 + k * 10)
        seen.append(layer.name)
    assert seen == ["stiff", "shiver", "stiff", "shiver"]


def test_the_old_moods_keep_their_poses() -> None:
    layer = bh.TailLayer()
    for mood, pose in (("happy", "wag"), ("proud", "wag"), ("sleepy", "droop")):
        layer.until = 0.0
        layer.choose("stand", mood, 10.0)
        assert layer.name == pose, mood


def test_the_engine_hands_the_layer_a_place_and_a_reaction() -> None:
    e, _ = make()
    t = 1.0
    e.update(t)
    assert e._tail_cue(t)[0] == "stand"
    e.perch = object()  # a window's top: it balances
    assert e._tail_cue(t)[0] == "perch"
    e.perch = None
    e._enter("sit", t)
    e.update(t + 0.04)
    assert e._tail_cue(t + 0.1)[0] == "sit"
    assert e._tail_cue(t + bh.LOUNGE_AFTER + 1.0)[0] == "lounge"
    e.ex.over = ("sad", t, 1e9)
    assert e._tail_cue(t)[1] == "sad"
    e.ex.over = None
    e.last_click = t
    e.mind.feel("happy", t)
    assert e._tail_cue(t + 0.1)[1] == "playful", "glad, and touched just now"


def test_the_new_poses_do_not_raise_the_rest_tick() -> None:
    """At rest the tail ticks at the old pace whatever the pose: `shiver` and the rest are only a different shape."""
    for name in NEW:
        e, _ = make()
        e.tail_layer.name, e.tail_layer.until = name, 1e9
        t = 1.0
        for _ in range(30):
            o = e.update(t)
            assert o.wake_ms is not None and o.wake_ms <= eng.FLOW_TICK_MS, name
            t += o.wake_ms / 1000.0
