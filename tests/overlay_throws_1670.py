"""A seeded spread of throws for the desktop companion (INBOX 1670, 15:45Z: "nearly every time I throw it no
matter how hard, it goes to the top to hang"). The engine and its fakes on a fixed clock: the figure is
picked up at a spot across the screen, the pointer is moved at a uniform angle and a speed from a gentle
fling up to `THROW_MAX`, and let go. It reports where the throw ended: hanging from the top or a title bar,
or settled on the floor."""

from __future__ import annotations

import math
import random
from collections import Counter

from tessellate.core.overlay import engine as eng
from tests.test_overlay_ride_1670 import AREA, WIN, make

#: Samples of the pointer's last tenth of a second, 60 Hz.
STEP = 1.0 / 60.0


def throw_once(
    gait: str, look: str, seed: int, angle: float, speed: float, at: tuple[float, float], windows: bool = True,
) -> str:
    """Pick the figure up with its middle at `at`, move the pointer at `speed` (px/s, logical) toward `angle`
    for a tenth of a second and let go. Returns "hang" (taking hold of the top or a title bar), or "floor"."""
    e, _s = make(look, gait, seed)
    e.big_ready = e.trip_ready = e.climb_ready = float("inf")
    if windows:
        e.set_windows([WIN], 0.0)
    w, h = e.size
    # the spot the figure is let go at: keep the whole body in the work area
    px = min(max(at[0], AREA[0] + w / 2), AREA[2] - w / 2)
    py = min(max(at[1], AREA[1] + h / 2), AREA[3] - h / 2)
    ux, uy = math.cos(angle), math.sin(angle)
    n = 6
    t = 1.0
    e.x, e.y = px - w / 2 - ux * speed * STEP * n, py - h / 2 - uy * speed * STEP * n
    e.x = min(max(e.x, AREA[0]), AREA[2] - w)
    e.y = min(max(e.y, AREA[1]), AREA[3] - h)
    e.update(t)
    sx, sy = int(e.x + w / 2), int(e.y + h / 2)
    e.update(t, (sx, sy), ("down", sx, sy))
    for i in range(1, n + 1):
        t += STEP
        e.update(t, event=("move", round(sx + ux * speed * STEP * i), round(sy + uy * speed * STEP * i)))
    t += STEP
    e.update(t, event=("up", round(sx + ux * speed * STEP * (n + 1)), round(sy + uy * speed * STEP * (n + 1))))
    hung = False
    end = t + 25.0
    while t < end:
        t += 0.016
        e.update(t)
        if e.state in ("hang", "rise") and e.then == "hang" or e.state == "hang":
            hung = True
            break
        if e.state in ("stand", "sit", "sleep", "land") and e.vx == e.vy == 0:
            break
    return "hang" if hung else "floor"


def spread(gait: str, look: str = "masculine", seed: int = 5, count: int = 200) -> dict:
    """`count` throws: a uniform angle, a speed from `THROW_MIN` up to `THROW_MAX` (uniform), a release
    spot anywhere in the work area. Returns the share that ended hanging, and by direction."""
    rng = random.Random(seed)
    up_hang = up_n = 0
    results: Counter = Counter()
    for i in range(count):
        angle = rng.uniform(0.0, 2 * math.pi)
        speed = rng.uniform(eng.THROW_MIN * 1.05, eng.THROW_MAX)
        at = (rng.uniform(AREA[0], AREA[2]), rng.uniform(AREA[1], AREA[3]))
        res = throw_once(gait, look, seed * 1000 + i, angle, speed, at)
        results[res] += 1
        if math.sin(angle) < -0.5:  # mostly upward (screen y grows down)
            up_n += 1
            up_hang += res == "hang"
    return {"hang_share": results["hang"] / count, "up_hang": up_hang, "up": up_n, "n": count}
