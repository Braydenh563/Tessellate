"""Seeded one-hour parity measure for the desktop companion (INBOX 1683 asks M4, M5, M6, M7, B9 quality): how many
different acts and pictures an hour it shows at rest, the longest run of one act, the share of the hour spent
moving, the wakes a minute, and how long a pointer gesture or a screen event takes to change the picture.
Fakes and a fixed clock, no Win32. `python -m tests.overlay_parity_sim` prints the table."""

from __future__ import annotations

import random
from collections import Counter

from tessellate.core.overlay import engine as eng
from tests.overlay_sim_1670 import MOVING, WINDOWS, home_at_edge, runs
from tests.test_overlay_ride_1670 import make


def picture(o: eng.Output) -> tuple:
    """Everything a viewer can see change: the frame, its pose, the prop drawn with it and the face on it."""
    return (o.frame, o.flip, o.pose, o.clip, o.fx, o.alpha, getattr(o, "prop", None), getattr(o, "face", None))


def hour(gait: str, look: str, seed: int, secs: float = 3600.0) -> dict:
    """One hour awake with a pointer wandering in and out of reach."""
    saved = eng.IDLE_SIT, eng.IDLE_SLEEP
    eng.IDLE_SIT = eng.IDLE_SLEEP = float("inf")
    try:
        e, _s = make(look, gait, seed)
        e.presence = False  # Intent moved (INBOX 1692, 00:50Z): spells (presence) have their own tests; this one measures the plain acts
        home_at_edge(e)
        e.big_ready, e.trip_ready, e.climb_ready = 300.0, 120.0, 0.0
        e.set_windows(list(WINDOWS), 0.0)
        rng = random.Random(seed + 7)
        px, t = 400, 0.0
        out = e.update(0.0, (px, 600))
        acts: list[str] = []
        pics: set = set()
        wakes = moving = 0.0
        last_start = None
        while t < secs:
            step = min(max(0.016, (out.wake_ms or 1000) / 1000.0), 1.0)
            t += step
            if rng.random() < step / 25.0:
                px = rng.randint(200, 1700)
            out = e.update(t, (px, 600))
            wakes += 1
            if e.state == "act" and e.act_started != last_start:
                last_start = e.act_started
                acts.append(e.act or "?")
            moving += step if e.state in MOVING else 0.0
            pics.add(picture(out))
        return {
            "acts": len(set(acts)), "act_starts": len(acts), "longest_repeat": runs(acts), "pictures": len(pics),
            "moving_share": moving / secs, "wakes_per_min": wakes / (secs / 60.0), "counts": Counter(acts),
        }
    finally:
        eng.IDLE_SIT, eng.IDLE_SLEEP = saved


if __name__ == "__main__":
    for look in ("masculine", "feminine"):
        for seed in (2, 3):
            r = hour("float", look, seed)
            r.pop("counts")
            print(look, seed, {k: round(v, 4) if isinstance(v, float) else v for k, v in r.items()})
