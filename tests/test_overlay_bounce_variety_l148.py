"""L148: a throw's bounce is its own: the wall and ceiling give back BOUNCE_DAMP scaled by a per-throw spread, so two
throws at the same wall do not rebound the same. It has its own random stream (no other draw moves) and a fake clock."""

from __future__ import annotations

from tessellate.core.overlay import engine_consts as ec
from tessellate.core.overlay import engine_flight as ef
from tests.test_overlay_moves import make


def _damps(seed: int, n: int = 40) -> list[float]:
    e = make(seed=seed)
    e.update(0.1)
    out = []
    for i in range(n):
        e._start_fly(300.0, -200.0)
        out.append(e.bounce_k)
    return out


def test_each_throw_draws_its_own_restitution_inside_the_spread() -> None:
    ks = _damps(3)
    assert len(set(round(k, 3) for k in ks)) > 10
    lo, hi = ec.BOUNCE_DAMP * (1 - ef.BOUNCE_SPREAD), ec.BOUNCE_DAMP
    assert all(lo - 1e-9 <= k <= hi + 1e-9 for k in ks)


def test_the_restitution_is_repeatable_per_seed_and_moves_no_other_draw() -> None:
    assert _damps(3) == _damps(3)
    a, b = make(seed=3), make(seed=3)
    b._start_fly(300.0, -200.0)
    assert a.rng.getstate() == b.rng.getstate()


def test_the_hardest_give_still_stands_a_wall_throw_within_the_feet_bound(monkeypatch) -> None:
    """The spread's top is BOUNCE_DAMP itself (a spread of 0 draws it): a hard wall throw, the slowest to stand on its
    feet (a stumble), stands within STAND_BY_FEET there (1.568 s; +25% above it stood at 1.632)."""
    from tests import test_overlay_land_1683 as land

    monkeypatch.setattr(ef, "BOUNCE_SPREAD", 0.0)
    r = land.fly("walk", next(k for k in land.KINDS if k[0] == "wall"))
    assert r["e"].bounce_k == ec.BOUNCE_DAMP
    assert r["state"] == "stand" and r["stand_at"] - r["touch"] <= land.STAND_BY_FEET, r["stand_at"] - r["touch"]
