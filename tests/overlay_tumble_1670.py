"""A thrown companion's tumble, measured on the engine and its fakes with a fixed clock (INBOX 1670, 17:05Z: "the
way that the desktop companion rotates in the air is not realistic at all, it like rotates by 45 degrees each time
and at 1 second intervals"). The figure is picked up, the pointer is moved at a speed and angle for a tenth of a
second and let go; every tick from there to the end of the flight is read: the spin picture drawn, how far it
turned since the last tick, how long a picture was held, the wake the engine asked for, and the turn rate."""

from __future__ import annotations

import math

from tessellate.core.overlay import sprites
from tests.test_overlay_ride_1670 import AREA, WIN, make

STEP = 1.0 / 60.0


def _release(e, speed: float, angle: float, at: tuple[float, float], curl: float = 0.0) -> float:
    """Pick the figure up with its middle at `at`, move the pointer `speed` px/s toward `angle` (with `curl` radians
    of turn per step on the way), let go. Returns the clock."""
    w, h = e.size
    px = min(max(at[0], AREA[0] + w / 2), AREA[2] - w / 2)
    py = min(max(at[1], AREA[1] + h / 2), AREA[3] - h / 2)
    n, t = 6, 1.0
    e.x, e.y = px - w / 2, py - h / 2
    e.update(t)
    sx, sy = int(e.x + w / 2), int(e.y + h / 2)
    e.update(t, (sx, sy), ("down", sx, sy))
    x, y, a = float(sx), float(sy), angle
    for _ in range(n):
        t += STEP
        x, y, a = x + math.cos(a) * speed * STEP, y + math.sin(a) * speed * STEP, a + curl
        e.update(t, event=("move", round(x), round(y)))
    t += STEP
    e.update(t, event=("up", round(x + math.cos(a) * speed * STEP), round(y + math.sin(a) * speed * STEP)))
    return t


def tumble(gait: str, look: str = "masculine", seed: int = 5, speed: float = 1500.0, angle: float = -0.6,
           at: tuple[float, float] = (900.0, 600.0), curl: float = 0.0, secs: float = 25.0) -> dict:
    """The flight from the release to its end. `turn` is the largest turn between two drawn pictures, in degrees;
    `hold` the longest a spin picture stayed up, in seconds; `wakes` the wakes asked while a spin picture was up;
    `jump` the largest change of the turn rate between two ticks as a share of max(the rate, 2 rad/s), counted away
    from a contact (a bounce shows the startled frame for `BONK_FOR`, and the rate may change then)."""
    e, _s = make(look, gait, seed)
    e.big_ready = e.trip_ready = e.climb_ready = float("inf")
    e.set_windows([WIN], 0.0)
    t = _release(e, speed, angle, at, curl)
    step = 360.0 / sprites.SPIN_STEPS
    shown, since, turn, hold, wakes, jump, picked = [], t, 0.0, 0.0, [], 0.0, None
    last_omega, bonk, grounded = getattr(e, "omega", None), e.bonk_until, getattr(e, "grounded", False)
    end = t + secs
    out = e.update(t)
    while t < end and e.state in ("fly", "hang", "rise"):
        t += max(0.004, min(0.1, (out.wake_ms or 16) / 1000.0))
        out = e.update(t)
        omega = getattr(e, "omega", None)
        # a floor touch is a contact too: from there the landing pays the turn out as one eased move to upright (INBOX 1683 v)
        contact = e.bonk_until != bonk or getattr(e, "grounded", False) != grounded or getattr(e, "touch_at", None) is not None
        bonk, grounded = e.bonk_until, getattr(e, "grounded", False)
        if omega is not None and last_omega is not None and e.state == "fly" and not contact:
            jump = max(jump, abs(omega - last_omega) / max(abs(last_omega), 2.0))
        last_omega = omega
        if e.state != "fly" or not out.frame.startswith("spin"):
            picked = None  # the startled frame of a bounce is shown between two spin pictures: a cut, not a turn
            continue
        wakes.append(out.wake_ms)
        k = int(out.frame[4:])
        if picked is not None and k != picked:
            d = abs(k - picked) % sprites.SPIN_STEPS
            turn = max(turn, min(d, sprites.SPIN_STEPS - d) * step)
            hold = max(hold, t - since)
            since = t
        picked = k
        shown.append(k)
    return {
        "state_end": e.state, "pictures": len(set(shown)), "turn": turn, "hold": hold, "jump": jump,
        "wake_min": min((w for w in wakes if w), default=0), "wake_max": max((w for w in wakes if w), default=0),
        "ticks": len(shown),
    }
