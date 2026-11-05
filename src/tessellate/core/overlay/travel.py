"""How the companion gets about, and what it keeps clear of (INBOX 1670, 13:22Z to 13:32Z).

Pure data and small pure functions: no clock, no randomness of its own (the engine passes its seeded
`rng`), no Win32.

**By its body first** (INBOX 1683 f, the owner: "all it does is sit on the taskbar and poof"). A leg is
walked (a floater glides) at a lively pace, a run when it is long, whatever it crosses; the older rule that
refused to walk a leg longer than a third of the width, or through the middle third, is gone. A portal, a
puff or an edge walk is a rare flourish (about one leg in ten when the leg is long, one in thirty when it is
short). Where it comes to *rest* is still never the middle third (`in_middle`, `out_of_middle`).

**A repertoire.** The mode is chosen by distance, mood and gait; a flourish used last (or the one before) is less likely.

**Keeping clear of the text box.** The caret's rectangle (from the foreground window, padded by
`CARET_MARGIN`) is somewhere the figure's drawn box does not rest or go.
"""

from __future__ import annotations

import random
from typing import NamedTuple

Rect = tuple[float, float, float, float]

#: Every way it travels. "walk" is a ground companion's, "glide" a floater's; the rest are for either.
MODES = ("walk", "glide", "portal", "puff", "edge", "jump", "climb", "fade")
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
}


def warp_for(mode: str, rng: random.Random) -> Warp:
    """The warp of a mode, a little different each time (within 10 percent)."""
    w = WARPS.get(mode, WARPS["fade"])
    k = rng.uniform(0.92, 1.08)
    return Warp(w.out * k, w.gap, w.back * k)


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
        if mode in ("portal", "edge") and mood in ("happy", "curious", "proud", "bored"):
            table[mode] *= 1.5
        if mode == "puff" and mood in ("startled", "sleepy"):
            table[mode] *= 1.8


def _by_recent(table: dict[str, float], recent: list[str], body: str) -> None:
    """The same flourish twice running is less likely; the body (walk or glide) may repeat freely."""
    if recent and recent[-1] != body:
        table[recent[-1]] = table.get(recent[-1], 0.0) * 0.25
    if len(recent) > 1 and recent[-2] != body and recent[-2] in table:
        table[recent[-2]] *= 0.6


def pick_mode(
    rng: random.Random, *, gait: str, long_leg: bool, mood: str, recent: list[str], edge_ok: bool,
) -> str:
    """One mode for a leg: nearly always the body (walk, or glide for a floater), with a portal, a puff or
    an edge walk now and then, a little more often on a long leg. What was used last is less likely, and
    nothing is used four times running."""
    body = "glide" if gait == "float" else "walk"
    if long_leg:
        table = {body: 9.0, "portal": 0.45, "puff": 0.35, "edge": 0.4 if edge_ok else 0.0}
    else:
        table = {body: 9.0, "portal": 0.12, "puff": 0.18}
    _by_mood(table, mood)
    _by_recent(table, recent, body)
    live = [(m, w) for m, w in table.items() if w > 0]
    if not live:
        return body
    roll = rng.random() * sum(w for _m, w in live)
    for mode, w in live:
        roll -= w
        if roll < 0:
            return mode
    return live[-1][0]
