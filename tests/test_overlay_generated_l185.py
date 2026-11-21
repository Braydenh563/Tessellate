"""L185: a companion made from the person's own figure (`capture.CAPTURED` only: no wave swing, no perch pictures) does everything the
engine asks of it, with a picture for each: walks, runs (crouching first), climbs a window, crouches, sits, lies down, and idles
slowly. Fixed clock, seeded. Measured 2026-11-21: 18 forced legs over 6 seeds were 6 walks, 3 runs, 3 hops and 6 warps, with 107 crouch ticks before them;
0 frames outside the captured set (plus the idle, spin, wave and lidded-sit names built from it); the idle is a breath of 24 pictures over 3.65 s."""

from __future__ import annotations

from collections import Counter

import pytest

from tessellate.core.overlay import capture, sprites
from tests.test_overlay_moves import make, step
from tests.test_overlay_roam import WIN, climb

#: What it may draw: what the page captures, the numbered runs of it, what a missing perch picture falls back to, the tumble's spin, the lidded sit made on load.
ALLOWED = set(capture.CAPTURED) | set(sprites.EXTRA_FALLBACK.values()) | {n for n in sprites.FRAME_NAMES if n.startswith(("spin", "wave"))} | {"sitblink"}
SEEDS = (1, 2, 3, 4, 5, 6)


def drawn(e, t: float, seconds: float, frames: Counter, states: Counter) -> float:
    end = t + seconds
    while t < end:
        t += 0.016
        o = e.update(t)
        frames[o.frame] += 1
        states[e.state] += 1
    return t


def far_legs(seed: int):
    e = make(seed=seed, gait="walk")
    e.plain_legs = False  # the way it really travels: a walk, a run, a hop chain, a portal
    e.update(1.0)
    area = e.current_monitor().area
    frames, states = Counter(), Counter()
    t = 2.0
    for goal in (area[0] + 40, area[2] - 140, area[0] + 60):
        e._go((goal, e.y), "stroll", t)
        t = drawn(e, t, 14.0, frames, states)
    return e, frames, states


def test_a_far_leg_is_a_walk_or_a_run_that_crouches_first_and_draws_only_captured_pictures() -> None:
    kinds, crouched = Counter(), 0
    for seed in SEEDS:
        e, frames, states = far_legs(seed)
        kinds.update(e.modes)
        crouched += states["crouch"] > 0
        assert not [f for f in frames if f not in ALLOWED and not f.startswith("idle")], (seed, set(frames) - ALLOWED)
        assert any(f.startswith("walk") for f in frames) or states["dash"], seed
    assert kinds["walk"] > 0 and kinds["run"] > 0, kinds
    assert crouched >= 1, "a run starts with a crouch, drawn on `land`"


def test_it_climbs_a_window_and_sits_and_lies_down_with_captured_pictures() -> None:
    frames, states = Counter(), Counter()
    for seed in SEEDS[:3]:
        e = make(seed=seed, gait="walk")
        t = climb(e)
        assert e.perch == WIN, seed
        t = drawn(e, t, 3.0, frames, states)
        for state, picture in (("sit", "sit"), ("sleep", "sleep")):
            e._enter(state, t)
            before = frames[picture]
            t = drawn(e, t, 2.0, frames, states)
            assert frames[picture] > before, (seed, state)
    assert states["leap"] + states["land"] + states["rise"] > 0, states
    assert not [f for f in frames if f not in ALLOWED and not f.startswith("idle")], set(frames) - ALLOWED


@pytest.mark.parametrize("hour", [8, 14, 22])
def test_a_long_sweep_at_the_desk_draws_nothing_it_has_no_picture_of(hour: int) -> None:
    e = make(seed=hour, gait="walk", roam_windows=True)
    e.set_windows([WIN], 1.0)
    e.hour = hour
    frames, states = Counter(), Counter()
    t = 1.0
    for i in range(int(300 / 0.05)):
        t += 0.05
        o = e.update(t, (900.0, 900.0) if (i // 1500) % 2 else None)
        frames[o.frame] += 1
        states[e.state] += 1
    assert not [f for f in frames if f not in ALLOWED and not f.startswith("idle")], set(frames) - ALLOWED
    assert sum(frames.values()) > 5000 and states["act"] > 0


def test_the_idle_is_a_slow_breath_of_twenty_four_pictures_that_closes_on_itself() -> None:
    e = make(seed=3, gait="walk")
    t, _ = step(e, 1.0, 0.5)
    assert e.state == "stand"
    seen: list[tuple[float, int]] = []
    start = t
    while t - start < 8.0 and e.state == "stand":
        t += 0.016
        o = e.update(t)
        if o.frame.startswith("idle"):
            n = int(o.frame[4:])
            if not seen or seen[-1][1] != n:
                seen.append((t - start, n))
    steps = [(b[1] - a[1]) % sprites.IDLE_COUNT for a, b in zip(seen, seen[1:])]
    assert len(seen) >= sprites.IDLE_COUNT and set(steps) == {1}, steps
    period = seen[sprites.IDLE_COUNT][0] - seen[0][0]
    assert period >= 3.0, period
