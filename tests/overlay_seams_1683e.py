"""Pose-continuity measurements for INBOX 1683 (e), (i) and (j): the engine on a fixed clock, one seeded
hour, every draw recorded. A "pose jump" is how far a drawn joint moves between two draws, in px of the
figure's own size: the head by lean and squash, the width by squeeze, the hem by drag. It is compared
with the per-draw step a normal ease makes, so a cut shows as a jump over `JUMP_PX`."""

from __future__ import annotations

import random

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import extras
from tests.overlay_sim_1670 import WINDOWS, home_at_edge
from tests.test_overlay_ride_1670 import make

#: A joint that moves more than this many px (of a 96 px figure) between two draws is a pop. A 60 Hz ease at
#: its fastest (a turn's squeeze, which is left out: it is a designed 0.24 s squeeze) steps about 3 px.
JUMP_PX = 4.0
#: The pose eases toward a turn's squeeze with a lag, so for this long after a turn its width recovers at the squeeze's own
#: designed rate (the squeeze sweeps ~9 px a draw at 60 Hz); that is the turn, not a pop.
TURN_TAIL = 0.3


def joints(p: tuple[float, float, float, float] | None, h: float) -> tuple[float, float, float, float]:
    """(head x shift, head y shift, width, hem drag) in px for a pose over a figure `h` px tall."""
    sx, sy, lean, drag = p if p is not None else (1.0, 1.0, 0.0, 0.0)
    return lean * h, (1.0 - sy) * h, sx * h * 0.5, drag


def twirling(e) -> bool:
    """An act whose keys squeeze the width to a sliver (a flip's twirl, `extras._TURN2`): the same designed turn squeeze as a
    turn's, played by the act, so it is left out the way a turn is."""
    act = eng.bh.ACTIVITIES.get(e.act or "") or extras.REACT_ACTS.get(e.act or "")
    return e.state == "act" and act is not None and min(k[1] for k in act.keys) < 0.5


def seam(a, b, h: float) -> float:
    """The largest joint move between two draws' poses."""
    return max(abs(x - y) for x, y in zip(joints(a, h), joints(b, h)))


def hour(gait: str, seed: int, secs: float = 3600.0, look: str = "masculine", detail: bool = False) -> dict:
    """One seeded hour with the person about; returns draw counts and every pose jump over `JUMP_PX`."""
    e, _s = make(look, gait, seed)
    home_at_edge(e)
    e.big_ready, e.trip_ready, e.climb_ready = 300.0, 120.0, 0.0
    e.set_windows(list(WINDOWS), 0.0)
    saved = eng.IDLE_SIT, eng.IDLE_SLEEP
    eng.IDLE_SIT = eng.IDLE_SLEEP = float("inf")
    rng = random.Random(seed + 7)
    px, t = 400, 0.0
    try:
        out = e.update(0.0, (px, 600))
        prev, prev_state, prev_t = out, e.state, 0.0
        turned_at = -9.0
        jumps: list[tuple[float, str, str, float]] = []
        draws = 0
        while t < secs:
            t += min(max(0.016, (out.wake_ms or 1000) / 1000.0), 1.0)
            if rng.random() < 0.04:
                px = rng.randint(200, 1700)
            out = e.update(t, (px, 600))
            draws += 1
            if e.state not in eng.POSE_OFF and prev_state not in eng.POSE_OFF:
                j = seam(prev.pose, out.pose, e.size[1])
                if j > JUMP_PX and t - prev_t < 0.25 and not e.turn_to and not twirling(e) and t - turned_at > TURN_TAIL and e.state != "warp":  # a warp's squeeze is a designed 0.5 s ease
                    jumps.append((round(t, 2), prev_state, e.state, round(j, 1)))
                    if detail:
                        print(t, prev_state, e.state, e.act, e.mode, prev.pose, out.pose, e.cur, e.pose_goal, out.wake_ms)
            prev, prev_state, prev_t = out, e.state, t
            if e.turn_to:
                turned_at = t
    finally:
        eng.IDLE_SIT, eng.IDLE_SLEEP = saved
    return {"draws": draws, "jumps": jumps}


if __name__ == "__main__":  # python -m tests.overlay_seams_1683e
    for gait in ("walk", "float"):
        for seed in (1, 2, 3):
            r = hour(gait, seed)
            print(gait, seed, r["draws"], len(r["jumps"]), r["jumps"][:6])
