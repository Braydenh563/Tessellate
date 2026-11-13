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

import functools
import math
import random
from typing import Any, NamedTuple

from tessellate.core.overlay import catalogue, wisps

#: Seconds an activity is not repeated after it was done.
NO_REPEAT = 180.0
#: Need rise per second at rest (they reach 1.0 in about this many seconds without relief).
NEED_FULL = {
    "rest": 1500.0, "curiosity": 700.0, "play": 1100.0,
    # B2: a wish for company (the person's attention), for comfort (a groom, a settle), for a bite, and for
    # something new (boredom is `novelty` high).
    "social": 900.0, "comfort": 1300.0, "hunger": 2400.0, "novelty": 1800.0,
}
MOODS = ("happy", "curious", "sleepy", "startled", "proud", "bored")
#: How long an event keeps a mood in front (seconds).
MOOD_FOR = 25.0
#: The lively ones (a bounce, a wiggle, a sway, a loop, a dance, a wave) are chosen acts, rare (INBOX
#: 1670, 13:15Z: "it can't sit still, it has like ADHD"): the first one comes no sooner than
#: `FIDGET_FIRST` seconds in, then one at most every `FIDGET_GAP`, so about two an hour at most.
FIDGETS = frozenset({"bounce", "wiggle", "sway", "float_loop", "little_dance", "wave_idle", "shake_off"})
FIDGET_FIRST = 600.0
FIDGET_GAP = 1800.0
#: How long a hang lasts by mood (INBOX 1670, 13:28Z: "it doesn't hang for a while"; INBOX 1696 b: minutes, not
#: tens of seconds): one to five minutes (longer took a third of an evening's spells). A tired one lets go sooner, a curious or bored one stays and looks about.
HANG_BY_MOOD = {
    "sleepy": (60.0, 120.0), "startled": (60.0, 90.0), "happy": (90.0, 240.0), "proud": (90.0, 180.0),
    "curious": (120.0, 300.0), "bored": (150.0, 300.0),
}


class Pose(NamedTuple):
    sx: float = 1.0
    sy: float = 1.0
    lean: float = 0.0
    drag: float = 0.0


NEUTRAL = Pose()
_N_SX, _N_SY, _N_LEAN, _N_DRAG = NEUTRAL


class SecondOrder:
    """A value that follows a target by second-order dynamics (research A2; t3ssel8r's "giving personality to
    procedural animations"): `f` is how quickly it responds (Hz), `zeta` the damping (below 1 it overshoots a little,
    1 and above it does not), `r` the initial response (0 starts from rest, below 0 it anticipates by stepping
    back first, above 1 it overshoots at once). The step is the semi-implicit one, made stable for any frame
    length by raising the inertia term when a frame is long."""

    def __init__(self, f: float, zeta: float, r: float, x0: float = 0.0) -> None:
        self.k1 = zeta / (math.pi * f)
        self.k2 = 1.0 / (2.0 * math.pi * f) ** 2
        self.k3 = r * zeta / (2.0 * math.pi * f)
        self.y, self.yd, self.xp = x0, 0.0, x0

    def step(self, dt: float, x: float) -> float:
        if dt <= 0.0:
            return self.y
        xd = (x - self.xp) / dt
        self.xp = x
        k2 = max(self.k2, dt * dt / 2.0 + dt * self.k1 / 2.0, dt * self.k1)  # stable for a long frame
        # velocity first, then position from the new velocity (symplectic Euler): moving by the old velocity made the first
        # step after a rest move nothing at all, a draw's worth of lag on every new target
        self.yd += dt * (x + self.k3 * xd - self.y - self.k1 * self.yd) / k2
        self.y += dt * self.yd
        return self.y
#: Pose steps: coarse enough to keep the warped-frame cache small, fine enough to be smooth.
Q_SCALE, Q_LEAN, Q_DRAG = 0.02, 0.02, 1.0


def quantise(sx: float, sy: float, lean: float, drag: float, q_sy: float = Q_SCALE) -> Pose | None:
    """`quantised` for the four numbers (a look-ahead runs it hundreds of thousands of times: no Pose in between)."""
    sx = round(round(sx / Q_SCALE) * Q_SCALE, 2)
    sy = round(round(sy / q_sy) * q_sy, 3)
    lean = round(round(lean / Q_LEAN) * Q_LEAN, 2)
    drag = float(round(drag / Q_DRAG) * Q_DRAG)
    if sx == _N_SX and sy == _N_SY and lean == _N_LEAN and drag == _N_DRAG:
        return None
    return Pose(sx, sy, lean, drag)


def cell(sx: float, sy: float, lean: float, drag: float, q_sy: float = Q_SCALE) -> tuple[int, int, int, int]:
    """The grid cell of a pose: the whole steps `quantise` multiplies back. Two poses are the same picture exactly when
    their cells are equal (the steps are far wider than the rounding after them), so a look-ahead compares cells."""
    return round(sx / Q_SCALE), round(sy / q_sy), round(lean / Q_LEAN), round(drag / Q_DRAG)


def quantised(p: Pose, q_sy: float = Q_SCALE) -> Pose | None:
    """The pose snapped to the cache grid (`q_sy` is the height's step), or None when it is the plain frame."""
    return quantise(p.sx, p.sy, p.lean, p.drag, q_sy)


def smooth(u: float) -> float:
    u = min(max(u, 0.0), 1.0)
    return u * u * (3.0 - 2.0 * u)


def smoother(u: float) -> float:
    u = min(max(u, 0.0), 1.0)
    return u * u * u * (u * (u * 6.0 - 15.0) + 10.0)


def sine_ease(u: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * min(max(u, 0.0), 1.0))


#: The easings a play can draw (research V3): the same keyframes, a slightly different feel each time.
EASES = (smooth, smoother, sine_ease)
VARY_AMP = (0.85, 1.15)
VARY_DUR = (0.85, 1.15)


class Variation(NamedTuple):
    """One play of an act: how big (factor), how long (factor) and which easing."""

    amp: float = 1.0
    dur: float = 1.0
    ease: Any = smooth


def vary(rng: random.Random) -> Variation:
    """A seeded per-play variation: amplitude 0.85 to 1.15, duration plus or minus 15%, one of `EASES`."""
    return Variation(rng.uniform(*VARY_AMP), rng.uniform(*VARY_DUR), rng.choice(EASES))


def scaled(p: Pose, amp: float) -> Pose:
    """`p` with its distance from neutral multiplied by `amp`."""
    return Pose(1.0 + (p.sx - 1.0) * amp, 1.0 + (p.sy - 1.0) * amp, p.lean * amp, p.drag)


Keys = tuple[tuple[float, float, float, float], ...]  # (u, sx, sy, lean)


def sample3(keys: Keys, u: float, ease: Any = smooth) -> tuple[float, float, float]:
    """`sample` as the bare (sx, sy, lean): the act look-ahead reads it thirty times a wake."""
    if not keys:
        return 1.0, 1.0, 0.0
    first = keys[0]
    if u <= first[0]:
        return first[1], first[2], first[3]
    a = first
    for b in keys[1:]:
        if u <= b[0]:
            k = ease((u - a[0]) / max(1e-6, b[0] - a[0]))
            return a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k, a[3] + (b[3] - a[3]) * k
        a = b
    last = keys[-1]
    return last[1], last[2], last[3]


def sample(keys: Keys, u: float, ease: Any = smooth) -> Pose:
    """The pose at `u` (0 to 1 through the activity), eased between keyframes."""
    if not keys:
        return NEUTRAL
    return Pose(*sample3(keys, u, ease))


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
_PACE = _k((0, 1, 1, 0), (0.2, 1, 1, 0.05), (0.45, 1, 1, -0.05), (0.7, 1, 1, 0.05), (1, 1, 1, 0))
#: B2/B1 (INBOX 1683 l): more things to do in place, each feeding one of the new needs.
ACTIVITIES.update({
    "groom": Activity("sit", (4.0, 7.0), _k((0, 1, 1, 0), (0.15, 1, 0.97, 0.05), (0.35, 1, 0.97, -0.05), (0.55, 1, 0.97, 0.05), (0.8, 1, 0.98, 0), (1, 1, 1, 0)), (("comfort", -0.45),), likes="sleepy"),
    "scratch": Activity("stand", (1.6, 2.6), _k((0, 1, 1, 0), (0.15, 1.01, 0.97, 0.06), (0.3, 1, 1, -0.02), (0.45, 1.01, 0.97, 0.06), (0.6, 1, 1, -0.02), (1, 1, 1, 0)), (("comfort", -0.2),)),
    "snack": Activity("sit", (6.0, 10.0), _k((0, 1, 1, 0), (0.15, 1, 0.98, 0.03), (0.4, 1, 1, 0.01), (0.65, 1, 0.98, 0.03), (1, 1, 1, 0)), (("hunger", -0.7), ("rest", -0.05)), likes="happy"),
    "peer_at_cursor": Activity("look", (2.0, 3.2), _k((0, 1, 1, 0), (0.25, 0.97, 1.03, 0.05), (0.8, 0.97, 1.03, 0.05), (1, 1, 1, 0)), (("social", -0.25), ("curiosity", -0.1)), likes="curious"),
    "pace": Activity("stand", (3.0, 5.0), _PACE, (("novelty", -0.25), ("play", -0.05))),
    "invent_game": Activity("hop", (2.4, 3.6), _k((0, 1, 1, 0), (0.15, 1.04, 0.88, 0), (0.35, 0.96, 1.1, 0.04), (0.55, 1.03, 0.9, 0), (0.75, 0.97, 1.08, -0.04), (1, 1, 1, 0)), (("novelty", -0.4), ("play", -0.3)), likes="happy"),
    "tinker": Activity("look", (3.0, 5.0), _k((0, 1, 1, 0), (0.2, 0.98, 0.99, -0.04), (0.5, 0.98, 0.99, 0.04), (0.8, 0.98, 0.99, -0.03), (1, 1, 1, 0)), (("novelty", -0.35), ("curiosity", -0.1)), likes="curious"),
    "dust_off": Activity("stand", (1.0, 1.5), _k((0, 1, 1, 0), (0.15, 1, 1, 0.06), (0.3, 1, 1, -0.06), (0.5, 1, 1, 0.04), (1, 1, 1, 0)), (("comfort", -0.2),)),
})
#: INBOX 1710 (the owner: "they need to be just as good as each other"): eleven of the in-app companion's own acts, each a
#: pose of its own over a frame the desk already has; their lengths and weights come from the shared catalogue (`_from_catalogue`). The long sitting ones
#: (meditate, lounge, rest head: up to 80 s on the sit frame) are `YIELD_TO_SIT`: at ten minutes idle the engine ends them so its own sit is not held off.
ACTIVITIES.update({
    "sigh": Activity("stand", (1.7, 2.8), _k((0, 1, 1, 0), (0.3, 1.01, 1.05, 0), (0.55, 1.01, 1.05, 0), (0.85, 1, 0.95, 0.01), (1, 1, 1, 0)), (("rest", -0.05),)),
    "head_tilt": Activity("look", (1.0, 2.0), _k((0, 1, 1, 0), (0.3, 1, 1, 0.09), (0.75, 1, 1, 0.09), (1, 1, 1, 0)), (("curiosity", -0.1),), likes="curious"),
    "juggle": Activity("wave", (5.4, 8.0), _k((0, 1, 1, 0), (0.1, 1, 1.03, 0.02), (0.25, 1, 0.97, -0.02), (0.4, 1, 1.03, 0.02), (0.55, 1, 0.97, -0.02), (0.7, 1, 1.03, 0.02), (0.85, 1, 0.98, -0.01), (1, 1, 1, 0)), (("play", -0.4),), likes="happy"),
    "toss_stars": Activity("wave", (4.4, 6.0), _k((0, 1, 1, 0), (0.15, 1, 1.05, 0.04), (0.3, 1, 0.96, -0.03), (0.5, 1, 1.05, 0.04), (0.7, 1, 0.96, -0.03), (0.9, 1, 1.02, 0), (1, 1, 1, 0)), (("play", -0.3),), likes="happy"),
    "ear_twitch": Activity("stand", (0.4, 0.8), _k((0, 1, 1, 0), (0.3, 1, 1.01, 0.03), (0.6, 1, 1, -0.02), (1, 1, 1, 0)), ()),
    "facepalm": Activity("stand", (2.6, 3.0), _k((0, 1, 1, 0), (0.25, 1, 0.96, 0.05), (0.75, 1, 0.96, 0.05), (1, 1, 1, 0)), (), likes="bored"),
    "hands_on_hips": Activity("stand", (10.0, 16.0), _k((0, 1, 1, 0), (0.08, 1.02, 1.02, 0), (0.3, 1.02, 1.03, 0.02), (0.6, 1.02, 1.03, -0.02), (0.92, 1.02, 1.02, 0), (1, 1, 1, 0)), (("curiosity", -0.05),)),
    "clasp_hands": Activity("stand", (10.0, 16.0), _k((0, 1, 1, 0), (0.08, 0.99, 1.01, 0), (0.35, 0.99, 1.02, 0.015), (0.65, 0.99, 1.02, -0.015), (0.92, 0.99, 1.01, 0), (1, 1, 1, 0)), (("comfort", -0.05),)),
    "lean_tilt": Activity("stand", (4.0, 6.0), _k((0, 1, 1, 0), (0.2, 1, 1, -0.07), (0.45, 1, 1, -0.07), (0.65, 1, 1, 0.07), (0.85, 1, 1, 0.07), (1, 1, 1, 0)), ()),
    "sniff": Activity("look", (2.0, 2.8), _k((0, 1, 1, 0), (0.15, 0.99, 1.03, 0.03), (0.3, 1, 1, 0), (0.45, 0.99, 1.03, 0.03), (0.6, 1, 1, 0), (0.8, 1, 1.02, 0.02), (1, 1, 1, 0)), (("curiosity", -0.15),)),
    "cast_sparkle": Activity("wave", (1.4, 2.4), _k((0, 1, 1, 0), (0.3, 1, 1.04, 0.03), (0.55, 1, 1.04, -0.03), (0.8, 1, 1.01, 0), (1, 1, 1, 0)), (("play", -0.15),), likes="happy"),
    #: INBOX 1710, 1711: four small things with no prop, also the app's (the catalogue's `act.sneeze`, `hiccup`, `self_hug`, `foot_tap`).
    "sneeze": Activity("stand", (1.0, 1.6), _k((0, 1, 1, 0), (0.4, 0.99, 1.06, -0.05), (0.55, 1.02, 0.93, 0.07), (0.8, 1, 1, 0.01), (1, 1, 1, 0)), ()),
    "hiccup": Activity("stand", (2.0, 4.0), _k((0, 1, 1, 0), (0.12, 1, 1.04, 0), (0.22, 1, 1, 0), (0.45, 1, 1.04, 0), (0.55, 1, 1, 0), (0.75, 1, 1.04, 0), (0.85, 1, 1, 0), (1, 1, 1, 0)), ()),
    "self_hug": Activity("stand", (3.0, 6.0), _k((0, 1, 1, 0), (0.12, 0.98, 0.99, 0.02), (0.4, 0.98, 0.99, -0.04), (0.7, 0.98, 0.99, 0.04), (0.9, 0.98, 0.99, 0), (1, 1, 1, 0)), (("comfort", -0.35),), likes="sleepy"),
    "foot_tap": Activity("stand", (2.0, 4.0), _k((0, 1, 1, 0), (0.1, 1, 0.98, 0.02), (0.2, 1, 1, 0), (0.35, 1, 0.98, 0.02), (0.45, 1, 1, 0), (0.6, 1, 0.98, 0.02), (0.7, 1, 1, 0), (0.85, 1, 0.98, 0.02), (1, 1, 1, 0)), (("novelty", -0.1),), likes="bored"),
    #: INBOX 1710, 1711: the long sitting acts (the catalogue's `act.meditate`, `lounge`, `rest_head`) and four more small ones.
    "meditate": Activity("meditate", (12.0, 80.0), _k((0, 1, 1, 0), (0.06, 1, 1.03, 0), (0.2, 1, 0.98, 0), (0.35, 1, 1.03, 0), (0.5, 1, 0.98, 0), (0.65, 1, 1.03, 0), (0.8, 1, 0.98, 0), (0.94, 1, 1.02, 0), (1, 1, 1, 0)), (("rest", -0.3), ("comfort", -0.2)), likes="sleepy"),
    "lounge": Activity("sit", (14.0, 60.0), _k((0, 1, 1, 0), (0.1, 1.02, 0.96, 0.03), (0.5, 1.02, 0.95, -0.03), (0.9, 1.02, 0.96, 0.02), (1, 1, 1, 0)), (("rest", -0.35), ("comfort", -0.3)), likes="sleepy"),
    "rest_head": Activity("sit", (11.0, 40.0), _k((0, 1, 1, 0), (0.1, 1, 0.98, -0.04), (0.45, 1, 0.98, -0.04), (0.55, 1, 0.98, 0.04), (0.9, 1, 0.98, 0.04), (1, 1, 1, 0)), (("rest", -0.3),)),
    "star_catch": Activity("wave", (3.0, 6.0), _k((0, 1, 1, 0), (0.15, 1, 1.04, 0.03), (0.3, 1, 0.97, -0.03), (0.45, 1, 1.05, 0.04), (0.6, 1, 0.97, -0.02), (0.8, 1, 1.03, 0.02), (1, 1, 1, 0)), (("play", -0.25), ("curiosity", -0.1)), likes="curious"),
    "count_stars": Activity("look", (4.0, 8.0), _k((0, 1, 1, 0), (0.12, 1, 1.02, 0.02), (0.3, 1, 1, -0.02), (0.45, 1, 1.02, 0.02), (0.6, 1, 1, -0.02), (0.8, 1, 1.02, 0.01), (1, 1, 1, 0)), (("curiosity", -0.15),), likes="curious"),
    #: L-ui-modernisation-41: a floater on its back in the air (the app's third drift, `pos.back_float`); only for a floating look. Its picture is `sprites.EXTRA_FRAMES`'s.
    "back_float": Activity("back_float", (8.0, 30.0), _k((0, 1, 1, 0), (0.15, 1, 1.01, 0.02), (0.5, 1, 1.02, -0.02), (0.85, 1, 1.01, 0.02), (1, 1, 1, 0)), (("rest", -0.2), ("curiosity", -0.15)), gait="float", likes="curious"),
    "card_nap": Activity("sleep", (6.0, 14.0), _k((0, 1, 1, 0), (0.1, 1, 0.97, 0.02), (0.5, 1, 1, 0.02), (1, 1, 0.97, 0.02)), (("rest", -0.4),), likes="sleepy"),
    "wave_pointer": Activity("wave", (1.5, 2.4), _k((0, 1, 1, 0), (0.2, 1, 1.02, 0.03), (0.8, 1, 1.02, 0.03), (1, 1, 1, 0)), (("social", -0.3),), likes="happy"),
})
for _n, _extra in {"wave_idle": (("social", -0.3),), "little_dance": (("social", -0.1), ("novelty", -0.1)), "glance_pointer": (("social", -0.1),),
                   "look_around": (("novelty", -0.1),), "stretch": (("comfort", -0.2),), "sit_down": (("comfort", -0.25),)}.items():
    ACTIVITIES[_n] = ACTIVITIES[_n]._replace(feeds=ACTIVITIES[_n].feeds + _extra)
#: The long sitting acts: the engine ends them at `IDLE_SIT` so the sit comes on time (they run up to 80 s on the sit frame).
#: W31 E2 (INBOX 1710): the app's legs over an edge and the let-go hand, now with a picture each. `dangle` and `kick_legs` are
#: `where="perch"`: only on a window's top (the edge the legs go over); `hang_one_hand` is `where="hang"`, so the table never picks it:
#: the engine plays it inside a hang (`Engine._let_one_go`) and feeds the mind. Lengths and weights come from the catalogue.
ACTIVITIES.update({
    "dangle": Activity("dangle", (6.0, 40.0), _k((0, 1, 1, 0), (0.12, 1, 1.01, 0.02), (0.5, 1, 1.01, -0.02), (0.88, 1, 1.01, 0.02), (1, 1, 1, 0)), (("comfort", -0.2), ("play", -0.05)), where="perch"),
    "kick_legs": Activity(
        ((0.0, "kick0"), (0.17, "kick1"), (0.33, "kick0"), (0.5, "kick1"), (0.67, "kick0"), (0.83, "kick1")), (1.6, 3.0),
        _k((0, 1, 1, 0), (0.2, 1, 1.02, 0.02), (0.5, 1, 1.02, -0.02), (0.8, 1, 1.02, 0.02), (1, 1, 1, 0)), (("play", -0.25),), likes="happy", where="perch",
    ),
    "hang_one_hand": Activity("hang_one", (4.2, 8.0), _k((0, 1, 1, 0), (1, 1, 1, 0)), (("play", -0.1),), likes="proud", where="hang"),
    #: L-ui-modernisation-10: the app's sleeping hang and its flip by the feet, played inside a hang as the one-handed hold is.
    "sloth": Activity("hang_sloth", (9.0, 20.0), _k((0, 1, 1, 0), (1, 1, 1, 0)), (("rest", -0.1),), likes="sleepy", where="hang"),
    "hang_by_feet": Activity("hang_feet", (7.0, 12.0), _k((0, 1, 1, 0), (1, 1, 1, 0)), (("play", -0.15),), likes="happy", where="hang"),
})
YIELD_TO_SIT = frozenset({"meditate", "lounge", "rest_head"})
#: The ones that only make sense in place: all of them (a trip is a different table).
IDLE_NAMES = tuple(ACTIVITIES)
#: How much likelier a perch-only act is on a window's top than its catalogue weight says (it is the only place it can happen).
PERCH_ACT_BOOST = 5.0
#: Base chance of each, before need, mood and repeat shape it. Quiet things are common.
BASE_WEIGHT = {
    "breathe": 9, "shift_weight": 8, "look_around": 8, "slow_blink": 8, "tail_flick": 7, "nod": 3, "shrug": 3,
    "stretch": 4, "yawn": 3, "glance_pointer": 5, "ponder": 4, "sway": 4, "wiggle": 3, "bounce": 2,
    "scan_horizon": 3, "little_dance": 2, "wave_idle": 2, "sit_down": 4, "doze": 2, "curl_up": 1, "pose_proud": 2,
    "peek_down": 3, "shake_off": 1, "crouch_watch": 3, "float_loop": 3, "lie_down": 2, "back_float": 1,
    "groom": 3, "scratch": 3, "snack": 3, "peer_at_cursor": 3, "pace": 2, "invent_game": 2, "tinker": 3, "dust_off": 2,
}


#: The acts `_from_catalogue` set from the table (props and extras register more later, with lengths of their own).
CATALOGUED: set[str] = set()
#: Acts that register later (the props', `props.register`) and still take the catalogue's mood, energy and day weights, so
#: tea is for the morning and supper for the evening on the desk as it is in the app (E5 c, INBOX 1692 d).
FACTORED: set[str] = set()


def _from_catalogue() -> None:
    """A3 (atlascat-1108): an act built on both sides takes its length and weight from the shared catalogue
    (`frontend/companion-catalogue.json`); an entry that covers several desk acts splits its weight among them.
    A missing file changes nothing."""
    names: dict[str, list[tuple[str, tuple[float, float], float]]] = {}
    for name, e in catalogue.by_desk_name().items():
        if name not in ACTIVITIES or e.get("app", {}).get("s") != "built":
            continue
        try:  # an entry without its numbers is skipped: a bad file leaves the built-ins
            span = (float(e["seconds"][0]), float(e["seconds"][1]))
            w = float(e["w"])
            e["energy"][2]
            e["id"]
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        names.setdefault(e["id"], []).append((name, span, w))
    for group in names.values():
        for name, span, w in group:
            # never shorter than the built-in minimum: a shorter play redraws faster than the 12 a second cap
            lo = max(span[0], ACTIVITIES[name].seconds[0])
            ACTIVITIES[name] = ACTIVITIES[name]._replace(seconds=(lo, max(lo, span[1])))
            BASE_WEIGHT[name] = w / len(group)
            CATALOGUED.add(name)


def phase_of(hour: int) -> str:
    """The part of the day (`phases` of the catalogue), "" without a catalogue."""
    for name, (a, b) in catalogue.load().get("phases", {}).items():
        if (a <= hour % 24 < b) if a < b else (hour % 24 >= a or hour % 24 < b):
            return name
    return ""


def catalogue_factor(name: str, mood: str, hour: int) -> float:
    """A5: what the catalogue's mood, energy and day weights make of an act now (1 for an act it does not list, and for the props' own). Energy
    is the part of the day's, none when sleepy and one more when happy or startled."""
    e = catalogue.by_desk_name().get(name) if name in CATALOGUED or name in FACTORED else None
    if e is None:
        return 1.0
    try:
        phase = phase_of(hour)
        energy = catalogue.load().get("energy_by_phase", {}).get(phase, 1)
        energy = 0 if mood == "sleepy" else min(2, energy + 1) if mood in ("happy", "startled") else energy
        return float(e.get("mood", {}).get(mood, 1.0) * e["energy"][energy] * e.get("day", {}).get(phase, 1.0))
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        return 1.0


def shift_every(name: str) -> tuple[float, float] | None:
    """How often the catalogue's pose-shifting beat of the act `name` falls (seconds), if it has one."""
    try:
        for b in catalogue.by_desk_name().get(name, {}).get("beats", []):
            if b.get("shifts"):
                return float(b["every"][0]), float(b["every"][1])
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        return None  # a malformed catalogue entry is no beat: the act keeps its built-in pose shifts
    return None


#: A4: a sit or a sleep that is not an act shifts by the beats of the catalogue entry it plays (a read's seat shift, a
#: nap's turn over), so neither holds one pose past 90 s.
STATE_BEATS = {"sit": "read_book", "sleep": "doze"}
_from_catalogue()


def mood_of(needs: dict[str, float], event: str, event_age: float, hour: int) -> str:
    """The mood: an event of the last `MOOD_FOR` seconds wins; else the strongest need."""
    if event and event_age < MOOD_FOR:
        return event
    if needs["rest"] > 0.65 or hour >= 23 or hour < 6:
        return "sleepy"
    if needs.get("novelty", 0.0) > 0.85:
        return "bored"
    if needs["curiosity"] > 0.6:
        return "curious"
    if needs["play"] > 0.6:
        return "happy"
    if needs["rest"] < 0.1 and needs["curiosity"] < 0.15 and needs["play"] < 0.15:
        return "bored"
    return "proud" if needs["play"] < 0.1 else "happy"


MICRO = ("breathe", "shift_weight", "slow_blink", "tail_flick")
#: Acts that ask for the person (they win when someone is here) and acts that are quiet (they win when they are away).
ATTENTION = frozenset({"wave_idle", "glance_pointer", "peer_at_cursor", "little_dance"})
QUIET = frozenset({"sit_down", "doze", "curl_up", "lie_down", "groom", "daydream", "stargaze"})
CHAIN_CHANCE = 0.45
#: Idle escalates with the seconds the person has been away (research B9, Agent idle levels 1 to 3): a look about,
#: then stretches and props, then a nap last. Each group is lifted in its own tier and held back before it.
IDLE_TIERS = (60.0, 180.0, 360.0)
TIER_LOOK = frozenset({"look_around", "scan_horizon", "peek_down", "ponder", "slow_blink"})
TIER_PROPS = frozenset({"stretch", "yawn", "groom", "scratch", "snack", "tinker", "invent_game", "dust_off", "pace"})
TIER_NAP = frozenset({"sit_down", "doze", "curl_up", "lie_down"})
#: (group, its tier, how far it is held back before that tier): a look about is never held, a nap most of all.
TIER_GROUPS = ((TIER_LOOK, 1, 1.0), (TIER_PROPS, 2, 0.75), (TIER_NAP, 3, 0.5))
TIER_LIFT = 2.0


def idle_tier(idle: float) -> int:
    """0 while they are about, then 1, 2, 3 as the time away passes each of `IDLE_TIERS`."""
    return sum(idle > t for t in IDLE_TIERS)


def tier_factor(name: str, idle: float) -> float:
    """What the idle tier does to an act's weight: lifted in its own tier, held back before it, plain after."""
    tier = idle_tier(idle)
    for group, level, hold in TIER_GROUPS:
        if name in group:
            return TIER_LIFT if tier == level else hold if tier < level else 1.0
    return 1.0


class Chain(NamedTuple):
    """A short run of acts that belong together (B4): started by its first act, with a mood that allows it."""

    steps: tuple[str, ...]
    moods: tuple[str, ...] = ()


CHAINS = (
    Chain(("stretch", "yawn", "sit_down")),
    Chain(("look_around", "ponder", "puzzle")),
    Chain(("tiptoe", "crouch_watch", "bounce"), ("curious", "happy")),
    Chain(("hum", "sway", "little_dance"), ("happy", "proud")),
    Chain(("sip_tea", "write_journal"), ("curious", "proud")),
    Chain(("scratch", "groom", "dust_off"), ()),
    Chain(("tinker", "invent_game"), ("bored", "curious", "happy")),
    # INBOX 1711: the small acts lead somewhere too (a sneeze shakes off into a groom, a tap of the foot looks for something to do, a hug winds down).
    Chain(("sneeze", "groom"), ()),
    Chain(("foot_tap", "look_around", "ponder"), ("bored", "curious")),
    Chain(("self_hug", "yawn", "sit_down"), ()),
    # INBOX 1710, 1711: a firefly leads to counting the stars, a wave to a look round, a rest to a stretch, a lounge to a nap on a card, a pace to a sigh, a sparkle to a toss of stars.
    Chain(("star_catch", "count_stars"), ("curious", "happy")),
    Chain(("wave_pointer", "look_around"), ()),
    Chain(("rest_head", "stretch", "yawn"), ()),
    Chain(("lounge", "card_nap"), ("sleepy",)),
    Chain(("dangle", "kick_legs"), ("happy",)),
    Chain(("pace", "sigh"), ()),
    Chain(("cast_sparkle", "toss_stars"), ("happy",)),
)


def curve(x: float, kind: str = "smooth") -> float:
    """A response curve from 0..1 to 0..1 (IAUS): slow-then-fast, fast-then-slow or an S."""
    x = min(max(x, 0.0), 1.0)
    return {"quad": x * x, "root": math.sqrt(x), "smooth": smooth(x)}[kind]


def utility(considerations: list[float]) -> float:
    """The product of the considerations (each 0..1) with the IAUS compensation, so many of them do not
    drag a good act to nothing: c' = c + (1 - c) * (1 - 1/n) * c."""
    n = max(1, len(considerations))
    mod = 1.0 - 1.0 / n
    out = 1.0
    for c in considerations:
        out *= c + (1.0 - c) * mod * c
    return out


class Mind:
    """Needs, mood and what it did lately."""

    def __init__(self, now: float = 0.0) -> None:
        self.needs = {"rest": 0.1, "curiosity": 0.2, "play": 0.2, "social": 0.2, "comfort": 0.15, "hunger": 0.1, "novelty": 0.2}
        self.event = ""
        self.event_at = -1e9
        self.done: dict[str, float] = {}
        self.at = now
        self.fidget_ready = now + FIDGET_FIRST
        #: The last few acts (no back-to-back repeat), seconds since the person last did anything and whether the
        #: pointer is near: the engine sets the last two before it asks for the next act.
        self.recent: list[str] = []
        self.idle = 0.0
        self.near = False
        #: The steps still to come of a running chain, and how many chains ran to the end.
        self.chain: list[str] = []
        self.chains_done = 0
        #: A4: when the running act next shifts its pose (a long act turns over or shifts its seat), and every how long.
        self.shift_at = math.inf
        self.shift_every: tuple[float, float] | None = None
        self.shifts = 0

    def tick(self, now: float, hour: int = 12) -> None:
        dt = min(max(now - self.at, 0.0), 30.0)
        self.at = now
        night = 2.0 if (hour >= 23 or hour < 6) else 1.0
        for k, full in NEED_FULL.items():
            self.needs[k] = min(1.0, self.needs.get(k, 0.2) + dt / full * (night if k == "rest" else 1.0))

    def mood(self, now: float, hour: int = 12) -> str:
        return mood_of(self.needs, self.event, now - self.event_at, hour)

    def feel(self, event: str, now: float) -> None:
        self.event, self.event_at = event, now

    def start_beats(self, name: str, now: float, rng: random.Random) -> None:
        """A4 (atlascat-1108): the act's catalogue beats that shift the pose are timed from its start, so a long act
        never holds one pose past its budget; an act with none draws nothing."""
        self.shift_every = shift_every(name)
        self.shift_at = now + rng.uniform(*self.shift_every) if self.shift_every else math.inf

    def shift_due(self, now: float, rng: random.Random) -> bool:
        """True once each time a pose shift falls due, and the next one is timed from it."""
        if self.shift_every is None or now < self.shift_at:
            return False
        self.shift_at = now + rng.uniform(*self.shift_every)
        self.shifts += 1
        return True

    def did(self, name: str, now: float) -> None:
        self.done[name] = now
        self.recent = [*self.recent[-5:], name]
        if name in FIDGETS:
            self.fidget_ready = now + FIDGET_GAP
        for need, delta in ACTIVITIES[name].feeds if name in ACTIVITIES else ():
            self.needs[need] = min(1.0, max(0.0, self.needs.get(need, 0.2) + delta))

    def weights(self, now: float, gait: str, hour: int = 12, where: str = "") -> list[tuple[str, float]]:
        mood = self.mood(now, hour)
        tired = mood == "sleepy" or self.needs["rest"] > 0.6
        out = []
        for name, act in ACTIVITIES.items():
            if act.gait not in ("any", gait) or (act.where and act.where != where):
                continue
            if name in FIDGETS and (now < self.fidget_ready or tired):
                continue  # a fidget is a rare, chosen act; a tired one does not
            if self.recent and name == self.recent[-1]:
                continue  # never the same act twice running, quiet ones included
            if now - self.done.get(name, -1e9) < NO_REPEAT and name not in MICRO:
                continue  # quiet micro things may recur (not back to back); the rest wait their turn
            #: on a window top the perch-only acts (legs over its edge) are the point of being there: a visit is short
            out.append((name, self._weight(name, act, mood, hour, now) * (PERCH_ACT_BOOST if act.where == "perch" else 1.0)))
        return out

    def _when(self, name: str, hour: int) -> float:
        """How well the hour and the rest suit the act: a quiet one at night or when tired, the rest by day."""
        night = hour >= 23 or hour < 6
        if name in QUIET or name in TIER_NAP:
            return 1.0 if night or self.needs["rest"] >= 0.3 else 0.25
        return 0.55 if night else 1.0

    def _seen(self, name: str, act: Activity) -> float:
        """What the person is doing suits the act: those that ask for company when they are here, quiet when away."""
        if name in ATTENTION or any(n == "social" for n, _d in act.feeds):
            return 0.25 + 0.55 * curve(1.0 - self.idle / 120.0, "root") + (0.2 if self.near else 0.0)
        return 0.4 + 0.6 * curve(self.idle / 180.0, "quad") if name in QUIET else 0.8

    def _weight(self, name: str, act: Activity, mood: str, hour: int, now: float = 0.0) -> float:
        """Base weight times the utility of its considerations (research B1): how much it is wanted (a need,
        on a curve), how well the mood and hour suit it, what the person is doing, and how lately it was done."""
        fed = [self.needs.get(n, 0.2) for n, d in act.feeds if d < 0]
        want = 0.2 + 0.8 * curve(max(fed), "quad") if fed else 0.5
        fits = 1.0 if act.likes == mood else (0.6 if not act.likes else 0.4)
        ago = now - self.done.get(name, -1e9)
        fresh = 0.5 + 0.5 * curve(ago / 30.0) if name in MICRO else 0.3 + 0.7 * curve(ago / (NO_REPEAT * 2.0))
        w = float(BASE_WEIGHT.get(name, 2)) * 4.0 * utility([want, fits, self._when(name, hour), self._seen(name, act), fresh])
        w *= tier_factor(name, self.idle) * catalogue_factor(name, mood, hour)
        if name in FIDGETS and (mood in ("proud", "bored") or self.needs["play"] < 0.15):
            w *= 0.4  # content, it has less to burn off
        return w

    def pick(self, rng: random.Random, now: float, gait: str, hour: int = 12, where: str = "") -> str:
        table = self.weights(now, gait, hour, where)
        nxt = self._next_in_chain(now, gait, where)
        if nxt:
            return nxt
        roll = rng.random() * sum(w for _n, w in table)
        for name, w in table:
            roll -= w
            if roll < 0:
                self._begin_chain(name, rng, now, hour)
                return name
        return "breathe"

    def _next_in_chain(self, now: float, gait: str, where: str) -> str:
        """The next step of a running chain, if it can still be done here; a step that cannot ends the chain."""
        if not self.chain:
            return ""
        step = self.chain[0]
        act = ACTIVITIES.get(step)
        if act is None or act.gait not in ("any", gait) or (act.where and act.where != where) or step == (self.recent[-1] if self.recent else ""):
            self.chain = []
            return ""
        if step not in MICRO and now - self.done.get(step, -1e9) < NO_REPEAT:
            self.chain = []  # a step done lately waits its turn like any act: the chain ends rather than repeat it
            return ""
        self.chain.pop(0)
        if not self.chain:
            self.chains_done += 1
        return step

    def _begin_chain(self, name: str, rng: random.Random, now: float, hour: int) -> None:
        for c in CHAINS:
            if c.steps[0] == name and all(s in ACTIVITIES for s in c.steps) and (not c.moods or self.mood(now, hour) in c.moods):
                if rng.random() < CHAIN_CHANCE:
                    self.chain = list(c.steps[1:])
                return


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
    #: The vertical chain (a landing or a hop throws the tail down, then up): softer, so a hop is no whip.
    LIFT_KICK = 0.04
    LIFT_MAX = 12.0

    def __init__(self) -> None:
        self.pos = [0.0] * self.LINKS
        self.vel = [0.0] * self.LINKS
        self.last_v = 0.0
        self.lift_pos = [0.0] * self.LINKS
        self.lift_vel = [0.0] * self.LINKS
        self.last_vy = 0.0

    @property
    def tip(self) -> float:
        return self.pos[-1]

    @property
    def lift(self) -> float:
        """The tip's vertical offset in px (y grows down): positive hangs below the root, as after a landing's stop."""
        return self.lift_pos[-1]

    def settled(self) -> bool:
        return abs(self.pos[-1]) < 0.6 and abs(self.vel[-1]) < 4.0 and abs(self.lift_pos[-1]) < 0.6 and abs(self.lift_vel[-1]) < 4.0

    def step(self, dt: float, body_vx: float, body_vy: float = 0.0) -> None:
        """Advance by `dt` seconds with the body moving at (`body_vx`, `body_vy`) px/s (before this step)."""
        if dt <= 0:
            return
        accel = (body_vx - self.last_v) / dt
        lift_accel = (body_vy - self.last_vy) / dt
        self.last_v, self.last_vy = body_vx, body_vy
        n = max(1, int(math.ceil(dt / 0.02)))
        h = dt / n
        for pos, vel, a, top in ((self.pos, self.vel, accel * self.KICK, self.MAX), (self.lift_pos, self.lift_vel, lift_accel * self.LIFT_KICK, self.LIFT_MAX)):
            self._chain(pos, vel, a, top, h, n)

    def _chain(self, pos: list[float], vel: list[float], kick: float, top: float, h: float, n: int) -> None:
        stiff, damp = self.STIFF, self.DAMP
        kicks = [kick * (1 + i) for i in range(self.LINKS)]  # the same product every pass: once per link
        links, low = range(self.LINKS), -top
        for _ in range(n):
            prev = 0.0
            for i in links:
                pi, vi = pos[i], vel[i]  # read once: the same arithmetic in the same order, so the same floats
                v = vi + (stiff * (prev - pi) - damp * vi - kicks[i]) * h
                vel[i] = v
                p = pi + v * h
                prev = pos[i] = top if p > top else low if p < low else p

    def reset(self) -> None:
        self.pos, self.vel, self.last_v = [0.0] * self.LINKS, [0.0] * self.LINKS, 0.0
        self.lift_pos, self.lift_vel, self.last_vy = [0.0] * self.LINKS, [0.0] * self.LINKS, 0.0


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
#: The hem rises and settles with the breath (INBOX 1683 a, 1696 w): px of the shipped frame at the tip, each strand a beat
#: after the last (`FLOW_BREATH_LAG` of a cycle across the width), the pose's reach scaling it (a sleeper's is half).
FLOW_BREATH = 1.5
FLOW_BREATH_LAG = 0.22
#: Arrangements by pose (INBOX 1683 B1, B3: "they dont even ahve different variations or change based on body
#: position"). The shipped frames carry one lower body per pose, so each strand also holds an arrangement of its
#: own, a new one every `FLOW_ARR_HOLD` seconds (its own length per strand) reached by an eased move over
#: `FLOW_ARR_EASE` seconds: its tip's lean and its rise, px of the shipped frame. Together with the sway the tip
#: stays under `FLOW_TIP * FLOW_ARR_SWAY + FLOW_ARR_TIP` (2.65 px, under 4 degrees off the torso at the hem: INBOX 615 and 619).
FLOW_ARR_TIP = 1.0
#: With an arrangement the sway takes this share of its reach, so the two together stay inside the torso's 4 degrees.
FLOW_ARR_SWAY = 0.75
FLOW_ARR_RISE = 0.4
FLOW_ARR_HOLD = (5.0, 9.0)
FLOW_ARR_EASE = 2.4
#: What a pose does to the streams: [reach, speed] by the start of the frame's name (the first match). Asleep they
#: are small and slow, glad or thrown they are wide and quick; both move on the way to the next pose over
#: `FLOW_POSE_EASE` seconds, so a change of pose is never a step.
FLOW_POSE = (("sleep", 0.5, 0.6), ("sit", 0.8, 0.85), ("hang", 0.95, 1.1), ("dangle", 0.95, 1.1), ("kick", 1.0, 1.7), ("meditate", 0.5, 0.55), ("wave", 1.0, 1.3), ("walk", 1.0, 1.35), ("hop", 1.0, 1.6), ("fall", 1.0, 1.6), ("land", 1.0, 1.2), ("idle", 0.9, 0.95))
FLOW_POSE_EASE = 0.8
#: What the figure is doing, over its frame (atlascat-1108 C4, the in-app `lower:*` states; INBOX 1696 z: "the lower body
#: doesnt change at all"): [reach, speed, tip lean px, rise px] by name, the engine's `_lower_state` picking it. A
#: state names the lower body's own sway and offset: it takes the place of the frame's `FLOW_POSE` row while it lasts, and
#: all four ease together over `FLOW_POSE_EASE`. The two offsets are small (the join with the torso allows 4 degrees,
#: INBOX 615 and 619): `glide` leans back from the way it goes (the engine signs it).
FLOW_LOWER = {
    "lie": (0.55, 0.55, 0.0, 0.5), "think": (0.7, 0.8, 0.5, 0.0), "sad": (0.45, 0.5, 0.0, -0.5),
    "startle": (1.0, 1.7, 0.0, 0.8), "lounge": (0.85, 0.7, 0.4, 0.2), "glide": (1.0, 1.4, 0.8, 0.3),
    # atlascat-1108 C5: a gust on a fast glide, tucked under cross-legged, a slow calm ripple, an excited flutter, spread
    # flat after a long sit, a playful kick of the hem, a spiral after a twirl, heavy when tired.
    "billow": (1.0, 1.9, 0.9, 0.9), "coil": (0.6, 0.7, 0.3, -0.3), "ripple_calm": (0.8, 0.5, 0.0, 0.2),
    "flutter": (0.9, 2.0, 0.0, 0.5), "pool": (0.5, 0.5, 0.6, -0.6), "hem_kick": (1.0, 1.8, 0.7, 0.8),
    "spiral": (1.0, 1.6, 0.8, 0.0), "heavy": (0.4, 0.4, 0.0, -0.8),
}
#: A sit this long is a lounge (the lower body spreads and slackens).
LOUNGE_AFTER = 6.0
#: Acts that are the figure thinking.
THINK_ACTS = frozenset({"ponder", "puzzle", "tinker"})
#: What the lower body spells beyond the base states (`Engine._lower_spell`): acts that sit it cross-legged, acts of
#: a glad figure that kick the hem, acts that twirl (a spiral that unwinds `SPIRAL_FOR` s after), a sit this long
#: spread flat, a calm stand's ripple (`RIPPLE_EVERY` s cycle, the last `RIPPLE_FOR` s of its first `RIPPLE_AT`), an
#: excited reaction's flutter, and the speed that makes a glide a gust.
COIL_ACTS = frozenset({"invent_game", "groom", "snack"})
HEM_ACTS = frozenset({"little_dance", "bounce", "wiggle"})
TWIRL_ACTS = frozenset({"flip_twirl", "float_loop"})
SPIRAL_FOR = 2.5
POOL_AFTER = 40.0
RIPPLE_EVERY, RIPPLE_AT, RIPPLE_FOR = 40.0, 24.0, 8.0
FLUTTER_FOR = 4.0
BILLOW_SPEED = 1.2  # times the walking speed


#: The tail as a layer (atlascat-1108 C1, INBOX 1696 w: "the tail is framed in that it isnt a smooth animation"): the idle
#: frames carry the tail's beat baked in at 6 a second, so the tail is drawn on its own, every display frame, over the body.
#: The poses are the in-app rig's (`ATLAS_TAIL_ACTS`): [curl rad root to tip (+ round and down), amp rad of the wave at the
#: tip, period s, k rad of phase root to tip]. A pose change eases over `TAIL_EASE` seconds, so no pose is ever a step.
#: Two more numbers on the end (the rig's `tip` and `env`): an extra bend over the last third (a hook, radians), and the
#: exponent of the wave's envelope along the tail (1.5 the whole tail; high, only the tip moves).
TAIL_POSES = {
    "sway": (0.15, 0.34, 3.9, 3.4, 0.0, 1.5), "curl": (-1.3, 0.19, 4.6, 2.4, 0.0, 1.5), "wrap": (1.1, 0.17, 4.9, 2.2, 0.0, 1.5),
    "wag": (-0.4, 0.46, 0.66, 2.4, 0.0, 1.5), "droop": (0.6, 0.11, 5.6, 1.8, 0.0, 1.5), "stiff": (-0.12, 0.08, 2.1, 2.0, 0.0, 1.5),
    # atlascat-1108 C2 and C3: a question-mark hook, the tip coiled (round a prop), a slow thump, a shiver, tucked in, a
    # figure of eight, a tip twitch (only the last fifth moves), level for balance, curled under the head.
    "hook": (-0.9, 0.1, 4.4, 2.0, 1.4, 1.5), "coil_hold": (1.3, 0.06, 6.0, 1.6, 1.2, 1.5), "thump": (0.3, 0.3, 1.4, 1.2, 0.0, 1.5),
    "shiver": (0.0, 0.08, 0.12, 5.0, 0.0, 1.5), "tuck": (1.6, 0.05, 6.0, 1.6, 0.4, 1.5), "loop8": (-0.2, 0.55, 2.2, 2.6, 0.0, 1.5),
    "tip_twitch": (0.25, 0.2, 0.9, 3.4, 0.0, 6.0), "balance": (0.0, 0.06, 2.6, 2.0, 0.0, 1.5), "pillow": (1.8, 0.05, 7.0, 1.6, 0.9, 1.5),
}
#: The poses a state picks from, by weight (the rig's `ATLAS_TAIL_BY_STATE`), and the mood's own (a glad one wags, a tired
#: or bored one lets it droop, a startled one holds it stiff).
#: A figure on a window's top balances (`perch`), one in a long sit coils its tip (`lounge`, the in-app `coil_hold`, with no
#: prop to hold yet).
TAIL_BY_STATE = {
    "stand": (("sway", 3.0), ("curl", 2.0), ("wrap", 1.4), ("tip_twitch", 1.0)), "sit": (("wrap", 2.0), ("sway", 1.0), ("curl", 1.0)),
    "perch": (("balance", 3.0), ("sway", 1.0)), "lounge": (("coil_hold", 2.0), ("wrap", 1.0)),
}
#: A name is a fixed pose; a list is a weighted pick. Impatient (bored) it thumps or lets it droop, curious it hooks it, sad
#: (the reaction's face) it tucks it in, playful (glad with the pointer near or a touch just now) it draws a figure of eight.
TAIL_BY_MOOD = {
    "happy": "wag", "proud": "wag", "sleepy": "droop", "bored": (("droop", 1.0), ("thump", 2.0)), "startled": "stiff",
    "curious": (("hook", 3.0), ("curl", 1.0)), "sad": (("tuck", 2.0), ("droop", 1.0)), "playful": (("loop8", 3.0), ("wag", 1.0)),
}
#: The body frames that carry the layered tail (the stand family and the sit; `sprites.TAIL_SOURCE` has the same names).
TAIL_FRAMES = ("stand", "idle", "blink", "look", "sit", "sitblink")
TAIL_HOLD = (3.0, 6.0)
TAIL_EASE = 0.9
TAIL_STEPS = 6  # control points along the tail, root excluded
TAIL_Q = 8.0  # steps a px of the shipped frame in a view
#: The tail's length in px of the shipped frame, and how much of a pose's own shape shows (a mesh shear, not a rig).
TAIL_LEN = 96.0
TAIL_REACH = 0.85


def tail_bend(s: float, p: tuple[float, ...], ph: float, ph2: float) -> float:
    """The angle the tail has turned through at `s` (0 root, 1 tip): the rig's `atlasTailBend` without its third ripple."""
    curl, amp, _period, k, tip, env = p
    e = s ** env
    hook = tip * max(0.0, (s - 0.62) / 0.38) ** 2
    return hook + curl * s * s + amp * e * math.sin(ph - k * s) + max(0.13, 0.35 * amp) * e * math.sin(ph2 - 1.7 * k * s + 0.7)


def tail_points(p: tuple[float, ...], ph: float, ph2: float, wave: bool = True) -> list[tuple[float, float]]:
    """The tail's axis, `TAIL_STEPS` points from the root (in tail lengths, x along the way it points, y down): the bend
    integrated along it."""
    x = y = 0.0
    out = []
    for i in range(1, TAIL_STEPS + 1):
        t = (i - 0.5) / TAIL_STEPS
        a = tail_bend(t, p, ph, ph2) if wave else p[0] * t * t
        x, y = x + math.cos(a) / TAIL_STEPS, y + math.sin(a) / TAIL_STEPS
        out.append((x, y))
    return out


class TailLayer:
    """The tail's own motion at the display rate: a pose picked by the state and mood (its own seeded stream, so the
    engine's other choices never shift), eased into from the last over `TAIL_EASE` seconds, a wave whose phase runs on
    with the eased period. `view` is what the picture needs: where each control point sits against the rest shape, in
    `TAIL_Q` steps of a px, so the sprite cache can key on it."""

    def __init__(self, seed: int = 1696) -> None:
        self.rng = random.Random(seed)
        self.name = "sway"
        self.p = list(TAIL_POSES["sway"])
        self.ph = self.rng.random() * math.tau
        self.ph2 = self.rng.random() * math.tau
        self.until = 0.0
        self.seen: float | None = None
        #: The shape the shipped frames carry (a plain curl of the sway's, no wave): the layer moves the tail from it.
        self.rest = tail_points((TAIL_POSES["sway"][0], 0.0, 1.0, 1.0, 0.0, 1.5), 0.0, 0.0, wave=False)

    def choose(self, state: str, mood: str, now: float) -> None:
        """Pick the next pose when the hold is over: the mood's if it has one, else a weighted pick of the state's."""
        if now < self.until:
            return
        self.until = now + self.rng.uniform(*TAIL_HOLD)
        if mood == "startled":  # a start holds it stiff, then it shivers, and so on while the mood lasts
            self.name = "shiver" if self.name == "stiff" else "stiff"
        elif mood == "sleepy" and state in ("sit", "lounge"):
            self.name = "pillow"  # drowsy and settled: curled under the head
        elif mood in TAIL_BY_MOOD and not (state in ("perch", "lounge") and mood in ("bored", "curious", "happy", "proud")):
            pick = TAIL_BY_MOOD[mood]
            self.name = pick if isinstance(pick, str) else self._weighted(pick)
        else:
            self.name = self._weighted(TAIL_BY_STATE.get(state, TAIL_BY_STATE["stand"]))

    def _weighted(self, table: tuple[tuple[str, float], ...]) -> str:
        names, weights = zip(*table)
        return self.rng.choices(names, weights)[0]

    def view(self, now: float, calm: bool = False) -> tuple[int, ...]:
        dt = 0.0 if self.seen is None else min(0.25, max(0.0, now - self.seen))
        self.seen = now
        goal = TAIL_POSES[self.name]
        k = 1.0 - math.exp(-dt / TAIL_EASE)
        for i in range(6):
            self.p[i] += (goal[i] - self.p[i]) * k
        slow = FLOW_CALM_SLOW if calm else 1.0
        period = max(0.1, self.p[2]) * slow
        self.ph = (self.ph + math.tau * dt / period) % math.tau
        self.ph2 = (self.ph2 + math.tau * dt / (period * 0.62)) % math.tau
        pose = tuple(self.p)
        pts = tail_points(pose, self.ph, self.ph2)
        amp = FLOW_CALM_AMP if calm else 1.0
        out: list[int] = []
        for (x, y), (rx, ry) in zip(pts, self.rest):
            out += [round((x - rx) * TAIL_LEN * TAIL_REACH * amp * TAIL_Q), round((y - ry) * TAIL_LEN * TAIL_REACH * amp * TAIL_Q)]
        return tuple(out)


def _frac(x: float) -> float:
    return x - math.floor(x)



@functools.lru_cache(maxsize=65536)
def _arr_pick(seed: int, i: int, k: int) -> tuple[float, float]:
    """One strand's arrangement for hold number `k`: a pure function of its arguments, so seeding a generator
    for it on every frame (354,000 seeds in a simulated hour) is a cost the cache removes."""
    rng = random.Random(seed * 1000003 + i * 7919 + k)
    return rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0)


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
        #: Each strand's (stiffness, damping, share of the throw), the same three numbers every wake: once, here.
        self.springs = [
            (k, 2.0 * FLOW_DAMP * math.sqrt(k), 0.7 + 0.6 * _frac(i * 0.43 + 0.1)) for i, k in enumerate(self.stiff)
        ]
        self.last_v = (0.0, 0.0)
        self.seed = seed
        self.hold = [FLOW_ARR_HOLD[0] + (FLOW_ARR_HOLD[1] - FLOW_ARR_HOLD[0]) * _frac(i * 0.618 + 0.29) for i in range(FLOW_BANDS)]
        # The pose's reach and speed, eased; `skew` is the time the speed has added, so a change of speed is no jump.
        self.k_reach, self.k_speed, self.skew, self.seen = 1.0, 1.0, 0.0, None
        self.k_tip, self.k_rise = 0.0, 0.0  # the lower state's offsets, eased (`FLOW_LOWER`)

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
        #: A flow with nothing pushing it and every spring below 1e-200 is at rest: the damped springs fall
        #: to denormals and stall there (1.5e-323 after 6,000 s), never to 0.0, and no picture can tell 1e-200
        #: from zero (`view` rounds to 1/`FLOW_Q` px). Snapped to zero and left alone, a settled wake is free
        #: (70k wakes: 1 s to 0.1 s) and every output is the same.
        if not (vx or vy or ax or ay) and max(map(abs, (x for row in (*self.pos, *self.vel) for x in row))) < 1e-200:
            for row in (*self.pos, *self.vel):
                row[0] = row[1] = 0.0
            return
        n = max(1, int(math.ceil(dt / 0.02)))
        h = dt / n
        hi, lo = FLOW_MAX, -FLOW_MAX
        steps = range(n)
        for i, (k, c, gain) in enumerate(self.springs):
            for axis, v, a in ((0, vx, ax), (1, vy, ay)):
                rest = -v * FLOW_STREAM * gain
                kick = a * FLOW_KICK * gain  # the same every pass
                p, q = self.pos[i][axis], self.vel[i][axis]
                for _ in steps:
                    q += (k * (rest - p) - c * q - kick) * h
                    p += q * h
                    p = hi if p > hi else lo if p < lo else p
                self.pos[i][axis], self.vel[i][axis] = p, q

    def arrangement(self, i: int, t: float) -> tuple[float, float]:
        """Strand `i`'s arrangement at `t` (each -1..1): the one it holds, eased into the next over the last
        `FLOW_ARR_EASE` seconds of its hold. A pure function of `t`, so it is the same however often it is read."""
        n, u = divmod(t / self.hold[i], 1.0)
        span = FLOW_ARR_EASE / self.hold[i]
        e = min(1.0, max(0.0, (u - (1.0 - span)) / span))
        e = e * e * (3.0 - 2.0 * e)

        a, b = _arr_pick(self.seed, i, int(n)), _arr_pick(self.seed, i, int(n) + 1)
        return a[0] + (b[0] - a[0]) * e, a[1] + (b[1] - a[1]) * e

    def pose(self, frame: str, now: float, lower: str = "", side: float = 1.0) -> None:
        """Ease the reach and speed toward the frame's pose and advance the clock by the speed (`FLOW_POSE`); a
        `lower` state (`FLOW_LOWER`) takes its place, with its two offsets (the tip's lean signed by `side`)."""
        reach, speed = next(((r, s) for key, r, s in FLOW_POSE if frame.startswith(key)), (1.0, 1.0))
        tip, rise = 0.0, 0.0
        if lower in FLOW_LOWER:
            reach, speed, tip, rise = FLOW_LOWER[lower]
            tip *= side
        dt = 0.0 if self.seen is None else min(0.25, max(0.0, now - self.seen))
        self.seen = now
        k = 1.0 - math.exp(-dt / FLOW_POSE_EASE)
        self.k_reach += (reach - self.k_reach) * k
        self.k_speed += (speed - self.k_speed) * k
        self.k_tip += (tip - self.k_tip) * k
        self.k_rise += (rise - self.k_rise) * k
        self.skew += (self.k_speed - 1.0) * dt

    @staticmethod
    def breath_drop(i: int, breath: float | None, reach: float, calm: bool) -> float:
        """Strand `i`'s rise with the breath, px (none without a phase): `FLOW_BREATH` scaled by the pose's reach."""
        if breath is None:
            return 0.0
        return FLOW_BREATH * reach * (FLOW_CALM_AMP if calm else 1.0) * wisps.lift(breath, FLOW_BREATH_LAG * i / (FLOW_BANDS - 1))

    def settled(self) -> bool:
        return all(abs(p[0]) < 0.3 and abs(p[1]) < 0.3 and abs(v[0]) < 2.0 and abs(v[1]) < 2.0 for p, v in zip(self.pos, self.vel))

    def view(self, t: float, calm: bool = False, frame: str = "", lower: str = "", side: float = 1.0, breath: float | None = None) -> tuple[int, ...]:
        """Per strand `(tip dx, middle dx, tip dy, sparkle sin, sparkle cos)` in `FLOW_Q` steps (the sparkle in
        tenths), the follow-through folded in: what the warp needs and nothing else. With a `frame` the pose's
        reach, speed and the strand's arrangement apply (`pose`, `arrangement`); without one, the bare flow. `breath` is
        the body's breath phase (`wisps.phase`), under which the hem lifts and settles; None, none."""
        if frame:
            self.pose(frame, t, lower, side)
        t = t + self.t0 + (self.skew if frame else 0.0)
        reach = self.k_reach if frame else 1.0
        out: list[int] = []
        for i in range(FLOW_BANDS):
            fx, fy = self.pos[i]
            ax, ay = self.arrangement(i, t) if frame else (0.0, 0.0)
            ax, ay = ax * reach * FLOW_ARR_TIP * (FLOW_CALM_AMP if calm else 1.0) + (self.k_tip if frame else 0.0), ay * reach * FLOW_ARR_RISE * (FLOW_CALM_AMP if calm else 1.0) + (self.k_rise if frame else 0.0)
            tip = max(-FLOW_MAX, min(FLOW_MAX, self.sway(i, t, calm) * reach * (FLOW_ARR_SWAY if frame else 1.0) + ax + fx))
            mid = max(-FLOW_MAX, min(FLOW_MAX, self.sway(i, t - 0.9, calm) * reach * (FLOW_ARR_SWAY if frame else 1.0) * (1 - FLOW_MID) + ax * 0.6 + fx * 0.5))
            drop = self.rise(i, t, calm) * reach + ay + fy
            drop += self.breath_drop(i, breath if frame else None, reach, calm)
            w = math.tau * t / (self.glint_periods[i] * (FLOW_CALM_SLOW if calm else 1.0)) + i * 1.3
            out += [round(tip * FLOW_Q), round(mid * FLOW_Q), round(drop * FLOW_Q), round(math.sin(w) * 10), round(math.cos(w) * 10)]
        return tuple(out)
