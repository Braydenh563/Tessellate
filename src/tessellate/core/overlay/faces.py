"""A face layer over the desk figure (INBOX 1683 ask M5: "really detailed micro expressions and transitions").

The shipped frames carry one face (a calm one), and a pose warp only squashes and leans it. This draws the rest
of an expression over the warped frame: the brows, the lids, the mouth, a blush. Pure Pillow, no state: the
engine says `(kind, level)` (`Output.face`), the level easing 1, 2, 3, 2, 1 so a look arrives and leaves instead
of snapping, and `Micro` is the seeded scheduler of the small unprompted ones a still figure makes (a brow lift,
a half-lid, a flicker of a smile). Everything is placed from the eye box the lids already use
(`sprites.LID_EYES`), found again in each frame by matching, so a sit or a wave is a few px off and still right.
"""

from __future__ import annotations

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
BROW_UP, BROW_LEN = 9.0, 11.0
MOUTH_DOWN = 13.0
#: Supersampling of the head patch.
UP = 4


class Look(NamedTuple):
    """One expression. `brow` tilts the inner ends (positive up, worried), `lift` raises both brows (px),
    `lid` closes the eyes from the top (0 open, 1 shut), `smile` curves the mouth (negative frowns), `open` is
    an o mouth's height (px), `arc` shuts the eyes as happy arcs, `blush` reddens the cheeks, `askew` raises
    one brow more than the other (px, left is the figure's)."""

    brow: float = 0.0
    lift: float = 0.0
    lid: float = 0.0
    smile: float = 0.0
    open: float = 0.0
    arc: float = 0.0
    blush: float = 0.0
    askew: float = 0.0


EXPRESSIONS: dict[str, Look] = {
    "smile": Look(lift=1.0, smile=4.0, blush=0.4),
    "joy": Look(lift=2.0, smile=6.0, arc=1.0, blush=0.8),
    "worried": Look(brow=5.0, lift=2.0, smile=-3.0),
    "miffed": Look(brow=-5.0, lift=-1.5, smile=-2.5, lid=0.25),
    "curious": Look(lift=3.0, askew=3.0, smile=1.0),
    "sleepy": Look(lid=0.6, smile=0.5, lift=-1.0),
    "surprised": Look(lift=4.5, open=5.0),
    "focus": Look(brow=-2.5, lift=-1.0, smile=-0.5),
    "content": Look(lid=0.35, smile=3.5, blush=0.5),
    "proud": Look(lift=2.0, smile=3.0, lid=0.15),
    "strain": Look(brow=-4.0, lift=-1.0, smile=-1.5, open=2.0, lid=0.2),
    "smirk": Look(askew=2.5, smile=2.5, lid=0.2),
}
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
    "peek_down": "curious", "pose_proud": "proud", "shake_off": "surprised", "wave_idle": "smile", "float_loop": "joy",
    "nod": "smile", "shrug": "smirk", "doze": "sleepy", "crouch_watch": "focus", "sit_down": "content",
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
    if name not in FACE_FRAMES:
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
    look = EXPRESSIONS.get(kind)
    at = head_point(spr, name, plain or base, flip, pose)
    if look is None or at is None or not 0 < level < len(LEVELS):
        return base
    from PIL import Image, ImageDraw

    cx, cy, k = at
    f = LEVELS[level]
    pad = int(28 * k)
    left, top = max(0, int(cx - pad)), max(0, int(cy - 20 * k))
    right, bottom = min(base.width, int(cx + pad)), min(base.height, int(cy + 26 * k))
    if right <= left or bottom <= top:
        return base
    whole = Image.frombytes("RGBA", (base.width, base.height), base.bgra, "raw", "BGRa")
    patch = whole.crop((left, top, right, bottom)).resize(((right - left) * UP, (bottom - top) * UP), Image.Resampling.LANCZOS)
    g = ImageDraw.Draw(patch)
    _features(g, patch, ((cx - left) * UP, (cy - top) * UP), k * UP, look, f, flip)
    here = patch.resize((right - left, bottom - top), Image.Resampling.LANCZOS)
    done = whole.crop((left, top, right, bottom))
    done.alpha_composite(here)
    return _splice(base, sp.premultiplied_bgra(sp.clear_faint_alpha(done)), left, top, right, bottom)


def _features(g: Any, patch: Any, at: tuple[float, float], u: float, look: Look, f: float, flip: bool) -> None:
    """The eyes, brows and mouth of `look` at strength `f`, drawn on the 4x patch about `at` (u: shipped px to patch px)."""
    ox, oy = at
    gap = 10.0  # each eye's centre, px from the middle (the lid box's quarter points)
    skin = _skin(patch, ox, oy)
    ink = (*INK, int(230 * min(1.0, f + 0.2)))
    sign = -1 if flip else 1
    for side in (-1, 1):
        ex = ox + side * gap * u
        if look.arc * f > 0.3 or look.lid * f > 0.05:
            _lid(g, ex, oy, u, look, f, skin, ink)
        if look.brow or look.lift or look.askew:
            _brow(g, ex, oy, u, side, side * sign > 0, look, f, ink)
    if look.smile or look.open or look.blush:
        _mouth(g, ox, oy + MOUTH_DOWN * u, u, look, f, skin, ink)


def _brow(g: Any, ex: float, oy: float, u: float, side: int, raised_side: bool, look: Look, f: float, ink: tuple) -> None:
    brow_y = oy - (BROW_UP + look.lift * f + (look.askew * f if raised_side else 0.0)) * u
    tilt = look.brow * f * u
    x_in, x_out = ex - side * 0.2 * BROW_LEN * u, ex + side * 0.55 * BROW_LEN * u
    g.line((x_out, brow_y, x_in, brow_y - tilt), fill=ink, width=max(2, int(1.5 * u)))


def _splice(base: sp.Frame, rows: bytes, left: int, top: int, right: int, bottom: int) -> sp.Frame:
    """`base` with only the head's rectangle rewritten from `rows`: every other byte is the base's own."""
    out = bytearray(base.bgra)
    for y in range(bottom - top):
        a = ((top + y) * base.width + left) * 4
        out[a:a + (right - left) * 4] = rows[y * (right - left) * 4:(y + 1) * (right - left) * 4]
    return sp.Frame(base.width, base.height, bytes(out), base.pad_x, base.pad_y, base.box)


def _lid(g: Any, ex: float, ey: float, u: float, look: Look, f: float, skin: tuple, ink: tuple) -> None:
    rx, ry = 7.5 * u, 6.5 * u
    if look.arc:  # happy shut eyes: skin over the eye, an upward arc on it
        g.ellipse((ex - rx, ey - ry, ex + rx, ey + ry), fill=skin)
        g.arc((ex - rx * 0.8, ey - ry * 0.7, ex + rx * 0.8, ey + ry * 0.9), 200, 340, fill=ink, width=max(2, int(1.6 * u)))
        return
    drop = look.lid * f * 2 * ry  # the lid comes down over the top of the eye
    g.pieslice((ex - rx, ey - ry, ex + rx, ey + ry), 180, 360, fill=skin) if drop >= 2 * ry * 0.9 else g.rectangle(
        (ex - rx, ey - ry, ex + rx, ey - ry + drop), fill=skin
    )
    g.line((ex - rx * 0.9, ey - ry + drop, ex + rx * 0.9, ey - ry + drop), fill=ink, width=max(2, int(1.2 * u)))


def _mouth(g: Any, mx: float, my: float, u: float, look: Look, f: float, skin: tuple, ink: tuple) -> None:
    w = 5.5 * u
    g.ellipse((mx - w * 1.5, my - 3.5 * u, mx + w * 1.5, my + 4.5 * u), fill=skin)  # the calm mouth the art has
    if look.blush:
        a = int(110 * look.blush * f)
        for side in (-1, 1):
            g.ellipse((mx + side * 17 * u - 5 * u, my - 6 * u, mx + side * 17 * u + 5 * u, my + 1 * u), fill=(236, 150, 168, a))
    s = look.smile * f * u
    if look.open:
        h = look.open * f * u
        g.ellipse((mx - 2.6 * u, my - h * 0.4, mx + 2.6 * u, my + h * 0.6), fill=(*INK, 235))
    elif abs(s) > 0.3 * u:
        top, bot = (my - 1.5 * u, my + s) if s > 0 else (my + s * 0.3, my - s * 0.2)
        if s > 0:
            g.arc((mx - w, my - s * 1.6, mx + w, my + s * 0.7), 20, 160, fill=ink, width=max(2, int(1.3 * u)))
        else:
            g.arc((mx - w, my + s * -0.2, mx + w, my - s * 1.6 + 2 * u), 200, 340, fill=ink, width=max(2, int(1.3 * u)))
    else:
        g.line((mx - w * 0.6, my, mx + w * 0.6, my), fill=ink, width=max(2, int(1.2 * u)))
