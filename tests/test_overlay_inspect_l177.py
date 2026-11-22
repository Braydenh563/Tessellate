"""L177: the desk companion climbs a window's side and inspects the window's corner, the clock and the cursor. Fixed clock, seeded.

What does each: the side climb is `_climb` (`_climb_sides` lists both sides of a window with room), the clock is the trip to the
screen's bottom-right corner that ends in a look (`_arrive_trip`), the cursor is `follow` that ends in a look at it
(`glance_pointer`, `peer_at_cursor`), and the window's corner is `peek_down` on a top (`PERCH_PEER_BOOST`). Measured 2026-11-21 over
4,000 picks on a top: `peek_down` 0.9% before, 3.6% after (x4)."""

from __future__ import annotations

import random

import pytest

from tessellate.core.overlay import behaviour as bh
from tessellate.core.overlay import gaze
from tessellate.core.overlay.engine import Perch
from tests.test_overlay_moves import SIZE, make, step
from tests.test_overlay_roam import WIN, climb


def _share(act: str, where: str, boost: float, picks: int = 4000) -> float:
    saved = bh.PERCH_PEER_BOOST
    bh.PERCH_PEER_BOOST = boost
    try:
        rng = random.Random(11)
        mind = bh.Mind(1000.0)
        got = 0
        for i in range(picks):
            got += mind.pick(rng, 1000.0 + i * 40.0, "walk", 14, where) == act
        return got / picks
    finally:
        bh.PERCH_PEER_BOOST = saved


def test_on_a_window_top_it_peers_down_over_the_edge_far_more_often_than_on_the_floor() -> None:
    before, after = _share("peek_down", "perch", 1.0), _share("peek_down", "perch", bh.PERCH_PEER_BOOST)
    floor = _share("peek_down", "", bh.PERCH_PEER_BOOST)
    assert after > before * 2.5, (before, after)
    assert abs(floor - _share("peek_down", "", 1.0)) < 1e-9, "the floor's table is untouched"
    assert "peek_down" in gaze.ATTEND_ACTS, "a peer is a held look, its eyes take small steps"


def test_the_clock_trip_ends_in_a_look_at_it() -> None:
    seen = set()
    for seed in range(1, 25):
        e = make(seed=seed)
        e._arrive_trip("clock", 100.0)
        seen.add(e.act)
        assert e.act in gaze.ATTEND_ACTS and e.state == "act", (seed, e.act)
    assert seen <= {"ponder", "look_around"} and len(seen) == 2


def test_the_cursor_is_looked_at_when_it_is_followed_to() -> None:
    assert {"glance_pointer", "peer_at_cursor"} <= gaze.ATTEND_ACTS
    assert bh.ACTIVITIES["peer_at_cursor"].frame == "look" and "peer_at_cursor" in bh.ATTENTION


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_a_walker_beside_a_window_climbs_its_side_onto_the_top(seed: int) -> None:
    e = make(seed=seed)
    sides = e._climb_sides(WIN, e.current_monitor().area, SIZE[0])
    assert sides and all(abs(x - WIN.left + SIZE[0]) < 1 or abs(x - WIN.right) < 1 for x in sides)
    t = climb(e)
    t, _ = step(e, t, 0.6)
    assert e.perch == WIN and e.y == WIN.top - SIZE[1]
    assert isinstance(WIN, Perch)
