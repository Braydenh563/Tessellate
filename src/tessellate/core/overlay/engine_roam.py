"""The engine's roam: other apps' window tops as places to stand, ride, climb to, hang from and throw it off (audit-1028 K24, moved whole out of engine.py).

`RoamMixin` holds the methods `Engine` inherits from `set_windows` and `is_riding` through `_leave_perch`: following a window, the eager and the climb choice, the grip and the slip, the wall pull. It reads only `engine_consts` and the sibling behaviour modules."""

from __future__ import annotations

import math
from . import extras
from .engine_consts import (
    CLIMB_EVERY,
    CLIMB_SOON,
    Cover,
    EAGER_EVERY,
    FLING_CARRY,
    FLING_ESCAPE,
    FLING_FLAIL,
    FLING_LIFT,
    FLING_SAFE,
    FLING_SPEED,
    GRIP_BASE,
    GRIP_MOOD,
    HANG_HANDS,
    HOP_OFF_V,
    Monitor,
    PERCH_FOR,
    PERCH_MIN_RISE,
    PERCH_MOVED,
    Perch,
    SCRABBLE_FOR,
    SLIP_REACH,
    SLIP_SPEED,
    THROW_MAX,
    TITLE_BAR,
    WALK_SPEED,
    WALL_REACH,
    WALL_SCRABBLE,
    perch_room,
    stand_x,
)
from typing import Any


class RoamMixin:
    # --- window tops (roam) ------------------------------------------------------------

    def is_riding(self) -> bool:
        """On a window's top, hidden behind one or hanging from one: its movement is read four times a second."""
        return self.perch is not None or self.tuck is not None or self.hang_on is not None

    def set_windows(self, windows: list[Perch], now: float, hangs: list[Perch] | tuple = (), covers: list[Cover] | tuple = ()) -> None:
        """The top edges the runner last read, and the edges only a hang takes hold of. A figure on one follows
        it: it falls (or floats down) when that window is gone or no longer under it, and keeps up when it moves."""
        self.windows = list(windows)
        self.hangs = list(hangs)
        self.covers, self.covers_at = list(covers), now
        if self.tuck is not None:
            self._check_tuck(now)
        self._note_new_edges(now)
        if self.hang_on is not None:
            self._check_hang(now)
        if self.perch is None:
            return
        cur = next((p for p in self.windows if p.key == self.perch.key), None)
        if cur is not None and self.roam_windows and self._window_throw(cur, now):
            return
        self.perch_at = now
        self._follow_window(cur, now)

    def _follow_window(self, cur: Perch | None, now: float) -> None:
        """The scan found the window it stands on: ride it, or leave it when it is gone or no longer under it."""
        if cur is not None and self.roam_windows:
            self._ride_sideways(cur)
        cx = self.x + self.size[0] / 2
        if cur is None or not self.roam_windows or not cur.left <= cx < cur.right:
            # Closed, minimised or dragged from under it: a hop off with a push, now and then a plain step off.
            self._leave_perch(now, hop=cur is None and self.rng.random() < 0.6)
        elif abs(cur.top - self.perch.top) > PERCH_MOVED:
            self._follow_top(cur, now)
        else:
            self.perch = cur

    def _note_new_edges(self, now: float) -> None:
        """A window top (else a title bar) not seen in the last scan: go to it within `CLIMB_SOON` seconds, once
        the stand it is in ends early. The keys seen are kept so one window is new once (INBOX 1692 n)."""
        keys = {p.key for p in self.windows} | {p.key for p in self.hangs}
        fresh = keys - self.seen_keys
        self.seen_keys = keys
        if not fresh or self.perch is not None or not (self.roam and self.roam_windows) or self.reduced:
            return
        kind = "climb" if any(p.key in fresh for p in self._candidates()) else "hang" if any(p.key in fresh for p in self.hangs) else ""
        if not kind:
            return
        self.eager_at, self.eager_kind = max(now + CLIMB_SOON, self.eager_ready), kind
        self.notes.append(f"a new {'window top' if kind == 'climb' else 'title bar'} was seen: going to it at {self.eager_at - now:.0f} s")
        if self.state == "stand":
            self.state_until = min(self.state_until, self.eager_at)

    def _eager(self, now: float) -> str | None:
        """The act for a newly seen edge once its time has come, else None (with the reason logged)."""
        if self.eager_at is None or now < self.eager_at:
            return None
        kind, self.eager_at = self.eager_kind, None
        if self.perch is not None or self.busy or self.reduced or not (self.roam and self.roam_windows):
            self.notes.append(f"eager {kind} skipped: busy, still or already on a window")
            return None
        if kind == "climb" and not self._candidates():
            self.notes.append("eager climb skipped: the window is no longer a place worth the trip")
            return None
        if kind == "hang" and not self.hangs:
            self.notes.append("eager hang skipped: the edge is gone")
            return None
        self.eager_ready = now + EAGER_EVERY
        self.notes.append(f"eager {kind}: chosen")
        if kind == "climb":
            self.climb_ready = 0.0
        else:
            self.big_ready = 0.0
        return kind

    def _follow_top(self, cur: Perch, now: float) -> None:
        """The window under it moved up or down: a floater drifts to the new height, a walker steps up, or
        falls when it went lower."""
        if self.gait == "float":  # it drifts to the new resting height
            self.perch = cur
            self._start_fly(0.0, 0.0)
        elif cur.top > self.perch.top:
            self.perch = None
            self._start_fall(0.0)
        else:
            self.perch = cur
            if self.state in ("stand", "walk", "wave", "notice", "startle", "land"):
                self.hop_from = self.y
                self._enter("hop", now)
            elif self.state not in ("hop", "rise", "leap"):
                self.y = cur.top - self.size[1]  # carried up with it, whatever it was doing

    def _low(self) -> bool:
        """Lying, sitting, napping or at a prop: a body that does not stand ready for the window to move."""
        return self.state in ("sit", "sleep") or (self.state == "act" and (self.act == "lie_down" or extras.props.spec_of(self.act) is not None))

    def _moved_fast(self, cur: Perch, now: float) -> tuple[float, float, float] | None:
        """The window's velocity (px/s) and its speed in logical px/s since the last scan, when that is a move fast enough
        to throw this figure (a resize is not a move), else None."""
        old, dt = self.perch, now - self.perch_at
        if old is None or dt <= 0.0 or self.reduced or self.state in FLING_SAFE:
            return None
        if abs((cur.right - cur.left) - (old.right - old.left)) > PERCH_MOVED:
            return None
        dx, dy = cur.left - old.left, cur.top - old.top
        if max(abs(dx), abs(dy)) <= PERCH_MOVED:
            return None
        vx, vy = dx / dt, dy / dt
        speed = math.hypot(vx, vy) / self._scale()
        return (vx, vy, speed) if speed >= (SLIP_SPEED if self._low() else FLING_SPEED) else None

    def _window_throw(self, cur: Perch, now: float) -> bool:
        """The window under it moved since the last scan: fast enough, it throws the figure off (a fling with a flail,
        or a pop away), a lying or sitting one slips off at a lower speed; slower, it rides (`_ride_sideways`). A resize is
        not a move. True when the figure left the window."""
        moved = self._moved_fast(cur, now)
        if moved is None:
            return False
        vx, vy, speed = moved
        self.perch = self.target = None
        self.legs.append(("jump", self.x, self.x, now))
        escape = self._escape_roll() if speed >= FLING_SPEED else False  # judged on the mood it had, before the shock
        self.mind.feel("startled", now)
        self.flung = "worried" if self.rng.random() < 0.5 else "miffed"
        if speed < FLING_SPEED:  # a body that cannot get up in time: it slides along with the window, or tips straight off
            self.last_fling = "slide" if abs(vx) >= abs(vy) else "tip"
            self._start_fall(0.4 * vx if self.last_fling == "slide" else 0.0)
            return True
        if escape:
            self.last_fling = escape
            self._escape_from(cur, escape, now)
            return True
        self.last_fling = "fall"
        k = self._scale()
        limit = THROW_MAX * k
        if (v := math.hypot(vx, vy)) > limit:
            vx, vy = vx * limit / v, vy * limit / v
        self.grab = (self.size[0] / 2, self.size[1] / 2)  # tossed from the middle: no lever, only the direction turns it
        self._start_fly(vx * FLING_CARRY, min(vy * FLING_CARRY, -FLING_LIFT * k))
        self.flail_until = now + FLING_FLAIL
        return True

    def _escape_roll(self) -> str | bool:
        """Whether the thrown figure pops away rather than falls, and how: a portal or a puff."""
        mood = self.mind.mood(self.now, self.hour)
        if self.rng.random() >= FLING_ESCAPE * (1.4 if mood in ("startled", "sleepy") else 1.0):
            return False
        return "portal" if self.rng.random() < 0.55 else "puff"

    def _escape_from(self, cur: Perch, mode: str, now: float) -> None:
        """Pop to somewhere safe: another window's top, else the floor at the far side of the screen from `cur`."""
        w, h = self.size
        m = self.current_monitor()
        others = [p for p in self._candidates() if p.key != cur.key]
        if others:
            p = self.rng.choice(others)
            self.target = p
            self._start_warp(mode, (stand_x(p, self.x, w), p.top - h), "perch", now)
            return
        gap = 24 * self._scale()
        far_left = (cur.left + cur.right) / 2 > (m.area[0] + m.area[2]) / 2
        self._start_warp(mode, (m.area[0] + gap if far_left else m.area[2] - w - gap, self.ground_y(m)), "evade", now)

    def _ride_sideways(self, cur: Perch) -> None:
        """A window dragged along: the figure keeps its place on it (the same width, moved by more than a
        few px), so it rides rather than being left in the air or dropped (INBOX 1683 g)."""
        old = self.perch
        if old is None or self.state in ("held", "pressed"):
            return
        dx = cur.left - old.left
        if abs(dx) > PERCH_MOVED and abs((cur.right - cur.left) - (old.right - old.left)) <= PERCH_MOVED:
            self.x += dx
            if self.state == "walk" and self.goal is not None:
                self.goal = (self.goal[0] + dx, self.goal[1])

    def _grip(self, p: Perch) -> float:
        """The y the hands take hold at on `p`: a floating window's title-bar bottom, or the edge itself (a bottom edge,
        and a maximised window's top: its tab strip or title bar is the screen's top, INBOX 1721 b, hands about 30 px
        too low with the title-bar offset)."""
        return p.top + (TITLE_BAR * self._scale() if p.kind == "top" else 0.0)

    def _lift(self) -> float:
        """How far the frame's top is above the hands that hold an edge."""
        return self.hang_top * self.size[1]

    def _hold_of(self, p: Perch) -> Perch | None:
        """The window `p` as the runner last read it, when its title bar is still where it
        was and the hands are still over it; else None."""
        cur = next((q for q in self.windows + self.hangs if q.key == p.key), None)
        if cur is None or not self.roam_windows or abs(cur.top - p.top) > PERCH_MOVED:
            return None
        c, w = self.x + self.size[0] / 2, self.size[0]
        if self.state in ("drift", "crouch"):  # on the way: it is the goal that must be over it
            goal = self.goal or (self.pending[0] if self.pending else None)
            c = (goal[0] if goal else self.x) + w / 2
        return cur if cur.left + HANG_HANDS * w <= c <= cur.right - HANG_HANDS * w else None

    def _check_hang(self, now: float) -> None:
        """A hang on a window's title bar (or the trip to it) ends when the window goes,
        moves or no longer lies under the hands: it lets go, or stops short."""
        p = self.hang_on
        assert p is not None
        cur = self._hold_of(p) if self.state in ("hang", "drift", "crouch") else None
        if cur is not None:
            self.hang_on = cur
        elif self.state == "hang":
            self._slip_hang(p, now)
        elif self.state in ("drift", "crouch") and self.then == "hang":
            self.hang_on, self.goal, self.then, self.pending = None, None, "stand", None
            self._enter("stand", now)

    def _grip_chance(self, now: float) -> float:
        """How likely a slipping hold is to grip again: the more rested (and the more cheerful or curious), the likelier."""
        rested = 1.0 - min(1.0, max(0.0, self.mind.needs["rest"]))
        return min(0.95, GRIP_BASE * (0.4 + 0.6 * rested) * GRIP_MOOD.get(self.mind.mood(now, self.hour), 1.0))

    def _slip_hang(self, p: Perch, now: float) -> None:
        """The hands lost the edge: if its window is still there with a top to stand on, a chance to grip again and
        scrabble (`_do_hang` pulls up when it ends), else the drop."""
        self.hang_on = None
        top = next((q for q in self.windows if q.key == p.key), None)
        #: Only where the edge is still in reach: a nudge (half the figure's height) is scrabbled back onto, a window that
        #: moved further leaves nothing under the hands (INBOX 1699, CI 2679d8f; the 1107 scrabble is a 50 px slip).
        stays = top is not None and abs(top.top - p.top) <= SLIP_REACH * self.size[1] * self._scale()
        if stays and top.kind == "top" and top.top - self.size[1] >= self.current_monitor().area[1] and self.rng.random() < self._grip_chance(now):
            self.last_slip, self.pulling = "pull", top
            self.scrabble_t0, self.scrabble_until = now, now + SCRABBLE_FOR
            self.state_until = self.scrabble_until
            return
        self.last_slip = "drop"
        self._let_go()

    def _wall_pull(self, now: float) -> bool:
        """Scrabbling down a screen side: after the scrabble, the nearest window top within reach is pulled up onto
        (the climb the hang slip ends in); with none, False and the slide goes on to the landing."""
        if now - self.wob_t0 < WALL_SCRABBLE:
            return False
        w, h = self.size
        scale = self._scale()
        area = self.current_monitor().area
        hands = self.y + self._dy(self._frame(now)) + 0.35 * h
        best: tuple[float, Perch] | None = None
        for p in self.windows:
            if p.kind != "top" or p.top - h < area[1] or p.right - p.left < w:
                continue
            gap = max(p.left - (self.x + w), self.x - p.right, 0.0)
            far = math.hypot(gap, p.top - hands)
            if far <= WALL_REACH * h * scale and (best is None or far < best[0]):
                best = (far, p)
        if best is None:
            return False
        cur = best[1]
        x = stand_x(cur, self.x, w)
        self.vx = self.vy = self.omega = self.kick = self.angle = self.wob = 0.0
        self.wall, self.wob_kind, self.grounded = 0, None, False
        self.target = cur
        self.legs.append(("climb", self.x, x, now))
        self._rise((x, cur.top - h), "perch", now)
        return True

    def _pull_up(self, now: float) -> None:
        """The scrabble is over: up onto the window's top where it is now, else the drop."""
        p, self.pulling = self.pulling, None
        cur = next((q for q in self.windows if p is not None and q.key == p.key), None)
        w, h = self.size
        if cur is None or cur.top - h < self.current_monitor().area[1]:
            self.last_slip = "drop"
            self._let_go()
            return
        x = stand_x(cur, self.x, w)
        self.target = cur
        self.legs.append(("climb", self.x, x, now))
        self._rise((x, cur.top - h), "perch", now)

    def _arrive_hang(self, now: float, m: Monitor) -> None:
        """At the edge a hang came for: hands on it, or (its window went on the way) a stand."""
        held = self._hold_of(self.hang_on) if self.hang_on is not None else None
        if self.hang_on is not None and held is None:
            self._enter("stand", now)
            return
        self.y = (self._grip(held) if held else m.area[1]) - self._lift()
        self._enter("hang", now)
        self.hang_on = held

    def _can_climb(self, now: float) -> bool:
        return (
            self.roam_windows and self.roam and not self.reduced and not self.busy and self.perch is None
            and now >= self.climb_ready and bool(self._candidates())
        )

    def _candidates(self, drops: Any = None) -> list[Perch]:
        """Window tops on this monitor worth the trip: they fit on screen with the
        figure above them, sit well above the floor, and are wide enough to stand on. The test is the DRAWN
        figure's top (the overlay window has headroom above it), so a window in the upper part of the screen
        counts (INBOX 1692 n). `drops`, when given, counts why a top was refused (counts only, for the log)."""
        m = self.current_monitor()
        left, top, right, _bottom = m.area
        scale = m.dpi / 96.0
        w, h = self.size
        found = []
        for p in self.windows:
            lo, hi = max(p.left, left), min(p.right, right)
            if hi - lo < perch_room(w, scale):
                why = "too narrow"
            elif self._box_at(0.0, p.top - h)[1] < top:
                why = "too close to the top"
            elif p.top - h > self.floor_y(m) - PERCH_MIN_RISE * scale:
                why = "too near the floor"
            else:
                found.append(p)
                continue
            if drops is not None:
                drops[why] += 1
        return found

    def _climb(self, now: float, only: Perch | None = None) -> None:
        """Up to a window's top: a walker standing under it jumps, one beside it climbs its side edge
        onto the top, and a floater glides there. Whatever lies between is crossed on foot (INBOX 1683 f)."""
        cand = self._candidates()
        if not cand:
            self._enter("stand", now)
            return
        p = only if only is not None else self.rng.choice(cand)
        self.climb_ready = now + self.rng.uniform(*CLIMB_EVERY)
        self.target = p
        m = self.current_monitor()
        area, (w, h) = m.area, self.size
        lo, hi = max(p.left, area[0]), min(p.right, area[2]) - w
        top = p.top - h
        if self.gait == "float" or not (abs(self.y - self.floor_y(m)) < 8 * self._scale()):
            x = min(max(self.x, lo), hi)  # straight to the nearest part of its top, over whatever is between (INBOX 1683 f)
            self.modes.append("glide")
            self._go((x, top), "perch", now, plain=True)
            return
        if lo <= self.x <= hi:  # underneath it: straight up
            self.modes.append("jump")
            self._arrive_at("climb", now)
            return
        sides = self._climb_sides(p, area, w)
        if sides:
            sx = min(sides, key=lambda v: abs(v - self.x))
            self.modes.append("climb")
            self._go((sx, self.floor_y(m)), "climbside", now, plain=True)
            return
        x = min(max(self.x, lo), hi)  # a window with no floor beside it (it spans the screen): a puff up, the one way
        self._start_warp("portal" if self.rng.random() < 0.6 else "puff", (x, top), "perch", now)

    def _climb_sides(self, p: Perch, area: tuple, w: float) -> list[float]:
        """Where it could stand beside a window to climb its side (on the screen, with the figure's width clear)."""
        sides = []
        if p.left - w >= area[0]:
            sides.append(p.left - w)
        if p.right <= area[2] - w:
            sides.append(float(p.right))
        return sides

    def _arrive_at(self, then: str, now: float) -> None:
        self.then = then
        self._arrive(now)

    def _target_here(self) -> Perch | None:
        """The window being climbed to, as the last scan has it (None: it is gone)."""
        t = self.target
        return next((p for p in self.windows if t is not None and p.key == t.key), None)

    def _stand_on(self, p: Perch, now: float) -> None:
        self.perch, self.target, self.perch_at = p, None, now
        self.perch_until = now + self.rng.uniform(*PERCH_FOR)
        self.x = stand_x(p, self.x, self.size[0])
        self.y = p.top - self.size[1]
        self._enter("land", now)

    def _leave_perch(self, now: float, hop: bool) -> None:
        """Off a window: a walker hops or falls to the floor, a floater drifts down."""
        self.perch, self.target = None, None
        self.legs.append(("jump", self.x, self.x, now))
        if self.gait == "float":
            self._start_fly(0.0, 0.0)
            return
        scale = self._scale()
        vx = self.facing * WALK_SPEED * scale * (1.6 if hop else 0.5)
        self._start_fall(vx, -HOP_OFF_V * scale if hop else 0.0)
