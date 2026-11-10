"""Research A7: the idle is not a strict 4 s loop: each cycle runs 8% faster or slower, drawn from its own seeded
stream, so the breath and the sway never line up twice. Fixed clock, no Win32."""

from __future__ import annotations

import random

from tessellate.core.overlay import engine as eng

ONE = [eng.Monitor((0, 0, 1920, 1040), 96)]


def make(seed: int = 7) -> eng.Engine:
    e = eng.Engine((100, 120), ONE, rng=random.Random(seed), idle_frames=24, home=(800, 920))
    e.update(0.1)
    return e


def cycle_starts(e: eng.Engine, cycles: int) -> list[float]:
    """The times the index returns to frame 0, read at 5 ms steps."""
    out, t, last = [], e.idle_start, -1
    while len(out) < cycles and t < e.idle_start + 200.0:
        i = e._idle_index(t)
        if i == 0 and last != 0:
            out.append(t)
        last = i
        t += 0.005
    return out


def test_cycles_differ_in_length_by_at_most_eight_per_cent_and_are_seeded() -> None:
    e = make()
    starts = cycle_starts(e, 12)
    lengths = [b - a for a, b in zip(starts, starts[1:])]
    base = eng.IDLE_FRAMES / eng.IDLE_FPS
    assert len({round(n, 2) for n in lengths}) > 4
    assert all(base / 1.081 <= n <= base / 0.979 for n in lengths), lengths
    assert cycle_starts(make(), 12) == starts


def test_it_still_starts_from_the_first_picture_and_never_goes_backwards_within_a_cycle() -> None:
    e = make()
    assert e._idle_index(e.idle_start) == 0
    seen = [e._idle_index(e.idle_start + i * 0.01) for i in range(0, 520)]
    assert all(b >= a for a, b in zip(seen, seen[1:]) if a != 23 or b != 0) and max(seen) == 23


def test_the_wake_time_is_when_the_index_next_changes() -> None:
    e = make()
    t = e.idle_start + 5.37
    i = e._idle_index(t)
    due = e._idle_next(t)
    assert e._idle_index(due - 0.002) == i and e._idle_index(due + 0.002) != i
