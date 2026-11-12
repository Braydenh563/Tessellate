"""A hang spot at the screen top is always offered (INBOX 1696 k, owner: "now its not even hanging from the top of my
screen"). The work area's top is an edge whatever the windows option says and however few windows are open (the log
read "hang spots 0"): the trip table lists a hang once the big-act gap is up. Fixed clock."""

from __future__ import annotations

import random

import pytest

from tessellate.core.overlay.engine import Engine, Monitor

SIZE = (100, 120)
ONE = [Monitor((0, 0, 1920, 1040), 96)]
TWO_STACKED = [Monitor((0, 0, 1920, 1040), 96), Monitor((0, -1080, 1920, 0), 96)]


def make(monitors=ONE, **kw) -> Engine:
    e = Engine(SIZE, monitors, rng=random.Random(3), home=(800, 920), hang_top=0.195, **kw)
    e.big_ready = 0.0
    return e


def kinds(e: Engine) -> list[str]:
    return [trip for _dest, trip, _w in e._trip_table(100.0)]


@pytest.mark.parametrize("windows", [True, False])
def test_the_top_of_the_work_area_is_offered_with_no_window_at_all(windows: bool) -> None:
    e = make(roam_windows=windows)
    e.set_windows([], 1.0)
    assert "hang" in kinds(e)


def test_it_is_not_offered_when_another_screen_sits_above_the_top() -> None:
    e = make(TWO_STACKED)
    e.set_windows([], 1.0)
    assert "hang" not in kinds(e)
