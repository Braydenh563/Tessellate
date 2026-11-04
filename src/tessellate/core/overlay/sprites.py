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
#: Every frame of a look, in the order they are rendered. Walking is `walk0` to
#: `walk5`; the others are what the engine's states draw.
FRAME_NAMES = (
    "stand", "blink", "look",
    "walk0", "walk1", "walk2", "walk3", "walk4", "walk5",
    "sit", "sleep", "wave", "held", "fall", "land", "hop", "hang", "tumble",
)
WALK_FRAMES = tuple(f"walk{i}" for i in range(6))
#: Rotated copies of the "tumble" frame, for a thrown figure: `spin0` to `spin7`
#: are 45 degree steps. Built once per dpi (and flip) with Pillow, then cached.
SPIN_STEPS = 8
SPIN_FRAMES = tuple(f"spin{i}" for i in range(SPIN_STEPS))
SPIN_BASE = "tumble"
#: "float" (Atlas, a wisp for a lower body: hovers and drifts) or "walk".
GAITS = {"masculine": "float", "feminine": "float"}
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

    def missing(self) -> list[str]:
        return [n for n in FRAME_NAMES if not (self.directory / f"{n}.png").is_file()]

    def _load(self, name: str) -> Any:
        if name not in self._source:
            from PIL import Image

            with Image.open(self.directory / f"{name}.png") as im:
                self._source[name] = im.convert("RGBA")
        return self._source[name]

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
        built = Frame(width, height, premultiplied_bgra(clear_faint_alpha(image)))
        self._cache[key] = built
        return built

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
        return Frame(side, side, premultiplied_bgra(clear_faint_alpha(turned)), pad_x, pad_y)
