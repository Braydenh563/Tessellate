"""The float that travels (INBOX 1658, the owner: "it just floats there ... it slow falls
and twitches a little but it doesnt really move"): legs across the work area every few
seconds, a bob and a sway every frame, the idle cycle playing while it rests. Measured on
the fake clock by following the engine's own wake requests, as the runner does."""

from __future__ import annotations

import random

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay.engine import Engine, Monitor

SIZE = (100, 120)
ONE = [Monitor((0, 0, 1920, 1040), 96)]
WIDTH = 1920 - SIZE[0]


def make(seed: int, **kw) -> Engine:
    e = Engine(SIZE, ONE, rng=random.Random(seed), home=(800, 1040 - 120), gait="float", **kw)
    e.big_ready = float("inf")  # no hang or peek: this is about travelling
    e.climb_ready = float("inf")
    return e


def follow(e: Engine, seconds: float):
    """(share of ticks whose frame or place changed, x extent, ticks) over `seconds`."""
    t, out = 0.0, e.update(0.0)
    last, changed, ticks, xs = (out.frame, out.x, out.y), 0, 0, [out.x]
    while out.wake_ms is not None and t < seconds:
        t += out.wake_ms / 1000.0
        out = e.update(t)
        now = (out.frame, out.x, out.y)
        ticks += 1
        changed += now != last
        last = now
        xs.append(out.x)
    return changed / max(1, ticks), max(xs) - min(xs), ticks


def test_a_settled_floater_does_not_move_between_its_small_things() -> None:
    # Intent reversed (INBOX 1670: "cant sit still", "why does it bob up and down so much, it is
    # floating"): it used to be tested as never still for more than a second. A settled floater now
    # stays on one spot; what changes is the picture (a blink, a look, an act), never the place.
    for seed in range(1, 9):
        e = make(seed)
        e._enter("stand", 0.0)
        e.state_until = 1e9
        e.next_ambient = 1e9
        e.trip_ready = e.climb_ready = float("inf")
        t, out, places = 0.0, e.update(0.0), set()
        while out.wake_ms is not None and t < 120.0:
            t += out.wake_ms / 1000.0
            out = e.update(t)
            places.add((out.x, out.y))
        assert len(places) == 1, (seed, places)


def test_the_floater_stays_by_its_home_and_does_not_cross_the_screen_in_a_minute() -> None:
    # Intent moved (INBOX 1670, 11:02Z "a buddy, not a nuisance"): it was 40 percent of the width
    # in 60 s (1658, "it just floats there"). Now it lives by its home spot; a trip is rare.
    for seed in range(1, 9):
        _share, extent, _ticks = follow(make(seed), 60.0)
        assert extent <= 2 * eng.STROLL + 2 * eng.FLOAT_SWAY + 4, (seed, extent)


def test_a_resting_floater_does_not_bob_and_plays_the_idle_cycle_without_pause() -> None:
    # Intent moved (INBOX 1670; 15:40Z): no bob or sway at rest; the tail cycle plays all the time, in place
    # (it was a burst now and then, then a plain stand).
    e = make(3)
    e._enter("stand", 0.0)
    e.state_until = 1e9
    e.next_ambient = 1e9
    seen, frames, t = set(), set(), 0.0
    for _ in range(120):
        t += 0.066
        o = e.update(t)
        seen.add((o.x, o.y))
        frames.add(o.frame)
    assert len(seen) == 1
    assert {f for f in frames if f.startswith("idle")} >= {f"idle{i}" for i in range(0, 12, 2)}
    assert o.frame.startswith("idle")  # still in the cycle


def test_a_reduced_floater_does_not_bob_and_neither_does_a_typing_one() -> None:
    # Was "a typing one bobs in place" (INBOX 1670, "it is also not animated"); the bob is gone for
    # everyone now ("it is floating"), so typing keeps the place and only the picture can change.
    r = Engine(SIZE, ONE, rng=random.Random(3), home=(800, 920), gait="float", reduced=True)
    assert len({(o.x, o.y) for o in (r.update(0.1 * i) for i in range(1, 40))}) == 1
    q = make(3)
    q.quiet = True
    q._enter("stand", 0.0)
    q.state_until = 1e9
    q.next_ambient = 1e9
    assert len({(o.x, o.y) for o in (q.update(0.1 * i) for i in range(1, 40))}) == 1


def test_the_bob_never_leaves_the_work_area_or_enters_a_window_it_rests_on() -> None:
    e = make(2)
    t = 0.0
    for _ in range(3000):
        t += 0.033
        o = e.update(t)
        assert 0 <= o.x <= WIDTH and 0 <= o.y <= 1040 - SIZE[1]


def test_a_wandering_floater_keeps_to_a_band_about_its_own_height_above_its_rest_line() -> None:
    """INBOX 1663: "it floats wayyy to high". Wandering legs aim within FLOAT_BAND figure
    heights of the rest line, at every dpi, on one monitor and on mixed ones."""
    from tessellate.core.overlay.engine import FLOAT_BAND

    layouts = [
        ([Monitor((0, 0, 1920, 1040), 144)], (233, 266)),
        ([Monitor((0, 0, 1920, 1040), 120)], (194, 222)),
        ([Monitor((0, 0, 1920, 1040), 144), Monitor((1920, 0, 3840, 1040), 96)], (233, 266)),
    ]
    for monitors, size in layouts:
        for seed in range(1, 4):
            e = Engine(size, monitors, rng=random.Random(seed), home=(800, 700), gait="float")
            e.big_ready = float("inf")
            e.climb_ready = float("inf")
            t, out, worst = 0.0, e.update(0.0), 0.0
            while out.wake_ms is not None and t < 300.0:
                t += out.wake_ms / 1000.0
                out = e.update(t)
                if e.state in ("stand", "drift"):
                    rest = e.ground_y(e.current_monitor())
                    worst = max(worst, rest - e.y)
            slack = 2.0  # rounding only: the clamp holds the band
            assert worst <= FLOAT_BAND * size[1] + slack, (monitors[0].dpi, seed, worst)
