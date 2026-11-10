"""How the companion gets about, and what it keeps clear of (INBOX 1670, 13:22Z to 13:32Z).

Pure data and small pure functions: no clock, no randomness of its own (the engine passes its seeded
`rng`), no Win32.

**A repertoire** (INBOX 1683 u, after f: the owner saw only puffs, then asked for "a lot of expansion"). The mode of
a leg is chosen by distance, mood and gait: a walk or a glide, a run or a swoop, a portal out and in, a walk off
one screen edge and in from the other; a puff is rare (under one leg in ten) and no mode is used twice running.
Where it comes to *rest* is still never the middle third (`in_middle`, `out_of_middle`).

**Keeping clear of the text box.** The caret's rectangle (from the foreground window, padded by
`CARET_MARGIN`) is somewhere the figure's drawn box does not rest or go.
"""

from __future__ import annotations

import random
from typing import NamedTuple

Rect = tuple[float, float, float, float]

#: Every way it travels. "walk" is a ground companion's, "glide" a floater's; the rest are for either.
MODES = ("walk", "run", "glide", "swoop", "portal", "puff", "edge", "jump", "climb", "fade", "blink", "cloud", "bubble")
#: The rides: the figure travels the whole time it is drawn in its cloud or bubble, not in a vanish and an arrival.
RIDES = ("cloud", "bubble")
#: The ways it gets to a new spot between presence spells, and the ones it steps aside from the caret in (never a walk).
VISIBLE = ("blink", "cloud", "bubble", "portal")
#: Jumps over the middle: the ones that do not pass through it.
LEAPS = ("portal", "puff", "edge")
#: A leg longer than this share of the work area's width is a long one (a run; a little likelier to flourish).
FAR_SHARE = 1.0 / 3.0
#: Rest spots lie within this many logical px of a screen edge (or on the taskbar line).
EDGE_ZONE = 120.0
#: The caret's rectangle is padded by this many logical px.
CARET_MARGIN = 28.0
#: Typing counts as busy for this many seconds after the last key.
TYPING_FOR = 4.0


class Warp(NamedTuple):
    """The seconds of a vanish-and-reappear: out, the gap between, and in. Each whole transition is
    0.4 to 1.2 s (the owner: quick and reads clearly)."""

    out: float
    gap: float
    back: float

    @property
    def total(self) -> float:
        return self.out + self.gap + self.back


WARPS = {
    "portal": Warp(0.50, 0.06, 0.50),
    "puff": Warp(0.32, 0.05, 0.36),
    "edge": Warp(0.45, 0.05, 0.55),
    "fade": Warp(0.25, 0.05, 0.25),
    "blink": Warp(0.80, 0.05, 0.80),  # sparkles gather, it is gone, sparkles scatter: long enough to be seen (1.5 s)
    "cloud": Warp(0.80, 0.0, 0.80),
    "bubble": Warp(0.90, 0.0, 0.90),
}
#: A ride is this long at least (seconds) and this much longer per 1000 logical px of the leg, at most RIDE_MAX.
RIDE_MIN, RIDE_PER_KPX, RIDE_MAX = 1.6, 1.4, 3.4


def warp_for(mode: str, rng: random.Random, dist: float = 0.0) -> Warp:
    """The warp of a mode, a little different each time (within 10 percent); a ride is longer for a longer leg
    (`dist`, logical px) so it is never a dash."""
    w = WARPS.get(mode, WARPS["fade"])
    k = rng.uniform(0.96, 1.08) if mode in RIDES or mode == "blink" else rng.uniform(0.92, 1.08)
    if mode in RIDES:
        half = min(RIDE_MAX, RIDE_MIN + RIDE_PER_KPX * abs(dist) / 1000.0) / 2.0
        return Warp(half * k, 0.0, half * k)
    return Warp(w.out * k, w.gap, w.back * k)


def caret_move(rng: random.Random, recent: list[str]) -> str:
    """How it steps out of the caret's way (INBOX 1692: it was always a puff, the move the owner met most): a blink, a
    portal or a puff, never the one it used last."""
    live = [m for m in ("blink", "portal", "puff") if not recent or m != recent[-1]]
    weights = {"blink": 4.0, "portal": 3.0, "puff": 1.0}
    roll = rng.random() * sum(weights[m] for m in live)
    for m in live:
        roll -= weights[m]
        if roll < 0:
            return m
    return live[-1]


def middle(area: Rect) -> tuple[float, float]:
    """The middle third of a work area's width (left, right)."""
    left, right = area[0], area[2]
    third = (right - left) / 3.0
    return left + third, left + 2.0 * third


def crosses_middle(x0: float, x1: float, area: Rect, width: float) -> bool:
    """Whether the figure's middle, going from window-left `x0` to `x1`, is ever in the middle third."""
    lo, hi = middle(area)
    a, b = sorted((x0 + width / 2.0, x1 + width / 2.0))
    return b > lo and a < hi


def in_middle(x: float, area: Rect, width: float) -> bool:
    """Whether a figure whose window is at `x` has its middle in the middle third."""
    lo, hi = middle(area)
    return lo < x + width / 2.0 < hi


def out_of_middle(x: float, area: Rect, width: float) -> float:
    """`x` moved out of the middle third to the nearer side of it (unchanged when it is not in it)."""
    lo, hi = middle(area)
    c = x + width / 2.0
    if not lo < c < hi:
        return x
    return (lo - 12.0 if c - lo < hi - c else hi + 12.0) - width / 2.0  # a margin: the drawn figure is offset a few px by its frame


def far(x0: float, x1: float, area: Rect) -> bool:
    return abs(x1 - x0) > FAR_SHARE * (area[2] - area[0])


def nearest_edge(x: float, area: Rect, width: float) -> int:
    """-1 for the left edge, 1 for the right: whichever the figure at `x` is nearer to."""
    return -1 if x - area[0] <= area[2] - width - x else 1


def edge_x(side: int, area: Rect, width: float, inset: float = 0.0) -> float:
    return area[0] + inset if side < 0 else area[2] - width - inset


def in_edge_zone(x: float, area: Rect, width: float, scale: float = 1.0) -> bool:
    zone = EDGE_ZONE * scale
    return x - area[0] <= zone or area[2] - width - x <= zone


def overlaps(a: Rect, b: Rect) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def padded(r: Rect, by: float) -> Rect:
    return r[0] - by, r[1] - by, r[2] + by, r[3] + by


def _by_mood(table: dict[str, float], mood: str) -> None:
    for mode in list(table):
        if mode in ("bubble", "blink") and mood in ("happy", "curious", "proud"):
            table[mode] *= 1.4
        if mode == "cloud" and mood in ("sleepy", "bored"):
            table[mode] *= 1.5
        if mode in ("portal", "edge") and mood in ("happy", "curious", "proud", "bored"):
            table[mode] *= 1.5
        if mode in ("run", "swoop") and mood in ("happy", "curious", "startled", "proud"):
            table[mode] *= 1.5
        if mode in ("walk", "glide") and mood in ("sleepy", "bored"):
            table[mode] *= 1.4
        if mode == "puff" and mood in ("startled", "sleepy"):
            table[mode] *= 1.8


def _mode_table(body: str, fast: str, long_leg: bool, edge_ok: bool, run_ok: bool, between: bool) -> dict[str, float]:
    """The weights of the modes for one leg: between presence spells (INBOX 1692) seen and never a long walk."""
    if between:
        table = {"blink": 2.0, "cloud": 3.0, "bubble": 2.0, "portal": 1.6, "puff": 0.1}
        if not long_leg:
            table[body] = 1.5
        return table
    hop = 1.4 if body == "walk" and not long_leg else 0.0  # a ground figure's chain of hops (a floater has its glide and swoop)
    if long_leg:
        return {body: 4.0, fast: 3.0, "jump": 2.4 if body == "walk" else 0.0, "portal": 1.6, "puff": 0.2, "edge": 1.6 if edge_ok else 0.0, "blink": 1.2, "cloud": 1.6, "bubble": 1.0}
    return {body: 6.0, "jump": hop if run_ok else 0.0, fast: 2.0 if run_ok else 0.0, "portal": 0.7, "puff": 0.12, "blink": 0.5, "cloud": 0.7, "bubble": 0.5}


def pick_mode(
    rng: random.Random, *, gait: str, long_leg: bool, mood: str, recent: list[str], edge_ok: bool, run_ok: bool = True,
    between: bool = False,
) -> str:
    """One mode for a leg (INBOX 1683 u, the owner: it "only ever poofs" and "needs a lot of expansion"): by
    distance and mood, a walk or a glide, a run or a swoop, a portal out and in, or a walk off one screen
    edge and in from the other; a puff only rarely (under one leg in ten). The mode just used is never
    used again (a leg too short for a run may walk twice)."""
    body, fast = ("glide", "swoop") if gait == "float" else ("walk", "run")
    table = _mode_table(body, fast, long_leg, edge_ok, run_ok, between)
    _by_mood(table, mood)
    if recent and (run_ok or recent[-1] != body):
        table[recent[-1]] = 0.0
    live = [(m, w) for m, w in table.items() if w > 0]
    if not live:
        return body
    roll = rng.random() * sum(w for _m, w in live)
    for mode, w in live:
        roll -= w
        if roll < 0:
            return mode
    return live[-1][0]
