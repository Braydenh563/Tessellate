"""Seeded throw sim for INBOX 1683 (k): the desk companion's landing, read tick by tick with a fixed clock.
`landings(n)` throws the figure `n` times (seeded speed, direction, grab, start) and reports, per throw, how it came
to rest, the longest tilt it held, and any drawn-angle jump over 30 degrees between two ticks."""

from __future__ import annotations

import math
import random

from tests.overlay_tumble_1670 import STEP, _release, make

TAU = 2 * math.pi


def err_of(angle: float) -> float:
    return angle - round(angle / TAU) * TAU


def one(seed: int, gait: str = "walk", look: str = "masculine") -> dict:
    rng = random.Random(seed)
    e, _s = make(look, gait, seed)
    e.big_ready = e.trip_ready = e.climb_ready = float("inf")
    speed, ang = rng.uniform(500.0, 3000.0), rng.uniform(-math.pi, math.pi)
    at = (rng.uniform(300.0, 1500.0), rng.uniform(250.0, 700.0))
    e.grab = (e.size[0] * rng.uniform(0.2, 0.8), e.size[1] * rng.uniform(0.2, 0.8))
    t = _release(e, speed, ang, at, rng.uniform(-0.15, 0.15))
    prev, tilt_run, tilt_max, snaps, outcomes, calm = None, 0.0, 0.0, 0, [], 0.0
    for _ in range(60 * 24):
        t += STEP
        out = e.update(t)
        drawn = out.angle if out.angle is not None else (e.angle if e.state == "fly" and not e.laid else 0.0)
        step = abs(err_of(drawn - prev)) if prev is not None else 0.0
        if step > math.radians(30):
            snaps += 1
        lying = bool(getattr(e, "lie_goal", None) is not None and e.grounded)
        held = not lying and math.radians(15) < abs(err_of(drawn)) < math.radians(165) and step < math.radians(0.5)
        tilt_run = tilt_run + STEP if held else 0.0
        tilt_max = max(tilt_max, tilt_run)
        prev = drawn
        o = getattr(e, "outcome", None)
        if o and (not outcomes or outcomes[-1] != o):
            outcomes.append(o)
        calm = calm + STEP if e.state in ("stand", "walk", "sit", "hang", "drift") else 0.0
        if calm > 0.5:
            break
    return {"outcomes": outcomes or ["feet"], "tilt": tilt_max, "snaps": snaps, "state": e.state, "t": t}


def landings(n: int = 200, gait: str = "walk", look: str = "masculine", pool=None) -> dict:
    rows = list(pool.starmap(one, [(s, gait, look) for s in range(n)])) if pool else [one(s, gait, look) for s in range(n)]
    kinds: dict[str, int] = {}
    for r in rows:
        k = "+".join(r["outcomes"])
        kinds[k] = kinds.get(k, 0) + 1
    return {"kinds": kinds, "tilt_max": max(r["tilt"] for r in rows), "snaps": sum(r["snaps"] for r in rows), "rows": rows}


if __name__ == "__main__":
    import multiprocessing

    pool = multiprocessing.Pool(4)
    for gait in ("walk", "float"):
        r = landings(200, gait, pool=pool)
        print(gait, r["kinds"], "longest held tilt %.2fs" % r["tilt_max"], "snaps", r["snaps"])
