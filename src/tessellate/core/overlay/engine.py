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
**Throw, float, hang, peek** (owner, 2026-11-04, "I cant throw it, it just drops",
"atlas should float like a wind spirit", "can it hang from the top or hide
below the taskbar"). While carried the last 100 ms of pointer moves are kept; a
release faster than `THROW_MIN` leaves with that velocity (`fly`: gravity for a
walker, air drag and a pull to the hover height for a floater; bounces off the
outer walls with damping and a short startle "bonk"; the ceiling is a hang).
`gait` is "walk" (floors, hops, falls) or "float" (Atlas: hovers 24 to 80
logical px above the floor and drifts in curves over the whole work area).
Now and then, at most one "big" act every couple of minutes (`ACTS`, one
table), it hangs from the top edge (`hang`), or sinks behind the work area's
bottom or an outer side edge and peeks (`peek`; the engine reports `Output.clip`
so the figure's hidden rows are clear and take no clicks). A click on a peeking
figure brings it out. Nothing but standing happens while `quiet` (typing,
presenting). All of it is states in this one machine.

**Roam and carry** (owner, 2026-11-04: "does it only walk along the top of my
taskbar", "carry a reminder"). Given the top edges of other apps' windows
(`set_windows`; read by the runner, never moved or touched) a walker now and
then walks to one, leaps up onto it, walks along it and hops or falls off at its
end, or when that window moves, minimises or closes; a floater (Atlas) floats
down to rest on it. At most one climb every few minutes (`CLIMB_EVERY`), never
while `quiet`, reduced or asleep. `bring_card(token)` makes it fetch a reminder:
it goes to the floor beside the pointer's monitor holding a card (`card0` and
`card1`), waits `CARD_FOR`, and a click on it reports `Output.card` (the token);
ignored, it sets the card down. One at a time, the rest queue.

Reduced motion: no walking, no noticing, no blinking; it sits at its place, can
still be clicked and carried, and a drop lands on the floor of its monitor at
once (a figure that cannot fall must not hang in mid-air; owner, 2026-11-04).
"""

from __future__ import annotations

import math
import random
from typing import Any, NamedTuple

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
#: Not touched for this long: sits, then sleeps. Ten and twenty minutes (the owner's
#: open call, taken): it keeps doing small acts while the person is away from the
#: keyboard, since the big acts (hang, peek) come two to four minutes apart.
IDLE_SIT = 600.0
IDLE_SLEEP = 1200.0
#: The idle cycle (`idle0` to `idle11`, one tail beat and one breath): a standing
#: figure draws these at `IDLE_FPS` so the parts move; reduced or typing-quiet it
#: is the one `stand` frame and costs no wake.
IDLE_FRAMES = 12
IDLE_FPS = 8.0

#: Logical pixels (scaled by the monitor's dpi).
WALK_SPEED = 55.0
GRAVITY = 2200.0
NOTICE_NEAR = 120.0
NOTICE_VERY_NEAR = 40.0
#: Physical pixels the pointer may move between press and release for it to be a click.
CLICK_SLOP = 4
#: A resting spot in from the right edge, away from the tray's flyouts.
HOME_INSET = 160.0

#: How long each state holds: a range (random) or a fixed time; the others set theirs in `_on_<state>`.
HOLD_RANGES = {"stand": STAND_FOR, "sit": SIT_FOR}
HOLD_FIXED = {"wave": WAVE_FOR, "land": LAND_FOR, "hop": HOP_FOR, "notice": NOTICE_FOR, "startle": STARTLE_FOR}

#: States drawn with a frame of another name.
FRAME_OF = {"pressed": "stand", "leap": "hop", "notice": "look", "startle": "hop", "hop": "hop", "held": "held", "hang": "hang", "emerge": "stand"}

#: Throw: the pointer's last THROW_WINDOW seconds decide the velocity. Logical
#: px per second (scaled by dpi): slower than THROW_MIN is a plain drop.
THROW_WINDOW = 0.1
THROW_MIN = 350.0
THROW_MAX = 3200.0
BOUNCE_DAMP = 0.55
BONK_FOR = 0.3
#: Radians per second of spin at full throw speed, and the angles the frames come in.
SPIN_RATE = 9.0
SPIN_STEPS = 8
#: A floater: hover height range above the floor, speed, turn rate, air drag,
#: and the pull back to its hover height (per second squared per pixel).
HOVER = (24.0, 80.0)
FLOAT_SPEED = 130.0
FLOAT_TURN = 1.8
FLOAT_DRAG = 3.0
FLOAT_PULL = 3.0
REACHED = 6.0
#: A floater travels (INBOX 1658: "it just floats there"): each leg is at least this share
#: of the work area's width, it rests only a moment between legs, and while it is
#: out it bobs (up to BOB logical px) and sways (FLOAT_SWAY), redrawn every BOB_TICK s.
FLOAT_LEG = (0.35, 0.8)
FLOAT_STAND_FOR = (0.8, 2.0)
FLOAT_MOVE_WEIGHT = 150
BOB = 7.0
BOB_HZ = 0.55
FLOAT_SWAY = 5.0
FLOAT_SWAY_HZ = 0.37
BOB_TICK = 0.05
#: Hang from the top edge, sway, and the climb up to it.
HANG_FOR = (8.0, 16.0)
SWAY = 6.0
SWAY_HZ = 0.4
#: What a hang takes hold of (INBOX 1660: "it thinks its hanging but its just ... hanging in
#: mid air"): the top of the work area, or the bottom edge of a window's title bar
#: (`TITLE_BAR` logical px under its top). The hands are `hang_top` of the frame's height
#: below the frame's top (measured from the hang frame at load), so the frame is lifted by
#: that much; the hands need `HANG_HANDS` of the figure's width either side of its centre
#: to be over the window's edge.
TITLE_BAR = 32.0
HANG_HANDS = 0.3
RISE_FOR = 0.9
#: Peek: the figure sinks behind an edge. Hidden share of the figure (0 shown, 1 gone).
PEEK_HEAD = 0.65
PEEK_SIDE = 0.55
#: (seconds, depth): 0 out, 1 the head shows, 2 gone. Sink, look about, duck,
#: wait, come up, look, out. Depth 1 is `PEEK_HEAD` (or `PEEK_SIDE`) hidden, 2 is all.
PEEK_PLAN = ((0.0, 0.0), (0.8, 1.0), (3.0, 1.0), (3.4, 2.0), (5.0, 2.0), (5.5, 1.0), (7.0, 1.0), (7.8, 0.0))
EMERGE_FOR = 0.4
#: Big acts (hang, peek) are at least this far apart (seconds): calm, minutes.
BIG_EVERY = (120.0, 240.0)
#: The first one comes sooner, inside the minutes before it sits down for good.
BIG_FIRST = (60.0, 150.0)
#: While the person is busy (typing, presenting) it asks again this often.
QUIET_RECHECK = 5.0
REST_FOR = (8.0, 20.0)
#: The ambient choice, one table: act -> (weight, big). `sleep` needs SLEEP_AFTER idle.
ACTS = {
    "move": (55, False), "rest": (12, False), "wave": (6, False), "sit": (10, False),
    "stand": (6, False), "sleep": (2, False), "hang": (5, True), "peek": (6, True),
    "climb": (8, False),
}
SLEEP_AFTER = 60.0

#: Window tops (roam): the first climb comes after `CLIMB_FIRST`, then one every
#: `CLIMB_EVERY` seconds at most; it stays on one window `PERCH_FOR`; a top must be
#: `PERCH_MIN_RISE` logical px above the floor to be worth the leap; a window top
#: that moves more than `PERCH_MOVED` physical px has moved.
CLIMB_FIRST = 40.0
CLIMB_EVERY = (180.0, 420.0)
PERCH_FOR = (25.0, 70.0)
PERCH_MIN_RISE = 48.0
PERCH_MOVED = 3.0
LEAP_BASE = 0.45
LEAP_SPEED = 1800.0
#: Hopping down off a window: the push (logical px per second).
HOP_OFF_V = 380.0
#: A reminder's card: waits this long (seconds); the pair of frames swaps this often.
CARD_FOR = 120.0
CARD_SWAP = 0.9
CARD_WALK_SWAP = 0.25
CARD_STAND = ("stand", "walk", "drift", "sit", "sleep", "land", "wave", "notice", "startle", "card")

TICK_WALK_MS = 33
TICK_FALL_MS = 16
#: Sitting and sleeping look at the pointer this often (a wake each).
POLL_QUIET_MS = 2000
MIN_WAKE_MS = 30

Rect = tuple[int, int, int, int]


class Perch(NamedTuple):
    """The top edge of another app's window: a surface to stand on (physical px)."""

    key: int
    left: int
    top: int
    right: int


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
    #: Visible part of the frame (left, top, right, bottom) in its own pixels,
    #: or None for all of it. The rest is drawn clear: it takes no clicks.
    clip: tuple[int, int, int, int] | None = None
    #: The token of the reminder whose card was just clicked (None otherwise).
    card: Any = None


def _adjoins(a: Rect, b: Rect, side: str) -> bool:
    """Whether rect `b` touches rect `a` along `a`'s `side` (within a pixel)."""
    al, at, ar, ab = a
    bl, bt, br, bb = b
    across_y, across_x = bt < ab and bb > at, bl < ar and br > al
    return {
        "left": abs(br - al) <= 1 and across_y, "right": abs(bl - ar) <= 1 and across_y,
        "top": abs(bb - at) <= 1 and across_x, "bottom": abs(bt - ab) <= 1 and across_x,
    }[side]


class Engine:
    def __init__(
        self,
        size: tuple[int, int],
        monitors: list[Monitor],
        *,
        home: tuple[int, int] | None = None,
        roam: bool = True,
        reduced: bool = False,
        roam_windows: bool = True,
        gait: str = "walk",
        hang_top: float = 0.0,
        idle_frames: int = IDLE_FRAMES,
        rng: random.Random | None = None,
        now: float = 0.0,
    ) -> None:
        self.size = size
        self.idle_frames = max(0, int(idle_frames))
        self.monitors = list(monitors) or [Monitor((0, 0, 1920, 1040))]
        self.roam = roam
        self.reduced = reduced
        self.rng = rng or random.Random()
        self.gait = "float" if gait == "float" else "walk"
        #: The share of the hang frame's height that is clear above the hands.
        self.hang_top = min(max(float(hang_top), 0.0), 0.5)
        #: The window whose title bar a hang (or the trip to one) takes hold of.
        self.hang_on: Perch | None = None
        #: True while the person is typing or presenting: it only stands.
        self.quiet = False
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
        self.trail: list[tuple[float, int, int]] = []
        self.pre_press = "stand"
        self.bonk_until = 0.0
        self.angle = 0.0
        self.spin_dir = 1
        self.heading = 0.0
        self.goal: tuple[float, float] | None = None
        self.then = "stand"
        self.trip = False
        self.hover = self.rng.uniform(*HOVER)
        self.big_ready = now + self.rng.uniform(*BIG_FIRST)
        self.roam_windows = roam_windows
        self.windows: list[Perch] = []
        self.perch: Perch | None = None
        self.target: Perch | None = None
        self.perch_until = 0.0
        self.climb_ready = now + CLIMB_FIRST
        self.pointer: tuple[int, int] | None = None
        self.card: Any = None
        self.card_queue: list[Any] = []
        self.card_settled = False
        self.card_until = 0.0
        self.card_clicked: Any = None
        self.sink = 0.0
        self.sink_max = PEEK_HEAD
        self.peek_edge: str | None = None
        self.peek_started = now
        self.peek_turned = False
        self.phase_from = (0.0, 0.0)
        self.phase_started = now
        self.phase_to = (0.0, 0.0)
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
        """What it stands on: a window's top while it is on one, else the monitor's floor."""
        if self.perch is not None:
            return self.perch.top - self.size[1]
        return (m or self.current_monitor()).area[3] - self.size[1]

    def _scale(self) -> float:
        return self.current_monitor().dpi / 96.0

    def ground_y(self, m: Monitor | None = None) -> float:
        """Where it rests: the floor for a walker, its hover height above it for a floater."""
        m = m or self.current_monitor()
        hover = self.hover * m.dpi / 96.0 if self.gait == "float" and self.perch is None else 0.0
        return self.floor_y(m) - hover

    def _place_on_floor(self) -> None:
        m = self.current_monitor()
        left, _t, right, _b = m.area
        self.x = min(max(self.x, left), right - self.size[0])
        self.y = self.ground_y(m)

    def _open_side(self, m: Monitor, side: str) -> bool:
        """True when no other monitor adjoins this side of `m`: a real screen edge."""
        return not any(n is not m and n.area != m.area and _adjoins(m.area, n.area, side) for n in self.monitors)

    def set_monitors(self, monitors: list[Monitor], size: tuple[int, int] | None = None) -> None:
        """Displays or dpi changed: keep the figure on a monitor that is there."""
        self.monitors = list(monitors) or self.monitors
        if size is not None:
            self.size = size
        m = self.current_monitor()
        left, top, right, bottom = m.area
        self.x = min(max(self.x, left), right - self.size[0])
        top -= self._lift() if self.state in ("hang", "rise") else 0.0
        self.y = min(max(self.y, top), bottom - self.size[1])
        moving = ("held", "fall", "hop", "fly", "hang", "rise", "peek", "emerge", "leap", "drift", "walk")
        if self.gait == "float" and self.state in moving:
            self.y = min(max(self.y, top), self.floor_y(m))
        elif self.state not in moving[:9]:
            self._place_on_floor()

    def home(self) -> tuple[int, int]:
        return int(round(self.x)), int(round(self.y))

    def resume(self, now: float) -> None:
        """After a suspend or a long stall: no jump, no catching up."""
        self.now = now
        self.next_ambient = now + self.rng.uniform(*AMBIENT_EVERY)
        self.state_until = max(self.state_until, now + 1.0)
        self.last_active = now
        if self.state in ("peek", "emerge"):
            self._enter("stand", now)

    # --- state changes ----------------------------------------------------------------

    def _enter(self, state: str, now: float) -> None:
        self.state = state
        self.flash = None
        if state not in ("hang", "drift", "rise"):
            self.hang_on = None
        if state not in ("peek", "emerge"):
            self.sink, self.peek_edge = 0.0, None
        if state not in ("walk", "drift"):
            self.goal = None
        self.trip = False
        if state == "stand" and self.gait == "float" and self.perch is None:
            self.state_until = now + self.rng.uniform(*FLOAT_STAND_FOR)
        elif state in HOLD_RANGES:
            self.state_until = now + self.rng.uniform(*HOLD_RANGES[state])
        elif state in HOLD_FIXED:
            self.state_until = now + HOLD_FIXED[state]
        elif state in ("sleep", "fly"):
            self.state_until = math.inf
        else:
            getattr(self, f"_on_{state}", lambda _now: None)(now)

    def _on_walk(self, now: float) -> None:
        self.state_until = now + self.rng.uniform(*WALK_FOR)
        self.walk_started = now
        if self.rng.random() < 0.3:
            self.facing = -self.facing

    def _on_drift(self, now: float) -> None:
        self.state_until = now + self.rng.uniform(*WALK_FOR)
        self.walk_started = now
        if self.goal is None:
            self.heading = self.rng.uniform(0, 2 * math.pi)

    def _on_hang(self, now: float) -> None:
        self.state_until = now + self.rng.uniform(*HANG_FOR)
        self.phase_started = now

    def _on_rise(self, now: float) -> None:
        self.state_until = now + RISE_FOR
        self.phase_from = (self.x, self.y)
        self.phase_started = now

    def _on_peek(self, now: float) -> None:
        self.peek_started, self.peek_turned = now, False
        self.state_until = now + PEEK_PLAN[-1][0]

    def _on_leap(self, now: float) -> None:
        assert self.target is not None
        height = max(0.0, self.y - (self.target.top - self.size[1]))
        self.phase_from = (self.x, self.y)
        self.phase_to = (self.x, self.target.top - self.size[1])
        self.state_until = now + LEAP_BASE + height / (LEAP_SPEED * self._scale())
        self.phase_started = now

    def _on_card(self, now: float) -> None:
        self.state_until = self.card_until

    def _on_emerge(self, now: float) -> None:
        self.state_until = now + EMERGE_FOR
        self.phase_from, self.phase_started = (self.sink, 0.0), now

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
        self.card_clicked = None
        if pointer is not None:
            self.pointer = pointer
        if event is not None:
            self._input(event, now)
        if self.state not in ("held", "pressed"):
            self._advance(now, dt, pointer)
        return self._output(now)

    def _advance(self, now: float, dt: float, pointer: tuple[int, int] | None) -> None:
        handler = getattr(self, f"_do_{self.state}")
        handler(now, dt)
        if self.card is not None or self.card_queue:
            self._card_step(now)
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
        if self.card is not None and self.card_settled:  # carried off its place: it waits again
            self._enter("card", now) if now < self.card_until else self._put_card_down(now)
            return
        if self.reduced or not self.roam:
            if idle >= IDLE_SIT:
                self._enter("sit", now)
            return
        if idle >= IDLE_SIT:
            if self.perch is not None:  # never sleeps on a window
                self._leave_perch(now, hop=False)
            else:
                self._enter("sit", now)
        elif self.perch is not None and now >= self.perch_until and self.gait == "walk":
            self._leave_perch(now, hop=self.rng.random() < 0.5)
        elif now >= self.state_until:
            if self.quiet:
                self.state_until = now + QUIET_RECHECK
                return
            self._perform(self._pick_act(now, idle), now)

    def _pick_act(self, now: float, idle: float) -> str:
        """One weighted choice from `ACTS`: a big act only when `big_ready` has passed,
        sleep only after a while untouched."""
        up = self.perch is not None
        climb = self._can_climb(now)
        table = [
            (act, FLOAT_MOVE_WEIGHT if act == "move" and self.gait == "float" else w) for act, (w, big) in ACTS.items()
            if not (big and (now < self.big_ready or up)) and not (act == "sleep" and (idle < SLEEP_AFTER or up))
            and not (act == "climb" and not climb)
        ]
        roll = self.rng.random() * sum(w for _a, w in table)
        for act, w in table:
            roll -= w
            if roll < 0:
                return act
        return "stand"

    def _perform(self, act: str, now: float) -> None:
        if self.perch is not None and self.gait == "float":
            self.perch = None  # a floater rests on a window, it does not stay on it
        if act in ("hang", "peek"):
            self.big_ready = now + self.rng.uniform(*BIG_EVERY)
        if act == "move":
            self._enter("drift" if self.gait == "float" else "walk", now)
        elif act == "rest":
            self._rest(now)
        elif act == "hang":
            self._hang(now)
        elif act == "peek":
            self._peek(now)
        elif act == "climb":
            self._climb(now)
        else:  # wave, sit, stand, sleep
            self._enter(act, now)

    # --- window tops (roam) ------------------------------------------------------------

    def set_windows(self, windows: list[Perch], now: float) -> None:
        """The top edges the runner last read. A figure on one follows it: it falls
        (or floats down) when that window is gone or no longer under it, and
        keeps up when it moves."""
        self.windows = list(windows)
        if self.hang_on is not None:
            self._check_hang(now)
        if self.perch is None:
            return
        cur = next((p for p in self.windows if p.key == self.perch.key), None)
        cx = self.x + self.size[0] / 2
        if cur is None or not self.roam_windows or not cur.left <= cx < cur.right:
            self._leave_perch(now, hop=False)
        elif abs(cur.top - self.perch.top) > PERCH_MOVED:
            lower = cur.top > self.perch.top
            if self.gait == "float":  # it drifts to the new resting height
                self.perch = cur
                self._start_fly(0.0, 0.0)
            elif lower:
                self.perch = None
                self._start_fall(0.0)
            else:
                self.perch = cur
                if self.state in ("stand", "walk", "wave", "notice", "startle", "land"):
                    self.hop_from = self.y
                    self._enter("hop", now)
        else:
            self.perch = cur

    def _lift(self) -> float:
        """How far the frame's top is above the hands that hold an edge."""
        return self.hang_top * self.size[1]

    def _hold_of(self, p: Perch) -> Perch | None:
        """The window `p` as the runner last read it, when its title bar is still where it
        was and the hands are still over it; else None."""
        cur = next((q for q in self.windows if q.key == p.key), None)
        if cur is None or not self.roam_windows or abs(cur.top - p.top) > PERCH_MOVED:
            return None
        c, w = self.x + self.size[0] / 2, self.size[0]
        if self.state == "drift":  # on the way: it is the goal that must be over it
            c = (self.goal[0] if self.goal else self.x) + w / 2
        return cur if cur.left + HANG_HANDS * w <= c <= cur.right - HANG_HANDS * w else None

    def _check_hang(self, now: float) -> None:
        """A hang on a window's title bar (or the trip to it) ends when the window goes,
        moves or no longer lies under the hands: it lets go, or stops short."""
        p = self.hang_on
        assert p is not None
        cur = self._hold_of(p) if self.state in ("hang", "drift") else None
        if cur is not None:
            self.hang_on = cur
        elif self.state == "hang":
            self.hang_on = None
            self._let_go()
        elif self.state == "drift" and self.then == "hang":
            self.hang_on, self.goal, self.then = None, None, "stand"
            self._enter("stand", now)

    def _arrive_hang(self, now: float, m: Monitor) -> None:
        """At the edge a hang came for: hands on it, or (its window went on the way) a stand."""
        held = self._hold_of(self.hang_on) if self.hang_on is not None else None
        if self.hang_on is not None and held is None:
            self._enter("stand", now)
            return
        self.y = (held.top + TITLE_BAR * self._scale() if held else m.area[1]) - self._lift()
        self._enter("hang", now)
        self.hang_on = held

    def _can_climb(self, now: float) -> bool:
        return (
            self.roam_windows and self.roam and not self.reduced and not self.quiet and self.perch is None
            and now >= self.climb_ready and bool(self._candidates())
        )

    def _candidates(self) -> list[Perch]:
        """Window tops on this monitor worth the trip: they fit on screen with the
        figure above them, sit well above the floor, and are wide enough to stand on."""
        m = self.current_monitor()
        left, top, right, _bottom = m.area
        scale = m.dpi / 96.0
        w, h = self.size
        found = []
        for p in self.windows:
            lo, hi = max(p.left, left), min(p.right, right)
            if hi - lo < w + 20 * scale or p.top - h < top:
                continue
            if p.top - h > self.floor_y(m) - PERCH_MIN_RISE * scale:
                continue
            found.append(p)
        return found

    def _climb(self, now: float) -> None:
        cand = self._candidates()
        if not cand:
            self._enter("stand", now)
            return
        p = self.rng.choice(cand)
        self.climb_ready = now + self.rng.uniform(*CLIMB_EVERY)
        self.target = p
        m = self.current_monitor()
        lo, hi = max(p.left, m.area[0]), min(p.right, m.area[2])
        x = self.rng.uniform(lo, hi - self.size[0])
        if self.gait == "float":
            self._go((x, p.top - self.size[1]), "perch", now)
        else:
            self._go((x, self.floor_y(m)), "climb", now)

    def _target_here(self) -> Perch | None:
        """The window being climbed to, as the last scan has it (None: it is gone)."""
        t = self.target
        return next((p for p in self.windows if t is not None and p.key == t.key), None)

    def _stand_on(self, p: Perch, now: float) -> None:
        self.perch, self.target = p, None
        self.perch_until = now + self.rng.uniform(*PERCH_FOR)
        self.x = min(max(self.x, p.left), p.right - self.size[0])
        self.y = p.top - self.size[1]
        self._enter("land", now)

    def _leave_perch(self, now: float, hop: bool) -> None:
        """Off a window: a walker hops or falls to the floor, a floater drifts down."""
        self.perch, self.target = None, None
        if self.gait == "float":
            self._start_fly(0.0, 0.0)
            return
        scale = self._scale()
        vx = self.facing * WALK_SPEED * scale * (1.6 if hop else 0.5)
        self._start_fall(vx, -HOP_OFF_V * scale if hop else 0.0)

    # --- a reminder's card -----------------------------------------------------------------

    def bring_card(self, token: Any, now: float) -> None:
        """A reminder fell due: fetch it. One at a time; the rest wait their turn."""
        self.card_queue.append(token)
        self.now = max(self.now, now)

    def _card_step(self, now: float) -> None:
        if self.card is None:
            if not self.card_queue or self.state not in CARD_STAND:
                return
            self.card, self.card_settled, self.card_until = self.card_queue.pop(0), False, math.inf
        if self.card_settled or self.state not in CARD_STAND[:-1]:
            return
        if self.state in ("walk", "drift") and self.trip and self.then == "card":
            return
        if self.perch is not None:
            self._leave_perch(now, hop=False)
            return
        self._go_card(now)

    def _go_card(self, now: float) -> None:
        """To the floor beside the pointer, on the pointer's own monitor."""
        if self.reduced or not self.roam or self.pointer is None:
            self._arrive_card(now)
            return
        px, py = self.pointer
        m = self.monitor_at(px, py)
        left, _top, right, _bottom = m.area
        w = self.size[0]
        if m is not self.current_monitor():  # no walkable way between: it comes in at the near side
            self.x = left if abs(self.x - left) < abs(self.x - (right - w)) else right - w
            self.y = self.ground_y(m)
        side = 1 if px < (left + right) / 2 else -1
        gx = min(max(px + side * w * 1.2 - w / 2, left), right - w)
        self._go((gx, self.ground_y(m)), "card", now)

    def _arrive_card(self, now: float) -> None:
        self.card_settled = True
        self.card_until = now + CARD_FOR
        self.goal = None
        self._enter("card", now)

    def _put_card_down(self, now: float) -> None:
        self.card, self.card_settled = None, False
        self._enter("stand", now)

    def _do_card(self, now: float, dt: float) -> None:
        if now >= self.state_until:
            self._put_card_down(now)

    def _do_leap(self, now: float, dt: float) -> None:
        t = min(1.0, (now - self.phase_started) / max(1e-6, self.state_until - self.phase_started))
        self.y = self.phase_from[1] + (self.phase_to[1] - self.phase_from[1]) * t - math.sin(t * math.pi) * 24 * self._scale()
        if now >= self.state_until:
            p = self._target_here()
            if p is None:
                self.target = None
                self._start_fall(0.0)
            else:
                self._stand_on(p, now)

    def _rest(self, now: float) -> None:
        if self.gait == "walk":
            self._enter("stand", now)
            self.state_until = now + self.rng.uniform(*REST_FOR)
            return
        # A wind spirit rests low, or up near the top.
        m = self.current_monitor()
        high = self.rng.random() < 0.4
        gy = m.area[1] + 20 * self._scale() if high else self.ground_y(m)
        self._go((self.rng.uniform(m.area[0], m.area[2] - self.size[0]), gy), "rest", now)

    def _hang(self, now: float) -> None:
        m = self.current_monitor()
        left, top, right, _b = m.area
        lift = self._lift()
        if self.gait != "float":
            self._rise((self.x, top - lift), "hang", now)
            return
        x, hold = self.rng.uniform(left, right - self.size[0]), None
        y = top - lift  # the work area's top is always an edge under the hands
        spots = self._title_bars(m)
        if spots and self.rng.random() < 0.5:
            hold, x = spots[self.rng.randrange(len(spots))]
            y = hold.top + TITLE_BAR * self._scale() - lift
        self._go((x, y), "hang", now)
        self.hang_on = hold

    def _title_bars(self, m: Monitor) -> list[tuple[Perch, float]]:
        """The windows a hang may take hold of on this monitor, each with an x for the
        figure that puts its hands over the window's edge: [(window, x)]."""
        if not (self.roam_windows and self.roam):
            return []
        left, top, right, _b = m.area
        w, k = self.size[0], self._scale()
        found = []
        for p in self.windows:
            lo, hi = max(left + w / 2, p.left + HANG_HANDS * w), min(right - w / 2, p.right - HANG_HANDS * w)
            edge = p.top + TITLE_BAR * k
            if hi - lo < 0.2 * w or p.top < top or edge > self.floor_y(m) - self._lift():
                continue
            found.append((p, self.rng.uniform(lo, hi) - w / 2))
        return found

    def _peek(self, now: float) -> None:
        m = self.current_monitor()
        edges = ["bottom"] + [e for e in ("left", "right") if self._open_side(m, e)]
        edge = self.rng.choice(edges)
        if edge == "bottom":
            self._go((self.x, self.floor_y(m)), "peek_bottom", now)
            return
        gx = m.area[0] if edge == "left" else m.area[2] - self.size[0]
        self._go((gx, self.y if self.gait == "float" else self.floor_y(m)), f"peek_{edge}", now)

    def _go(self, goal: tuple[float, float], then: str, now: float) -> None:
        """Travel to a point (walking along the floor, or drifting), then `then`."""
        self.then = then
        if self.gait == "walk":
            if abs(goal[0] - self.x) < 1.0:
                self._arrive(now)
                return
            self._enter("walk", now)
            self.goal = goal
            self.facing = 1 if goal[0] >= self.x else -1
        else:
            self.goal = goal
            self._enter("drift", now)
            self.heading = math.atan2(goal[1] - self.y, goal[0] - self.x)
        self.trip = True
        self.state_until = math.inf

    def _rise(self, to: tuple[float, float], then: str, now: float) -> None:
        self.then = then
        self._enter("rise", now)
        self.phase_to = to

    def _arrive(self, now: float) -> None:
        """At the goal of a trip: what it came for."""
        then, self.goal = self.then, None
        m = self.current_monitor()
        if then == "card":
            self._arrive_card(now)
        elif then == "climb":
            if self._target_here() is None:
                self.target = None
                self._enter("stand", now)
            else:
                self.target = self._target_here()
                self._enter("leap", now)
        elif then == "perch":
            p = self._target_here()
            if p is None:
                self.target = None
                self._enter("stand", now)
            else:
                self._stand_on(p, now)
                self.perch_until = now + self.rng.uniform(*REST_FOR)
                self._enter("stand", now)
                self.state_until = self.perch_until
        elif then == "hang":
            self._arrive_hang(now, m)
        elif then.startswith("peek_"):
            self.peek_edge = then[5:]
            self.sink_max = PEEK_HEAD if self.peek_edge == "bottom" else PEEK_SIDE
            if self.peek_edge == "left":
                self.facing = 1
            elif self.peek_edge == "right":
                self.facing = -1
            self._enter("peek", now)
        else:
            self._enter("stand", now)
            if then == "rest":
                self.state_until = now + self.rng.uniform(*REST_FOR)

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

    def _do_drift(self, now: float, dt: float) -> None:
        """Float: steer toward a point with a limited turn rate (so the path curves),
        slowing in as it gets there; wandering picks a new point each time."""
        m = self.current_monitor()
        left, top, right, _b = m.area
        scale = self._scale()
        if self.goal is None:
            self.goal = (self._leg_x(left, right), self.rng.uniform(top, self.ground_y(m)))
            wandering = True
        else:
            wandering = not self.trip
        gx, gy = self.goal
        dx, dy = gx - self.x, gy - self.y
        dist = math.hypot(dx, dy)
        if dist <= REACHED * scale:
            self.x, self.y = gx, gy
            if wandering and now < self.state_until:
                self.goal = None
            else:
                self._arrive(now)
            return
        want = math.atan2(dy, dx)
        if dist < 30 * scale:
            self.heading = want
        else:
            diff = (want - self.heading + math.pi) % (2 * math.pi) - math.pi
            self.heading += max(-FLOAT_TURN * dt, min(FLOAT_TURN * dt, diff))
        speed = FLOAT_SPEED * scale * max(0.3, min(1.0, dist / (60 * scale)))
        self.x = min(max(self.x + math.cos(self.heading) * speed * dt, left), right - self.size[0])
        high = top - (self._lift() if self.then == "hang" and self.trip else 0.0)
        self.y = min(max(self.y + math.sin(self.heading) * speed * dt, high), self.floor_y(m))
        if abs(math.cos(self.heading)) > 0.3:
            self.facing = 1 if math.cos(self.heading) > 0 else -1
        if wandering and now >= self.state_until:
            self.goal = None
            self._enter("stand", now)

    def _leg_x(self, left: float, right: float) -> float:
        """The far end of a drift leg: a good way across the work area (FLOAT_LEG of its
        width), toward the side with more room, never a short shuffle."""
        span = right - left - self.size[0]
        room_l, room_r = self.x - left, right - self.size[0] - self.x
        go_right = self.rng.random() < room_r / max(1.0, room_l + room_r)
        room = room_r if go_right else room_l
        want = self.rng.uniform(*FLOAT_LEG) * span
        if room < FLOAT_LEG[0] * span:  # not enough that way: the other
            go_right, room = not go_right, room_l if go_right else room_r
        step = min(want, room)
        return self.x + step if go_right else self.x - step

    def _do_rise(self, now: float, dt: float) -> None:
        t = min(1.0, (now - self.phase_started) / RISE_FOR)
        t = t * t * (3 - 2 * t)
        self.x = self.phase_from[0] + (self.phase_to[0] - self.phase_from[0]) * t
        self.y = self.phase_from[1] + (self.phase_to[1] - self.phase_from[1]) * t
        if now >= self.state_until:
            self._arrive(now)

    def _do_hang(self, now: float, dt: float) -> None:
        if now >= self.state_until:
            self._let_go()

    def _let_go(self) -> None:
        """Off the ceiling: a walker falls, a floater drifts down to its hover height."""
        self._start_fall(0.0)

    def _peek_depth(self, t: float) -> float:
        plan = PEEK_PLAN
        for (t0, d0), (t1, d1) in zip(plan, plan[1:]):
            if t <= t1:
                return d0 + (d1 - d0) * (t - t0) / (t1 - t0)
        return plan[-1][1]

    def _do_peek(self, now: float, dt: float) -> None:
        t = now - self.peek_started
        depth = self._peek_depth(t)
        if depth <= 1.0:
            self.sink = depth * self.sink_max
        else:  # ducked: from the head showing to all of it gone
            self.sink = self.sink_max + (1.0 - self.sink_max) * (depth - 1.0)
        if self.peek_edge == "bottom" and not self.peek_turned and t >= 1.8:
            self.peek_turned = True
            self.facing = -self.facing
        if now >= self.state_until:
            self._enter("stand", now)

    def _do_emerge(self, now: float, dt: float) -> None:
        t = min(1.0, (now - self.phase_started) / EMERGE_FOR)
        self.sink = self.phase_from[0] * (1.0 - t)
        if now >= self.state_until:
            self.peek_edge = None
            self.sink = 0.0
            self._enter("wave" if not self.reduced else "sit", now)

    def _do_fly(self, now: float, dt: float) -> None:
        """Thrown: ballistic (gravity for a walker; for a floater air drag and a gentle
        pull to its hover height). Bounces off the outer walls, hangs from the ceiling."""
        scale = self._scale()
        m = self.current_monitor()
        left, top, right, _b = m.area
        floater = self.gait == "float"
        if floater:
            decay = math.exp(-FLOAT_DRAG * dt)
            self.vx *= decay
            self.vy = self.vy * decay + FLOAT_PULL * (self.ground_y(m) - self.y) * dt
        else:
            self.vy += GRAVITY * scale * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        speed = math.hypot(self.vx, self.vy)
        self.angle += self.spin_dir * SPIN_RATE * min(1.0, speed / (THROW_MAX * 0.4 * scale)) * dt
        if self.x < left and self._open_side(m, "left"):
            self.x, self.vx = left, abs(self.vx) * BOUNCE_DAMP
            self.bonk_until = now + BONK_FOR
        elif self.x > right - self.size[0] and self._open_side(m, "right"):
            self.x, self.vx = right - self.size[0], -abs(self.vx) * BOUNCE_DAMP
            self.bonk_until = now + BONK_FOR
        if self.y <= top - self._lift() and self._open_side(m, "top"):
            self.y, self.vx, self.vy = top - self._lift(), 0.0, 0.0
            self.angle = 0.0
            self._enter("hang", now)
            return
        floor = self.floor_y(m)
        if floater:
            self.y = min(self.y, floor)
            if speed < 25 * scale and abs(self.ground_y(m) - self.y) < 4 * scale:
                self.vx = self.vy = 0.0
                self.y = self.ground_y(m)
                self.settled_now = True
                self._enter("stand", now)
        elif self.y >= floor:
            self.y, self.vy, self.vx = floor, 0.0, 0.0
            self.settled_now = True
            self._enter("land", now)

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
        if self.goal is not None and abs(self.goal[0] - self.x) <= abs(step):
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
        self._enter("fall", self.now)

    def _start_fly(self, vx: float, vy: float) -> None:
        self.vx, self.vy = vx, vy
        self.spin_dir = 1 if vx >= 0 else -1
        if abs(vx) > 1:
            self.facing = 1 if vx > 0 else -1
        self._enter("fly", self.now)

    # --- the pointer ---------------------------------------------------------------------------

    def _notice(self, now: float, pointer: tuple[int, int]) -> None:
        if self.state not in ("stand", "walk", "drift", "sit", "sleep") or now < self.notice_ready:
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
        if self.carrying:
            self.x, self.y = px - self.grab[0], py - self.grab[1]
            self._keep_on_screen()
            self.trail.append((self.now, px, py))
            del self.trail[:-16]

    def _keep_on_screen(self) -> None:
        m = self.current_monitor()
        left, top, right, bottom = m.area
        self.x = min(max(self.x, left - self.size[0] / 2), right - self.size[0] / 2)
        self.y = min(max(self.y, top), bottom - self.size[1] / 2)

    def _release(self, px: int, py: int, now: float) -> None:
        self.press = None
        self._touched(now)
        if not self.carrying:
            self._clicked(now)
            return
        self.carrying = False
        self.x = min(max(self.x, self.current_monitor().area[0]), self.current_monitor().area[2] - self.size[0])
        velocity = None if self.reduced else self._throw_velocity(now, px, py)
        if velocity is not None:
            self._start_fly(*velocity)
        else:
            self._drop(now)

    def _clicked(self, now: float) -> None:
        """A press that was never a drag: open a card, bring a peeker out, let a hanger go, or wave."""
        reply = "sit" if self.reduced else "wave"
        if self.pre_press == "card" and self.card is not None:
            self.card_clicked = self.card  # the reminder opens; the card is set down
            self._put_card_down(now)
            self._enter(reply, now)
            return
        self.click_now = "left"
        if self.pre_press in ("peek", "emerge") and self.peek_edge and not self.reduced:
            self._enter("emerge", now)  # a click brings a peeking figure out
        elif self.pre_press == "hang" and not self.reduced:
            self._let_go()
        else:
            self._enter(reply, now)

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

    # --- the answer ------------------------------------------------------------------------------------

    def _frame(self, now: float) -> str:
        s = self.state
        if self.card is not None and s in ("walk", "drift"):
            return f"card{int((now - self.walk_started) / CARD_WALK_SWAP) % 2}"
        if s == "card":
            return f"card{int(now / CARD_SWAP) % 2}"
        if s in ("walk", "drift"):
            return f"walk{int((now - self.walk_started) / 0.125) % 6}"
        if s in FRAME_OF:
            return FRAME_OF[s]
        if s == "fly":
            if now < self.bonk_until:
                return "hop"
            return f"spin{int(round(self.angle / (2 * math.pi / SPIN_STEPS))) % SPIN_STEPS}"
        if s in ("rise", "peek"):
            return self._edge_frame(now)
        if s == "stand":
            return self._stand_frame(now)
        return s  # sit, sleep, wave, fall, land

    def _edge_frame(self, now: float) -> str:
        if self.state == "rise":
            return "hop" if self.gait == "walk" else f"walk{int((now - self.phase_started) / 0.125) % 6}"
        return "stand" if self.sink < self.sink_max * 0.5 or now - self.peek_started < 0.8 else "look"

    def _stand_frame(self, now: float) -> str:
        if self.flash:
            return self.flash[0]
        return f"idle{self._idle_index(now)}" if self._idling() else "stand"

    def _idling(self) -> bool:
        """Standing with life in its parts: not reduced, not typing-quiet, frames present."""
        return self.state == "stand" and not self.reduced and not self.quiet and self.idle_frames > 0

    def _idle_index(self, now: float) -> int:
        return int(now * IDLE_FPS + 1e-6) % self.idle_frames

    def _wake(self, now: float) -> int | None:
        s = self.state
        if s == "card":  # waiting with a card, even when still: it swaps and it runs out
            return max(MIN_WAKE_MS, min(int(CARD_SWAP * 1000), int(math.ceil((self.state_until - now) * 1000))))
        if self.reduced:
            return None
        if s in ("walk", "held", "drift", "hang", "rise", "peek", "emerge"):
            return TICK_WALK_MS
        if s in ("fall", "hop", "fly", "leap"):
            return TICK_FALL_MS
        if s == "pressed":
            return None
        if s in ("sleep", "sit"):
            return POLL_QUIET_MS
        due = [self.state_until] if s != "stand" or (self.roam and not self.reduced) else []
        if s == "stand":
            due += [self.flash[1]] if self.flash else [self.next_ambient]
            due.append(self.last_active + IDLE_SIT)
        if self._bobbing():  # the next bob step
            due.append(now + BOB_TICK)
        if self._idling():  # the next idle frame: a redraw only when the index changes
            due.append((math.floor(now * IDLE_FPS + 1e-6) + 1) / IDLE_FPS)
        soonest = min(due)
        if soonest == math.inf:
            return None
        return max(MIN_WAKE_MS, int(math.ceil((soonest - now) * 1000)) + 1)

    def _bobbing(self) -> bool:
        """A floater out in the air, standing or drifting, with motion allowed: it bobs
        and sways (never on a window it rests on, or while reduced or typing-quiet)."""
        return (
            self.gait == "float" and self.state in ("stand", "drift") and not self.reduced and not self.quiet
            and self.perch is None and self.sink <= 0
        )

    def _display(self) -> tuple[float, float, tuple[int, int, int, int] | None]:
        """Where the window is drawn and which part of the frame shows: the rest
        position, less the sink behind an edge, plus the sway of a hang and the bob
        and sway of a floater."""
        w, h = self.size
        x, y = self.x, self.y
        if self._bobbing():
            m, k = self.current_monitor(), self._scale()
            tau = 2 * math.pi * self.now
            y = max(m.area[1], y - BOB * k * (0.5 + 0.5 * math.sin(tau * BOB_HZ)))
            x = min(max(x + FLOAT_SWAY * k * math.sin(tau * FLOAT_SWAY_HZ + 1.3), m.area[0]), m.area[2] - w)
        if self.state == "hang":
            x += math.sin((self.now - self.phase_started) * 2 * math.pi * SWAY_HZ) * SWAY * self._scale()
        if self.sink <= 0 or self.peek_edge is None:
            return x, y, None
        if self.peek_edge == "bottom":
            hidden = round(self.sink * h)
            return x, y + hidden, (0, 0, w, h - hidden)
        hidden = round(self.sink * w)
        if self.peek_edge == "left":
            return x - hidden, y, (hidden, 0, w, h)
        return x + hidden, y, (0, 0, w - hidden, h)

    def _output(self, now: float) -> Output:
        x, y, clip = self._display()
        return Output(
            self._frame(now), int(round(x)), int(round(y)), self.facing < 0, self._wake(now),
            self.click_now, self.settled_now, clip, self.card_clicked,
        )
