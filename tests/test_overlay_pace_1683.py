"""Every animation step rides the display-rate grid (INBOX 1683, owner: "the whole desktop companion feels really laggy
and framey"). INBOX 1670 put a MOVING figure on a 60 Hz grid; what was left on `SetTimer` (15.625 ms system tick) was
the tail and lower wisps settling after a stop (asked 50 ms), a hang's swing (50), an act's pose steps (looked ahead
every 50 ms, floored at 30): drawn 31, 47, 62 ms apart. Measured on the sim's timers, fixed clock, the 2 s after a walk
stops: ticks mean 67 ms (p95 109); now the tail settle asks 16 ms and every ask of 100 ms or less lands on a grid line.
Real Windows is not measured here: the host's high-resolution timer is covered by the fake layer in
`test_overlay_smooth_1670.py`."""

from __future__ import annotations

import statistics

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import engine as eng  # noqa: E402
from tessellate.core.overlay import pacing  # noqa: E402
from tests import overlay_pace_sim as sim  # noqa: E402


def test_asks_up_to_a_tenth_of_a_second_land_on_the_grid_line_at_or_after_their_time() -> None:
    p = pacing.Pacer()
    t = 5.0
    anchor = p.next(t, 16) - pacing.FRAME_S
    for ms in (16, 33, 50, 84, 100):
        line = p.next(anchor, ms)
        n = (line - anchor) / pacing.FRAME_S
        assert abs(n - round(n)) < 1e-9, ms  # on the grid
        assert line >= anchor + ms / 1000.0 - 0.0011, ms  # never early
        assert line < anchor + ms / 1000.0 + pacing.FRAME_S, ms  # never a frame late


def test_a_walk_then_a_stop_ticks_every_frame_while_the_tail_settles() -> None:
    gaps: list[float] = []
    for gait in ("float", "walk"):
        for seed in range(1, 6):
            e, _s = sim.make("masculine", gait, seed)
            e.plain_legs = True
            timer = sim.paced_host()
            t = 0.0
            out = e.update(t)
            e.command("wander", t)
            moved = False
            for _ in range(6000):
                t = timer(t, out.wake_ms or 16)
                out = e.update(t)
                moved = moved or e.state in ("walk", "drift")
                if moved and e.state not in ("walk", "drift", "crouch", "land", "hop", "fall"):
                    break
            # the tail swings on: while it does, the ask is a frame
            while out.wake_ms is not None and not e.tail.settled():
                assert out.wake_ms <= pacing.NEXT_FRAME_MS, (out.wake_ms, e.state)
                nxt = timer(t, out.wake_ms)
                gaps.append((nxt - t) * 1000)
                t = nxt
                out = e.update(t)
                if len(gaps) > 4000:
                    break
    assert len(gaps) > 100
    assert statistics.fmean(gaps) < 20.0 and max(gaps) < 34.0  # before: 62.5 ms every tick
    assert statistics.pstdev(gaps) < 4.0


def test_the_tail_pose_and_hang_asks_are_display_frames_not_fifty_milliseconds() -> None:
    assert eng.TAIL_TICK_MS <= pacing.NEXT_FRAME_MS
    assert eng.HANG_TICK_MS * 60 % 1000 == 0 or abs(eng.HANG_TICK_MS - 2000 / 60) < 1.0  # two lines of the grid
    assert eng.POSE_LOOK_STEP <= 1.0 / 60.0 + 1e-9


def test_an_act_wakes_at_the_frame_its_pose_steps_not_thirty_milliseconds_after_a_floor() -> None:
    e, _s = sim.make("masculine", "float", 2)
    e.plain_legs = True
    t = 1.0
    e.update(t)
    e._start_act("stretch", t)
    asks = []
    for _ in range(300):
        t += 0.0167
        out = e.update(t)
        if e.state != "act":
            break
        asks.append(out.wake_ms)
    assert asks and min(a for a in asks if a) >= eng.TICK_WALK_MS
    assert min(a for a in asks if a) < eng.MIN_WAKE_MS  # an act is no longer floored at 30


def test_a_rest_is_still_asked_slowly_so_the_calm_budget_holds() -> None:
    wakes = sim.rest_wakes_per_minute(sim.paced_host(), secs=900.0)
    print(f"rest wakes a minute after: {wakes:.0f}")
    assert wakes <= 480, wakes  # same bar as test_overlay_smooth_1670 (measured 395 before this change)
