"""Measures how smoothly the desktop companion moves (INBOX 1670, 14:14Z: "very framey and not
seamless"): the engine driven by a fake host timer, on a seeded fixed clock (never the real one).

The host asks the engine for its next wake in milliseconds and sleeps that long. On Windows a
`SetTimer` fires on the system tick, 15.625 ms, so a 33 ms ask is 31 or 47 ms; the paced host
(`pacing.py`) fires on a 60 Hz grid. A timer model is `(now, wake_ms) -> next time`. Everything here
is a number a test can assert: tick interval, window step per redraw, how often the bob and sway are
recomputed, cycle frames drawn per second, wakes at rest, draws and moves per moving second."""

from __future__ import annotations

import math
import random
import statistics
from typing import Callable

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import pacing
from tests.test_overlay_ride_1670 import make

#: Windows' timer tick: what `SetTimer` rounds a wake up to.
SYSTEM_TICK = 1.0 / 64.0
Timer = Callable[[float, int], float]


def settimer(now: float, wake_ms: int) -> float:
    """`SetTimer` as Windows runs it: the next 15.625 ms system tick at or after the ask."""
    return math.ceil((now + wake_ms / 1000.0) / SYSTEM_TICK - 1e-9) * SYSTEM_TICK


def paced_host() -> Timer:
    """The host as it is now: a next-frame ask on the 60 Hz grid, anything else on `SetTimer`."""
    pacer = pacing.Pacer()

    def timer(now: float, wake_ms: int) -> float:
        if pacer.paced(wake_ms):
            return pacer.next(now, wake_ms)
        pacer.reset()
        return settimer(now, wake_ms)

    return timer


def stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"n": 0, "mean": 0.0, "p95": 0.0, "max": 0.0}
    ordered = sorted(values)
    return {"n": len(values), "mean": statistics.fmean(values), "p95": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], "max": ordered[-1]}


def drive(e: eng.Engine, timer: Timer, t0: float, until: Callable[[eng.Engine], bool], limit: int = 4000, pointer=None) -> list[tuple]:
    """Tick the engine as the host would; one record per tick: (t, state, x, y, frame, key, wake_ms), where
    `key` is what the runner compares to decide a new bitmap (frame, flip, clip, pose, fx, alpha)."""
    t, rec = t0, []
    for _ in range(limit):
        out = e.update(t, pointer)
        rec.append((t, e.state, out.x, out.y, out.frame, (out.frame, out.flip, out.clip, out.pose, out.fx, out.alpha), out.wake_ms))
        if out.wake_ms is None or until(e):
            break
        t = timer(t, out.wake_ms)
    return rec


def walking(timer: Timer, seed: int = 3, look: str = "masculine") -> tuple[eng.Engine, list[tuple]]:
    """A walker on a long plain leg across the work area."""
    e, _s = make(look, "walk", seed)
    e.x = 100.0
    e._place_on_floor()
    e.update(0.0)
    e._go((e.x + 380.0, e.y), "stand", 0.0, plain=True)  # under DASH_OVER: a walk, not a run
    return e, drive(e, timer, 0.0, lambda en: en.state == "stand")


def floating(timer: Timer, seed: int = 3, look: str = "masculine") -> tuple[eng.Engine, list[tuple]]:
    """A floater on a long plain glide, bobbing and swaying as it goes."""
    e, _s = make(look, "float", seed)
    e.x = 100.0
    e._place_on_floor()
    e.update(0.0)
    e._go((e.x + 380.0, e.y - 120.0), "stand", 0.0, plain=True)
    return e, drive(e, timer, 0.0, lambda en: en.state == "stand")


def falling(timer: Timer, seed: int = 3, look: str = "masculine") -> tuple[eng.Engine, list[tuple]]:
    """A walker dropped from 300 px up."""
    e, _s = make(look, "walk", seed)
    e.x = 600.0
    e._place_on_floor()
    e.update(0.0)
    e.y -= 300.0
    e._start_fall(60.0)
    return e, drive(e, timer, 0.0, lambda en: en.state != "fall")


def thrown(timer: Timer, seed: int = 3, look: str = "masculine") -> tuple[eng.Engine, list[tuple]]:
    """A floater thrown across the screen, until it settles."""
    e, _s = make(look, "float", seed)
    e.x = 300.0
    e._place_on_floor()
    e.update(0.0)
    e._start_fly(900.0, -500.0)
    return e, drive(e, timer, 0.0, lambda en: en.state != "fly", limit=2500)


def intervals(rec: list[tuple], states: tuple[str, ...]) -> list[float]:
    """Milliseconds between consecutive ticks that both fall in `states`."""
    return [(b[0] - a[0]) * 1000.0 for a, b in zip(rec, rec[1:]) if a[1] in states and b[1] in states]


def steps(rec: list[tuple], states: tuple[str, ...]) -> list[float]:
    """The window's move in px between consecutive ticks in `states`."""
    return [math.hypot(b[2] - a[2], b[3] - a[3]) for a, b in zip(rec, rec[1:]) if a[1] in states and b[1] in states and a[5][1] == b[5][1]]


def figure_steps(e: eng.Engine, rec: list[tuple], states: tuple[str, ...]) -> list[float]:
    """What a person sees move: the drawn figure's left edge and feet line, not the window. The window also
    shifts when the frame changes, by the difference of the frames' margins, so that the feet stay planted
    and the figure stays put; that is not motion."""

    def place(r: tuple) -> tuple[float, float]:
        left, _top, _right, bottom = e.metrics.get((r[4], r[5][1]), (0.0, 0.0, 0.0, 0.0))
        return r[2] + left, r[3] + bottom

    out = []
    for a, b in zip(rec, rec[1:]):
        if a[1] in states and b[1] in states and a[5][1] == b[5][1]:  # not the tick a turn mirrors the frame on (a sliver, 12% wide)
            (ax, ay), (bx, by) = place(a), place(b)
            out.append(math.hypot(bx - ax, by - ay))
    return out


def draw_counts(rec: list[tuple], states: tuple[str, ...]) -> dict[str, float]:
    """What the runner would do per moving second: `presents` (a new bitmap to UpdateLayeredWindow,
    the key changed), `moves` (a bare SetWindowPos), and engine ticks."""
    present = move = ticks = 0
    span = 0.0
    prev = None
    for r in rec:
        if r[1] not in states:
            prev = None
            continue
        if prev is not None:
            ticks += 1
            span += r[0] - prev[0]
            if r[5] != prev[5]:
                present += 1
            elif (r[2], r[3]) != (prev[2], prev[3]):
                move += 1
        prev = r
    return {"seconds": span, "ticks_per_s": ticks / span, "presents_per_s": present / span, "moves_per_s": move / span}


def cycle_fps(rec: list[tuple], states: tuple[str, ...], prefix: str) -> float:
    """Distinct frames of a cycle (`walk`, `idle`) drawn per second of the time spent drawing them."""
    changes = 0
    span = 0.0
    for a, b in zip(rec, rec[1:]):
        if a[1] in states and b[1] in states and a[4].startswith(prefix) and b[4].startswith(prefix):
            span += b[0] - a[0]
            changes += 1 if a[4] != b[4] else 0
    return changes / span if span else 0.0


def bob_recompute_hz(rec: list[tuple]) -> float:
    """How often the bob and sway are put into the window position while it bobs: the tick rate over the
    drift (the position is rebuilt on every tick from the clock)."""
    iv = intervals(rec, ("drift",))
    return 1000.0 / statistics.fmean(iv) if iv else 0.0


def rest_wakes_per_minute(timer: Timer, seed: int = 4, look: str = "masculine", gait: str = "float", secs: float = 1800.0) -> float:
    """Engine ticks per minute spent at rest (not travelling), over a seeded half hour awake with the pointer about."""
    saved = eng.IDLE_SIT, eng.IDLE_SLEEP
    eng.IDLE_SIT = eng.IDLE_SLEEP = float("inf")
    try:
        e, _s = make(look, gait, seed)
        e.big_ready, e.trip_ready, e.climb_ready = 300.0, 120.0, 0.0
        rng = random.Random(seed + 7)
        t, px = 0.0, 400
        out = e.update(t, (px, 600))
        # A hang swings from its grip and is paced as a moving state (`Engine._moving_wake`, HANG_TICK_MS); the sim
        # saw none until the hang spots (INBOX 1683 w, g) made it a destination, so it is listed with the travel.
        moving = ("walk", "drift", "rise", "leap", "fly", "fall", "hop", "crouch", "held", "pressed", "warp", "hang")
        rest_ticks, rest_secs = 0, 0.0
        while t < secs:
            wait = min(max(0.016, (out.wake_ms or 1000) / 1000.0), 1.0)
            nxt = timer(t, int(round(wait * 1000)))
            step = nxt - t
            if rng.random() < step / 25.0:
                px = rng.randint(200, 1700)
            t = nxt
            out = e.update(t, (px, 600))
            if e.state not in moving:
                rest_ticks += 1
                rest_secs += step
        return rest_ticks / (rest_secs / 60.0)
    finally:
        eng.IDLE_SIT, eng.IDLE_SLEEP = saved
