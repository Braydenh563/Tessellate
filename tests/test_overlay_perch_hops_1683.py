"""INBOX 1683 (travel-1109 L10): a hop chain on a window top (a perch) has a seeded measure. A hop-chain leg is the
walker's `_do_walk` with a lift drawn over it (`Engine._hop_arc`): on a perch the same leg must keep the body on the
window's top (no fall off the edge, the perch kept), lift the drawn figure by at most `HOP_RISE` of its height, make one
hop per `HOP_SPAN` figure widths of ground, ease the lift to nothing at the arrival and stand there. Seeded sweep over
both looks, both directions and eight seeds on the engine with a fixed clock; real Windows (the hop picture at 1440 and 4K)
is not run here."""

from __future__ import annotations

import math

import pytest

from tessellate.core.overlay import engine_consts as consts
from tessellate.core.overlay.engine import Perch
from tests.test_overlay_ride_1670 import make

WIN = Perch(11, 400, 500, 1400)
TICK = 1.0 / 60.0


def hop_leg(seed: int, look: str, rightward: bool, win: Perch = WIN) -> dict:
    """Stand on `win`, ask for a hop-chain leg across most of its top, tick until it is over."""
    e, _s = make(look, "walk", seed)
    e.roam = True
    t = 1.0
    e.update(t)
    e.set_windows([win], t)
    e._stand_on(win, t)
    w = e.size[0]
    e.x = win.left + 20.0 if rightward else win.right - w - 20.0
    for _ in range(80):  # the landing is over
        t += TICK
        e.update(t)
    e._leg_mode = lambda goal, then: "jump"  # the leg is a hop chain, whatever the table would have drawn
    goal_x = win.right - w - 20.0 if rightward else win.left + 20.0
    start_x, base_y = e.x, e.y
    e._go((goal_x, e.y), "stand", t)
    rows: list[tuple[str, float, float, bool]] = []
    for _ in range(60 * 30):
        t += TICK
        e.update(t)
        rows.append((e.state, e.hop_lift, e.y, e.perch is not None))
        if len(rows) > 10 and e.state == "stand" and e.goal is None and not e.hopping:
            break
    lifts = [r[1] for r in rows]
    peak = max(lifts)
    # one hop is one hump of the lift: count the local maxima that reach half the highest
    humps = sum(1 for a, b, c in zip(lifts, lifts[1:], lifts[2:]) if b > a and b >= c and b > 0.5 * peak)
    return {
        "e": e, "rows": rows, "humps": humps, "peak": peak, "dist": abs(goal_x - start_x), "goal_x": goal_x, "base_y": base_y,
        "end_lift": lifts[-1], "secs": len(rows) * TICK,
    }


@pytest.mark.parametrize("look", ["masculine", "feminine"])
@pytest.mark.parametrize("rightward", [True, False])
@pytest.mark.parametrize("seed", range(1, 5))
def test_a_hop_chain_on_a_window_top_hops_in_place_of_the_walk_and_stays_on_it(look: str, rightward: bool, seed: int) -> None:
    got = hop_leg(seed, look, rightward)
    e, rows = got["e"], got["rows"]
    h = e.size[1]
    assert {r[0] for r in rows} <= {"crouch", "walk", "stand"}, {r[0] for r in rows}  # wound up, hopped, stood: never a fall
    assert all(r[3] for r in rows)  # the perch kept the whole leg
    assert max(abs(r[2] - got["base_y"]) for r in rows) < 0.01  # the body stays on the window's top: only the drawing lifts
    assert 0.9 * consts.HOP_RISE * h <= got["peak"] <= consts.HOP_RISE * h + 0.01  # measured 24.3 px of 152 (0.16)
    span = consts.HOP_SPAN * e.size[0]
    assert abs(got["humps"] - got["dist"] / span) <= 1.5, (got["humps"], got["dist"] / span)  # measured 6 hops over 5.2 spans
    assert got["end_lift"] < 0.5  # eased out over the last span: it lands where it stops
    assert abs(e.x - got["goal_x"]) < 1.0 and e.state == "stand" and e.perch is not None
    assert got["secs"] < 12.0  # 816 px at the walk pace and a wind-up: 7.8 s measured


def test_a_hop_chain_never_carries_it_past_the_end_of_a_narrow_window() -> None:
    narrow = Perch(12, 700, 500, 1000)  # 300 px, a figure and a half
    for seed in range(1, 5):
        got = hop_leg(seed, "masculine", True, narrow)
        e = got["e"]
        assert all(r[3] for r in got["rows"]) and narrow.left <= e.x + e.size[0] / 2 <= narrow.right, (seed, e.x)  # its middle stays on the window (`_reach`)
        assert not any(math.isnan(r[1]) for r in got["rows"])
