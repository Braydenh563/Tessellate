"""INBOX 1683 (u, j), the owner's standing ask for travel that is seen (walk, glide, jump, climb, not teleport): a
ground figure can cross a long leg as a chain of hops. The drawn feet leave the floor in arcs and land on it, the
body never leaves the walkable floor (no fall), the leg ends at its goal, and the leg mix has hops in it. Fixed clock;
real Windows is unverified."""
from __future__ import annotations

import random
from collections import Counter

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import travel as tv
from tests.test_overlay_ride_1670 import make


def _hop_leg(seed: int = 3):
    e, _s = make("masculine", "walk", seed)
    e.x = 100.0
    e._place_on_floor()
    e.last_x = e.x
    e.update(0.0, None)
    goal = (1500.0, e.y)
    e.modes.append("jump")
    e._leg_mode = lambda g, t: "jump"
    e._go(goal, "settle", 0.1)
    return e, goal


def test_a_hop_leg_leaves_the_floor_in_arcs_and_lands_on_the_goal() -> None:
    e, goal = _hop_leg()
    lifts, frames, t = [], Counter(), 0.1
    while t < 40.0 and e.state in ("walk", "crouch"):
        t += 1 / 60
        o = e.update(t, None)
        lifts.append(e.hop_lift)
        frames[o.frame] += 1
        assert e.state != "fall"
    assert abs(e.x - goal[0]) < 2.0
    hops = sum(1 for a, b in zip(lifts, lifts[1:]) if a > 0.5 and b <= 0.5)
    assert hops >= 4, hops
    assert 0.1 * e.size[1] <= max(lifts) <= 0.3 * e.size[1], max(lifts)
    assert frames["hop"] > 20 and sum(v for k, v in frames.items() if k.startswith("walk")) > 20
    assert e.hop_lift == 0.0


def test_the_drawn_feet_never_step_more_than_a_frame_of_arc() -> None:
    e, _goal = _hop_leg(5)
    feet, t = [], 0.1
    while t < 40.0 and e.state in ("walk", "crouch"):
        t += 1 / 60
        o = e.update(t, None)
        feet.append(o.y + e._box(o.frame, False)[3])  # the drawn lowest row: frames carry their own foot offsets
    steps = [abs(b - a) for a, b in zip(feet, feet[1:])]
    assert max(steps) <= 0.04 * e.size[1], (max(steps), e.size[1])


def test_the_mode_table_offers_hops_to_a_walker_and_never_to_a_floater() -> None:
    def shares(gait: str) -> Counter:
        rng, recent, c = random.Random(1), [], Counter()
        for i in range(2000):
            m = tv.pick_mode(rng, gait=gait, long_leg=i % 2 == 0, mood="happy", recent=recent[-3:], edge_ok=True)
            recent.append(m)
            c[m] += 1
        return c

    walker, floater = shares("walk"), shares("float")
    assert walker["jump"] / 2000 >= 0.07 and floater["jump"] == 0
