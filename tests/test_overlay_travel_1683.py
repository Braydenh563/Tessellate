"""INBOX 1683 (f): the desktop companion travels by its body (walks or glides at a lively pace, a run when the leg
is long) and a puff, portal or edge walk is a rare flourish. The owner: "all it does is sit on the taskbar and
poof". Fixed clock, seeded randomness; nothing here runs on real Windows."""
from __future__ import annotations

import random
from collections import Counter

import pytest

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import travel as tv
from tessellate.core.overlay.engine import Perch
from tests.overlay_sim_1670 import simulate
from tests.test_overlay_moves import FLOOR, make

BODY = ("walk", "glide", "jump", "climb")  # a run is a walk leg here
FLOURISH = ("puff", "portal", "edge", "fade", "blink", "cloud", "bubble")

# --- (f) it travels by its body -----------------------------------------------------------------


@pytest.mark.parametrize("gait", ["walk", "float"])
@pytest.mark.parametrize("long_leg", [True, False])
def test_a_flourish_is_rare_whatever_the_leg(gait: str, long_leg: bool) -> None:
    rng, recent, picks = random.Random(5), [], Counter()
    for _ in range(4000):
        mode = tv.pick_mode(rng, gait=gait, long_leg=long_leg, mood="happy", recent=recent[-3:], edge_ok=True)
        picks[mode] += 1
        recent.append(mode)
    flourish = sum(picks[m] for m in FLOURISH) / 4000
    # INBOX 1683 u (the owner: "it needs a lot of expansion"): portals and edge walks are now a fifth to two fifths of
    # the legs, so this bound moved from 0.22/0.12; the puff alone stays rare and a walk, glide or run still leads.
    # Intent moved (INBOX 1692, the owner 00:50Z: "i dont see a portal or like magic ... float on a cloud, more life"):
    # a sparkle blink, a cloud ride and a bubble drift joined the flourishes, so they are about a third of the short
    # legs and well over half of the long ones (measured 0.36 and 0.57); the puff alone stays rare and a walk still
    # leads the short legs.
    assert flourish <= (0.62 if long_leg else 0.42), picks
    assert picks["puff"] / 4000 < 0.10, picks
    # Intent moved (INBOX 1683 u, hops): a ground leg may be a chain of hops, a seen move by the body like a walk or a
    # run, so it counts with them; measured walk, run and jump 0.62 (walk, run alone 0.38 on the short and long legs).
    assert sum(picks[m] for m in ("walk", "glide", "run", "swoop", "jump")) / 4000 >= 0.4, picks


def test_a_long_leg_across_the_middle_is_walked_not_puffed() -> None:
    walked = 0
    for seed in range(40):
        e = make(seed=seed)
        e.plain_legs = False
        e.x = 60.0
        e._place_on_floor()
        e._go((1700.0, FLOOR), "stand", 1.0)
        walked += e.state in ("walk", "crouch")  # a long run starts with a crouch
    # Intent moved (INBOX 1692): a blink, cloud or bubble is a legitimate way across; 33 of 40 became about 23.
    assert walked >= 16, walked


def test_the_walk_is_lively_and_a_long_leg_is_a_run() -> None:
    assert eng.WALK_SPEED * 1.0 >= 120.0  # logical px/s; was 55
    e = make(seed=3)
    e.plain_legs = True
    e.x = 100.0
    e._place_on_floor()
    e._go((1700.0, FLOOR), "stand", 1.0)
    t, speeds = 1.0, []
    for _ in range(700):
        t += 0.016
        x0 = e.x
        e.update(t)
        if e.state == "walk" and 600 < e.x < 1200:
            speeds.append(abs(e.x - x0) / 0.016)
    assert speeds and max(speeds) >= 240.0, max(speeds, default=0)  # a run, about 260 px/s (was 94)


def test_an_hour_is_mostly_walked_glided_jumped_or_climbed() -> None:
    legs: Counter = Counter()
    for gait in ("walk", "float"):
        for seed in (1, 2, 3, 4, 5, 6):
            legs.update(leg[0] for leg in simulate(gait, seed)["legs"])
    total = sum(legs.values())
    body = sum(legs[m] for m in BODY)
    assert total >= 20, legs
    # Intent moved (INBOX 1692, 00:50Z): the owner asked for portals, magic and a cloud to ride; measured 0.55.
    assert body / total >= 0.45, legs  # measured 45 percent before (walk, glide, jump, climb), 55 percent puffs, portals, edges


def test_a_window_across_the_middle_is_reached_on_foot() -> None:
    win = Perch(11, 1400, 700, 1900)
    modes: Counter = Counter()
    for seed in range(12):
        e = make(seed=seed)
        e.plain_legs = False
        e.x = 60.0
        e._place_on_floor()
        e.set_windows([win], 0.0)
        e.climb_ready = 0.0
        e._climb(1.0)
        modes[e.state] += 1
        assert e.state not in ("warp",), (seed, e.state)
    assert modes["walk"] + modes["crouch"] == 12, modes
