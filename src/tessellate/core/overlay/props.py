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
from . import catalogue, faces
from . import sprites as sp

S = 3  # supersampling of the prop layer
#: Where an act is in its length when the prop is out: the first and last share it is being fetched or put away.
FETCH = 0.1
#: A long act (a presence spell is minutes) fetches and puts the prop away in this many seconds, not a tenth of its length.
FETCH_S = 6.0
#: The room a prop gets round the figure, as a share of its drawn height: a fishing line, a plant, a sky of stars.
ROOM = 0.18
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
    #: E5 (OPEN.md, INBOX 1692 e and 1711): a bowl at supper, a wand and its bubbles, two needles of light knitting a strand.
    #: The hour weights come from the shared catalogue (`act.dinner`, `act.blow_bubbles`, `act.knit_starlight`).
    "eat_dinner": (
        Spec("bowl", 2.0, 4, "content", (0.14, 0.64)),
        _act("sit", (18.0, 32.0), ((0, 1, 1, 0), (0.12, 1, 0.98, 0.03), (0.3, 1, 1, 0.01), (0.5, 1, 0.98, 0.03), (0.7, 1, 1, 0.01), (0.88, 1, 0.98, 0.03), (1, 1, 1, 0)), (("hunger", -0.8), ("rest", -0.1)), "happy"),
        3,
    ),
    "blow_bubbles": (
        Spec("wand", 4.0, 4, "smile", (0.16, 0.5)),
        _act("stand", (7.0, 12.0), ((0, 1, 1, 0), (0.15, 1, 1.01, 0.03), (0.5, 1, 1.02, 0.05), (0.85, 1, 1.01, 0.03), (1, 1, 1, 0)), (("play", -0.3), ("novelty", -0.15)), "happy"),
        2,
    ),
    "knit_starlight": (
        Spec("knit", 2.0, 4, "content", (0.1, 0.7)),
        _act("sit", (30.0, 60.0), ((0, 1, 1, 0), (0.1, 1, 0.97, 0.05), (0.9, 1, 0.97, 0.05), (1, 1, 1, 0)), (("rest", -0.15), ("curiosity", -0.1)), "content"),
        2,
    ),
    #: L-ui-modernisation-41: the app's `chair` (a chair pulled up and sat on), drawn under the seated figure. Weight and length are the catalogue's (`act.chair`).
    "sit_chair": (
        Spec("chair", 0.3, 2, "content", (0.0, 0.84), under=True),
        _act("sit", (20.0, 40.0), ((0, 1, 1, 0), (0.1, 1, 0.98, 0.02), (0.9, 1, 0.98, 0.02), (1, 1, 1, 0)), (("rest", -0.15), ("comfort", -0.2)), "sleepy"),
        1,
    ),
}
#: Acts with no prop that the app has and the desk had not.
#: What a presence spell (INBOX 1692) uses that the short acts do not: a sky, a blanket, a plant. Weight 0: the mind never
#: picks them by itself, only the engine's spell does, for minutes.
SPELL_ACTS: dict[str, tuple[Spec, bh.Activity]] = {
    "watch_stars": (
        Spec("stars", 1.5, 4, "content", (0.34, 0.26)),
        _act("look", (60.0, 120.0), ((0, 1, 1, 0), (0.1, 0.98, 1.03, -0.05), (0.9, 0.98, 1.03, -0.05), (1, 1, 1, 0)), (("rest", -0.15), ("curiosity", -0.2)), "sleepy"),
    ),
    "blanket_nap": (
        Spec("blanket", 0.25, 2, "content", (0.0, 0.52)),
        _act("sit", (60.0, 120.0), ((0, 1, 1, 0), (0.1, 1, 0.96, 0.02), (0.9, 1, 0.96, 0.02), (1, 1, 1, 0)), (("rest", -0.5),), "sleepy"),
    ),
    "water_plant": (
        #: L-ui-modernisation-42: under the figure, so its tail curl lies over the pot's lower edge and holds it (the app's pot in the tail curl).
        Spec("plant", 1.0, 4, "content", (0.30, 0.70), under=True),
        _act("stand", (60.0, 120.0), ((0, 1, 1, 0), (0.1, 1.01, 0.99, 0.04), (0.9, 1.01, 0.99, 0.04), (1, 1, 1, 0)), (("play", -0.15),), "curious"),
    ),
}
#: The wind-spirit ride (E5, INBOX 1692 n; `windspirit.py` chooses): not acts, the pictures a floater gets on its way.
#: Motes streaming behind it, a spiral that unwinds after a turn, an eddy at its feet where it settles. Drawn through the
#: same `Output.prop` channel as the rest, so the lean, the trailing wisp and the tail stay on (`Output.fx` would switch them off).
WIND_SPECS: dict[str, Spec] = {
    "gust": Spec("gust", 6.0, 4, "", (0.0, 0.5)),
    "spiral": Spec("spiral", 8.0, 4, "", (0.0, 0.5)),
    "eddy": Spec("eddy", 6.0, 4, "", (0.0, 0.92)),
}
#: What the notebook's reactions wear (L-ui-modernisation-11, the app's `nmp-glasses`, the `hide` hands and the speech bubble): reading
#: glasses on a long note, both hands over the eyes for a private one, a bubble of dots for a remark (the feed carries no
#: words, so the desk's is wordless). Reaction acts, not prop acts: `view` and `draw` look here, the mind never picks them.
#: `at` is the eyes' height, about a third of the figure from its top, and a little left of its middle.
REACT_PROPS: dict[str, Spec] = {
    "read_glasses": Spec("glasses", 1.0, 2, "", (-0.035, 0.33)),
    "cover_eyes": Spec("hands", 2.0, 2, "", (-0.035, 0.33)),
    "remark_say": Spec("bubble", 2.5, 3, "", (0.3, 0.04)),
}
#: Acts the mind has already that gain a prop (L-ui-modernisation-42): the nap curled on a note card, drawn under the sleeper.
ACT_PROPS: dict[str, Spec] = {
    "card_nap": Spec("notecard", 0.3, 2, "", (0.0, 0.86), under=True),
}
PLAIN_ACTS: dict[str, tuple[bh.Activity, int, str]] = {
    "hum": (_act("stand", (4.0, 7.0), ((0, 1, 1, 0), (0.25, 1, 1.01, 0.04), (0.75, 1, 1.01, -0.04), (1, 1, 1, 0)), (("play", -0.15),), "happy"), 3, "content"),
    "tiptoe": (_act("look", (2.0, 3.2), ((0, 1, 1, 0), (0.3, 0.98, 1.06, 0.03), (0.7, 0.98, 1.06, 0.03), (1, 1, 1, 0)), (("curiosity", -0.15),), "curious"), 3, "curious"),
    "stargaze": (_act("look", (6.0, 10.0), ((0, 1, 1, 0), (0.2, 0.98, 1.04, -0.05), (0.85, 0.98, 1.04, -0.05), (1, 1, 1, 0)), (("curiosity", -0.2), ("rest", -0.1)), "sleepy"), 2, "content"),
    "daydream": (_act("sit", (10.0, 20.0), ((0, 1, 1, 0), (0.2, 1, 0.98, 0.02), (1, 1, 0.98, 0.02)), (("rest", -0.2),), "sleepy"), 2, "sleepy"),
    "puzzle": (_act("look", (5.0, 9.0), ((0, 1, 1, 0), (0.2, 0.98, 0.99, -0.04), (0.55, 0.98, 0.99, 0.04), (1, 1, 1, 0)), (("curiosity", -0.2),), "curious"), 2, "focus"),
}
#: What the menu says it is doing during a prop, spell or plain act (INBOX 1718 b: a figure holding a gridded panel
#: gave no hint it was reading a map). Acts not listed read as their own name, spaces for underscores.
DOING = {
    "read_book": "reading a book", "lounge_beanbag": "lounging on a beanbag", "go_fishing": "fishing", "push_ups": "doing push-ups",
    "read_map": "reading a map", "hold_lantern": "holding a lantern", "lift_weights": "lifting weights", "sip_tea": "sipping tea",
    "write_journal": "writing in a journal", "watch_stars": "watching the stars", "blanket_nap": "napping under a blanket",
    "water_plant": "watering a plant", "stargaze": "stargazing", "daydream": "daydreaming", "puzzle": "working on a puzzle",
    "eat_dinner": "eating dinner", "sit_chair": "sitting on a chair", "card_nap": "napping on a note card", "blow_bubbles": "blowing bubbles", "knit_starlight": "knitting a strand of starlight",
}
#: Act name -> the face it wears for its length (the props' and the plain ones'), added to `faces.ACT_FACES`.
_REGISTERED: set[str] = set()


def register() -> None:
    """Add the acts to the mind's tables once (the engine calls it at import)."""
    if _REGISTERED:
        return
    _REGISTERED.add(__name__)
    for name, (spec, act, weight) in PROP_ACTS.items():
        _add(name, act, weight, spec.face)
    for name, (act, weight, face) in PLAIN_ACTS.items():
        _add(name, act, weight, face)
    for name, (spec, act) in SPELL_ACTS.items():
        _add(name, act, 0, spec.face)
    # E5 (c): these register after the catalogue was read, so they would carry none of its mood, energy and day weights;
    # the factor alone is theirs (their lengths and weights stay the props' own: a tea spell is minutes, a short sip is not)
    bh.FACTORED.update(n for n in (*PROP_ACTS, *SPELL_ACTS, *PLAIN_ACTS) if n in catalogue.by_desk_name())


def _add(name: str, act: bh.Activity, weight: int, face: str) -> None:
    bh.ACTIVITIES[name] = act
    bh.BASE_WEIGHT[name] = weight
    bh.AMPLITUDE[name] = bh._amplitude(act.keys)
    faces.ACT_FACES[name] = face


def spec_of(act: str | None) -> Spec | None:
    if act in PROP_ACTS:
        return PROP_ACTS[act][0]
    return SPELL_ACTS[act][0] if act in SPELL_ACTS else ACT_PROPS.get(act or "")


def _fetch(length: float) -> float:
    return FETCH if length <= 0.0 else min(FETCH, FETCH_S / length)


def view(act: str | None, u: float, now_in: float, length: float = 0.0) -> tuple[str, int, int] | None:
    """The prop to draw for `act` at `u` (0 to 1 through it) and `now_in` seconds into it: `(name, phase, size)`."""
    spec = spec_of(act) or REACT_PROPS.get(act or "")
    if spec is None or not 0.0 <= u < 1.0:
        return None
    edge = min(u, 1.0 - u) / _fetch(length)
    size = 3 if edge >= 1.0 else 2 if edge >= 0.55 else 1 if edge >= 0.2 else 0
    if not size:
        return None
    return spec.prop, int(now_in * spec.fps) % spec.steps, size


def next_step(act: str | None, u: float, length: float, now_in: float) -> float | None:
    """Seconds until the prop's picture next changes (a phase step or a size step), or None."""
    spec = spec_of(act)
    if spec is None:
        return None
    to_phase = (int(now_in * spec.fps) + 1) / spec.fps - now_in
    edge = min(u, 1.0 - u)
    f = _fetch(length)
    marks = [f * 0.2, f * 0.55, f, 1.0 - f, 1.0 - f * 0.55, 1.0 - f * 0.2]
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
    spec = next((sp_ for sp_, _a, _w in PROP_ACTS.values() if sp_.prop == name), None) or next((sp_ for sp_, _a in SPELL_ACTS.values() if sp_.prop == name), None) or WIND_SPECS.get(name) or next((r for r in (*REACT_PROPS.values(), *ACT_PROPS.values()) if r.prop == name), None)
    if spec is None or frame.box[2] <= frame.box[0]:
        return frame
    lx, t, r, b = frame.box
    h = max(1.0, float(b - t))
    d = -1 if flip else 1
    k = SIZES[size]
    m = int(h * ROOM)  # the canvas grows so a line, a plant or a sky is never cut at the picture's edge (the window keeps its place)
    cw, ch = frame.width + 2 * m, frame.height + 2 * m
    layer = Image.new("RGBA", (cw * S, ch * S), (0, 0, 0, 0))
    g = ImageDraw.Draw(layer)
    u = h / 100.0 * S * k
    ax = ((lx + r) / 2.0 + m + d * spec.at[0] * h) * S
    ay = (t + m + spec.at[1] * h) * S
    {
        "book": _book, "beanbag": _beanbag, "rod": _rod, "mat": _mat, "map": _map, "lantern": _lantern,
        "dumbbell": _dumbbell, "cup": _cup, "journal": _journal, "stars": _stars, "blanket": _blanket, "plant": _plant,
        "bowl": _bowl, "wand": _wand, "knit": _knit, "gust": _gust, "spiral": _spiral, "eddy": _eddy,
        "glasses": _glasses, "hands": _hands, "bubble": _bubble, "chair": _chair, "notecard": _notecard,
    }[name](g, ax, ay, u, d, phase)
    whole = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    whole.paste(Image.frombytes("RGBA", (frame.width, frame.height), frame.bgra, "raw", "BGRa"), (m, m))
    layer = layer.resize((cw, ch), Image.Resampling.LANCZOS)
    if spec.under:
        layer.alpha_composite(whole)
        done = layer
    else:
        done = whole
        done.alpha_composite(layer)
    return sp.Frame(cw, ch, sp.premultiplied_bgra(sp.clear_faint_alpha(done)), frame.pad_x + m, frame.pad_y + m, (lx + m, t + m, r + m, b + m))


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


def _glasses(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    """Round lenses about the eyes with a bridge between them and a glint that shifts as the page does."""
    gap, r = 4.6 * u, 4.3 * u
    for sx in (-1, 1):
        g.ellipse((x + sx * gap - r, y - r, x + sx * gap + r, y + r), fill=(*TEAL, 60), outline=(*INDIGO, 255), width=max(1, int(u * 0.9)))
        gx = x + sx * gap - r * (0.45 - 0.2 * (phase % 2))
        g.ellipse((gx - 0.7 * u, y - 0.6 * r - 0.7 * u, gx + 0.7 * u, y - 0.6 * r + 0.7 * u), fill=(*CREAM, 255))
    g.line((x - gap + r, y - 0.3 * u, x + gap - r, y - 0.3 * u), fill=(*INDIGO, 255), width=max(1, int(u * 0.9)))


def _hands(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    """Both hands flat over the eyes, the fingers showing; the second phase lets one pair of fingers part (a peek)."""
    gap, w, h = 4.6 * u, 4.6 * u, 4.0 * u
    for sx in (-1, 1):
        cx = x + sx * gap
        g.ellipse((cx - w, y - h, cx + w, y + h), fill=(*LILAC, 255), outline=(*INDIGO, 255), width=max(1, int(u * 0.8)))
        for k in (-1, 0, 1):
            g.line((cx + k * 1.8 * u, y - h * 0.9, cx + k * 1.8 * u, y - h * 0.1), fill=(*INDIGO, 200), width=max(1, int(u * 0.5)))
    if phase % 2:
        g.line((x + gap - 1.8 * u, y - h * 0.9, x + gap - 1.8 * u, y + h * 0.4), fill=(*CREAM, 255), width=max(1, int(u * 0.9)))


def _bubble(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    """A speech bubble by the head with three dots that fill in one after another (no words: the feed carries none)."""
    w, h = 12 * u, 7 * u
    g.rounded_rectangle((x - w, y - h, x + w, y + h), radius=4 * u, fill=(*CREAM, 255), outline=(*INDIGO, 255), width=max(1, int(u * 0.9)))
    g.polygon([(x - d * 6 * u, y + h - 0.5 * u), (x - d * 10 * u, y + h + 5 * u), (x - d * 2 * u, y + h - 0.5 * u)], fill=(*CREAM, 255), outline=(*INDIGO, 255))
    g.line((x - d * 5.4 * u, y + h - 0.2 * u, x - d * 2.6 * u, y + h - 0.2 * u), fill=(*CREAM, 255), width=max(1, int(u * 1.2)))
    for i in range(3):
        cx = x + (i - 1) * 6 * u
        on = i <= phase % 3
        g.ellipse((cx - 1.5 * u, y - 1.5 * u, cx + 1.5 * u, y + 1.5 * u), fill=(*(INDIGO if on else LILAC), 255))


def _beanbag(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    sag = 0.8 * (phase % 2)
    g.ellipse((x - 40 * u, y - 20 * u + sag * u, x + 40 * u, y + 12 * u), fill=(*TEAL, 255), outline=(*INDIGO, 255), width=max(1, int(u * 0.8)))
    g.arc((x - 30 * u, y - 15 * u, x + 30 * u, y + 6 * u), 200, 340, fill=(*CREAM, 200), width=max(1, int(u * 0.8)))
    g.line((x, y - 20 * u, x, y - 6 * u), fill=(*INDIGO, 160), width=max(1, int(u * 0.7)))


WOOD = (176, 128, 92)


def _chair(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    """A wooden chair seen from the side, its back behind the figure, its cushion giving a little each second beat."""
    w = max(1, int(u * 0.8))
    bx = x - d * 17 * u
    g.rounded_rectangle((bx - 3 * u, y - 36 * u, bx + 3 * u, y + 3 * u), radius=1.5 * u, fill=(*WOOD, 255), outline=(*INDIGO, 255), width=w)
    g.rounded_rectangle((bx - 4 * u, y - 38 * u, bx + 4 * u, y - 33 * u), radius=1.5 * u, fill=(*WOOD, 255), outline=(*INDIGO, 255), width=w)
    for lx in (x - 17 * u, x + 15 * u):
        g.rectangle((lx, y + 4 * u, lx + 2.6 * u, y + 17 * u), fill=(138, 96, 66, 255), outline=(*INDIGO, 255), width=w)
    g.line((x - 15 * u, y + 12 * u, x + 15 * u, y + 12 * u), fill=(*INDIGO, 200), width=w)
    g.rounded_rectangle((x - 21 * u, y, x + 21 * u, y + 5 * u), radius=1.8 * u, fill=(*WOOD, 255), outline=(*INDIGO, 255), width=w)
    sag = 0.7 * (phase % 2)
    g.rounded_rectangle((x - 17 * u, y - 3 * u + sag * u, x + 17 * u, y + 0.6 * u), radius=1.6 * u, fill=(*LILAC, 255), outline=(*INDIGO, 220), width=w)


def _notecard(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    """A note card lying flat under the sleeper, a ruled line or two on it and a folded corner; its near edge lifts a hair on the second beat."""
    w = max(1, int(u * 0.8))
    lift = 0.8 * (phase % 2)
    pts = [(x - 38 * u, y), (x + 34 * u, y - 3 * u), (x + 40 * u, y + 11 * u - lift * u), (x - 32 * u, y + 14 * u - lift * u)]
    g.polygon([(px, py + 2.2 * u) for px, py in pts], fill=(*INDIGO, 90))
    g.polygon(pts, fill=(*CREAM, 255), outline=(*INDIGO, 255))
    for k, frac in enumerate((0.38, 0.66)):
        ax, ay = x - 32 * u + 6 * u * frac, y + (3 + 8 * frac) * u
        g.line((ax - 4 * u, ay - 1.2 * u, ax + (48 - 14 * k) * u, ay - 3.2 * u - lift * 0.3 * u), fill=(*TEAL, 230), width=w)
    g.polygon([(x + 34 * u, y - 3 * u), (x + 28 * u, y - 2.6 * u), (x + 33 * u, y + 3 * u)], fill=(*LILAC, 255), outline=(*INDIGO, 255))


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


def _stars(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    """A small night sky beside the head: a crescent moon and stars that twinkle out of step."""
    g.ellipse((x - 7 * u, y - 7 * u, x + 7 * u, y + 7 * u), fill=(*WARM, 255))
    g.ellipse((x - 3 * u, y - 9 * u, x + 10 * u, y + 5 * u), fill=(0, 0, 0, 0))
    for i, (dx, dy) in enumerate(((14, -12), (20, 2), (9, 12), (24, -18), (17, -24))):
        r = (1.6 + 1.4 * (((phase + i) % 4) == 0)) * u
        cx, cy = x + d * dx * u * 0.8, y + dy * u * 0.8
        g.polygon([(cx, cy - r * 1.8), (cx + r * 0.5, cy - r * 0.5), (cx + r * 1.8, cy), (cx + r * 0.5, cy + r * 0.5), (cx, cy + r * 1.8), (cx - r * 0.5, cy + r * 0.5), (cx - r * 1.8, cy), (cx - r * 0.5, cy - r * 0.5)], fill=(*CREAM, 255 if (phase + i) % 4 else 170))


def _blanket(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    """A knitted blanket over the lap that rises and falls with the breath."""
    y -= (phase % 2) * 0.7 * u
    g.rounded_rectangle((x - 34 * u, y, x + 34 * u, y + 40 * u), radius=7 * u, fill=(*TEAL, 255), outline=(*INDIGO, 255), width=max(1, int(u * 0.8)))
    for i in range(1, 4):
        g.line((x - 34 * u + i * 17 * u, y + 2 * u, x - 34 * u + i * 17 * u, y + 38 * u), fill=(*CREAM, 150), width=max(1, int(u * 0.6)))
    for j in range(1, 3):
        g.line((x - 32 * u, y + j * 13 * u, x + 32 * u, y + j * 13 * u), fill=(*LILAC, 170), width=max(1, int(u * 0.6)))


def _plant(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    """A pot with a plant that grows a leaf a beat, and a watering can tipped over it with drops falling."""
    g.polygon([(x - 7 * u, y), (x + 7 * u, y), (x + 5 * u, y + 12 * u), (x - 5 * u, y + 12 * u)], fill=(214, 128, 96, 255), outline=(*INDIGO, 255))
    for i in range(1 + phase % 4):
        a = (i - 1.5) * 0.55
        tip = (x + math.sin(a) * 11 * u, y - (7 + 4 * (i % 2)) * u)
        g.line((x, y, *tip), fill=(96, 170, 120, 255), width=max(2, int(u * 1.1)))
        g.ellipse((tip[0] - 3 * u, tip[1] - 2.4 * u, tip[0] + 3 * u, tip[1] + 2.4 * u), fill=(120, 196, 140, 255))
    cx, cy = x - d * 13 * u, y - 24 * u
    g.rounded_rectangle((cx - 6 * u, cy - 4 * u, cx + 6 * u, cy + 5 * u), radius=2 * u, fill=(*LILAC, 255), outline=(*INDIGO, 255), width=max(1, int(u * 0.7)))
    g.line((cx + d * 6 * u, cy - 2 * u, cx + d * 13 * u, cy + 3 * u), fill=(*INDIGO, 255), width=max(2, int(u * 1.0)))
    for i in range(3):
        dy = ((phase + i) % 4) * 4 * u
        g.ellipse((cx + d * 13 * u - u, cy + 6 * u + dy, cx + d * 13 * u + u, cy + 8.5 * u + dy), fill=(*TEAL, 230))


def _bowl(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    """A bowl of supper with steam over it and a spoon that goes to the mouth and back, a beat a step."""
    lw = max(1, int(u * 0.8))
    g.chord((x - 9 * u, y - 5 * u, x + 9 * u, y + 9 * u), 0, 180, fill=(*CREAM, 255), outline=(*INDIGO, 255), width=lw)
    g.pieslice((x - 7 * u, y - 9 * u, x + 7 * u, y + 1 * u), 180, 360, fill=(*WARM, 255))
    g.line((x - 9 * u, y + 2 * u, x + 9 * u, y + 2 * u), fill=(*INDIGO, 255), width=lw)
    g.line((x - 4 * u, y + 7 * u, x + 4 * u, y + 7 * u), fill=(*LILAC, 255), width=lw)
    rise = (0.0, 5.0, 11.0, 5.0)[phase % 4]  # the spoon: in the bowl, lifted, at the mouth, coming back
    sx, sy = x + d * (4 + rise * 0.5) * u, y - (4 + rise) * u
    g.line((x + d * 2 * u, y - 4 * u, sx + d * 7 * u, sy - 6 * u), fill=(*WARM, 255), width=max(2, int(u * 1.0)))
    g.ellipse((sx - 2.4 * u, sy - 1.8 * u, sx + 2.4 * u, sy + 1.8 * u), fill=(*CREAM, 255), outline=(*INDIGO, 255), width=lw)
    for i in range(2):  # steam
        px = x + (i * 6 - 3) * u
        off = ((phase + i * 2) % 4) * 1.6 * u
        g.arc((px - 1.5 * u, y - 18 * u - off, px + 1.5 * u, y - 12 * u - off), 90, 270, fill=(*CREAM, 190), width=max(1, int(u * 0.6)))


def _wand(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    """A bubble wand held out, and three bubbles that leave its ring, drift up, grow and pop."""
    lw = max(1, int(u * 0.8))
    rx, ry = x + d * 15 * u, y - 14 * u
    g.line((x, y, rx, ry), fill=(*WARM, 255), width=max(2, int(u * 1.0)))
    g.ellipse((rx - 4 * u, ry - 6 * u, rx + 4 * u, ry + 2 * u), outline=(*INDIGO, 255), width=lw)
    for i in range(3):
        t = ((phase + i * 4 / 3) % 4) / 4.0  # how far this bubble is on its way
        bx = rx + d * (2 + 9 * t + i * 3) * u + math.sin(t * 6.0 + i) * 2 * u
        by = ry - 4 * u - t * 30 * u
        r = (1.8 + 3.0 * t) * u
        a = int(235 * (1.0 - t**3))
        g.ellipse((bx - r, by - r, bx + r, by + r), fill=(*TEAL, int(a * 0.22)), outline=(*TEAL, a), width=lw)
        g.arc((bx - r * 0.6, by - r * 0.6, bx + r * 0.6, by + r * 0.6), 200, 260, fill=(*CREAM, a), width=lw)
        if t > 0.8:  # the pop: three short strokes
            for ang in (0, 120, 240):
                ca, sa = math.cos(math.radians(ang + 30)), math.sin(math.radians(ang + 30))
                g.line((bx + ca * r * 1.2, by + sa * r * 1.2, bx + ca * r * 2.2, by + sa * r * 2.2), fill=(*CREAM, 200), width=lw)


def _knit(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    """Two crossed needles of warm light knitting a strand of starlight that hangs from them, a star running down it."""
    lw = max(1, int(u * 0.8))
    click = (phase % 2) * 1.4 * u  # the needles tap together a beat apart
    g.line((x - 12 * u, y + 7 * u, x + 13 * u, y - 8 * u + click), fill=(*WARM, 255), width=max(2, int(u * 1.1)))
    g.line((x - 13 * u, y - 7 * u + click, x + 12 * u, y + 8 * u), fill=(*WARM, 255), width=max(2, int(u * 1.1)))
    for sx, sy in ((x + 13 * u, y - 8 * u + click), (x + 12 * u, y + 8 * u)):
        g.ellipse((sx - 1.6 * u, sy - 1.6 * u, sx + 1.6 * u, sy + 1.6 * u), fill=(*CREAM, 255), outline=(*INDIGO, 255), width=lw)
    pts = [(x + math.sin(i * 1.7 + phase * 0.5) * 2.2 * u, y + 6 * u + i * 4.5 * u) for i in range(6)]
    g.line(pts, fill=(*LILAC, 255), width=max(2, int(u * 1.5)))
    for i, (px, py) in enumerate(pts):  # stitches
        g.line((px - 3 * u, py, px + 3 * u, py + 1.2 * u), fill=(*TEAL, 220), width=lw)
    r = 2.2 * u  # a star runs down the strand
    px, py = pts[phase % 4 + 1]
    g.polygon([(px, py - r * 1.8), (px + r * 0.5, py - r * 0.5), (px + r * 1.8, py), (px + r * 0.5, py + r * 0.5), (px, py + r * 1.8), (px - r * 0.5, py + r * 0.5), (px - r * 1.8, py), (px - r * 0.5, py - r * 0.5)], fill=(*CREAM, 255))


def _gust(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    """The wind it rides: streaks and motes streaming behind it (to the way it faces), each a beat further along."""
    lw = max(1, int(u * 0.9))
    for i in range(5):
        run = (phase * 3 + i * 5) % 14  # how far back this one has been blown
        sx = x - d * (24 + run * 2.4 + i * 3) * u
        sy = y + (i - 2) * 11 * u + math.sin(phase + i) * 1.5 * u
        a = int(230 * (1.0 - run / 14.0))
        g.line((sx, sy, sx - d * (9 + (i % 2) * 5) * u, sy), fill=(*(LILAC if i % 2 else TEAL), a), width=lw)
        g.ellipse((sx + d * 3 * u - u, sy - 5 * u - u, sx + d * 3 * u + u, sy - 5 * u + u), fill=(*CREAM, a))


def _spiral(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    """A spiral of wind round the figure that turns a quarter a step: the gust curling as it turns about."""
    lw = max(1, int(u * 1.0))
    pts = []
    for i in range(0, 37):
        th = i / 36.0 * 3.0 * math.pi + phase * math.pi / 2.0
        r = (12 + 22 * i / 36.0) * u
        pts.append((x + math.cos(th) * r * d, y + math.sin(th) * r * 0.8))
    for a, b in zip(pts, pts[1:]):
        g.line((*a, *b), fill=(*LILAC, 200), width=lw)
    g.ellipse((pts[-1][0] - 1.6 * u, pts[-1][1] - 1.6 * u, pts[-1][0] + 1.6 * u, pts[-1][1] + 1.6 * u), fill=(*CREAM, 235))


def _eddy(g: Any, x: float, y: float, u: float, d: int, phase: int) -> None:
    """The settle: a small whirl at its feet that widens and thins as the air lets it down."""
    lw = max(1, int(u * 0.9))
    r = (12 + phase * 6) * u
    a = 230 - phase * 55
    g.ellipse((x - r, y - r * 0.28, x + r, y + r * 0.28), outline=(*TEAL, a), width=lw)
    g.ellipse((x - r * 0.6, y - r * 0.17, x + r * 0.6, y + r * 0.17), outline=(*LILAC, a), width=lw)
    for i in range(3):
        th = phase * 0.9 + i * 2.1
        g.ellipse((x + d * math.cos(th) * r * 0.9 - u, y + math.sin(th) * r * 0.25 - 2 * u - u, x + d * math.cos(th) * r * 0.9 + u, y + math.sin(th) * r * 0.25 - 2 * u + u), fill=(*CREAM, a))
