"""Things the desk figure uses (INBOX 1683 ask M4: "why cant it like read a book, lounge on a bean bag, go fishing,
do push ups, read the map ... dont limit to these, but also I want it to be like the regular atlas on the app").

The shipped frames carry no prop, so every prop here is drawn over (or, for a bean bag, under) the frame by
Pillow from a few vector shapes in the figure's own indigo and lilac. A prop act is an ordinary `behaviour.Activity`
(a base frame, a pose over it, what it feeds) registered with the mind by `register()`, so the mind weighs it like
the rest; what makes it a prop act is `SPECS`: which prop, how fast it animates, the face it wears. It is fetched,
used and put away: the prop grows in over the first steps of the act and shrinks out over the last (`Output.prop`
is `(name, phase, size)` with the size 1 to 3), and the prop's own motion (a page, a bobber, a flame, steam) is
`phase`, a few steps a second so the redraw stays cheap.
"""

from __future__ import annotations

import math
from typing import Any, NamedTuple

from . import behaviour as bh
from . import faces
from . import sprites as sp

S = 3  # supersampling of the prop layer
#: Where an act is in its length when the prop is out: the first and last share it is being fetched or put away.
FETCH = 0.1
#: The size of each step of a fetch (index into `faces.LEVELS`-like steps: 1 small, 2 most, 3 whole).
SIZES = (0.0, 0.5, 0.85, 1.0)


class Spec(NamedTuple):
    prop: str
    #: Phases a second and how many it has.
    fps: float
    steps: int
    face: str
    #: The anchor on the figure, as shares of its drawn height from its middle (to the way it faces) and its top.
    at: tuple[float, float]
    under: bool = False


def _act(frame: Any, seconds: tuple[float, float], keys: tuple, feeds: tuple, likes: str = "", **kw: Any) -> bh.Activity:
    return bh.Activity(frame, seconds, keys, feeds, likes=likes, **kw)


def _breath(depth: float) -> tuple:
    return ((0, 1, 1, 0), (0.5, 1, 1 + depth, 0), (1, 1, 1, 0))


#: The prop acts: name -> (spec, activity, base weight).
PROP_ACTS: dict[str, tuple[Spec, bh.Activity, int]] = {
    "read_book": (
        Spec("book", 0.5, 4, "focus", (0.12, 0.66)),
        _act("sit", (25.0, 55.0), ((0, 1, 1, 0), (0.1, 1, 0.98, 0.03), (0.9, 1, 0.98, 0.03), (1, 1, 1, 0)), (("curiosity", -0.25), ("rest", -0.1)), "curious"),
        4,
    ),
    "lounge_beanbag": (
        Spec("beanbag", 0.3, 2, "content", (0.0, 0.8), under=True),
        _act("sit", (30.0, 70.0), ((0, 1, 1, 0), (0.12, 1.03, 0.95, 0), (1, 1.03, 0.95, 0)), (("rest", -0.5),), "sleepy"),
        3,
    ),
    "go_fishing": (
        Spec("rod", 1.5, 4, "content", (0.15, 0.62)),
        _act("sit", (30.0, 70.0), ((0, 1, 1, 0), (0.1, 1, 0.99, 0.02), (0.9, 1, 0.99, 0.02), (1, 1, 1, 0)), (("rest", -0.2), ("play", -0.2)), "sleepy"),
        3,
    ),
    "push_ups": (
        Spec("mat", 2.0, 4, "strain", (0.0, 0.9), under=True),
        _act("land", (8.0, 14.0), ((0, 1, 1, 0), (0.1, 1.04, 0.9, 0.05), (0.25, 1.04, 0.84, 0.05), (0.4, 1.04, 0.92, 0.05), (0.55, 1.04, 0.84, 0.05), (0.7, 1.04, 0.92, 0.05), (0.85, 1.04, 0.84, 0.05), (1, 1, 1, 0)), (("play", -0.35), ("rest", 0.1)), "happy", gait="walk"),
        2,
    ),
    "read_map": (
        Spec("map", 0.8, 3, "focus", (0.15, 0.48)),
        _act("stand", (12.0, 22.0), ((0, 1, 1, 0), (0.12, 1.01, 0.99, 0.04), (0.9, 1.01, 0.99, 0.04), (1, 1, 1, 0)), (("curiosity", -0.3),), "curious"),
        4,
    ),
    "hold_lantern": (
        Spec("lantern", 6.0, 4, "curious", (0.3, 0.5)),
        _act("wave", (10.0, 20.0), ((0, 1, 1, 0), (0.15, 1, 1.02, 0.02), (0.9, 1, 1.02, 0.02), (1, 1, 1, 0)), (("curiosity", -0.15),), "curious"),
        3,
    ),
    "lift_weights": (
        Spec("dumbbell", 2.0, 4, "strain", (0.28, 0.2)),
        _act("wave", (8.0, 14.0), ((0, 1, 1, 0), (0.1, 1, 1.03, 0), (0.3, 1, 0.97, 0), (0.5, 1, 1.03, 0), (0.7, 1, 0.97, 0), (0.9, 1, 1.02, 0), (1, 1, 1, 0)), (("play", -0.3),), "proud"),
        2,
    ),
    "sip_tea": (
        Spec("cup", 1.0, 4, "content", (0.14, 0.62)),
        _act("sit", (12.0, 24.0), ((0, 1, 1, 0), (0.15, 1, 0.99, 0.03), (0.5, 1, 1, 0.01), (0.85, 1, 0.99, 0.03), (1, 1, 1, 0)), (("rest", -0.2),), "sleepy"),
        3,
    ),
    "write_journal": (
        Spec("journal", 1.0, 4, "focus", (0.12, 0.7)),
        _act("sit", (20.0, 45.0), ((0, 1, 1, 0), (0.1, 1, 0.97, 0.05), (0.9, 1, 0.97, 0.05), (1, 1, 1, 0)), (("curiosity", -0.15), ("play", -0.1)), "curious"),
        3,
    ),
}
#: Acts with no prop that the app has and the desk had not.
PLAIN_ACTS: dict[str, tuple[bh.Activity, int, str]] = {
    "hum": (_act("stand", (4.0, 7.0), ((0, 1, 1, 0), (0.25, 1, 1.01, 0.04), (0.75, 1, 1.01, -0.04), (1, 1, 1, 0)), (("play", -0.15),), "happy"), 3, "content"),
    "tiptoe": (_act("look", (2.0, 3.2), ((0, 1, 1, 0), (0.3, 0.98, 1.06, 0.03), (0.7, 0.98, 1.06, 0.03), (1, 1, 1, 0)), (("curiosity", -0.15),), "curious"), 3, "curious"),
    "stargaze": (_act("look", (6.0, 10.0), ((0, 1, 1, 0), (0.2, 0.98, 1.04, -0.05), (0.85, 0.98, 1.04, -0.05), (1, 1, 1, 0)), (("curiosity", -0.2), ("rest", -0.1)), "sleepy"), 2, "content"),
    "daydream": (_act("sit", (10.0, 20.0), ((0, 1, 1, 0), (0.2, 1, 0.98, 0.02), (1, 1, 0.98, 0.02)), (("rest", -0.2),), "sleepy"), 2, "sleepy"),
    "puzzle": (_act("look", (5.0, 9.0), ((0, 1, 1, 0), (0.2, 0.98, 0.99, -0.04), (0.55, 0.98, 0.99, 0.04), (1, 1, 1, 0)), (("curiosity", -0.2),), "curious"), 2, "focus"),
}
#: Act name -> the face it wears for its length (the props' and the plain ones'), added to `faces.ACT_FACES`.
_registered = False


def register() -> None:
    """Add the acts to the mind's tables once (the engine calls it at import)."""
    global _registered
    if _registered:
        return
    _registered = True
    for name, (spec, act, weight) in PROP_ACTS.items():
        _add(name, act, weight, spec.face)
    for name, (act, weight, face) in PLAIN_ACTS.items():
        _add(name, act, weight, face)


def _add(name: str, act: bh.Activity, weight: int, face: str) -> None:
    bh.ACTIVITIES[name] = act
    bh.BASE_WEIGHT[name] = weight
    bh.AMPLITUDE[name] = bh._amplitude(act.keys)
    faces.ACT_FACES[name] = face


def view(act: str | None, u: float, now_in: float) -> tuple[str, int, int] | None:
    """The prop to draw for `act` at `u` (0 to 1 through it) and `now_in` seconds into it: `(name, phase, size)`."""
    if act not in PROP_ACTS or not 0.0 <= u < 1.0:
        return None
    spec = PROP_ACTS[act][0]
    edge = min(u, 1.0 - u) / FETCH
    size = 3 if edge >= 1.0 else 2 if edge >= 0.55 else 1 if edge >= 0.2 else 0
    if not size:
        return None
    return spec.prop, int(now_in * spec.fps) % spec.steps, size


def next_step(act: str | None, u: float, length: float, now_in: float) -> float | None:
    """Seconds until the prop's picture next changes (a phase step or a size step), or None."""
    if act not in PROP_ACTS:
        return None
    spec = PROP_ACTS[act][0]
    to_phase = (int(now_in * spec.fps) + 1) / spec.fps - now_in
    edge = min(u, 1.0 - u)
    marks = [FETCH * 0.2, FETCH * 0.55, FETCH, 1.0 - FETCH, 1.0 - FETCH * 0.55, 1.0 - FETCH * 0.2]
    ahead = [(m - u) * length for m in marks if m > u]
    return max(0.016, min([to_phase, *ahead]) if edge >= 0 else to_phase)


# --- drawing -------------------------------------------------------------------------------------

INDIGO = (60, 56, 140)
LILAC = (186, 176, 238)
CREAM = (244, 240, 252)
TEAL = (110, 168, 196)
WARM = (240, 196, 120)
INK = (*sp.LID_INK,)


def draw(frame: sp.Frame, prop: tuple[str, int, int], flip: bool) -> sp.Frame:
    """`frame` with the prop drawn on it (under the figure for a bean bag or a mat, over it otherwise)."""
    from PIL import Image, ImageDraw

    name, phase, size = prop
    spec = next((s for s, _a, _w in PROP_ACTS.values() if s.prop == name), None)
    if spec is None or frame.box[2] <= frame.box[0]:
        return frame
    l, t, r, b = frame.box
    h = max(1.0, float(b - t))
    d = -1 if flip else 1
    k = SIZES[size]
    layer = Image.new("RGBA", (frame.width * S, frame.height * S), (0, 0, 0, 0))
    g = ImageDraw.Draw(layer)
    u = h / 100.0 * S * k
    ax = ((l + r) / 2.0 + d * spec.at[0] * h) * S
    ay = (t + spec.at[1] * h) * S
    {
        "book": _book, "beanbag": _beanbag, "rod": _rod, "mat": _mat, "map": _map, "lantern": _lantern,
        "dumbbell": _dumbbell, "cup": _cup, "journal": _journal,
    }[name](g, ax, ay, u, d, phase)
    whole = Image.frombytes("RGBA", (frame.width, frame.height), frame.bgra, "raw", "BGRa")
    layer = layer.resize((frame.width, frame.height), Image.Resampling.LANCZOS)
    if spec.under:
        layer.alpha_composite(whole)
        done = layer
    else:
        done = whole
        done.alpha_composite(layer)
    return sp.Frame(frame.width, frame.height, sp.premultiplied_bgra(sp.clear_faint_alpha(done)), frame.pad_x, frame.pad_y, frame.box)


def _book(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    w, h = 17 * u, 12 * u
    g.polygon([(x - w, y), (x, y - 3 * u), (x, y + h - 3 * u), (x - w, y + h)], fill=(*CREAM, 255), outline=(*INDIGO, 255))
    g.polygon([(x + w, y), (x, y - 3 * u), (x, y + h - 3 * u), (x + w, y + h)], fill=(*CREAM, 255), outline=(*INDIGO, 255))
    g.line((x, y - 3 * u, x, y + h - 3 * u), fill=(*INDIGO, 255), width=max(1, int(u * 0.8)))
    for i in range(3):  # lines of text
        yy = y + (2.5 + i * 3.2) * u
        g.line((x - w * 0.85, yy, x - w * 0.15, yy - 0.8 * u), fill=(*LILAC, 255), width=max(1, int(u * 0.6)))
        g.line((x + w * 0.15, yy - 0.8 * u, x + w * 0.85, yy), fill=(*LILAC, 255), width=max(1, int(u * 0.6)))
    lift = (phase % 4) * 1.2  # a page turning: its edge rises and falls
    if phase % 2:
        g.polygon([(x, y - 3 * u), (x + w * 0.8, y - lift * u), (x + w * 0.8, y + h - lift * u), (x, y + h - 3 * u)], fill=(*CREAM, 235), outline=(*INDIGO, 255))


def _beanbag(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    sag = 0.8 * (phase % 2)
    g.ellipse((x - 40 * u, y - 20 * u + sag * u, x + 40 * u, y + 12 * u), fill=(*TEAL, 255), outline=(*INDIGO, 255), width=max(1, int(u * 0.8)))
    g.arc((x - 30 * u, y - 15 * u, x + 30 * u, y + 6 * u), 200, 340, fill=(*CREAM, 200), width=max(1, int(u * 0.8)))
    g.line((x, y - 20 * u, x, y - 6 * u), fill=(*INDIGO, 160), width=max(1, int(u * 0.7)))


def _rod(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    tip = (x + d * 44 * u, y - 26 * u)
    g.line((x, y, *tip), fill=(*WARM, 255), width=max(2, int(u * 1.3)))
    bob = (phase % 4 - 1.5) * 0.7
    water = (tip[0] + d * 4 * u, y + 40 * u + bob * u)
    g.line((*tip, *water), fill=(*CREAM, 230), width=max(1, int(u * 0.5)))
    g.ellipse((water[0] - 2.6 * u, water[1] - 2.6 * u, water[0] + 2.6 * u, water[1] + 2.6 * u), fill=(230, 90, 100, 255), outline=(*CREAM, 255))
    ring = 5 + (phase % 4) * 2
    g.ellipse((water[0] - ring * u, water[1] + 1.5 * u, water[0] + ring * u, water[1] + 4 * u), outline=(*TEAL, 170), width=max(1, int(u * 0.6)))


def _mat(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    g.rounded_rectangle((x - 42 * u, y - 2 * u, x + 42 * u, y + 5 * u), radius=3 * u, fill=(*LILAC, 255), outline=(*INDIGO, 255), width=max(1, int(u * 0.7)))
    if phase % 2:  # a drop of effort
        g.ellipse((x - d * 22 * u, y - 70 * u, x - d * 19 * u, y - 64 * u), fill=(*TEAL, 220))


def _map(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    sway = (phase - 1) * 0.8 * u
    w, h = 16 * u, 12 * u
    pts = [(x - w + sway, y - h), (x + w + sway, y - h * 0.9), (x + w - sway, y + h), (x - w - sway, y + h * 0.9)]
    g.polygon(pts, fill=(*CREAM, 255), outline=(*INDIGO, 255))
    g.line((x - w * 0.3 + sway, y - h, x - w * 0.3 - sway, y + h), fill=(*LILAC, 255), width=max(1, int(u * 0.7)))
    g.line((x + w * 0.35 + sway, y - h, x + w * 0.35 - sway, y + h), fill=(*LILAC, 255), width=max(1, int(u * 0.7)))
    g.line((x - w * 0.7, y + h * 0.3, x - w * 0.1, y - h * 0.2, x + w * 0.5, y + h * 0.2), fill=(*TEAL, 255), width=max(1, int(u * 0.8)))
    g.text((x + w * 0.45, y - h * 0.1), "x", fill=(220, 70, 90, 255))


def _lantern(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    glow = 18 + (phase % 4) * 1.5
    for i, a in enumerate((26, 40, 60)):
        rr = (glow - i * 5) * u
        g.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(255, 220, 140, a))
    g.rounded_rectangle((x - 4 * u, y - 6 * u, x + 4 * u, y + 6 * u), radius=1.5 * u, fill=(255, 236, 170, 255), outline=(*INDIGO, 255), width=max(1, int(u * 0.7)))
    g.arc((x - 3 * u, y - 11 * u, x + 3 * u, y - 4 * u), 180, 360, fill=(*INDIGO, 255), width=max(1, int(u * 0.7)))


def _dumbbell(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    y -= (phase % 4 if phase % 4 < 3 else 1) * 2.5 * u
    g.line((x - 9 * u, y, x + 9 * u, y), fill=(*INDIGO, 255), width=max(2, int(u * 1.2)))
    for sx in (-1, 1):
        g.rounded_rectangle((x + sx * 9 * u - 3 * u, y - 5 * u, x + sx * 9 * u + 3 * u, y + 5 * u), radius=1.5 * u, fill=(*TEAL, 255), outline=(*INDIGO, 255), width=max(1, int(u * 0.7)))


def _cup(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    g.rounded_rectangle((x - 5 * u, y - 4 * u, x + 5 * u, y + 5 * u), radius=2.5 * u, fill=(*CREAM, 255), outline=(*INDIGO, 255), width=max(1, int(u * 0.7)))
    g.arc((x + 3 * u, y - 2 * u, x + 8 * u, y + 3 * u), 270, 90, fill=(*INDIGO, 255), width=max(1, int(u * 0.7)))
    for i in range(2):  # steam
        sx = x + (i * 4 - 2) * u
        off = ((phase + i * 2) % 4) * 1.6 * u
        g.arc((sx - 1.5 * u, y - 13 * u - off, sx + 1.5 * u, y - 7 * u - off), 90, 270, fill=(*CREAM, 190), width=max(1, int(u * 0.6)))


def _journal(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    g.polygon([(x - 11 * u, y), (x + 11 * u, y - 2 * u), (x + 11 * u, y + 9 * u), (x - 11 * u, y + 11 * u)], fill=(*CREAM, 255), outline=(*INDIGO, 255))
    for i in range(3):
        g.line((x - 8 * u, y + (2 + i * 2.6) * u, x + 7 * u, y + (0.5 + i * 2.6) * u), fill=(*LILAC, 255), width=max(1, int(u * 0.6)))
    px = x - 8 * u + (phase % 4) * 3.5 * u
    g.line((px, y + 1 * u, px + 4 * u, y - 7 * u), fill=(*WARM, 255), width=max(2, int(u * 0.9)))
