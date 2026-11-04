"""INBOX 1670, 14:14Z: "the desktop companion doesnt move smoothly, it is very framey and not seamless".
The measuring half: a seeded simulation of the engine under a fake `SetTimer` that rounds up to the
15.625 ms system tick (`tests/overlay_pace_sim.py`). It pins what the owner saw, so a fix has a number
to beat; run with `-s` to print the table."""

from __future__ import annotations

from tests import overlay_pace_sim as sim

MOVE = {"walk": ("walk",), "float": ("drift",), "fall": ("fall",), "fly": ("fly",)}


def table() -> dict[str, dict]:
    rows = {}
    for name, run in (("walk", sim.walking), ("float", sim.floating), ("fall", sim.falling), ("fly", sim.thrown)):
        e, rec = run(sim.settimer)
        iv = sim.stats(sim.intervals(rec, MOVE[name]))
        st = sim.stats(sim.steps(rec, MOVE[name]))
        rows[name] = {"interval_ms": iv, "step_px": st, "draws": sim.draw_counts(rec, MOVE[name]), "rec": rec}
    return rows


def test_settimer_judders_a_walk_and_a_float() -> None:
    """The baseline: a 33 ms ask lands on 31 or 47 ms (and the engine's own slow-motion asks reach 94 ms)."""
    rows = table()
    for name in ("walk", "float"):
        iv = rows[name]["interval_ms"]
        print(f"{name}: interval ms mean {iv['mean']:.1f} p95 {iv['p95']:.1f} max {iv['max']:.1f}; step px max {rows[name]['step_px']['max']:.1f}; {rows[name]['draws']}")
        assert iv["n"] > 50
        assert iv["p95"] > 20.0  # not 16.7: the problem the paced host removes


def test_the_other_numbers_the_owner_asked_for_are_measured() -> None:
    e, rec = sim.walking(sim.settimer)
    fps = sim.cycle_fps(rec, ("walk",), "walk")
    assert 0.0 < fps < 20.0
    e2, rec2 = sim.floating(sim.settimer)
    assert sim.bob_recompute_hz(rec2) > 0.0
    print(f"walk cycle {fps:.1f} frames/s; bob recomputed {sim.bob_recompute_hz(rec2):.1f} Hz")
    wakes = sim.rest_wakes_per_minute(sim.settimer, secs=900.0)
    print(f"rest wakes per minute {wakes:.0f}")
    assert wakes > 0
