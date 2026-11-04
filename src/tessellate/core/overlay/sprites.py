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
    "sit", "sleep", "wave", "held", "fall", "land", "hop",
)
WALK_FRAMES = tuple(f"walk{i}" for i in range(6))
#: Alpha under this is clear: the click-through guard.
ALPHA_FLOOR = 8
#: The shipped frames are at twice the CSS pixel size.
SOURCE_SCALE = 2.0


class Frame(NamedTuple):
    width: int
    height: int
    #: Premultiplied BGRA, top-down, `width * height * 4` bytes.
    bgra: bytes


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
        if name not in FRAME_NAMES:
            raise KeyError(name)
        key = (name, int(dpi), bool(flip))
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        from PIL import Image, ImageOps

        image = self._load(name)
        if flip:
            image = ImageOps.mirror(image)
        width, height = self.size(dpi)
        if (width, height) != image.size:
            image = image.resize((width, height), Image.Resampling.LANCZOS)
        built = Frame(width, height, premultiplied_bgra(clear_faint_alpha(image)))
        self._cache[key] = built
        return built
