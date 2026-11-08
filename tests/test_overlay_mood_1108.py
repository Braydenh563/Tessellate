"""Desk companion moods (deskmood-1108): sad when left alone a long time, welcome back when the person returns, and
confused when a let-go misses the window top it was over. Fake clock, no Win32; real Windows is unverified."""

from __future__ import annotations

import random

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import extras
from tessellate.core.overlay.engine import Engine, Monitor

SIZE = (100, 120)
FULL = (0, 0, 1920, 1080)


def make() -> Engine:
    e = Engine(SIZE, [Monitor(FULL, 96, FULL, ())], home=(900, 700), rng=random.Random(5), idle_frames=0, now=0.0)
    e.update(0.1)
    return e


def run(e: Engine, t0: float, t1: float, step: float = 0.25, pointer=None) -> list[tuple[float, str, tuple | None]]:
    """Tick from t0 to t1: (time, state, face) at each tick."""
    t, seen = t0, []
    while t < t1:
        t += step
        out = e.update(t, pointer)
        seen.append((t, e.state, out.face))
    return seen


def faces_of(seen, name: str) -> list:
    return [s for s in seen if s[2] and s[2][0] == name]


# --- 1: sad when left alone ---------------------------------------------------------------------------------


def test_left_alone_past_the_threshold_it_looks_sad_once() -> None:
    e = make()
    seen = run(e, 0.1, eng.LONELY_AFTER - 30)
    assert not faces_of(seen, "sad")
    seen = run(e, eng.LONELY_AFTER - 30, eng.LONELY_AFTER + 600, step=0.25)
    sad = faces_of(seen, "sad")
    assert sad, "never sad"
    assert min(s[0] for s in sad) >= eng.LONELY_AFTER
    assert all(s[1] in ("stand", "sit") for s in sad)
    # once: every sad tick falls inside one reaction's length
    assert max(s[0] for s in sad) - min(s[0] for s in sad) <= extras.REACTIONS["refused"].seconds + 3.0


def test_the_threshold_sits_between_sitting_and_sleeping() -> None:
    assert eng.IDLE_SIT < eng.LONELY_AFTER < eng.IDLE_SLEEP


def test_a_pointer_nearby_means_it_is_not_alone() -> None:
    e = make()
    t, seen = 0.1, []
    while t < eng.LONELY_AFTER + 200:  # the pointer rests 60 px from wherever the figure is
        t += 0.25
        out = e.update(t, (int(e.x + SIZE[0] / 2) + 60, int(e.y + SIZE[1] / 2)))
        seen.append((t, e.state, out.face))
    assert not faces_of(seen, "sad")


def test_busy_or_reduced_or_asleep_it_is_not_sad() -> None:
    for how in ("busy", "reduced"):
        e = make()
        run(e, 0.1, eng.LONELY_AFTER - 60)
        if how == "busy":
            e.quiet = True
        else:
            e.reduced = True
        assert not faces_of(run(e, eng.LONELY_AFTER - 60, eng.LONELY_AFTER + 120, step=0.25), "sad"), how
    e = make()
    e._enter("sleep", 1.0)
    e.last_active = -eng.LONELY_AFTER * 2
    assert not faces_of(run(e, 1.0, 60.0, step=0.25), "sad")


def test_a_new_idle_stretch_is_sad_again_but_not_before() -> None:
    e = make()
    first = faces_of(run(e, 0.1, eng.LONELY_AFTER + 60, step=0.25), "sad")
    assert first
    start = eng.LONELY_AFTER + 61
    e._touched(start)
    again = faces_of(run(e, start, start + eng.LONELY_AFTER + 60, step=0.25), "sad")
    assert again and min(s[0] for s in again) >= start + eng.LONELY_AFTER
