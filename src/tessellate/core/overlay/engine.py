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
from typing import Any

from . import behaviour as bh
from . import extras
from . import presence as pr
from . import travel as tv
from . import vitals
from . import landing as ld, wisps  # tests patch `eng.ld.smack` and `eng.wisps.phase`
from .engine_consts import (
    ACTS, AMBIENT_EVERY, AMBIENT_SKEW, AWAY, AWAY_STAND_FOR, BIG_EVERY, BIG_FIRST, BLINK_FOR,
    CARD_FOR, CARD_STAND, CARD_SWAP, CARRY_STAGES, CLIMB_FIRST, COME_FOR, COME_GAP, COME_MOVED,
    COME_WAIT, CROUCH_FOR, Cover, DASH_K, DASH_OVER, DEST_RUN, DIZZY_WAIT, DOUBLE_GAP, DOUBLE_SHARE,
    DRAG_STEP_MAX, DRIFT_BREATH, DRIFT_BREATH_S, EASE_IN, EASE_OUT, EMERGE_FOR, EXERTING,
    EXHALE_AFTER, EXHALE_DIP, EXHALE_FOR, FLING_FACE, FLOAT_BAND, FLOAT_LEG, FLOAT_SPEED,
    FLOAT_TURN, FLOW_CALM_MS, FLOW_SLEEP_MS, FLOW_SPEED_MAX, FLOW_SPELL_MS, FLOW_TICK_MS,
    FOLLOW_FOR, FOLLOW_GAP, GREET_AFTER, GROUNDED, HANG_DRAG_IN, HANG_ENDS, HANG_FOR, HANG_GLANCE,
    HANG_HANDS, HANG_KICK, HANG_KICK_FOR, HANG_LEAP, HANG_PERIOD, HANG_SWING, HANG_TICK_MS,
    HANG_TRIP_WEIGHT, HOLD_FIXED, HOLD_RANGES, HOME_INSET, HOME_KEEP, HOP_FOR, HOVER, IDLE_FRAMES,
    KICK_HZ, LEAN_MAX, LEAP_BASE, LEAP_SPEED, LIFT_SY, LIVELY, LONELY_AFTER,
    LONG_WALK_GAP, LONG_WALK_WEIGHT, LOOK_FOR, LOOK_SHARE, MAX_DT, MIN_WAKE_MS, Monitor, NAP_FOR,
    NOTICE_NEAR, Output, PACE_GAP, PACE_SLEW, PEEK_BEHIND, PEEK_HEAD, PEEK_OPEN, PEEK_PLAN,
    PEEK_SIDE, PEEK_TOP_PEER, PEEK_TOP_PLAN, PEEK_TOP_SHOWN, PEEK_TUCK, PERCH_MOVED, PLAIN_THENS,
    POLL_QUIET_MS, POSE_DT_MAX, POSE_DT_WAKE, POSE_DYN, POSE_GAP_FREE, POSE_LOOK_STEP, POSE_OFF,
    POSE_RATE, Perch, QUIET_RECHECK, Q_BREATH, REACHED, REACT_FOR, RELOCATE_AFTER, REST_DRAW_MS,
    REST_FOR, REST_LIFE, RESUMED_THENS, RISE_FOR, RUN_MIN, Rect, SCRABBLE_DRAG, SCRABBLE_HZ,
    SHIFT_FOR, SHIFT_LEAN, SIGH_FOR, SLEEP_AFTER, SPELL_MOVE, SPELL_QUIET, SPELL_ROOM, SPELL_SETTLE,
    SPIN_FRAMES_ENGINE, SPIN_STEPS, SQUASH, SQUASH_FOR, STAND_FAMILY, STAND_LEAN, STAND_LEAN_S,
    STEP_K, STEP_UNDER, STRIDE, STROLL, SWING_BOOST, SWING_FOR, SWING_REACH, TAIL_LAG, TAIL_TICK_MS,
    TAIL_WANDER, TAIL_WANDER_S, TICK_FALL_MS, TICK_WALK_MS, TRIP_EVERY, TRIP_FIRST,
    TRIP_OVERDUE_MAX, TRIP_OVERDUE_S, TUCK_FRESH, TUCK_PLAN, TUCK_REACH, TURN_FOR, TuckSpot,
    VX_SMOOTH_S, WALK_FOR, WALK_FRAMES, WALK_SPEED, WANDER_MIN, WARP_MIN, WAVE_GAP, WAVE_IDLE,
    WAVE_NEAR, YIELD_BRAKE_S, YIELD_MAX, YIELD_NEAR, _adjoins, _same_screens, stand_x,
)
from .engine_consts import (  # re-exported: tests and `runner` read them as `eng.NAME`
    AWAY_DRIFT, AWAY_FALL, AWAY_FOR, BOUNCE_DAMP, Bar, CEIL_CATCH, CEIL_LEAVE, CEIL_TILT,
    CLIMB_EVERY, CLIMB_SOON, FLING_SPEED, IDLE_FPS, NOTICE_COOLDOWN, PERCH_THROW,
    SLIP_SPEED, SPIN_DRAG, SPIN_OMEGA, TAIL_LAYER_MS, TAIL_TOUCHED_FOR, THROW_MAX, THROW_MIN,
    TITLE_BAR, WALL_SCRABBLE, WAVE_FOR, LAND_FOR, perch_room,
)
__all__ = [
    "AWAY_DRIFT", "AWAY_FALL", "AWAY_FOR", "BOUNCE_DAMP", "Bar", "CEIL_CATCH", "CEIL_LEAVE",
    "CEIL_TILT", "CLIMB_EVERY", "CLIMB_SOON", "FLING_SPEED", "IDLE_FPS",
    "NOTICE_COOLDOWN", "PERCH_THROW", "SLIP_SPEED", "SPIN_DRAG", "SPIN_OMEGA", "TAIL_LAYER_MS",
    "TAIL_TOUCHED_FOR", "THROW_MAX", "THROW_MIN", "TITLE_BAR", "WALL_SCRABBLE", "WAVE_FOR",
    "perch_room", "LAND_FOR", "ld", "wisps",
]
from .engine_deskacts import SIT_REGISTERED, DeskActsMixin
from .engine_flight import FlightMixin
from .engine_frames import FramesMixin
from .engine_input import InputMixin
from .engine_roam import RoamMixin
from .engine_touch import TouchMixin

#: Not touched for this long: sits, then sleeps. Ten and twenty minutes (the owner's
#: open call, taken): it keeps doing small acts while the person is away from the
#: keyboard, since the big acts (hang, peek) come two to four minutes apart.
IDLE_SIT = 600.0
IDLE_SLEEP = 1200.0


class Engine(RoamMixin, FlightMixin, InputMixin, FramesMixin, DeskActsMixin, TouchMixin):
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
        wave_frames: int = 0,
        extra_frames: frozenset[str] = frozenset(),
        rng: random.Random | None = None,
        now: float = 0.0,
    ) -> None:
        self.size = size
        self.idle_frames = max(0, int(idle_frames))
        self.walk_frames = max(1, int(walk_frames))
        self.wave_frames = max(0, int(wave_frames))
        #: Which of `sprites.EXTRA_FRAMES` the look ships; the others draw their `EXTRA_FALLBACK`.
        self.extra_frames = frozenset(extra_frames)
        self._init_rng_and_config(monitors, roam, reduced, rng, gait, hang_top)
        self._init_state_and_blink(now)
        self._init_press_and_tumble(now)
        self._init_perch_and_cards(now, roam_windows)
        self._init_mind_and_flow(now)
        self._init_hang_and_carry(now)
        x, y = home if home is not None else self._default_home()
        self.x, self.y = float(x), float(y)
        self._place_on_floor()
        self.home_x = self.x
        #: When the person last chose its home from the menu (`_wander`); -inf for never.
        self.homed_at = -math.inf
        self.last_x = self.x
        self.last_y = self.y
        #: Its props, its face, its answers to the pointer and the screen (`extras.py`).
        self.ex = extras.Extras(self)
        self._enter("stand" if not reduced else "sit", now)
        self._maybe_relocate(now)

    def _init_rng_and_config(self, monitors: list[Monitor], roam: bool, reduced: bool, rng: random.Random | None, gait: str, hang_top: float) -> None:
        """The monitors, the random streams and the gait: the choices made once, at the start."""
        self.monitors = list(monitors) or [Monitor((0, 0, 1920, 1040))]
        self.roam = roam
        self.reduced = reduced
        self.rng = rng or random.Random()
        #: Blinks and glances draw from their own stream (seeded from the key's second word, which differs by seed; the first is 2147483648 for every seed; read, not drawn from), so the
        #: far more frequent ambient moments leave every other choice the same for a seed.
        self.life_rng = random.Random(self.rng.getstate()[1][1])
        self.idle_rng = random.Random(self.rng.getstate()[1][1] + 2)
        self._edges: list[float] = [0.0]  # cycle ends, in seconds from `idle_start`; reset when a stand begins
        self.var_rng = random.Random(self.rng.getstate()[1][1] + 1)
        self.act_var = bh.Variation()
        self.gait = "float" if gait == "float" else "walk"
        #: The share of the hang frame's height that is clear above the hands.
        self.hang_top = min(max(float(hang_top), 0.0), 0.5)

    def _init_state_and_blink(self, now: float) -> None:
        """The hang, the base state, blinks and looks."""
        #: The window whose title bar a hang (or the trip to one) takes hold of.
        self.hang_on: Perch | None = None
        #: Edges only a hang takes hold of (a maximised window's title bar, a floating window's bottom edge).
        self.hangs: list[Perch] = []
        #: The kinds of the last few destinations ("floor", "window", "hang"), and a hang a walker walks to first.
        self.dest_hist: list[str] = []
        self.hang_plan: tuple[Perch, float] | None = None
        #: The window a swinging hang will drop to, when it started swinging, and a startled beat before letting go.
        self.swing_to: Perch | None = None
        self.swing_at = 0.0
        self.releasing = False
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
        self.blink_at = -1e9  # when the last blink began
        self.exerted_at = -1e9  # when it last stopped walking, hopping or being carried
        self.rest_breath = 1.0  # the sit's or the sleep's breath period scale, set as it begins
        self.blink_for = BLINK_FOR  # how long this blink's lid is down (`vitals.blink`: longer tired or sleepy)
        self.lively = "usual"  # the menu's Activity: a key of LIVELY
        self.look_after_blink = False  # the blink now showing opens a look (a gaze shift is blinked into)
        self.notice_ready = now
        self.walk_started = now
        self.press: tuple[int, int] | None = None
        self.grab = (0, 0)
        self.carrying = False
        self.hop_from = 0.0
        self.settled_now = False

    def _init_press_and_tumble(self, now: float) -> None:
        """The pointer, the throw and the landing: tumble, lie and wall-slide state."""
        #: Trips that arrived home or at the home the menu chose (`_arrive`): the runner saves the place on a change.
        self.home_arrivals = 0
        self.click_now: str | None = None
        self.trail: list[tuple[float, int, int]] = []
        self.shake_read_at = -1e9  # when the carried pointer was last read for a shake
        self.woke_at = -1e9  # when it last woke from sleep (a pet soon after is shy)
        self.pre_press = "stand"
        self.bonk_until = 0.0
        self.angle = 0.0
        self.squash_at = -math.inf  # when a thrown floater last came to rest
        self.shift_at = -math.inf  # when a sit or a sleep last shifted its weight (A4)
        self.kick = 0.0  # the change of turn rate a contact has still to pay out (`_spin`)
        self.omega = 0.0  # a thrown figure's turn rate, rad/s
        self.right_t = 0.0  # seconds it has been righting itself
        self.grounded = False  # a walker's tumble that has reached the floor
        self.feet_from: tuple[float, float] | None = None  # the turn and rate where a landing on the feet began (`_feet_begin`)
        self.feet_s = 0.0
        self.outcome: str | None = None  # how the last throw came to rest: feet, belly, back (`landing.decide`)
        self.lie_goal: float | None = None  # the quarter turn a body on its back or belly settles to (None: upright)
        self.lie_until = 0.0  # when it gets up, once it lies still
        self.lying = False  # down on its back or belly: not a held tilt, a pose
        self.wall = 0  # -1 or 1 while it slides down a side wall it smacked
        self.wob_kind: str | None = None  # a scrabble or a flail drawn over the true angle (`landing.wobble`)
        self.wob_t0 = 0.0
        self.wob = 0.0  # the scrabble or flail angle added to the true one this tick
        self.passed_at = -math.inf  # when a hard smack last carried it out of one edge and in at the other
        self.wrapping: dict[str, Any] | None = None  # that crossing while it runs: its side, far edge and phase
        self.air_t0 = 0.0  # when the drop since the last upward motion began
        self.laid = False  # upright and slow: the held pose, for good until the next throw
        self.ground_mon: Monitor | None = None  # the screen a walker's tumble landed on
        self.slow_for = 0.0  # seconds a thrown figure has been under FLY_SPIN_MIN
        self.heading = 0.0
        self.goal: tuple[float, float] | None = None
        self.then = "stand"
        self.trip = False

    def _init_perch_and_cards(self, now: float, roam_windows: bool) -> None:
        """Where it roams, the windows it knows, and the cards it holds."""
        self.hover = self.rng.uniform(*HOVER)
        self.big_ready = now + self.rng.uniform(*BIG_FIRST)
        self.roam_windows = roam_windows
        self.windows: list[Perch] = []
        self.perch: Perch | None = None
        self.target: Perch | None = None
        self.perch_until = 0.0
        self.climb_ready = now + CLIMB_FIRST
        #: When a newly seen window top is gone to (None: nothing new), what it is ("climb" or "hang"), the keys
        #: already seen, the next eager trip, and what the runner should log about trips.
        self.eager_at: float | None = None
        self.eager_kind = "climb"
        self.seen_keys: set[int] = set()
        self.eager_ready = 0.0
        self.notes: list[str] = []
        self.pointer: tuple[int, int] | None = None
        self.card: Any = None
        self.card_queue: list[Any] = []
        self.card_settled = False
        self.card_until = 0.0
        self.card_clicked: Any = None
        self.sink = 0.0

    def _init_mind_and_flow(self, now: float) -> None:
        """Mind, flow, mood and the first trip and wave timers."""
        #: Mind, home, and the body's follow-through (INBOX 1670, row B).
        self.mind = bh.Mind(now)
        self.tail = bh.Trail()
        self.drift_phase = 0.0  # breaths so far of a drifting floater (`_follow_through`)
        self.settle_at = -1e9  # when the exhale after the last startle begins (`_do_startle`)
        #: The wisps and the nebula streams (INBOX 1683 c): always swaying, thrown by the body's moves.
        self.flow = bh.Flow()
        #: The tail's own layer (C1): a floater's tail is drawn every display frame, not baked in the idle cycle.
        self.tail_layer = bh.TailLayer()
        self.tail_layer_on = True  # the runner turns it off for a look whose tail is not Atlas's (a captured companion)
        self.state_at, self._seen_state = now, ""  # when the state was first seen drawn (a long sit is a lounge)
        self._twirl_at = -1e9  # the last time a twirl was drawn (its spiral unwinds after)
        self._flow_held: tuple[int, ...] | None = None
        self._flow_at = 0.0
        self._mood_kept: tuple[float, float, str] = (-1e9, -1.0, "content")  # (when, the event's time, mood): see `_mood`
        self.last_y = 0.0
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
        self.come: dict | None = None  # "Come here": follow the pointer (INBOX 1683 t)
        self.nap_after_land = False
        self.nap_req = False  # a nap was asked for (INBOX 1683 u): the next sleep is a held one
        self.nap_until = 0.0  # while above zero the sleep is a nap: only a poke, a drag, a command or this ends it
        self.follow_check = 0.0
        self.yield_since: float | None = None
        self.pace_at = -math.inf
        self.pace_last = 0.0  # the pace of the last step (`_pace`), which a yield brakes from
        self.pointer_busy_at = -1e9
        self.last_pointer: tuple[int, int] | None = None
        self.last_click = -1e9
        self.moving_since = now
        self.act_turned = -1.0
        self.placed = False
        self.greet_at = 0.0
        self.pose_goal = bh.NEUTRAL
        self.cur = bh.NEUTRAL
        #: The squash and stretch overshoot a little and settle, the lean anticipates a move (research A2); the tail's
        #: drag has its own spring chain and keeps the plain lag.
        self.pose_dyn = [bh.SecondOrder(*POSE_DYN[0], 1.0), bh.SecondOrder(*POSE_DYN[1], 1.0), bh.SecondOrder(*POSE_DYN[2], 0.0)]
        self.last_x = 0.0
        self.travel = 0.0
        #: A hop-chain leg: whether this walk is one, where its ground count began, and how high the figure is drawn now.
        self.hopping, self.hop_origin, self.hop_lift, self.hop_next = False, 0.0, 0.0, False
        self.trips = 0
        #: The rare long walk across the screen (owner: only on a good mood, never twice within an hour).
        self.last_long_walk = -1e9
        self.long_walks = 0
        self.greet_pending = False
        self.wave_rest = None  # pointer_busy_at of the rest already waved at
        self.wave_ready, self.wave_free_at = 0.0, 0.0
        #: The text caret of the foreground window (physical px) and when it was read, or None. While
        #: there is one, or the person is typing, the figure is busy: no trip, and it keeps clear of it.
        self.caret: Rect | None = None
        self.evade_ready = 0.0
        self.warp: dict[str, Any] | None = None
        self.edge_plan: tuple[tuple[float, float], str] | None = None
        #: What it did to get about: `modes` the chosen ones, `legs` every move `(mode, x0, x1, t)`.
        self.modes: list[str] = []
        self.legs: list[tuple[str, float, float, float]] = []
        #: The spell it is in or just did `{"name", "act", "start", "len"}`, every spell begun `spells`, and the length the
        #: next act is to take (`_on_act`).
        self.presence = True
        self.spell: dict[str, Any] | None = None
        self.spells: list[tuple[str, float, float]] = []
        self.spell_len = 0.0

    def _init_hang_and_carry(self, now: float) -> None:
        """Hanging, peeking, tucking, being thrown or carried, and the slip."""
        self.hang_started = now
        self.hang_drag0 = 0.0
        self.hang_kick_at = -1e9  # when a hanger was last patted or startled: the swing kick (`HANG_KICK`)
        self.hang_phase = 0.0
        self.hang_glance_at = math.inf
        self.idle_start = 0.0
        self.launch = (0.0, 0.0)  # the last throw's velocity: the ceiling holds a hard upward one
        self.away_until: float | None = None  # out of view above the top until then (`CEIL_LEAVE`)
        self.away_x = 0.0
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
        #: A top peek turned over (drawn upside-down from `peek_show` of its height below the edge).
        self.peek_flip = False
        self.peek_show = 0.0
        #: Windows to tuck behind (the last scan), when it was read, the one a walk is heading for, the one hidden behind.
        self.covers: list[Cover] = []
        self.covers_at = -math.inf
        self.tuck_goal: int | None = None
        self.tuck: Cover | None = None
        #: A window thrown it (INBOX 1683 x): when the perch was last read, how it left ("fall", "puff", "portal", "slide",
        #: "tip"), the face it will wear on landing, and until when it flails.
        self.perch_at = 0.0
        self.last_fling = ""
        self.flung: str | None = None
        #: A carry shaken hard enough (`extras.shake_flips`), and the moment a drop owes a dizzy sway (None: none owed).
        self.shaken = False
        self.dizzy_owed: float | None = None
        #: The `last_active` of the idle stretch it has already looked sad in (one look per stretch).
        self.lonely_stretch: float | None = None
        #: When it was let go over a window top it missed by a little (`_top_in_reach`), until it has looked confused for it.
        self.missed_owed: float | None = None
        self.missed_top = False
        #: Carried upside down (grabbed by the feet, or shaken): drawn as the turned tumble picture, half a circle round.
        self.upside = False
        #: When this carry began and the stage it has reached (`CARRY_STAGES`): "", "kick", "cross" or "sigh".
        self.carry_since: float | None = None
        self.carry_stage = ""
        self.flail_until = 0.0
        #: A hold that slipped: the window it will pull up onto, the scrabble's span, and how the last slip ended.
        self.pulling: Perch | None = None
        self.scrabble_t0 = self.scrabble_until = 0.0
        self.last_slip = ""
        self.phase_from = (0.0, 0.0)
        self.phase_started = now
        self.phase_to = (0.0, 0.0)

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
        if not self.metrics or frame in ("hang", "hang_one"):
            return 0.0
        if frame in SIT_REGISTERED:  # a dangle sits on the line with its hem below it; a meditation is the sit
            frame = "sit"
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
        return f"spin{int(round((self.angle + self.wob) / (2 * math.pi / SPIN_STEPS))) % SPIN_STEPS}"

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
        left, top, right, bottom = (
            min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes),
        )
        if frame == "held":
            # A lifted or pressed figure is still drawn as a stand or an idle picture for a moment (the rise, the
            # press), whose tail or ring may reach a px or two past the held pose: the sides cover the whole cycle,
            # so no picture of it is cut by the screen's edge on a ride (INBOX 1670).
            dx = self._flip_dx("stand", flip)
            for n in (*STAND_FAMILY, *(f"idle{i}" for i in range(IDLE_FRAMES))):
                b = self.metrics.get((n, flip))
                if b:
                    left, right = min(left, b[0] + dx), max(right, b[2] + dx)
        return left, top, right, bottom

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
        old_size = self.size
        old_floor = self.ground_y() if self.perch is None and self.state in GROUNDED else None
        # only a bar coming or going (the same screens, the same dpi) drops the floor under it; a new resolution re-plants it
        same = _same_screens(monitors, self.monitors)
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
        elif same and old_floor is not None and self.ground_y(m) > old_floor + 1.0 and self.size == old_size:
            self.x = min(max(self.x, left), right - self.size[0])
            self._start_fall(0.0)  # the bar went away: it falls to the new floor, it does not snap there
        elif self.state not in moving[:9]:
            self._place_on_floor()

    def resize(self, size: tuple[int, int], metrics: dict[tuple[str, bool], tuple[float, float, float, float]]) -> None:
        """The person sized the figure (the desk size handle): the window's middle stays where it was, and what holds
        it stays held: standing keeps its feet on the floor (set_monitors plants them), hanging keeps its hands on the
        edge (the lift above them changes with the size), so a pull never moves it at rest."""
        old_w, lift = self.size[0], self._lift()
        self.set_metrics(metrics)
        self.size = size
        self.x += (old_w - size[0]) / 2
        if self.state in ("hang", "rise"):
            self.y += lift - self._lift()
        self.set_monitors(self.monitors, size)

    def hold(self) -> Output:
        """The picture as it is, time not advanced: the figure held still while the size handle is pulled (the
        caller `resume`s it on release, so nothing it was doing is caught up)."""
        return self._output(self.now)

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
        if self.tuck is not None:
            self._check_tuck(self.now)

    def react(self, kind: str, now: float) -> bool:
        """Something happened on the screen (`extras.REACTIONS`: a window opened or closed, the foreground app
        changed, the person came back, the hour, a download, the battery): play its short answer if it is free to.
        True when it did. Asked on the engine's own thread, like `command`."""
        return self.ex.fire(kind, now)

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
        if self.state == "sleep" and state != "sleep":
            self.woke_at = now
        self._catch_breath(state, now)
        self._wear_face(state, now)
        self.state = state
        self._arm_nap(state, now)
        if state in bh.STATE_BEATS:
            self.mind.start_beats(bh.STATE_BEATS[state], now, self.var_rng)
        self.flash = None
        self._drop_holds(state)
        self.trip = False
        if state != "warp":
            self.warp = None
        if state == "stand":
            self.idle_start, self._edges = now, [0.0]  # the cycle starts from its first picture
        if state == "stand" and self.presence and self.roam and not self.reduced:
            self.state_until = now + self.rng.uniform(*SPELL_SETTLE)  # a breath between two things, not minutes of stillness
        elif state in HOLD_RANGES:
            self.state_until = now + self.rng.uniform(*HOLD_RANGES[state])
        elif state in HOLD_FIXED:
            self.state_until = now + HOLD_FIXED[state]
        elif state in ("sleep", "fly"):
            self.state_until = math.inf
        else:
            getattr(self, f"_on_{state}", lambda _now: None)(now)
        if state == "stand" and self.perch is not None:  # a visit to a window ends when its time does
            self.state_until = min(self.state_until, max(now + 1.0, self.perch_until))

    def _catch_breath(self, state: str, now: float) -> None:
        """Leaving a walk, a hop or a carry starts the breath's ease back; a sit or a sleep takes its breath period from it."""
        if self.state in EXERTING:
            self.exerted_at = now
        if state in REST_LIFE:
            self.rest_breath = vitals.breath(self.mind.mood(now, self.hour), vitals.exertion(now - self.exerted_at))

    def _carry_tick(self, now: float) -> None:
        """A carry that goes on: after `CARRY_STAGES[0]` s it kicks its legs, then crosses its arms, then sighs (INBOX
        1696 kk). Everything resets with the drop."""
        if self.state != "held" or self.carry_since is None:
            self.carry_since, self.carry_stage = None, ""
            return
        held = now - self.carry_since
        self.carry_stage = next((n for at, n in reversed(CARRY_STAGES) if held >= at), "")

    def _carry_pose(self) -> tuple[float, float, float, float] | None:
        """The body language of a long carry over the held picture: the legs kick (a quick lean back and forth), the
        arms cross (a touch narrower, kept), a sigh (a slow dip and rise of the chest). None upside down, where the
        turned picture sits on a bigger canvas, and before the first stage."""
        if self.upside or not self.carry_stage or self.carry_since is None:
            return None
        into = self.now - self.carry_since - dict((n, at) for at, n in CARRY_STAGES)[self.carry_stage]
        sx, sy, lean = 1.0, 1.0, 0.0
        if self.carry_stage == "kick":
            lean = 0.08 * math.sin(2 * math.pi * KICK_HZ * into)
        else:
            sx = 0.96  # arms crossed
            if self.carry_stage == "sigh" and into < SIGH_FOR:
                sy = 1.0 - 0.08 * math.sin(math.pi * into / SIGH_FOR)
        q = bh.quantised(bh.Pose(sx, sy, lean, 0.0))
        return None if q is None else (q.sx, q.sy, q.lean, q.drag)

    def _dizzy(self, now: float) -> None:
        """A shaken carry has been let go: once it stands or sits again (the fall and the landing come first) it sways
        dizzily for `extras.DIZZY_FOR` s, spiral eyes and all. Given up if it has not stood within `DIZZY_WAIT` s."""
        if self.dizzy_owed is None:
            return
        if now - self.dizzy_owed > DIZZY_WAIT:
            self.dizzy_owed = None
        elif self.state in ("stand", "sit"):
            self.dizzy_owed = None
            self.ex.fire("dizzy", now, seconds=self.ex.rng.uniform(*extras.DIZZY_FOR))

    def _missed(self, now: float) -> None:
        """Let go over a window top it was not close enough to reach: once it stands or sits on the floor it looks
        confused (the face alone), given up after `DIZZY_WAIT` s. A hang, a perch or another carry ends the debt."""
        if self.missed_owed is None:
            return
        if now - self.missed_owed > DIZZY_WAIT or self.perch is not None or self.state in ("held", "pressed", "hang"):
            self.missed_owed = None
        elif self.state in ("stand", "sit"):
            self.missed_owed = None
            self.ex.fire("confused", now)

    def _lonely(self, now: float, pointer: tuple[int, int] | None) -> None:
        """Left alone `LONELY_AFTER` s while standing or sitting (not asleep, not busy, not reduced): the refused look,
        once per idle stretch (a pointer within `NOTICE_NEAR` is company). The look does not count as activity, so the sit and the sleep keep their times."""
        if now - self.last_active < LONELY_AFTER or self.lonely_stretch == self.last_active:
            return
        if self.state not in ("stand", "sit") or self.busy or self.reduced:
            return
        if pointer is not None and math.hypot(pointer[0] - self.x - self.size[0] / 2, pointer[1] - self.y - self.size[1] / 2) <= NOTICE_NEAR * self._scale():
            return  # a pointer resting beside it is company
        kept = self.last_active
        if self.ex.fire("refused", now):
            self.lonely_stretch = self.last_active = kept

    def _wave_at_pointer(self, now: float) -> None:
        """The pointer rests near a figure that is standing about: it waves, once for that rest."""
        if self.card is not None:
            self.wave_free_at = now  # a card it brought is the person's business: the rest counts from when it is put down
        if self.pointer is None or self.state != "stand" or self.busy or self.reduced or self.nap_until:
            return
        if now - max(self.pointer_busy_at, self.wave_free_at) < WAVE_IDLE or self.wave_rest == self.pointer_busy_at or now < self.wave_ready:
            return
        cx, cy = self.x + self.size[0] / 2, self.y + self.size[1] / 2
        if math.hypot(self.pointer[0] - cx, self.pointer[1] - cy) > WAVE_NEAR * self._scale():
            return
        self.wave_rest, self.wave_ready = self.pointer_busy_at, now + WAVE_GAP
        if self.pointer[0] != cx:
            self.facing = -1 if self.pointer[0] < cx else 1
        self.last_active = now
        self._start_act("wave_pointer", now)

    def _wear_face(self, state: str, now: float) -> None:
        if self.flung is not None:  # thrown off a window: the face comes with the first moment it can wear one
            if state in extras.FACE_STATES:
                self.ex.over = (self.flung, now, self.rng.uniform(*FLING_FACE))
                self.flung = None
            elif state in ("held", "pressed", "hang", "peek", "emerge", "rise"):
                self.flung = None

    def _drop_holds(self, state: str) -> None:
        """What the new state lets go of."""
        if state not in ("hang", "drift", "rise", "crouch"):
            self.hang_on = None
        if state != "fly":
            self.wrapping = None
            self.away_until = None  # only a flight can be out of view above the top
        if state not in ("peek", "emerge") and self.wrapping is None:
            self.sink, self.peek_edge, self.tuck = 0.0, None, None
        if state not in ("walk", "drift", "crouch"):
            self.goal = None
        if state != "walk":
            self.hopping, self.hop_lift = False, 0.0
        if state != "peek":
            self.peek_flip, self.peek_show = False, 0.0
        if state != "held":
            self.upside = False
        if state != "hang":
            self.pulling, self.scrabble_until = None, 0.0
        if state != "act":
            self.act = None

    def _arm_nap(self, state: str, now: float) -> None:
        """A sleep that was asked for (`nap_req`) is a nap with an end of its own; any other state is not one."""
        self.nap_until = now + self.rng.uniform(*NAP_FOR) if state == "sleep" and self.nap_req and not self.reduced else 0.0
        if state == "sleep":
            self.nap_req = False

    def _on_warp(self, now: float) -> None:
        self.state_until = math.inf

    def _on_walk(self, now: float) -> None:
        self.state_until = now + self.rng.uniform(*WALK_FOR)
        self.walk_started = now

    def _on_act(self, now: float) -> None:
        act = bh.ACTIVITIES[self.act or "breathe"]
        self.act_started, self.act_len = now, self.rng.uniform(*act.seconds)
        self.act_var = bh.vary(self.var_rng)  # V3: not the same play twice; its own stream, so no other draw moves
        self.act_len *= self.act_var.dur
        if self.spell_len:
            self.act_len, self.spell_len = self.spell_len, 0.0
        self.act_turned = -1.0
        self.mind.start_beats(self.act or "breathe", now, self.var_rng)  # A4: a long act shifts its pose within its budget
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
        self.hang_drag0 = self.cur.drag  # the hem the hang starts from: the swing is blended in from it (`_target_pose`)
        self.hang_phase = self.rng.uniform(0.0, 2 * math.pi)
        self.hang_glance_at = now + self.rng.uniform(*HANG_GLANCE)
        self.swing_to, self.releasing = None, False
        self._hang_one_reset(now)

    def _on_rise(self, now: float) -> None:
        self.state_until = now + RISE_FOR
        self.phase_started = now

    def _on_peek(self, now: float) -> None:
        self.peek_started, self.peek_turned = now, False
        self.state_until = now + (PEEK_TOP_PLAN if self.peek_edge == "top" else TUCK_PLAN if self.tuck else PEEK_PLAN)[-1][0]

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
        self.nap_req = False
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
        if self.come is not None:
            self._come_step(now)
        if self.state not in ("held", "pressed"):
            self._advance(now, dt, pointer)
        if self.caret is not None and self.state not in ("held", "pressed", "fly", "fall", "warp"):
            self._keep_off_caret(now)
        if self.turn_to:  # a turn begun in an act or a stand still finishes
            self._turning(now)
        self._follow_through(now, dt)
        self._dizzy(now)
        self._missed(now)
        self._lonely(now, pointer)
        self._wave_at_pointer(now)
        self._carry_tick(now)
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
        vy = (self.y - self.last_y) / dt
        self.last_y = self.y
        held = self.state in ("held", "pressed")
        if self.state == "drift":  # the floater's breath is a phase that runs at the vitals' rate, so a change of rate is no jump
            self.drift_phase += min(dt, 0.5) / (DRIFT_BREATH_S * vitals.breath(self.mind.mood(now, self.hour), vitals.exertion(now - self.exerted_at)))  # a drift is a float, not a run
        self.tail.step(dt, 0.0 if held else vx, 0.0 if held else vy)
        px = FLOW_SPEED_MAX * self._scale()  # a vanish or a hop of the window is no speed
        scale = self._scale()
        self.flow.step(dt, max(-px, min(px, vx)) / scale, max(-px, min(px, vy)) / scale)
        target = self.pose_goal = self._target_pose(now)
        gap = max(abs(a - b) / q for a, b, q in zip(self.cur, target, (bh.Q_SCALE, bh.Q_SCALE, bh.Q_LEAN, bh.Q_DRAG)))
        nxt = self._ease_pose(dt if gap <= POSE_GAP_FREE or dt <= POSE_DT_WAKE else POSE_DT_MAX, target)
        # the hem is a swinging spring: a dash's stop threw its tip 26 px and back in 0.2 s, 5 to 6 px between two draws. The
        # drawn hem moves by at most DRAG_STEP_MAX px a draw (the follow-through stays, only its speed is bounded)
        step = max(-DRAG_STEP_MAX, min(DRAG_STEP_MAX, nxt.drag - self.cur.drag))
        self.cur = nxt._replace(drag=self.cur.drag + step)
        # a draw that moved the figure by less than a pixel read as speed 0 and dropped the lean target for one picture;
        # the lean follows a short low-pass of the speed instead (INBOX 1683 j)
        if abs(vx) > px:  # a vanish, a warp or a placement is no speed: it leans no more, and the low-pass must not carry it on
            self.vx_px = 0.0
        else:
            self.vx_px += (vx - self.vx_px) * (1.0 - math.exp(-dt / VX_SMOOTH_S))

    def _ease_pose(self, dt: float, target: bh.Pose) -> bh.Pose:
        """The pose one draw later: scale and lean by second-order dynamics (from where `cur` is, so a pose set by
        hand is honoured), the drag by the plain lag."""
        out = []
        for so, value, goal, q in zip(self.pose_dyn, self.cur, target, (math.inf, bh.Q_SCALE, bh.Q_LEAN)):
            so.y = value
            nxt = so.step(dt, goal)
            # a spring's peak speed is over a cache step a draw: two grid steps of the height or the lean in one picture read as a
            # pop. The width is left free: it is half the joint, and a turn's squeeze is a designed sweep
            if abs(nxt - value) > q:
                nxt = value + math.copysign(q, nxt - value)
                so.yd = (nxt - value) / dt  # the velocity it really has, so it does not wind up behind the cap
            out.append(nxt)
        k = min(1.0, dt * POSE_RATE)
        return bh.Pose(out[0], out[1], out[2], self.cur.drag + (target.drag - self.cur.drag) * k)

    def _hang_drag(self, now: float) -> float:
        """The hem of a hanger: the pendulum eased in from the hem it started with, a kick when patted or startled on the
        edge (INBOX 1721 a: a swing that dies away) and the shake of a scrabble."""
        t = now - self.hang_started
        amp = bh.smooth(t / 1.5) * (0.65 + 0.35 * math.sin(2 * math.pi * t / 41.0 + self.hang_phase))
        if self.swing_to is not None:  # winding up to let go toward a window: the swing grows
            amp *= 1.0 + SWING_BOOST * bh.smooth((now - self.swing_at) / SWING_FOR)
        drag = HANG_SWING * amp * math.sin(2 * math.pi * t / HANG_PERIOD + self.hang_phase)
        blend = bh.smooth(t / HANG_DRAG_IN)  # a hem left swinging by the leap or climb is not dropped to the pendulum in one pose ease
        drag = self.hang_drag0 * (1.0 - blend) + drag * blend
        since = now - self.hang_kick_at
        if 0.0 <= since < HANG_KICK_FOR:
            drag += HANG_KICK * (1.0 - since / HANG_KICK_FOR) ** 2 * math.sin(2 * math.pi * since / (HANG_PERIOD / 3))
        if now < self.scrabble_until:  # the hands slipped and it is clawing back: the hem shakes
            drag += SCRABBLE_DRAG * math.sin(2 * math.pi * SCRABBLE_HZ * (now - self.scrabble_t0))
        return drag

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
            drag = self._hang_drag(now)
        elif s_ == "warp" and self.warp is not None and self.warp["kind"] == "portal":
            squeeze = self._warp_view(now)[2]
            sx, sy = 1.0 - 0.8 * squeeze, 1.0 - 0.2 * squeeze
        elif s_ == "act":
            p = bh.scaled(bh.sample(bh.ACTIVITIES[self.act or "breathe"].keys, (now - self.act_started) / max(0.01, self.act_len), self.act_var.ease), self.act_var.amp)
            sx, sy, lean = p.sx, p.sy, p.lean * (1 if self.facing > 0 else -1)
        else:
            sx, sy, lean = self._ground_pose(now, s_)
        if self.turn_to != 0:
            u = (now - self.turn_started) / TURN_FOR
            sx *= max(0.12, abs(math.cos(math.pi * min(1.0, u))))
        u = (now - self.shift_at) / SHIFT_FOR
        if s_ in ("act", "sit", "sleep") and 0.0 <= u < 1.0:  # A4: a long act or rest shifts its weight over and settles
            lean += SHIFT_LEAN * math.sin(math.pi * u) * (1 if self.mind.shifts % 2 else -1)
            sy -= 0.02 * math.sin(math.pi * u)
        return bh.Pose(sx, sy + LIFT_SY * self.tail.lift, lean, drag)  # a landing's stop stretches the hem down, then back

    def _ground_pose(self, now: float, s_: str) -> tuple[float, float, float]:
        """The squash and lean of a crouch, a landing, a step or a mood's stand."""
        sx = sy = 1.0
        lean = 0.0
        if s_ == "crouch":
            sy, sx = 1.0 - 0.12 * bh.smooth((now - (self.state_until - CROUCH_FOR)) / CROUCH_FOR), 1.03
        elif s_ == "land":
            sx, sy, lean = self._touch_pose(now)  # E6: how hard it came down sets the depth, the length and a stumble's lean
        elif s_ in ("walk", "drift") and self.turn_to == 0:
            speed = min(1.0, abs(self.vx_px) / (WALK_SPEED * self._scale() * 1.2))
            lean = LEAN_MAX * speed * (1 if self.vx_px > 0 else -1) * (1.6 if self.mode == "dash" else 1.0)
            if self.gait == "float":  # the window never bobs: a floater's breath is in the figure
                sy = 1.0 + DRIFT_BREATH * (1.0 - math.cos(2 * math.pi * self.drift_phase)) / 2.0
            if self.gait == "walk":  # a ground companion bounces with its steps
                sy = 1.0 + 0.012 * math.sin(self.travel / self._scale() * 2 * math.pi / (STRIDE * 2))
        elif s_ == "stand":
            mood = self.mind.mood(now, self.hour)
            sy = {"sleepy": 0.975, "proud": 1.035, "bored": 0.985, "startled": 1.05}.get(mood, 1.0)
            if self._idling():  # the 24 baked frames repeat every 4 s: a slow lean on the pose grid, two clocks that never meet
                lean = STAND_LEAN * (0.6 * math.sin(2 * math.pi * now / STAND_LEAN_S[0]) + 0.4 * math.sin(2 * math.pi * now / STAND_LEAN_S[1] + 1.3))
            u = (now - self.squash_at) / SQUASH_FOR
            if 0.0 <= u < 1.0:  # the settle after a throw: a small squash and back
                sy -= SQUASH * math.sin(math.pi * u)
                sx = 1.0 + 0.5 * SQUASH * math.sin(math.pi * u)
            u = (now - self.settle_at) / EXHALE_FOR
            if 0.0 <= u < 1.0:  # the exhale after a startle: the shoulders drop and come back (INBOX 1719 b)
                sy -= EXHALE_DIP * math.sin(math.pi * u)
                sx += 0.5 * EXHALE_DIP * math.sin(math.pi * u)
        return sx, sy, lean

    def _pose(self) -> tuple[float, float, float, float] | None:
        """The body pose to draw over the frame; none while it is carried, thrown, falling or at an
        edge (those frames carry their own shape, and a spin sits on a bigger canvas)."""
        if self.state == "held":
            return self._carry_pose()
        if self.state in POSE_OFF:
            return None
        q = self._life_pose(self.now)
        return None if q is None else (q.sx, q.sy, q.lean, q.drag)

    def _rest_life(self) -> tuple[float, float, float, float] | None:
        """`REST_LIFE` for the state with its breath period scaled by the rest's own `rest_breath`."""
        life = REST_LIFE.get(self.state)
        return None if life is None else (life[0] * self.rest_breath, *life[1:])

    def _life_pose(self, at: float, scale: float | None = None) -> bh.Pose | None:
        """The eased body pose with the breath and tail sway of a sit or a sleep over it, on the grid."""
        life = self._rest_life()
        if life is None or self.reduced:
            return bh.quantised(self.cur)
        breath, depth, sway, sway_s = life
        c = self.cur
        swell = (1.0 - math.cos(2 * math.pi * at / breath)) / 2.0
        return bh.quantise(c.sx, c.sy * (1.0 + depth * swell), c.lean, c.drag + self._rest_tail(at, life, scale), Q_BREATH)

    def _life_cell(self, at: float, scale: float) -> tuple[int, int, int, int]:
        """`_life_pose`'s grid cell (equal cells are equal poses): what a look-ahead compares."""
        life = self._rest_life()
        c = self.cur
        if life is None or self.reduced:
            return bh.cell(c.sx, c.sy, c.lean, c.drag)
        swell = (1.0 - math.cos(2 * math.pi * at / life[0])) / 2.0
        return bh.cell(c.sx, c.sy * (1.0 + life[1] * swell), c.lean, c.drag + self._rest_tail(at, life, scale), Q_BREATH)

    def _rest_tail(self, at: float, life: tuple[float, float, float, float], scale: float | None = None) -> float:
        """The tail's lag, px: a slow sway whose period drifts, a faster one over it, and the body's own breath a
        beat late, so a sit never repeats and the tail follows the body rather than keeping time with it."""
        breath, _depth, sway, sway_s = life
        tau = 2 * math.pi
        drift = TAIL_WANDER * TAIL_WANDER_S / sway_s * math.sin(tau * at / TAIL_WANDER_S)  # period within +-12 percent
        slow = math.sin(tau * at / sway_s + drift)
        fast = math.sin(tau * at / (sway_s * 0.62) + 1.7)
        late = (1.0 - math.cos(tau * (at - TAIL_LAG) / breath)) / 2.0 - 0.5
        return sway * (self._scale() if scale is None else scale) * (0.65 * slow + 0.3 * fast + 0.4 * late)

    def _next_life_change(self, now: float) -> float:
        """The next time a sit's or a sleep's breath or sway crosses a step of the grid, looking ahead
        at most `POLL_QUIET_MS` and never sooner than a redraw's pace (12 a second)."""
        scale = self._scale()  # the figure does not move while it looks ahead
        base = self._life_cell(now, scale)
        t, pace = now, REST_DRAW_MS / 1000.0
        while t < now + POLL_QUIET_MS / 1000.0:
            t += pace
            if self._life_cell(t, scale) != base:
                return t
        return now + POLL_QUIET_MS / 1000.0

    def _advance(self, now: float, dt: float, pointer: tuple[int, int] | None) -> None:
        handler = getattr(self, f"_do_{self.state}")
        handler(now, dt)
        if self.card is not None or self.card_queue:
            self._card_step(now)
        self.ex.life(now)
        if pointer is not None and not self.reduced:
            if not self.ex.pointer(now, pointer):
                self._notice(now, pointer)

    # --- states -----------------------------------------------------------------------------

    def _ambient_gap(self) -> float:
        lo, hi = AMBIENT_EVERY
        return lo + (hi - lo) * self.life_rng.random() ** AMBIENT_SKEW * self._blink_scale()[0]  # the 2 s floor holds (INBOX 1670)

    def _blink_scale(self) -> tuple[float, float]:
        """INBOX 1719 b: the mood and the tiredness of the moment set how often it blinks and how slowly (`vitals.blink`):
        sleepy or tired, more often and longer; curious or startled, a held gaze."""
        mind = getattr(self, "mind", None)
        if mind is None:
            return 1.0, 1.0
        return vitals.blink(mind.mood(self.now, self.hour), mind.needs.get("rest", 0.0))

    def _blink(self, now: float) -> None:
        """A blink begins: its length is the mood's, drawn once so its phases keep their shares."""
        self.blink_for = BLINK_FOR * self._blink_scale()[1]
        self.flash, self.blink_at = ("blink", now + self.blink_for), now

    def _ambient(self, now: float) -> None:
        """Blink, and now and then look about: while standing (a sit blinks, it does not look), and only
        when motion is allowed."""
        if self.reduced:
            return
        if self.flash and now >= self.flash[1]:
            if self.flash[0] == "look":  # the cycle resumes where the look paused it, not on another picture
                self.idle_start += now - (self.flash[1] - LOOK_FOR)
            self.flash = ("look", now + LOOK_FOR) if self.flash[0] == "blink" and self.look_after_blink else None
            self.look_after_blink = False
        if self.flash is None and now >= self.next_ambient:
            look = self.state == "stand" and self.life_rng.random() < LOOK_SHARE
            # G2: a big gaze shift starts with a blink (Eyes Alive), then the look.
            self._blink(now)
            self.look_after_blink = look
            double = not look and self.life_rng.random() < DOUBLE_SHARE and self.blink_for <= BLINK_FOR * 1.1  # a heavy lid is not doubled
            self.next_ambient = now + (self.blink_for + DOUBLE_GAP if double else self._ambient_gap())

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
            if not self.reduced and self.roam and self.perch is None and self.card is None and self.presence and self.come is None:
                self._spell_quietly(now)  # the person is typing: the spell goes on, in place, not a freeze
            else:
                self.state_until = now + QUIET_RECHECK
            return
        eager = self._eager(now)
        if eager is not None:
            self._perform(eager, now)
            return
        if self.follow_until > now and self._follow(now):
            return
        if self.come is not None and self.come["phase"] != "wait":  # keeping company: small things, not a stroll
            self._start_act(self.mind.pick(self.rng, now, self.gait, self.hour), now)
            return
        if self._away() and self.perch is None:
            self._go_home(now)
            return
        self._tell_mind(now, idle)
        self._perform(self._pick_act(now, idle), now)

    def _tell_mind(self, now: float, idle: float) -> None:
        """What the person is doing, for the mind's considerations: seconds since they last did anything and
        whether the pointer is within a few figures of it."""
        self.mind.idle = idle
        p = self.pointer
        self.mind.near = p is not None and abs(p[0] - (self.x + self.size[0] / 2)) < 4 * self.size[0]

    # --- home, trips, and what to do in place (INBOX 1670, row B) ------------------------

    def _away(self) -> bool:
        """Further from home than a stroll's end, or off the floor line: it goes back."""
        if self.home_x is None or self.card is not None or self.come is not None:
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

    # --- presence spells (INBOX 1692) -------------------------------------------------------

    def _begin_spell(self, now: float) -> None:
        """Choose the next spell by the hour and the mood and go to its spot (a seen move, never a long walk), or start
        it where it is when that is spot enough."""
        name = pr.pick_spell(self.rng, self.hour, self.mind.mood(now, self.hour), [s[0] for s in self.spells[-2:]])
        self.spell = {"name": name, "act": pr.SPELLS[name].act, "start": now, "len": pr.length_of(self.rng, name)}
        spot = self._spell_spot(now)
        if spot is not None and abs(spot[0] - self.x) > SPELL_MOVE * self._scale():
            self._go(spot, "spell", now)
        else:
            self._start_spell(now)

    def _spell_spot(self, now: float) -> tuple[float, float] | None:
        """A spot to settle at: by a screen edge (never the middle third), more often the far one, clear of the caret;
        the home itself while a home chosen from the menu holds (`HOME_KEEP`)."""
        m = self.current_monitor()
        k = self._scale()
        if now - self.homed_at < HOME_KEEP and self.home_x is not None:
            # INBOX 1696: the near edge was often where it had come from (a wander lands just out of the middle third),
            # so the first spell took it back there in a puff, seconds after it arrived
            return self._clear_of_caret(self.home_x, self.ground_y(m), SPELL_ROOM * self.size[1])
        side = tv.nearest_edge(self.x, m.area, self.size[0])
        if now - self.homed_at >= HOME_KEEP and self.rng.random() < 0.65:
            side = -side
        x = tv.edge_x(side, m.area, self.size[0], self.rng.uniform(6.0, tv.EDGE_ZONE * 0.8) * k)
        if self.home_x is not None and tv.nearest_edge(self.home_x, m.area, self.size[0]) == side:
            reach = 1.95 * AWAY * k  # a spell on the home's own side stays within the home radius (the hour test's 2 x AWAY)
            x = min(max(x, self.home_x - reach), self.home_x + reach)
        return self._clear_of_caret(x, self.ground_y(m), SPELL_ROOM * self.size[1])

    def _start_spell(self, now: float) -> None:
        """The spell's act, one long prop act: fetched in seconds, its prop moving, put away at the end."""
        sp_ = self.spell
        if sp_ is None:
            self._enter("stand", now)
            return
        sp_["start"] = now
        self.spells.append((sp_["name"], now, sp_["len"]))
        self.spell_len = sp_["len"]
        self._start_act(sp_["act"], now)

    def _spell_quietly(self, now: float) -> None:
        """While the person types the spell's act goes on in place (a shorter one at a time), as a companion keeps
        you company without getting in the way."""
        if self.spell is None:
            name = pr.pick_spell(self.rng, self.hour, self.mind.mood(now, self.hour), [s[0] for s in self.spells[-2:]])
            self.spell = {"name": name, "act": pr.SPELLS[name].act, "start": now, "len": 0.0}
        sp_ = self.spell
        self.spell_len = self.rng.uniform(*SPELL_QUIET)
        self._start_act(sp_["act"], now)

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
        if self.mind.shift_due(now, self.var_rng):
            self.shift_at = now  # A4: the same lean and settle as a sit's, the window does not move
        if self.act in bh.YIELD_TO_SIT and now - self.last_active >= IDLE_SIT:
            self.state_until = now  # a long seated act gives way to the ten-minute sit
        if now >= self.state_until:
            self._enter("stand", now)
            self.ex.after_act(now)

    def _do_crouch(self, now: float, dt: float) -> None:
        if now >= self.state_until:
            self._begin_go(now)

    def set_lively(self, name: str) -> None:
        """The menu's Activity: Calm, Usual or Lively; anything else is Usual."""
        self.lively = name if name in LIVELY else "usual"

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
        self.trip_ready = now + self.rng.uniform(*TRIP_EVERY) * LIVELY[self.lively][0]
        self.trips += 1
        m = self.current_monitor()
        k = self._scale()
        if self.greet_pending and self.pointer is not None and now - self.greet_at < 240.0:
            self.greet_pending = False
            self._note_dest("floor")
            px = min(max(self.pointer[0] - self.size[0] / 2 - FOLLOW_GAP * k * (1 if self.pointer[0] > self.x else -1), m.area[0]), m.area[2] - self.size[0])
            self._go((px, self.ground_y(m)), "greet", now)
            return
        pick = self._trip_pick(now)
        self._note_dest({"window": "window", "hang": "hang"}.get(pick, "floor"))
        if pick == "window":
            self.climb_ready = 0.0
            self._climb(now)
        elif pick == "hang":
            self.big_ready = now + self.rng.uniform(*BIG_EVERY)
            self._hang(now)
        elif pick == "follow":
            self.follow_until = now + self.rng.uniform(*FOLLOW_FOR)
            self._follow(now) or self._enter("stand", now)
        elif pick == "longwalk":
            self._long_walk(now)
        elif pick == "clock":
            self._go((m.area[2] - self.size[0] - 6 * k, self.ground_y(m)), "clock", now)
        else:  # nap: the nearer outer edge
            left = self.x - m.area[0] < m.area[2] - self.size[0] - self.x
            self._go((m.area[0] + 4 * k if left else m.area[2] - self.size[0] - 4 * k, self.ground_y(m)), "nap", now)

    def _trip_table(self, now: float) -> list[tuple[str, str, float]]:
        """(destination kind, trip, weight) for each trip that can happen now."""
        table = [("floor", "clock", 2.0), ("floor", "nap", 2.0 if self.mind.needs["rest"] > 0.5 else 0.3)]
        if self.pointer is not None:
            table.append(("floor", "follow", 2.0))
        if self.roam_windows and self._candidates():
            table.append(("window", "window", 4.0))
        if self._long_walk_ok(now):
            table.append(("floor", "longwalk", LONG_WALK_WEIGHT))
        if now >= self.big_ready and self._hang_ok():  # a hang is a big act: minutes apart, whoever chose it
            table.append(("hang", "hang", HANG_TRIP_WEIGHT))
        return table

    def _long_walk_ok(self, now: float) -> bool:
        """A long walk is rare: a lively mood (happy or curious), some energy, and an hour since the last."""
        return (
            self.roam and not self.reduced and self.perch is None and now - self.last_long_walk >= LONG_WALK_GAP
            and self.lively != "calm"
            and self.mind.mood(now, self.hour) in ("happy", "curious") and self.mind.needs["rest"] < 0.55
        )

    def _long_walk(self, now: float) -> None:
        """Across most of the screen on foot (a floater glides), then a look about when it gets there."""
        self.last_long_walk, self.long_walks = now, self.long_walks + 1
        m = self.current_monitor()
        lo, hi = m.area[0], m.area[2] - self.size[0]
        far = [x for x in (lo + (hi - lo) * 0.08, lo + (hi - lo) * 0.92) if abs(x - self.x) >= (hi - lo) * 0.45]
        x = self.rng.choice(far) if far else (hi if self.x < (lo + hi) / 2 else lo)
        self._go((x, self.ground_y(m)), "longwalk", now, plain=True)

    def _trip_pick(self, now: float) -> str:
        table = self._trip_table(now)
        kept = [row for row in table if not self._dest_repeats(row[0])]
        table = kept or table  # the floor stays the fallback when nothing else is in reach
        roll = self.rng.random() * sum(w for _k, _n, w in table)
        for _kind, name, w in table:
            roll -= w
            if roll < 0:
                return name
        return table[-1][1]

    def _dest_repeats(self, kind: str) -> bool:
        """Whether `kind` was the last `DEST_RUN` destinations."""
        h = self.dest_hist
        return len(h) >= DEST_RUN and all(k == kind for k in h[-DEST_RUN:])

    def _note_dest(self, kind: str) -> None:
        self.dest_hist = (self.dest_hist + [kind])[-DEST_RUN:]

    def _arrive_trip(self, then: str, now: float) -> None:
        if then == "greet":
            self._enter("wave", now)
        elif then in ("clock", "longwalk"):
            options = [n for n in ("ponder", "look_around") if n not in self.mind.recent[-1:]]  # never the act it just did
            self._start_act(self.rng.choice(options), now)
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

    def _act_blocked(self, act: str, big: bool, now: float, idle: float) -> bool:
        """An act that cannot happen now: a big one too soon or off the floor, a sleep too early, a trip or a
        climb with nowhere to go, a stroll from a window."""
        up = self.perch is not None
        if big and (now < self.big_ready or up):
            return True
        if act == "sleep":
            return idle < SLEEP_AFTER or up or self.mind.needs["rest"] < 0.4
        if act == "trip":
            return not self._trip_ok(now)
        if act == "climb":
            return not self._can_climb(now) or self._dest_repeats("window")
        if act == "hang" and self._dest_repeats("hang"):
            return True
        if act == "spell":
            return up or self._no_spell()
        return act == "stroll" and up

    def _no_spell(self) -> bool:
        return not self.presence or self.reduced or not self.roam or self.card is not None or self.come is not None

    def _act_table(self, now: float, idle: float) -> list[tuple[str, float]]:
        mood = self.mind.mood(now, self.hour)
        table = []
        for act, (w, big) in ACTS.items():
            if self._act_blocked(act, big, now, idle):
                continue
            if act in ("stroll", "trip") and mood == "bored":
                w *= 2
            if act in ("trip", "climb", "hang", "peek"):
                w *= LIVELY[self.lively][1]
            if act == "trip":  # a trip that has waited past its time is wanted more, up to five times (owner: too rare)
                w *= 1.0 + min(TRIP_OVERDUE_MAX, max(0.0, now - self.trip_ready) / TRIP_OVERDUE_S)
            table.append((act, w))
        return table

    def _perform(self, act: str, now: float) -> None:
        rested = self._rested_on_perch()  # a floater drops the perch just below, but sits on it for a dangle
        if self.perch is not None and self.gait == "float":
            self.perch = None  # a floater rests on a window, it does not stay on it
        if act in ("hang", "peek"):
            self.big_ready = now + self.rng.uniform(*BIG_EVERY)
        if act in ("climb", "hang"):
            self._note_dest("window" if act == "climb" else "hang")
        if act != "spell":
            self.spell = None
        if act == "spell":
            self._begin_spell(now)
        elif act == "stroll":
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
            self._start_act(self.mind.pick(self.rng, now, self.gait, self.hour, "perch" if rested else ""), now)

    # --- asked from the menu (INBOX 1670, row C) ----------------------------------------------

    #: What the menu can ask for; `command` says whether it was done.
    COMMANDS = ("wave", "come", "wander", "nap", "wake", "perch", "stay", "roam")
    #: The states a request may break into; anything else (carried, thrown, falling, leaping) is left alone.
    _FREE = ("stand", "sit", "sleep", "walk", "drift", "act", "crouch", "wave", "notice", "startle", "land", "hop", "card")

    def command(self, name: str, now: float) -> bool:
        """A choice from the companion's menu, on the engine's own thread. True when it took
        effect; False when it cannot be done now (carried, no window to sit on, motion off), and it looks sad."""
        ran = self._command(name, now)
        if not ran:
            self.ex.fire("refused", now)
        return ran

    def _command(self, name: str, now: float) -> bool:
        if name == "come" and self.come is not None:  # a second "Come here" ends the following
            self.come = None
            return True
        if name == "stay":
            return self._stay(now)
        if name == "roam":
            return self._roam(now)
        if not self._free_for_command(now):
            return False
        self.last_active = now
        if name != "nap":
            self.nap_req = False
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
        self.come = None
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
        if self.state == "warp" and self.spell is not None and not self.reduced:  # a request ends the puff to a spell's spot: it is taken at once
            self.spell = None
            self._enter("stand", now)
            return True
        return self.state in self._FREE

    def _nap(self, now: float) -> None:
        if self.perch is not None and not self.reduced and self.gait == "walk":
            self.nap_after_land = True  # it never sleeps on a window: down first, then to sleep
            self._leave_perch(now, hop=False)
            return
        self.perch = None
        self.spell = None
        self.follow_until = self.follow_close_until = 0.0
        self.relocate_at = None
        if self.reduced:
            self._enter("sit", now)
            return
        self.nap_req = True
        spot = self._nap_spot()
        if spot is not None and self.gait == "walk":
            self._go(spot, "nap", now, plain=True)  # to a corner first, on foot
            return
        self._settle_to_sleep(now)

    def _nap_spot(self) -> tuple[float, float] | None:
        """Where a nap is taken: out of the middle third, by the nearer edge; None when it is there already."""
        m = self.current_monitor()
        x = tv.out_of_middle(self.x, m.area, self.size[0])
        if abs(x - self.x) < 12 * self._scale():
            return None
        return x, self.ground_y(m)

    def _settle_to_sleep(self, now: float) -> None:
        """A turn (to face the way it came, tail to the room) and a curl, then asleep."""
        if self.metrics:
            self._face(-self.facing, now)
        self._enter("sleep", now)

    def _wake_up(self, now: float) -> None:
        if not self.reduced:
            self._wake_for(now)
            if self.state == "stand":
                self._start_act("stretch", now)

    def _wake_for(self, now: float) -> None:
        if self.state in ("sleep", "sit"):
            self._enter("stand", now)

    def _come(self, now: float) -> bool:
        """"Come here" means follow me. The menu is opened on the figure, so it first waits for the pointer to
        leave (COME_MOVED px, or COME_WAIT s), then goes to it wherever it is. False without a pointer."""
        if self.pointer is None:
            return False
        self._wake_for(now)
        self.follow_until = self.follow_close_until = 0.0
        self.come = {"phase": "wait", "t0": now, "p0": self.pointer, "until": now + COME_FOR, "to": None}
        return True

    def _come_step(self, now: float) -> None:
        c, p, k = self.come, self.pointer, self._scale()
        assert c is not None
        if p is None or self.reduced or not self.roam or self.state in ("held", "pressed"):
            self.come = None
            return
        if c["phase"] == "wait":
            if now - c["t0"] >= COME_WAIT or math.hypot(p[0] - c["p0"][0], p[1] - c["p0"][1]) > COME_MOVED * k:
                c["phase"], c["until"] = "go", now + COME_FOR
            return
        self._come_move(c, p, now)

    def _come_move(self, c: dict, p: tuple[int, int], now: float) -> None:
        """Come here once the pointer has left the menu: go to it, arrive with a wave, keep company, then stop."""
        if self.state not in ("stand", "act") or self.busy:
            return
        if self.perch is not None:
            c["until"] = max(c["until"], now + 1.0)
            self.perch_until = max(self.perch_until, c["until"])
        want = self._come_target(p)
        if self._come_there(want, c["phase"] == "stay"):
            self._come_arrived(c, now)
            return
        if c["phase"] == "stay" and now >= c["until"]:
            self.come = None
            return
        c["phase"], c["to"] = "go", want
        self._come_head(want, now)

    def _come_arrived(self, c: dict, now: float) -> None:
        if c["phase"] == "go":  # arrived: a happy look, then company
            c["phase"], c["until"] = "stay", now + COME_FOR
            self.mind.feel("happy", now)
            self._enter("wave", now)
        elif now >= c["until"]:
            self.come = None

    def _come_head(self, want: tuple, now: float) -> None:
        if want[0] == "perch":
            self._climb(now, want[1])
        elif self.perch is not None:
            self._leave_perch(now, hop=True)
        else:
            self._go((want[1], self.ground_y(self.current_monitor())), "come", now, plain=True)

    def _come_target(self, p: tuple[int, int]) -> tuple:
        """A window top when the pointer is high over one it could stand on, else a spot on the ground by the pointer."""
        if self.roam_windows:
            h = self.size[1]
            over = [q for q in self._candidates() if q.left <= p[0] <= q.right and p[1] <= q.top + h]
            if over:
                return ("perch", max(over, key=lambda q: q.top))
        m = self.current_monitor()
        k = self._scale()
        side = -1 if p[0] > self.x + self.size[0] / 2 else 1
        gx = p[0] - self.size[0] / 2 + side * COME_GAP * k
        return ("ground", min(max(gx, m.area[0]), m.area[2] - self.size[0]))

    def _come_there(self, want: tuple, company: bool) -> bool:
        """At the goal; once there, company tolerates the pointer drifting (FOLLOW_GAP) before it re-targets."""
        if want[0] == "perch":
            return self.perch is not None and self.perch.key == want[1].key
        return self.perch is None and abs(want[1] - self.x) < (FOLLOW_GAP if company else 30) * self._scale()

    def _wander(self, now: float) -> bool:
        """Go to another part of the work area, far from here, and make it home."""
        self.come = None
        self._wake_for(now)
        if self.perch is not None:
            self._leave_perch(now, hop=True)
            return True
        m = self.current_monitor()
        k = self._scale()
        lo, hi = m.area[0], m.area[2] - self.size[0]
        far = [x for x in (lo + (hi - lo) * i / 10 for i in range(11)) if abs(x - self.x) >= WANDER_MIN * k]
        pool = far or [lo if self.x - lo > hi - self.x else hi]
        ground = self.ground_y(m)
        gx, _gy = self._clear_of_caret(tv.out_of_middle(self.rng.choice(pool), m.area, self.size[0]), ground)  # where _go aims
        if abs(gx - self.x) < 12 * k:
            return False
        # INBOX 1696: home from the moment it is chosen. Set on arrival, a step aside from the caret on the way (a puff to
        # the nearest edge) left the old home, and the next decision took it back there
        self.home_x = gx
        self._go((gx, ground), "settle", now)
        self.homed_at = now
        return True

    def carry(self) -> dict[str, Any]:
        """What a new engine takes up from this one when the runner restarts (frames drawn, a look or motion answer): the
        home, how long ago the menu chose it, and the goal of the menu's trip or a trip home still under way."""
        # read once each: this runs on the coordinator's thread while the overlay's own may finish a warp or a leg
        walking, pending, warp, plan, then = self.goal, self.pending, self.warp, self.edge_plan, self.then
        goal, then = (walking, then) if walking is not None else pending or (None, "")
        if self.state == "warp" and warp is not None:
            goal, then = warp["dst"], self.then
        if plan is not None:
            goal, then = plan
        live = goal is not None and then in RESUMED_THENS
        return {"home_x": self.home_x, "homed_for": self.now - self.homed_at, "goal": goal[0] if live else None, "then": then if live else ""}

    def take(self, carried: dict[str, Any] | None, now: float) -> None:
        """A restart's `carry`, on the new engine where the old one stood (INBOX 1696 i): the home is kept, so the middle
        third's relocation does not take it to the nearer edge (the one a trip set off from), and the menu's trip goes on."""
        if not carried:
            return
        m = self.current_monitor()
        lo, hi = m.area[0], m.area[2] - self.size[0]
        home = carried.get("home_x")
        if isinstance(home, (int, float)) and math.isfinite(home):
            self.home_x = min(max(float(home), lo), hi)
        homed = float(carried.get("homed_for", math.inf))
        self.homed_at = -math.inf if math.isnan(homed) else now - homed
        self.relocate_at = None
        self._maybe_relocate(now)
        goal = carried.get("goal")
        if not isinstance(goal, (int, float)) or not math.isfinite(goal) or self.reduced or not self.roam or self.state != "stand":
            return
        gx = min(max(float(goal), lo), hi)  # on this monitor, on its floor: a screen may have gone with the old runner
        if abs(gx - self.x) >= 12 * self._scale():
            self._go((gx, self.ground_y(m)), str(carried.get("then") or "home"), now)

    def _sit_on_window(self, now: float) -> bool:
        """Climb to a window's top edge the last scan found. False when there is none to sit on."""
        if not (self.roam_windows and self.roam) or self.perch is not None or not self._candidates():
            return False
        self._wake_for(now)
        self.climb_ready = 0.0
        self._climb(now)
        return True


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
        """Take hold of an edge: the work area's top, or (a window option on) a title bar, a maximised window's
        bar or a floating window's bottom edge, half the time when there is one."""
        m = self.current_monitor()
        left, top, right, _b = m.area
        lift, w, k = self._lift(), self.size[0], self._scale()
        x, hold, y = self.rng.uniform(left, right - w), None, top - lift  # the work area's top is always an edge
        spots = self._hang_spots(m)
        if spots and self.rng.random() < 0.5:
            hold, lo, hi = spots[self.rng.randrange(len(spots))]
            x, y = self.rng.uniform(lo, hi) - w / 2, self._grip(hold) - lift
        if self.gait != "float":
            if hold is None:
                self._rise((self.x, y), "hang", now)
            elif abs(x - self.x) > HANG_LEAP * k:  # too far to leap: walk under it first
                self.hang_plan = (hold, x)
                self._go((x, self.floor_y(m)), "hangleap", now, plain=True)
            else:
                self.hang_on = hold
                self._rise((x, y), "hang", now)
            return
        self._go((x, y), "hang", now)
        self.hang_on = hold

    def _leap_to_hang(self, now: float) -> None:
        """A walker is under the edge it came for: leap up and take hold, unless the window went on the way."""
        plan, self.hang_plan = self.hang_plan, None
        held = self._hold_of(plan[0]) if plan is not None else None
        if held is None:
            self._enter("stand", now)
            return
        self.hang_on = held
        self._rise((self.x, self._grip(held) - self._lift()), "hang", now)

    def _hang_ok(self) -> bool:
        """A hang trip needs an edge to take: the work area's top is always one (INBOX 1696 k), the windows' edges
        only with the windows option."""
        m = self.current_monitor()
        return self.roam and not self.reduced and (bool(self._hang_spots(m)) or self._open_side(m, "top"))

    def _hang_spots(self, m: Monitor) -> list[tuple[Perch, float, float]]:
        """The edges a hang may take hold of on this monitor, each with the range of x (the hands' centre) that
        puts the hands over it: title bars of the windows, maximised windows' bars, floating windows' bottoms."""
        if not (self.roam_windows and self.roam):
            return []
        left, top, right, _b = m.area
        w = self.size[0]
        found = []
        for p in self.windows + self.hangs:
            lo, hi = max(left + w / 2, p.left + HANG_HANDS * w), min(right - w / 2, p.right - HANG_HANDS * w)
            edge = self._grip(p)
            # A bar sits on the work area's top, so its frame rises above it like the screen-top hang (`_hang`).
            if hi - lo < 0.2 * w or p.top < top or (edge - self._lift() < top and p.kind != "bar") or edge > self.floor_y(m) - self._lift():
                continue
            found.append((p, lo, hi))
        return found

    def _peek_edges(self, m: Monitor, now: float) -> list[tuple[str, float]]:
        """The edges a peek may be taken from and how much each is wanted: behind a shown bar (the taskbar on whichever
        edge it is anchored, a docked sidebar) or out of a screen edge with no bar, the top too (hands over it). The
        play area's edge is the bar's inner edge, so one rule serves both. The mood bends the weights: a sleepy or
        startled one tucks behind a bar, a curious one peers out of an open edge, a happy or bored one plays at the top."""
        mood = self.mind.mood(now, self.hour)
        out = []
        for edge in ("bottom", "left", "right", "top"):
            if edge != "bottom" and not self._open_side(m, edge):
                continue  # another monitor adjoins: a figure walking there is not at an edge
            if edge == "top" and not (self.roam_windows and self.roam):
                continue  # a climb to the ceiling is a window-level trip, like a hang
            out.append((edge, self._edge_weight(edge, m.bar(edge) is not None, mood)))
        if self._tuck_spots(m):
            out.append(("tuck", PEEK_TUCK * (2.0 if mood in ("sleepy", "startled") else 1.0)))
        return out

    @staticmethod
    def _edge_weight(edge: str, behind: bool, mood: str) -> float:
        w = PEEK_BEHIND if behind else PEEK_OPEN[edge]
        if behind and mood in ("sleepy", "startled"):
            return w * 2.0
        if not behind and mood == "curious":
            return w * 1.5
        if edge == "top" and mood in ("happy", "bored"):
            return w * 2.0
        return w

    def _peek(self, now: float, edge: str | None = None) -> None:
        m = self.current_monitor()
        if edge is None:
            table = self._peek_edges(m, now)
            roll = self.rng.random() * sum(w for _e, w in table)
            edge = table[-1][0]
            for e, w in table:
                roll -= w
                if roll < 0:
                    edge = e
                    break
        if edge == "tuck":
            spot = self.rng.choice(self._tuck_spots(m))
            self.tuck_goal = spot.cover.key
            self._go((spot.x, spot.y), f"tuck_{spot.edge}", now)
        elif edge == "bottom":
            self._go((self.x, self.floor_y(m)), "peek_bottom", now)
        elif edge == "top":
            x = min(max(self.x, m.area[0]), m.area[2] - self.size[0])
            self._rise((x, m.area[1] - self._lift()), "peek_top", now)
        else:
            gx = m.area[0] if edge == "left" else m.area[2] - self.size[0]
            self._go((gx, self.y if self.gait == "float" else self.floor_y(m)), f"peek_{edge}", now)

    def _go(self, goal: tuple[float, float], then: str, now: float, plain: bool = False) -> None:
        """Travel to a point, then `then`. By distance: close range a step, the middle a walk, far a
        run or (a floater) a swoop that crouches first; each eased in and out, and it turns before
        it goes the other way."""
        self.then = then
        if not plain:
            m = self.current_monitor()
            gx = goal[0] if then == "card" or then.startswith("tuck_") else tv.out_of_middle(goal[0], m.area, self.size[0])
            goal = self._clear_of_caret(gx, goal[1])
        dist = abs(goal[0] - self.x) if self.gait == "walk" else math.hypot(goal[0] - self.x, goal[1] - self.y)
        if self.gait == "walk" and dist < 1.0:
            self._arrive(now)
            return
        mode = ""
        if not plain and dist > 12 * self._scale():
            mode = self._leg_mode(goal, then)
            mode = self._short_of_warp(mode, dist)
            if mode == "here":
                self._arrive(now)
                return
            if mode == "edge":  # walks off one edge, comes in from the other (a warp only for the slip itself)
                self.modes.append(mode)
                self._start_edge(goal, then, now)
                return
            if mode in tv.WARPS:
                self._start_warp(mode, goal, then, now)
                return
            self.modes.append(mode)
        far = dist / self._scale()
        self.mode = self._leg_pace(far, plain)
        self.pending = (goal, then)
        if self._winds_up(mode):
            self._enter("crouch", now)  # a crouch before a long run or a chain of hops
            self.pending = (goal, then)
            self._face(1 if goal[0] >= self.x else -1, now)  # the turn rides the crouch, so the walk does not set off with a stale facing and stand turning
            return
        self._begin_go(now)

    def _winds_up(self, mode: str) -> bool:
        """Whether the leg starts with a crouch: a run, or a chain of hops (`hop_next`, taken by `_begin_go`)."""
        self.hop_next = mode == "jump" and not self.reduced
        return (self.mode == "dash" or self.hop_next) and not self.reduced and self.gait == "walk"

    def _leg_pace(self, far: float, plain: bool) -> str:
        """step, walk or dash for a leg `far` logical px long; a chosen leg takes its pace from its mode (INBOX 1683 u)."""
        if far < STEP_UNDER:
            return "step"
        if plain or self.reduced or self.plain_legs:
            return "dash" if far >= DASH_OVER else "walk"
        return "dash" if self.modes and self.modes[-1] in ("run", "swoop") else "walk"

    def _begin_go(self, now: float) -> None:
        assert self.pending is not None
        goal, then = self.pending
        self.pending = None
        self.then = then
        if self.gait == "walk":
            self._enter("walk", now)
            self.hopping, self.hop_origin, self.hop_next = self.hop_next, self.travel, False
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
        if then == "hang" and self.gait == "float":
            # INBOX 1696 b: a glide up drew the idle frames (the stand picture sliding up) and waited under a busy
            # pointer part way; the way up to a hang is a blink or a cloud ride, never the one just used
            return "cloud" if self.modes[-1:] == ["blink"] else "blink" if self.modes[-1:] == ["cloud"] else self.rng.choice(("blink", "cloud"))
        m = self.current_monitor()
        area, w = m.area, self.size[0]
        long_leg = tv.far(self.x, goal[0], area) or tv.crosses_middle(self.x, goal[0], area, w)
        flat = abs(goal[1] - self.ground_y(m)) < 8 * self._scale() and abs(self.y - self.ground_y(m)) < 8 * self._scale()
        opposite = (self.x + w / 2 - (area[0] + area[2]) / 2) * (goal[0] + w / 2 - (area[0] + area[2]) / 2) < 0
        # INBOX 1696: a floater's glide or swoop draws the idle frames, so a menu wander that drifted read as the stand
        # picture sliding across the taskbar; it is a seen move (a blink, a ride, a portal), as between two spells
        seen = then == "settle" and self.gait == "float"
        mode = tv.pick_mode(
            self.rng, gait=self.gait, long_leg=long_leg or seen, mood=self.mind.mood(self.now, self.hour),
            recent=self.modes[-3:], edge_ok=flat and opposite and self.perch is None,
            run_ok=abs(goal[0] - self.x) >= RUN_MIN * self._scale(), between=then == "spell" or seen,
        )
        return mode

    def _short_of_warp(self, mode: str, dist: float) -> str:
        """A vanish needs somewhere else to go (INBOX 1721 c: "vanishes and reappears in the same spot"): a leg under
        `WARP_MIN` figure widths is walked or glided instead, or for a floater between two spells ("here") is not made at
        all (a glide between spells is never seen, INBOX 1696: it is there already)."""
        if mode not in tv.WARPS or dist >= WARP_MIN * self.size[0]:
            return mode
        if self.gait == "float":
            return "here" if self.then in ("spell", "settle") else "glide"
        return "walk"

    def _box_at(self, x: float, y: float, frame: str = "stand") -> tv.Rect:
        """The drawn box of `frame` for a window at (x, y), in screen px."""
        flip = self.facing < 0
        left, top, right, bottom = self._box(frame, flip)
        dx, dy = self._flip_dx(frame, flip), self._dy(frame)
        return x + left + dx, y + top + dy, x + right + dx, y + bottom + dy

    def _clear_of_caret(self, gx: float, gy: float, room: float = 0.0) -> tuple[float, float]:
        """A goal that is not over the text box: the nearer screen edge if it is. `room` (px) is more clearance, for a
        prop that reaches past the figure."""
        if self.caret is None:
            return gx, gy
        k, m = self._scale(), self.current_monitor()
        keep = tv.padded(self.caret, tv.CARET_MARGIN * k + room)
        if not tv.overlaps(self._box_at(gx, gy), keep):
            return gx, gy
        for side in sorted((-1, 1), key=lambda sd: abs(tv.edge_x(sd, m.area, self.size[0]) - gx)):
            x = tv.edge_x(side, m.area, self.size[0], 4 * k)
            if not tv.overlaps(self._box_at(x, gy), keep):
                return x, gy
        return gx, gy

    def _keep_off_caret(self, now: float) -> None:
        """Over the foreground window's text box (padded): step aside on the taskbar line (`_step_aside`), in a blink,
        a portal or a puff (a fade when reduced), inside a second."""
        if now < self.evade_ready or self.caret is None or self.nap_until:
            return
        k = self._scale()
        frame = self._frame(now)
        x, y, _clip = self._display(frame)
        left, top, right, bottom = self._box(frame, self.facing < 0)
        room = SPELL_ROOM * self.size[1] if self.state == "act" and extras.props.spec_of(self.act) is not None else 0.0
        keep = tv.padded(self.caret, tv.CARET_MARGIN * k + room)
        if not tv.overlaps((x + left, y + top, x + right, y + bottom), keep):
            return
        self.evade_ready = now + 1.0
        self._step_aside(keep, now)

    def _trip_ahead(self) -> tuple[tuple[float, float] | None, str]:
        """The goal of the trip under way and what it is for (a walk or drift, or the crouch before a run)."""
        if self.goal is not None:
            return self.goal, self.then
        return self.pending if self.pending else (None, "")

    def _step_aside(self, keep: tv.Rect, now: float) -> None:
        """Out of the caret's padded box `keep`, in a seen move. INBOX 1696 i: halfway along a trip the nearest edge is
        the one it set off from, so a caret by the taskbar line (a terminal's last line) sent it back where it came
        from. On a trip it goes to the goal itself when that is clear, finishing the trip, else to the edge on the
        goal's side; standing, to the nearest edge."""
        k, m = self._scale(), self.current_monitor()
        ground = self.ground_y(m) if self.perch is None else m.area[3] - self.size[1]
        goal, then = self._trip_ahead()
        if goal is not None and self.perch is None and then in PLAIN_THENS and not tv.overlaps(self._box_at(goal[0], ground), keep):
            self.target = self.pending = None
            self._start_warp("fade" if self.reduced else tv.caret_move(self.rng, self.modes), (goal[0], ground), then, now)
            return
        toward = goal[0] if goal is not None else self.x
        for side in sorted((-1, 1), key=lambda sd: abs(tv.edge_x(sd, m.area, self.size[0]) - toward)):
            tx = tv.edge_x(side, m.area, self.size[0], 4 * k)
            if not tv.overlaps(self._box_at(tx, ground), keep):
                self.perch = self.target = self.pending = None
                self._start_warp("fade" if self.reduced else tv.caret_move(self.rng, self.modes), (tx, ground), "evade", now)
                return

    def doing(self) -> str:
        """What a prop or presence act is, in words, for the menu ('' when it is only standing about): INBOX 1718 b."""
        if self.state != "act" or not self.act or (self.act not in extras.props.DOING and extras.props.spec_of(self.act) is None):
            return ""
        return extras.props.DOING.get(self.act, self.act.replace("_", " "))

    def enter_scene(self, now: float) -> str:
        """The first show (app start, the first minimise): it arrives, never a plain pop (INBOX 1718 a). A portal or a
        puff plays only its way in; an edge slips in from the screen edge nearest its home; a walker may instead drop in
        from the top and land. Returns the entrance chosen ('' when it stays put: reduced motion, or not standing)."""
        if self.reduced or self.state != "stand" or not self.roam:
            return ""
        # A drop needs an open top: with a screen above, it would come in on that one and land there.
        drop = 2.0 if self.gait != "float" and self._open_side(self.current_monitor(), "top") else 0.0
        pick = self.rng.choices(["portal", "puff", "edge", "drop"], [4.0, 2.0, 3.0, drop])[0]
        if pick == "drop":
            self.y = self.current_monitor().area[1] - self.size[1]
            self._start_fall(0.0)
            return pick
        self._start_warp(pick, (self.x, self.y), "stand", now)
        wp = self.warp["w"]
        self.warp["t0"] = now - (wp.out + wp.gap)  # the way out was skipped: the ring opens, the cloud thins, the edge lets it in
        self.state_until -= wp.out + wp.gap  # and the state ends with the way in, not half a second after it is fully seen
        self.legs.clear()
        return pick

    def _start_warp(self, mode: str, dest: tuple[float, float], then: str, now: float) -> None:
        """Vanish here and appear at `dest`, then do `then`. A portal opens a ring of nebula beside it,
        it steps in and the ring closes; a puff is a cloud; a fade is only the picture (reduced motion);
        an edge walk slips off the near edge of the screen and comes in from the far one."""
        src = (self.x, self.y)
        wp = tv.warp_for(mode, self.rng, math.hypot(dest[0] - self.x, dest[1] - self.y) / self._scale())
        side = tv.nearest_edge(self.x, self.current_monitor().area, self.size[0])
        if mode in tv.RIDES and abs(dest[0] - self.x) > 4 * self._scale():
            self._face(1 if dest[0] > self.x else -1, now)  # it sets off facing the way it goes
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
        if kind in tv.RIDES:  # carried the whole time: the cloud or bubble grows round it, holds, and thins at the end
            ut = min(1.0, t / wp.total)
            edge = bh.smooth(min(ut, 1.0 - ut) / 0.14)
            shimmer = 0.0625 * (int(t * 3.0) % 2) if edge >= 1.0 else 0.0  # a step a third of a second keeps the picture alive
            return (kind, edge - shimmer, self.facing), 1.0, 0.0
        if kind == "blink":
            alpha = 1.0 - bh.smooth((v - 0.3) / 0.4)
            return ("blink", math.sin(math.pi * v) ** 0.7, 0), alpha, 0.0
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
        if kind in tv.RIDES:
            self._ride(w, t / wp.total)
            w["moved"] = True
        elif not w["moved"] and t >= wp.out:
            w["moved"] = True
            self.x, self.y = w["dst"]
            if kind == "edge":
                self.peek_edge = "right" if w["side"] < 0 else "left"  # in from the far edge
                self.facing = -w["side"]
        if kind == "edge":
            self.sink = bh.smooth(t / wp.out) if t < wp.out else 1.0 if t < wp.out + wp.gap else 1.0 - bh.smooth((t - wp.out - wp.gap) / wp.back)
        if t >= wp.total:
            self._finish_warp(now)

    def _ride(self, w: dict, u: float) -> None:
        """Where a cloud or a bubble has carried it by `u` (0 to 1) of the ride: eased along the line, a cloud with
        a slow bob, a bubble up and over in an arc that comes back down at the end."""
        e = bh.smooth(min(1.0, max(0.0, u)))
        (sx, sy), (dx, dy) = w["src"], w["dst"]
        k = self._scale()
        self.x = sx + (dx - sx) * e
        base = sy + (dy - sy) * e
        if w["kind"] == "bubble":
            lift = min(150.0 * k, 40.0 * k + abs(dx - sx) * 0.12)
            self.y = base - lift * math.sin(math.pi * e)
        else:
            self.y = base - 6.0 * k * math.sin(math.pi * e) - 2.5 * k * math.sin(u * 14.0) * math.sin(math.pi * e)

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
            if self.flash is None and now - self.blink_at >= AMBIENT_EVERY[0]:  # G2: the turn is blinked into
                self._blink(now)  # (never within the least gap of another)
                self.next_ambient = max(self.next_ambient, now + AMBIENT_EVERY[0])
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
        want = k * max(0.12, min(rise, max(0.2, fall)))
        # the pace never rises faster than PACE_SLEW a second from where it was last: a start, the end of a turn or the end of
        # a yield that jumped to the pace set a step of speed, which is an acceleration spike for the tail's spring and moved
        # the hem 5 to 6 px in one draw (INBOX 1683 j). A gap since the last step is a fresh start from nothing.
        gap = now - self.pace_at
        self.pace_at = now
        fresh = not 0.0 <= gap <= PACE_GAP
        base, step = (0.0, 1.0 / 60.0) if fresh else (self.pace_last, gap)
        self.pace_last = min(want, base + PACE_SLEW * step) if want > base else want
        return self.pace_last

    def _brake(self, now: float, dt: float) -> float:
        """The pace while it gives way to a busy pointer: the last pace decays over a few draws, so the stop is a slowing
        and the hem and tail are not thrown by a speed that fell to nothing in one draw (INBOX 1683 j). 0 once stopped."""
        self.pace_last *= math.exp(-dt / YIELD_BRAKE_S)
        if self.pace_last < 0.03:
            self.pace_last = 0.0
            self.walk_started = now  # the pace eases in from when it moves, not from when it was told
        self.pace_at = now
        return self.pace_last

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
        elif then == "hangleap":
            self._leap_to_hang(now)
        elif then.startswith("peek_"):
            self._arrive_peek(then[5:], now)
        elif then.startswith("tuck_"):
            self._arrive_tuck(then[5:], now)
        else:
            self._arrive_plain(then, now)
        if then in RESUMED_THENS and self.goal is None and self.perch is None and self.state != "warp":
            self.home_arrivals += 1  # where it lives now: the runner saves it, as a drop is saved

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
            self._stand_on(p, now)  # stays for PERCH_FOR (45 to 120 s): long enough to be seen (it was 8 to 20, then 20 to 50)
            self._enter("stand", now)
            self.state_until = self.perch_until

    def _arrive_peek(self, edge: str, now: float) -> None:
        self.peek_edge = edge
        self.sink_max = PEEK_HEAD if edge == "bottom" else PEEK_SIDE
        if edge == "top":
            self.sink_max = min(0.8, max(0.1, 1.0 - self.hang_top - PEEK_TOP_SHOWN))
            self.y = self.current_monitor().area[1] - self._lift()  # the hands are over the edge
        if edge == "left":
            self.facing = 1
        elif edge == "right":
            self.facing = -1
        self._enter("peek", now)

    def _tuck_spots(self, m: Monitor) -> list[TuckSpot]:
        """Where a figure may hide behind the side of a window: the window's frame reaches the figure's whole height
        (the clip is a rectangle, so a window that stops short would show the feet), is at least as wide as the
        figure, has room on the screen for it beside the edge, and nothing above it covers that edge. Never the window
        with the text caret in it (the person is working there), and only from a recent scan (INBOX 1683 k)."""
        if not (self.roam_windows and self.roam) or self.reduced or self.now - self.covers_at > TUCK_FRESH or not self.covers:
            return []
        w, h = self.size
        k = self._scale()
        keep = tv.padded(self.caret, tv.CARET_MARGIN * k) if self.caret is not None else None
        found: list[TuckSpot] = []
        for c in self.covers:
            y = self.floor_y(m) if self.gait != "float" else min(max(self.y, c.rect[1]), c.rect[3] - h)
            if not self._tuck_blocked(c.rect, y, k, keep):
                found.extend(self._tuck_sides(c, m, y))
        return found

    def _tuck_blocked(self, rect: tuple[float, float, float, float], y: float, k: float, keep) -> bool:
        """The window cannot hide the figure: too narrow, not reaching its whole height, or where the person types."""
        w, h = self.size
        left, top, right, bottom = rect
        return right - left < w or top > y or bottom < y + h - TUCK_REACH * k or (keep is not None and tv.overlaps(rect, keep))

    def _tuck_sides(self, c: Cover, m: Monitor, y: float) -> list[TuckSpot]:
        """The sides of one window with room on the screen and nothing above the edge."""
        w, h = self.size
        left, _top, right, _bottom = c.rect
        found: list[TuckSpot] = []
        for edge, x, wall in (("right", left - w, left), ("left", right, right)):
            if x < m.area[0] or x + w > m.area[2]:
                continue
            zone = (wall - w, y, wall + w, y + h)
            if not any(tv.overlaps(zone, a) for a in c.above):
                found.append(TuckSpot(c, edge, x, y))
        return found

    def _arrive_tuck(self, edge: str, now: float) -> None:
        """At the foot of the window's side: tuck if it is still there, where it was and still a place, else stand."""
        key, self.tuck_goal = self.tuck_goal, None
        spot = next((s for s in self._tuck_spots(self.current_monitor()) if s.cover.key == key and s.edge == edge), None)
        if spot is None or abs(spot.x - self.x) > 4 * self._scale():
            self._enter("stand", now)
            return
        self.tuck = spot.cover
        self._arrive_peek(edge, now)

    def _check_tuck(self, now: float) -> None:
        """Hidden behind a window: come out when it is gone (closed or minimised), has moved, has another window over
        its edge, or the person starts typing in it. Read with every scan, and when the caret moves."""
        cover = self.tuck
        if cover is None or self.state != "peek":
            return
        cur = next((c for c in self.covers if c.key == cover.key), None)
        k = self._scale()
        why = ""
        if cur is None:
            why = "gone"
        elif any(abs(a - b) > PERCH_MOVED * k for a, b in zip(cur.rect, cover.rect)):
            why = "moved"
        else:
            wall = cur.rect[0] if self.peek_edge == "right" else cur.rect[2]
            zone = (wall - self.size[0], self.y, wall + self.size[0], self.y + self.size[1])
            if any(tv.overlaps(zone, a) for a in cur.above):
                why = "covered"
            elif self.caret is not None and tv.overlaps(cur.rect, tv.padded(self.caret, tv.CARET_MARGIN * k)):
                why = "typed in"
        if why:
            self.notes.append(f"tuck ended: the window it was behind is {why}")
            self.tuck = None
            self._enter("emerge", now)

    def _arrive_plain(self, then: str, now: float) -> None:
        if then == "follow":
            self._enter("stand", now)
            self.state_until = now + 1.5
        elif then == "home":
            self._enter("land" if self.mode == "dash" else "stand", now)
        elif then == "spell":
            self._enter("stand", now)
            self._start_spell(now)
        else:
            self._enter("stand", now)
            if then == "rest":
                self.state_until = now + self.rng.uniform(*REST_FOR)
            if then == "nap":
                self._settle_to_sleep(now)
            elif then in ("clock", "greet", "settle", "longwalk"):
                self._arrive_trip(then, now)

    def _do_stand(self, now: float, dt: float) -> None:
        self._ambient(now)
        self._after_stand(now)

    def _do_sit(self, now: float, dt: float) -> None:
        self._ambient(now)
        if self.mind.shift_due(now, self.var_rng):
            self.shift_at = now  # a seat shift: a lean and a settle (`_ground_pose`), the window does not move
        idle = now - self.last_active
        if idle >= IDLE_SLEEP:
            self._enter("sleep", now)
        elif now >= self.state_until and idle < IDLE_SIT and not self.reduced and self.roam:
            self._enter("stand", now)

    def _do_sleep(self, now: float, dt: float) -> None:
        if self.mind.shift_due(now, self.var_rng):
            self.shift_at = now  # turns over in its sleep: the same lean and settle
        if self.nap_until and now >= self.nap_until:  # its own long nap is over: up with a stretch
            self._wake_up(now)

    def _do_wave(self, now: float, dt: float) -> None:
        if now >= self.state_until:
            self._enter("stand", now)

    def _do_notice(self, now: float, dt: float) -> None:
        if now >= self.state_until:
            self._enter("stand", now)

    def _do_startle(self, now: float, dt: float) -> None:
        if now >= self.state_until:
            self._enter("stand", now)
            self.settle_at = now + EXHALE_AFTER[0] + (EXHALE_AFTER[1] - EXHALE_AFTER[0]) * self.var_rng.random()  # the exhale

    def _do_land(self, now: float, dt: float) -> None:
        if now >= self.state_until:
            if self.mind.event == "startled" and not self.reduced and now - self.mind.event_at < 20.0:
                self.mind.feel("proud", now)  # a little pleased with the landing; the landing was the one settle
            if self.nap_after_land and not self.reduced:
                self.nap_after_land = False
                self._enter("sleep", now)
                return
            self._enter("sit" if self.reduced else "stand", now)
            if self.perch is None and not self.reduced and self.roam and self._away() and tv.in_middle(self.x, self.current_monitor().area, self.size[0]):
                # down from a window it hopped off into the middle third: a stand of a few breaths, then home. The full settle (minutes
                # of in-place acts) rested it in the middle third, where it never rests (a 15 minute spell there in one hour)
                self.state_until = min(self.state_until, now + self.rng.uniform(*AWAY_STAND_FOR))

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
        if self._turning(now):
            self.walk_started, self.pace_last = now, 0.0  # the pace eases in from when it moves, not from when it was told
            return
        pace = self._brake(now, dt) if self._yields(now, math.cos(self.heading) * 90 * scale) else self._pace(now, dist)
        if pace <= 0.0:
            return
        self._drift_move(m, FLOAT_SPEED * scale * pace * dt)
        if abs(math.cos(self.heading)) > 0.5:
            self._face(1 if math.cos(self.heading) > 0 else -1, now)
        if wandering and now >= self.state_until:
            self.goal = None
            self._enter("stand", now)

    def _drift_move(self, m: Monitor, step: float) -> None:
        """Move `step` px along the heading, inside the work area and (a wander) the hover band."""
        left, top, right, _b = m.area
        self.x = min(max(self.x + math.cos(self.heading) * step, left), right - self.size[0])
        high = top - (self._lift() if self.then == "hang" and self.trip else 0.0)
        if not self.trip:  # a wander turns wide, so the band is held by the clamp too, not only by the goal
            high = max(high, self.ground_y(m) - FLOAT_BAND * self.size[1])
        self.y = min(max(self.y + math.sin(self.heading) * step, high), self.floor_y(m))

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
        if self.pulling is not None:
            if now >= self.scrabble_until:
                self._pull_up(now)
            return
        if now >= self.hang_glance_at and now < self.state_until - 3.0:
            self._face(-self.facing, now)
            self.hang_glance_at = now + self.rng.uniform(*HANG_GLANCE)
        self._let_one_go(now)
        if now >= self.state_until:
            if self.swing_to is not None:
                self._release_swing(now)
            elif self.releasing:
                self.releasing = False
                self._let_go()
            else:
                self._end_hang(now)

    def _end_hang(self, now: float) -> None:
        """The rest is up: pull up onto the edge it holds, swing and drop to a window top, or (a window's edge only) let
        go after a startled beat. A hang from the screen top never falls on a roll or a timer: after its full rest, with nothing to pull
        onto or drop to, it makes a calm drop to its feet (INBOX 1683 h; owner 2026-11-10)."""
        held = self._hold_of(self.hang_on) if self.hang_on is not None else None
        w, h = self.size
        table: dict[str, float] = {"react": HANG_ENDS["react"]} if self.hang_on is not None else {}
        if held is not None and held.kind == "top" and held.top - h >= self.current_monitor().area[1]:
            table["pull"] = HANG_ENDS["pull"]
        drop = self._drop_target()
        if drop is not None:
            table["swing"] = HANG_ENDS["swing"]
        if not table:  # the screen top, nothing to pull onto or drop to: a chosen, calm drop to its feet, never a fall (owner 2026-11-10)
            self.legs.append(("hang_calm", self.x, self.x, now))
            self.hang_on = None
            self._rise((self.x, self.ground_y()), "calm", now)
            return
        roll = self.rng.random() * sum(table.values())
        pick = next(iter(table))
        for name, wt in table.items():
            roll -= wt
            if roll < 0:
                pick = name
                break
        self.legs.append(("hang_" + pick, self.x, self.x, now))
        if pick == "pull" and held is not None:
            x = stand_x(held, self.x, w)
            self.target = held
            self.legs.append(("climb", self.x, x, now))
            self._rise((x, held.top - h), "perch", now)
        elif pick == "swing" and drop is not None:
            self.swing_to, self.swing_at = drop, now
            self.state_until = now + SWING_FOR
        else:
            self.releasing = True  # a startled beat (a glance, the mood) and then it lets go
            self.mind.feel("startled", now)
            self._face(-self.facing, now)
            self.state_until = now + REACT_FOR

    def _drop_target(self) -> Perch | None:
        """A window top below the hands that a swing from here can reach (the nearest by sideways distance)."""
        k, (w, h) = self._scale(), self.size
        hands = self.y + self._lift()
        best, best_dx = None, SWING_REACH * k
        for p in self._candidates():
            if p.top - h < hands + 40 * k:  # not clearly below
                continue
            if self.hang_on is not None and p.key == self.hang_on.key:
                continue
            x = stand_x(p, self.x, w)
            if abs(x - self.x) <= best_dx:
                best, best_dx = p, abs(x - self.x)
        return best

    def _release_swing(self, now: float) -> None:
        """At the top of the swing: let go and drop onto the window top chosen when it began (if it is still
        there and still below); else the plain letting go with its startled beat."""
        p = next((q for q in self.windows if self.swing_to is not None and q.key == self.swing_to.key), None)
        self.swing_to = None
        if p is None or p.top - self.size[1] < self.y + self._lift():
            self.releasing = False
            self._let_go()
            return
        x = stand_x(p, self.x, self.size[0])
        self.target, self.hang_on = p, None
        self.legs.append(("drop", self.x, x, now))
        self._rise((x, p.top - self.size[1]), "perch", now)

    def _let_go(self) -> None:
        """Off the ceiling: a walker falls, a floater drifts down to its hover height."""
        self._start_fall(0.0)
        # the pose it drops in is taller than the hang: keep all of it on the screen
        m = self.current_monitor()
        if self._open_side(m, "top"):
            self.y = max(self.y, self._ride_limits("fly" if self.state == "fly" else self.state)[2])

    def _peek_depth(self, t: float) -> float:
        plan = TUCK_PLAN if self.tuck else PEEK_PLAN
        for (t0, d0), (t1, d1) in zip(plan, plan[1:]):
            if t <= t1:
                return d0 + (d1 - d0) * (t - t0) / (t1 - t0)
        return plan[-1][1]

    def _top_peek(self, t: float) -> None:
        """The top peek's pose at `t`: pulled up out of sight hanging, turned over there, lowered upside-down to peer."""
        d = PEEK_TOP_PLAN[-1][1]
        for (t0, d0), (t1, d1) in zip(PEEK_TOP_PLAN, PEEK_TOP_PLAN[1:]):
            if t <= t1:
                d = d0 + (d1 - d0) * bh.smooth((t - t0) / (t1 - t0))
                break
        self.peek_flip = d > 1.0
        self.sink = min(d, 1.0)
        self.peek_show = max(0.0, d - 1.0) * PEEK_TOP_PEER

    def _do_peek(self, now: float, dt: float) -> None:
        t = now - self.peek_started
        if self.peek_edge == "top":
            self._top_peek(t)
            if now >= self.state_until:
                self._arrive_hang(now, self.current_monitor())  # back down on its hands, not standing in the air
            return
        depth = self._peek_depth(t)
        if depth <= 1.0:
            self.sink = depth * self.sink_max
        else:  # ducked: from the head showing to all of it gone
            self.sink = self.sink_max + (1.0 - self.sink_max) * (depth - 1.0)
        if self.peek_edge == "bottom" and not self.peek_turned and t >= 1.8:
            self.peek_turned = True
            self.facing = -self.facing
        if now >= self.state_until:
            if self.peek_edge == "top":
                self._arrive_hang(now, self.current_monitor())  # back down on its hands, not standing in the air
            else:
                self._enter("stand", now)

    def _do_emerge(self, now: float, dt: float) -> None:
        t = min(1.0, (now - self.phase_started) / EMERGE_FOR)
        self.sink = self.phase_from[0] * (1.0 - t)
        if now >= self.state_until:
            if self.peek_edge == "top":
                self._arrive_hang(now, self.current_monitor())
                return
            self.peek_edge = None
            self.sink = 0.0
            self._enter("wave" if not self.reduced else "sit", now)

    def _wake(self, now: float) -> int | None:
        """When to draw next: the state's own pace, and never later than the streams' (`FLOW_TICK_MS`, a calm
        drift's `FLOW_CALM_MS` under reduced motion), so no part of the figure is still for a second."""
        wake = self._wake_state(now)
        if self.state == "pressed" or self.state == "warp":
            return wake
        mine = self.ex.wake_ms(now)
        if mine is not None:
            wake = mine if wake is None else min(wake, mine)
        tick = FLOW_CALM_MS if self.reduced else FLOW_SLEEP_MS if self.state == "sleep" else FLOW_TICK_MS
        if self._tail_ticks():
            tick = self._tail_ms(now)
        if self.state == "act" and self.spell is not None and self.act == self.spell["act"] and not self.reduced:
            tick = FLOW_SPELL_MS
        return tick if wake is None else min(wake, tick)

    def _wake_state(self, now: float) -> int | None:
        s = self.state
        if s == "card":  # waiting with a card, even when still: it swaps and it runs out
            return max(MIN_WAKE_MS, min(int(CARD_SWAP * 1000), int(math.ceil((self.state_until - now) * 1000))))
        if self.reduced:
            return None
        if s in ("walk", "held", "drift", "hang", "rise", "peek", "emerge", "crouch", "warp", "land") or self.turn_to:  # land: its squash eases at 60 Hz (INBOX 1683 j: one 170 ms draw jumped it 18 px)
            return self._moving_wake(s)
        if s == "act":
            soonest = min(self.state_until, self._next_pose_change(now, 0.5))
            return max(REST_DRAW_MS if self.ex.calm(self.act) else TICK_WALK_MS, int(math.ceil((soonest - now) * 1000)) + 1)
        if s in ("fall", "hop", "fly", "leap"):  # before the tail: it swings through a fall, and the window moves fastest here
            return TICK_FALL_MS
        if self._follow_moving():  # the tail still swings, or the body is easing to its pose
            return TAIL_TICK_MS
        if s == "pressed":
            return None
        if s in REST_LIFE:  # alive in place: the next step of the breath or the tail (or a sit's blink), else the pointer look
            nxt = self._next_life_change(now)
            if s == "sit":
                nxt = min(nxt, self._flash_due(now) if self.flash else self.next_ambient)
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
        if s in ("stand", "act") and self.turn_to:  # a turn in place (scan_horizon's) stays under the rest cap of 12 draws a second
            return REST_DRAW_MS
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
            due += [self._flash_due(now)] if self.flash else [self.next_ambient]
            due.append(self.last_active + IDLE_SIT)
        if s in ("stand", "sit") and self.lonely_stretch != self.last_active and self.last_active + LONELY_AFTER > now:
            due.append(self.last_active + LONELY_AFTER)
        # The next idle frame: a redraw only when the index changes, and not while a blink or a look is under way. A look and a
        # blink's shut step draw their own picture whatever the index (those edges were wakes that drew nothing new); in a
        # blink's lid steps the breath's step is drawn with the lid's next one (a third of the blink late at most; the idle
        # clock is untouched, so the cycle keeps its tempo and nothing else moves).
        if self._idling() and not self.flash:
            due.append(self._idle_next(now))
        return due

    def _next_pose_change(self, now: float, horizon: float = 1.0) -> float:
        """The next time the body pose crosses a step of the cache grid, looking ahead."""
        if self.state == "act" and not self.reduced and self.turn_to == 0:
            return self._next_act_pose_change(now, horizon)
        base = bh.quantised(self.cur)
        t = now
        while t < now + horizon:
            t += POSE_LOOK_STEP  # a display frame: the 50 ms look-ahead stepped an act's pose at 20 a second (INBOX 1683)
            if bh.quantised(self._target_pose(t)) != base:
                return t
        return now + horizon

    def _next_act_pose_change(self, now: float, horizon: float) -> float:
        """`_next_pose_change` for an act with no turn: `_target_pose`'s act branch with everything that does not change
        over the look-ahead read once (the same arithmetic in the same order, so the same poses)."""
        keys = bh.ACTIVITIES[self.act or "breathe"].keys
        started, length = self.act_started, max(0.01, self.act_len)
        ease, amp = self.act_var.ease, self.act_var.amp
        side = 1 if self.facing > 0 else -1
        drag = self.tail.tip
        shift_at, flip = self.shift_at, 1 if self.mind.shifts % 2 else -1
        base = bh.cell(*self.cur)
        t = now
        while t < now + horizon:
            t += POSE_LOOK_STEP
            sx, sy, lean = bh.sample3(keys, (t - started) / length, ease)
            sx, sy, lean = 1.0 + (sx - 1.0) * amp, 1.0 + (sy - 1.0) * amp, lean * amp * side
            u = (t - shift_at) / SHIFT_FOR
            if 0.0 <= u < 1.0:
                lean += SHIFT_LEAN * math.sin(math.pi * u) * flip
                sy -= 0.02 * math.sin(math.pi * u)
            if bh.cell(sx, sy, lean, drag) != base:
                return t
        return now + horizon

    def _display(self, frame: str) -> tuple[float, float, tuple[int, int, int, int] | None]:
        """Where the window is drawn and which part of the frame shows: the rest
        position, less the sink behind an edge."""
        w, h = self.size
        if self.peek_flip and self.peek_edge == "top":
            # upside-down, drawn turned half a circle on the tumble's square canvas: its head comes first below the
            # edge and everything above the work area's top is clear (the canvas pad shifts the clip)
            top, side = self.current_monitor().area[1], math.ceil(math.hypot(w, h))
            yb = top - h + round(self.peek_show * h)
            return self.x, yb, (0, max(0, top - yb + (side - h) // 2), side, side)
        x, y = self.x, self.y
        # a bonk shows the startle frame in mid-air: no foot offset of its own
        y += self._dy("held" if self.state == "fly" else frame)  # each frame is registered to the floor, so a hop's drawn feet are `hop_lift` above it
        y -= self.hop_lift if self.hopping else 0.0
        x += self._flip_dx(frame, self.facing < 0)
        if self.peek_edge == "top" or (self.state == "rise" and self.then == "peek_top"):
            # hands over the top edge: what is above the play area's top (behind the bar, or off the screen) is clear
            up = round(self.sink * (h - self._lift())) if self.peek_edge == "top" else 0
            return x, y - up, (0, min(h, max(0, round(self.current_monitor().area[1] - (y - up)))), w, h)
        if self.sink <= 0 or self.peek_edge is None:
            return x, y, None
        if self.peek_edge == "bottom":
            hidden = round(self.sink * h)
            # cut where the work area ends, not where the (lower) window does
            return x, y + hidden, (0, 0, w, max(0, h - hidden - round(self._dy(frame))))
        if self.wrapping is not None:
            w = max(w, round(self._box(self._fly_frame())[2]))  # a tumble's canvas is wider than the window
        hidden = round(self.sink * w)
        if self.peek_edge == "left":
            return x - hidden, y, (hidden, 0, w, h)
        return x + hidden, y, (0, 0, w - hidden, h)

    def _output(self, now: float) -> Output:
        frame = self._frame(now)
        x, y, clip = self._display(frame)
        fx, alpha, _squeeze = self._warp_view(now) if self.state == "warp" else (None, 1.0, 0.0)
        if self.away_until is not None:
            alpha = 0.0  # out through the top
        if fx is not None:
            fx = (fx[0], round(max(0.0, min(1.0, fx[1])) * 16) / 16.0, fx[2])  # as alpha is: a step finer than 1/16 is a picture nobody sees
        prop, face = self.ex.view(now)
        return Output(
            frame, int(round(x)), int(round(y)), self.facing < 0, self._wake(now),
            self.click_now, self.settled_now, clip, self.card_clicked, self._pose(), fx, round(alpha * 16) / 16.0,
            self.angle + self.wob if frame.startswith("spin") and self.state == "fly" else math.pi if self.peek_flip or (self.upside and self.state == "held") else None,
            self._flow_view(now, frame, self._lower_state(now, face)) if fx is None else None, prop, self._blink_face(now, frame, face),
            self._tail_view(now, frame) if fx is None and self.tail_layer_on else None, self._edge_squash(now),
        )
