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

from . import behaviour as bh
from . import travel as tv

#: Seconds.
MAX_DT = 0.1
#: One ambient moment (a blink, now and then a look) this far apart, like the in-app companion's blinks
#: (INBOX 1670, 16:40Z: irregular, 2 to 7 s): each costs two wakes (start and end). The gap is drawn
#: skewed to the short end (a person blinks more often than not within 4 s), and one blink in `DOUBLE_SHARE`
#: is followed by a second after `DOUBLE_GAP` seconds.
AMBIENT_EVERY = (2.0, 7.0)
AMBIENT_SKEW = 1.4
DOUBLE_SHARE = 0.14
DOUBLE_GAP = 0.16
LOOK_SHARE = 0.12
BLINK_FOR = 0.18
LOOK_FOR = 1.2
STAND_FOR = (3.0, 8.0)
#: A settled spell (INBOX 1670, 13:15Z: "it can't sit still"): standing, it stays put this long before it
#: so much as picks something to do (median about six minutes); a blink or a tail beat does not break it.
SETTLE_FOR = (200.0, 520.0)
#: Sitting and sleeping live in place on the body pose (INBOX 1670, 15:40Z: "doesnt have any subtle animation",
#: like the in-app companion): a breath and a slow tail sway, as (breath period s, share of height, tail px,
#: tail period s). The window never moves; asleep the breath is slower and deeper. The tail's period is not a
#: multiple of the breath's, wanders by `TAIL_WANDER` of itself over `TAIL_WANDER_S` and trails the body by
#: `TAIL_LAG` seconds, with a second, faster sway over the first (INBOX 1670, 16:40Z: no rigid loop, like the
#: in-app tail), so the pair never repeats; every picture is on the pose grid and the cache holds the recent ones.
REST_LIFE = {"sit": (4.8, 0.012, 3.0, 3.7), "sleep": (7.5, 0.016, 2.0, 11.3)}
TAIL_WANDER = 0.12
TAIL_WANDER_S = 43.0
TAIL_LAG = 0.9
#: Finer than the walk's grid so a 1.5 px breath is a few smooth steps, not a hard on and off.
Q_BREATH = 0.005
#: A drifting floater breathes in the figure (share of height, period s) now that the window does not bob.
DRIFT_BREATH = 0.012
DRIFT_BREATH_S = 4.4
#: A rest redraw is at most this often: 12 a second.
REST_DRAW_MS = 84
STAND_FAMILY = ("stand", "blink", "look")
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
#: The idle cycle (`idle0` to `idle23`, one tail beat and one breath): a standing figure draws these at
#: `IDLE_FPS` all the time so the parts never stop (INBOX 1670, 15:40Z); reduced it is the one `stand` frame
#: and costs no wake.
IDLE_FRAMES = 24
#: 24 frames at 6 a second keep the cycle at 4 s (one tail beat, one breath) with twice the in-betweens.
#: Faster would be the energetic child the owner does not want (INBOX 1670, 14:10Z).
IDLE_FPS = 6.0

#: Logical pixels (scaled by the monitor's dpi).
#: Lively, not a crawl (INBOX 1683 f: "all it does is poof"); was 55, so a 1,500 px leg took 16 s at a dash.
WALK_SPEED = 130.0
#: A unhurried pace, by distance (INBOX 1670: "a buddy, not a nuisance"): close range is a step,
#: the middle distance a walk, far a run (a swoop for a floater), each eased in and out.
STEP_UNDER = 60.0
DASH_OVER = 420.0
STEP_K, DASH_K = 0.6, 2.0
EASE_IN = 0.7
EASE_OUT = 70.0
CROUCH_FOR = 0.25
TURN_FOR = 0.24
#: Home: where it was left. Most of its time is spent there; strolls stay within STROLL px of it,
#: a trip away comes at most every TRIP_EVERY seconds (a few an hour), then it goes home.
STROLL = 150.0
TRIP_EVERY = (520.0, 1100.0)
TRIP_FIRST = (300.0, 700.0)
AWAY = 40.0
#: Following the pointer at a polite distance, for a while.
FOLLOW_GAP = 240.0
#: "Come here" (the menu): it stops this close to the pointer, and keeps company this long.
COME_GAP = 70.0
COME_FOR = 20.0
#: A "Go somewhere else" is at least this far (logical px), when the work area allows.
WANDER_MIN = 420.0
FOLLOW_FOR = (10.0, 18.0)
GREET_AFTER = 420.0
#: Under a busy pointer it waits instead of passing (px ahead / height of the path / seconds).
YIELD_NEAR = 130.0
YIELD_MAX = 4.0
LEAN_MAX = 0.07
POSE_RATE = 14.0
POSE_OFF = ("held", "pressed", "fly", "fall", "rise", "peek", "emerge", "leap", "hop", "card")
#: Logical px of travel per walk frame (six frames a stride).
#: Travel (logical px) per frame of the walk cycle at the shipped 12 frames: 42 px a cycle, as with 6.
STRIDE = 3.5
WALK_FRAMES = 12
TAIL_TICK_MS = 50
GRAVITY = 2200.0
NOTICE_NEAR = 120.0
NOTICE_VERY_NEAR = 40.0
#: Physical pixels the pointer may move between press and release for it to be a click.
CLICK_SLOP = 4
#: A resting spot in from the right edge, away from the tray's flyouts.
HOME_INSET = 100.0
#: A home found in the middle third of the work area moves to an edge after this long (s).
RELOCATE_AFTER = 120.0

#: How long each state holds: a range (random) or a fixed time; the others set theirs in `_on_<state>`.
HOLD_RANGES = {"stand": SETTLE_FOR, "sit": SIT_FOR}
HOLD_FIXED = {"wave": WAVE_FOR, "land": LAND_FOR, "hop": HOP_FOR, "notice": NOTICE_FOR, "startle": STARTLE_FOR}

#: States drawn with a frame of another name.
FRAME_OF = {"pressed": "stand", "leap": "hop", "notice": "look", "startle": "hop", "hop": "hop", "held": "held", "hang": "hang", "emerge": "stand", "warp": "stand"}

#: Throw: the pointer's last THROW_WINDOW seconds decide the velocity. Logical
#: px per second (scaled by dpi): slower than THROW_MIN is a plain drop.
THROW_WINDOW = 0.1
THROW_MIN = 350.0
THROW_MAX = 3200.0
BOUNCE_DAMP = 0.55
BONK_FOR = 0.3
#: A thrown figure's spin (INBOX 1670, 17:05Z: it turned "by 45 degrees each time, at 1 second intervals"):
#: the angle is continuous and drawn in `SPIN_STEPS` frames of 7.5 degrees. The turn rate is set at the
#: release (`SPIN_OMEGA` rad/s from a slow throw to a hard one, plus `SPIN_SWIRL` for a throw that curls),
#: fades by its own drag, and a contact changes it; it is not tied to the speed of the flight.
#: Slower than this (px per second at 96 dpi) a thrown figure stops tumbling.
FLY_SPIN_MIN = 60.0
#: It lays the tumble down only after being this slow for this long (s): a vertical throw is
#: under FLY_SPIN_MIN for a few frames at its apex, and the held pose (a smaller canvas) in
#: between flickered the window's size and offset (review of INBOX 1670).
FLY_REST_DWELL = 0.3
SPIN_OMEGA = (2.5, 11.0)
SPIN_SWIRL = 3.0
SPIN_DRAG = 0.5
SPIN_CONTACT = 0.6
#: Once the flight is this slow (px per second at 96 dpi), or it is on the floor, it rights itself with an
#: eased turn (a critically damped spring to the nearest upright, `RIGHT_W` rad/s, ramped in over `RIGHT_RAMP`
#: s so the turn rate stays continuous) and is laid down only when upright.
RIGHT_SPEED = 150.0
RIGHT_W = 2.6
RIGHT_RAMP = 0.4
SPIN_STEPS = 48
SPIN_FRAMES_ENGINE = tuple(f"spin{i}" for i in range(SPIN_STEPS))
#: A floater: hover height range above the floor, speed, turn rate, air drag,
#: and the pull back to its hover height (per second squared per pixel).
#: Its rest line: a hand's breadth above the work area's bottom, so the feet are on the
#: taskbar (INBOX 1670: "it still sits like 20px above the bottom bar"). It never sinks below. Was (24, 80), a figure's height up.
HOVER = (0.0, 0.0)
#: How far below the work area's top a released figure's head may be and still take hold.
HANG_REACH = 0.3
#: The ceiling takes hold of a throw only when it was thrown hard and mostly upward (INBOX 1670, 15:45Z: "nearly every
#: time I throw it no matter how hard, it goes to the top to hang"): this much upward launch speed (logical px per
#: second, over half of `THROW_MAX`) and at least this share of the throw's speed pointing up. It is read at the
#: launch, not at the top, because a floater's drag takes most of a hard throw's speed before it gets there. Any
#: other throw bounces off the top like a side wall.
CEIL_CATCH = 2000.0
CEIL_UPWARD = 0.8
FLOAT_SPEED = 170.0
FLOAT_TURN = 1.8
FLOAT_DRAG = 3.0
FLOAT_PULL = 3.0
REACHED = 2.0
#: A floater travels (INBOX 1658: "it just floats there"): each leg is at least this share
#: of the work area's width, it rests only a moment between legs, and while it is
#: out it travels; the window never bobs or sways (INBOX 1670, 16:40Z: it must not jitter up and down).
FLOAT_LEG = (0.35, 0.8)
FLOAT_STAND_FOR = (0.8, 2.0)
#: A wandering leg aims within this many figure heights above the rest line (INBOX 1663:
#: "floats wayyy to high"); only a trip to a window or an edge goes higher.
FLOAT_BAND = 0.35
FLOAT_MOVE_WEIGHT = 150
#: Hang from the top edge, and the climb up to it. The window holds still while it hangs
#: (INBOX 1663: "slides a little from side to side"): any life is in the frames.
HANG_FOR = (45.0, 120.0)
#: A hang swings from its grip like a pendulum (the lower body lags by this many px, `Pose.drag`), a
#: slow one, and glances about now and then (INBOX 1670, 13:28Z: "it basically doesn't move while it is
#: hanging"). The window itself holds still: only the picture swings.
HANG_SWING = 9.0
HANG_PERIOD = 5.6
HANG_GLANCE = (11.0, 26.0)
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
BIG_EVERY = (700.0, 1300.0)
#: The first one comes sooner, inside the minutes before it sits down for good.
BIG_FIRST = (300.0, 700.0)
#: While the person is busy (typing, presenting) it asks again this often.
QUIET_RECHECK = 5.0
REST_FOR = (8.0, 20.0)
#: The ambient choice, one table: act -> (weight, big). `sleep` needs SLEEP_AFTER idle.
ACTS = {
    "idle": (62, False), "stroll": (3, False), "trip": (16, False), "sleep": (2, False),
    "hang": (4, True), "peek": (5, True),
}
SLEEP_AFTER = 60.0

#: Window tops (roam): the first climb comes after `CLIMB_FIRST`, then one every
#: `CLIMB_EVERY` seconds at most; it stays on one window `PERCH_FOR`; a top must be
#: `PERCH_MIN_RISE` logical px above the floor to be worth the leap; a window top
#: that moves more than `PERCH_MOVED` physical px has moved.
CLIMB_FIRST = 40.0
CLIMB_EVERY = (180.0, 420.0)
PERCH_FOR = (20.0, 50.0)
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

#: The wake of anything that moves the window: one display frame at 60 Hz. The host puts a wake this
#: short on a fixed 60 Hz grid (`pacing.py`); at 33 ms `SetTimer` made it 31 or 47 (INBOX 1670, 14:14Z,
#: "very framey"). The position is read from the clock on every tick, so a late tick lands where the
#: figure should be and never stutters. Slow things (a hanging swing, the tail's settle) keep their own.
TICK_WALK_MS = 16
TICK_FALL_MS = 16
HANG_TICK_MS = 50
#: A visit to a window is not a rest spot: the first leg to a window top stays under a minute.
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
    #: Body language over the frame, `(sx, sy, lean, drag)` on the cache grid (`behaviour.quantised`),
    #: or None for the plain frame.
    pose: tuple[float, float, float, float] | None = None
    #: A travel effect over the frame, `(kind, amount, side)`: a "portal" ring or a "puff" of nebula
    #: (amount 0 to 1, on the side the figure faces), or None.
    fx: tuple[str, float, int] | None = None
    #: How much of the figure shows (1 whole, 0 gone): a vanish or a step through a ring.
    alpha: float = 1.0


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
        walk_frames: int = WALK_FRAMES,
        rng: random.Random | None = None,
        now: float = 0.0,
    ) -> None:
        self.size = size
        self.idle_frames = max(0, int(idle_frames))
        self.walk_frames = max(1, int(walk_frames))
        self.monitors = list(monitors) or [Monitor((0, 0, 1920, 1040))]
        self.roam = roam
        self.reduced = reduced
        self.rng = rng or random.Random()
        #: Blinks and glances draw from their own stream (seeded from the engine's, not drawn from it), so the
        #: far more frequent ambient moments leave every other choice the same for a seed.
        self.life_rng = random.Random(self.rng.getstate()[1][0])
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
        self.next_ambient = now + self._ambient_gap()
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
        self.omega = 0.0  # a thrown figure's turn rate, rad/s
        self.right_t = 0.0  # seconds it has been righting itself
        self.grounded = False  # a walker's tumble that has reached the floor
        self.laid = False  # upright and slow: the held pose, for good until the next throw
        self.ground_mon: Monitor | None = None  # the screen a walker's tumble landed on
        self.slow_for = 0.0  # seconds a thrown figure has been under FLY_SPIN_MIN
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
        #: Mind, home, and the body's follow-through (INBOX 1670, row B).
        self.mind = bh.Mind(now)
        self.tail = bh.Trail()
        self.hour = 12
        self.act: str | None = None
        self.act_started = now
        self.act_len = 1.0
        self.mode = "walk"
        self.pending: tuple[tuple[float, float], str] | None = None
        self.turn_to = 0
        self.turn_started = -1e9
        self.vx_px = 0.0
        self.home_x: float | None = None
        self.trip_ready = now + self.rng.uniform(*TRIP_FIRST)
        self.follow_until = 0.0
        self.follow_close_until = 0.0
        self.nap_after_land = False
        self.follow_check = 0.0
        self.yield_since: float | None = None
        self.pointer_busy_at = -1e9
        self.last_pointer: tuple[int, int] | None = None
        self.last_click = -1e9
        self.moving_since = now
        self.act_turned = -1.0
        self.placed = False
        self.greet_at = 0.0
        self.pose_goal = bh.NEUTRAL
        self.cur = bh.NEUTRAL
        self.last_x = 0.0
        self.travel = 0.0
        self.trips = 0
        self.greet_pending = False
        #: The text caret of the foreground window (physical px) and when it was read, or None. While
        #: there is one, or the person is typing, the figure is busy: no trip, and it keeps clear of it.
        self.caret: Rect | None = None
        self.evade_ready = 0.0
        self.warp: dict[str, Any] | None = None
        self.edge_plan: tuple[tuple[float, float], str] | None = None
        #: What it did to get about: `modes` the chosen ones, `legs` every move `(mode, x0, x1, t)`.
        self.modes: list[str] = []
        self.legs: list[tuple[str, float, float, float]] = []
        self.hang_started = now
        self.hang_phase = 0.0
        self.hang_glance_at = math.inf
        self.idle_start = 0.0
        self.launch = (0.0, 0.0)  # the last throw's velocity: the ceiling holds a hard upward one
        self.plain_legs = False  # tests: every leg is the plain walk or drift, no vanish, no glide
        self.relocate_at: float | None = None
        #: The drawn box of every frame, `(name, mirrored) -> (left, top, right, bottom)` in px
        #: from where the window is placed (`SpriteSet.metrics`); empty means "the whole window".
        self.metrics: dict[tuple[str, bool], tuple[float, float, float, float]] = {}
        self._stand_bottom: float | None = None
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
        self.home_x = self.x
        self.last_x = self.x
        self._enter("stand" if not reduced else "sit", now)
        self._maybe_relocate(now)

    # --- geometry ------------------------------------------------------------------

    def set_metrics(self, metrics: dict[tuple[str, bool], tuple[float, float, float, float]]) -> None:
        self.metrics = dict(metrics)
        self._stand_bottom = None

    def _box(self, frame: str, flip: bool | None = None) -> tuple[float, float, float, float]:
        flip = self.facing < 0 if flip is None else flip
        return self.metrics.get((frame, flip)) or (0.0, 0.0, float(self.size[0]), float(self.size[1]))

    def _dy(self, frame: str) -> float:
        """How far a frame is drawn below the window's rest line so its lowest drawn row is on
        the floor: every frame is registered to one box, and the margin below the feet varies by
        pose (INBOX 1670). A hang is held by its hands, not stood on; a tumble keeps a held pose's."""
        if not self.metrics or frame == "hang":
            return 0.0
        if frame.startswith("spin"):
            frame = "held"
        elif frame in STAND_FAMILY or frame.startswith(("idle", "walk")) or frame == "wave":
            # the wave and the walk or drift cycle stand on the stand's line: their own boxes are up to 4 px
            # lower on one look (its tail), which hopped the window at entry and with every step (16:40Z)
            return max(0.0, self.size[1] - self._stand_family_bottom())
        elif frame == "sitblink":
            frame = "sit"
        return max(0.0, self.size[1] - self._box(frame, False)[3])

    def _stand_family_bottom(self) -> float:
        """The lowest drawn row of the stand, its blink and look and the whole idle cycle: they share one
        rest line, so the window never moves while the figure lives in place (INBOX 1670, 15:40Z) and no
        picture of the cycle dips under the floor."""
        if self._stand_bottom is None:
            names = (*STAND_FAMILY, *(f"idle{i}" for i in range(IDLE_FRAMES)))
            self._stand_bottom = max(self.metrics[(n, False)][3] for n in names if (n, False) in self.metrics)
        return self._stand_bottom

    def _fly_frame(self) -> str:
        """What a thrown figure shows: the tumble while it has speed, a limp upright pose
        (the held one, same foot offset) once it drifts to rest, so the settle is no step."""
        if self.laid:
            return "held"
        return f"spin{int(round(self.angle / (2 * math.pi / SPIN_STEPS))) % SPIN_STEPS}"

    def _flip_dx(self, frame: str, flip: bool) -> float:
        """The sideways shift that keeps a mirrored figure where it stood (the frames are not
        symmetric about the window's middle, so turning would otherwise jump it a few px)."""
        if not flip or not self.metrics or frame.startswith("spin"):
            return 0.0
        left, _t, right, _b = self._box("stand", False)
        return left + right - self.size[0]

    def _ride_box(self, frame: str) -> tuple[float, float, float, float]:
        """The drawn box of a frame (or of every frame a thrown figure may show, for "fly"),
        from the engine's x and y: its foot offset and mirror shift included."""
        flip = self.facing < 0
        names = ("held", "hop", *SPIN_FRAMES_ENGINE) if frame == "fly" else (frame,)
        boxes = []
        for n in names:
            left, top, right, bottom = self._box(n, flip)
            dx, dy = self._flip_dx(n, flip), self._dy("held" if frame == "fly" else n)
            boxes.append((left + dx, top + dy, right + dx, bottom + dy))
        return (
            min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes),
        )

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

    @property
    def busy(self) -> bool:
        """The person is working: typing, or a text caret in the foreground window."""
        return self.quiet or self.caret is not None

    def set_caret(self, rect: Rect | None) -> None:
        """The foreground window's caret rectangle in screen px (None: no caret). Read by the runner at
        about 0.5 Hz; the figure steps off it on the next tick."""
        self.caret = rect

    def resume(self, now: float) -> None:
        """After a suspend or a long stall: no jump, no catching up."""
        self.now = now
        self.next_ambient = now + self._ambient_gap()
        self.state_until = max(self.state_until, now + 1.0)
        self.last_active = now
        if self.state in ("peek", "emerge"):
            self._enter("stand", now)

    # --- state changes ----------------------------------------------------------------

    def _enter(self, state: str, now: float) -> None:
        self.state = state
        self.flash = None
        if state not in ("hang", "drift", "rise", "crouch"):
            self.hang_on = None
        if state not in ("peek", "emerge"):
            self.sink, self.peek_edge = 0.0, None
        if state not in ("walk", "drift", "crouch"):
            self.goal = None
        if state != "act":
            self.act = None
        self.trip = False
        if state != "warp":
            self.warp = None
        if state == "stand":
            self.idle_start = now  # the cycle starts from its first picture
        if state in HOLD_RANGES:
            self.state_until = now + self.rng.uniform(*HOLD_RANGES[state])
        elif state in HOLD_FIXED:
            self.state_until = now + HOLD_FIXED[state]
        elif state in ("sleep", "fly"):
            self.state_until = math.inf
        else:
            getattr(self, f"_on_{state}", lambda _now: None)(now)
        if state == "stand" and self.perch is not None:  # a visit to a window ends when its time does
            self.state_until = min(self.state_until, max(now + 1.0, self.perch_until))

    def _on_warp(self, now: float) -> None:
        self.state_until = math.inf

    def _on_walk(self, now: float) -> None:
        self.state_until = now + self.rng.uniform(*WALK_FOR)
        self.walk_started = now

    def _on_act(self, now: float) -> None:
        act = bh.ACTIVITIES[self.act or "breathe"]
        self.act_started, self.act_len = now, self.rng.uniform(*act.seconds)
        self.act_turned = -1.0
        self.state_until = now + self.act_len

    def _on_crouch(self, now: float) -> None:
        self.state_until = now + CROUCH_FOR

    def _on_drift(self, now: float) -> None:
        self.state_until = now + self.rng.uniform(*WALK_FOR)
        self.walk_started = now
        if self.goal is None:
            self.heading = self.rng.uniform(0, 2 * math.pi)

    def _on_hang(self, now: float) -> None:
        self.state_until = now + self.rng.uniform(*bh.HANG_BY_MOOD.get(self.mind.mood(now, self.hour), HANG_FOR))
        self.phase_started = self.hang_started = now
        self.hang_phase = self.rng.uniform(0.0, 2 * math.pi)
        self.hang_glance_at = now + self.rng.uniform(*HANG_GLANCE)

    def _on_rise(self, now: float) -> None:
        self.state_until = now + RISE_FOR
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
            if self.pointer is None or math.hypot(pointer[0] - self.pointer[0], pointer[1] - self.pointer[1]) > 3:
                if now - self.pointer_busy_at > GREET_AFTER:  # it is back after a long quiet: say hello
                    self.greet_pending, self.greet_at = True, now
                self.pointer_busy_at = now
            self.pointer = pointer
        self.mind.tick(now, self.hour)
        if event is not None:
            if event[0] == "down" and self.state == "warp":
                self._finish_warp(now)  # taken hold of mid-vanish: it is where it was going
            self._input(event, now)
        if self.state not in ("held", "pressed"):
            self._advance(now, dt, pointer)
        if self.caret is not None and self.state not in ("held", "pressed", "fly", "fall", "warp"):
            self._keep_off_caret(now)
        if self.turn_to:  # a turn begun in an act or a stand still finishes
            self._turning(now)
        self._follow_through(now, dt)
        if self.settled_now and self.placed:  # where the person left it is home
            self.home_x, self.placed = self.x, False
            self._maybe_relocate(now)
        return self._output(now)

    def _follow_through(self, now: float, dt: float) -> None:
        """The tail and the lower wisp lag the body (a spring chain thrown by its acceleration),
        and the pose eases toward its target (no state change snaps the body's shape)."""
        if dt <= 0:
            return
        vx = (self.x - self.last_x) / dt
        self.travel += abs(self.x - self.last_x)
        self.last_x = self.x
        self.tail.step(dt, vx if self.state not in ("held", "pressed") else 0.0)
        target = self.pose_goal = self._target_pose(now)
        k = min(1.0, dt * POSE_RATE)
        self.cur = bh.Pose(*(a + (b - a) * k for a, b in zip(self.cur, target)))
        self.vx_px = vx

    def _target_pose(self, now: float) -> bh.Pose:
        """What the body shape wants now: the act's keyframes, a turn's squeeze, a lean into the
        way it travels, a crouch or a landing's squash, a mood's carriage, and the tail's lag."""
        sx = sy = 1.0
        lean = 0.0
        drag = self.tail.tip
        s_ = self.state
        if self.reduced:
            return bh.NEUTRAL
        if s_ == "hang":  # a slow pendulum from the grip: the lower body swings, the hands do not move
            t = now - self.hang_started
            amp = bh.smooth(t / 1.5) * (0.65 + 0.35 * math.sin(2 * math.pi * t / 41.0 + self.hang_phase))
            drag = HANG_SWING * amp * math.sin(2 * math.pi * t / HANG_PERIOD + self.hang_phase)
        elif s_ == "warp" and self.warp is not None and self.warp["kind"] == "portal":
            squeeze = self._warp_view(now)[2]
            sx, sy = 1.0 - 0.8 * squeeze, 1.0 - 0.2 * squeeze
        elif s_ == "act":
            p = bh.sample(bh.ACTIVITIES[self.act or "breathe"].keys, (now - self.act_started) / max(0.01, self.act_len))
            sx, sy, lean = p.sx, p.sy, p.lean * (1 if self.facing > 0 else -1)
        else:
            sx, sy, lean = self._ground_pose(now, s_)
        if self.turn_to != 0:
            u = (now - self.turn_started) / TURN_FOR
            sx *= max(0.12, abs(math.cos(math.pi * min(1.0, u))))
        return bh.Pose(sx, sy, lean, drag)

    def _ground_pose(self, now: float, s_: str) -> tuple[float, float, float]:
        """The squash and lean of a crouch, a landing, a step or a mood's stand."""
        sx = sy = 1.0
        lean = 0.0
        if s_ == "crouch":
            sy, sx = 1.0 - 0.12 * bh.smooth((now - (self.state_until - CROUCH_FOR)) / CROUCH_FOR), 1.03
        elif s_ == "land":
            u = 1.0 - max(0.0, self.state_until - now) / LAND_FOR
            sy = 1.0 - 0.12 * math.sin(min(1.0, u) * math.pi)
            sx = 1.0 + 0.06 * math.sin(min(1.0, u) * math.pi)
        elif s_ in ("walk", "drift") and self.turn_to == 0:
            speed = min(1.0, abs(self.vx_px) / (WALK_SPEED * self._scale() * 1.2))
            lean = LEAN_MAX * speed * (1 if self.vx_px > 0 else -1) * (1.6 if self.mode == "dash" else 1.0)
            if self.gait == "float":  # the window never bobs: a floater's breath is in the figure
                sy = 1.0 + DRIFT_BREATH * (1.0 - math.cos(2 * math.pi * now / DRIFT_BREATH_S)) / 2.0
            if self.gait == "walk":  # a ground companion bounces with its steps
                sy = 1.0 + 0.012 * math.sin(self.travel / self._scale() * 2 * math.pi / (STRIDE * 2))
        elif s_ == "stand":
            mood = self.mind.mood(now, self.hour)
            sy = {"sleepy": 0.975, "proud": 1.035, "bored": 0.985, "startled": 1.05}.get(mood, 1.0)
        return sx, sy, lean

    def _pose(self) -> tuple[float, float, float, float] | None:
        """The body pose to draw over the frame; none while it is carried, thrown, falling or at an
        edge (those frames carry their own shape, and a spin sits on a bigger canvas)."""
        if self.state in POSE_OFF:
            return None
        q = self._life_pose(self.now)
        return None if q is None else (q.sx, q.sy, q.lean, q.drag)

    def _life_pose(self, at: float) -> bh.Pose | None:
        """The eased body pose with the breath and tail sway of a sit or a sleep over it, on the grid."""
        life = REST_LIFE.get(self.state)
        if life is None or self.reduced:
            return bh.quantised(self.cur)
        breath, depth, sway, sway_s = life
        c = self.cur
        swell = (1.0 - math.cos(2 * math.pi * at / breath)) / 2.0
        return bh.quantised(bh.Pose(c.sx, c.sy * (1.0 + depth * swell), c.lean, c.drag + self._rest_tail(at, life)), Q_BREATH)

    def _rest_tail(self, at: float, life: tuple[float, float, float, float]) -> float:
        """The tail's lag, px: a slow sway whose period drifts, a faster one over it, and the body's own breath a
        beat late, so a sit never repeats and the tail follows the body rather than keeping time with it."""
        breath, _depth, sway, sway_s = life
        tau = 2 * math.pi
        drift = TAIL_WANDER * TAIL_WANDER_S / sway_s * math.sin(tau * at / TAIL_WANDER_S)  # period within +-12 percent
        slow = math.sin(tau * at / sway_s + drift)
        fast = math.sin(tau * at / (sway_s * 0.62) + 1.7)
        late = (1.0 - math.cos(tau * (at - TAIL_LAG) / breath)) / 2.0 - 0.5
        return sway * self._scale() * (0.65 * slow + 0.3 * fast + 0.4 * late)

    def _next_life_change(self, now: float) -> float:
        """The next time a sit's or a sleep's breath or sway crosses a step of the grid, looking ahead
        at most `POLL_QUIET_MS` and never sooner than a redraw's pace (12 a second)."""
        base = self._life_pose(now)
        t, pace = now, REST_DRAW_MS / 1000.0
        while t < now + POLL_QUIET_MS / 1000.0:
            t += pace
            if self._life_pose(t) != base:
                return t
        return now + POLL_QUIET_MS / 1000.0

    def _advance(self, now: float, dt: float, pointer: tuple[int, int] | None) -> None:
        handler = getattr(self, f"_do_{self.state}")
        handler(now, dt)
        if self.card is not None or self.card_queue:
            self._card_step(now)
        if pointer is not None and not self.reduced:
            self._notice(now, pointer)

    # --- states -----------------------------------------------------------------------------

    def _ambient_gap(self) -> float:
        lo, hi = AMBIENT_EVERY
        return lo + (hi - lo) * self.life_rng.random() ** AMBIENT_SKEW

    def _ambient(self, now: float) -> None:
        """Blink, and now and then look about: while standing (a sit blinks, it does not look), and only
        when motion is allowed."""
        if self.reduced:
            return
        if self.flash and now >= self.flash[1]:
            if self.flash[0] == "look":  # the cycle resumes where the look paused it, not on another picture
                self.idle_start += now - (self.flash[1] - LOOK_FOR)
            self.flash = None
        if self.flash is None and now >= self.next_ambient:
            look = self.state == "stand" and self.life_rng.random() < LOOK_SHARE
            self.flash = ("look", now + LOOK_FOR) if look else ("blink", now + BLINK_FOR)
            double = not look and self.life_rng.random() < DOUBLE_SHARE
            self.next_ambient = now + (BLINK_FOR + DOUBLE_GAP if double else self._ambient_gap())

    def _after_stand(self, now: float) -> None:
        idle = now - self.last_active
        if self._stand_fixed(now, idle):
            return
        if self.relocate_at is not None and now >= self.relocate_at and self.perch is None and not self.busy:
            self._relocate(now)
        elif idle >= IDLE_SIT:
            self._after_long_idle(now)
        elif self.perch is not None and now >= self.perch_until and self.gait == "walk":
            self._leave_perch(now, hop=self.rng.random() < 0.5)
        elif now >= self.state_until:
            self._decide(now, idle)

    def _stand_fixed(self, now: float, idle: float) -> bool:
        """The cases where a stand does not lead to a roam: a card, reduced motion, no roaming."""
        if self.card is not None and self.card_settled:  # carried off its place: it waits again
            self._enter("card", now) if now < self.card_until else self._put_card_down(now)
            return True
        if self.reduced or not self.roam:
            if idle >= IDLE_SIT:
                self._enter("sit", now)
            return True
        return False

    def _after_long_idle(self, now: float) -> None:
        if self._away() and self.perch is None and not self.busy:
            self._go_home(now)  # it rests at its home spot, not wherever a stroll ended
        elif self.perch is not None:  # never sleeps on a window
            self._leave_perch(now, hop=False)
        else:
            self._enter("sit", now)

    def _decide(self, now: float, idle: float) -> None:
        """A settled spell is over: follow, go home, or do the next thing."""
        if self.busy:
            self.state_until = now + QUIET_RECHECK
            return
        if self.follow_until > now and self._follow(now):
            return
        if self._away() and self.perch is None:
            self._go_home(now)
            return
        self._perform(self._pick_act(now, idle), now)

    # --- home, trips, and what to do in place (INBOX 1670, row B) ------------------------

    def _away(self) -> bool:
        """Further from home than a stroll's end, or off the floor line: it goes back."""
        if self.home_x is None or self.card is not None:
            return False
        if abs(self.x - self.home_x) > AWAY * self._scale():
            return True
        return self.gait == "float" and self.y < self.ground_y() - 6 * self._scale()

    def _go_home(self, now: float) -> None:
        m = self.current_monitor()
        assert self.home_x is not None
        self._go((min(max(self.home_x, m.area[0]), m.area[2] - self.size[0]), self.ground_y(m)), "home", now)

    def _set_home(self) -> None:
        self.home_x = self.x

    def _start_act(self, name: str, now: float) -> None:
        self.mind.did(name, now)
        self.act = name
        self._enter("act", now)

    def _do_act(self, now: float, dt: float) -> None:
        act = bh.ACTIVITIES[self.act or "breathe"]
        u = (now - self.act_started) / max(0.01, self.act_len)
        for t in act.turns:
            if u >= t and self.act_turned < t:
                self.act_turned = t
                self._face(-self.facing, now)
        if now >= self.state_until:
            self._enter("stand", now)

    def _do_crouch(self, now: float, dt: float) -> None:
        if now >= self.state_until:
            self._begin_go(now)

    def _trip_ok(self, now: float) -> bool:
        return (
            self.roam and not self.reduced and not self.busy and self.perch is None and now >= self.trip_ready
            and self.card is None
        )

    def _stroll(self, now: float) -> None:
        """A short wander near home: a few steps either way, never across the screen."""
        m = self.current_monitor()
        k = self._scale()
        hx = self.home_x if self.home_x is not None else self.x
        off = self.rng.uniform(25, STROLL) * k * self.rng.choice((-1, 1))
        gx = min(max(hx + off, m.area[0]), m.area[2] - self.size[0])
        if tv.in_edge_zone(hx, m.area, self.size[0], k):  # a stroll from an edge spot stays by that edge
            side = tv.nearest_edge(hx, m.area, self.size[0])
            near, far_ = sorted((tv.edge_x(side, m.area, self.size[0], 6 * k), tv.edge_x(side, m.area, self.size[0], tv.EDGE_ZONE * k)))
            gx = min(max(gx, near), far_)
        if abs(gx - self.x) < 12 * k:
            self._start_act(self.mind.pick(self.rng, now, self.gait, self.hour), now)
            return
        self._go((gx, self.ground_y(m)), "stand", now)

    def _start_trip(self, now: float) -> None:
        """A rare, short, purposeful trip: to a window it is curious about, to greet the pointer
        after a long idle, to the clock corner, to follow the pointer a while, or to nap at an edge.
        Afterwards `_after_stand` brings it home."""
        self.trip_ready = now + self.rng.uniform(*TRIP_EVERY)
        self.trips += 1
        m = self.current_monitor()
        k = self._scale()
        if self.greet_pending and self.pointer is not None and now - self.greet_at < 240.0:
            self.greet_pending = False
            px = min(max(self.pointer[0] - self.size[0] / 2 - FOLLOW_GAP * k * (1 if self.pointer[0] > self.x else -1), m.area[0]), m.area[2] - self.size[0])
            self._go((px, self.ground_y(m)), "greet", now)
            return
        pick = self._trip_pick()
        if pick == "window":
            self.climb_ready = 0.0
            self._climb(now)
        elif pick == "follow":
            self.follow_until = now + self.rng.uniform(*FOLLOW_FOR)
            self._follow(now) or self._enter("stand", now)
        elif pick == "clock":
            self._go((m.area[2] - self.size[0] - 6 * k, self.ground_y(m)), "clock", now)
        else:  # nap: the nearer outer edge
            left = self.x - m.area[0] < m.area[2] - self.size[0] - self.x
            self._go((m.area[0] + 4 * k if left else m.area[2] - self.size[0] - 4 * k, self.ground_y(m)), "nap", now)

    def _trip_pick(self) -> str:
        table = [("clock", 2.0), ("nap", 2.0 if self.mind.needs["rest"] > 0.5 else 0.3)]
        if self.pointer is not None:
            table.append(("follow", 2.0))
        if self.roam_windows and self._candidates():
            table.append(("window", 4.0))
        roll = self.rng.random() * sum(w for _n, w in table)
        for name, w in table:
            roll -= w
            if roll < 0:
                return name
        return table[-1][0]

    def _arrive_trip(self, then: str, now: float) -> None:
        if then == "greet":
            self._enter("wave", now)
        elif then == "clock":
            self._start_act("ponder" if self.rng.random() < 0.5 else "look_around", now)
        elif then == "settle":  # "Go somewhere else": the new spot is home now
            self._set_home()
        else:
            self._start_act("lie_down" if self.gait == "walk" else "curl_up", now)

    def _follow(self, now: float) -> bool:
        """Keep a polite distance from the pointer for a while, then lose interest. False when
        there is nothing to follow (the pointer is not on this screen)."""
        p = self.pointer
        m = self.current_monitor()
        if p is None or not (m.area[0] <= p[0] <= m.area[2]):
            self.follow_until = 0.0
            return False
        k = self._scale()
        side = -1 if p[0] > self.x + self.size[0] / 2 else 1
        gap = COME_GAP if now < self.follow_close_until else FOLLOW_GAP
        gx = min(max(p[0] - self.size[0] / 2 + side * gap * k, m.area[0]), m.area[2] - self.size[0])
        gx = tv.out_of_middle(gx, m.area, self.size[0])  # the goal it will be given, so "close enough" is judged on that
        if abs(gx - self.x) < 60 * k:  # close enough: keep it company, small things
            self._start_act(self.mind.pick(self.rng, now, self.gait, self.hour), now)
            return True
        self._go((gx, self.ground_y(m)), "follow", now)
        return True

    def _pick_act(self, now: float, idle: float) -> str:
        """One weighted choice from `ACTS`: a big act only when `big_ready` has passed, a trip only
        when `trip_ready` has, sleep only after a while untouched and when tired."""
        table = self._act_table(now, idle)
        roll = self.rng.random() * sum(w for _a, w in table)
        for act, w in table:
            roll -= w
            if roll < 0:
                return act
        return "idle"

    def _act_table(self, now: float, idle: float) -> list[tuple[str, float]]:
        up = self.perch is not None
        mood = self.mind.mood(now, self.hour)
        table = []
        for act, (w, big) in ACTS.items():
            if big and (now < self.big_ready or up):
                continue
            if act == "sleep" and (idle < SLEEP_AFTER or up or self.mind.needs["rest"] < 0.4):
                continue
            if (act == "trip" and not self._trip_ok(now)) or (act == "stroll" and up):
                continue
            if act in ("stroll", "trip") and mood == "bored":
                w *= 2
            table.append((act, w))
        return table

    def _perform(self, act: str, now: float) -> None:
        if self.perch is not None and self.gait == "float":
            self.perch = None  # a floater rests on a window, it does not stay on it
        if act in ("hang", "peek"):
            self.big_ready = now + self.rng.uniform(*BIG_EVERY)
        if act == "stroll":
            self._stroll(now)
        elif act == "trip":
            self._start_trip(now)
        elif act == "hang":
            self._hang(now)
        elif act == "peek":
            self._peek(now)
        elif act == "climb":
            self._climb(now)
        elif act == "sleep":
            self._enter("sleep", now)
        else:
            self._start_act(self.mind.pick(self.rng, now, self.gait, self.hour, "perch" if self.perch else ""), now)

    # --- asked from the menu (INBOX 1670, row C) ----------------------------------------------

    #: What the menu can ask for; `command` says whether it was done.
    COMMANDS = ("wave", "come", "wander", "nap", "wake", "perch", "stay", "roam")
    #: The states a request may break into; anything else (carried, thrown, falling, leaping) is left alone.
    _FREE = ("stand", "sit", "sleep", "walk", "drift", "act", "crouch", "wave", "notice", "startle", "land", "hop", "card")

    def command(self, name: str, now: float) -> bool:
        """A choice from the companion's menu, on the engine's own thread. True when it took
        effect; False when it cannot be done now (carried, no window to sit on, motion off)."""
        if name == "stay":
            return self._stay(now)
        if name == "roam":
            return self._roam(now)
        if not self._free_for_command(now):
            return False
        self.last_active = now
        if name == "wave":
            self._enter("sit" if self.reduced else "wave", now)
        elif name == "nap":
            self._nap(now)
        elif name == "wake":
            self._wake_up(now)
        elif self.reduced:
            return False
        elif name == "come":
            return self._come(now)
        elif name == "wander":
            return self._wander(now)
        elif name == "perch":
            return self._sit_on_window(now)
        else:
            return False
        return True

    def _stay(self, now: float) -> bool:
        self.roam = False
        self.follow_until = 0.0
        if self.state in ("walk", "drift", "crouch") and not self.reduced:
            self._enter("stand", now)
        return True

    def _roam(self, now: float) -> bool:
        self.roam = True
        self.last_active = now
        if self.state == "sit" and not self.reduced:
            self._enter("stand", now)
        return True

    def _free_for_command(self, now: float) -> bool:
        """Bring a peeking or hanging figure back to its feet; False in a state a request may not break."""
        if self.state in ("peek", "emerge") and not self.reduced:
            self._enter("stand", now)
            return True
        if self.state == "hang" and not self.reduced:
            self._let_go()
            return True
        return self.state in self._FREE

    def _nap(self, now: float) -> None:
        if self.perch is not None and not self.reduced and self.gait == "walk":
            self.nap_after_land = True  # it never sleeps on a window: down first, then to sleep
            self._leave_perch(now, hop=False)
            return
        self.perch = None
        self._enter("sit" if self.reduced else "sleep", now)

    def _wake_up(self, now: float) -> None:
        if not self.reduced:
            self._wake_for(now)
            if self.state == "stand":
                self._start_act("stretch", now)

    def _wake_for(self, now: float) -> None:
        if self.state in ("sleep", "sit"):
            self._enter("stand", now)

    def _come(self, now: float) -> bool:
        """Walk to the pointer and keep close for a while. False when the pointer is not on this screen."""
        if self.pointer is None:
            return False
        self._wake_for(now)
        self.follow_until = now + COME_FOR
        self.follow_close_until = self.follow_until
        if self.perch is not None:
            self._leave_perch(now, hop=True)
            return True
        if self._follow(now):
            return True
        self.follow_until = self.follow_close_until = 0.0
        return False

    def _wander(self, now: float) -> bool:
        """Go to another part of the work area, far from here, and make it home."""
        self._wake_for(now)
        if self.perch is not None:
            self._leave_perch(now, hop=True)
            return True
        m = self.current_monitor()
        k = self._scale()
        lo, hi = m.area[0], m.area[2] - self.size[0]
        far = [x for x in (lo + (hi - lo) * i / 10 for i in range(11)) if abs(x - self.x) >= WANDER_MIN * k]
        pool = far or [lo if self.x - lo > hi - self.x else hi]
        gx = self.rng.choice(pool)
        if abs(gx - self.x) < 12 * k:
            return False
        self._go((gx, self.ground_y(m)), "settle", now)
        return True

    def _sit_on_window(self, now: float) -> bool:
        """Climb to a window's top edge the last scan found. False when there is none to sit on."""
        if not (self.roam_windows and self.roam) or self.perch is not None or not self._candidates():
            return False
        self._wake_for(now)
        self.climb_ready = 0.0
        self._climb(now)
        return True

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
            self.hang_on = None
            self._let_go()
        elif self.state in ("drift", "crouch") and self.then == "hang":
            self.hang_on, self.goal, self.then, self.pending = None, None, "stand", None
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
            self.roam_windows and self.roam and not self.reduced and not self.busy and self.perch is None
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
        """Up to a window's top: a walker standing under it jumps, one beside it climbs its side edge
        onto the top, and a floater glides there. Whatever lies between is crossed on foot (INBOX 1683 f)."""
        cand = self._candidates()
        if not cand:
            self._enter("stand", now)
            return
        p = self.rng.choice(cand)
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
        self.perch, self.target = p, None
        self.perch_until = now + self.rng.uniform(*PERCH_FOR)
        self.x = min(max(self.x, p.left), p.right - self.size[0])
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

    def _go(self, goal: tuple[float, float], then: str, now: float, plain: bool = False) -> None:
        """Travel to a point, then `then`. By distance: close range a step, the middle a walk, far a
        run or (a floater) a swoop that crouches first; each eased in and out, and it turns before
        it goes the other way."""
        self.then = then
        if not plain:
            m = self.current_monitor()
            gx = goal[0] if then == "card" else tv.out_of_middle(goal[0], m.area, self.size[0])
            goal = self._clear_of_caret(gx, goal[1])
        dist = abs(goal[0] - self.x) if self.gait == "walk" else math.hypot(goal[0] - self.x, goal[1] - self.y)
        if self.gait == "walk" and dist < 1.0:
            self._arrive(now)
            return
        if not plain and dist > 12 * self._scale():
            mode = self._leg_mode(goal, then)
            if mode == "edge":  # walks off one edge, comes in from the other (a warp only for the slip itself)
                self.modes.append(mode)
                self._start_edge(goal, then, now)
                return
            if mode in tv.WARPS:
                self._start_warp(mode, goal, then, now)
                return
            self.modes.append(mode)
        far = dist / self._scale()
        self.mode = "step" if far < STEP_UNDER else "dash" if far >= DASH_OVER else "walk"
        self.pending = (goal, then)
        if self.mode == "dash" and not self.reduced and self.gait == "walk":
            self._enter("crouch", now)  # a crouch before a long run
            self.pending = (goal, then)
            return
        self._begin_go(now)

    def _begin_go(self, now: float) -> None:
        assert self.pending is not None
        goal, then = self.pending
        self.pending = None
        self.then = then
        if self.gait == "walk":
            self._enter("walk", now)
            self.goal = goal
            self._face(1 if goal[0] >= self.x else -1, now)
        else:
            self.goal = goal
            self._enter("drift", now)
            self.heading = math.atan2(goal[1] - self.y, goal[0] - self.x)
            if math.hypot(goal[0] - self.x, goal[1] - self.y) > 80 * self._scale():  # a glide sails in an arc
                self.heading += self.rng.choice((-0.8, 0.8))
            if abs(math.cos(self.heading)) > 0.3:
                self._face(1 if math.cos(self.heading) > 0 else -1, now)
        self.trip = True
        self.state_until = math.inf
        self.legs.append(("walk" if self.gait == "walk" else "glide", self.x, goal[0], now))

    # --- the repertoire: portal, puff, glide, edge walk, jump, climb (INBOX 1670, 13:22Z to 13:32Z) ----

    def _leg_mode(self, goal: tuple[float, float], then: str) -> str:
        """How to get to `goal`: a leg longer than a third of the work area, or through its middle third,
        is never walked; a portal, a puff or a walk off one edge and in from the other. Short ones near
        an edge are walked (glided), with the odd portal or puff for variety."""
        if self.reduced:
            return "fade"
        if self.plain_legs:
            return "walk"
        m = self.current_monitor()
        area, w = m.area, self.size[0]
        long_leg = tv.far(self.x, goal[0], area) or tv.crosses_middle(self.x, goal[0], area, w)
        flat = abs(goal[1] - self.ground_y(m)) < 8 * self._scale() and abs(self.y - self.ground_y(m)) < 8 * self._scale()
        opposite = (self.x + w / 2 - (area[0] + area[2]) / 2) * (goal[0] + w / 2 - (area[0] + area[2]) / 2) < 0
        mode = tv.pick_mode(
            self.rng, gait=self.gait, long_leg=long_leg, mood=self.mind.mood(self.now, self.hour),
            recent=self.modes[-3:], edge_ok=flat and opposite and self.perch is None,
        )
        return mode

    def _box_at(self, x: float, y: float, frame: str = "stand") -> tv.Rect:
        """The drawn box of `frame` for a window at (x, y), in screen px."""
        flip = self.facing < 0
        left, top, right, bottom = self._box(frame, flip)
        dx, dy = self._flip_dx(frame, flip), self._dy(frame)
        return x + left + dx, y + top + dy, x + right + dx, y + bottom + dy

    def _clear_of_caret(self, gx: float, gy: float) -> tuple[float, float]:
        """A goal that is not over the text box: the nearer screen edge if it is."""
        if self.caret is None:
            return gx, gy
        k, m = self._scale(), self.current_monitor()
        keep = tv.padded(self.caret, tv.CARET_MARGIN * k)
        if not tv.overlaps(self._box_at(gx, gy), keep):
            return gx, gy
        for side in sorted((-1, 1), key=lambda sd: abs(tv.edge_x(sd, m.area, self.size[0]) - gx)):
            x = tv.edge_x(side, m.area, self.size[0], 4 * k)
            if not tv.overlaps(self._box_at(x, gy), keep):
                return x, gy
        return gx, gy

    def _keep_off_caret(self, now: float) -> None:
        """Over the foreground window's text box (padded): step aside to the nearest edge on the taskbar
        line, in a puff (a fade when reduced), inside a second."""
        if now < self.evade_ready or self.caret is None:
            return
        k, m = self._scale(), self.current_monitor()
        frame = self._frame(now)
        x, y, _clip = self._display(frame)
        left, top, right, bottom = self._box(frame, self.facing < 0)
        keep = tv.padded(self.caret, tv.CARET_MARGIN * k)
        if not tv.overlaps((x + left, y + top, x + right, y + bottom), keep):
            return
        self.evade_ready = now + 1.0
        ground = self.ground_y(m) if self.perch is None else m.area[3] - self.size[1]
        for side in sorted((-1, 1), key=lambda sd: abs(tv.edge_x(sd, m.area, self.size[0]) - self.x)):
            tx = tv.edge_x(side, m.area, self.size[0], 4 * k)
            if not tv.overlaps(self._box_at(tx, ground), keep):
                self.perch = self.target = None
                self._start_warp("fade" if self.reduced else "puff", (tx, ground), "evade", now)
                return

    def _start_warp(self, mode: str, dest: tuple[float, float], then: str, now: float) -> None:
        """Vanish here and appear at `dest`, then do `then`. A portal opens a ring of nebula beside it,
        it steps in and the ring closes; a puff is a cloud; a fade is only the picture (reduced motion);
        an edge walk slips off the near edge of the screen and comes in from the far one."""
        src = (self.x, self.y)
        wp = tv.warp_for(mode, self.rng)
        side = tv.nearest_edge(self.x, self.current_monitor().area, self.size[0])
        self._enter("warp", now)
        self.then = then
        self.legs.append((mode, src[0], dest[0], now))
        if mode != "edge":
            self.modes.append(mode)
        self.warp = {
            "kind": mode, "t0": now, "w": wp, "src": src, "dst": dest, "moved": False, "side": side,
            "face": self.facing,
        }
        self.state_until = now + wp.total
        if mode == "edge":
            self.peek_edge = "left" if side < 0 else "right"
            self.facing = side

    def _warp_view(self, now: float) -> tuple[tuple[str, float, int] | None, float, float]:
        """(fx, alpha, squeeze) of the warp at `now`: its effect, how much of the picture shows, and how
        far it has stepped into the ring."""
        w = self.warp
        if w is None:
            return None, 1.0, 0.0
        wp, kind = w["w"], w["kind"]
        t = now - w["t0"]
        if t < wp.out:
            phase, u = "out", t / wp.out
        elif t < wp.out + wp.gap:
            phase, u = "gap", 1.0
        else:
            phase, u = "in", min(1.0, (t - wp.out - wp.gap) / wp.back)
        if phase == "gap":
            return None, 0.0, 1.0
        v = u if phase == "out" else 1.0 - u  # the way back is the way out, backwards
        if kind == "portal":
            ring = bh.smooth(v / 0.35) * (1.0 - bh.smooth((v - 0.8) / 0.2))
            alpha = 1.0 - bh.smooth((v - 0.35) / 0.5)
            squeeze = bh.smooth((v - 0.2) / 0.6)
            fx = ("portal", ring, w["face"] if phase == "out" else self.facing)
        elif kind == "puff":
            alpha = 1.0 - bh.smooth(v / 0.6)
            squeeze = 0.0
            fx = ("puff", math.sin(math.pi * min(1.0, u)), 0)
        elif kind == "fade":
            alpha, squeeze, fx = 1.0 - bh.smooth(v), 0.0, None
        else:
            alpha, squeeze, fx = 1.0, 0.0, None
        return fx, alpha, squeeze

    def _do_warp(self, now: float, dt: float) -> None:
        w = self.warp
        if w is None:
            self._enter("stand", now)
            return
        wp, kind = w["w"], w["kind"]
        t = now - w["t0"]
        if not w["moved"] and t >= wp.out:
            w["moved"] = True
            self.x, self.y = w["dst"]
            if kind == "edge":
                self.peek_edge = "right" if w["side"] < 0 else "left"  # in from the far edge
                self.facing = -w["side"]
        if kind == "edge":
            self.sink = bh.smooth(t / wp.out) if t < wp.out else 1.0 if t < wp.out + wp.gap else 1.0 - bh.smooth((t - wp.out - wp.gap) / wp.back)
        if t >= wp.total:
            self._finish_warp(now)

    def _finish_warp(self, now: float) -> None:
        w = self.warp
        if w is None:
            return
        self.x, self.y = w["dst"]
        self.sink, self.peek_edge, self.warp = 0.0, None, None
        self.goal = None
        self._arrive(now)

    def _start_edge(self, dest: tuple[float, float], then: str, now: float) -> None:
        """Walk to the near edge, slip off it, come in from the far edge already walking."""
        m = self.current_monitor()
        side = tv.nearest_edge(self.x, m.area, self.size[0])
        y = self.ground_y(m)
        self.edge_plan = (dest, then)
        exit_x = tv.edge_x(side, m.area, self.size[0])
        if abs(exit_x - self.x) > 6 * self._scale():
            self._go((exit_x, y), "edgeexit", now, plain=True)
        else:
            self.then = "edgeexit"
            self._arrive(now)

    def _arrive_edge(self, now: float, exiting: bool) -> None:
        plan = self.edge_plan
        if plan is None:
            self._enter("stand", now)
            return
        m = self.current_monitor()
        if exiting:
            side = tv.nearest_edge(self.x, m.area, self.size[0])
            self._start_warp("edge", (tv.edge_x(-side, m.area, self.size[0]), self.ground_y(m)), "edgein", now)
        else:
            self.edge_plan = None
            self._go(plan[0], plan[1], now, plain=True)

    # --- relocation: a home is by an edge, never the middle ----------------------------------

    def _maybe_relocate(self, now: float) -> None:
        if self.roam and not self.reduced and self.home_x is not None and self.perch is None:
            m = self.current_monitor()
            if tv.in_middle(self.home_x, m.area, self.size[0]) and self.relocate_at is None:
                self.relocate_at = now + RELOCATE_AFTER
                if self.state == "stand":
                    self.state_until = min(self.state_until, self.relocate_at)

    def _relocate(self, now: float) -> None:
        m = self.current_monitor()
        self.relocate_at = None
        if self.home_x is not None and tv.in_middle(self.home_x, m.area, self.size[0]):
            side = tv.nearest_edge(self.home_x, m.area, self.size[0])
            self.home_x = tv.edge_x(side, m.area, self.size[0], HOME_INSET * self._scale())
        if self._away():
            self._go_home(now)

    def _face(self, direction: int, now: float) -> None:
        """Turn to face a way: a squeeze to a sliver and back (`TURN_FOR`), never a snap. The
        facing itself changes at the narrowest point."""
        if self.turn_to != 0:  # a turn under way: the latest word wins, it never ends facing a stale way
            if direction == self.facing:
                self.turn_to = 0
            elif direction != self.turn_to:
                self.turn_to, self.turn_started = direction, now
            return
        if direction == self.facing:
            return
        if not self.reduced and self.metrics and self.state not in ("held", "fly", "fall"):
            self.turn_to, self.turn_started = direction, now
        else:
            self.facing = direction

    def _turning(self, now: float) -> bool:
        if self.turn_to == 0:
            return False
        u = (now - self.turn_started) / TURN_FOR
        if u >= 0.5 and self.facing != self.turn_to:
            self.facing = self.turn_to
        if u >= 1.0:
            self.turn_to = 0
            return False
        return True

    def _pace(self, now: float, left: float | None) -> float:
        """The share of full speed now: eased in over EASE_IN s from the start of a leg, and eased
        out over the last EASE_OUT px to its goal; a step is slower, a dash faster."""
        k = {"step": STEP_K, "dash": DASH_K}.get(self.mode, 1.0)
        rise = bh.smooth((now - self.walk_started) / EASE_IN)
        fall = 1.0 if left is None else bh.smooth(left / (EASE_OUT * self._scale()))
        return k * max(0.12, min(rise, max(0.2, fall)))

    def _yields(self, now: float, ahead: float) -> bool:
        """Wait, rather than pass under a busy pointer: the pointer within YIELD_NEAR px of the path
        ahead and moved lately. Never longer than YIELD_MAX s, then it goes on."""
        p = self.pointer
        busy = p is not None and now - self.pointer_busy_at < 1.0
        if p is None or not busy:
            self.yield_since = None
            return False
        k = self._scale()
        cx = self.x + self.size[0] / 2
        near = abs(p[0] - (cx + ahead)) < YIELD_NEAR * k and abs(p[1] - (self.y + self.size[1] / 2)) < self.size[1]
        if not near:
            self.yield_since = None
            return False
        if self.yield_since is None:
            self.yield_since = now
        return now - self.yield_since < YIELD_MAX

    def _rise(self, to: tuple[float, float], then: str, now: float, drawn_from: float | None = None) -> None:
        """Move smoothly to a point. The path is of where it is drawn, so the swap of frames
        (each with its own foot offset) never shows as a step."""
        self.then = then
        if drawn_from is None:
            drawn_from = self.y + self._dy(self._frame(now))
        self._enter("rise", now)
        self.phase_to = to
        self.phase_from = (self.x, drawn_from)

    def _arrive(self, now: float) -> None:
        """At the goal of a trip: what it came for."""
        then, self.goal = self.then, None
        if then == "card":
            self._arrive_card(now)
        elif then in ("edgeexit", "edgein"):
            self._arrive_edge(now, then == "edgeexit")
        elif then in ("climbside", "climbtop", "climb", "perch"):
            self._arrive_climb(then, now)
        elif then == "hang":
            self._arrive_hang(now, self.current_monitor())
        elif then.startswith("peek_"):
            self._arrive_peek(then[5:], now)
        else:
            self._arrive_plain(then, now)

    def _arrive_climb(self, then: str, now: float) -> None:
        """The steps of getting onto a window top: up its side, over its edge, a leap, the stand."""
        p = self._target_here()
        if p is None:  # the window went while it was on the way
            self.target = None
            if then == "climbtop":
                self._start_fall(0.0)
            else:
                self._enter("stand", now)
        elif then == "climbside":
            self.legs.append(("climb", self.x, self.x, now))
            self._rise((self.x, p.top - self.size[1]), "climbtop", now)
        elif then == "climbtop":
            inner = min(max(self.x + (self.size[0] * 0.6 if self.x < p.left else -self.size[0] * 0.6), p.left), p.right - self.size[0])
            self._rise((inner, p.top - self.size[1]), "perch", now)
        elif then == "climb":
            self.target = p
            self.legs.append(("jump", self.x, self.x, now))
            self._enter("leap", now)
        else:
            self._stand_on(p, now)
            self.perch_until = now + self.rng.uniform(*REST_FOR)
            self._enter("stand", now)
            self.state_until = self.perch_until

    def _arrive_peek(self, edge: str, now: float) -> None:
        self.peek_edge = edge
        self.sink_max = PEEK_HEAD if edge == "bottom" else PEEK_SIDE
        if edge == "left":
            self.facing = 1
        elif edge == "right":
            self.facing = -1
        self._enter("peek", now)

    def _arrive_plain(self, then: str, now: float) -> None:
        if then == "follow":
            self._enter("stand", now)
            self.state_until = now + 1.5
        elif then == "home":
            self._enter("land" if self.mode == "dash" else "stand", now)
        else:
            self._enter("stand", now)
            if then == "rest":
                self.state_until = now + self.rng.uniform(*REST_FOR)
            if then in ("clock", "nap", "greet", "settle"):
                self._arrive_trip(then, now)

    def _do_stand(self, now: float, dt: float) -> None:
        self._ambient(now)
        self._after_stand(now)

    def _do_sit(self, now: float, dt: float) -> None:
        self._ambient(now)
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
            if self.mind.event == "startled" and not self.reduced and now - self.mind.event_at < 20.0:
                self.mind.feel("proud", now)  # a little pleased with the landing; the landing was the one settle
            if self.nap_after_land and not self.reduced:
                self.nap_after_land = False
                self._enter("sleep", now)
                return
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
            rest = self.ground_y(m)
            self.goal = (self._leg_x(left, right), self.rng.uniform(max(top, rest - FLOAT_BAND * self.size[1]), rest))
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
        if self._turning(now) or self._yields(now, math.cos(self.heading) * 90 * scale):
            self.walk_started = now  # the pace eases in from when it moves, not from when it was told
            return
        speed = FLOAT_SPEED * scale * self._pace(now, dist)
        self.x = min(max(self.x + math.cos(self.heading) * speed * dt, left), right - self.size[0])
        high = top - (self._lift() if self.then == "hang" and self.trip else 0.0)
        if not self.trip:  # a wander turns wide, so the band is held by the clamp too, not only by the goal
            high = max(high, self.ground_y(m) - FLOAT_BAND * self.size[1])
        self.y = min(max(self.y + math.sin(self.heading) * speed * dt, high), self.floor_y(m))
        if abs(math.cos(self.heading)) > 0.5:
            self._face(1 if math.cos(self.heading) > 0 else -1, now)
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

    def _rise_drawn(self, now: float) -> float:
        """Where a rise draws the window's top at `now`: the path is of what is drawn."""
        t = min(1.0, (now - self.phase_started) / RISE_FOR)
        t = t * t * (3 - 2 * t)
        return self.phase_from[1] + (self.phase_to[1] - self.phase_from[1]) * t

    def _do_rise(self, now: float, dt: float) -> None:
        t = min(1.0, (now - self.phase_started) / RISE_FOR)
        t = t * t * (3 - 2 * t)
        self.x = self.phase_from[0] + (self.phase_to[0] - self.phase_from[0]) * t
        self.y = self._rise_drawn(now) - self._dy(self._frame(now))
        if now >= self.state_until:
            self._arrive(now)

    def _do_hang(self, now: float, dt: float) -> None:
        """Hanging is alive: the picture swings from the grip (`_target_pose`), and now and then it glances
        round (a turn). It lets go by its own choice: climbs up onto the window's edge, or drops."""
        if now >= self.hang_glance_at and now < self.state_until - 3.0:
            self._face(-self.facing, now)
            self.hang_glance_at = now + self.rng.uniform(*HANG_GLANCE)
        if now >= self.state_until:
            self._end_hang(now)

    def _end_hang(self, now: float) -> None:
        held = self._hold_of(self.hang_on) if self.hang_on is not None else None
        mood = self.mind.mood(now, self.hour)
        if held is not None and mood in ("curious", "happy", "proud", "bored") and self.rng.random() < 0.7:
            w, h = self.size
            x = min(max(self.x, held.left), held.right - w)
            if held.top - h >= self.current_monitor().area[1]:
                self.target = held
                self.legs.append(("climb", self.x, x, now))
                self._rise((x, held.top - h), "perch", now)
                return
        self._let_go()

    def _let_go(self) -> None:
        """Off the ceiling: a walker falls, a floater drifts down to its hover height."""
        self._start_fall(0.0)
        # the pose it drops in is taller than the hang: keep all of it on the screen
        m = self.current_monitor()
        if self._open_side(m, "top"):
            self.y = max(self.y, self._ride_limits("fly" if self.state == "fly" else self.state)[2])

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

    def _hit_ceiling(self, m: Monitor, uy0: float, now: float) -> bool:
        """A thrown figure that reaches the top of an open work area takes hold and hangs."""
        top, scale = m.area[1], self._scale()
        if self.vy >= 0 or not self._open_side(m, "top"):
            return False
        self.y = max(self.y, uy0)  # a step may carry it past the top: the drawn box stops at the edge
        if self.y > max(top - self._lift(), uy0):
            return False
        if not self._ceiling_holds():  # it bounces off the top like a side wall and drifts back down
            self.vy = abs(self.vy) * BOUNCE_DAMP
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

    def _ceiling_holds(self) -> bool:
        """Whether the throw now reaching the top was hard and mostly upward (see `CEIL_CATCH`)."""
        vx, vy = self.launch
        return -vy >= CEIL_CATCH * self._scale() and -vy >= CEIL_UPWARD * math.hypot(vx, vy)

    def _track_rest(self, speed: float, dt: float) -> None:
        """Count how long a thrown figure has been slow. Once it has been long enough it is laid
        down for good (a floater's pull back to its hover can creep its speed over the line again,
        and the tumble must not start up on the way to rest) until the next throw."""
        if self.slow_for < FLY_REST_DWELL:
            self.slow_for = self.slow_for + dt if speed < FLY_SPIN_MIN * self._scale() else 0.0

    def _do_fly(self, now: float, dt: float) -> None:
        """Thrown: ballistic (gravity for a walker; for a floater air drag and a gentle
        pull to its hover height). Bounces off the outer walls, hangs from the ceiling."""
        scale = self._scale()
        m = self.ground_mon if self.grounded and self.ground_mon else self.current_monitor()
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
        self._track_rest(speed, dt)
        self._spin(dt, speed)
        uy0, uy1 = self._fly_walls(m, now)
        if self._hit_ceiling(m, uy0, now):
            return
        floor = min(self.floor_y(m), uy1) if self._open_side(m, "bottom") else self.floor_y(m)
        if floater:
            self.y = min(self.y, floor)
            # at the drawn-box limit counts as down: the tumble's box is taller than the figure, so the
            # limit can sit above the rest line, and it hung there in the limp pose (INBOX 1670)
            if speed < 25 * scale and self._righted() and (abs(self.ground_y(m) - self.y) < 4 * scale or self.y >= floor - 0.5):
                self.vx = self.vy = 0.0
                self.y = self.ground_y(m)
                self.settled_now = True
                self._enter("stand", now)
        elif self.y >= floor:
            self._land_tumble(m, floor, dt, now)

    def _fly_walls(self, m: Monitor, now: float) -> tuple[float, float]:
        """Bounce off an open side wall (the walls are of what is drawn: the tumble's widest frame, not the
        window around it); returns the drawn box's top and bottom limits."""
        ux0, ux1, uy0, uy1 = self._ride_limits("fly")
        if self.x < ux0 and self._open_side(m, "left"):
            self.x, self.vx = ux0, abs(self.vx) * BOUNCE_DAMP
            self.bonk_until = now + BONK_FOR
            self._spin_contact(1.0)
        elif self.x > ux1 and self._open_side(m, "right"):
            self.x, self.vx = ux1, -abs(self.vx) * BOUNCE_DAMP
            self.bonk_until = now + BONK_FOR
            self._spin_contact(-1.0)
        return uy0, uy1

    def _land_tumble(self, m: Monitor, floor: float, dt: float, now: float) -> None:
        """A walker's tumble reaches the floor: it slides to a stop and rights itself there, then lands."""
        self.y, self.vy = floor, 0.0
        if not self.grounded:
            self.grounded = True
            self.ground_mon = m  # the slide stays on the screen it landed on: a seam would jump the floor under it
            self._spin_contact(1.0 if self.vx >= 0 else -1.0)
        self.vx *= math.exp(-6.0 * dt)
        self.x = min(max(self.x, m.area[0]), m.area[2] - self.size[0])
        if self._righted() and abs(self.vx) < 20 * self._scale():
            self.vx = 0.0
            self.y = self.floor_y(m)
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
        if self._turning(now):
            self.walk_started = now
            return
        left = abs(self.goal[0] - self.x) if self.goal is not None else None
        if self._yields(now, self.facing * 90 * self._scale()):
            self.walk_started = now
            return
        step = WALK_SPEED * self._scale() * dt * self.facing * self._pace(now, left)
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
        return max(-hi, min(hi, turn * rate + SPIN_SWIRL * swirl))

    def _spin(self, dt: float, speed: float) -> None:
        """One step of the turn: its own drag, and once the flight is slow (or on the floor) an eased turn
        to the nearest upright."""
        self.omega *= math.exp(-SPIN_DRAG * dt)
        slow = speed < RIGHT_SPEED * self._scale() or self.grounded
        self.right_t = self.right_t + dt if slow else 0.0
        if self.right_t > 0.0:
            gain = bh.smooth(min(1.0, self.right_t / RIGHT_RAMP))
            err = self.angle - round(self.angle / (2 * math.pi)) * 2 * math.pi
            self.omega -= gain * (RIGHT_W * RIGHT_W * err + 2 * RIGHT_W * self.omega) * dt
        self.angle += self.omega * dt
        if self.slow_for >= FLY_REST_DWELL and self._righted():
            self.laid = True  # laid down for good until the next throw: the held pose never swaps back to the tumble

    def _righted(self) -> bool:
        """Upright and still turning no more than a drift: safe to lay down."""
        err = self.angle - round(self.angle / (2 * math.pi)) * 2 * math.pi
        return abs(err) < 0.06 and abs(self.omega) < 0.5

    def _spin_contact(self, push: float) -> None:
        """A bounce takes some of the turn, reverses it and adds the kick of the surface (`push` -1 to 1)."""
        hi = SPIN_OMEGA[1]
        self.omega = max(-hi, min(hi, -SPIN_CONTACT * self.omega + SPIN_SWIRL * 0.5 * push))

    def _start_fly(self, vx: float, vy: float, swirl: float = 0.0) -> None:
        self.vx, self.vy = vx, vy
        self.launch = (vx, vy)
        self.slow_for = self.right_t = 0.0
        self.grounded = self.laid = False
        self.y += self._dy(self._frame(self.now)) - self._dy("spin0")  # drawn where it was
        self.angle, self.omega = 0.0, self._launch_spin(vx, vy, swirl)
        if abs(vx) > 1:
            self.facing = 1 if vx > 0 else -1
        self._enter("fly", self.now)

    # --- the pointer ---------------------------------------------------------------------------

    def _notice(self, now: float, pointer: tuple[int, int]) -> None:
        if self.state not in ("stand", "walk", "drift", "sit", "sleep") or now < self.notice_ready:
            return
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
            frame = self._frame(now)
            drawn_x, drawn_y, _clip = self._display(frame)
            #: Held by where it is drawn: the pointer keeps its place on the figure.
            self.grab = (px - drawn_x, py - drawn_y)
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
            self.x = px - self.grab[0] - self._flip_dx("held", self.facing < 0)
            self.y = py - self.grab[1] - self._dy("held")
            self._keep_on_screen()
            self.trail.append((self.now, px, py))
            del self.trail[:-16]

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
        self.mind.feel("startled", now)
        m = self.current_monitor()
        x0, x1, _y0, _y1 = self._ride_limits("held")
        self.x = min(max(self.x, max(x0, m.area[0] - self._ride_box("held")[0])), min(x1, m.area[2] - self._ride_box("held")[2]))
        velocity = None if self.reduced else self._throw_velocity(now, px, py)
        if velocity is not None:  # a throw is a throw: only a release that is not one takes hold near an edge
            self._start_fly(*velocity, self._swirl(now, px, py))
        elif not self._grab_edge(now):
            self._drop(now)

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

    # --- the answer ------------------------------------------------------------------------------------

    def _frame(self, now: float) -> str:
        s = self.state
        if s in ("card", "walk", "drift"):
            return self._step_frame(now, s)
        if s == "act":
            return bh.activity_frame(bh.ACTIVITIES[self.act or "breathe"], (now - self.act_started) / max(0.01, self.act_len))
        if s == "crouch":
            return "land"
        if s == "warp" and self.warp is not None and self.warp["kind"] == "edge":
            return f"walk{int((now - self.warp['t0']) / (0.75 / self.walk_frames)) % self.walk_frames}"
        if s in FRAME_OF:
            return FRAME_OF[s]
        if s == "fly":
            return "hop" if now < self.bonk_until else self._fly_frame()
        if s in ("rise", "peek"):
            return self._edge_frame(now)
        if s == "stand":
            return self._stand_frame(now)
        if s == "sit" and self.flash:  # eyelids over the sat figure's eyes (`SpriteSet` derives the frame)
            return "sitblink"
        return s  # sit, sleep, wave, fall, land

    def _step_frame(self, now: float, s: str) -> str:
        if s == "card":
            return f"card{int(now / CARD_SWAP) % 2}"
        if self.card is not None:
            return f"card{int((now - self.walk_started) / CARD_WALK_SWAP) % 2}"
        return f"walk{int(self.travel / (STRIDE * WALK_FRAMES / self.walk_frames * self._scale())) % self.walk_frames}"

    def _edge_frame(self, now: float) -> str:
        if self.state == "rise":
            frame = "hop" if self.gait == "walk" else f"walk{int((now - self.phase_started) / (0.75 / self.walk_frames)) % self.walk_frames}"
            if self.then == "hang" and self._rise_drawn(now) + self._box(frame)[1] < self.current_monitor().area[1]:
                return "hang"  # its head would pass the top of the screen: hands up, in the pose that fits
            return frame
        return "stand" if self.sink < self.sink_max * 0.5 or now - self.peek_started < 0.8 else "look"

    def _stand_frame(self, now: float) -> str:
        if self.flash:
            return self.flash[0]
        return f"idle{self._idle_index(now)}" if self._idling() else "stand"

    def _idling(self) -> bool:
        """Standing with life in its parts: not reduced, frames present. Typing keeps it in
        place, not lifeless (INBOX 1670: "it is also not animated")."""
        return self.state == "stand" and not self.reduced and self.idle_frames > 0

    def _idle_fps(self) -> float:
        """Frames a second: a shipped set of fewer frames plays slower, so the cycle stays 4 s."""
        return IDLE_FPS * max(1, self.idle_frames) / IDLE_FRAMES

    def _idle_index(self, now: float) -> int:
        return int((now - self.idle_start) * self._idle_fps() + 1e-6) % self.idle_frames

    def _wake(self, now: float) -> int | None:
        s = self.state
        if s == "card":  # waiting with a card, even when still: it swaps and it runs out
            return max(MIN_WAKE_MS, min(int(CARD_SWAP * 1000), int(math.ceil((self.state_until - now) * 1000))))
        if self.reduced:
            return None
        if s in ("walk", "held", "drift", "hang", "rise", "peek", "emerge", "crouch", "warp") or self.turn_to:
            return self._moving_wake(s)
        if s == "act":
            soonest = min(self.state_until, self._next_pose_change(now, 0.5))
            return max(MIN_WAKE_MS, int(math.ceil((soonest - now) * 1000)) + 1)
        if s in ("fall", "hop", "fly", "leap"):  # before the tail: it swings through a fall, and the window moves fastest here
            return TICK_FALL_MS
        if self._follow_moving():  # the tail still swings, or the body is easing to its pose
            return TAIL_TICK_MS
        if s == "pressed":
            return None
        if s in REST_LIFE:  # alive in place: the next step of the breath or the tail (or a sit's blink), else the pointer look
            nxt = self._next_life_change(now)
            if s == "sit":
                nxt = min(nxt, self.flash[1] if self.flash else self.next_ambient)
            return max(REST_DRAW_MS if not self.flash else MIN_WAKE_MS, min(POLL_QUIET_MS, int(math.ceil((nxt - now) * 1000))))
        return self._wake_at_rest(now, s)

    def _wake_at_rest(self, now: float, s: str) -> int | None:
        due = self._due(now)
        soonest = min(due)
        if s == "stand" and not self.reduced and self.roam:  # it looks at the pointer now and then
            soonest = min(soonest, now + POLL_QUIET_MS / 1000.0)
        if soonest == math.inf:
            return None
        return max(MIN_WAKE_MS, int(math.ceil((soonest - now) * 1000)) + 1)

    def _moving_wake(self, s: str) -> int:
        if s == "hang" and not self.turn_to:  # the picture swings from the grip; the window does not move
            return HANG_TICK_MS
        return TICK_WALK_MS

    def _follow_moving(self) -> bool:
        if not self.tail.settled():
            return True
        return max(abs(a - b) for a, b in zip(self.cur, self.pose_goal)) > 0.006

    def _due(self, now: float) -> list[float]:
        """The times a calm state next needs a redraw: its end, an ambient act, an idle frame."""
        s = self.state
        due = [self.state_until] if s != "stand" or (self.roam and not self.reduced) else []
        if s == "stand":
            due += [self.flash[1]] if self.flash else [self.next_ambient]
            due.append(self.last_active + IDLE_SIT)
        if self._idling():  # the next idle frame: a redraw only when the index changes
            due.append(self.idle_start + (math.floor((now - self.idle_start) * self._idle_fps() + 1e-6) + 1) / self._idle_fps())
        return due

    def _next_pose_change(self, now: float, horizon: float = 1.0) -> float:
        """The next time the body pose crosses a step of the cache grid, looking ahead."""
        base = bh.quantised(self.cur)
        t = now
        while t < now + horizon:
            t += 0.05
            if bh.quantised(self._target_pose(t)) != base:
                return t
        return now + horizon

    def _display(self, frame: str) -> tuple[float, float, tuple[int, int, int, int] | None]:
        """Where the window is drawn and which part of the frame shows: the rest
        position, less the sink behind an edge."""
        w, h = self.size
        x, y = self.x, self.y
        # a bonk shows the startle frame in mid-air: no foot offset of its own
        y += self._dy("held" if self.state == "fly" else frame)
        x += self._flip_dx(frame, self.facing < 0)
        if self.sink <= 0 or self.peek_edge is None:
            return x, y, None
        if self.peek_edge == "bottom":
            hidden = round(self.sink * h)
            # cut where the work area ends, not where the (lower) window does
            return x, y + hidden, (0, 0, w, max(0, h - hidden - round(self._dy(frame))))
        hidden = round(self.sink * w)
        if self.peek_edge == "left":
            return x - hidden, y, (hidden, 0, w, h)
        return x + hidden, y, (0, 0, w - hidden, h)

    def _output(self, now: float) -> Output:
        frame = self._frame(now)
        x, y, clip = self._display(frame)
        fx, alpha, _squeeze = self._warp_view(now) if self.state == "warp" else (None, 1.0, 0.0)
        return Output(
            frame, int(round(x)), int(round(y)), self.facing < 0, self._wake(now),
            self.click_now, self.settled_now, clip, self.card_clicked, self._pose(), fx, round(alpha * 16) / 16.0,
        )
