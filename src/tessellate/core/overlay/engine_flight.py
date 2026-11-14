"""The engine's flight, fall and walk: the ceiling and the walls, a thrown figure's arc, spin and righting, the landing tumble, and the walking step (audit-1028 K24, moved whole out of engine.py).

`FlightMixin` holds the `_do_fly`, `_do_fall` and `_do_walk` states and what they call. It reads only `engine_consts` and the sibling behaviour modules."""

from __future__ import annotations

import math
from . import behaviour as bh, landing as ld
from .engine_consts import (
    AWAY_DRIFT,
    AWAY_FALL,
    AWAY_FOR,
    BONK_FOR,
    BOUNCE_DAMP,
    CEIL_CATCH,
    CEIL_LEAVE,
    CEIL_TILT,
    CEIL_UPWARD,
    FLOAT_DRAG,
    FLOAT_PULL,
    FLY_REST_DWELL,
    FLY_SPIN_MIN,
    GRAVITY,
    HOP_RISE,
    HOP_SPAN,
    Monitor,
    RIGHT_RAMP,
    RIGHT_SPEED,
    RIGHT_SPENT,
    RIGHT_W,
    SPIN_CONTACT,
    SPIN_DRAG,
    SPIN_EASE,
    SPIN_LEVER,
    SPIN_OMEGA,
    SPIN_SWIRL,
    THROW_MAX,
    WALK_SPEED,
)


#: Each throw's own give: BOUNCE_DAMP scaled by up to this much either way, drawn at the release from its own stream (L148).
BOUNCE_SPREAD = 0.25

class FlightMixin:
    def _hit_ceiling(self, m: Monitor, uy0: float, now: float) -> bool:
        """A thrown figure that reaches the top of an open work area takes hold and hangs."""
        top, scale = m.area[1], self._scale()
        if self.vy >= 0 or not self._open_side(m, "top"):
            return False
        self.y = max(self.y, uy0)  # a step may carry it past the top: the drawn box stops at the edge
        if self.y > max(top - self._lift(), uy0):
            return False
        if self._leaves():
            self._leave_top(m, now)
            return True
        if not self._ceiling_holds():  # it bounces off the top like a side wall and drifts back down
            self.vy = abs(self.vy) * self.bounce_k
            self.bonk_until = now + BONK_FOR
            self._spin_contact(1.0 if self.vx >= 0 else -1.0)
            return False
        hang_y, drawn = top - self._lift(), self.y + self._dy("held")
        self.vx = self.vy = self.angle = 0.0
        if abs(drawn - hang_y) > 4.0 * scale:  # caught above where the hands go: reach up to it
            self._rise((self.x, hang_y), "hang", now, drawn_from=drawn)
        else:
            self.y = hang_y
            self._enter("hang", now)
        return True

    def _leaves(self) -> bool:
        """Whether the throw reaching the top was past `CEIL_LEAVE` and mostly upward: it goes out through the top."""
        vx, vy = self.launch
        return -vy >= CEIL_LEAVE * self._scale() and -vy >= CEIL_UPWARD * math.hypot(vx, vy)

    def _leave_top(self, m: Monitor, now: float) -> None:
        """Out through the top: unseen for longer the harder it was thrown (the line to `THROW_MAX` maps to `AWAY_FOR`)."""
        k = self._scale()
        f = min(1.0, max(0.0, (-self.launch[1] / k - CEIL_LEAVE) / (THROW_MAX - CEIL_LEAVE)))
        self.away_until = now + AWAY_FOR[0] + (AWAY_FOR[1] - AWAY_FOR[0]) * f
        self.away_x = self.x
        self.vx = self.vy = self.omega = self.kick = 0.0
        self.y = m.area[1] - self.size[1] - 40 * k

    def _return_top(self, now: float) -> None:
        """Back in from above the top near where it left, turning over; the ordinary flight lands it."""
        k, w = self._scale(), self.size[0]
        ux0, ux1 = self._ride_limits("fly")[:2]
        self.away_until = None
        self.x = min(max(self.away_x + self.rng.uniform(-AWAY_DRIFT, AWAY_DRIFT) * w, ux0), ux1)
        self.vx, self.vy = self.rng.uniform(-80, 80) * k, AWAY_FALL * k
        self.launch = (self.vx, self.vy)
        self.omega = self.rng.choice((-1, 1)) * SPIN_OMEGA[1] * 0.8
        self.slow_for = self.right_t = 0.0

    def _ceiling_holds(self) -> bool:
        """Whether the throw now reaching the top was hard and mostly upward (see `CEIL_CATCH`) and the body is near
        upright: head over heels it cannot take hold, it smacks the ceiling and drops."""
        return self._ceiling_fast() and abs(ld.wrap(self.angle)) <= CEIL_TILT

    def _ceiling_fast(self) -> bool:
        vx, vy = self.launch
        return -vy >= CEIL_CATCH * self._scale() and -vy >= CEIL_UPWARD * math.hypot(vx, vy)

    def _reaching(self) -> bool:
        """Rising hard towards a top it would take hold of, a few tenths of a second away: it turns to reach for it."""
        m = self.current_monitor()
        if self.vy >= 0 or self.grounded or not self._open_side(m, "top") or not self._ceiling_fast():
            return False
        return self.y - (m.area[1] - self._lift()) < -self.vy * ld.REACH_AHEAD

    def _track_rest(self, speed: float, dt: float) -> None:
        """Count how long a thrown figure has been slow. Once it has been long enough it is laid
        down for good (a floater's pull back to its hover can creep its speed over the line again,
        and the tumble must not start up on the way to rest) until the next throw."""
        if self.slow_for < FLY_REST_DWELL:
            self.slow_for = self.slow_for + dt if speed < FLY_SPIN_MIN * self._scale() else 0.0

    def _do_fly(self, now: float, dt: float) -> None:
        """Thrown: ballistic (gravity for a walker; for a floater air drag and a gentle
        pull to its hover height). Bounces off the outer walls, hangs from the ceiling."""
        if self.wrapping is not None:
            self._wrap_step(dt)
            return
        if self.away_until is not None:
            if now < self.away_until:
                return
            self._return_top(now)
        scale = self._scale()
        m = self.ground_mon if self.grounded and self.ground_mon else self.current_monitor()
        floater = self.gait == "float"
        if floater:
            decay = math.exp(-FLOAT_DRAG * dt)
            self.vx *= decay
            self.vy = self.vy * decay + FLOAT_PULL * (self.ground_y(m) - self.y) * dt
        elif self.wall:  # sliding down a wall: it drags, and it scrabbles (`_air_wobble`)
            self.vy = min(self.vy + GRAVITY * ld.WALL_GRIP * scale * dt, ld.WALL_SLIDE * scale)
        else:
            self.vy += GRAVITY * scale * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        speed = math.hypot(self.vx, self.vy)
        self._track_rest(speed, dt)
        self._spin(dt, speed)
        self._air_wobble(now, dt)
        uy0, uy1 = self._fly_walls(m, now)
        if self.wall and self._wall_pull(now):
            return
        if self._hit_ceiling(m, uy0, now):
            return
        floor = min(self.floor_y(m), uy1) if self._open_side(m, "bottom") else self.floor_y(m)
        if floater:
            self._float_floor(m, floor, speed, now)
        elif self.y >= floor or self.grounded:
            self._land_tumble(m, floor, dt, now)

    def _float_floor(self, m: Monitor, floor: float, speed: float, now: float) -> None:
        """A thrown floater at its floor line: the landing move begins, the picture's feet reach the line, and once upright
        and slow it settles into the stand."""
        scale = self._scale()
        if self._floored():
            self._feet_begin()
        floor = self._pose_floor(m, floor)  # the picture shown now, not the tumble's tallest frame: upright, its feet reach the line
        self.y = min(self.y, floor)
        # at the drawn-box limit counts as down: the tumble's box is taller than the figure, so the
        # limit can sit above the rest line, and it hung there in the limp pose (INBOX 1670)
        if speed < 25 * scale and self._righted() and (abs(self.ground_y(m) - self.y) < 4 * scale or self.y >= floor - 0.5):
            self.vx = self.vy = 0.0
            self.y = self.ground_y(m)
            self.settled_now = True
            self.squash_at = now  # INBOX 1683: the settle ends in a small squash (`_ground_pose`), then the stand
            self._enter("stand", now)

    def _fly_walls(self, m: Monitor, now: float) -> tuple[float, float]:
        """The side walls (of what is drawn: the tumble's widest frame, not the window around it); returns the
        drawn box's top and bottom limits. A hard hit smacks (`_smack`); a soft one bounces; on the floor it stops."""
        ux0, ux1, uy0, uy1 = self._ride_limits("fly")
        if self.grounded or self.wall:
            ex0, ex1 = self._ride_limits(self._fly_frame())[:2] if self.grounded else (ux0, ux1)
            if self.wall:
                self.x, self.vx = (ex0 if self.wall < 0 else ex1), 0.0
            elif not ex0 <= self.x <= ex1:
                self.x, self.vx = min(max(self.x, ex0), ex1), 0.0
            return uy0, uy1
        side = -1 if self.x < ux0 and self._open_side(m, "left") else (1 if self.x > ux1 and self._open_side(m, "right") else 0)
        if side:
            self._smack(side, ux0 if side < 0 else ux1, ux1 if side < 0 else ux0, now)
        return uy0, uy1

    def _smack(self, side: int, edge: float, far: float, now: float) -> None:
        """A wall hit: soft or a floater's, it bounces; hard, a walker sticks and slides down scrabbling, or (harder
        still) goes out of the edge and in at the far one (INBOX 1683 k)."""
        verdict = "bounce" if self.gait == "float" else ld.smack(abs(self.vx), self._scale(), self.rng)
        if verdict == "through":
            self._start_wrap(side, edge, far, now)
            return
        self.x = edge
        self.bonk_until = now + BONK_FOR
        self._edge_touch(side, abs(self.vx), now)
        if verdict == "slide":
            self.wall, self.vx, self.vy, self.outcome = side, 0.0, self.vy * 0.4, "slide"
            self.wob_kind, self.wob_t0 = "scrabble", now
            self._spin_contact(float(-side))
            return
        self.vx = -side * abs(self.vx) * self.bounce_k
        self._spin_contact(float(-side))

    def _start_wrap(self, side: int, edge: float, far: float, now: float) -> None:
        """Out of one side and in at the other without a cut (INBOX 1683 i, j): the old jump put the figure at the far
        edge in one draw. Now it keeps its speed and slides out under the edge's clip (the `sink` of a peek), then
        in under the far edge's clip, so every draw moves it by its own velocity and no more."""
        self.x, self.vx, self.outcome = edge, self.vx * 0.9, "through"
        self.passed_at = now
        self.wrapping = {"side": side, "far": far, "phase": "out"}
        self.peek_edge, self.sink = ("left" if side < 0 else "right"), 0.0

    def _wrap_step(self, dt: float) -> None:
        """Advance the crossing by the distance the figure travels in `dt` (gravity and the spin run as in a throw)."""
        w = self.wrapping
        if w is None:
            return
        scale = self._scale()
        if self.gait != "float":
            self.vy += GRAVITY * scale * dt
        self.y += self.vy * dt
        m = self.current_monitor()
        uy0, uy1 = self._ride_limits("fly")[2:]
        floor = min(self.floor_y(m), uy1) if self._open_side(m, "bottom") else self.floor_y(m)
        if self.y > floor:  # the crossing is a flight: the floor holds it (review of INBOX 1683 i)
            self.y, self.vy = floor, 0.0
        elif self.y < uy0:  # open or not, the top stops a crossing: it cannot take hold mid-wrap, so it went through
            self.y, self.vy = uy0, max(self.vy, 0.0)
        self._spin(dt, math.hypot(self.vx, self.vy))
        width = max(1.0, self._box(self._fly_frame())[2])
        step = max(abs(self.vx) * dt, 1.0) / width
        if w["phase"] == "out":
            self.sink = min(1.0, self.sink + step)
            if self.sink >= 1.0:
                w["phase"] = "in"
                self.x = w["far"]
                self.peek_edge = "right" if w["side"] < 0 else "left"
        else:
            self.sink = max(0.0, self.sink - step)
            if self.sink <= 0.0:
                self.sink, self.peek_edge, self.wrapping = 0.0, None, None

    def _air_wobble(self, now: float, dt: float) -> None:
        """The scrabble against a wall, or a flail once a drop has gone on a while with the tumble spent."""
        kind = "scrabble" if self.wall else None
        if self.vy <= 0 or self.grounded:
            self.air_t0 = now
        elif not self.wall and self.gait != "float" and (now < self.flail_until or (now - self.air_t0 > ld.FLAIL_AFTER and abs(self.omega) < 1.5)):
            kind = "flail"
        if kind != self.wob_kind:
            self.wob_kind, self.wob_t0 = kind, now
        # a low-pass, so a flail that ends at the floor or turns into a scrabble fades, never steps
        self.wob += (ld.wobble(self.wob_kind, now - self.wob_t0) - self.wob) * (1.0 - math.exp(-25.0 * dt))

    def _pose_floor(self, m: Monitor, floor: float) -> float:
        """Where the engine's y rests the picture now shown on the floor: a body lying down is shorter than the
        tumble's tallest frame, so it lies on the floor, not above it."""
        if not self._open_side(m, "bottom"):
            return floor
        return min(self.floor_y(m), m.area[3] - self._ride_box(self._fly_frame())[3])

    def _land_tumble(self, m: Monitor, floor: float, dt: float, now: float) -> None:
        """A walker's tumble reaches the floor and comes to rest by outcome (`landing.decide`): stumbling onto its
        feet, or down on its back or belly, skidding, lying a moment, then getting up with an eased turn."""
        if not self.grounded:
            self.grounded, self.wall = True, 0
            self.ground_mon = m  # the slide stays on the screen it landed on: a seam would jump the floor under it
            self.outcome, goal = ld.decide(self.angle, self.omega, 1 if self.facing >= 0 else -1, self.vy > 0 and abs(self.launch[1]) > 600 * self._scale(), self.rng)
            self.lie_goal = goal if self.outcome != "feet" else None
            if self.lie_goal is not None:  # the thump of a body going down; a landing on the feet adds no turn (INBOX 1683 v)
                self._spin_contact(1.0 if self.vx >= 0 else -1.0)
            else:
                self._touch_down(now)  # reads the speed it meets the floor at, before the floor takes it
        self.vy = 0.0
        self.vx *= math.exp(-self._floor_friction() * dt)
        self.x = min(max(self.x, m.area[0]), m.area[2] - self.size[0])
        self.y = self._pose_floor(m, floor)
        if self.lie_goal is not None:
            self._lie_down(now)
        elif self._righted() and abs(self.vx) < 20 * self._scale():
            self.vx = 0.0
            self.y = self.floor_y(m)
            self.settled_now = True
            if self.outcome == "feet":
                self._enter("land", now)
                self._touch_hold(now)
            else:
                self._start_act("shake_off", now)  # it picks itself up and shakes it off, miffed

    def _lie_down(self, now: float) -> None:
        """Down on its back or belly: once it has stopped turning and sliding it lies a moment, then gets up."""
        if not self.lying:
            if abs(self._turn_err()) < 0.06 and abs(self.omega) < 0.4 and abs(self.vx) < 40 * self._scale():
                self.lying, self.lie_until = True, now + ld.rest_for(self.rng)
        elif now >= self.lie_until:
            self.lying, self.lie_goal = False, None

    def _do_fall(self, now: float, dt: float) -> None:
        scale = self._scale()
        self.vy += GRAVITY * scale * dt
        self.y += self.vy * dt
        self.x += self.vx * dt
        m = self.current_monitor()
        self.x = min(max(self.x, m.area[0]), m.area[2] - self.size[0])
        floor = self.floor_y(m)
        if self.y >= floor:
            speed = abs(self.vy)
            self.y, self.vy, self.vx = floor, 0.0, 0.0
            self.settled_now = True
            self._enter("land", now)
            self._fall_touch(now, speed)

    def _do_walk(self, now: float, dt: float) -> None:
        if self._turning(now):
            self.walk_started, self.pace_last = now, 0.0
            return
        left = abs(self.goal[0] - self.x) if self.goal is not None else None
        pace = self._brake(now, dt) if self._yields(now, self.facing * 90 * self._scale()) else self._pace(now, left)
        if pace <= 0.0:
            return
        step = WALK_SPEED * self._scale() * dt * self.facing * pace
        nx = self.x + step
        if self.goal is not None and abs(self.goal[0] - self.x) <= max(abs(step), 0.75):
            self.x = self.goal[0]
            self._arrive(now)
            return
        bounds = self._reach(nx)
        if bounds is None:  # the end of the walkable floor: turn around
            if self.goal is not None:  # a trip that cannot be made is dropped
                dropped = self.then
                self.goal = None
                self._arrive_card(now) if dropped == "card" else self._enter("stand", now)
                return
            if self.perch is not None:  # the end of the window: hop or fall off it
                self._leave_perch(now, hop=self.rng.random() < 0.5)
                return
            self._face(-self.facing, now)
        else:
            self.x = nx
            self._hop_arc(left)
            floor = self.floor_y(bounds)
            if floor > self.y + 0.5:
                self._start_fall(0.0)
            elif floor < self.y - 0.5:
                self.hop_from = self.y
                self._enter("hop", now)
        if self.state == "walk" and now >= self.state_until:
            self._enter("stand", now)

    def _hop_arc(self, left: float | None) -> None:
        """The lift of a hop-chain step: a half sine per span of ground, eased in with the pace and out over the last
        span. Only the drawing is lifted (`_display`); the body stays on its floor, so nothing here can fall."""
        if not self.hopping:
            return
        span = HOP_SPAN * self.size[0]
        u = ((self.travel - self.hop_origin) / span) % 1.0
        fade = 1.0 if left is None else bh.smooth(left / span)
        self.hop_lift = math.sin(math.pi * u) * HOP_RISE * self.size[1] * min(1.0, self.pace_last) * fade

    def _reach(self, nx: float) -> Monitor | None:
        """The monitor the figure may stand on at `nx`, or None past the last one:
        one whose width holds the figure's middle and whose height overlaps its own."""
        cx = nx + self.size[0] / 2
        if self.perch is not None and not self.perch.left <= cx < self.perch.right:
            return None
        if nx < min(m.area[0] for m in self.monitors) or nx + self.size[0] > max(m.area[2] for m in self.monitors):
            return None
        for m in self.monitors:
            left, top, right, bottom = m.area
            if left <= cx < right and top < self.y + self.size[1] and bottom > self.y - 2 * self.size[1]:
                return m
        return None

    def _start_fall(self, vx: float, vy: float = 0.0) -> None:
        if self.gait == "float":
            self._start_fly(vx, vy)
            return
        self.vx, self.vy = vx, vy
        self.y += self._dy(self._frame(self.now)) - self._dy("fall")  # drawn where it was
        self._enter("fall", self.now)

    def _launch_spin(self, vx: float, vy: float, swirl: float) -> float:
        """The turn rate a throw leaves with: faster for a harder throw, in the direction it moves sideways,
        and a curling throw adds its swirl (-1 to 1, clockwise positive). A drop (no speed) leaves none."""
        speed = math.hypot(vx, vy)
        if speed < 1.0:
            return 0.0
        lo, hi = SPIN_OMEGA
        rate = lo + (hi - lo) * min(1.0, speed / (THROW_MAX * 0.5 * self._scale()))
        turn = (1.0 if vx > 0 else -1.0) if abs(vx) > 1.0 else (1.0 if swirl >= 0 else -1.0)
        # the hand held it off-centre: the torque is (arm x velocity) over (arm squared + a body's radius squared)
        rx, ry = self.grab[0] - self.size[0] / 2, self.grab[1] - self.size[1] / 2
        radius = SPIN_LEVER * max(self.size)
        lever = (rx * vy - ry * vx) / (rx * rx + ry * ry + radius * radius)
        return max(-hi, min(hi, 0.6 * turn * rate + lever + SPIN_SWIRL * swirl))

    def _spin(self, dt: float, speed: float) -> None:
        """One step of the turn: its own drag, and once the flight is slow (or on the floor) an eased turn
        to the nearest upright."""
        if self.feet_from is not None:
            self._feet_step(dt)
        elif self.roll is not None:
            self._roll_step(dt)
        else:
            self.omega *= math.exp(-SPIN_DRAG * dt)
            self._pay_kick(dt)
            self._right_step(dt, speed)
            self.angle += self.omega * dt
        # on the floor, upright and still it is the held pose at once: the tumble's upright frame stands 14 px higher than the held
        # one, so waiting out the dwell drew the feet off the line and then stepped them down (INBOX 1683 v)
        if (self.slow_for >= FLY_REST_DWELL or self.grounded or self._floored()) and self._righted():
            self.laid = True  # laid down for good until the next throw: the held pose never swaps back to the tumble

    def _pay_kick(self, dt: float) -> None:
        """A contact's change of rate is paid out over a few ticks, not taken in one."""
        if not self.kick:
            return
        part = self.kick * (1.0 - math.exp(-SPIN_EASE * dt))
        self.omega, self.kick = self.omega + part, self.kick - part
        if abs(self.kick) < 0.02:
            self.omega, self.kick = self.omega + self.kick, 0.0

    def _right_step(self, dt: float, speed: float) -> None:
        """The eased turn to the nearest upright; a spent tumble rights itself too, not only a slow flight: a floater's
        drag kept it over the speed line while the turn had died down, so it hung tilted (INBOX 1683 k: a held 45 degrees)."""
        reach = self._reaching()
        slow = speed < RIGHT_SPEED * self._scale() or self.grounded or self.wall != 0 or abs(self.omega) < RIGHT_SPENT or reach
        self.right_t = self.right_t + dt if slow else 0.0
        if self.right_t <= 0.0:
            return
        # on the floor the turn starts at once: the long ramp held a 45 degree tilt still for most of a second
        quick = self.grounded or reach
        gain = bh.smooth(min(1.0, self.right_t / (ld.GROUND_RAMP if quick else RIGHT_RAMP)))
        w = self._right_w(reach)
        self.omega -= gain * (w * w * self._turn_err() + 2 * w * self.omega) * dt

    def _right_w(self, reach: bool) -> float:
        if self.lie_goal is not None and not self.lying:
            return ld.THUMP_W
        return ld.GETUP_W if self.grounded else (ld.REACH_W if reach else RIGHT_W)

    def _floored(self) -> bool:
        """A floater at its rest line: it never sets `grounded` (it hovers), but this is its floor contact."""
        if self.gait != "float" or self.vy < 0:
            return False
        m = self.current_monitor()
        # the drawn box's bottom limit can sit above the rest line (see `_do_fly`): at it counts as down
        return self.y >= min(self.ground_y(m) - 4 * self._scale(), self._pose_floor(m, self.floor_y(m))) - 0.5

    def _turn_err(self) -> float:
        """How far the angle is from where it settles: the nearest upright, or the quarter turn it lies at."""
        if self.lie_goal is None:
            return ld.wrap(self.angle)
        return ld.wrap(self.angle - self.lie_goal)

    def _righted(self) -> bool:
        """Upright and still turning no more than a drift: safe to lay down."""
        if self.lie_goal is not None or self.roll is not None:
            return False
        err = ld.wrap(self.angle)
        return abs(err) < 0.012 and abs(self.omega) < 0.15  # 0.7 degrees: the snap to the upright stand is under one (review of 1683)

    def _spin_contact(self, push: float) -> None:
        """A bounce takes some of the turn, reverses it and adds the kick of the surface (`push` -1 to 1)."""
        hi = SPIN_OMEGA[1]
        self.kick = max(-hi, min(hi, -SPIN_CONTACT * self.omega + SPIN_SWIRL * 0.5 * push)) - self.omega

    def _start_fly(self, vx: float, vy: float, swirl: float = 0.0) -> None:
        self.vx, self.vy = vx, vy
        self.launch = (vx, vy)
        self.slow_for = self.right_t = 0.0
        self.grounded = self.laid = self.lying = False
        self.feet_from, self.feet_s = None, 0.0
        self.outcome = self.lie_goal = self.wob_kind = self.touched = self.roll = None
        self.wall, self.wob, self.air_t0 = 0, 0.0, self.now
        self.y += self._dy(self._frame(self.now)) - self._dy("spin0")  # drawn where it was
        self.angle, self.omega, self.kick = 0.0, self._launch_spin(vx, vy, swirl), 0.0
        self.bounce_k = BOUNCE_DAMP * (1.0 + BOUNCE_SPREAD * (2.0 * self.var_rng.random() - 1.0))
        if abs(vx) > 1:
            self.facing = 1 if vx > 0 else -1
        self._enter("fly", self.now)
