"""The engine's pointer and input: noticing the cursor, press, drag, throw, release, click and the drop that follows (audit-1028 K24, moved whole out of engine.py).

`InputMixin` holds the methods `Engine` inherits for `_notice` and `_input` and what they call. It reads only `engine_consts` and the sibling behaviour modules."""

from __future__ import annotations

import math
from . import extras
from .engine_consts import (
    CLICK_SLOP,
    DROP_REACH,
    FEET_GRAB,
    HANG_HANDS,
    HANG_REACH,
    NOTICE_COOLDOWN,
    NOTICE_NEAR,
    NOTICE_VERY_NEAR,
    PERCH_THROW,
    Perch,
    THROW_MAX,
    THROW_MIN,
    THROW_WINDOW,
    TITLE_BAR,
    TRAIL_CAP,
    UPSIDE_FRAME,
    stand_x,
)


class InputMixin:
    # --- the pointer ---------------------------------------------------------------------------

    def _notice(self, now: float, pointer: tuple[int, int]) -> None:
        if self.state not in ("stand", "walk", "drift", "sit", "sleep") or now < self.notice_ready:
            return
        if self.nap_until:
            return  # a nap holds: the pointer passing, or the menu that asked for it, is not a poke (INBOX 1683 u)
        if self.trip and self.state in ("walk", "drift"):
            return  # on its way: a look at the pointer would end the trip mid-screen (INBOX 1683 f, trips are common now)
        cx, cy = self.x + self.size[0] / 2, self.y + self.size[1] / 2
        dist = math.hypot(pointer[0] - cx, pointer[1] - cy)
        scale = self._scale()
        if dist <= NOTICE_VERY_NEAR * scale and self.state != "sleep":
            self.notice_ready = now + NOTICE_COOLDOWN
            self._enter("startle", now)
        elif dist <= NOTICE_NEAR * scale:
            self.notice_ready = now + NOTICE_COOLDOWN
            if pointer[0] != cx:
                self.facing = -1 if pointer[0] < cx else 1
            self.last_active = now
            self._enter("notice" if self.state != "sleep" else "stand", now)

    # --- input -------------------------------------------------------------------------------------

    def _input(self, event: tuple[str, int, int], now: float) -> None:
        kind, px, py = event
        if kind == "down":
            self.press = (px, py)
            if self.state == "fly":  # caught on its way back in through the top (`_return_top`): held inside the screen
                self.away_until = None
                self.y = max(self.y, self.current_monitor().area[1])
            frame = self._frame(now)
            drawn_x, drawn_y, _clip = self._display(frame)
            #: Held by where it is drawn: the pointer keeps its place on the figure.
            self.grab = (px - drawn_x, py - drawn_y)
            self.carrying = False
            self.shaken = False
            self.trail = [(now, px, py)]
            self.pre_press = self.state
            self.state = "pressed"
            self._touched(now)
        elif kind == "move" and self.press is not None:
            self._move_while_pressed(px, py)
        elif kind == "up" and self.press is not None:
            self._release(px, py, now)
        elif kind == "right":
            self.click_now = "right"
            self._touched(now)
        elif kind == "move":
            self._touched(now)

    def _move_while_pressed(self, px: int, py: int) -> None:
        assert self.press is not None
        if not self.carrying and math.hypot(px - self.press[0], py - self.press[1]) > CLICK_SLOP:
            self.carrying = True
            self.state = "held"
            self.sink, self.peek_edge, self.goal = 0.0, None, None
            self.perch = self.target = None
            self.upside = False
            self.carry_since = self.now
            if self._by_the_feet():
                self._turn_over(True)
        if self.carrying:
            self.trail.append((self.now, px, py))
            self._trim_trail()
            if self._shake_due() and extras.shake_flips(self.trail, self.now, self._scale()) >= extras.SHAKE_FLIPS:
                self.shaken = True
                self._turn_over(True)
            self.x = px - self.grab[0] - self._flip_dx(self._held_frame(), self.facing < 0)
            self.y = py - self.grab[1] - self._dy("held")
            self._keep_on_screen()

    def _shake_due(self) -> bool:
        """Whether to read the shake now: not once shaken or when reduced, and at most every `SHAKE_EVERY` s (a 1000 Hz
        mouse would otherwise read it a thousand times a second, about 0.3 ms each)."""
        if self.shaken or self.reduced or self.now - self.shake_read_at < extras.SHAKE_EVERY:
            return False
        self.shake_read_at = self.now
        return True

    def _trim_trail(self) -> None:
        """Keep the carried pointer's last `SHAKE_WINDOW` s, whatever the pointer's rate (every raw move arrives), capped
        by count (a 1000 Hz mouse sends 600 samples in that time) so a stalled clock cannot grow it."""
        keep = self.now - extras.SHAKE_WINDOW
        drop = 0
        while drop < len(self.trail) - 1 and self.trail[drop][0] < keep:
            drop += 1
        del self.trail[:drop]
        del self.trail[:-TRAIL_CAP]

    def _held_frame(self) -> str:
        """The picture a carried figure shows: the held pose, or the tumble turned half a circle when upside down."""
        return UPSIDE_FRAME if self.upside else "held"

    def _by_the_feet(self) -> bool:
        """Whether the press that began this carry was on the figure's feet (the lowest `1 - FEET_GRAB` of its body)."""
        _l, top, _r, bottom = self._box("stand", False)
        return self.grab[1] >= top + FEET_GRAB * (bottom - top)

    def _turn_over(self, on: bool) -> None:
        """Carry it upside down (or upright again). The turned picture is the held one rotated half a circle about the
        window's middle, so the point the pointer holds moves to the opposite corner of the window with it."""
        if on == self.upside or (on and self.reduced):
            return
        self.upside = on
        w, h = self.size
        self.grab = (w - self.grab[0], h - self.grab[1])

    def _ride_limits(self, frame: str) -> tuple[float, float, float, float]:
        """Where the engine's x and y may go (x low, x high, y low, y high) so the drawn box of
        `frame` stays inside the work area on every side that is a real screen edge (INBOX 1670:
        "cut off a little on the ride"); a side another monitor adjoins lets it through, as far as
        its middle."""
        m = self.current_monitor()
        left, top, right, bottom = m.area
        bl, bt, br, bb = self._ride_box(frame)
        w, h = self.size
        return (
            left - bl if self._open_side(m, "left") else left - w / 2,
            right - br if self._open_side(m, "right") else right - w / 2,
            top - bt if self._open_side(m, "top") else top,
            bottom - bb if self._open_side(m, "bottom") else bottom - h / 2,
        )

    def _keep_on_screen(self) -> None:
        x0, x1, y0, y1 = self._ride_limits("held")
        self.x = min(max(self.x, x0), x1)
        self.y = min(max(self.y, y0), y1)

    def _release(self, px: int, py: int, now: float) -> None:
        self.press = None
        self._touched(now)
        if not self.carrying:
            self._clicked(now)
            return
        self.carrying = False
        self.placed = True
        self.upside = False
        if self.shaken:
            self.shaken, self.dizzy_owed = False, now
        self.mind.feel("startled", now)
        m = self.current_monitor()
        x0, x1, _y0, _y1 = self._ride_limits("held")
        self.x = min(max(self.x, max(x0, m.area[0] - self._ride_box("held")[0])), min(x1, m.area[2] - self._ride_box("held")[2]))
        velocity = None if self.reduced else self._throw_velocity(now, px, py)
        speed = 0.0 if velocity is None else math.hypot(*velocity)
        if speed < PERCH_THROW * THROW_MIN * self._scale():
            if self._drop_on_top(now):
                return
            if self.missed_top:
                self.missed_owed = now
        if velocity is not None:  # a throw is a throw: only a release that is not one takes hold near an edge
            self._start_fly(*velocity, self._swirl(now, px, py))
        elif not self._grab_edge(now):
            self._drop(now)

    def _drop_on_top(self, now: float) -> bool:
        """Let go with the feet near a window's top, over it: it settles onto that top and stands there (INBOX 1696 b).
        The runner reads the windows afresh at the release, so the edge is where the window is now. Each release over
        or near an edge leaves a note saying why it did or did not stay."""
        if self.reduced or not (self.roam and self.roam_windows):
            return False
        w, h = self.size
        best = self._top_in_reach()
        if best is None:
            return False
        p = best[1]
        x = stand_x(p, self.x, w)
        self.notes.append(f"let go over a window top ({best[0]:.0f} px from the feet): standing on it")
        self.target, self.hang_on, self.placed = p, None, True
        self.legs.append(("drop", self.x, x, now))
        self._rise((x, p.top - h), "perch", now, drawn_from=self.y + self._dy("held"))
        return True

    def _top_in_reach(self) -> tuple[float, Perch] | None:
        """The window top nearest the feet within `DROP_REACH` under the figure's middle, with the gap (positive: the
        feet above it); a note for each top near but out of reach, or for none under the figure at all."""
        w, h = self.size
        feet, centre, m = self.y + h, self.x + w / 2, self.current_monitor()
        self.missed_top = False
        above, below = DROP_REACH[0] * h, DROP_REACH[1] * h
        under = [(p.top - feet, p) for p in self.windows if p.kind == "top" and p.top >= m.area[1] and p.left <= centre < p.right]
        reach = [(gap, p) for gap, p in under if -below <= gap <= above]
        self._note_out_of_reach([gap for gap, _p in under if not -below <= gap <= above], above, below)
        if not reach and not any(p.kind == "top" and p.left <= centre < p.right for p in self.windows):
            self.notes.append(f"let go with no window top under the figure ({len(self.windows)} standable in the scan)")
        return min(reach, key=lambda gp: abs(gp[0])) if reach else None

    def _note_out_of_reach(self, gaps: list[float], above: float, below: float) -> None:
        for gap in gaps:
            if abs(gap) < 2 * self.size[1]:
                self.missed_top = True
                self.notes.append(f"let go {abs(gap):.0f} px {'above' if gap > 0 else 'below'} a window top: out of reach (within {above:.0f} above or {below:.0f} below)")

    def _swirl(self, now: float, px: int, py: int) -> float:
        """How much the pointer's path curled over the throw window, -1 to 1 (clockwise on screen positive):
        the mean of the turn between each pair of steps. A straight flick is 0."""
        pts = [(x, y) for t, x, y in self.trail if t >= now - THROW_WINDOW] + [(px, py)]
        turns = []
        for a, b, c in zip(pts, pts[1:], pts[2:]):
            d1, d2 = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
            norm = math.hypot(*d1) * math.hypot(*d2)
            if norm > 1e-6:
                turns.append((d1[0] * d2[1] - d1[1] * d2[0]) / norm)
        return max(-1.0, min(1.0, 3.0 * sum(turns) / len(turns))) if turns else 0.0

    def _grab_edge(self, now: float) -> bool:
        """Let go with the head near the work area's top, or near the bottom edge of a window's
        title bar under the middle of the figure: it takes hold and hangs there (INBOX 1670: "I
        cant drag the companion to hang on another section of the top of my screen, it always
        falls"). The nearer edge wins; anywhere else it is dropped or thrown as before."""
        if self.reduced or not self.roam:
            return False
        m = self.current_monitor()
        top, k, w = m.area[1], self._scale(), self.size[0]
        reach = HANG_REACH * self.size[1]
        head = self.y + self._ride_box("held")[1]
        centre = self.x + w / 2
        best: tuple[float, Perch | None, float] | None = None
        if self._open_side(m, "top") and head - top <= reach:
            best = (head - top, None, top)
        if self.roam_windows:
            for p in self.windows:
                edge = p.top + TITLE_BAR * k
                near = abs(head - edge)
                if (
                    p.top >= top and near <= reach and p.left + HANG_HANDS * w <= centre <= p.right - HANG_HANDS * w
                    and (best is None or near < best[0])
                ):
                    best = (near, p, edge)
        if best is None:
            return False
        _gap, hold, edge = best
        self._rise((self.x, edge - self._lift()), "hang", now, drawn_from=self.y + self._dy("held"))
        self.hang_on = hold
        self.home_x, self.placed = self.x, False
        return True

    def _clicked(self, now: float) -> None:
        """A press that was never a drag: open a card, bring a peeker out, keep a hanger hanging, or wave."""
        reply = "sit" if self.reduced else "wave"
        if self.pre_press == "card" and self.card is not None:
            self.card_clicked = self.card  # the reminder opens; the card is set down
            self._put_card_down(now)
            self._enter(reply, now)
            return
        self.click_now = "left"
        if self.pre_press in ("peek", "emerge") and self.peek_edge and not self.reduced:
            self._enter("emerge", now)  # a click brings a peeking figure out
        elif self.pre_press == "hang":
            # INBOX 1690 c: the click opens the menu; the hanger keeps its grip
            # (letting go here left a floater drifting mid-air beside the menu). It still answers the pat (1721 a).
            self.state = "hang"
            self.ex.fire("pat", now)
        else:
            self.mind.feel("happy", now)
            if now - self.last_click < 4.0 and not self.reduced:  # a second pat: it purrs
                self._start_act("sway", now)
            else:
                self._enter(reply, now)
            self.last_click = now

    def _drop(self, now: float) -> None:
        """Let go without a throw: sit at once when reduced, land when on the floor, else fall."""
        if self.reduced:
            # On the floor at once, without a fall: it would otherwise hang
            # where it was let go, in mid-air, with nothing to bring it down.
            self._place_on_floor()
            self.settled_now = True
            self._enter("sit", now)
        elif self.y >= self.ground_y() - 0.5 and self.gait == "walk":
            self._place_on_floor()
            self.settled_now = True
            self._enter("land", now)
        else:
            self._start_fall(0.0)

    def _throw_velocity(self, now: float, px: int, py: int) -> tuple[float, float] | None:
        """Pointer velocity over the last THROW_WINDOW seconds (physical px per second),
        clamped; None when it is slower than THROW_MIN (a plain drop)."""
        samples = [p for p in self.trail if p[0] >= now - THROW_WINDOW]
        samples.append((now, px, py))
        t0, x0, y0 = samples[0]
        span = now - t0
        if len(samples) < 2 or span < 0.02:
            return None
        vx, vy = (px - x0) / span, (py - y0) / span
        scale = self._scale()
        speed = math.hypot(vx, vy)
        if speed < THROW_MIN * scale:
            return None
        limit = THROW_MAX * scale
        if speed > limit:
            vx, vy = vx * limit / speed, vy * limit / speed
        return vx, vy
