"""The companion's mind and body language (INBOX 1670, row B): pure data and small pure functions.

No clock, no randomness of its own (the engine passes `now` and its seeded `rng`), no Win32.

**Mind.** Three needs rise with time (`rest`, `curiosity`, `play`), a mood follows them and the
last event (`happy`, `curious`, `sleepy`, `startled`, `proud`, `bored`), and the next thing it
does is a weighted choice: an activity is likelier when it feeds a high need, is vetoed for
`NO_REPEAT` seconds after it was done, and costs less the closer the mood is to it. Doing an
activity lowers the needs it feeds, so a figure that just played wants quiet.

**Body language.** There are only the shipped frames, so every activity is a base frame plus a
`Pose` over it: a bottom-anchored squash and stretch (`sy`), a turn-about squeeze (`sx`), a lean
(`lean`, the head moves by that share of the figure's height) and a `drag` (how far the lower
wisp and tail lag, from `Trail`). `sprites.SpriteSet.posed` draws a pose by a mesh warp, cached by
the quantised pose, so a stretch, a breath or a turn needs no new picture.
"""

from __future__ import annotations

import math
import random
from typing import Any, NamedTuple

#: Seconds an activity is not repeated after it was done.
NO_REPEAT = 180.0
#: Need rise per second at rest (they reach 1.0 in about this many seconds without relief).
NEED_FULL = {"rest": 1500.0, "curiosity": 700.0, "play": 1100.0}
MOODS = ("happy", "curious", "sleepy", "startled", "proud", "bored")
#: How long an event keeps a mood in front (seconds).
MOOD_FOR = 25.0
#: The lively ones (a bounce, a wiggle, a sway, a loop, a dance, a wave) are chosen acts, rare (INBOX
#: 1670, 13:15Z: "it can't sit still, it has like ADHD"): the first one comes no sooner than
#: `FIDGET_FIRST` seconds in, then one at most every `FIDGET_GAP`, so about two an hour at most.
FIDGETS = frozenset({"bounce", "wiggle", "sway", "float_loop", "little_dance", "wave_idle", "shake_off"})
FIDGET_FIRST = 600.0
FIDGET_GAP = 1800.0
#: How long a hang lasts by mood (INBOX 1670, 13:28Z: "it doesn't hang for a while"): tens of seconds to
#: a few minutes. A tired one lets go sooner, a curious or bored one stays and looks about.
HANG_BY_MOOD = {
    "sleepy": (30.0, 60.0), "startled": (30.0, 50.0), "happy": (60.0, 140.0), "proud": (50.0, 120.0),
    "curious": (80.0, 170.0), "bored": (90.0, 200.0),
}


class Pose(NamedTuple):
    sx: float = 1.0
    sy: float = 1.0
    lean: float = 0.0
    drag: float = 0.0


NEUTRAL = Pose()
#: Pose steps: coarse enough to keep the warped-frame cache small, fine enough to be smooth.
Q_SCALE, Q_LEAN, Q_DRAG = 0.02, 0.02, 1.0


def quantised(p: Pose, q_sy: float = Q_SCALE) -> Pose | None:
    """The pose snapped to the cache grid (`q_sy` is the height's step), or None when it is the plain frame."""
    q = Pose(
        round(p.sx / Q_SCALE) * Q_SCALE, round(p.sy / q_sy) * q_sy,
        round(p.lean / Q_LEAN) * Q_LEAN, round(p.drag / Q_DRAG) * Q_DRAG,
    )
    q = Pose(round(q.sx, 2), round(q.sy, 3), round(q.lean, 2), float(q.drag))
    return None if q == NEUTRAL else q


def smooth(u: float) -> float:
    u = min(max(u, 0.0), 1.0)
    return u * u * (3.0 - 2.0 * u)


Keys = tuple[tuple[float, float, float, float], ...]  # (u, sx, sy, lean)


def sample(keys: Keys, u: float) -> Pose:
    """The pose at `u` (0 to 1 through the activity), eased between keyframes."""
    if not keys:
        return NEUTRAL
    if u <= keys[0][0]:
        return Pose(keys[0][1], keys[0][2], keys[0][3])
    for a, b in zip(keys, keys[1:]):
        if u <= b[0]:
            k = smooth((u - a[0]) / max(1e-6, b[0] - a[0]))
            return Pose(a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k, a[3] + (b[3] - a[3]) * k)
    return Pose(keys[-1][1], keys[-1][2], keys[-1][3])


class Activity(NamedTuple):
    #: The base frame, or a timeline of (u, frame) switches.
    frame: str | tuple[tuple[float, str], ...]
    seconds: tuple[float, float]
    keys: Keys
    #: Need -> how much it lowers (negative) or raises when it is done.
    feeds: tuple[tuple[str, float], ...]
    #: "any", "walk" (a ground companion) or "float" (Atlas).
    gait: str = "any"
    #: Mood that makes it likelier, and one that rules it out.
    likes: str = ""
    #: Times (u) at which it turns to face the other way.
    turns: tuple[float, ...] = ()
    #: Only on a perch or only on the floor; "" for either.
    where: str = ""


def _k(*rows: tuple[float, float, float, float]) -> Keys:
    return rows


#: At least twenty things to do in place (INBOX 1670: "a lot of actions and activities it can
#: perform or do while idle"). Each is a base frame, a pose over it, and what it feeds.
ACTIVITIES: dict[str, Activity] = {
    "breathe": Activity("stand", (4.0, 6.0), _k((0, 1, 1, 0), (0.5, 1, 1.018, 0), (1, 1, 1, 0)), (("rest", -0.05),)),
    "shift_weight": Activity("stand", (2.0, 3.0), _k((0, 1, 1, 0), (0.4, 1, 0.99, 0.05), (0.8, 1, 0.99, -0.04), (1, 1, 1, 0)), ()),
    "look_around": Activity(((0, "look"),), (2.5, 4.0), _k((0, 1, 1, 0), (0.3, 0.97, 1, 0.03), (0.7, 0.97, 1, -0.03), (1, 1, 1, 0)), (("curiosity", -0.15),), turns=(0.5,), likes="curious"),
    "slow_blink": Activity(((0, "stand"), (0.35, "blink"), (0.6, "stand")), (1.2, 1.6), _k((0, 1, 1, 0), (0.5, 1, 0.99, 0), (1, 1, 1, 0)), ()),
    "stretch": Activity("stand", (2.2, 3.0), _k((0, 1, 1, 0), (0.25, 1.03, 0.94, 0), (0.6, 0.97, 1.09, 0), (0.85, 1, 1.02, 0), (1, 1, 1, 0)), (("rest", -0.25),), likes="sleepy"),
    "yawn": Activity(((0, "stand"), (0.3, "blink"), (0.75, "stand")), (2.0, 2.6), _k((0, 1, 1, 0), (0.3, 0.98, 1.06, 0), (0.7, 0.98, 1.06, 0), (1, 1, 1, 0)), (("rest", -0.1),), likes="sleepy"),
    "glance_pointer": Activity("look", (1.4, 2.4), _k((0, 1, 1, 0), (0.3, 0.98, 1.01, 0.04), (0.8, 0.98, 1.01, 0.04), (1, 1, 1, 0)), (("curiosity", -0.1),), likes="curious"),
    "little_dance": Activity("wave", (3.0, 4.2), _k((0, 1, 1, 0), (0.15, 1, 0.94, 0.06), (0.3, 1, 1.05, -0.07), (0.45, 1, 0.94, 0.07), (0.6, 1, 1.05, -0.07), (0.75, 1, 0.94, 0.05), (0.9, 1, 1.03, 0), (1, 1, 1, 0)), (("play", -0.5),), likes="happy"),
    "sway": Activity("stand", (4.0, 6.0), _k((0, 1, 1, 0), (0.25, 1, 1.01, 0.05), (0.75, 1, 1.01, -0.05), (1, 1, 1, 0)), (("play", -0.1),), likes="happy"),
    "ponder": Activity("look", (3.0, 5.0), _k((0, 1, 1, 0), (0.3, 0.98, 0.99, -0.05), (0.8, 0.98, 0.99, -0.05), (1, 1, 1, 0)), (("curiosity", -0.1),), likes="curious"),
    "nod": Activity("stand", (1.0, 1.4), _k((0, 1, 1, 0), (0.3, 1.01, 0.95, 0.02), (0.6, 1, 1, 0), (0.8, 1.01, 0.97, 0.02), (1, 1, 1, 0)), ()),
    "shrug": Activity("stand", (1.2, 1.6), _k((0, 1, 1, 0), (0.3, 1.03, 0.95, 0), (0.6, 1.03, 0.95, 0), (1, 1, 1, 0)), ()),
    "wiggle": Activity("stand", (1.0, 1.6), _k((0, 1, 1, 0), (0.15, 1, 1, 0.07), (0.3, 1, 1, -0.07), (0.45, 1, 1, 0.06), (0.6, 1, 1, -0.05), (0.8, 1, 1, 0.02), (1, 1, 1, 0)), (("play", -0.15),), likes="happy"),
    "bounce": Activity("hop", (1.2, 1.6), _k((0, 1, 1, 0), (0.2, 1.04, 0.86, 0), (0.45, 0.96, 1.12, 0), (0.7, 1.03, 0.9, 0), (1, 1, 1, 0)), (("play", -0.3),), likes="happy"),
    "scan_horizon": Activity("look", (4.0, 6.0), _k((0, 1, 1, 0), (0.2, 0.97, 1.02, 0.04), (0.5, 0.97, 1.02, 0.04), (0.55, 0.97, 1.02, -0.04), (0.9, 0.97, 1.02, -0.04), (1, 1, 1, 0)), (("curiosity", -0.2),), turns=(0.5,), likes="curious"),
    "sit_down": Activity("sit", (8.0, 18.0), _k((0, 1, 1, 0), (0.05, 1, 0.97, 0), (0.12, 1, 1, 0), (1, 1, 1, 0)), (("rest", -0.5),), likes="sleepy"),
    "doze": Activity(((0, "sit"), (0.2, "sleep")), (10.0, 24.0), _k((0, 1, 1, 0), (0.2, 1, 0.98, 0.02), (1, 1, 0.98, 0.02)), (("rest", -0.8),), likes="sleepy"),
    "curl_up": Activity("sleep", (12.0, 30.0), _k((0, 1, 1, 0), (0.1, 1, 0.98, 0), (1, 1, 0.98, 0)), (("rest", -1.0),), likes="sleepy"),
    "pose_proud": Activity("stand", (2.0, 3.0), _k((0, 1, 1, 0), (0.25, 0.99, 1.06, 0), (0.8, 0.99, 1.06, 0), (1, 1, 1, 0)), (), likes="proud"),
    "peek_down": Activity("look", (2.0, 3.0), _k((0, 1, 1, 0), (0.3, 1, 0.97, 0.06), (0.8, 1, 0.97, 0.06), (1, 1, 1, 0)), (("curiosity", -0.1),)),
    "shake_off": Activity("stand", (0.8, 1.1), _k((0, 1, 1, 0), (0.12, 1, 1, 0.08), (0.24, 1, 1, -0.08), (0.36, 1, 1, 0.07), (0.48, 1, 1, -0.07), (0.6, 1, 1, 0.05), (0.75, 1, 1, -0.03), (1, 1, 1, 0)), (), likes="startled"),
    "wave_idle": Activity("wave", (1.6, 2.4), _k((0, 1, 1, 0), (0.2, 1, 1.02, 0.02), (0.8, 1, 1.02, 0.02), (1, 1, 1, 0)), (("play", -0.1),), likes="happy"),
    "crouch_watch": Activity("land", (2.0, 3.5), _k((0, 1, 1, 0), (0.25, 1.03, 0.9, 0), (0.85, 1.03, 0.9, 0), (1, 1, 1, 0)), (("curiosity", -0.15),), gait="walk", likes="curious"),
    "float_loop": Activity("hop", (2.2, 3.0), _k((0, 1, 1, 0), (0.3, 0.98, 1.05, 0.05), (0.7, 0.98, 1.05, -0.05), (1, 1, 1, 0)), (("play", -0.3),), gait="float", likes="happy"),
    "lie_down": Activity("sleep", (10.0, 22.0), _k((0, 1, 1, 0), (0.15, 1.04, 0.9, 0), (1, 1.04, 0.9, 0)), (("rest", -0.8),), gait="walk", likes="sleepy"),
    "tail_flick": Activity("stand", (0.9, 1.3), _k((0, 1, 1, 0), (0.2, 1, 1, 0.06), (0.4, 1, 1, -0.02), (1, 1, 1, 0)), ()),
}
#: The ones that only make sense in place: all of them (a trip is a different table).
IDLE_NAMES = tuple(ACTIVITIES)
#: Base chance of each, before need, mood and repeat shape it. Quiet things are common.
BASE_WEIGHT = {
    "breathe": 9, "shift_weight": 8, "look_around": 8, "slow_blink": 8, "tail_flick": 7, "nod": 3, "shrug": 3,
    "stretch": 4, "yawn": 3, "glance_pointer": 5, "ponder": 4, "sway": 4, "wiggle": 3, "bounce": 2,
    "scan_horizon": 3, "little_dance": 2, "wave_idle": 2, "sit_down": 4, "doze": 2, "curl_up": 1, "pose_proud": 2,
    "peek_down": 3, "shake_off": 1, "crouch_watch": 3, "float_loop": 3, "lie_down": 2,
}


def mood_of(needs: dict[str, float], event: str, event_age: float, hour: int) -> str:
    """The mood: an event of the last `MOOD_FOR` seconds wins; else the strongest need."""
    if event and event_age < MOOD_FOR:
        return event
    if needs["rest"] > 0.65 or hour >= 23 or hour < 6:
        return "sleepy"
    if needs["curiosity"] > 0.6:
        return "curious"
    if needs["play"] > 0.6:
        return "happy"
    if needs["rest"] < 0.1 and needs["curiosity"] < 0.15 and needs["play"] < 0.15:
        return "bored"
    return "proud" if needs["play"] < 0.1 else "happy"


class Mind:
    """Needs, mood and what it did lately."""

    def __init__(self, now: float = 0.0) -> None:
        self.needs = {"rest": 0.1, "curiosity": 0.2, "play": 0.2}
        self.event = ""
        self.event_at = -1e9
        self.done: dict[str, float] = {}
        self.at = now
        self.fidget_ready = now + FIDGET_FIRST

    def tick(self, now: float, hour: int = 12) -> None:
        dt = min(max(now - self.at, 0.0), 30.0)
        self.at = now
        night = 2.0 if (hour >= 23 or hour < 6) else 1.0
        for k, full in NEED_FULL.items():
            self.needs[k] = min(1.0, self.needs[k] + dt / full * (night if k == "rest" else 1.0))

    def mood(self, now: float, hour: int = 12) -> str:
        return mood_of(self.needs, self.event, now - self.event_at, hour)

    def feel(self, event: str, now: float) -> None:
        self.event, self.event_at = event, now

    def did(self, name: str, now: float) -> None:
        self.done[name] = now
        if name in FIDGETS:
            self.fidget_ready = now + FIDGET_GAP
        for need, delta in ACTIVITIES[name].feeds if name in ACTIVITIES else ():
            self.needs[need] = min(1.0, max(0.0, self.needs[need] + delta))

    def weights(self, now: float, gait: str, hour: int = 12, where: str = "") -> list[tuple[str, float]]:
        mood = self.mood(now, hour)
        tired = mood == "sleepy" or self.needs["rest"] > 0.6
        content = mood in ("proud", "bored") or self.needs["play"] < 0.15
        out = []
        for name, act in ACTIVITIES.items():
            if act.gait not in ("any", gait) or (act.where and act.where != where):
                continue
            if name in FIDGETS and (now < self.fidget_ready or tired):
                continue  # a fidget is a rare, chosen act; a tired one does not
            if now - self.done.get(name, -1e9) < NO_REPEAT and name not in ("breathe", "shift_weight", "slow_blink", "tail_flick"):
                continue  # quiet micro things may recur; the rest wait their turn
            out.append((name, self._weight(name, act, mood, content, hour)))
        return out

    def _weight(self, name: str, act: Activity, mood: str, content: bool, hour: int) -> float:
        w = float(BASE_WEIGHT.get(name, 2))
        for need, delta in act.feeds:
            if delta < 0:
                w *= 1.0 + 3.0 * self.needs[need]
        if act.likes == mood:
            w *= 2.5
        if name in FIDGETS and content:
            w *= 0.4  # content, it has less to burn off
        if name in ("doze", "curl_up", "lie_down", "sit_down") and self.needs["rest"] < 0.3 and not (hour >= 23 or hour < 6):
            w *= 0.2
        return w

    def pick(self, rng: random.Random, now: float, gait: str, hour: int = 12, where: str = "") -> str:
        table = self.weights(now, gait, hour, where)
        roll = rng.random() * sum(w for _n, w in table)
        for name, w in table:
            roll -= w
            if roll < 0:
                return name
        return "breathe"


def activity_frame(act: Activity, u: float) -> str:
    if isinstance(act.frame, str):
        return act.frame
    frame = act.frame[0][1]
    for at, name in act.frame:
        if u >= at:
            frame = name
    return frame


# --- tail and lower wisp physics ---------------------------------------------------------


class Trail:
    """A spring chain that lags the body: the tail, the lower wisp, the nebula trail. Each
    link is pulled toward the one before it and thrown by the body's acceleration, so it
    streams behind a start, overshoots a stop and swings round a turn. `tip` is the last link's
    offset in px, opposite to the way the body speeds up; the sprite warp reads it."""

    LINKS = 3
    STIFF = 90.0
    DAMP = 9.0
    KICK = 0.8
    MAX = 26.0

    def __init__(self) -> None:
        self.pos = [0.0] * self.LINKS
        self.vel = [0.0] * self.LINKS
        self.last_v = 0.0

    @property
    def tip(self) -> float:
        return self.pos[-1]

    def settled(self) -> bool:
        return abs(self.pos[-1]) < 0.6 and abs(self.vel[-1]) < 4.0

    def step(self, dt: float, body_vx: float) -> None:
        """Advance by `dt` seconds with the body moving at `body_vx` px/s (before this step)."""
        if dt <= 0:
            return
        accel = (body_vx - self.last_v) / dt
        self.last_v = body_vx
        n = max(1, int(math.ceil(dt / 0.02)))
        h = dt / n
        for _ in range(n):
            prev = 0.0
            for i in range(self.LINKS):
                force = self.STIFF * (prev - self.pos[i]) - self.DAMP * self.vel[i] - accel * self.KICK * (1 + i)
                self.vel[i] += force * h
                self.pos[i] = max(-self.MAX, min(self.MAX, self.pos[i] + self.vel[i] * h))
                prev = self.pos[i]

    def reset(self) -> None:
        self.pos, self.vel, self.last_v = [0.0] * self.LINKS, [0.0] * self.LINKS, 0.0


def _amplitude(keys: Keys) -> float:
    return max(max(abs(k[1] - 1), abs(k[2] - 1), abs(k[3]) * 0.8) for k in keys)


#: How much each activity moves the body (the engine redraws a calm one less often).
AMPLITUDE = {name: _amplitude(a.keys) for name, a in ACTIVITIES.items()}


# --- the lower body's own life: wisps and nebula streams (INBOX 1683 c) ---------------------------------
#: Strands across the figure's width. Each has its own octave periods, so no two move together and none
#: reads as a loop; `FLOW_PERIODS` are the three octaves' ranges in seconds (the shortest is over 4 s, the
#: wander below keeps it so) and `FLOW_WEIGHTS` how much each counts (the fastest leads).
FLOW_BANDS = 7
FLOW_PERIODS = ((9.0, 13.0), (5.6, 8.6), (4.4, 5.9))
FLOW_WEIGHTS = (0.4, 0.6, 1.0)
#: Largest ambient sway of a strand's tip and its rise and fall, px of the shipped frame. At the hem this is
#: under 3 degrees off the torso over the lower body's length (INBOX 615 and 619: never more than 4).
FLOW_TIP = 2.2
FLOW_RISE = 1.1
#: Outer strands (the orbiting streams) sway more than the middle ones; a middle's lead over its tip.
FLOW_EDGE = 1.0
FLOW_MID = 0.35
#: Follow-through: each strand is a spring with its own stiffness, thrown by the body's acceleration and leaning
#: back with its speed (a stream trails what moves it), `FLOW_MAX` px at most.
FLOW_STIFF = (34.0, 62.0)
FLOW_DAMP = 0.4
FLOW_KICK = 0.18
FLOW_STREAM = 0.012
FLOW_MAX = 6.0
#: Reduced motion: a slow drift only, this share of the sway at this multiple of the periods.
FLOW_CALM_AMP = 0.5
FLOW_CALM_SLOW = 2.6
FLOW_Q = 8.0


def _frac(x: float) -> float:
    return x - math.floor(x)


class Flow:
    """The wisps and the nebula streams move all the time. Each of `FLOW_BANDS` strands carries three octaves of
    sine at its own periods and phases (so nothing lines up or repeats within a minute) with a slow wander of
    its phase, the sway of its middle a beat behind its tip (a wave runs down it), a rise and fall a quarter
    turn behind the sway (the tip goes round an ellipse, never at rest in both at once), and a sparkle that
    travels down it. On top sits the follow-through: a spring per strand thrown by the body's acceleration,
    leaning back with its speed (it streams behind a start and when the figure floats up, and drifts on after a
    stop). `view` is the picture's whole input as small integers (`FLOW_Q` steps a px), so the sprite cache can
    key on it and a still view costs no redraw."""

    def __init__(self, seed: int = 1683) -> None:
        rng = random.Random(seed)
        self.t0 = rng.random() * 500.0
        self.bands = []
        for i in range(FLOW_BANDS):
            octaves = []
            for k, (lo, hi) in enumerate(FLOW_PERIODS):
                octaves.append((lo + (hi - lo) * _frac(i * (0.618 + 0.137 * k) + 0.23 * k + rng.random() * 0.2), rng.random() * math.tau))
            self.bands.append(octaves)
        self.wander = [37.0 + 5.3 * i for i in range(FLOW_BANDS)]
        self.glint_periods = [4.6 + 0.8 * ((i * 2) % FLOW_BANDS) for i in range(FLOW_BANDS)]
        self.pos = [[0.0, 0.0] for _ in range(FLOW_BANDS)]
        self.vel = [[0.0, 0.0] for _ in range(FLOW_BANDS)]
        self.stiff = [FLOW_STIFF[0] + (FLOW_STIFF[1] - FLOW_STIFF[0]) * _frac(i * 0.754 + 0.31) for i in range(FLOW_BANDS)]
        self.last_v = (0.0, 0.0)

    def reach(self, i: int) -> float:
        """How far strand `i` sways: the outer ones (the streams) most."""
        edge = abs(i - (FLOW_BANDS - 1) / 2) / ((FLOW_BANDS - 1) / 2)
        return FLOW_TIP * (0.75 + (FLOW_EDGE * 0.25) * edge)

    def _octaves(self, i: int, t: float, calm: bool, wave: Any) -> float:
        slow = FLOW_CALM_SLOW if calm else 1.0
        total = 0.0
        for k, (period, phase) in enumerate(self.bands[i]):
            wander = 0.15 * math.sin(math.tau * t / (self.wander[i] * slow) + phase * 3.0)
            total += FLOW_WEIGHTS[k] * wave(math.tau * t / (period * slow) + phase + wander)
        return total / sum(FLOW_WEIGHTS) * (FLOW_CALM_AMP if calm else 1.0)

    def sway(self, i: int, t: float, calm: bool = False) -> float:
        """Strand `i`'s ambient sway at `t`, px (-FLOW_TIP..FLOW_TIP): three octaves, each a phase that wanders."""
        return self.reach(i) * self._octaves(i, t, calm, math.sin)

    def rise(self, i: int, t: float, calm: bool = False) -> float:
        """Its rise and fall: the same octaves a quarter turn on."""
        return FLOW_RISE * self._octaves(i, t, calm, math.cos)

    def step(self, dt: float, vx: float, vy: float) -> None:
        """Advance the follow-through by `dt` seconds with the body at (`vx`, `vy`) px/s of the shipped frame."""
        if dt <= 0:
            return
        ax, ay = (vx - self.last_v[0]) / dt, (vy - self.last_v[1]) / dt
        self.last_v = (vx, vy)
        n = max(1, int(math.ceil(dt / 0.02)))
        h = dt / n
        for i in range(FLOW_BANDS):
            k = self.stiff[i]
            c = 2.0 * FLOW_DAMP * math.sqrt(k)
            gain = 0.7 + 0.6 * _frac(i * 0.43 + 0.1)  # each strand is thrown by its own share
            for axis, v, a in ((0, vx, ax), (1, vy, ay)):
                rest = -v * FLOW_STREAM * gain
                p, q = self.pos[i][axis], self.vel[i][axis]
                for _ in range(n):
                    q += (k * (rest - p) - c * q - a * FLOW_KICK * gain) * h
                    p = max(-FLOW_MAX, min(FLOW_MAX, p + q * h))
                self.pos[i][axis], self.vel[i][axis] = p, q

    def settled(self) -> bool:
        return all(abs(p[0]) < 0.3 and abs(p[1]) < 0.3 and abs(v[0]) < 2.0 and abs(v[1]) < 2.0 for p, v in zip(self.pos, self.vel))

    def view(self, t: float, calm: bool = False) -> tuple[int, ...]:
        """Per strand `(tip dx, middle dx, tip dy, sparkle sin, sparkle cos)` in `FLOW_Q` steps (the sparkle in
        tenths), the follow-through folded in: what the warp needs and nothing else."""
        t = t + self.t0
        out: list[int] = []
        for i in range(FLOW_BANDS):
            fx, fy = self.pos[i]
            tip = max(-FLOW_MAX, min(FLOW_MAX, self.sway(i, t, calm) + fx))
            mid = max(-FLOW_MAX, min(FLOW_MAX, self.sway(i, t - 0.9, calm) * (1 - FLOW_MID) + fx * 0.5))
            drop = self.rise(i, t, calm) + fy
            w = math.tau * t / (self.glint_periods[i] * (FLOW_CALM_SLOW if calm else 1.0)) + i * 1.3
            out += [round(tip * FLOW_Q), round(mid * FLOW_Q), round(drop * FLOW_Q), round(math.sin(w) * 10), round(math.cos(w) * 10)]
        return tuple(out)
