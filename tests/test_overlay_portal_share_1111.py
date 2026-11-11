"""The portal's share of the desk companion's trips (E6, companion-asks N9, 1683 x 4 and u): the owner wants it
for long trips and as the escape, not every trip ("only ever poofs"). Measured over the seeded hour (both gaits, six seeds,
the travel legs) and over `pick_mode` itself; fixed seeds, no clock."""

from __future__ import annotations

import random
from collections import Counter

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import travel as tv  # noqa: E402
from tests.overlay_sim_1670 import simulate  # noqa: E402

SEEDS = (1, 2, 3, 4, 5, 6)


def hour_legs() -> Counter:
    legs: Counter = Counter()
    for gait in ("walk", "float"):
        for seed in SEEDS:
            legs.update(leg[0] for leg in simulate(gait, seed)["legs"] if leg[0] in tv.MODES)
    return legs


def picks(long_leg: bool, gait: str = "walk", mood: str = "calm", n: int = 4000) -> Counter:
    rng = random.Random(7)
    recent: list[str] = []
    counts: Counter = Counter()
    for _ in range(n):
        mode = tv.pick_mode(rng, gait=gait, long_leg=long_leg, mood=mood, recent=recent, edge_ok=True)
        counts[mode] += 1
        recent.append(mode)
        del recent[:-3]
    return counts


def test_the_portal_is_between_one_in_twenty_and_one_in_five_trips_of_the_seeded_hour() -> None:
    legs = hour_legs()
    total = sum(legs.values())
    assert total >= 100, legs
    share = legs["portal"] / total
    assert 0.05 <= share <= 0.18, (round(share, 3), dict(legs))  # measured 0.099 over 333 legs
    assert max(legs.values()) / total < 0.30, dict(legs)  # and no one mode runs the hour (measured: glide 0.24)


@pytest.mark.parametrize("gait", ["walk", "float"])
def test_the_portal_is_chosen_more_for_a_long_trip_than_for_a_short_one(gait: str) -> None:
    far, near = picks(True, gait), picks(False, gait)
    far_share, near_share = far["portal"] / sum(far.values()), near["portal"] / sum(near.values())
    assert far_share > near_share * 1.5, (far_share, near_share)
    assert 0.05 <= far_share <= 0.20 and near_share <= 0.10, (far_share, near_share)


def test_the_portal_is_never_the_same_trip_twice_in_a_row() -> None:
    rng = random.Random(3)
    recent: list[str] = []
    for _ in range(2000):
        mode = tv.pick_mode(rng, gait="walk", long_leg=True, mood="happy", recent=recent, edge_ok=True)
        assert not (recent and mode == "portal" == recent[-1])
        recent.append(mode)
