"""The overlay's behaviour: a pure state machine (BACKLOG 16, O3).

No Win32, no clock, no randomness of its own: `update(now, pointer, event)`
takes a monotonic time in seconds, where the pointer is, and at most one input
event, and returns what to draw (`Output`: frame name, window top-left in
physical pixels, mirrored or not) and when to be asked again (`wake_ms`).

**Behaviours** (the owner, 2026-11-04, pointing at DesktopGoose and goose: "it
doesnt move"; scope fixed in INBOX 1645, nothing that touches other windows):
stand and blink and look about, walk along the floor of the work area and turn
at its edges, sit and then sleep when nobody has touched it for a while,
notice the pointer coming near (look; hop when it is very close), be picked up
and carried (held) and fall to the floor when let go (then land), wave when
clicked. The floor is the bottom of the work area of the monitor under the
figure; walking on to a monitor with a lower floor is a fall, a higher one a hop.

**Cost.** No fixed tick while standing: the next wake is the next blink, look
or change (3 to 8 s apart). About 30 Hz only while walking, carried or falling.
`dt` is clamped to 100 ms so a stalled process or a resume never teleports it.
Reduced motion: no walking, no noticing, no blinking; it sits at its place, can
still be clicked and carried, and a drop is placed where it is let go.
"""

from __future__ import annotations

import math
import random
from typing import NamedTuple

#: Seconds.
MAX_DT = 0.1
#: One ambient moment (a blink, now and then a look) this far apart: each costs two
#: wakes (start and end), so 60 s of standing is at most 20 (about 14).
AMBIENT_EVERY = (6.0, 11.0)
LOOK_SHARE = 0.25
BLINK_FOR = 0.18
LOOK_FOR = 1.2
STAND_FOR = (3.0, 8.0)
WALK_FOR = (4.0, 12.0)
SIT_FOR = (8.0, 20.0)
WAVE_FOR = 1.4
LAND_FOR = 0.35
HOP_FOR = 0.4
NOTICE_FOR = 1.5
STARTLE_FOR = 0.5
NOTICE_COOLDOWN = 8.0
#: Not touched for this long: sits, then sleeps.
IDLE_SIT = 180.0
IDLE_SLEEP = 360.0

#: Logical pixels (scaled by the monitor's dpi).
WALK_SPEED = 55.0
GRAVITY = 2200.0
NOTICE_NEAR = 120.0
NOTICE_VERY_NEAR = 40.0
#: Physical pixels the pointer may move between press and release for it to be a click.
CLICK_SLOP = 4
#: A resting spot in from the right edge, away from the tray's flyouts.
HOME_INSET = 160.0

TICK_WALK_MS = 33
TICK_FALL_MS = 16
#: Sitting and sleeping look at the pointer this often (a wake each).
POLL_QUIET_MS = 2000
MIN_WAKE_MS = 30

Rect = tuple[int, int, int, int]


class Monitor(NamedTuple):
    """A work area (left, top, right, bottom) in physical pixels and its dpi."""

    area: Rect
    dpi: int = 96


class Output(NamedTuple):
    frame: str
    x: int
    y: int
    flip: bool
    #: Ask again in this many ms, or None: nothing to do until an event.
    wake_ms: int | None
    #: "left" or "right" when a click just finished (the coordinator opens the panel).
    click: str | None = None
    #: True the moment a drop has landed: the place worth saving.
    settled: bool = False


class Engine:
    def __init__(
        self,
        size: tuple[int, int],
        monitors: list[Monitor],
        *,
        home: tuple[int, int] | None = None,
        roam: bool = True,
        reduced: bool = False,
        rng: random.Random | None = None,
        now: float = 0.0,
    ) -> None:
        self.size = size
        self.monitors = list(monitors) or [Monitor((0, 0, 1920, 1040))]
        self.roam = roam
        self.reduced = reduced
        self.rng = rng or random.Random()
        self.now = now
        self.state = "stand"
        self.state_until = 0.0
        self.facing = -1  # the frames face right; -1 is left (mirrored)
        self.vx = self.vy = 0.0
        self.last_active = now
        self.next_ambient = now + self.rng.uniform(*AMBIENT_EVERY)
        self.flash: tuple[str, float] | None = None  # (frame, until): a blink or a look
        self.notice_ready = now
        self.walk_started = now
        self.press: tuple[int, int] | None = None
        self.grab = (0, 0)
        self.carrying = False
        self.hop_from = 0.0
        self.settled_now = False
        self.click_now: str | None = None
        x, y = home if home is not None else self._default_home()
        self.x, self.y = float(x), float(y)
        self._place_on_floor()
        self._enter("stand" if not reduced else "sit", now)

    # --- geometry ------------------------------------------------------------------

    def _default_home(self) -> tuple[int, int]:
        m = self.monitors[0]
        left, _top, right, bottom = m.area
        scale = m.dpi / 96.0
        return int(right - self.size[0] - HOME_INSET * scale), bottom - self.size[1]

    def monitor_at(self, cx: float, cy: float) -> Monitor:
        """The monitor under a point: of those whose width holds it, the one
        nearest vertically; else the nearest of all."""
        def gap(m: Monitor) -> tuple[float, float]:
            left, top, right, bottom = m.area
            dx = max(left - cx, 0, cx - right + 1)
            dy = max(top - cy, 0, cy - bottom)
            return (dx > 0, dx * dx + dy * dy)

        return min(self.monitors, key=gap)

    def current_monitor(self) -> Monitor:
        return self.monitor_at(self.x + self.size[0] / 2, self.y + self.size[1] / 2)

    def floor_y(self, m: Monitor | None = None) -> float:
        return (m or self.current_monitor()).area[3] - self.size[1]

    def _scale(self) -> float:
        return self.current_monitor().dpi / 96.0

    def _place_on_floor(self) -> None:
        m = self.current_monitor()
        left, _t, right, _b = m.area
        self.x = min(max(self.x, left), right - self.size[0])
        self.y = self.floor_y(m)

    def set_monitors(self, monitors: list[Monitor], size: tuple[int, int] | None = None) -> None:
        """Displays or dpi changed: keep the figure on a monitor that is there."""
        self.monitors = list(monitors) or self.monitors
        if size is not None:
            self.size = size
        m = self.current_monitor()
        left, top, right, bottom = m.area
        self.x = min(max(self.x, left), right - self.size[0])
        self.y = min(max(self.y, top), bottom - self.size[1])
        if self.state not in ("held", "fall", "hop"):
            self._place_on_floor()

    def home(self) -> tuple[int, int]:
        return int(round(self.x)), int(round(self.y))

    def resume(self, now: float) -> None:
        """After a suspend or a long stall: no jump, no catching up."""
        self.now = now
        self.next_ambient = now + self.rng.uniform(*AMBIENT_EVERY)
        self.state_until = max(self.state_until, now + 1.0)
        self.last_active = now

    # --- state changes ----------------------------------------------------------------

    def _enter(self, state: str, now: float) -> None:
        self.state = state
        self.flash = None
        if state == "stand":
            self.state_until = now + self.rng.uniform(*STAND_FOR)
        elif state == "walk":
            self.state_until = now + self.rng.uniform(*WALK_FOR)
            self.walk_started = now
            if self.rng.random() < 0.3:
                self.facing = -self.facing
        elif state == "sit":
            self.state_until = now + self.rng.uniform(*SIT_FOR)
        elif state == "wave":
            self.state_until = now + WAVE_FOR
        elif state == "land":
            self.state_until = now + LAND_FOR
        elif state == "hop":
            self.state_until = now + HOP_FOR
        elif state == "notice":
            self.state_until = now + NOTICE_FOR
        elif state == "startle":
            self.state_until = now + STARTLE_FOR
        elif state == "sleep":
            self.state_until = math.inf

    def _touched(self, now: float) -> None:
        self.last_active = now
        if self.state in ("sleep", "sit") and not self.reduced and self.state != "held":
            self._enter("stand", now)

    # --- the one entry point ---------------------------------------------------------------

    def update(self, now: float, pointer: tuple[int, int] | None = None, event: tuple[str, int, int] | None = None) -> Output:
        dt = min(max(now - self.now, 0.0), MAX_DT)
        self.now = now
        self.click_now = None
        self.settled_now = False
        if event is not None:
            self._input(event, now)
        if self.state not in ("held", "pressed"):
            self._advance(now, dt, pointer)
        return self._output(now)

    def _advance(self, now: float, dt: float, pointer: tuple[int, int] | None) -> None:
        handler = getattr(self, f"_do_{self.state}")
        handler(now, dt)
        if pointer is not None and not self.reduced:
            self._notice(now, pointer)

    # --- states -----------------------------------------------------------------------------

    def _ambient(self, now: float) -> None:
        """Blink and look about: only while standing, and only when motion is allowed."""
        if self.reduced:
            return
        if self.flash and now >= self.flash[1]:
            self.flash = None
        if self.flash is None and now >= self.next_ambient:
            look = self.rng.random() < LOOK_SHARE
            self.flash = ("look", now + LOOK_FOR) if look else ("blink", now + BLINK_FOR)
            self.next_ambient = now + self.rng.uniform(*AMBIENT_EVERY)

    def _after_stand(self, now: float) -> None:
        idle = now - self.last_active
        if self.reduced or not self.roam:
            if idle >= IDLE_SIT:
                self._enter("sit", now)
            return
        if idle >= IDLE_SIT:
            self._enter("sit", now)
        elif now >= self.state_until:
            roll = self.rng.random()
            self._enter("walk" if roll < 0.7 else "wave" if roll < 0.78 else "sit" if roll < 0.9 else "stand", now)

    def _do_stand(self, now: float, dt: float) -> None:
        self._ambient(now)
        self._after_stand(now)

    def _do_sit(self, now: float, dt: float) -> None:
        idle = now - self.last_active
        if idle >= IDLE_SLEEP:
            self._enter("sleep", now)
        elif now >= self.state_until and idle < IDLE_SIT and not self.reduced and self.roam:
            self._enter("stand", now)

    def _do_sleep(self, now: float, dt: float) -> None:
        return

    def _do_wave(self, now: float, dt: float) -> None:
        if now >= self.state_until:
            self._enter("stand", now)

    def _do_notice(self, now: float, dt: float) -> None:
        if now >= self.state_until:
            self._enter("stand", now)

    def _do_startle(self, now: float, dt: float) -> None:
        if now >= self.state_until:
            self._enter("stand", now)

    def _do_land(self, now: float, dt: float) -> None:
        if now >= self.state_until:
            self._enter("sit" if self.reduced else "stand", now)

    def _do_hop(self, now: float, dt: float) -> None:
        # A hop up to a higher floor: a short arc, then it stands there.
        t = 1.0 - max(0.0, self.state_until - now) / HOP_FOR
        self.y = self.hop_from + (self.floor_y() - self.hop_from) * min(1.0, t) - math.sin(min(1.0, t) * math.pi) * 14 * self._scale()
        if now >= self.state_until:
            self._place_on_floor()
            self._enter("stand", now)

    def _do_fall(self, now: float, dt: float) -> None:
        scale = self._scale()
        self.vy += GRAVITY * scale * dt
        self.y += self.vy * dt
        self.x += self.vx * dt
        m = self.current_monitor()
        self.x = min(max(self.x, m.area[0]), m.area[2] - self.size[0])
        floor = self.floor_y(m)
        if self.y >= floor:
            self.y, self.vy, self.vx = floor, 0.0, 0.0
            self.settled_now = True
            self._enter("land", now)

    def _do_walk(self, now: float, dt: float) -> None:
        step = WALK_SPEED * self._scale() * dt * self.facing
        nx = self.x + step
        bounds = self._reach(nx)
        if bounds is None:  # the end of the walkable floor: turn around
            self.facing = -self.facing
        else:
            self.x = nx
            floor = self.floor_y(bounds)
            if floor > self.y + 0.5:
                self._start_fall(0.0)
            elif floor < self.y - 0.5:
                self.hop_from = self.y
                self._enter("hop", now)
        if self.state == "walk" and now >= self.state_until:
            self._enter("stand", now)

    def _reach(self, nx: float) -> Monitor | None:
        """The monitor the figure may stand on at `nx`, or None past the last one:
        one whose width holds the figure's middle and whose height overlaps its own."""
        cx = nx + self.size[0] / 2
        if nx < min(m.area[0] for m in self.monitors) or nx + self.size[0] > max(m.area[2] for m in self.monitors):
            return None
        for m in self.monitors:
            left, top, right, bottom = m.area
            if left <= cx < right and top < self.y + self.size[1] and bottom > self.y - 2 * self.size[1]:
                return m
        return None

    def _start_fall(self, vx: float) -> None:
        self.vx, self.vy = vx, 0.0
        self._enter("fall", self.now)

    # --- the pointer ---------------------------------------------------------------------------

    def _notice(self, now: float, pointer: tuple[int, int]) -> None:
        if self.state not in ("stand", "walk", "sit", "sleep") or now < self.notice_ready:
            return
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
            self.grab = (px - self.x, py - self.y)
            self.carrying = False
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
        if self.carrying:
            self.x, self.y = px - self.grab[0], py - self.grab[1]
            self._keep_on_screen()

    def _keep_on_screen(self) -> None:
        m = self.current_monitor()
        left, top, right, bottom = m.area
        self.x = min(max(self.x, left - self.size[0] / 2), right - self.size[0] / 2)
        self.y = min(max(self.y, top), bottom - self.size[1] / 2)

    def _release(self, px: int, py: int, now: float) -> None:
        self.press = None
        self._touched(now)
        if not self.carrying:
            self.click_now = "left"
            self._enter("wave", now) if not self.reduced else self._enter("sit", now)
            return
        self.carrying = False
        self.x = min(max(self.x, self.current_monitor().area[0]), self.current_monitor().area[2] - self.size[0])
        if self.reduced:
            # Placed where it is let go, without a fall.
            self.y = min(max(self.y, self.current_monitor().area[1]), self.current_monitor().area[3] - self.size[1])
            self.settled_now = True
            self._enter("sit", now)
        elif self.y >= self.floor_y() - 0.5:
            self._place_on_floor()
            self.settled_now = True
            self._enter("land", now)
        else:
            self._start_fall(0.0)

    # --- the answer ------------------------------------------------------------------------------------

    def _frame(self, now: float) -> str:
        s = self.state
        if s == "walk":
            return f"walk{int((now - self.walk_started) / 0.125) % 6}"
        if s == "pressed":
            return "stand"
        if s == "notice":
            return "look"
        if s == "startle" or s == "hop":
            return "hop"
        if s == "held":
            return "held"
        if s == "stand":
            return self.flash[0] if self.flash else "stand"
        return s  # sit, sleep, wave, fall, land

    def _wake(self, now: float) -> int | None:
        s = self.state
        if self.reduced:
            return None
        if s in ("walk", "held"):
            return TICK_WALK_MS
        if s in ("fall", "hop"):
            return TICK_FALL_MS
        if s == "pressed":
            return None
        if s in ("sleep", "sit"):
            return POLL_QUIET_MS
        due = [self.state_until] if s != "stand" or (self.roam and not self.reduced) else []
        if s == "stand":
            due += [self.flash[1]] if self.flash else [self.next_ambient]
            due.append(self.last_active + IDLE_SIT)
        soonest = min(due)
        if soonest == math.inf:
            return None
        return max(MIN_WAKE_MS, int(math.ceil((soonest - now) * 1000)))

    def _output(self, now: float) -> Output:
        return Output(
            self._frame(now), int(round(self.x)), int(round(self.y)), self.facing < 0, self._wake(now),
            self.click_now, self.settled_now,
        )
