"""A face layer over the desk figure (INBOX 1683 ask M5: "really detailed micro expressions and transitions").

The shipped frames carry one face (a calm one), and a pose warp only squashes and leans it. This draws the rest
of an expression over the warped frame: the brows, the lids, the mouth, a blush. Pure Pillow, no state: the
engine says `(kind, level)` (`Output.face`), the level easing 1, 2, 3, 2, 1 so a look arrives and leaves instead
of snapping, and `Micro` is the seeded scheduler of the small unprompted ones a still figure makes (a brow lift,
a half-lid, a flicker of a smile). Everything is placed from the eye box the lids already use
(`sprites.LID_EYES`), found again in each frame by matching, so a sit or a wave is a few px off and still right.
"""

from __future__ import annotations

import math
import random
from typing import Any, NamedTuple

from . import sprites as sp

#: Intensity of each step of a level (0 is no face at all).
LEVELS = (0.0, 0.45, 0.8, 1.0)
#: Frames whose head is where `stand`'s is, give or take a few px (matched per frame).
FACE_FRAMES = ("stand", "look", "wave", "sit", "land", *sp.IDLE_FRAMES)
MATCH_REACH = 8
#: How far a frame's eye box may differ from `stand`'s and still be the same face (a look's eyes are turned aside).
MATCH_LIMIT, MATCH_LIMIT_LOOK = 60.0, 120.0
INK = sp.LID_INK
#: Where the parts sit from the eye line, shipped px: the brow above, the mouth below.
BROW_UP, BROW_LEN = 11.5, 11.0
#: A brow travels `LIFT_GAIN` px for each px of a look's `lift` (INBOX 1704: "why dont its actual eyebrows move": one px of lift
#: was half a px on the screen).
LIFT_GAIN = 1.4
MOUTH_DOWN = 13.0
MOUTH_W = 5.5  # half the mouth's width, shipped px
#: The eye the lids and arcs are drawn on: each eye's centre is `EYE_GAP` from the middle, the lid ellipse `EYE_RX` by `EYE_RY`; the
#: iris is `IRIS_H` tall and its top `IRIS_TOP` above the centre (shipped px), so a lid's cover is known (a half lid hides a third at most).
EYE_GAP, EYE_RX, EYE_RY = 10.0, 7.5, 6.5
IRIS_H, IRIS_TOP = 10.0, 5.0
#: The share of the way shut each step of a blink (`kind|step`, or the plain `blink` look) draws: a light lid, a half lid, shut.
SHUT = (0.0, 0.40, 0.72, 0.95)
#: Supersampling of the head patch.
UP = 4


class Look(NamedTuple):
    """One expression. `brow` tilts the inner ends (positive up, worried), `lift` raises both brows (px),
    `lid` closes the eyes from the top (0 open, 1 shut), `smile` curves the mouth (negative frowns), `open` is
    an o mouth's height (px), `arc` shuts the eyes as happy arcs, `blush` reddens the cheeks, `askew` raises
    one brow more than the other (px, left is the figure's), `spiral` swirls the eyes (dizzy), `heart` turns them to hearts (love),
    `brows` 0 draws none (a blink is lids alone). Every other look has one brow per eye, except over a happy arc."""

    brow: float = 0.0
    lift: float = 0.0
    lid: float = 0.0
    smile: float = 0.0
    open: float = 0.0
    arc: float = 0.0
    blush: float = 0.0
    askew: float = 0.0
    spiral: float = 0.0
    heart: float = 0.0
    brows: float = 1.0
    gx: float = 0.0  # the eyes' step aside (shipped px, right positive): a micro-saccade (`gaze`), over whatever else the look draws
    gy: float = 0.0


EXPRESSIONS: dict[str, Look] = {
    "smile": Look(lift=1.0, smile=4.0, blush=0.4),
    "joy": Look(lift=2.0, smile=6.0, arc=1.0, blush=0.8),
    "worried": Look(brow=5.0, lift=2.0, smile=-3.0),
    "miffed": Look(brow=-5.0, lift=-1.0, smile=-2.5, lid=0.25),
    "curious": Look(lift=3.0, askew=3.0, smile=1.0),
    "sleepy": Look(lid=0.6, smile=0.5, lift=-2.0),
    "surprised": Look(lift=4.5, open=5.0),
    "focus": Look(brow=-2.5, lift=-1.0, smile=-0.5),
    "content": Look(lid=0.3, smile=3.5, blush=0.5),
    "proud": Look(lift=2.0, smile=3.0, lid=0.15),
    "strain": Look(brow=-4.0, lift=-1.0, smile=-1.5, open=2.0, lid=0.2),
    "smirk": Look(askew=2.5, smile=2.5, lid=0.2),
    "dizzy": Look(brow=2.0, lift=1.0, open=2.5, spiral=1.0),
    # catalogue B4: the in-app moods the desk figure lacked
    "confused": Look(brow=3.5, lift=1.0, askew=3.5, smile=-1.5),
    "sad": Look(brow=6.0, lift=-0.5, lid=0.25, smile=-4.5),
    "shy": Look(brow=3.0, lift=0.5, lid=0.3, smile=1.5, blush=1.0),
    "love": Look(lift=1.5, smile=4.0, blush=1.0, heart=1.0),
    "laughing": Look(lift=2.0, smile=3.0, open=6.5, arc=1.0, blush=0.3),
    # a blink on its own: lids only, no brow and no mouth (the engine eases it in and out, `engine._blink_level`)
    "blink": Look(lid=SHUT[3], brows=0.0),
}
#: The eyes alone (`gaze~3`, a micro-saccade under no other look): nothing but the step, which `draw` fills in from `GAZE`. Not an
#: expression (it has no brow, mouth or lid to be one), so it is kept out of `EXPRESSIONS`, whose every entry the face tests walk.
EYES_ONLY = Look(brows=0.0)
#: A micro-saccade's steps: where the irises sit after one, in shipped px from where the art has them (`gaze.py` picks the next).
#: A step is about a fifth of an iris, so it reads as an eye that is alive and not as one that looked away.
GAZE = ((-1.8, 0.0), (1.8, 0.0), (0.0, -1.1), (1.3, 0.8), (-1.3, 0.8), (1.2, -0.8))
#: The easing of a level over a hold: up, held, down (step indexes into `LEVELS`).
EASE = (1, 2, 3, 2, 1)
#: A micro-expression per mood: the unprompted flicker. (kind, seconds the whole of it takes.)
MICRO = {
    "happy": (("smile", 1.6), ("curious", 1.2), ("proud", 1.4)),
    "curious": (("curious", 1.4), ("surprised", 0.9), ("focus", 1.1)),
    "sleepy": (("sleepy", 2.4), ("content", 2.0)),
    "bored": (("miffed", 1.2), ("sleepy", 1.8), ("smirk", 1.2)),
    "proud": (("proud", 1.8), ("smile", 1.4), ("smirk", 1.2)),
    "startled": (("surprised", 1.0), ("worried", 1.2)),
}
MICRO_EVERY = (6.0, 16.0)
#: What an act wears for its whole length (the prop acts name their own in `props`).
ACT_FACES = {
    "yawn": "sleepy", "stretch": "content", "little_dance": "joy", "sway": "content", "wiggle": "smile", "bounce": "smile",
    "look_around": "curious", "ponder": "curious", "scan_horizon": "curious", "glance_pointer": "curious",
    "peek_down": "curious", "pose_proud": "proud", "shake_off": "surprised", "wave_idle": "smile", "float_loop": "joy", "back_float": "content",
    "nod": "smile", "shrug": "smirk", "doze": "sleepy", "crouch_watch": "focus", "sit_down": "content",
    "groom": "content", "scratch": "smile", "snack": "content", "peer_at_cursor": "curious", "pace": "focus",
    "invent_game": "joy", "tinker": "focus", "dust_off": "surprised",
}


def level_at(u: float) -> int:
    """The step of the easing at `u` (0 to 1 through the whole look): 0 outside it."""
    if not 0.0 <= u < 1.0:
        return 0
    return EASE[min(len(EASE) - 1, int(u * len(EASE)))]


class Micro:
    """The small unprompted expressions of a still figure: one every `MICRO_EVERY` seconds, in the mood's own
    flavour, from its own seeded stream so they never shift the engine's other choices."""

    def __init__(self, rng: random.Random, now: float = 0.0) -> None:
        self.rng = rng
        self.next_at = now + rng.uniform(*MICRO_EVERY)
        self.kind = ""
        self.start = 0.0
        self.length = 0.0

    def tick(self, now: float, mood: str, able: bool) -> None:
        if self.kind and now >= self.start + self.length:
            self.kind = ""
        if not self.kind and now >= self.next_at:
            self.next_at = now + self.rng.uniform(*MICRO_EVERY)
            if able and mood in MICRO:
                self.kind, self.length = self.rng.choice(MICRO[mood])
                self.start = now

    def view(self, now: float) -> tuple[str, int] | None:
        if not self.kind:
            return None
        lv = level_at((now - self.start) / self.length)
        return (self.kind, lv) if lv else None

    def next_change(self, now: float) -> float:
        """The next time the picture of a micro-expression steps (or one may begin)."""
        if not self.kind:
            return self.next_at
        step = self.length / len(EASE)
        return self.start + (int((now - self.start) / step + 1e-9) + 1) * step


# --- drawing -------------------------------------------------------------------------------------


_anchors: dict[tuple[str, str], tuple[int, int] | None] = {}


def eye_anchor(spr: Any, name: str) -> tuple[float, float] | None:
    """The eyes' centre in the shipped frame `name` (px of the source art), or None where the face does not
    sit like `stand`'s (the frame is not one of `FACE_FRAMES`, or no match is close)."""
    # A captured figure (INBOX 1690 b) has no charted eye box: no face, rather than a KeyError that kills the overlay.
    if name not in FACE_FRAMES or spr.look not in sp.LID_EYES:
        return None
    x0, y0, x1, y1 = sp.LID_EYES[spr.look]
    key = (spr.look, name)
    if key not in _anchors:
        _anchors[key] = _match(spr, name, (x0, y0, x1, y1))
    hit = _anchors[key]
    return None if hit is None else ((x0 + x1) / 2.0 + hit[0], (y0 + y1) / 2.0 + hit[1])


def _match(spr: Any, name: str, box: tuple[int, int, int, int]) -> tuple[int, int] | None:
    from PIL import ImageChops, ImageStat

    ref = spr._load("stand").crop(box)
    if name == "stand":
        return (0, 0)
    image = spr._load(name)
    best = None
    for dy in range(-MATCH_REACH, MATCH_REACH + 1):
        for dx in range(-MATCH_REACH, MATCH_REACH + 1):
            here = image.crop((box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy))
            err = sum(ImageStat.Stat(ImageChops.difference(ref, here)).mean)
            if best is None or err < best[0]:
                best = (err, dx, dy)
    limit = MATCH_LIMIT_LOOK if name == "look" else MATCH_LIMIT
    return (best[1], best[2]) if best and best[0] <= limit else None


def head_point(spr: Any, name: str, base: sp.Frame, flip: bool, pose: tuple[float, float, float, float] | None) -> tuple[float, float, float] | None:
    """Where the eye line is on the drawn picture: `(x, y, scale)` in its px, through the same mapping the pose
    warp uses (squash about the feet, lean from them), or None where there is no face to draw on."""
    anchor = eye_anchor(spr, name)
    if anchor is None:
        return None
    src_w = spr._load("stand").size[0]
    k = base.width / src_w
    x, y = anchor[0] * k, anchor[1] * k
    if flip:
        x = base.width - x
    if pose is not None:
        sx, sy, lean, drag = pose
        feet = base.box[3] or base.height
        mid = (base.box[0] + base.box[2]) / 2.0 if base.box[2] else base.width / 2.0
        y2 = feet + (y - feet) * sy
        shift = lean * (feet - y2) * 0.9 - drag * k * (y2 / base.height) ** 2
        x, y = mid + (x - mid) * sx + shift, y2
    return x, y, k


def _skin(patch: Any, cx: float, cy: float) -> tuple[int, int, int, int]:
    """The skin tone between the eyes, from the patch (4x)."""
    px = patch.getpixel((int(cx), int(cy)))
    return (px[0], px[1], px[2], 255)


def draw(
    spr: Any, name: str, base: sp.Frame, flip: bool, pose: tuple[float, float, float, float] | None, face: tuple[str, int],
    plain: sp.Frame | None = None,
) -> sp.Frame:
    """`base` (the posed frame) with the expression `face` drawn on it; `base` itself where there is no face to
    draw. `plain` is the same frame before the pose, whose box the pose warp is about (`base` when not given)."""
    kind, level = face
    kind, _bar, shut = kind.partition("|")  # `smile|2`: the look with its lids at step 2 of a blink
    kind, _tilde, step = kind.partition("~")  # `smile~3`: the look with its eyes at step 3 of `GAZE` (`gaze~3`: the eyes alone)
    look = EYES_ONLY if kind == "gaze" else EXPRESSIONS.get(kind)
    if look is not None and step.isdigit() and int(step) < len(GAZE):
        look = look._replace(gx=GAZE[int(step)][0], gy=GAZE[int(step)][1])
    at = head_point(spr, name, plain or base, flip, pose)
    if look is None or at is None or not 0 < level < len(LEVELS):
        return base
    from PIL import Image, ImageDraw

    cx, cy, k = at
    f = LEVELS[level]
    pad = int(28 * k)
    left, top = max(0, int(cx - pad)), max(0, int(cy - 26 * k))
    right, bottom = min(base.width, int(cx + pad)), min(base.height, int(cy + 26 * k))
    if right <= left or bottom <= top:
        return base
    whole = Image.frombytes("RGBA", (base.width, base.height), base.bgra, "raw", "BGRa")
    patch = whole.crop((left, top, right, bottom)).resize(((right - left) * UP, (bottom - top) * UP), Image.Resampling.LANCZOS)
    g = ImageDraw.Draw(patch)
    _features(g, patch, ((cx - left) * UP, (cy - top) * UP), k * UP, look, f, flip, SHUT[int(shut)] if shut.isdigit() else 0.0)
    here = patch.resize((right - left, bottom - top), Image.Resampling.LANCZOS)
    done = whole.crop((left, top, right, bottom))
    done.alpha_composite(here)
    return _splice(base, sp.premultiplied_bgra(sp.clear_faint_alpha(done)), left, top, right, bottom)


def _features(g: Any, patch: Any, at: tuple[float, float], u: float, look: Look, f: float, flip: bool, shut: float = 0.0) -> None:
    """The eyes, brows and mouth of `look` at strength `f`, drawn on the 4x patch about `at` (u: shipped px to patch px).
    `shut` closes the lids that far over whatever the look has (a blink under an expression). One brow per eye, and none
    over a happy arc: the arc is that eye's line (INBOX 1704: a brow drawn over an arc read as a second brow)."""
    ox, oy = at
    skin = _skin(patch, ox, oy)
    ink = (*INK, int(230 * min(1.0, f + 0.2)))
    if look.gx or look.gy:  # first: the lids, brows and arcs below are drawn over the stepped eye
        for side in (-1, 1):
            _step_eye(patch, ox + side * EYE_GAP * u, oy, u, look.gx, look.gy)
    for side in (-1, 1):
        _eye(g, patch, ox + side * EYE_GAP * u, oy, u, side, side * (-1 if flip else 1) > 0, look, f, shut, skin, ink)
    if look.smile or look.open or look.blush:
        _mouth(g, patch, ox, oy + MOUTH_DOWN * u, u, look, f, ink)


def _step_eye(patch: Any, ex: float, ey: float, u: float, gx: float, gy: float) -> None:
    """The eye's own picture moved `gx`, `gy` shipped px: the art's iris and its glints go with it, the rest of the face stays. The
    copy is the eye's ellipse (a little under the lids' box, so the lash line is not doubled) with a feathered edge."""
    from PIL import Image, ImageDraw, ImageFilter

    rx, ry, pad = EYE_RX * 0.95 * u, EYE_RY * 0.9 * u, int(2 * u)
    x0, y0 = max(0, int(ex - rx) - pad), max(0, int(ey - ry) - pad)
    x1, y1 = min(patch.width, int(ex + rx) + pad), min(patch.height, int(ey + ry) + pad)
    if x1 <= x0 or y1 <= y0:
        return
    mask = Image.new("L", (x1 - x0, y1 - y0), 0)
    ImageDraw.Draw(mask).ellipse((ex - rx - x0, ey - ry - y0, ex + rx - x0, ey + ry - y0), fill=255)
    patch.paste(patch.crop((x0, y0, x1, y1)), (x0 + round(gx * u), y0 + round(gy * u)), mask.filter(ImageFilter.GaussianBlur(0.5 * u)))


def _eye(g: Any, patch: Any, ex: float, oy: float, u: float, side: int, raised: bool, look: Look, f: float, shut: float, skin: tuple, ink: tuple) -> None:
    """One eye of `look` (its spiral, heart, arc or lid) and its brow."""
    arc = look.arc * f > 0.3 and shut < 0.5
    if look.spiral * f > 0.3 and shut < 0.5:
        _spiral(patch, g, ex, oy, u, f, skin, ink)
    elif look.heart * f > 0.3 and shut < 0.5:
        _heart(patch, g, ex, oy, u, skin)
    elif arc or max(look.lid * f, shut) > 0.05:
        _lid(patch, g, ex, oy - (look.lift * f * 0.5 * u if arc else 0.0), u, arc, max(look.lid * f, shut), skin, ink)
    if look.brows and not arc:
        _brow(g, ex, oy, u, side, raised, look, f, ink)


def _brow(g: Any, ex: float, oy: float, u: float, side: int, raised_side: bool, look: Look, f: float, ink: tuple) -> None:
    """The brow: a short arch over the eye, `BROW_UP` above it at rest, raised by `lift` (and `askew` on one side), the inner end
    tilted by `brow` (up worried, down cross). Softer than the lash line, so it is a brow and not a second lid."""
    brow_y = oy - (BROW_UP + (look.lift * f + (look.askew * f if raised_side else 0.0)) * LIFT_GAIN) * u
    tilt = look.brow * f * u * 0.5
    x_in, x_out = ex - side * 0.2 * BROW_LEN * u, ex + side * 0.55 * BROW_LEN * u
    x_mid = (x_in + x_out) / 2.0
    pts = [(x_out, brow_y + 0.5 * u), (x_mid, brow_y - 0.6 * u - tilt * 0.5), (x_in, brow_y - tilt)]
    g.line(pts, fill=(*ink[:3], int(ink[3] * 0.85)), width=max(2, int(1.4 * u)), joint="curve")


def _splice(base: sp.Frame, rows: bytes, left: int, top: int, right: int, bottom: int) -> sp.Frame:
    """`base` with only the head's rectangle rewritten from `rows`: every other byte is the base's own."""
    out = bytearray(base.bgra)
    for y in range(bottom - top):
        a = ((top + y) * base.width + left) * 4
        out[a:a + (right - left) * 4] = rows[y * (right - left) * 4:(y + 1) * (right - left) * 4]
    return sp.Frame(base.width, base.height, bytes(out), base.pad_x, base.pad_y, base.box)


def _cover(patch: Any, ex: float, ey: float, u: float, skin: tuple, below: float | None = None) -> None:
    """Skin over the eye (`EYE_RX` by `EYE_RY`) with a feathered edge, down to `below` (patch y) when only the lid part is
    covered: a flat disc of one tone sat lighter than the shading round it and showed as a round patch (INBOX 1704)."""
    from PIL import Image, ImageDraw, ImageFilter

    rx, ry = EYE_RX * u, EYE_RY * u
    pad = int(3 * u)
    x0, y0 = max(0, int(ex - rx) - pad), max(0, int(ey - ry) - pad)
    x1, y1 = min(patch.width, int(ex + rx) + pad), min(patch.height, int(ey + ry) + pad)
    if x1 <= x0 or y1 <= y0:
        return
    mask = Image.new("L", (x1 - x0, y1 - y0), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((ex - rx - x0, ey - ry - y0, ex + rx - x0, ey + ry - y0), fill=255)
    if below is not None:
        d.rectangle((0, below - y0, x1 - x0, y1 - y0), fill=0)
    patch.paste(Image.new("RGBA", mask.size, skin), (x0, y0), mask.filter(ImageFilter.GaussianBlur(0.6 * u)))


def _heart(patch: Any, g: Any, ex: float, ey: float, u: float, skin: tuple) -> None:
    """A loving eye: skin over it and a small pink heart (two lobes and a point)."""
    _cover(patch, ex, ey, u, skin)
    pink, r = (226, 72, 112, 240), 3.1 * u
    for side in (-1, 1):
        g.ellipse((ex + side * 2.6 * u - r, ey - 1.6 * u - r, ex + side * 2.6 * u + r, ey - 1.6 * u + r), fill=pink)
    g.polygon([(ex - 5.6 * u, ey - 0.6 * u), (ex + 5.6 * u, ey - 0.6 * u), (ex, ey + 5.6 * u)], fill=pink)


def _spiral(patch: Any, g: Any, ex: float, ey: float, u: float, f: float, skin: tuple, ink: tuple) -> None:
    """A dizzy eye: skin over it and two turns of a spiral winding out from its middle."""
    _cover(patch, ex, ey, u, skin)
    rx, ry = EYE_RX * u, EYE_RY * u
    steps = 28
    pts = []
    for i in range(steps + 1):
        a, r = 4.0 * math.pi * i / steps, 0.9 * i / steps
        pts.append((ex + rx * r * math.cos(a), ey + ry * r * math.sin(a)))
    g.line(pts, fill=ink, width=max(2, int(1.1 * u)))


def _lid(patch: Any, g: Any, ex: float, ey: float, u: float, arc: bool, closure: float, skin: tuple, ink: tuple) -> None:
    """A happy arc, or a lid `closure` of the way down (0 open, 1 shut). The lid line is the lash line, thin and lighter than
    the ink of a brow, and sits inside the eye's box; both eyes are drawn by the same call, so they close alike."""
    rx, ry = EYE_RX * u, EYE_RY * u
    if arc:  # happy shut eyes: skin over the eye, an upward arc on it
        _cover(patch, ex, ey, u, skin)
        g.arc((ex - rx * 0.8, ey - ry * 0.7, ex + rx * 0.8, ey + ry * 0.9), 200, 340, fill=ink, width=max(2, int(1.6 * u)))
        return
    drop = closure * 2 * ry  # the lid comes down over the top of the eye
    shut = drop >= 2 * ry * 0.9
    _cover(patch, ex, ey, u, skin, None if shut else ey - ry + drop)
    line = (*ink[:3], int(ink[3] * 0.8))
    if shut:  # shut: the lash line curves along the lower lid, as the shipped blink's does
        g.arc((ex - rx * 0.8, ey - ry * 0.9, ex + rx * 0.8, ey + ry * 0.9), 20, 160, fill=line, width=max(2, int(1.3 * u)))
    else:
        y = ey - ry + drop
        g.line((ex - rx * 0.85, y, ex + rx * 0.85, y), fill=line, width=max(2, int(1.0 * u)))


def _erase_mouth(patch: Any, mx: float, my: float, u: float) -> None:
    """The calm mouth the art has, painted out from the face around it, not with one flat tone: each row runs
    from the skin just left of the mouth to the skin just right of it, and the edge is feathered (INBOX 1696
    hh, the owner: "white paste around its mouth": a flat disc of the between-the-eyes tone sat lighter than
    the chin's shading, with a hard edge)."""
    from PIL import Image, ImageDraw, ImageFilter

    w = 5.5 * u * 1.3
    x0, x1 = int(mx - w) - int(2 * u), int(mx + w) + int(2 * u)
    y0, y1 = int(my - 3.5 * u), int(my + 4.5 * u)
    width, height = x1 - x0, y1 - y0
    if width < 8 or height < 4 or x0 < 3 or x1 + 3 > patch.width or y1 > patch.height:
        return
    left = patch.crop((x0 - 3, y0, x0, y1)).resize((1, height), Image.Resampling.BOX).resize((width, height))
    right = patch.crop((x1, y0, x1 + 3, y1)).resize((1, height), Image.Resampling.BOX).resize((width, height))
    across = Image.linear_gradient("L").transpose(Image.Transpose.ROTATE_90).resize((width, height))
    fill = Image.composite(right, left, across)
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).ellipse((int(2 * u), 0, width - int(2 * u), height - 1), fill=255)
    patch.paste(fill, (x0, y0), mask.filter(ImageFilter.GaussianBlur(1.0 * u)))


def _mouth(g: Any, patch: Any, mx: float, my: float, u: float, look: Look, f: float, ink: tuple) -> None:
    """The mouth keeps its corners at `my` and its width at `MOUTH_W` through every look and every step of an easing; only the
    middle dips (a smile) or rises (a frown) or opens (an o), so it never jumps about (INBOX 1704: "mouth animations look off")."""
    w = MOUTH_W * u
    _erase_mouth(patch, mx, my, u)
    if look.blush:
        a = int(110 * look.blush * f)
        for side in (-1, 1):
            g.ellipse((mx + side * 17 * u - 5 * u, my - 6 * u, mx + side * 17 * u + 5 * u, my + 1 * u), fill=(236, 150, 168, a))
    s = look.smile * f
    width = max(2, int(1.3 * u))
    if look.open:
        h = look.open * f * u
        hw = (2.6 + max(0.0, look.smile) * 0.6) * u  # a laugh opens wide
        g.ellipse((mx - hw, my - 1.0 * u, mx + hw, my - 1.0 * u + max(2.0 * u, h)), fill=(*INK, 235))
    else:
        dip = 0.5 * max(-2.0, min(8.0, s)) * u if abs(s) > 0.3 else 0.0
        pts = [(mx + w * x / 6.0, my + dip * (1 - (x / 6.0) ** 2)) for x in range(-6, 7)]
        g.line(pts, fill=ink, width=width, joint="curve")


