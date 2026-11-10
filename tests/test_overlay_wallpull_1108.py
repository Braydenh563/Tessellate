"""Edges-1107 "Left" (INBOX 1683 x, y): the wall-slide scrabble on a screen side ends in a pull-up onto the nearest window
top edge within reach, else a landing. Fake clock, no Win32; real Windows is unverified."""

from __future__ import annotations

import math

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import engine as eng  # noqa: E402
from tessellate.core.overlay import landing as ld  # noqa: E402
from tests.overlay_tumble_1670 import STEP, make  # noqa: E402


def sliding(monkeypatch: pytest.MonkeyPatch, windows: list, side: int = -1, y: float = 300.0):
    """A walker smacked against the `side` wall (-1 left, 1 right) at height `y` and sticking, with `windows` listed."""
    monkeypatch.setattr(ld, "smack", lambda speed, scale, rng: "slide")
    e, _s = make("masculine", "walk", 3)
    e.big_ready = e.trip_ready = e.climb_ready = math.inf
    e.x, e.y = 800.0, y
    e.update(1.0)
    e.set_windows(windows, 1.0)
    e._start_fly(side * 2600.0, 0.0)
    t = 1.0
    for _ in range(60):
        t += STEP
        e.update(t)
        if e.wall:
            return e, t
    raise AssertionError("never stuck to the wall")


def run(e, t: float, secs: float, until):
    for _ in range(int(secs / STEP)):
        t += STEP
        e.update(t)
        if until(e):
            break
    return t


def test_the_scrabble_ends_in_a_pull_up_onto_a_window_top_within_reach(monkeypatch: pytest.MonkeyPatch) -> None:
    near = eng.Perch(7, 40, 560, 700)
    e, t = sliding(monkeypatch, [near])
    started = t
    t = run(e, t, 3.0, lambda en: en.state == "rise")
    assert e.state == "rise" and e.wall == 0 and e.angle == 0.0
    assert t - started >= eng.WALL_SCRABBLE - 0.1  # it scrabbled a beat first, as a hang slip does
    assert e.phase_to[1] == pytest.approx(near.top - e.size[1])
    assert near.left <= e.phase_to[0] <= near.right - e.size[0]
    run(e, t, 4.0, lambda en: en.state == "stand")
    assert e.state == "stand" and e.perch is not None and e.perch.key == 7 and not e.grounded


def test_the_nearest_of_two_tops_is_taken(monkeypatch: pytest.MonkeyPatch) -> None:
    far, near = eng.Perch(8, 40, 860, 900), eng.Perch(9, 40, 640, 900)
    e, t = sliding(monkeypatch, [far, near])
    run(e, t, 3.0, lambda en: en.state == "rise")
    assert e.state == "rise" and e.target is not None and e.target.key == 9


def test_the_right_wall_pulls_up_onto_a_window_at_that_side(monkeypatch: pytest.MonkeyPatch) -> None:
    right = eng.Perch(5, 1300, 740, 1900)
    e, t = sliding(monkeypatch, [right], side=1)
    run(e, t, 3.0, lambda en: en.state == "rise")
    assert e.state == "rise" and e.phase_to[0] + e.size[0] <= right.right


def test_with_no_window_in_reach_it_slides_on_and_lands(monkeypatch: pytest.MonkeyPatch) -> None:
    out_of_reach = eng.Perch(6, 900, 560, 1500)  # a window far from the wall
    e, t = sliding(monkeypatch, [out_of_reach])
    seen = set()
    for _ in range(int(8.0 / STEP)):
        t += STEP
        e.update(t)
        seen.add(e.state)
        if e.state != "fly":
            break
    assert "rise" not in seen and e.state != "fly" and e.wall == 0


def test_a_top_too_high_for_the_figure_to_stand_on_is_not_taken(monkeypatch: pytest.MonkeyPatch) -> None:
    e, t = sliding(monkeypatch, [eng.Perch(4, 40, 30, 700)])  # its top leaves no room above it on screen
    seen = set()
    for _ in range(int(8.0 / STEP)):
        t += STEP
        e.update(t)
        seen.add(e.state)
        if e.state != "fly":
            break
    assert "rise" not in seen
