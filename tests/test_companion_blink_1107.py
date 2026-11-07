"""Research G2: a blink goes with a large gaze shift or head turn (Eyes Alive: blinks accompany big gaze
changes). Seeded streams, fixed clock, no Win32."""

from __future__ import annotations

import random

from tessellate.core.overlay import engine as eng

ONE = [eng.Monitor((0, 0, 1920, 1040), 96)]


def make() -> eng.Engine:
    e = eng.Engine((100, 120), ONE, rng=random.Random(7), idle_frames=0, home=(800, 920))
    e.set_metrics({("stand", False): (10.0, 10.0, 90.0, 118.0), ("stand", True): (10.0, 10.0, 90.0, 118.0)})
    e.update(0.1)
    return e


def test_a_look_starts_with_a_blink_then_the_look() -> None:
    e = make()
    e.life_rng.random = lambda: 0.0  # type: ignore[method-assign]  # always a look, never a double
    e.next_ambient = 1.0
    seen = []
    t = 1.0
    while t < 1.0 + eng.BLINK_FOR + eng.LOOK_FOR + 0.3:
        e.update(t)
        seen.append(e.flash[0] if e.flash else None)
        t += 0.02
    run = [s for s in seen if s]
    assert run[0] == "blink" and "look" in run and run.index("look") > run.index("blink")


def test_a_head_turn_starts_a_blink_and_reduced_motion_does_not() -> None:
    e = make()
    assert e.flash is None
    e._face(-e.facing, 2.0)
    assert e.turn_to != 0 and e.flash is not None and e.flash[0] == "blink"
    e2 = make()
    e2.reduced = True
    e2._face(-e2.facing, 2.0)
    assert e2.flash is None
