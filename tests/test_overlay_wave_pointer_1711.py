"""A wave at the pointer after a pause (INBOX 1711 b, owner: wave "when the pointer is idle"): the desk figure standing
about waves once when the pointer rests near it for WAVE_IDLE s, not while it moves, not far off, not again for the same rest."""

from __future__ import annotations

import random

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay.engine import Engine, Monitor

ONE = [Monitor((0, 0, 1920, 1040), 96)]


def make(seed: int = 4) -> Engine:
    e = Engine((100, 120), ONE, rng=random.Random(seed), home=(800, 920), roam=False)
    e.update(1.0)
    return e


def waves(e: Engine, pointer, until: float, t: float = 2.0) -> list[float]:
    """The times the rest trigger fired (the weighted pick may also choose the act, so the trigger is read, not the act)."""
    out, seen = [], e.wave_rest
    while t < until:
        e.update(t, pointer(t) if callable(pointer) else pointer)
        if e.wave_rest != seen:
            seen = e.wave_rest
            out.append(t)
        t += 0.05
    return out


def test_a_pointer_resting_near_draws_one_wave_after_the_pause() -> None:
    e = make()
    got = waves(e, (950, 980), 8.0 + eng.WAVE_IDLE + 6)
    assert len(got) == 1 and got[0] >= 2.0 + eng.WAVE_IDLE - 0.1


def test_the_same_rest_does_not_wave_twice() -> None:
    e = make()
    assert len(waves(e, (950, 980), 120.0)) == 1


def test_a_far_pointer_or_a_moving_one_draws_none() -> None:
    assert waves(make(), (1900, 20), 60.0) == []
    assert waves(make(), lambda t: (900 + 10 * int(t * 2) % 60, 980), 40.0) == []


def test_the_app_side_has_the_same_numbers_and_waits_for_a_standing_idle_companion() -> None:
    """The in-app trigger (avatars.js `nmb.waveRest`) mirrors the desk's constants; read as text, not driven."""
    from pathlib import Path

    js = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
    body = js.split("nmb.waveRest = (x, y) => {")[1].split("\n};\n")[0]
    assert f"NMB_WAVE_IDLE = {int(eng.WAVE_IDLE * 1000)}, NMB_WAVE_NEAR = {int(eng.WAVE_NEAR)}, NMB_WAVE_GAP = {int(eng.WAVE_GAP * 1000)}" in js
    assert 'nmb.pose !== "stand"' in body and "nmb.act" in body and 'nameMarkBuddyAct("wavepointer"' in body
