"""INBOX 1692, the owner 2026-11-08: "when the desktop companion moves like walking instead of teleporting
(specifically for atlas ...), it still looks like it hobbles along and its eyes blick ferociously but atlas doesnt
walk, it doesnt have legs, it floats like a wind spirit". Atlas's shipped walk frames close its eyes on every
other frame and bob the body, so a floater's trip never draws them: it streams on its idle cycle."""

from __future__ import annotations

import random

from tessellate.core.overlay.engine import Engine, Monitor

SIZE = (100, 120)
ONE = [Monitor((0, 0, 1920, 1040), 96)]


def trip_frames(gait: str, seed: int) -> set[str]:
    e = Engine(SIZE, ONE, rng=random.Random(seed), home=(300, 1040 - 120), gait=gait, idle_frames=24)
    e.big_ready = e.climb_ready = float("inf")
    e.plain_legs = True
    out = e.update(0.0)
    e._go((1500.0, e.ground_y()), "stand", 0.0, plain=True)
    t, frames = 0.0, set()
    while t < 30:
        t += (out.wake_ms or 50) / 1000.0
        out = e.update(t)
        if e.state in ("walk", "drift"):
            frames.add(out.frame)
    return frames


def test_a_floater_never_draws_the_walk_cycle_on_a_trip() -> None:
    seen = set()
    for seed in range(1, 7):
        seen |= trip_frames("float", seed)
    assert seen, "no trip"
    assert not {f for f in seen if f.startswith("walk")}, sorted(seen)
    assert {f for f in seen if f.startswith("idle")}, sorted(seen)


def test_a_walker_still_walks() -> None:
    seen = set()
    for seed in range(1, 7):
        seen |= trip_frames("walk", seed)
    assert {f for f in seen if f.startswith("walk")}, sorted(seen)
