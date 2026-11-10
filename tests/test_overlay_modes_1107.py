"""Ledger N8: the portal is the escape (a window throws the figure off and it may open one) and stays one of the
travel modes. Over the seeded one-hour runs no mode is more than 40 percent of the legs, the portal is at least 5
percent and the puff under 15. Fixed clock, seeded randomness; nothing here runs on real Windows."""

from __future__ import annotations

from collections import Counter

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import travel as tv
from tests.overlay_sim_1670 import simulate
from tests.test_overlay_fling_1107 import drag, on_top

SEEDS = (1, 2, 3, 4, 5, 6)
TRAVEL = set(tv.MODES)


def test_the_portal_and_the_puff_stay_travel_modes_and_are_the_escapes() -> None:
    assert {"portal", "puff"} <= TRAVEL
    for seed in range(40):
        e = on_top(seed=seed)
        drag(e, eng.FLING_SPEED * 1.5)
        assert e.last_fling in ("fall", *TRAVEL)


def test_an_escape_is_logged_as_the_leg_it_is() -> None:
    for seed in range(60):
        e = on_top(seed=seed)
        drag(e, eng.FLING_SPEED * 1.5)
        if e.last_fling in ("portal", "puff"):
            assert e.legs[-1][0] == e.last_fling and e.modes[-1] == e.last_fling
            return
    raise AssertionError("no escape in sixty seeds")


def test_the_seeded_hour_shares_of_the_travel_modes() -> None:
    legs: Counter = Counter()
    for gait in ("walk", "float"):
        for seed in SEEDS:
            legs.update(leg[0] for leg in simulate(gait, seed)["legs"] if leg[0] in TRAVEL)
    total = sum(legs.values())
    assert total >= 100, legs
    share = {mode: n / total for mode, n in legs.items()}
    assert max(share.values()) < 0.40, share
    assert share.get("portal", 0.0) >= 0.05, share
    assert share.get("puff", 0.0) < 0.15, share
