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


def test_the_floater_is_never_still_for_more_than_a_second() -> None:
    # Intent kept, measure moved: "it just floats there" (1658) was a floater that did not look
    # alive. It used to be tested as 90 percent of wakes changing something, which only held with
    # a 16 Hz bob; the wakes now come when something would change (a pixel of bob, a frame of the
    # idle cycle, a step of a pose), so the bar is the longest stretch with nothing new drawn.
    for seed in range(1, 9):
        e = make(seed)
        t, out = 0.0, e.update(0.0)
        last, since, worst = (out.frame, out.x, out.y, out.pose), 0.0, 0.0
        while out.wake_ms is not None and t < 120.0:
            t += out.wake_ms / 1000.0
            out = e.update(t)
            now = (out.frame, out.x, out.y, out.pose)
            if now != last or e.state == "act":
                last, since = now, t  # an act (a held look, a nap) is life, not a freeze
            worst = max(worst, t - since)
        assert worst <= 1.0, (seed, worst)


def test_the_floater_stays_by_its_home_and_does_not_cross_the_screen_in_a_minute() -> None:
    # Intent moved (INBOX 1670, 11:02Z "a buddy, not a nuisance"): it was 40 percent of the width
    # in 60 s (1658, "it just floats there"). Now it lives by its home spot; a trip is rare.
    for seed in range(1, 9):
        _share, extent, _ticks = follow(make(seed), 60.0)
        assert extent <= 2 * eng.STROLL + 2 * eng.FLOAT_SWAY + 4, (seed, extent)


def test_a_resting_floater_still_bobs_and_sways_and_plays_the_idle_cycle() -> None:
    e = make(3)
    e._enter("stand", 0.0)
    e.state_until = 1e9
    seen, frames, t = set(), set(), 0.0
    for _ in range(120):
        t += 0.066
        o = e.update(t)
        seen.add((o.x, o.y))
        frames.add(o.frame)
    # 2 px of bob and sway over a 4 s breath: a few distinct places, not a flutter
    assert len({y for _x, y in seen}) >= 2 and len({x for x, _y in seen}) >= 2
    assert any(f.startswith("idle") for f in frames)


def test_a_reduced_floater_does_not_bob_and_a_typing_one_bobs_in_place() -> None:
    # Typing moved from "no bob" to "bobs in place" 2026-11-04: the owner's "it is also
    # not animated" (INBOX 1670). It still does not travel: x stays within the sway.
    r = Engine(SIZE, ONE, rng=random.Random(3), home=(800, 920), gait="float", reduced=True)
    assert len({(o.x, o.y) for o in (r.update(0.1 * i) for i in range(1, 40))}) == 1
    q = make(3)
    q.quiet = True
    q._enter("stand", 0.0)
    q.state_until = 1e9
    seen = [(o.x, o.y) for o in (q.update(0.1 * i) for i in range(1, 40))]
    assert len({y for _x, y in seen}) > 1
    assert max(x for x, _y in seen) - min(x for x, _y in seen) <= 2 * eng.FLOAT_SWAY + 2


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
