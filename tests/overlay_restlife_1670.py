"""Seeded rest-life measurement for the desktop companion (INBOX 1670, 15:40Z): the engine and its fakes
on a fixed clock, no pointer, the person about (the long-idle sit and sleep off). It counts what the host
would do at rest: wakes, draws (the picture, pose or window differs from the last), the distinct pictures
drawn and the window moves. Rest is a stand, a sit or a sleep with nothing else started."""

from __future__ import annotations

from tessellate.core.overlay import engine as eng
from tests.overlay_sim_1670 import home_at_edge
from tests.test_overlay_ride_1670 import make


def rest_life(gait: str, look: str, state: str, seed: int, secs: float = 120.0, reduced: bool = False) -> dict:
    """`secs` of `state` with nothing started: draws, distinct pictures, window moves and wakes a minute."""
    saved = eng.IDLE_SIT, eng.IDLE_SLEEP
    eng.IDLE_SIT = eng.IDLE_SLEEP = float("inf")
    try:
        e, _s = make(look, gait, seed)
        e.reduced = reduced
        home_at_edge(e)
        e.big_ready = e.trip_ready = e.climb_ready = float("inf")
        e.update(0.0)
        if state != "stand":
            e._enter(state, 0.0)
            e.state_until = float("inf")
        e.next_ambient = 5.0  # the first blink does not wait out the whole run
        out = e.update(0.0)
        t, wakes, draws, moves = 0.0, 0, 0, 0
        pics: set = set()
        per_sec: dict[int, int] = {}
        last = None
        while t < secs:
            t += min(max(0.016, (out.wake_ms or 1000) / 1000.0), 1.0)
            out = e.update(t)
            wakes += 1
            pic = (out.frame, out.flip, out.pose, out.clip, out.fx, out.alpha)
            if last is not None and (pic != last[0] or (out.x, out.y) != last[1]):
                draws += 1
                per_sec[int(t)] = per_sec.get(int(t), 0) + 1
            if last is not None and (out.x, out.y) != last[1]:
                moves += 1
            last = (pic, (out.x, out.y))
            pics.add(pic)
        k = secs / 60.0
        return {
            "state_end": e.state, "wakes": wakes / k, "draws": draws / k, "pictures": len(pics) / k,
            "distinct": len(pics), "moves": moves / k, "max_draws_a_second": max(per_sec.values(), default=0),
        }
    finally:
        eng.IDLE_SIT, eng.IDLE_SLEEP = saved
