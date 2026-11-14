"""L-ui-modernisation-140: a floater's dash ends at its goal, never stepping past it and back for ever.

Found under L-ui-modernisation-99: a seeded desk hour (float seed 3) drifted 86% of the hour, 2 px either side of its
home spot. The dash's step near the goal (4.1 px a 0.1 s tick) was over twice the arrival radius (2 px), so each tick
stepped past the goal, turned, and stepped back.
"""

from __future__ import annotations

import pytest

from tests.test_overlay_ride_1670 import make


@pytest.mark.parametrize("mode", ["dash", "walk", "step"])
def test_every_drift_leg_arrives(mode: str) -> None:
    stuck = []
    for i in range(60):
        dx = 200.0 + i * 3.37  # 375.24 px is one that stepped back and forth before
        e, _ = make(gait="float", seed=3)
        e.update(1.0)
        e._go((e.x + dx, e.ground_y()), "home", 1.0, plain=True)
        e.mode = mode
        t = 1.0
        while t < 40.0 and e.state == "drift":
            t += 0.1
            e.update(t)
        if e.state == "drift":
            stuck.append(round(dx, 2))
    assert not stuck, stuck
