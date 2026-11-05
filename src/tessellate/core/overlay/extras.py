"""The desk figure's own life beyond the roaming engine (INBOX 1683 asks M4 to M7, B9 quality): the small acts it
does while it stands (a prop act, a plain one), a face that changes with them, the way it answers the pointer (a
pat, a rub, a poke by mood, a flip, a flinch from a fast swipe, a warm look when hovered) and the way it answers
what happens on the screen (a window opening or closing, the foreground app changing, the person coming back, the
hour, a download, the battery).

It is one object per engine (`Engine.ex`) so the engine's own file stays about moving: the engine asks it for the
prop and the face to draw (`view`), for how soon to look again (`wake_ms`) and hands it the pointer (`pointer`) and
the screen's events (`react`). It draws on its own random stream, so the engine's other choices do not shift for a
seed, and everything is a function of the clock the engine is given: deterministic, no Win32.
"""

from __future__ import annotations

import math
import random
from collections import deque
from typing import Any, NamedTuple

from . import behaviour as bh
from . import faces, props

#: In-place acts while it stands: one every this many seconds, in the mind's own weighing (`mind.pick`).
LIFE_EVERY = (28.0, 80.0)
MIN_WAKE_MS = 16
#: The pointer is watched at this pace while it is near the figure (a gesture needs 15 samples a second).
WATCH_MS = 60
WATCH_REACH = 3.0  # box widths
#: ... and for this long after it last moved (a hover has to be seen as still, a rub as it begins).
WATCH_FOR = 1.0
SAMPLE_KEEP = 1.6
#: Gesture thresholds, logical px (scaled by the figure's size) and seconds.
PAT_DIP, PAT_REVERSALS, PAT_WINDOW, HEAD_ZONE = 7.0, 2, 1.0, 0.42
RUB_SWING, RUB_REVERSALS, RUB_WINDOW, RUB_FLAT = 9.0, 3, 1.4, 0.7
POKE_SPEED, POKE_REST, POKE_WINDOW = 800.0, 260.0, 0.4
SWIPE_SPEED, FLINCH_REACH = 1500.0, 150.0
HOVER_FOR, HOVER_STILL = 1.2, 80.0
#: States a reaction may break into, and the few more a touch may.
SCREEN_FREE = ("stand", "act", "notice", "wave", "land")
TOUCH_FREE = (*SCREEN_FREE, "sit", "sleep", "startle")
FACE_STATES = ("stand", "act", "notice", "startle", "wave", "land", "sit")


class Reaction(NamedTuple):
    #: The act it plays ("" for a face alone), the face it wears and for how long, the mood it leaves.
    act: str
    face: str
    seconds: float
    feel: str = ""
    cooldown: float = 6.0
    touch: bool = False


REACTIONS: dict[str, Reaction] = {
    # the pointer
    "pat": Reaction("pat_happy", "joy", 2.2, "happy", 3.0, True),
    "rub": Reaction("rub_purr", "content", 3.4, "happy", 6.0, True),
    "poke_giggle": Reaction("poke_giggle", "smile", 1.6, "happy", 4.0, True),
    "poke_miffed": Reaction("poke_miffed", "miffed", 2.0, "startled", 4.0, True),
    "poke_curious": Reaction("poke_curious", "curious", 1.8, "", 4.0, True),
    "flip": Reaction("flip_twirl", "joy", 1.6, "happy", 5.0, True),
    "flinch": Reaction("flinch", "worried", 1.2, "startled", 5.0, True),
    "hover": Reaction("", "smile", 3.0, "happy", 25.0, True),
    # the screen
    "window_opened": Reaction("glance_window", "curious", 2.0, "", 20.0),
    "window_closed": Reaction("relief", "content", 1.8, "", 30.0),
    "app_switched": Reaction("glance_screen", "curious", 1.4, "", 45.0),
    "idle_return": Reaction("welcome_back", "smile", 2.2, "happy", 60.0),
    "hour_chime": Reaction("chime_nod", "smile", 2.0, "", 3000.0),
    "battery_low": Reaction("shiver", "worried", 3.0, "startled", 600.0),
    "download_done": Reaction("cheer", "joy", 2.0, "happy", 15.0),
    "toast": Reaction("perk_up", "surprised", 1.6, "", 20.0),
}
#: A poke by mood, as the app's: a happy one giggles, a tired or cross one is miffed, the rest are curious.
POKE_BY_MOOD = {"happy": "poke_giggle", "proud": "poke_giggle", "sleepy": "poke_miffed", "startled": "poke_miffed", "bored": "poke_curious", "curious": "poke_curious"}


def _k(*rows: tuple[float, float, float, float]) -> bh.Keys:
    return rows


_TURN2 = _k((0, 1, 1, 0), (0.12, 1, 1.1, 0), (0.3, 0.14, 1.1, 0), (0.45, 1, 1.12, 0), (0.6, 0.14, 1.1, 0), (0.75, 1, 1.05, 0), (0.9, 1.03, 0.9, 0), (1, 1, 1, 0))
#: Acts only a reaction plays (`where` "react" keeps them out of the mind's own choice).
REACT_ACTS: dict[str, bh.Activity] = {
    "pat_happy": bh.Activity("stand", (1.8, 2.2), _k((0, 1, 1, 0), (0.15, 1.02, 0.9, 0.02), (0.3, 1, 1.03, 0), (0.5, 1.02, 0.92, 0.02), (0.7, 1, 1.02, 0), (1, 1, 1, 0)), (("play", -0.2),), where="react"),
    "rub_purr": bh.Activity("stand", (2.8, 3.6), _k((0, 1, 1, 0), (0.2, 1, 0.97, 0.05), (0.45, 1, 0.97, -0.05), (0.7, 1, 0.97, 0.05), (1, 1, 1, 0)), (("play", -0.15), ("rest", -0.05)), where="react"),
    "poke_giggle": bh.Activity("hop", (1.0, 1.4), _k((0, 1, 1, 0), (0.2, 1.04, 0.86, 0), (0.45, 0.96, 1.12, 0), (0.7, 1.03, 0.9, 0), (1, 1, 1, 0)), (("play", -0.2),), where="react"),
    "poke_miffed": bh.Activity("stand", (1.2, 1.6), _k((0, 1, 1, 0), (0.15, 1, 1.02, 0.06), (0.3, 1, 1.02, -0.06), (0.5, 1, 1.02, 0.04), (0.7, 1, 1, -0.02), (1, 1, 1, 0)), (), where="react"),
    "poke_curious": bh.Activity("look", (1.5, 2.0), _k((0, 1, 1, 0), (0.25, 0.97, 1.02, 0.04), (0.8, 0.97, 1.02, 0.04), (1, 1, 1, 0)), (("curiosity", -0.1),), where="react"),
    "flip_twirl": bh.Activity(((0, "hop"), (0.85, "land")), (1.2, 1.5), _TURN2, (("play", -0.4),), turns=(0.3, 0.6), where="react"),
    "flinch": bh.Activity("look", (0.9, 1.2), _k((0, 1, 1, 0), (0.12, 0.96, 1.05, -0.07), (0.7, 0.97, 1.03, -0.05), (1, 1, 1, 0)), (), where="react"),
    "glance_window": bh.Activity("look", (1.6, 2.2), _k((0, 1, 1, 0), (0.25, 0.97, 1.02, 0.04), (0.85, 0.97, 1.02, 0.04), (1, 1, 1, 0)), (("curiosity", -0.1),), turns=(0.5,), where="react"),
    "relief": bh.Activity("stand", (1.6, 2.0), _k((0, 1, 1, 0), (0.3, 1.01, 1.03, 0), (0.6, 1, 0.98, 0), (1, 1, 1, 0)), (("rest", -0.05),), where="react"),
    "glance_screen": bh.Activity("look", (1.1, 1.5), _k((0, 1, 1, 0), (0.3, 0.98, 1.01, 0.04), (0.8, 0.98, 1.01, 0.04), (1, 1, 1, 0)), (), where="react"),
    "welcome_back": bh.Activity("wave", (1.8, 2.4), _k((0, 1, 1, 0), (0.2, 1, 1.02, 0.02), (0.8, 1, 1.02, 0.02), (1, 1, 1, 0)), (("play", -0.1),), where="react"),
    "chime_nod": bh.Activity("stand", (1.6, 2.0), _k((0, 1, 1, 0), (0.25, 1.01, 0.95, 0.02), (0.5, 1, 1, 0), (0.7, 1.01, 0.97, 0.02), (1, 1, 1, 0)), (), where="react"),
    "shiver": bh.Activity("stand", (2.4, 3.0), _k((0, 1, 1, 0), (0.1, 1, 0.98, 0.05), (0.2, 1, 1, -0.05), (0.3, 1, 0.98, 0.05), (0.4, 1, 1, -0.05), (0.55, 1, 0.98, 0.04), (0.7, 1, 1, -0.03), (1, 1, 1, 0)), (), where="react"),
    "cheer": bh.Activity("hop", (1.6, 2.2), _k((0, 1, 1, 0), (0.15, 1.04, 0.86, 0), (0.3, 0.96, 1.12, 0), (0.5, 1.04, 0.88, 0), (0.65, 0.96, 1.12, 0), (0.85, 1.02, 0.94, 0), (1, 1, 1, 0)), (("play", -0.3),), where="react"),
    "perk_up": bh.Activity("look", (1.2, 1.6), _k((0, 1, 1, 0), (0.15, 0.97, 1.06, 0.02), (0.8, 0.98, 1.03, 0.02), (1, 1, 1, 0)), (), where="react"),
}
_registered = False


def register() -> None:
    """Add the prop and the plain acts and the reactions' own to the mind's tables, once."""
    global _registered
    if _registered:
        return
    _registered = True
    props.register()
    for name, act in REACT_ACTS.items():
        bh.ACTIVITIES[name] = act
        bh.AMPLITUDE[name] = bh._amplitude(act.keys)
    for r in REACTIONS.values():
        if r.act:
            faces.ACT_FACES[r.act] = r.face


class Pointer:
    """A classifier of the pointer's last second and a half: the gesture it just made, if any."""

    def __init__(self) -> None:
        self.samples: deque[tuple[float, float, float]] = deque()
        self.inside_since: float | None = None

    def feed(self, now: float, x: float, y: float) -> None:
        if not self.samples or (x, y) != self.samples[-1][1:] or now - self.samples[-1][0] > 0.2:
            self.samples.append((now, x, y))
        while self.samples and now - self.samples[0][0] > SAMPLE_KEEP:
            self.samples.popleft()

    def clear(self) -> None:
        self.samples.clear()
        self.inside_since = None

    def speed(self, now: float, over: float) -> float:
        """Path length a second over the last `over` seconds."""
        pts = [s for s in self.samples if now - s[0] <= over]
        if len(pts) < 2:
            return 0.0
        path = sum(math.hypot(b[1] - a[1], b[2] - a[2]) for a, b in zip(pts, pts[1:]))
        return path / max(0.016, pts[-1][0] - pts[0][0])

    def reversals(self, pts: list[tuple[float, float, float]], axis: int, swing: float) -> int:
        """Turns of direction along an axis (1 x, 2 y), each after at least `swing` px of travel."""
        n, direction, anchor = 0, 0, pts[0][axis] if pts else 0.0
        for p in pts[1:]:
            d = p[axis] - anchor
            if abs(d) >= swing:
                sign = 1 if d > 0 else -1
                if direction and sign != direction:
                    n += 1
                direction, anchor = sign, p[axis]
            elif direction and (p[axis] - anchor) * direction > 0:
                anchor = p[axis]
        return n

    def classify(self, now: float, box: tuple[float, float, float, float], k: float, mood: str) -> str | None:
        """`pat`, `rub`, `poke`, `flip`, `flinch`, `hover` or None, from the samples and the figure's drawn box."""
        if len(self.samples) < 2:
            return None
        l, t, r, b = box
        pad = 6.0 * k

        def inside(s: tuple[float, float, float]) -> bool:
            return l - pad <= s[1] <= r + pad and t - pad <= s[2] <= b + pad

        last = self.samples[-1]
        quick = [s for s in self.samples if now - s[0] <= 0.3]
        fast = self.speed(now, 0.3)
        if fast >= SWIPE_SPEED * k and len(quick) >= 2:
            xs = [s[1] for s in quick]
            if min(xs) < l and max(xs) > r and all(t <= s[2] <= b for s in quick if l <= s[1] <= r):
                return "flip"
        pts_in = [s for s in self.samples if inside(s)]
        if inside(last):
            self.inside_since = self.inside_since if self.inside_since is not None else last[0]
        else:
            self.inside_since = None
        if inside(last):
            before = [s for s in self.samples if POKE_WINDOW >= now - s[0] > 0.12]
            peak = max((self._leg(a, c) for a, c in zip(self.samples, list(self.samples)[1:]) if now - c[0] <= POKE_WINDOW), default=0.0)
            if before and not inside(before[0]) and peak >= POKE_SPEED * k and self.speed(now, 0.12) <= POKE_REST * k:
                return "poke"
            head = [s for s in pts_in if now - s[0] <= PAT_WINDOW and s[2] <= t + HEAD_ZONE * (b - t)]
            if len(head) >= 4 and self.reversals(head, 2, PAT_DIP * k) >= PAT_REVERSALS and self._spread(head, 1) <= (r - l):
                return "pat"
            body = [s for s in pts_in if now - s[0] <= RUB_WINDOW]
            if len(body) >= 6 and self.reversals(body, 1, RUB_SWING * k) >= RUB_REVERSALS and self._spread(body, 2) <= RUB_FLAT * (b - t):
                return "rub"
            if self.inside_since is not None and now - self.inside_since >= HOVER_FOR and self.speed(now, HOVER_FOR) <= HOVER_STILL * k:
                return "hover"
        elif self._swipe_ended(now, k):
            cx, cy = (l + r) / 2, (t + b) / 2
            if math.hypot(last[1] - cx, last[2] - cy) <= FLINCH_REACH * k + (r - l) / 2:
                return "flinch"
        return None

    def _swipe_ended(self, now: float, k: float) -> bool:
        """A fast swipe that has just slowed to a stop: the leg's peak over the last 0.4 s was a swipe, now it is slow."""
        pts = [s for s in self.samples if now - s[0] <= 0.4]
        peak = max((self._leg(a, c) for a, c in zip(pts, pts[1:])), default=0.0)
        return peak >= SWIPE_SPEED * k * 0.9 and self.speed(now, 0.12) <= peak * 0.5

    @staticmethod
    def _leg(a: tuple[float, float, float], c: tuple[float, float, float]) -> float:
        return math.hypot(c[1] - a[1], c[2] - a[2]) / max(0.016, c[0] - a[0])

    @staticmethod
    def _spread(pts: list, axis: int) -> float:
        vals = [p[axis] for p in pts]
        return max(vals) - min(vals) if vals else 0.0


def ease(t: float, length: float) -> int:
    """The step (0 to 3) of a face's ease at `t` seconds into `length`: up over a quarter second, down over the last."""
    if t < 0.0 or t >= length:
        return 0
    rest = length - t
    up = 1 if t < 0.12 else 2 if t < 0.26 else 3
    down = 1 if rest < 0.15 else 2 if rest < 0.3 else 3
    return min(up, down)


def ease_marks(start: float, length: float) -> list[float]:
    return [start + 0.12, start + 0.26, start + length - 0.3, start + length - 0.15, start + length]


class Extras:
    """Everything the desk figure adds to the engine's roaming (one per engine)."""

    def __init__(self, engine: Any) -> None:
        register()
        self.e = engine
        self.rng = random.Random(engine.life_rng.getstate()[1][1])
        self.micro = faces.Micro(random.Random(engine.life_rng.getstate()[1][2]), 0.0)
        self.pointer_state = Pointer()
        #: When the next in-place act may start; `inf` stops them (tests that want a still stand).
        self.act_ready = engine.now + self.rng.uniform(*LIFE_EVERY)
        self.cool: dict[str, float] = {}
        self.over: tuple[str, float, float] | None = None
        self.hold: float | None = None
        self.last: list[str] = []
        self.near = False
        #: Where the pointer was last and when it last moved: it is watched finely only while it moves near the figure.
        self.seen: tuple[int, int] | None = None
        self.moved_at = -1e9

    # --- what to draw ------------------------------------------------------------------------

    def view(self, now: float) -> tuple[tuple[str, int, int] | None, tuple[str, int] | None]:
        """`(prop, face)` to draw now (the engine's `Output.prop` and `Output.face`)."""
        e = self.e
        if e.reduced or e.state not in FACE_STATES:
            return None, None
        prop = None
        face = self._override(now)
        if e.state == "act" and e.act:
            length = max(0.01, e.act_len)
            t = now - e.act_started
            prop = props.view(e.act, t / length, t)
            kind = faces.ACT_FACES.get(e.act)
            if face is None and kind and (lv := ease(t, length)):
                face = (kind, lv)
        if face is None and e.state in ("stand", "sit"):
            self.micro.tick(now, e.mind.mood(now, e.hour), self._free_for_micro())
            face = self.micro.view(now)
        return prop, face

    def _free_for_micro(self) -> bool:
        e = self.e
        return not (e.quiet or e.busy or e.card is not None)

    def _override(self, now: float) -> tuple[str, int] | None:
        if self.over is None:
            return None
        kind, start, length = self.over
        lv = ease(now - start, length)
        if not lv:
            self.over = None
            return None
        return kind, lv

    def wake_ms(self, now: float) -> int | None:
        """How soon to look again for the sake of the face, the prop and the pointer, or None."""
        e = self.e
        if e.reduced:
            return None
        soon: list[float] = []
        if self.over is not None:
            soon += [m for m in ease_marks(self.over[1], self.over[2]) if m > now]
        if e.state == "act" and e.act:
            length = max(0.01, e.act_len)
            if e.act in faces.ACT_FACES:
                soon += [m for m in ease_marks(e.act_started, length) if m > now]
            step = props.next_step(e.act, (now - e.act_started) / length, length, now - e.act_started)
            if step is not None:
                soon.append(now + step)
        if e.state in ("stand", "sit"):
            soon.append(self.micro.next_change(now))
        soon = [m for m in soon if m < math.inf]
        ms = None if not soon else max(MIN_WAKE_MS, int(math.ceil((min(soon) - now) * 1000)) + 1)
        if self.near and now - self.moved_at < WATCH_FOR:
            ms = WATCH_MS if ms is None else min(ms, WATCH_MS)
        return ms

    # --- the pointer -------------------------------------------------------------------------

    def pointer(self, now: float, pointer: tuple[int, int]) -> bool:
        """Feed the pointer; True when a gesture was answered (the caller then skips the plain look)."""
        e = self.e
        frame = e._frame(now)
        x, y, _clip = e._display(frame)
        l, t, r, b = e._box(frame)
        box = (x + l, y + t, x + r, y + b)
        k = e._scale()
        w = box[2] - box[0]
        self.near = (box[0] - WATCH_REACH * w <= pointer[0] <= box[2] + WATCH_REACH * w
                     and box[1] - WATCH_REACH * w <= pointer[1] <= box[3] + WATCH_REACH * w)
        if not self.near:
            self.pointer_state.clear()
            return False
        if pointer != self.seen:
            self.seen, self.moved_at = pointer, now
        self.pointer_state.feed(now, float(pointer[0]), float(pointer[1]))
        if e.state not in TOUCH_FREE or e.quiet or e.busy:
            return False
        kind = self.pointer_state.classify(now, box, k, e.mind.mood(now, e.hour))
        if kind is None:
            return False
        if kind == "poke":
            kind = POKE_BY_MOOD.get(e.mind.mood(now, e.hour), "poke_curious")
        if self.fire(kind, now, toward=pointer[0]):
            self.pointer_state.clear()
            return True
        return False

    # --- reactions ---------------------------------------------------------------------------

    def fire(self, kind: str, now: float, toward: float | None = None) -> bool:
        """Play a reaction if it is allowed now (state, cooldown, nobody typing). True when it started."""
        e = self.e
        r = REACTIONS.get(kind)
        if r is None or e.reduced or e.quiet or e.busy or e.card is not None or now < self.cool.get(kind, -1e9):
            return False
        if e.state not in (TOUCH_FREE if r.touch else SCREEN_FREE):
            return False
        if e.state == "act" and e.act in REACT_ACTS and not r.touch:
            return False  # a screen event never breaks a reaction that is running
        self.cool[kind] = now + r.cooldown
        self.last = [*self.last[-7:], kind]
        if r.feel:
            e.mind.feel(r.feel, now)
        e.last_active = now
        if toward is not None and r.touch:
            e.facing = -1 if toward < e.x + e.size[0] / 2 else 1
        self.over = (r.face, now, r.seconds)
        if r.act:
            self._play(r.act, r.seconds, now)
        return True

    def _play(self, name: str, seconds: float, now: float) -> None:
        e = self.e
        if self.hold is None and e.state in ("stand", "sit"):
            self.hold = e.state_until
        if e.state in ("sleep", "sit"):
            e._enter("stand", now)
        e.mind.did(name, now)
        e.act = name
        e._enter("act", now)
        e.act_len = seconds
        e.state_until = now + seconds

    def after_act(self, now: float) -> None:
        """An act ended and the stand began again: the stand's own end (a trip, a climb) is not pushed back."""
        if self.hold is not None:
            e = self.e
            if e.state == "stand" and self.hold > now:
                e.state_until = min(e.state_until, self.hold)
            self.hold = None

    # --- life while it stands ----------------------------------------------------------------

    def life(self, now: float) -> None:
        """Now and then, while it stands with nothing else to do, it does something in place."""
        e = self.e
        if now < self.act_ready or e.state != "stand" or e.reduced or e.quiet or e.busy or e.card is not None or e.turn_to:
            return
        if e.trip or e.target is not None or e.caret is not None or e.pending is not None:
            return
        self.act_ready = now + self.rng.uniform(*LIFE_EVERY)
        name = e.mind.pick(self.rng, now, e.gait, e.hour, "perch" if e.perch else "")
        if self.hold is None:
            self.hold = e.state_until
        e._start_act(name, now)

