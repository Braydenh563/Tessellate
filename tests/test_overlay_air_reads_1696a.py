"""INBOX 1696 a (B64): the periodic reads wait for the landing. Measured on the seeded sweep in
`tests/overlay_airborne_reads.py` (a throw at 1500 px/s, 3.23 s in the air, the timers' phases spread over ten seconds,
FakeWin32 at the owner's 2560x1504 and dpi 192): before, every flight caught one window list, one foreground, battery and
downloads poll and one typing read (3 reads in 40 of 40 flights, each a tick of its own between two frames); now 0 in the
air, and the three are read on three different ticks after the landing. Fixed clock."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from tests.overlay_airborne_reads import AIR, STEP, flight, runner_at, sweep  # noqa: E402


def test_no_periodic_read_lands_in_a_flight() -> None:
    got = sweep(20)
    assert got["air_s"] > 2.0  # long enough that every flight crossed a 2 s timer
    assert got["reads_per_flight"] == 0.0 and got["with_a_read"] == 0.0


@pytest.mark.parametrize("look", ["masculine", "feminine"])
def test_the_reads_come_back_on_the_ground_one_at_a_time(look: str) -> None:
    r, clock = runner_at(0.0, look)
    e = r.engine
    calls: list[tuple[str, float]] = []
    for name, target, attr in (("windows", r, "_list_windows"), ("typing", r, "_read_typing"), ("poll", r._watch, "poll")):
        orig = getattr(target, attr)

        def counted(*a, _o=orig, _n=name, **kw):
            if _n != "poll" or r.clock() >= r._watch.next_at:
                calls.append((_n, r.clock()))
            return _o(*a, **kw)

        setattr(target, attr, counted)
    e.x, e.y = 1200.0, 300.0
    r._on_event("tick", 0, 0)
    e._start_fly(900.0, -300.0)
    started = clock.t
    landed = None
    for _ in range(60 * 12):
        clock.t += STEP
        r._on_event("tick", 0, 0)
        if e.state not in AIR:
            landed = clock.t
            break
    assert landed is not None
    during = [c for c in calls if started < c[1] < landed]  # the tick before the throw read them once
    assert not during, during
    for _ in range(90):
        clock.t += STEP
        r._on_event("tick", 0, 0)
    after = {n: t for n, t in calls if t > landed}
    assert set(after) == {"windows", "typing", "poll"}, calls  # none was lost
    assert len({round(t, 3) for t in after.values()}) == 3  # and no two on the same tick
    r.stop()


def test_a_flight_that_never_ends_still_reads_after_the_bound() -> None:
    r, clock = runner_at(0.0)
    e = r.engine
    e.state = "fly"
    assert r._aloft(e, 10.0)
    assert not r._aloft(e, 10.0 + 8.01)
    e.state = "stand"
    assert not r._aloft(e, 30.0) and r._air_since is None
    r.stop()


def test_a_flight_catches_no_read_wherever_the_timers_stand() -> None:
    seen, secs, _ticks = flight(3.0)
    assert secs > 2.0 and not seen


def test_a_slow_tick_is_logged_with_the_reads_in_it_and_only_every_few_seconds(caplog) -> None:
    caplog.set_level("INFO", logger="tessellate.core.overlay.runner")
    r, clock = runner_at(0.0)
    e = r.engine
    e.x, e.y = 1200.0, 300.0
    r._on_event("tick", 0, 0)
    caplog.clear()
    ticks = iter(range(10_000))
    r._perf = lambda: next(ticks) * 0.011  # every call of the clock is 11 ms on: a tick with three reads spans over 30 ms
    clock.t += 3.0  # the busy, poll and window timers are all due
    r._on_event("tick", 0, 0)
    lines = [rec.getMessage() for rec in caplog.records if "a slow tick" in rec.getMessage()]
    assert len(lines) == 1 and "typing 11 ms" in lines[0] and "windows 11 ms" in lines[0], lines
    clock.t += 3.0
    r._on_event("tick", 0, 0)
    assert len([rec for rec in caplog.records if "a slow tick" in rec.getMessage()]) == 1  # rate limited to one in 5 s
    r.stop()
