"""How the figure meets a surface (E6): a landing on the feet comes down soft, in a stumble or in a roll, and a wall it
touches presses it flat for a moment (audit-1028 K24 layering: its own mixin, so `engine_flight.py` does not grow).

`TouchMixin` holds the touch of a landing (`_touch_down`, the roll, the squash `_touch_pose` draws), the turn upright a
landing on the feet makes (`_feet_begin`, `_feet_step`, moved whole from `engine_flight.py`) and the wall squash
(`_edge_touch`, `_edge_squash`). It reads only `engine_consts` and `landing`."""

from __future__ import annotations

import math

from . import landing as ld
from .engine_consts import LAND_FOR


class TouchMixin:
    #: How the last landing on the feet came down: `(touch, at, hold seconds, direction)` or None; the roll under way
    #: `(start angle, start rate, direction, seconds in)` or None; the last wall touch `(at, side, strength 0..1)`.
    #: Class defaults: the engine's `__init__` is not the place.
    touched: tuple[str, float, float, int] | None = None
    roll: tuple[float, float, int, float] | None = None
    edge: tuple[float, int, float] | None = None

    def _feet_begin(self) -> None:
        """The first floor contact of a body that comes down on its feet: from here its turn is one eased move (a cubic
        Hermite from the angle and rate now to upright and still, `landing.FEET_FOR` s). A spring stiff enough to be upright
        in that time changed the rate by up to 3 rad/s a tick; the move changes it by 0.14 (INBOX 1683 v)."""
        if self.feet_from is None:
            self.feet_from, self.feet_s = (ld.wrap(self.angle), self.omega + self.kick), 0.0
            self.kick = 0.0

    def _feet_step(self, dt: float) -> None:
        a0, w0 = self.feet_from or (0.0, 0.0)
        self.feet_s += dt
        self.angle, self.omega = ld.hermite(a0, w0, self.feet_s)
        if self.feet_s >= ld.FEET_FOR:
            self.angle = self.omega = 0.0

    def _touch_down(self, now: float) -> None:
        """A landing on the feet comes down soft, in a stumble or in a roll by the speed it meets the floor at
        (`landing.touch`). A roll is one eased forward turn that takes the impact (it keeps the way it was going, at
        least `ROLL_SPEED_MIN`); the others turn upright as before."""
        kind = ld.touch(abs(self.vy), self._scale())
        direction = (1 if self.vx >= 0 else -1) if abs(self.vx) > 1.0 else (1 if self.facing >= 0 else -1)
        self.touched = (kind, now, LAND_FOR * ld.TOUCHES[kind][1], direction)
        if kind == "roll":
            self.roll = (ld.wrap(self.angle), self.omega + self.kick, direction, 0.0)
            self.kick = 0.0
            self.vx = direction * max(abs(self.vx), ld.ROLL_SPEED_MIN * self._scale())
        else:
            self._feet_begin()  # a wall bounce's unpaid kick is dropped there: the floor turns it upright, not further

    def _roll_step(self, dt: float) -> None:
        a0, w0, direction, s = self.roll or (0.0, 0.0, 1, 0.0)
        s += dt
        self.angle, self.omega = ld.roll_turn(a0, w0, direction, s)
        if s >= ld.ROLL_FOR:
            self.angle = self.omega = 0.0
            self.roll = None
        else:
            self.roll = (a0, w0, direction, s)

    def _floor_friction(self) -> float:
        """The floor's grip on a body sliding in: a lying one skids, a standing one by its touch."""
        if self.lie_goal is not None:
            return ld.SKID_K
        return ld.TOUCHES[self.touched[0]][3] if self.touched else ld.STUMBLE_K

    def _touch_hold(self, now: float) -> None:
        """The hold of the landing's touch, from the moment it settles."""
        if self.touched:
            self.state_until = now + self.touched[2]
            self.touched = (self.touched[0], now, self.touched[2], self.touched[3])

    def _fall_touch(self, now: float, speed: float) -> None:
        """A step off a ledge touches down too, but never rolls: it has no spin to roll out of."""
        kind = ld.touch(speed, self._scale())
        kind = "stumble" if kind == "roll" else kind
        hold = LAND_FOR * ld.TOUCHES[kind][1]
        self.state_until, self.touched = now + hold, (kind, now, hold, self.facing)

    def _touch_pose(self, now: float) -> tuple[float, float, float]:
        """The squash and forward lean of the landing: how hard it came down sets the depth, the length and a stumble's lean."""
        t = self.touched
        k, span = (ld.TOUCHES[t[0]], t[2]) if t and 0.0 <= now - t[1] <= t[2] + 0.1 else (None, LAND_FOR)
        sin = math.sin(min(1.0, 1.0 - max(0.0, self.state_until - now) / span) * math.pi)
        depth = ld.LAND_SQUASH * (k[0] if k else 1.0) * sin
        return 1.0 + 0.5 * depth, 1.0 - depth, (t[3] * ld.STUMBLE_LEAN * k[2] * sin if k and k[2] else 0.0)

    def _edge_touch(self, side: int, speed: float, now: float) -> None:
        """A wall touched at `speed` (px/s): how hard sets how flat it is pressed (`_edge_squash`)."""
        self.edge = (now, side, min(1.0, speed / (ld.EDGE_SPEED * self._scale())))

    def _edge_squash(self, now: float) -> tuple[float, int] | None:
        """`(amount 0..1 on a 1/8 grid, side)` the figure is pressed against a wall, or None: a bounce squeezes for
        `EDGE_FOR` and lets go; a slide holds `EDGE_HOLD` (eased in) while it is stuck. The runner draws it."""
        if self.edge is None:
            return None
        at, side, strength = self.edge
        u = (now - at) / ld.EDGE_FOR
        if self.wall:
            amount = ld.EDGE_HOLD * min(1.0, max(u, 0.0) / 0.5) if u < 0.5 else ld.EDGE_HOLD
        elif 0.0 <= u < 1.0:
            amount = strength * math.sin(math.pi * u)
        else:
            return None
        amount = round(amount * 8) / 8.0
        return (amount, side) if amount else None
