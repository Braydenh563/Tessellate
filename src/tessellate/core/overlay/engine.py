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
from . import extras
from . import landing as ld
from . import presence as pr
from . import travel as tv
from . import vitals, wisps

#: Seconds.
MAX_DT = 0.1
#: One ambient moment (a blink, now and then a look) this far apart, like the in-app companion's blinks
#: (INBOX 1670, 16:40Z: irregular, 2 to 7 s): each costs two wakes (start and end). The gap is drawn
#: skewed to the short end (a person blinks more often than not within 4 s), and one blink in `DOUBLE_SHARE`
#: is followed by a second after `DOUBLE_GAP` seconds.
AMBIENT_EVERY = (2.0, 7.0)
AMBIENT_SKEW = 1.4
DOUBLE_SHARE = 0.14
DOUBLE_GAP = 0.12  # (BLINK_FOR 0.28: the double still starts within 0.45 s of the first)
LOOK_SHARE = 0.12
BLINK_FOR = 0.28
#: A blink is eased (INBOX 1704: "some of the blink animations look off": the shipped shut-eye picture popped in for 0.18 s): the
#: lid comes down to step 2 of `faces.SHUT` (a half lid), the shut picture holds, and the lid goes up through step 2 again (each
#: phase is a wake, and the standing wake budget in `tests/test_overlay_engine.py` allows three). Shares of
#: `BLINK_FOR` at which each phase begins, and the step it draws (0: the shut picture).
BLINK_PHASES = ((0.0, 2), (0.3, 0), (0.7, 2))
LOOK_FOR = 1.2
#: Each idle cycle runs up to this share faster than 4 s, and `IDLE_SLOWEST` slower (research A7). The slow side is
#: short because a picture held past the 170 ms stream tick would be redrawn unchanged before it moved on.
IDLE_SPREAD = 0.08
IDLE_SLOWEST = 0.02
STAND_FOR = (3.0, 8.0)
#: How long a stand lasts after a landing in the middle third before it heads back.
AWAY_STAND_FOR = (15.0, 35.0)
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
#: States that leave the figure out of breath (INBOX 1719 b): a sit or a sleep begun soon after one breathes quicker,
#: easing back over `vitals` `half_s` (the period is set as the rest begins, so the picture never jumps).
EXERTING = ("walk", "hop", "leap", "land", "fly", "fall", "held", "rise", "drift")
TAIL_WANDER_S = 43.0
TAIL_LAG = 0.9
#: Finer than the walk's grid so a 1.5 px breath is a few smooth steps, not a hard on and off.
Q_BREATH = 0.005
#: A drifting floater breathes in the figure (share of height, period s) now that the window does not bob.
DRIFT_BREATH = 0.012
DRIFT_BREATH_S = 4.4
#: A calm stand leans this much (about 1.7 degrees at most) on two slow clocks (seconds), so no two 4 s cycles draw the same pictures.
STAND_LEAN = 0.03
STAND_LEAN_S = (53.0, 31.0)
#: The wisps and the nebula streams (INBOX 1683 c) are redrawn at least this often, so none is still for a second:
#: 10 a second (the picture itself changes only as a strand crosses a step of `behaviour.FLOW_Q`); a slow drift
#: under reduced motion, once a second. A body's speed over this (px per second at 96 dpi) is a jump, not a move.
FLOW_TICK_MS = 170
#: A sleeper's streams drift slower (its breath is the only quick thing), a third of the pictures.
FLOW_SLEEP_MS = 340
FLOW_CALM_MS = 1000
#: In a presence spell the streams and the prop step together at this pace (3 pictures a second at most): minutes of
#: it must cost what a minute of standing does (INBOX 1692, the CPU budget).
FLOW_SPELL_MS = 300
FLOW_SPEED_MAX = 900.0
#: States in which the streams keep their last picture: held, thrown, falling or hopping move the window every
#: display frame, and a mesh warp each would cost a quarter of the frame at 96 dpi (measured 5.7 ms).
FLOW_FROZEN = ("pressed", "held", "fly", "fall", "hop", "leap")
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
#: After a startle a stand lets its breath out 1 to 3 s later (`EXHALE_AFTER`): shoulders down `EXHALE_DIP` of the height for `EXHALE_FOR` s.
EXHALE_AFTER = (1.0, 3.0)
EXHALE_FOR = 1.6
EXHALE_DIP = 0.03
#: Share of the height the tail's vertical swing (px, `Trail.lift`) adds: 12 px at most, so under 4%.
LIFT_SY = 0.003
NOTICE_COOLDOWN = 8.0
#: Not touched for this long: sits, then sleeps. Ten and twenty minutes (the owner's
#: open call, taken): it keeps doing small acts while the person is away from the
#: keyboard, since the big acts (hang, peek) come two to four minutes apart.
IDLE_SIT = 600.0
IDLE_SLEEP = 1200.0
#: Left alone this long (no pointer near it, no touch, no reaction): a sad look, once per idle stretch. Fifteen minutes,
#: between the sit at `IDLE_SIT` and the sleep at `IDLE_SLEEP`, so it is seen sitting and never while asleep.
LONELY_AFTER = 900.0
#: The idle cycle (`idle0` to `idle23`, one tail beat and one breath): a standing figure draws these at
#: `IDLE_FPS` all the time so the parts never stop (INBOX 1670, 15:40Z); reduced it is the one `stand` frame
#: and costs no wake.
IDLE_FRAMES = 24
#: 24 frames at 6 a second keep the cycle at 4 s (one tail beat, one breath) with twice the in-betweens.
#: Faster would be the energetic child the owner does not want (INBOX 1670, 14:10Z).
IDLE_FPS = 6.0
#: The wave's arm swing (`sprites.WAVE_FRAMES`): six frames a swing and back, a little over two swings a second.
WAVE_FPS = 14.0

#: Logical pixels (scaled by the monitor's dpi).
#: Lively, not a crawl (INBOX 1683 f: "all it does is poof"); was 55, so a 1,500 px leg took 16 s at a dash.
WALK_SPEED = 130.0
#: A unhurried pace, by distance (INBOX 1670: "a buddy, not a nuisance"): close range is a step,
#: the middle distance a walk, far a run (a swoop for a floater), each eased in and out.
STEP_UNDER = 60.0
DASH_OVER = 420.0
STEP_K, DASH_K = 0.6, 2.0
EASE_IN = 0.7
PACE_SLEW, PACE_GAP = 3.0, 0.4  # a draw slower than 10 a second (8 on a big 200% screen) is a hitch, not a fresh start (INBOX 1696 i)
EASE_OUT = 70.0
CROUCH_FOR = 0.25
TURN_FOR = 0.24
#: Home: where it was left. Most of its time is spent there; strolls stay within STROLL px of it,
#: a trip away comes at most every TRIP_EVERY seconds (a few an hour), then it goes home.
STROLL = 150.0
TRIP_EVERY = (520.0, 1100.0)
TRIP_FIRST = (300.0, 700.0)
#: Each TRIP_OVERDUE_S a trip is overdue adds one to its weight, to TRIP_OVERDUE_MAX more.
#: How lively it is (research DG5, the menu's Activity): (the gap between trips times this, the weight of a trip, a
#: climb, a hang or a peek times this). A calm one also takes no long walk.
LIVELY = {"calm": (1.6, 0.5), "usual": (1.0, 1.0), "lively": (0.6, 1.6)}
TRIP_OVERDUE_S = 300.0
TRIP_OVERDUE_MAX = 4.0
#: The long walk: a low chance among the trips, and never within an hour of the last (owner 1683 l).
LONG_WALK_WEIGHT = 3.0
LONG_WALK_GAP = 3600.0
AWAY = 40.0
#: Following the pointer at a polite distance, for a while.
FOLLOW_GAP = 240.0
#: "Come here" (the menu): it stops this close to the pointer, and keeps company this long.
COME_GAP = 70.0
COME_FOR = 20.0
#: "Come here" waits for the pointer to leave the menu (this far, or COME_WAIT seconds), then follows it.
COME_MOVED = 120.0
COME_WAIT = 1.5
#: A "Go somewhere else" is at least this far (logical px), when the work area allows.
WANDER_MIN = 420.0
#: A nap asked for from the menu lasts this long (s) unless something wakes it (INBOX 1683 u).
NAP_FOR = (150.0, 300.0)
#: A leg shorter than this (logical px) is never a run.
RUN_MIN = 150.0
FOLLOW_FOR = (10.0, 18.0)
GREET_AFTER = 420.0
#: A pointer resting this many s within WAVE_NEAR of a standing figure draws one wave, once per rest, WAVE_GAP s apart
#: (INBOX 1711 b: a wave "after a pause", not only a weighted pick).
WAVE_IDLE, WAVE_NEAR, WAVE_GAP = 8.0, 420.0, 150.0
#: Under a busy pointer it waits instead of passing (px ahead / height of the path / seconds).
YIELD_NEAR = 130.0
YIELD_MAX = 4.0
YIELD_BRAKE_S = 0.12
LEAN_MAX = 0.07
POSE_RATE = 14.0
HANG_DRAG_IN = 0.6
DRAG_STEP_MAX = 3.5
#: (frequency Hz, damping, response) of the body's scale x, scale y and lean. The scales are a touch underdamped (about
#: 3% over); the lean has a slight anticipation. The step is about as quick as the lag it replaced (POSE_RATE).
POSE_DYN = ((3.4, 0.8, 0.0), (3.4, 0.8, 0.0), (3.0, 0.85, -0.12))
#: The longest slice of time one draw eases the pose by after a long sleep (an act's hold, a rest): easing by all of it snapped
#: a 0.1 gap to neutral in one picture (INBOX 1683 j). A draw within `POSE_DT_WAKE` of the last is at the moving pace and
#: eases by all of its dt (a turn's squeeze is drawn at 30 Hz); a gap under `POSE_GAP_FREE` cache steps (`bh.Q_SCALE`: 3 px
#: of the 150 px figure) is one picture's change at most, so it is closed at the real dt, however long the sleep (a capped
#: slice there made a long-sleeping act crawl in short draws). The spring (`POSE_DYN`) is stable at any dt.
POSE_DT_MAX, POSE_DT_WAKE, POSE_GAP_FREE = 1.0 / 60.0, 0.05, 0.75
VX_SMOOTH_S = 0.06
POSE_OFF = ("held", "pressed", "fly", "fall", "rise", "peek", "emerge", "leap", "hop", "card")
#: Logical px of travel per walk frame (six frames a stride).
#: Travel (logical px) per frame of the walk cycle at the shipped 12 frames: 42 px a cycle, as with 6.
STRIDE = 3.5
WALK_FRAMES = 12
TAIL_TICK_MS = 16
#: The layered tail (`behaviour.TailLayer`, atlascat-1108 C1) redraws at the display's pace only while it is looked at: a
#: pointer near, a touch in the last `TAIL_TOUCHED_FOR` seconds (15 a second; the tail's picture is one small warp, 2 ms at
#: dpi 192). At rest (a sit, a lounge, a droop, a calm or glad mood) it ticks with the streams, every `FLOW_TICK_MS`, and the
#: body warp is renewed on each of those ticks, so a body warp never lands between two tail ticks and rest costs the old
#: pace plus one small tail patch. While fast, the body warp is renewed on every second tick. Asleep the tail never ticks.
TAIL_LAYER_MS = 66
TAIL_TOUCHED_FOR = 4.0
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
#: On its feet on the monitor floor, not mid-move: a floor that drops (a taskbar hides) lets these fall to the new one.
GROUNDED = ("stand", "walk", "drift", "sit", "sleep", "act", "look", "wave", "notice", "startle")
HOLD_RANGES = {"stand": SETTLE_FOR, "sit": SIT_FOR}
HOLD_FIXED = {"wave": WAVE_FOR, "land": LAND_FOR, "hop": HOP_FOR, "notice": NOTICE_FOR, "startle": STARTLE_FOR}

#: States drawn with a frame of another name.
FRAME_OF = {"pressed": "stand", "leap": "hop", "notice": "look", "startle": "hop", "hop": "hop", "held": "held", "hang": "hang", "emerge": "stand", "warp": "stand"}

#: Throw: the pointer's last THROW_WINDOW seconds decide the velocity. Logical
#: px per second (scaled by dpi): slower than THROW_MIN is a plain drop.
THROW_WINDOW = 0.1
#: Most carried-pointer samples kept for the shake and the throw: 0.6 s of a 1000 Hz mouse plus a margin.
TRAIL_CAP = 800
THROW_MIN = 350.0
THROW_MAX = 3200.0
#: A window dragged out from under the figure (INBOX 1683 x): faster than `FLING_SPEED` (logical px/s) throws it, a
#: lying, sitting, napping or prop figure slips off at `SLIP_SPEED`; slower than those it rides. The throw keeps
#: `FLING_CARRY` of the window's velocity and is always lifted by `FLING_LIFT`; it flails for `FLING_FLAIL` s; it
#: pops away instead (`FLING_ESCAPE`, more when startled or sleepy) and wears a worried or miffed face `FLING_FACE` s.
FLING_SPEED = 2 * THROW_MIN
SLIP_SPEED = THROW_MIN / 2
FLING_CARRY = 0.6
FLING_LIFT = 300.0
FLING_FLAIL = 1.6
FLING_ESCAPE = 0.4
FLING_FACE = (2.0, 4.0)
#: How long a drop waits to stand before the dizzy sway it owes is given up.
DIZZY_WAIT = 10.0
#: A press on the lowest part of the body (share of its height from the top) carries it by the feet: upside down.
FEET_GRAB = 0.78
#: A long carry: (seconds held, stage). The legs kick, the arms cross, then it sighs; a sigh is `SIGH_FOR` s of breath.
CARRY_STAGES = ((4.0, "kick"), (6.0, "cross"), (8.0, "sigh"))
KICK_HZ, SIGH_FOR = 2.5, 1.8
UPSIDE_FRAME = "spin24"  # the tumble turned half a circle (24 of 48 steps), the picture a turned peek uses too
#: A hold that slips (the window moved under the hands, INBOX 1683 k): it may grip again, scrabble for `SCRABBLE_FOR` s
#: (the hem shakes `SCRABBLE_DRAG` at `SCRABBLE_HZ`) and pull up onto the edge's top, else it drops. The chance is
#: `GRIP_BASE` bent by how rested it is and by the mood (`GRIP_MOOD`).
GRIP_BASE = 0.55
GRIP_MOOD = {"sleepy": 0.5, "bored": 0.8, "startled": 0.9, "curious": 1.1, "happy": 1.2, "proud": 1.2}
SCRABBLE_FOR = 0.9
SLIP_REACH = 0.5  # of the figure's height: how far a slipped edge may move and still be gripped again
SCRABBLE_DRAG = 6.0
SCRABBLE_HZ = 6.0
#: Sliding down a screen side and scrabbling (INBOX 1683 x, y): after `WALL_SCRABBLE` s (the slide takes about a second
#: from the middle of the screen, so a beat), a window top within `WALL_REACH` figure heights of the hands is
#: something to pull up onto (the nearest), else it slides on and lands.
WALL_SCRABBLE = 0.45
WALL_REACH = 1.3
#: States a dragged window does not throw the figure out of: it is already off the window, held, or going somewhere.
FLING_SAFE = ("held", "pressed", "fly", "fall", "warp", "hang", "rise", "peek", "emerge", "leap")
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
#: INBOX 1683 ("rotating when thrown ... still horrible"): the figure is drawn at its true angle every tick
#: (`Output.angle`), so the turn rate is what a person sees. At 60 Hz 4.2 rad/s is 4 degrees a tick (the old 11
#: was 10.5, a spin that strobed); a soft toss turns about 1 degree a tick. The rate comes from the throw: its speed,
#: and the lever of where the figure was held (`SPIN_LEVER`, a throw off-centre turns it the way the hand pulls).
#: A bounce or a bonk changes the rate by easing to it (`SPIN_EASE` per second), never in one tick.
SPIN_OMEGA = (0.9, 4.2)
SPIN_SWIRL = 1.2
SPIN_DRAG = 0.5
SPIN_CONTACT = 0.5
SPIN_EASE = 5.0
SPIN_LEVER = 0.9
#: The squash a thrown floater makes as it comes to rest: this much of its height, over this many seconds.
SQUASH = 0.1
SQUASH_FOR = 0.35
#: A4: a sit or a sleep shifting its weight (seconds, and the lean it takes).
SHIFT_FOR, SHIFT_LEAN = 2.4, 0.05
#: Once the flight is this slow (px per second at 96 dpi), or it is on the floor, it rights itself with an
#: eased turn (a critically damped spring to the nearest upright, `RIGHT_W` rad/s, ramped in over `RIGHT_RAMP`
#: s so the turn rate stays continuous) and is laid down only when upright.
RIGHT_SPEED = 150.0
RIGHT_W = 4.2
RIGHT_RAMP = 0.4
RIGHT_SPENT = 0.5
#: A throw reaching the ceiling takes hold only within this much of upright (rad, about 26 degrees, under the 30 a snap is counted at): hanging would snap it.
CEIL_TILT = 0.45
SPIN_STEPS = 48
SPIN_FRAMES_ENGINE = tuple(f"spin{i}" for i in range(SPIN_STEPS))
#: A floater: hover height range above the floor, speed, turn rate, air drag,
#: and the pull back to its hover height (per second squared per pixel).
#: Its rest line: a hand's breadth above the work area's bottom, so the feet are on the
#: taskbar (INBOX 1670: "it still sits like 20px above the bottom bar"). It never sinks below. Was (24, 80), a figure's height up.
HOVER = (0.0, 0.0)
#: How far below the work area's top a released figure's head may be and still take hold.
HANG_REACH = 0.3
#: Let go with its feet this near a window's top (shares of its height: above the edge, and below it with the legs in
#: front of the title bar) and it settles onto that top (INBOX 1696 b: "I tried to drag the desktop companion onto the
#: top of my file explorer window but it just fell"). A release slower than `PERCH_THROW` times THROW_MIN is a placing.
DROP_REACH = (0.6, 0.35)
PERCH_THROW = 2.0
#: The ceiling takes hold of a throw only when it was thrown hard and mostly upward (INBOX 1670, 15:45Z: "nearly every
#: time I throw it no matter how hard, it goes to the top to hang"): this much upward launch speed (logical px per
#: second, over half of `THROW_MAX`) and at least this share of the throw's speed pointing up. It is read at the
#: launch, not at the top, because a floater's drag takes most of a hard throw's speed before it gets there. Any
#: other throw bounces off the top like a side wall.
CEIL_CATCH = 2000.0
CEIL_UPWARD = 0.8
#: INBOX 1719 (a): a throw harder than this (upward launch speed, logical px per second, above `CEIL_CATCH`, below
#: `THROW_MAX`) and mostly upward does not hang from the top: it leaves through it, stays out of view for a time that
#: grows with the speed (`AWAY_FOR`, seconds, from the line to `THROW_MAX`; capped), then falls back in from the top
#: within `AWAY_DRIFT` figure widths of where it left, turning over.
CEIL_LEAVE = 2500.0
AWAY_FOR = (1.0, 8.0)
AWAY_DRIFT = 0.6
AWAY_FALL = 450.0
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
HANG_FOR = (90.0, 300.0)  # INBOX 1696 b: minutes, as `bh.HANG_BY_MOOD`; the long end is the longest mood's
#: A hang swings from its grip like a pendulum (the lower body lags by this many px, `Pose.drag`), a
#: slow one, and glances about now and then (INBOX 1670, 13:28Z: "it basically doesn't move while it is
#: hanging"). The window itself holds still: only the picture swings.
HANG_SWING = 9.0
#: A hanger that is patted or hears a screen event swings: an extra hem swing this big, dying away over `HANG_KICK_FOR` s.
HANG_KICK = 12.0
#: A vanish needs somewhere else to go: a leg shorter than this many figure widths is walked (INBOX 1721 c). 0.3 is about 50 px, where a move
#: reads as one; larger values also shifted the seeded hour of test_overlay_life_1670.
WARP_MIN = 0.3
HANG_KICK_FOR = 2.4
#: A hang ends by its own choice (INBOX 1683 h), never a plain fall on a timer: it pulls itself up onto the
#: window it holds, swings (a bigger pendulum for `SWING_FOR` s) and drops to a window top within `SWING_REACH`
#: logical px, or lets go after a startled beat of `REACT_FOR` s.
SWING_FOR = 1.5
SWING_BOOST = 1.7
SWING_REACH = 520.0
REACT_FOR = 0.6
HANG_ENDS = {"pull": 5.0, "swing": 4.0, "react": 2.0}
HANG_PERIOD = 5.6
HANG_GLANCE = (11.0, 26.0)
#: What a hang takes hold of (INBOX 1660: "it thinks its hanging but its just ... hanging in
#: mid air"): the top of the work area, or the bottom edge of a window's title bar
#: (`TITLE_BAR` logical px under its top). The hands are `hang_top` of the frame's height
#: below the frame's top (measured from the hang frame at load), so the frame is lifted by
#: that much; the hands need `HANG_HANDS` of the figure's width either side of its centre
#: to be over the window's edge.
TITLE_BAR = 32.0
#: Where a trip goes (INBOX 1683 w, the owner on Windows: "it always chooses the taskbar as a perch, it never
#: chooses to hang"): the floor, a window's top, or a hang. A kind is not chosen a third time running, and a
#: hang trip has its own weight beside the window's (4) and the floor's few (clock 2, nap 0.3 to 2, follow 2).
HANG_TRIP_WEIGHT = 4.0
DEST_RUN = 2
#: A walker hangs from a spot this far (logical px) from where it stands by leaping; farther it walks under it first.
HANG_LEAP = 300.0
HANG_HANDS = 0.3
RISE_FOR = 0.9
#: Peek: the figure sinks behind an edge. Hidden share of the figure (0 shown, 1 gone).
PEEK_HEAD = 0.65
PEEK_SIDE = 0.55
#: A peek from the top edge hangs by the hands and climbs up behind the edge; this share of the figure (its legs) is
#: the last to go (INBOX 1683 y: "hands over the edge").
PEEK_TOP_SHOWN = 0.45
#: Where a peek is taken, as weights: behind a bar that is shown (tucked away behind the taskbar or a sidebar), or out
#: of an edge with no bar. The mood bends them (`_peek_edges`).
PEEK_BEHIND = 3.0
PEEK_OPEN = {"bottom": 2.0, "left": 1.5, "right": 1.5, "top": 1.0}
#: Behind the side of a smaller window (INBOX 1683 k): its weight beside the edges, how old the window scan may be for
#: it to be trusted (seconds), and the plan, which holds longer than a peek so the window is seen to matter.
PEEK_TUCK = 2.5
TUCK_FRESH = 3.0
TUCK_PLAN = ((0.0, 0.0), (1.0, 1.0), (6.0, 1.0), (6.5, 2.0), (13.0, 2.0), (13.5, 1.0), (16.0, 1.0), (16.8, 0.0))
#: How far (logical px) a window may stop short of the figure's feet and still hide them.
TUCK_REACH = 3.0
#: (seconds, depth): 0 out, 1 the head shows, 2 gone. Sink, look about, duck,
#: wait, come up, look, out. Depth 1 is `PEEK_HEAD` (or `PEEK_SIDE`) hidden, 2 is all.
PEEK_PLAN = ((0.0, 0.0), (0.8, 1.0), (3.0, 1.0), (3.4, 2.0), (5.0, 2.0), (5.5, 1.0), (7.0, 1.0), (7.8, 0.0))
EMERGE_FOR = 0.4
#: The top peek (INBOX 1683 x, y: "upside-down, peering down from behind the top edge"): (seconds, step) with 0 hanging in
#: view, 1 pulled up out of sight, 2 turned over and lowered to peer down (`PEEK_TOP_PEER` of the figure shows, its head
#: first). The turn is made while it is out of sight, so the pose changes without a step.
PEEK_TOP_PLAN = ((0.0, 0.0), (0.8, 1.0), (2.2, 2.0), (6.2, 2.0), (7.4, 1.0), (8.2, 0.0))
PEEK_TOP_PEER = 0.4
#: Big acts (hang, peek) are at least this far apart (seconds): calm, minutes.
BIG_EVERY = (700.0, 1300.0)
#: The first one comes sooner, inside the minutes before it sits down for good.
BIG_FIRST = (300.0, 700.0)
#: While the person is busy (typing, presenting) it asks again this often.
QUIET_RECHECK = 5.0
REST_FOR = (8.0, 20.0)
#: The ambient choice, one table: act -> (weight, big). `sleep` needs SLEEP_AFTER idle.
#: A presence spell (INBOX 1692): a few minutes of one quiet thing in place, by the hour and the mood (`presence.py`).
SPELL_WEIGHT = 170
#: It moves to another spot between spells when the spot is further than this many logical px.
SPELL_MOVE = 160.0
#: Typing: a spell carries on quietly in place, in acts of this many seconds, while the person works.
SPELL_QUIET = (45.0, 100.0)
#: A prop reaches this share of the figure's height past its drawn box (a rod, a plant, a sky): the caret is kept this
#: much further off while it is out.
SPELL_ROOM = 0.3
#: A home the person chose from the menu ("Go somewhere else") is kept this long: a spell settles on its side of the
#: screen, not back across it (the menu's own test caught a doodle carrying it home again 46 s later).
HOME_KEEP = 600.0
#: Trips that end on the floor in `_arrive_plain` with nothing to climb or hold: one met by a caret may finish in a warp
#: straight to its goal, and one cut short by a runner restart may be taken up again (`take`) when it was the menu's.
PLAIN_THENS = ("settle", "home", "rest", "spell", "follow", "clock", "greet", "longwalk", "nap", "evade")
RESUMED_THENS = ("settle", "home")
#: With presence on (the default) it stands this long between two things, not `SETTLE_FOR` (200 to 520 s of stillness,
#: which was 50 of every 60 minutes): it is there and doing something, and the stillness is the rest.
SPELL_SETTLE = (6.0, 22.0)
ACTS = {
    "idle": (62, False), "stroll": (3, False), "trip": (16, False), "sleep": (2, False),
    "hang": (4, True), "peek": (5, True), "climb": (90, False),
    "spell": (SPELL_WEIGHT, False),
}
SLEEP_AFTER = 60.0

#: Window tops (roam): the first climb comes after `CLIMB_FIRST`, then one every
#: `CLIMB_EVERY` seconds at most; it stays on one window `PERCH_FOR`; a top must be
#: `PERCH_MIN_RISE` logical px above the floor to be worth the leap; a window top
#: that moves more than `PERCH_MOVED` physical px has moved.
CLIMB_FIRST = 40.0
#: The `climb` act was missing from `ACTS` (so `_can_climb` was never called and a window came only with a rare
#: trip, one in thirty minutes or so): the owner on Windows had never seen it perch (INBOX 1683 g).
CLIMB_EVERY = (90.0, 240.0)
#: A window top (or a title bar) that has just appeared is gone to within this many seconds, not after the
#: ordinary wait; one such eager trip per `EAGER_EVERY` seconds so it stays a moment, not a habit (INBOX 1692 n).
CLIMB_SOON = 3.0
EAGER_EVERY = 45.0
PERCH_FOR = (45.0, 120.0)  # long enough to be seen and to count as a settled spell (was 20 to 50)
PERCH_MIN_RISE = 48.0
#: The share of the figure's width its feet need of a window top (INBOX 1697): a narrower top is no place to stand,
#: a wider one is, however much of the figure's box hangs past its side. `PERCH_MARGIN` logical px is the slack.
PERCH_FEET = 0.4
PERCH_MARGIN = 8.0


def perch_room(width: float, scale: float) -> int:
    """The narrowest stretch of a window top a figure `width` px wide may stand on (the runner's scan and the
    engine's climb share it, so a drop and a climb agree on what is a perch)."""
    return int(width * PERCH_FEET + PERCH_MARGIN * scale)


def stand_x(p: "Perch", x: float, width: float) -> float:
    """`x` moved so the figure stands on `p`: all of its box over the top when that is wide enough, else its middle
    kept over the top by the feet's half span (a small window is stood on with the body hanging past its sides)."""
    if p.right - p.left >= width:
        return min(max(x, p.left), p.right - width)
    half = min(width * PERCH_FEET / 2, (p.right - p.left) / 2)
    return min(max(x + width / 2, p.left + half), p.right - half) - width / 2
PERCH_MOVED = 3.0
#: A ground leg crossed as a chain of hops (INBOX 1683 u, the owner: travel that is seen, a varied mix): one arc every
#: `HOP_SPAN` figure widths of ground, `HOP_RISE` of the figure's height at the top, eased to nothing over the last
#: span so the leg lands on its goal and the start rises with the pace.
HOP_SPAN = 1.1
HOP_RISE = 0.16
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
#: figure should be and never stutters. The tail's settle and a pose easing ask the same 16 ms (INBOX 1683: they were
#: 50, drawn at about 16 a second); a hanging swing asks 33 (two lines of the grid), an act the time its pose next steps.
TICK_WALK_MS = 16
TICK_FALL_MS = 16
HANG_TICK_MS = 33
#: A visit to a window is not a rest spot: the first leg to a window top stays under a minute.
#: Sitting and sleeping look at the pointer this often (a wake each).
POLL_QUIET_MS = 2000
MIN_WAKE_MS = 30
POSE_LOOK_STEP = 1.0 / 60.0

Rect = tuple[int, int, int, int]


class Perch(NamedTuple):
    """The top edge of another app's window: a surface to stand on (physical px). `kind` "top" is a window's
    top (to stand on, or its title bar to hang from); "bar" a maximised window's title bar and "bottom" a
    floating window's bottom edge (key negated), which are only hung from (INBOX 1683 w)."""

    key: int
    left: int
    top: int
    right: int
    kind: str = "top"


class Cover(NamedTuple):
    """A window the figure may tuck behind the side of (physical px): its frame, and the frames of the windows
    above it in the stacking order that overlap it (INBOX 1683 k)."""

    key: int
    rect: Rect
    above: tuple[Rect, ...] = ()


class TuckSpot(NamedTuple):
    """Where to stand to tuck behind `cover`: the figure's left edge `x` and top `y` at rest, and the `peek_edge`
    it looks out of ("right" when the window is on its right)."""

    cover: Cover
    edge: str
    x: float
    y: float


class Bar(NamedTuple):
    """A strip along one edge of a monitor (INBOX 1683 y): a taskbar or a docked appbar or sidebar. `edge` is the
    monitor's side it lies along, `rect` its screen pixels, `shown` whether it is there to be hidden behind (not
    auto-hidden, not hidden by a tool, not under a full-screen window)."""

    edge: str
    rect: Rect
    shown: bool = True


class Monitor(NamedTuple):
    """A play area (left, top, right, bottom) in physical pixels and its dpi. The area is the floor, ceiling and
    sides: the work area, with the strip of every bar that is not shown given back. `screen` is the whole monitor
    (None: the area is all there is) and `bars` what lies along its edges."""

    area: Rect
    dpi: int = 96
    screen: Rect | None = None
    bars: tuple[Bar, ...] = ()

    def full(self) -> Rect:
        return self.screen or self.area

    def bar(self, edge: str) -> Bar | None:
        """The shown bar along an edge, or None: the edge is the screen's own."""
        return next((b for b in self.bars if b.edge == edge and b.shown), None)


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
    #: The true angle of a thrown figure's tumble, radians (clockwise on screen positive), or None. `frame` is
    #: then the nearest of the `SPIN_STEPS` pictures (its box, its name); the runner draws `angle` itself.
    angle: float | None = None
    #: The wisps' and streams' own motion over the frame (`behaviour.Flow.view`, small integers), or None.
    flow: tuple[int, ...] | None = None
    #: A prop the figure uses, drawn with the frame, `(name, phase, size)` (`props.view`), or None.
    prop: tuple[str, int, int] | None = None
    #: The face it wears over the frame, `(kind, step)` (`faces.EXPRESSIONS`, step 1 to 3), or None.
    face: tuple[str, int] | None = None
    #: The tail layer's view (`behaviour.TailLayer.view`: control points' moves, small integers), or None.
    tail: tuple[int, ...] | None = None


def _adjoins(a: Rect, b: Rect, side: str) -> bool:
    """Whether rect `b` touches rect `a` along `a`'s `side` (within a pixel)."""
    al, at, ar, ab = a
    bl, bt, br, bb = b
    across_y, across_x = bt < ab and bb > at, bl < ar and br > al
    return {
        "left": abs(br - al) <= 1 and across_y, "right": abs(bl - ar) <= 1 and across_y,
        "top": abs(bb - at) <= 1 and across_x, "bottom": abs(bt - ab) <= 1 and across_x,
    }[side]


def _same_screens(new: list[Monitor], old: list[Monitor]) -> bool:
    """The same screens at the same dpi (only a bar may have come or gone)."""
    return len(new) == len(old) and all(a.screen is not None and (a.screen, a.dpi) == (b.screen, b.dpi) for a, b in zip(new, old))


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
        wave_frames: int = 0,
        rng: random.Random | None = None,
        now: float = 0.0,
    ) -> None:
        self.size = size
        self.idle_frames = max(0, int(idle_frames))
        self.walk_frames = max(1, int(walk_frames))
        self.wave_frames = max(0, int(wave_frames))
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
            u = 1.0 - max(0.0, self.state_until - now) / LAND_FOR
            sy = 1.0 - 0.12 * math.sin(min(1.0, u) * math.pi)
            sx = 1.0 + 0.06 * math.sin(min(1.0, u) * math.pi)
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
            self._start_act(self.mind.pick(self.rng, now, self.gait, self.hour, "perch" if self.perch else ""), now)

    # --- asked from the menu (INBOX 1670, row C) ----------------------------------------------

    #: What the menu can ask for; `command` says whether it was done.
    COMMANDS = ("wave", "come", "wander", "nap", "wake", "perch", "stay", "roam")
    #: The states a request may break into; anything else (carried, thrown, falling, leaping) is left alone.
    _FREE = ("stand", "sit", "sleep", "walk", "drift", "act", "crouch", "wave", "notice", "startle", "land", "hop", "card")

    def command(self, name: str, now: float) -> bool:
        """A choice from the companion's menu, on the engine's own thread. True when it took
        effect; False when it cannot be done now (carried, no window to sit on, motion off), and it looks sad."""
        done = self._command(name, now)
        if not done:
            self.ex.fire("refused", now)
        return done

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
        return self.state in ("sit", "sleep") or (self.state == "act" and self.act in (*extras.props.PROP_ACTS, *extras.props.SPELL_ACTS, "lie_down"))

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
        if now >= self.state_until:
            if self.swing_to is not None:
                self._release_swing(now)
            elif self.releasing:
                self.releasing = False
                self._let_go()
            else:
                self._end_hang(now)

    def _end_hang(self, now: float) -> None:
        """The hang is over, by its own choice: pull up onto the edge it holds, swing and drop to a window top,
        or let go after a startled beat. Never a plain fall on a timer (INBOX 1683 h)."""
        held = self._hold_of(self.hang_on) if self.hang_on is not None else None
        w, h = self.size
        table: dict[str, float] = {"react": HANG_ENDS["react"]}
        if held is not None and held.kind == "top" and held.top - h >= self.current_monitor().area[1]:
            table["pull"] = HANG_ENDS["pull"]
        drop = self._drop_target()
        if drop is not None:
            table["swing"] = HANG_ENDS["swing"]
        roll = self.rng.random() * sum(table.values())
        pick = "react"
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
        if verdict == "slide":
            self.wall, self.vx, self.vy, self.outcome = side, 0.0, self.vy * 0.4, "slide"
            self.wob_kind, self.wob_t0 = "scrabble", now
            self._spin_contact(float(-side))
            return
        self.vx = -side * abs(self.vx) * BOUNCE_DAMP
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
                self._feet_begin()  # a wall bounce's unpaid kick is dropped there: the floor turns it upright, not further
        self.vy = 0.0
        self.vx *= math.exp(-(ld.STUMBLE_K if self.lie_goal is None else ld.SKID_K) * dt)
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
            self.y, self.vy, self.vx = floor, 0.0, 0.0
            self.settled_now = True
            self._enter("land", now)

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
        else:
            self.omega *= math.exp(-SPIN_DRAG * dt)
            self._pay_kick(dt)
            self._right_step(dt, speed)
            self.angle += self.omega * dt
        # on the floor, upright and still it is the held pose at once: the tumble's upright frame stands 14 px higher than the held
        # one, so waiting out the dwell drew the feet off the line and then stepped them down (INBOX 1683 v)
        if (self.slow_for >= FLY_REST_DWELL or self.grounded or self._floored()) and self._righted():
            self.laid = True  # laid down for good until the next throw: the held pose never swaps back to the tumble

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
        if self.lie_goal is not None:
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
        self.outcome = self.lie_goal = self.wob_kind = None
        self.wall, self.wob, self.air_t0 = 0, 0.0, self.now
        self.y += self._dy(self._frame(self.now)) - self._dy("spin0")  # drawn where it was
        self.angle, self.omega, self.kick = 0.0, self._launch_spin(vx, vy, swirl), 0.0
        if abs(vx) > 1:
            self.facing = 1 if vx > 0 else -1
        self._enter("fly", self.now)

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

    # --- the answer ------------------------------------------------------------------------------------

    def _fixed_frame(self, s: str) -> str:
        if s == "held":
            return self._held_frame()
        if s == "pressed" and self.pre_press == "hang":
            return "hang"  # a press on a hanger keeps the hang pose until it is dragged (INBOX 1690 c)
        return FRAME_OF[s]

    def _frame(self, now: float) -> str:
        name = self._state_frame(now)
        #: A wave swings its arm (INBOX 1696: one held frame read as a salute), wherever it is drawn: the wave
        #: state, an act that waves, a dance.
        if name == "wave" and self.wave_frames:
            return f"wave{int(now * WAVE_FPS + 1e-6) % self.wave_frames}"
        return name

    def _state_frame(self, now: float) -> str:
        s = self.state
        if s in ("card", "walk", "drift"):
            return self._step_frame(now, s)
        if s == "act":
            return bh.activity_frame(bh.ACTIVITIES[self.act or "breathe"], (now - self.act_started) / max(0.01, self.act_len))
        if s == "crouch":
            return "land"
        if s == "warp" and self.warp is not None and self.warp["kind"] == "edge":
            return self._edge_warp_frame(now)
        if s in FRAME_OF:
            return self._fixed_frame(s)
        if s == "fly":
            return self._flying_frame(now)
        if s in ("rise", "peek"):
            return self._edge_frame(now)
        if s == "stand":
            return self._stand_frame(now)
        if s == "sit" and self.flash:
            return self._sit_frame(now)
        return s  # sit, sleep, wave, fall, land

    def _edge_warp_frame(self, now: float) -> str:
        """Off one side and on at the other: a floater flows on its idle cycle, a walker steps."""
        if self.gait == "float":
            return self._stream_frame(now)
        return f"walk{int((now - self.warp['t0']) / (0.75 / self.walk_frames)) % self.walk_frames}"

    def _flying_frame(self, now: float) -> str:
        """A bonk shows the startled hop only when the figure is not turning: a picture swap in the middle of a
        spin was the snap (INBOX 1683); the contact is felt in the turn rate instead."""
        return "hop" if now < self.bonk_until and self.laid else self._fly_frame()

    def _step_frame(self, now: float, s: str) -> str:
        if s == "card":
            return f"card{int(now / CARD_SWAP) % 2}"
        if self.card is not None:
            return f"card{int((now - self.walk_started) / CARD_WALK_SWAP) % 2}"
        if self.gait == "float":
            return self._stream_frame(now)
        if self.hopping and self.hop_lift > 0.35 * HOP_RISE * self.size[1]:
            return "hop"  # tucked while it is in the air, the stride on the ground
        return f"walk{int(self.travel / (STRIDE * WALK_FRAMES / self.walk_frames * self._scale())) % self.walk_frames}"

    def _stream_frame(self, now: float) -> str:
        """A floater on the move: its idle cycle (tail and streams flowing, eyes open), never the walk cycle, whose
        shipped Atlas frames shut the eyes on every other step and bob the body (INBOX 1692: "it still looks like it
        hobbles along and its eyes blick ferociously ... it floats like a wind spirit")."""
        if self.idle_frames <= 0:
            return "stand"
        return f"idle{int(now * IDLE_FPS + 1e-6) % self.idle_frames}"

    def _edge_frame(self, now: float) -> str:
        if self.state == "rise":
            frame = "hop" if self.gait == "walk" else self._stream_frame(now)
            if self.then == "peek_top":
                return "hang"
            if self.then == "hang" and self._rise_drawn(now) + self._box(frame)[1] < self.current_monitor().area[1]:
                return "hang"  # its head would pass the top of the screen: hands up, in the pose that fits
            return frame
        if self.peek_edge == "top":
            return "spin24" if self.peek_flip else "hang"
        return "stand" if self.sink < self.sink_max * 0.5 or now - self.peek_started < 0.8 else "look"

    def _blink_step(self, now: float) -> tuple[int | None, float]:
        """The phase of the blink under way: `(step, next_change)`, step 1 or 2 for a light or a half lid drawn over the open
        picture, 0 for the shut one, None when no blink shows (or a motion cannot draw a lid: reduced, or no face layer)."""
        if not self.flash or self.flash[0] != "blink":
            return None, math.inf
        span = self.blink_for
        u = (now - (self.flash[1] - span)) / span
        k = max(i for i, (at, _s) in enumerate(BLINK_PHASES) if u >= at - 1e-9) if u > 0 else 0
        nxt = BLINK_PHASES[k + 1][0] if k + 1 < len(BLINK_PHASES) else 1.0
        return BLINK_PHASES[k][1], self.flash[1] - span + nxt * span

    def _blink_face(self, now: float, frame: str, face: tuple[str, int] | None) -> tuple[str, int] | None:
        """`face` with the blink's lids over it: the light and half lids are drawn over the open picture, over an expression too
        (`kind|step`, `faces.draw`); the shut step of a plain blink is the shipped picture, so no face."""
        lid = self._blink_step(now)[0] if frame in ("sit", "stand") or frame.startswith("idle") else None
        if lid is None or not (lid or face):
            return face
        return (f"{face[0]}|{lid or 3}", face[1]) if face else ("blink", lid)

    def _sit_frame(self, now: float) -> str:
        """A sit: its own picture, or its lids over the sat figure's eyes (`SpriteSet` derives the shut frame)."""
        step = self._blink_step(now)[0]
        return "sit" if not self.flash or step or (step == 0 and self.ex.view(now)[1]) else "sitblink"

    def _flash_due(self, now: float) -> float:
        """When the picture next changes for a blink or a look under way."""
        return min(self._blink_step(now)[1], self.flash[1]) if self.flash else math.inf

    def _stand_frame(self, now: float) -> str:
        if self.flash:
            step = self._blink_step(now)[0]
            if step or (step == 0 and self.flash[0] == "blink" and self.ex.view(now)[1]):  # a lid over the open picture (`_output`)
                return f"idle{self._idle_index(now)}" if self._idling() else "stand"  # (shut too, under an expression: it keeps its mouth)
            return self.flash[0]
        return f"idle{self._idle_index(now)}" if self._idling() else "stand"

    def _idling(self) -> bool:
        """Standing with life in its parts: not reduced, frames present. Typing keeps it in
        place, not lifeless (INBOX 1670: "it is also not animated")."""
        return self.state == "stand" and not self.reduced and self.idle_frames > 0

    def _idle_fps(self) -> float:
        """Frames a second: a shipped set of fewer frames plays slower, so the cycle stays 4 s."""
        return IDLE_FPS * max(1, self.idle_frames) / IDLE_FRAMES

    def _idle_cycle(self, now: float) -> tuple[float, float]:
        """(start, length) of the idle cycle `now` is in. Each cycle runs a little faster or slower than
        the last, from its own seeded stream, so the breath and sway never line up twice (research A7)."""
        t = max(0.0, now - self.idle_start)
        nominal = max(1, self.idle_frames) / self._idle_fps()
        while self._edges[-1] <= t:
            self._edges.append(self._edges[-1] + nominal / (1.0 + self.idle_rng.uniform(-IDLE_SLOWEST, IDLE_SPREAD)))
        k = next(i for i in range(len(self._edges) - 1, 0, -1) if self._edges[i - 1] <= t)
        return self.idle_start + self._edges[k - 1], self._edges[k] - self._edges[k - 1]

    def _idle_index(self, now: float) -> int:
        start, length = self._idle_cycle(now)
        return min(self.idle_frames - 1, int((now - start) / length * self.idle_frames + 1e-6)) % self.idle_frames

    def _idle_next(self, now: float) -> float:
        """When the idle picture next changes."""
        start, length = self._idle_cycle(now)
        step = length / self.idle_frames
        return start + (math.floor((now - start) / step + 1e-6) + 1) * step

    def _lower_state(self, now: float, face: tuple[str, int] | None) -> str:
        """What the lower body is doing, for `bh.FLOW_LOWER` (atlascat-1108 C4, C5): the base state (`_lower_base`) read
        with the act, the speed and how long it has lasted (`_lower_spell`); "" for the frame's own row."""
        return self._lower_spell(now, self._lower_base(now, face))

    def _lower_spell(self, now: float, base: str) -> str:
        """A state of the lower body's own beyond the base ones (atlascat-1108 C5): a twirl's spiral (and its 2.5 s unwinding),
        a glad act's hem kick, a seated act's coil, a fast glide's billow, and at rest a tired heaviness, an excited flutter,
        a long sit spread flat (a pool), a calm stand's slow ripple."""
        s, act = self.state, self.act if self.state == "act" else ""
        if act in bh.TWIRL_ACTS:
            self._twirl_at = now
        if now - self._twirl_at < bh.SPIRAL_FOR:
            return "spiral"
        if act in bh.HEM_ACTS:
            return "hem_kick"
        if act in bh.COIL_ACTS:
            return "coil"
        if base == "glide":
            fast = self.mode == "dash" or abs(self.vx_px) >= bh.BILLOW_SPEED * WALK_SPEED * self._scale()
            return "billow" if fast else base
        return self._lower_rest(now, base) if s in ("stand", "sit") else base

    def _lower_rest(self, now: float, base: str) -> str:
        """The resting spells: sleepy is heavy, a glad reaction flutters, a sit of `POOL_AFTER` s is a pool, and a calm stand
        ripples for `RIPPLE_FOR` s of every `RIPPLE_EVERY` once `RIPPLE_AT` s in. A sad or startled figure keeps its own."""
        if base in ("sad", "startle"):
            return base
        if self._mood(now) == "sleepy":
            return "heavy"
        if self.mind.event == "happy" and 0.0 <= now - self.mind.event_at < bh.FLUTTER_FOR:
            return "flutter"
        held = now - self.state_at
        if self.state == "sit":
            return "pool" if held >= bh.POOL_AFTER else base
        return "ripple_calm" if base == "" and bh.RIPPLE_AT <= held % bh.RIPPLE_EVERY < bh.RIPPLE_AT + bh.RIPPLE_FOR else base

    def _lower_base(self, now: float, face: tuple[str, int] | None) -> str:
        """What the lower body is doing, for `bh.FLOW_LOWER` (atlascat-1108 C4): lying in a nap, thinking, sad, startled,
        lounging in a long sit, gliding on the move; "" for the frame's own row."""
        s = self.state
        if s != self._seen_state:
            self._seen_state, self.state_at = s, now  # read here, not in `_enter`: a sit counts from its first picture
        if s == "sleep":
            return "lie" if self.nap_until else ""
        over = self.ex.over[0] if self.ex.over is not None else None  # the reaction's face, the signal the startle reads
        if s == "startle" or over in ("surprised", "worried"):
            return "startle"
        if over == "sad" or (face is not None and face[0] == "sad"):
            return "sad"
        if s == "act" and self.act in bh.THINK_ACTS:
            return "think"
        if s == "sit":
            return "lounge" if now - self.state_at >= bh.LOUNGE_AFTER else ""
        if s in ("walk", "drift"):
            return "glide"
        return ""

    def _tail_view(self, now: float, frame: str) -> tuple[int, ...] | None:
        """The layered tail's view over a stand-family or sit frame, or None (no layer: another frame, reduced motion, a
        walker, a figure the person has hold of)."""
        if self.gait != "float" or self.reduced or self.state not in ("stand", "sit") or frame.rstrip("0123456789") not in bh.TAIL_FRAMES:
            return None
        state, mood = self._tail_cue(now)
        self.tail_layer.choose(state, mood, now)
        return self.tail_layer.view(now)

    def _tail_cue(self, now: float) -> tuple[str, str]:
        """What the tail picks its pose by (atlascat-1108 C2, C3): the state, with a window's top as `perch` (balance) and a
        long sit as `lounge`; the mood, with a sad reaction as `sad` (tuck) and a glad one looked at as `playful` (loop8)."""
        state, mood = self.state, self._mood(now)
        if self.perch is not None and state == "stand":
            state = "perch"
        elif state == "sit" and now - self.state_at >= bh.LOUNGE_AFTER:
            state = "lounge"
        over = self.ex.over[0] if self.ex.over is not None else None
        if over == "sad" and mood != "startled":
            mood = "sad"
        elif mood in ("happy", "proud") and self._tail_fast(now):
            mood = "playful"
        return state, mood

    def _mood(self, now: float) -> str:
        """`Mind.mood`, kept for half a second (the needs move over minutes; an event shows at once): not worked out per tick."""
        at, ev, kept = self._mood_kept
        if 0.0 <= now - at < 0.5 and ev == self.mind.event_at:
            return kept
        kept = self.mind.mood(now, self.hour)
        self._mood_kept = (now, self.mind.event_at, kept)
        return kept

    def _tail_fast(self, now: float) -> bool:
        """The tail is being looked at: the pointer near, a touch just now. (A glad mood's wag at rest is drawn at the rest
        pace too: glad is the usual mood, and it would hold the whole hour at the active pace.)"""
        if now - self.last_click < TAIL_TOUCHED_FOR:
            return True
        p = self.pointer
        return p is not None and math.hypot(p[0] - self.x - self.size[0] / 2, p[1] - self.y - self.size[1] / 2) <= NOTICE_NEAR * self._scale()

    def _tail_ms(self, now: float) -> int:
        return TAIL_LAYER_MS if self._tail_fast(now) else FLOW_TICK_MS

    def _flow_view(self, now: float, frame: str = "", lower: str = "") -> tuple[int, ...] | None:
        """What the wisps and streams are doing at `now`; under reduced motion a slow drift only. While the
        person has hold of it or it is thrown or falling the last view is kept (review of 1683: a new flow is a
        new picture, and a warp a frame on the drag is the lag the owner complained of); a tumble frame takes
        none (its picture is the same with any)."""
        if frame.startswith("spin"):
            return None
        if self.state in FLOW_FROZEN:
            return self._flow_held
        if self._flow_held is not None and self._tail_ticks() and self._tail_fast(now) and 0.0 <= now - self._flow_at < 1.5 * TAIL_LAYER_MS / 1000.0:
            return self._flow_held  # while fast, every other tail tick reuses the body picture: only the tail is redrawn between two warps
        self._flow_at = now
        self._flow_held = self.flow.view(now, calm=self.reduced, frame=frame or "stand", lower=lower, side=-float(self.facing), breath=self._breath_phase(frame, now))
        return self._flow_held

    def _breath_phase(self, frame: str, now: float) -> float | None:
        """The body's breath phase for the lower body (`wisps.phase`); an act in place breathes at a sit's pace; none under reduced motion."""
        if self.reduced:
            return None
        life = self._rest_life()
        period = life[0] if life else REST_LIFE["sit"][0] * self.rest_breath if self.state == "act" else None
        return wisps.phase(self.state, frame, now, period, self.idle_frames, DRIFT_BREATH_S)

    def _tail_ticks(self) -> bool:
        """The layered tail sets the pace of the redraws now (a stand or a sit of a floater, not reduced)."""
        return self.gait == "float" and not self.reduced and self.tail_layer_on and self.state in ("stand", "sit")

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
            self._tail_view(now, frame) if fx is None and self.tail_layer_on else None,
        )
