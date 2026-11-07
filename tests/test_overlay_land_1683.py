"""INBOX 1683 (v), the owner on Windows: "it keeps turning even after it lands when I throw it", then "it doesnt land
right" (a screenshot of the desk figure resting on the floor, drawn tilted about 45 degrees). Measured on the engine with
the shipped frames' alpha and a fixed clock. Before: from the first floor contact a thrown figure took 1.9 to 3.5 s
(walker) and 1.2 to 3.0 s (floater) to be laid, because the righting was a soft spring (2.6 rad/s) behind a 0.4 s ramp
and the laid pose also waited 0.3 s of being slow; a landing added a spin kick; and a bounce while righting re-added
turn. Then the first floor contact paid the turn out as one eased move to the nearest upright.

Intent moved (INBOX 1683 k, the owner: "I want it to either land on tis feet, land on its back or stomach and like skid"):
a landing now ends on the feet, the back or the belly (`landing.decide`), and a lie gets up again. What stays pinned here
is the owner's complaint of (v): from the first floor contact the body reaches its outcome in one move, is never drawn
turned once laid, has its feet on the line it rests on, and ends standing upright and still within a bounded time."""

from __future__ import annotations

import math

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import engine as eng  # noqa: E402
from tests.overlay_tumble_1670 import AREA, _release, make  # noqa: E402

DEG = math.pi / 180.0
#: (name, speed px/s, direction rad, middle of the figure when let go)
KINDS = [
    ("soft", 400.0, 1.2, (900.0, 700.0)),
    ("hard", 1800.0, -0.3, (900.0, 600.0)),
    ("wall", 1800.0, 0.0, (1500.0, 500.0)),
    ("corner", 1800.0, 0.8, (1700.0, 700.0)),
    ("fast_down", 1500.0, 1.5, (900.0, 500.0)),
    ("upside_down", 900.0, 1.4, (900.0, 600.0)),
]


def wrapped(a: float) -> float:
    return a - round(a / (2 * math.pi)) * 2 * math.pi


def fly(gait: str, kind: tuple, look: str = "masculine") -> dict:
    name, speed, direction, at = kind
    e, s = make(look, gait, 5)
    e.big_ready = e.trip_ready = e.climb_ready = float("inf")
    t = _release(e, speed, direction, at)
    boxes = s.metrics(96)
    rows, flipped, touch, outcome = [], False, None, None
    out = e.update(t)
    end = t + 12.0
    while t < end and e.state == "fly":
        t += max(0.004, min(0.1, (out.wake_ms or 16) / 1000.0))
        if name == "upside_down" and not flipped and touch is None and e.y > e.ground_y() - 90:
            flipped, e.angle, e.omega = True, math.pi - 0.1, 0.8  # about to land on its head, still turning
        out = e.update(t)
        if touch is None and e.grounded:
            touch = t
        outcome = outcome or e.outcome
        foot = out.y + boxes[(out.frame, out.flip)][3]
        rows.append((t, e.state, out.frame, out.angle, e.angle, foot, e.laid))
    last = out
    while e.state != "stand" and t < end + 3:
        t += 0.016
        last = e.update(t)
    return {"e": e, "rows": rows, "touch": touch, "outcome": outcome, "final_foot": last.y + boxes[(last.frame, last.flip)][3], "state": e.state}


@pytest.mark.parametrize("gait", ["walk", "float"])
@pytest.mark.parametrize("kind", KINDS, ids=[k[0] for k in KINDS])
def test_a_thrown_figure_is_upright_and_laid_within_a_breath_of_the_floor(gait: str, kind: tuple) -> None:
    r = fly(gait, kind)
    assert r["touch"] is not None, "never reached the floor"
    laid = next((t for t, _st, _f, _a, _ang, _ft, lay in r["rows"] if lay), None)
    assert laid is not None and laid - r["touch"] <= 0.6, (laid, r["touch"])
    # once on the floor and laid, it is never drawn turned: no spin picture, no angle, whether sliding or at rest
    for t, st, frame, drawn, ang, _foot, lay in r["rows"]:
        if lay:
            assert drawn is None and not frame.startswith("spin"), (t, frame, drawn)
            assert abs(wrapped(ang)) < 0.7 * DEG, (t, ang)
    assert r["state"] == "stand" and abs(wrapped(r["e"].angle)) < 0.7 * DEG and abs(r["e"].omega) < 0.15


@pytest.mark.parametrize("gait", ["walk", "float"])
@pytest.mark.parametrize("kind", KINDS, ids=[k[0] for k in KINDS])
def test_a_laid_figure_has_its_feet_on_the_line_it_comes_to_rest_on(gait: str, kind: tuple) -> None:
    r = fly(gait, kind)
    laid_rows = [row for row in r["rows"] if row[6]]
    assert laid_rows
    for t, _st, frame, _d, _a, foot, _lay in laid_rows:
        assert abs(foot - r["final_foot"]) <= 2.0, (t, frame, foot, r["final_foot"])
    if gait == "walk":  # a walker's feet are on the floor itself
        assert abs(r["final_foot"] - AREA[3]) <= 2.0, r["final_foot"]


@pytest.mark.parametrize("gait", ["walk", "float"])
def test_the_landing_turn_is_one_move_without_a_reversal_or_a_strobe(gait: str) -> None:
    """From the touch the angle goes to upright without turning a full circle or flipping to the far upright, and
    the largest step between two 60 Hz ticks stays under 10 degrees (the 11 rad/s spin the owner called a strobe)."""
    for kind in KINDS:
        r = fly(gait, kind)
        ang = [wrapped(row[4]) for row in r["rows"] if row[0] >= r["touch"]]
        assert max(abs(a) for a in ang) <= math.pi + 0.5, kind
        assert max(abs(b - a) for a, b in zip(ang, ang[1:])) <= 10.0 * DEG * 1.7, kind  # ticks up to 28 ms in the log


def test_the_landing_adds_no_turn() -> None:
    """The kick of a floor contact (`_spin_contact`) and of a wall met while righting must not re-add spin."""
    r = fly("walk", KINDS[3])
    e = r["e"]
    after = [row for row in r["rows"] if r["touch"] is not None and row[0] > r["touch"]]
    assert after and all(abs(row[4] - wrapped(row[4])) < 7.0 for row in after)
    assert e.kick == 0.0 and eng.LAND_RIGHT_FOR <= 0.5
