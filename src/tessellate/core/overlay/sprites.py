"""The overlay's frames: pre-rendered Atlas, loaded, mirrored and scaled for
the window (BACKLOG 16, O2).

The frames are PNGs under `frontend/img/desk/<look>/<frame>.png`, made by
`scripts/render_desk_frames.py` from the live figure (transparent background,
device scale 2, every frame of a look cropped to the same box so they stay
registered) and shipped with the app. Here they are turned into what
`UpdateLayeredWindow` wants: premultiplied BGRA, by Pillow's raw `BGRa` mode
(never per-pixel Python).

**The halo guard.** A layered window takes clicks on every pixel whose alpha is
above 0, so an antialiased fringe or a soft shadow is an invisible ring that
eats clicks meant for what is under it. Alpha below `ALPHA_FLOOR` (8 of 255) is
zeroed, after every resize too (resampling makes new faint pixels).

Pillow is in the `desktop` extra, not the base install: imported here on use.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, NamedTuple

logger = logging.getLogger(__name__)

LOOKS = ("masculine", "feminine")
#: The idle cycle a standing figure draws (`engine.IDLE_FRAMES` of them, at `engine.IDLE_FPS`):
#: tail beat and breath sampled from the live rig by `scripts/render_desk_frames.js`. 24 in-betweens
#: (was 12, INBOX 1670: "very framey"); a shipped set of 12 still runs (see `SpriteSet.idle_count`).
IDLE_COUNT = 24
OLD_IDLE_COUNT = 12
IDLE_FRAMES = tuple(f"idle{i}" for i in range(IDLE_COUNT))
#: The float or walk cycle: 12 frames (was 6) so a cycle of travel changes the picture every 3.5 px
#: of it, not every 7. A shipped set of 6 still runs (`SpriteSet.walk_count`).
WALK_COUNT = 12
OLD_WALK_COUNT = 6
#: Every frame of a look, in the order they are rendered. Walking is `walk0` to
#: `walk11`; the others are what the engine's states draw. `card0` and `card1` are the
#: figure holding a reminder's card (`scripts/render_card_frames.py`, Pillow, from
#: `stand` and `wave`).
FRAME_NAMES = (
    "stand", "blink", "look",
    *(f"walk{i}" for i in range(WALK_COUNT)),
    "sit", "sleep", "wave", "held", "fall", "land", "hop", "hang", "tumble",
    "card0", "card1",
    *IDLE_FRAMES,
)
#: Drawn by `scripts/render_card_frames.py`, not captured from the app.
CARD_FRAMES = ("card0", "card1")
WALK_FRAMES = tuple(f"walk{i}" for i in range(WALK_COUNT))
#: Rotated copies of the "tumble" frame, for a thrown figure: `spin0` to `spin7`
#: are 45 degree steps. Built once per dpi (and flip) with Pillow, then cached.
SPIN_STEPS = 8
SPIN_FRAMES = tuple(f"spin{i}" for i in range(SPIN_STEPS))
SPIN_BASE = "tumble"
#: "float" (Atlas, a wisp for a lower body: hovers and drifts) or "walk".
GAITS = {"masculine": "float", "feminine": "float"}
#: Pixels around the solid body that stay the frame's own (its soft edge), at the shipped scale.
CORE_GROW = 5
#: Posed frames kept (a pose is a squash, a lean, a lag): the least recently used go.
POSED_KEEP = 40
#: Horizontal strips a pose is warped in.
POSE_STRIPS = 24
#: Alpha under this is clear: the click-through guard.
ALPHA_FLOOR = 8
#: The shipped frames are at twice the CSS pixel size.
SOURCE_SCALE = 2.0


class Frame(NamedTuple):
    width: int
    height: int
    #: Premultiplied BGRA, top-down, `width * height * 4` bytes.
    bgra: bytes
    #: How far the picture's origin is up and left of the figure's own box: a
    #: rotated frame is on a bigger canvas, so the window moves back by this much.
    pad_x: int = 0
    pad_y: int = 0
    #: The drawn pixels' box in this picture (left, top, right, bottom; alpha at the floor
    #: or more), so the quick panel is placed from the figure, not from the window around it
    #: (INBOX 1663: the figure's margin varies by pose and mirror, 8 to 110 px).
    box: tuple[int, int, int, int] = (0, 0, 0, 0)


def clipped(frame: Frame, clip: tuple[int, int, int, int] | None) -> Frame:
    """The frame with everything outside `clip` (left, top, right, bottom) clear.
    Clear pixels take no clicks (the halo guard's rule), so a figure sunk behind
    an edge cannot be clicked where it is hidden. Byte slicing, no Pillow."""
    if clip is None:
        return frame
    w, h = frame.width, frame.height
    left, top = max(0, clip[0]), max(0, clip[1])
    right, bottom = min(w, clip[2]), min(h, clip[3])
    if (left, top, right, bottom) == (0, 0, w, h):
        return frame
    out = bytearray(w * h * 4)
    if right > left and bottom > top:
        for row in range(top, bottom):
            a, b = (row * w + left) * 4, (row * w + right) * 4
            out[a:b] = frame.bgra[a:b]
    return frame._replace(bgra=bytes(out))


def frames_dir() -> Path:
    """`frontend/img/desk`, in a checkout or a bundled build."""
    from tessellate.api.app import FRONTEND_DIR

    return Path(FRONTEND_DIR) / "img" / "desk"


def look_for(name: Any) -> str:
    """A frame set for a look name: anything but feminine is the masculine set."""
    return "feminine" if str(name).strip().lower() == "feminine" else "masculine"


def clear_faint_alpha(image: Any) -> Any:
    """The halo guard: alpha below `ALPHA_FLOOR` to 0, colour with it."""
    from PIL import Image

    alpha = image.getchannel("A").point(lambda a: 0 if a < ALPHA_FLOOR else a)
    image = image.copy()
    image.putalpha(alpha)
    mask = alpha.point(lambda a: 255 if a else 0)
    return Image.composite(image, Image.new("RGBA", image.size, (0, 0, 0, 0)), mask)


def _drawn_box(image: Any) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) of the pixels a click lands on; the whole picture when empty."""
    box = image.getchannel("A").point(lambda a: 255 if a >= ALPHA_FLOOR else 0).getbbox()
    return tuple(box) if box else (0, 0, image.size[0], image.size[1])  # type: ignore[return-value]


def premultiplied_bgra(image: Any) -> bytes:
    """An RGBA image as premultiplied BGRA bytes (Pillow's raw `BGRa`)."""
    return image.convert("RGBA").tobytes("raw", "BGRa")


class SpriteSet:
    """One look's frames, scaled per dpi and cached."""

    def __init__(self, look: str, directory: Path | None = None) -> None:
        self.look = look_for(look)
        self.gait = GAITS[self.look]
        self.directory = (directory or frames_dir()) / self.look
        self._source: dict[str, Any] = {}
        self._cache: dict[tuple[str, int, bool], Frame] = {}
        self._posed: dict[tuple[str, int, bool, tuple[float, ...]], Frame] = {}

    def _has(self, name: str) -> bool:
        return (self.directory / f"{name}.png").is_file()

    def missing(self) -> list[str]:
        """What a look must have to run: the frames an older, shorter set also had."""
        extra = {*WALK_FRAMES[OLD_WALK_COUNT:], *IDLE_FRAMES[OLD_IDLE_COUNT:]}
        return [n for n in FRAME_NAMES if n not in extra and not self._has(n)]

    def walk_count(self) -> int:
        """How many frames of the walk cycle are shipped (6 or 12), for the engine's stride."""
        return WALK_COUNT if all(self._has(n) for n in WALK_FRAMES) else OLD_WALK_COUNT

    def idle_count(self) -> int:
        return IDLE_COUNT if all(self._has(n) for n in IDLE_FRAMES) else OLD_IDLE_COUNT

    def available(self) -> list[str]:
        return [n for n in FRAME_NAMES if self._has(n)]

    def _load(self, name: str) -> Any:
        if name not in self._source:
            from PIL import Image

            with Image.open(self.directory / f"{name}.png") as im:
                loaded = im.convert("RGBA")
            # as shipped: the standing family already carries one shared nebula stream (render_desk_frames.py
            # `shared_stream`); a loader-side veil swap cut it away under the body and added a step (INBOX 1670)
            self._source[name] = loaded
        return self._source[name]

    def _raw(self, name: str) -> Any:
        from PIL import Image

        with Image.open(self.directory / f"{name}.png") as im:
            return im.convert("RGBA")

    @staticmethod
    def _core(image: Any) -> Any:
        """The body and its own soft edge: solid pixels grown by `CORE_GROW` px."""
        from PIL import ImageFilter

        solid = image.getchannel("A").point(lambda a: 255 if a >= 250 else 0)
        return solid.filter(ImageFilter.MaxFilter(CORE_GROW * 2 + 1))

    def top_share(self, name: str = "hang") -> float:
        """How much of a frame's height is clear above its first drawn row, measured from
        the shipped picture at load (INBOX 1660: the hang frame's hands start 57 px below
        its top, so a hang at the frame's top held nothing). A share, so it holds at any
        dpi; 0.0 when the frame is empty."""
        image = self._load(name)
        box = image.getchannel("A").point(lambda a: 255 if a >= ALPHA_FLOOR else 0).getbbox()
        return box[1] / image.size[1] if box else 0.0

    def scale_for(self, dpi: int) -> float:
        """Pixels of the window per pixel of the shipped frame at this dpi."""
        return max(0.25, min(4.0, (int(dpi) or 96) / 96.0 / SOURCE_SCALE))

    def size(self, dpi: int = 96) -> tuple[int, int]:
        """Every frame of a look is this size at this dpi."""
        width, height = self._load("stand").size
        scale = self.scale_for(dpi)
        return max(1, round(width * scale)), max(1, round(height * scale))

    def frame(self, name: str, dpi: int = 96, flip: bool = False) -> Frame:
        """The frame as premultiplied BGRA at the dpi, mirrored when `flip`
        (the shipped frames face right; walking left is the mirror)."""
        if name not in FRAME_NAMES and name not in SPIN_FRAMES:
            raise KeyError(name)
        key = (name, int(dpi), bool(flip))
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        from PIL import Image, ImageOps

        image = self._load(SPIN_BASE if name in SPIN_FRAMES else name)
        if flip:
            image = ImageOps.mirror(image)
        width, height = self.size(dpi)
        if (width, height) != image.size:
            image = image.resize((width, height), Image.Resampling.LANCZOS)
        if name in SPIN_FRAMES:
            built = self._spun(image, SPIN_FRAMES.index(name), width, height)
            self._cache[key] = built
            return built
        clear = clear_faint_alpha(image)
        built = Frame(width, height, premultiplied_bgra(clear), box=_drawn_box(clear))
        self._cache[key] = built
        return built

    def posed(self, name: str, dpi: int, flip: bool, pose: tuple[float, float, float, float]) -> Frame:
        """The frame with a body pose over it: `pose` is (sx, sy, lean, drag), see
        `behaviour.Pose`. A bottom-anchored squash or stretch, a turn-about squeeze about the
        middle, a lean (the head moves by `lean` of the height, the feet stay) and a lag of the
        lower part (the tail and wisp trail by `drag` px, growing toward the bottom), by a mesh of
        horizontal strips. Cached by the pose, `POSED_KEEP` of them; the plain frame when the pose is."""
        sx, sy, lean, drag = pose
        if (sx, sy, lean, drag) == (1.0, 1.0, 0.0, 0.0):
            return self.frame(name, dpi, flip)
        key = (name, int(dpi), bool(flip), (sx, sy, lean, drag))
        hit = self._posed.pop(key, None)
        if hit is None:
            hit = self._warp(self.frame(name, dpi, flip), self._pose_image(name, dpi, flip), sx, sy, lean, drag)
        self._posed[key] = hit  # most recent last
        while len(self._posed) > POSED_KEEP:
            del self._posed[next(iter(self._posed))]
        return hit

    def _pose_image(self, name: str, dpi: int, flip: bool) -> Any:
        from PIL import Image, ImageOps

        image = self._load(SPIN_BASE if name in SPIN_FRAMES else name)
        if flip:
            image = ImageOps.mirror(image)
        width, height = self.size(dpi)
        return image.resize((width, height), Image.Resampling.LANCZOS) if (width, height) != image.size else image

    def _warp(self, base: Frame, image: Any, sx: float, sy: float, lean: float, drag: float) -> Frame:
        from PIL import Image

        w, h = image.size
        scale = w / (self._load("stand").size[0])  # px of this dpi per px of the shipped frame
        feet = base.box[3] or h  # squash is about the feet
        mid = (base.box[0] + base.box[2]) / 2 if base.box[2] else w / 2
        step = h / POSE_STRIPS
        mesh = []
        for i in range(POSE_STRIPS):
            y0, y1 = round(i * step), round((i + 1) * step)
            ym = (y0 + y1) / 2
            lag = drag * scale * (ym / h) ** 2
            shift = lean * (feet - ym) * 0.9 - lag
            sy0, sy1 = feet + (y0 - feet) / sy, feet + (y1 - feet) / sy
            a, b = mid + (0 - mid - shift) / sx, mid + (w - mid - shift) / sx
            mesh.append(((0, y0, w, y1), (a, sy0, a, sy1, b, sy1, b, sy0)))
        warped = image.transform((w, h), Image.Transform.MESH, mesh, Image.Resampling.BILINEAR)
        clear = clear_faint_alpha(warped)
        return Frame(w, h, premultiplied_bgra(clear), box=_drawn_box(clear))

    def metrics(self, dpi: int = 96) -> dict[tuple[str, bool], tuple[int, int, int, int]]:
        """The drawn box of every frame, both mirrors, in the engine's own coordinates: from
        where the window is placed (`out.x`, `out.y`), so a rotated frame's pad is taken off.
        The engine plants feet and keeps a ride inside the work area from these (INBOX 1670)."""
        found = {}
        for name in (*self.available(), *SPIN_FRAMES):
            for flip in (False, True):
                f = self.frame(name, dpi, flip)
                left, top, right, bottom = f.box
                found[(name, flip)] = (left - f.pad_x, top - f.pad_y, right - f.pad_x, bottom - f.pad_y)
        return found

    def _spun(self, image: Any, step: int, width: int, height: int) -> Frame:
        """The picture turned by `step` x 45 degrees on a square canvas big enough
        for any angle (the diagonal), so no corner is cut; the pad tells the window
        where the figure's own box sits in it."""
        import math

        from PIL import Image

        side = math.ceil(math.hypot(width, height))
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        pad_x, pad_y = (side - width) // 2, (side - height) // 2
        canvas.paste(image, (pad_x, pad_y))
        turned = canvas.rotate(-step * 360.0 / SPIN_STEPS, resample=Image.Resampling.BICUBIC)
        clear = clear_faint_alpha(turned)
        return Frame(side, side, premultiplied_bgra(clear), pad_x, pad_y, _drawn_box(clear))


#: Alpha under this share of the picture is gone altogether: no faint ghost, and no click lands on it.
FADE_CLEAR = 0.06
#: The portal's ring (nebula violet, a lighter rim) and the puff's smoke (soft grey-white).
PORTAL_RING = (150, 110, 255)
PORTAL_RIM = (210, 190, 255)
PUFF_SMOKE = (236, 238, 244)


def mix(a: Frame, b: Frame, u: float) -> Frame | None:
    """A dissolve from `a` to `b`, `u` of the way (INBOX 1670: a pose change blends, it does not cut): both
    frames' premultiplied pixels interpolated, so a pixel solid in both stays solid (no see-through dip) and
    one only in `b` comes up as `u`. None when the two are not on the same canvas (a spin, a clipped
    frame): the caller cuts. The halo guard applies to the mix as to any frame. One C-speed Pillow blend."""
    if (a.width, a.height, a.pad_x, a.pad_y) != (b.width, b.height, b.pad_x, b.pad_y):
        return None
    from PIL import Image

    size = (a.width, a.height)
    ia = Image.frombytes("RGBA", size, a.bgra, "raw", "BGRA")
    ib = Image.frombytes("RGBA", size, b.bgra, "raw", "BGRA")
    out = Image.blend(ia, ib, max(0.0, min(1.0, u)))
    live = out.getchannel("A").point(lambda v: 255 if v >= ALPHA_FLOOR else 0)
    out = Image.composite(out, Image.new("RGBA", size, (0, 0, 0, 0)), live)
    box = live.getbbox() or (0, 0, a.width, a.height)
    return Frame(a.width, a.height, out.tobytes("raw", "BGRA"), a.pad_x, a.pad_y, box=box)


def effect(frame: Frame, fx: tuple[str, float, int] | None, alpha: float) -> Frame:
    """The frame as a vanish or an arrival shows it (INBOX 1670): the figure's alpha scaled by `alpha`
    (clear below FADE_CLEAR), with a portal ring or a puff of smoke over it. `fx` is (kind, strength 0..1,
    facing); the plain fade is `fx` None. Straight alpha through Pillow, then the halo guard, so a faint
    edge takes no click. The box stays the figure's own (the quick panel is placed from it)."""
    if fx is None and alpha >= 1.0:
        return frame
    from PIL import Image, ImageDraw, ImageFilter

    w, h = frame.width, frame.height
    image = Image.frombytes("RGBA", (w, h), frame.bgra, "raw", "BGRa")
    share = 0.0 if alpha < FADE_CLEAR else max(0.0, min(1.0, alpha))
    if share < 1.0:
        image.putalpha(image.getchannel("A").point(lambda a: int(a * share)))
    if fx is not None and fx[1] > 0.0:
        kind, strength, face = fx
        left, top, right, bottom = frame.box if frame.box[2] else (0, 0, w, h)
        cx, cy = (left + right) / 2.0, (top + bottom) / 2.0
        bw, bh = right - left, bottom - top
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        if kind == "portal":
            ox = (1 if face >= 0 else -1) * bw * 0.18
            rx, ry = bw * 0.30 * (0.5 + 0.5 * strength), bh * 0.62 * (0.6 + 0.4 * strength)
            box = (cx + ox - rx, cy - ry, cx + ox + rx, cy + ry)
            tone = max(1, int(220 * strength))
            for grow, rgb in ((10, PORTAL_RING), (5, PORTAL_RING), (0, PORTAL_RIM)):
                draw.ellipse((box[0] - grow, box[1] - grow, box[2] + grow, box[3] + grow), outline=(*rgb, tone // (1 + grow // 5)), width=3)
            layer = layer.filter(ImageFilter.GaussianBlur(1.5))
        else:
            tone = max(1, int(200 * strength))
            for dx, dy, rad in ((-0.3, 0.25, 0.30), (0.3, 0.2, 0.28), (0.0, -0.1, 0.36), (-0.2, -0.3, 0.24), (0.25, -0.3, 0.22)):
                r = max(bw, bh) * rad * (0.4 + 0.8 * strength)
                x, y = cx + dx * bw, cy + dy * bh
                draw.ellipse((x - r, y - r, x + r, y + r), fill=(*PUFF_SMOKE, tone))
            layer = layer.filter(ImageFilter.GaussianBlur(max(2.0, bw * 0.04)))
        image = Image.alpha_composite(image, layer)
    clear = clear_faint_alpha(image)
    return Frame(w, h, premultiplied_bgra(clear), frame.pad_x, frame.pad_y, frame.box)
