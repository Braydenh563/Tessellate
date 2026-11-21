"""L181's definition of done: a lifelike, diverse desk companion, measured on the seeded hours (fixed clock, fixed seeds).

Measured 2026-11-21 on the head with the L178 acts: 63.5 distinct acts a seeded hour on the desk Mind (the least 52),
ten ways of getting about across the six rest hours (blink, bubble, climb, cloud, edge, glide, jump, portal, run, walk),
17 chains of acts that belong together over five moods, and still home most of the hour (moving 0.005 to 0.013)."""

from __future__ import annotations

import statistics

from tessellate.core.overlay import behaviour as bh
from tessellate.core.overlay import extras
from tests.test_companion_weights_1108 import HOURS, SEEDS, _desk_hour
from tests.test_overlay_rest_1670 import GAITS, hour
from tests.test_overlay_rest_1670 import SEEDS as REST_SEEDS


def test_an_hour_on_the_desk_is_many_different_acts() -> None:
    counts = [len(_desk_hour(s, h)) for h in HOURS for s in SEEDS]
    assert statistics.mean(counts) >= 55 and min(counts) >= 45, counts


def test_it_gets_about_in_many_ways_and_still_stays_home() -> None:
    kinds: set[str] = set()
    for gait in GAITS:
        for seed in REST_SEEDS:
            m = hour(gait, seed)
            kinds |= set(m["modes"]) | set(m["warps"])
            assert m["moving_share"] <= 0.03, (gait, seed, m["moving_share"])
    assert len(kinds) >= 8, kinds


def test_the_mind_has_chains_over_the_moods() -> None:
    extras.register()
    assert len(bh.CHAINS) >= 15
    assert len({m for c in bh.CHAINS for m in (c.moods or ())}) >= 5
