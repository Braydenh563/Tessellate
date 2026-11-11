"""The frame interval, logged once a minute (INBOX 1683 a and 1670 r: "real Windows frame interval logged", "display-paced
timer, 16.7 ms plus or minus 3"). The simulation proves the grid; only the owner's machine can say what the timer really
did, so the runner writes one line a minute with the median, the 95th percentile and the worst interval of the paced
wakes. Fixed clock: every time here is passed in, nothing reads the real one."""

from __future__ import annotations

import logging

import pytest

from tessellate.core.overlay import pacing


def feed(log: pacing.IntervalLog, intervals: list[float], start: float = 100.0) -> list[str]:
    lines = []
    t = start
    log.note(t)
    for dt in intervals:
        log.asked(16 if dt <= 0.12 else 1500)  # a frame ask comes before a frame gap; a rest's ask is long
        t += dt
        line = log.note(t)
        if line:
            lines.append(line)
    return lines


def test_a_minute_of_steady_frames_reads_as_one_line_with_the_percentiles() -> None:
    log = pacing.IntervalLog()
    steady = [pacing.FRAME_S] * 3700  # a little over a minute at 60 a second
    lines = feed(log, steady)
    assert len(lines) == 1
    assert "p50 16.7 ms" in lines[0] and "p95 16.7 ms" in lines[0] and "max 16.7 ms" in lines[0], lines[0]


def test_the_percentiles_are_of_the_intervals_not_of_the_times() -> None:
    log = pacing.IntervalLog()
    mix = ([0.0167] * 9 + [0.031]) * 400  # nine in ten on the grid, one a line late
    lines = feed(log, mix)
    got = " ".join(lines)
    assert "p50 16.7 ms" in got and "p95 31.0 ms" in got and "max 31.0 ms" in got, got


def test_an_animations_own_step_is_not_a_frame_gap() -> None:
    # The engine's 33 ms ask (a tail settling, a pose easing) lands on the second grid line: it is not the timer being slow.
    log = pacing.IntervalLog()
    lines = []
    t = 0.0
    log.note(t)
    for _ in range(3000):
        log.asked(33)
        t += 0.0333
        lines += [x for x in [log.note(t)] if x]
    assert lines == [], lines


def test_a_late_frame_wake_is_counted_against_the_timer() -> None:
    log = pacing.IntervalLog()
    lines = []
    t = 0.0
    log.note(t)
    for k in range(4000):
        log.asked(16)  # always a next-frame ask; every hundredth wake comes 200 ms late
        t += 0.2 if k % 100 == 99 else pacing.FRAME_S
        lines += [x for x in [log.note(t)] if x]
    assert lines and "max 200.0 ms" in " ".join(lines), lines


def test_a_rest_is_not_an_interval() -> None:
    # A wake longer than PACED_AT_MS is the engine's slow ask: it is a rest, not a frame, so it must not read as a miss.
    log = pacing.IntervalLog()
    lines = feed(log, [0.0167, 0.0167, 1.5, 0.0167, 0.0167] * 400)
    assert lines and all("max 16.7 ms" in line for line in lines), lines


def test_nothing_is_said_before_a_minute_or_with_no_frames() -> None:
    log = pacing.IntervalLog()
    assert feed(log, [0.0167] * 100) == []
    assert pacing.IntervalLog().note(5.0) is None
    assert feed(pacing.IntervalLog(), [2.0] * 100) == [], "only rests: no paced interval to report"


def test_each_line_starts_a_new_window() -> None:
    log = pacing.IntervalLog()
    first = feed(log, [0.0167] * 3700)
    second = feed(log, [0.025] * 2500, start=500.0)
    assert len(first) == 1 and len(second) == 1
    assert "p50 25.0 ms" in second[0], second


def test_a_runner_tick_stream_logs_the_interval_line(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """The real `_on_event` path: ticks the engine answers with a next-frame ask make the gaps the line is built from."""
    from tessellate.core.overlay import runner
    from tests.test_overlay_runner import make as make_runner

    caplog.set_level(logging.INFO, logger=runner.logger.name)
    monkeypatch.setattr(pacing, "LOG_EVERY_S", 3.0)  # three seconds of ticks, not a minute of them
    r, _fake, clock, *_ = make_runner()
    assert r.start()
    r.show()
    asks = []
    for _ in range(240):  # four seconds at 60 a second, the fixed clock moved by hand
        clock.t += pacing.FRAME_S
        asks.append(r._on_event("tick", 0, 0))
    r.stop()
    lines = [rec.getMessage() for rec in caplog.records if "frame interval" in rec.getMessage()]
    assert any(a is not None and pacing.PACED_FROM_MS <= a <= pacing.NEXT_FRAME_MS for a in asks), "the engine asked for frames"
    assert lines, "the window's ticks wrote its line"
    assert "p50 16.7 ms" in lines[0], lines[0]
