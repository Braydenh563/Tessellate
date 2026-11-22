"""L185 (owner ask 1670 i): a companion that is not Atlas walks, runs, climbs, crouches, sits and lies on the desk.

The audit asked to confirm the frames exist. A companion made from a name walks (`gait="walk"`) and has only the
frames `capture.CAPTURED` takes from the app, so each of those behaviours must resolve to one of them: the run is the
dash on the walk cycle (a hop in the air), the crouch is the landing squat, the climb rises on the hop and holds on
the hang, the lie is the sleep."""

from __future__ import annotations

import random

import pytest

from tessellate.core.overlay import capture
from tessellate.core.overlay.engine import Engine, Monitor

ONE = [Monitor((0, 0, 1920, 1040), 96)]


def walker() -> Engine:
    return Engine((100, 120), ONE, rng=random.Random(3), home=(800, 920), gait="walk")


@pytest.mark.parametrize(
    ("state", "mode", "expect"),
    [
        ("walk", "walk", "walk"),
        ("walk", "dash", "walk"),
        ("crouch", None, "land"),
        ("rise", None, "hop"),
        ("hang", None, "hang"),
        ("sit", None, "sit"),
        ("sleep", None, "sleep"),
        ("stand", None, None),
    ],
)
def test_each_desk_behaviour_of_a_walker_draws_a_frame_it_was_given(state, mode, expect) -> None:
    e = walker()
    e.state = state
    if mode:
        e.mode = mode
    if state == "rise":
        e.then = "perch"
    frame = e._frame(5.0)
    assert frame in capture.CAPTURED, (state, frame)
    if expect:
        assert frame.rstrip("0123456789") == expect, (state, frame)


def test_the_run_steps_through_the_walk_cycle() -> None:
    e = walker()
    e.state, e.mode = "walk", "dash"
    seen = set()
    for i in range(40):
        e.travel = i * 9.0
        seen.add(e._frame(5.0))
    assert len(seen) > 4 and all(f in capture.CAPTURED for f in seen)
