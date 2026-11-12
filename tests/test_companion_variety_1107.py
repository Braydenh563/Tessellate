"""Research V3: an act is not played the same way twice. Seeded, fixed clock, no Win32."""

from __future__ import annotations

import random

from tessellate.core.overlay import behaviour as bh
from tessellate.core.overlay.engine import Engine, Monitor

ONE = [Monitor((0, 0, 1920, 1040), 96)]


def make(seed: int = 7) -> Engine:
    return Engine((100, 120), ONE, rng=random.Random(seed), idle_frames=0, home=(800, 920))


def play(seed: int, name: str = "stretch", t0: float = 10.0):
    e = make(seed)
    e.update(0.1)
    e._start_act(name, t0)
    return e


def test_a_variation_stays_inside_its_bounds_and_is_seeded() -> None:
    a = [bh.vary(random.Random(3)) for _ in range(2)]
    assert a[0] == a[1]
    rng = random.Random(1)
    for _ in range(200):
        v = bh.vary(rng)
        assert 0.85 <= v.amp <= 1.15 and 0.85 <= v.dur <= 1.15 and v.ease in bh.EASES


def test_two_plays_of_one_act_differ_in_length_and_amplitude() -> None:
    e = make()
    e.update(0.1)
    seen = set()
    for i in range(6):
        e._start_act("stretch", 10.0 + 20 * i)
        seen.add((round(e.act_len, 3), round(e.act_var.amp, 3)))
    assert len(seen) == 6
    lo, hi = bh.ACTIVITIES["stretch"].seconds
    assert all(lo * 0.85 - 1e-9 <= n <= hi * 1.15 + 1e-9 for n, _ in seen)


def test_same_seed_plays_the_same_and_the_pose_is_scaled() -> None:
    a, b = play(5), play(5)
    assert a.act_len == b.act_len and a.act_var == b.act_var
    v = a.act_var
    p = bh.scaled(bh.Pose(1.1, 0.9, 0.04), v.amp)
    assert abs((p.sx - 1) - 0.1 * v.amp) < 1e-9 and abs(p.lean - 0.04 * v.amp) < 1e-9
    assert bh.scaled(bh.NEUTRAL, 1.15) == bh.NEUTRAL


def test_every_easing_hits_both_ends() -> None:
    for f in bh.EASES:
        assert f(0.0) == 0.0 and abs(f(1.0) - 1.0) < 1e-9 and 0.0 < f(0.5) < 1.0
    keys = bh.ACTIVITIES["stretch"].keys
    assert bh.sample(keys, 0.0, bh.EASES[1]) == bh.sample(keys, 0.0)


def test_the_drawn_pose_follows_the_variation() -> None:
    def drawn(amp: float):
        e = play(2)
        e.act_var = bh.Variation(amp, 1.0, bh.smooth)
        e.act_len = 2.5
        t, out = 10.0, None
        while t < 10.0 + 2.5 * 0.6:
            t += 0.033
            out = e.update(t)
        return out.pose

    big, small = drawn(1.15), drawn(0.85)
    assert big is not None and small is not None
    assert abs(big[1] - 1) > abs(small[1] - 1)
