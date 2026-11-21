"""L139. With no window on the screen at all the companion still makes its trips, to the floor and to an edge, and not too often.

Measured on this branch, three simulated hours, seeds 1 to 4, a walker and a floater each: 5 to 8 trips (1.7 to 2.7 an hour), every
destination the floor (the clock corner, an edge nap, a long walk) or a hang, none a window.
"""

from __future__ import annotations

import collections

import pytest

from tests.test_overlay_moves import make


@pytest.mark.parametrize("gait", ["walk", "float"])
@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_trips_go_to_places_with_no_window_and_stay_a_few_an_hour(seed: int, gait: str) -> None:
    e = make(seed=seed, gait=gait)
    kinds: collections.Counter[str] = collections.Counter()
    note = e._note_dest

    def counted(kind: str) -> None:
        kinds[kind] += 1
        note(kind)

    e._note_dest = counted  # type: ignore[method-assign]
    e.set_windows([], 0.0)
    t, out = 0.0, e.update(0.0)
    while t < 3 * 3600:
        t += (out.wake_ms or 1000) / 1000.0
        out = e.update(t, event=("move", 0, 0)) if int(t) % 25 == 0 else e.update(t)
    assert 4 <= e.trips <= 9, e.trips
    assert set(kinds) <= {"floor", "hang"} and kinds["floor"] >= 2, kinds
    assert "window" not in kinds
