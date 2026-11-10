"""A throw that crosses a side edge (the wrap) stops at the top like any flight: the ceiling check runs only for a
plain throw, so a wrapping figure thrown hard upward rose through an open top (CI on PR 216, ride seed 1: 32 px cut)."""

from __future__ import annotations

import pytest

from tests.test_overlay_ride_1670 import LOOKS, make


@pytest.mark.parametrize("look", LOOKS)
def test_a_wrapping_throw_never_draws_above_the_top(look: str) -> None:
    e, _s = make(look, "walk", 1)
    e.state, e.y, e.vx, e.vy = "fly", 60.0, -900.0, -1600.0
    e.wrapping = {"side": -1, "far": 1800.0, "phase": "out"}
    top = e._ride_limits("fly")[2]
    for _ in range(40):
        e._wrap_step(0.016)
        assert e.y >= top - 0.01, (e.y, top)
