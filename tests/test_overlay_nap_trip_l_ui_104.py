"""L-ui-modernisation-104: a nap it takes on its own trip ends, with the person about.

The cause: the nap trip (`Engine._start_trip`) walks to an edge and settles to sleep with `nap_req` unset, so the sleep
had no end of its own (`nap_until` 0) and only a touch woke it; a moving pointer and a refreshed `last_active` never did.
Walk seed 4 slept 68% of a seeded hour and float seed 3 44% that way.
"""

from __future__ import annotations

import random

import pytest

from tessellate.core.overlay import engine_consts as ec
from tests.test_overlay_ride_1670 import make


def _person_about(e, secs: float, seed: int, t: float = 0.0) -> tuple[float, float]:
    """`secs` seconds with the pointer moved and `last_active` refreshed every 10 to 30 s; the share asleep."""
    person = random.Random(100 + seed)
    nxt, asleep, end = t + 5.0, 0, t + secs
    while t < end:
        t += 0.1
        pointer = None
        if t >= nxt:
            nxt = t + person.uniform(10.0, 30.0)
            pointer = (person.randint(100, 1800), person.randint(100, 900))
            e.last_active = t
        e.update(t, pointer)
        asleep += e.state == "sleep"
    return t, asleep / (secs / 0.1)


@pytest.mark.parametrize("gait", ["walk", "float"])
def test_a_nap_trip_ends_by_itself_with_a_stretch(gait: str) -> None:
    e, _ = make(gait=gait, seed=4)
    e.update(1.0)
    e._trip_pick = lambda now: "nap"
    e.trip_ready = 0.0
    e._start_trip(2.0)
    t, slept_at = 2.0, None
    while t < 120.0 and slept_at is None:
        t += 0.1
        e.last_active = t
        e.update(t)
        slept_at = t if e.state == "sleep" else None
    assert slept_at is not None, e.state
    assert 0.0 < e.nap_until - slept_at <= ec.NAP_FOR[1] + 0.2, e.nap_until
    _person_about(e, ec.NAP_FOR[1] + 20.0, 4, t)
    assert e.state != "sleep"


def test_a_seeded_half_hour_with_the_person_about_is_not_mostly_asleep() -> None:
    e, s = make(gait="walk", seed=4)
    e.extra_frames = frozenset(s.extras())
    _t, share = _person_about(e, 1800.0, 4)
    assert share <= 0.15, share  # 0.37 before (0.68 over the hour)
