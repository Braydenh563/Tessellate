"""Measures what the overlay thread reads from Windows while the figure is in the air (INBOX 1696 a, B64: "when the
desktop companion is falling, it stops and glitches at like 8 frames per second"). The engine's fall tick is 16.67 ms
on the pacing grid and a spun picture is a transpose, so the other suspect is the periodic reads that share the tick:
the window list (EnumWindows plus a class and a style query on each of the owner's ~590), the foreground window and
the downloads folder, the display layout, the typing and notification-state reads. One of them landing in a flight is
one long tick, a hitch, and a seeded sweep over the phases of those timers says how often.

Fixed clock, seeded engine, FakeWin32; the cost of a read on real Windows is not measured here, only how many land
between a throw's release and its landing."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from tests._overlay_fake import FakeWin32
from tests.test_overlay_runner import make, wait_for

STEP = 1.0 / 60.0
AIR = ("fly", "fall")


def runner_at(phase: float, look: str = "masculine"):
    """An owner-sized runner (2560x1504 at dpi 192) whose clock starts `phase` seconds into its timers' cycles."""
    fake = FakeWin32()
    fake.monitor_list = [((0, 0, 2560, 1504), 192)]
    r, fake, clock, *_ = make(fake, reduced=False, look=look, home=(1200, 1400))
    assert r.start()
    r.show()
    assert wait_for(lambda: r.host.visible)
    clock.t += phase
    e = r.engine
    e.big_ready = e.trip_ready = e.climb_ready = float("inf")  # no trip of its own: the only motion is the throw
    return r, clock


def count_reads(r) -> Counter:
    """Wrap the runner's heavy reads with counters keyed by the engine state at the moment of the read."""
    seen: Counter = Counter()

    def wrap(name: str, target: Any, attr: str) -> None:
        orig = getattr(target, attr)

        def counted(*a: Any, **kw: Any):
            if name != "_watch.poll" or r.clock() >= r._watch.next_at:  # an early return is no read
                seen[(name, r.engine.state)] += 1
            return orig(*a, **kw)

        setattr(target, attr, counted)

    wrap("_list_windows", r, "_list_windows")
    wrap("_read_typing", r, "_read_typing")
    wrap("_watch.poll", r._watch, "poll")
    wrap("_watch_taskbar", r, "_refresh_monitors")
    return seen


def flight(phase: float, speed: float = 1500.0, angle: float = -0.6, look: str = "masculine") -> tuple[Counter, float, int]:
    """One throw from a pick-up, ticked through the runner as the host does (a `tick` system event every 1/60 s), until it
    lands. Returns (reads by (name, state), seconds in the air, longest run of ticks with no read at all in the air)."""
    r, clock = runner_at(phase, look)
    e = r.engine
    w, h = e.size
    e.x, e.y = 1200.0, 300.0
    r._on_event("tick", 0, 0)
    sx, sy = int(e.x + w / 2), int(e.y + h / 2)
    r._on_event("down", sx, sy)
    x, y = float(sx), float(sy)
    for _ in range(6):
        clock.t += STEP
        x, y = x + math.cos(angle) * speed * STEP, y + math.sin(angle) * speed * STEP
        r._on_event("move", round(x), round(y))
    clock.t += STEP
    r._on_event("up", round(x), round(y))
    seen = count_reads(r)  # the release's own scan (`_scan_at_release`, the perch decision) is before this
    air = 0
    for _ in range(60 * 10):
        clock.t += STEP
        r._on_event("tick", round(x), round(y))
        if e.state in AIR:
            air += 1
        elif air:
            break
    r.stop()
    return seen, air * STEP, air


def sweep(count: int = 40, speed: float = 1500.0, look: str = "masculine") -> dict[str, float]:
    """`count` flights, the timers' phases spread over ten seconds. Returns the share of flights with a heavy read in the
    air, the reads per flight, and the mean seconds in the air."""
    hit = reads = 0
    secs = 0.0
    for i in range(count):
        seen, s, _ticks = flight(i * 10.0 / count, speed, look=look)
        mid = sum(n for (name, state), n in seen.items() if state in AIR)
        hit += 1 if mid else 0
        reads += mid
        secs += s
    return {"flights": count, "with_a_read": hit / count, "reads_per_flight": reads / count, "air_s": secs / count}


if __name__ == "__main__":
    for look in ("masculine", "feminine"):
        for speed in (1500.0, 2200.0):
            print(look, speed, sweep(40, speed, look))
