"""The overlay engine's numbers, shapes and two small geometry helpers (audit-1028 K24, moved whole out of engine.py).

Every timing, speed, distance and weight the state machine in `engine.py` reads, the named tuples it exchanges (`Perch`, `Cover`, `TuckSpot`, `Bar`,
`Monitor`, `Output`) and `perch_room`, `stand_x`, `_adjoins`, `_same_screens`. `IDLE_SIT` and `IDLE_SLEEP` stay in `engine.py`: the sims and tests set them
there, so only code that lives there may read them."""

from __future__ import annotations

from typing import Any, NamedTuple


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
#: logical px, or (a hang from a window's edge only) lets go after a startled beat of `REACT_FOR` s. A hang from the screen top has no such
#: ending: after its full rest, with neither of the first two, it makes a calm drop to its feet (owner 2026-11-10).
SWING_FOR = 1.5
SWING_BOOST = 1.7
SWING_REACH = 520.0
REACT_FOR = 0.6
HANG_ENDS = {"pull": 5.0, "swing": 4.0, "react": 2.0}
HANG_PERIOD = 5.6
HANG_GLANCE = (11.0, 26.0)
#: W31 E2: how long a long hang holds on with both hands between the times it lets one go (`bh.ACTIVITIES["hang_one_hand"]`).
HANG_ONE_EVERY = (20.0, 55.0)
#: The pictures placed as the sit is: its seat on the rest line, whatever hangs below it (a dangle's hem, a kick's) is drawn under it.
SIT_REGISTERED = ("dangle", "kick0", "kick1", "meditate")
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
