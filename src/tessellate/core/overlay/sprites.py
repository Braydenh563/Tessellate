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

import functools
import logging
import math
import re
import threading
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
#: The wave's arm swing (INBOX 1696: one frame held the arm straight up, "it looks liek a nazi salute"): the arm
#: swung side to side about the raised position, `wave0` to `wave5`. Optional: a set without it draws `wave`.
WAVE_COUNT = 6
WAVE_FRAMES = tuple(f"wave{i}" for i in range(WAVE_COUNT))
#: Pictures of acts the app drew and the desk did not (W31 E1, E2; INBOX 1710): the lower wisp let down over an edge
#: and swung (`dangle`, and `kick0` and `kick1` thrown forward and back), the hang with one hand let go (`hang_one`)
#: and the long sit with the eyes shut (`meditate`). Optional like the wave's: a set without them draws `EXTRA_FALLBACK`
#: (the sit, the hang), and a companion made from the person's own name has none (`capture.CAPTURED`).
EXTRA_FRAMES = ("dangle", "kick0", "kick1", "hang_one", "meditate", "hang_sloth", "hang_feet")
#: `hang_sloth` is the hang asleep by one hand and `hang_feet` the hang flipped (L-ui-modernisation-10).
EXTRA_FALLBACK = {"dangle": "sit", "kick0": "sit", "kick1": "sit", "hang_one": "hang", "meditate": "sit", "hang_sloth": "hang", "hang_feet": "hang"}
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
    *WAVE_FRAMES,
    *EXTRA_FRAMES,
)
#: Drawn by `scripts/render_card_frames.py`, not captured from the app.
CARD_FRAMES = ("card0", "card1")
WALK_FRAMES = tuple(f"walk{i}" for i in range(WALK_COUNT))
#: Rotated copies of the "tumble" frame, for a thrown figure: `spin0` to `spin47` are 7.5 degree steps
#: (INBOX 1670, 17:05Z: eight 45 degree frames turned "by 45 degrees each time"). Each is built on first use
#: per dpi (and flip) with Pillow and cached, so a throw pays for the angles it passes through and a session
#: that never throws pays for none. `SPIN_COARSE` of them (45 degrees apart) give the engine its boxes.
SPIN_STEPS = 48
SPIN_COARSE = 8
SPIN_FRAMES = tuple(f"spin{i}" for i in range(SPIN_STEPS))
SPIN_BASE = "tumble"
#: A thrown figure is drawn at its true angle (INBOX 1683: "rotating when thrown ... still horrible"; the 48 steps of
#: 7.5 degrees held a picture for 2 to 3 ticks and then jumped 7.5 or 15): `spun_at` turns the tumble by any angle,
#: rounded to `SPIN_QUANT` degrees, on the same canvas as the `spinN` frames. INBOX 1696 a: at dpi 192 a fresh turn
#: was 6 ms of Pillow (4.7 of it the rotate, ten GIL hand-backs) on every tick of a fall, about 8 fps on the owner's
#: machine; now the quarter turn is rotated once per size (`warm_spins`, off the overlay thread), kept cropped to the
#: drawn box (19.5 MB at dpi 192), and every other angle and the mirror are that picture transposed (0.15 ms).
#: Only the last `SPUN_KEEP` assembled pictures are kept, since a spinning figure never shows an angle twice in a row.
SPIN_QUANT = 1.0
SPIN_QUARTER = round(90.0 / SPIN_QUANT)
SPUN_KEEP = 6
#: The sat figure with its eyes shut (INBOX 1670, 16:40Z: a sit had no blink). Not a shipped file: derived at
#: load from `sit` with closed lids drawn over its eyes, so the frame set and its byte budget do not move.
#: Asleep the eyes are already shut. `LID_EYES` is each look's two eyes as one box in shipped px on `stand`;
#: the sit is a few px off it, found by matching the box.
LID_FRAME = "sitblink"
LID_EYES = {"masculine": (110, 109, 155, 125), "feminine": (112, 110, 157, 126)}
LID_REACH = 6
LID_INK = (44, 42, 112)
DERIVED_FRAMES = (*SPIN_FRAMES, LID_FRAME)
#: "float" (Atlas, a wisp for a lower body: hovers and drifts) or "walk".
GAITS = {"masculine": "float", "feminine": "float"}
#: Pixels around the solid body that stay the frame's own (its soft edge), at the shipped scale.
CORE_GROW = 5
#: Posed frames kept (a pose is a squash, a lean, a lag): the least recently used go.
POSED_KEEP = 40
#: Plain frames kept at the size in use, the least recently used going first (the size handle's bound).
FRAME_KEEP = 50
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


def capped_pose(base: Frame, pose: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """`pose` with its stretch (`sy` above 1, about the feet) held where the drawn top stays two rows inside the canvas (the bilinear edge is one)
    (INBOX 1704, found by 1699: `fall` has no room above it at `sy` 1.1, and the stretch cut it with a straight edge)."""
    sx, sy, lean, drag = pose
    left, top, right, feet = base.box
    if sy <= 1.0 or not right or feet - top < 1:
        return pose
    return sx, max(1.0, min(sy, (feet - 2.0) / (feet - top))), lean, drag


#: A picture whose last drawn row is solid this wide was cut there (INBOX 1704: `render_desk_frames.clip_idle_tails` pinned
#: the feminine stand and idle tails to one lowest row, so the tail ends in a flat edge 36 to 45 px wide); its last
#: `TAPER_ROWS` rows fade out instead, so the cut does not read as a straight edge. The drawn box does not move.
CUT_WIDTH, TAPER_ROWS = 12, 8


def tapered(image: Any) -> Any:
    """`image` with a flat cut at its lowest drawn row faded over `TAPER_ROWS` rows (alpha only); the image itself otherwise."""
    from PIL import Image

    alpha = image.getchannel("A")
    box = alpha.point(lambda a: 255 if a >= ALPHA_FLOOR else 0).getbbox()
    if not box or box[3] < TAPER_ROWS + 2:
        return image
    last = box[3] - 1
    row = alpha.crop((0, last, image.width, last + 1)).point(lambda a: 255 if a >= 200 else 0)
    if sum(row.tobytes()) // 255 < CUT_WIDTH:
        return image
    ramp = Image.new("L", (1, image.height), 255)
    ramp.putdata([255 if y < last - TAPER_ROWS + 1 else round(255 * (last + 1 - y) / (TAPER_ROWS + 1)) if y <= last else 255 for y in range(image.height)])
    from PIL import ImageChops

    image = image.copy()
    image.putalpha(ImageChops.multiply(alpha, ramp.resize(image.size, Image.Resampling.NEAREST)))
    return image


def captured_root() -> Path:
    """`desk_frames` in the data folder, where `capture` writes a captured companion's set; here, not in
    `capture`, which reads this module's frame names, so the two do not import each other."""
    from tessellate.core.config import resolved_data_dir

    return resolved_data_dir() / "desk_frames"


def frames_dir() -> Path:
    """`frontend/img/desk`, in a checkout or a bundled build."""
    from tessellate.api.app import FRONTEND_DIR

    return Path(FRONTEND_DIR) / "img" / "desk"


def look_for(name: Any) -> str:
    """A frame set for a look name: a captured companion's key (`capture.is_key`, INBOX 1684) as it is,
    else feminine or, for anything else, the masculine set."""
    text = str(name).strip().lower()
    if re.fullmatch(r"c-[0-9a-f]{12}", text):
        return text
    return "feminine" if text == "feminine" else "masculine"


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


#: INBOX 1724 (the feminine desk companion "very purple or pink compared to the in-app one"): the desk capture leaves out
#: the app's blue aura and rings, so beside the app the figure tilted violet (the translucent stream 4.4 degrees in the
#: light theme and 10.3 in the dark, the body bands 0.7 to 3.1). A look's grade is the hue turn, toward blue, of a solid
#: pixel and of a translucent one, in Pillow's 1/256 of a turn (1.41 degrees). Saturation is left alone: it was already
#: within 8 points of the app in every band, and lowering it pushed the highlights out of that. Measured by band in
#: `tests/test_overlay_palette_1724.py`. Colour only: alpha is never touched.
GRADE = {"feminine": (1, 5)}
GLOW_BELOW = 200


def graded(image: Any, look: str) -> Any:
    """`image` with the look's grade (`GRADE`) applied to its colour; the image itself when the look has none."""
    spec = GRADE.get(look)
    if spec is None:
        return image
    from PIL import Image, ImageChops

    solid, glow = spec
    alpha = image.getchannel("A")
    hue, sa, val = image.convert("RGB").convert("HSV").split()
    hue = ImageChops.subtract(hue, alpha.point(lambda a: glow if a < GLOW_BELOW else solid))
    out = Image.merge("HSV", (hue, sa, val)).convert("RGB").convert("RGBA")
    out.putalpha(alpha)
    return out


class SpriteSet:
    """One look's frames, scaled per dpi and cached."""

    def __init__(self, look: str, directory: Path | None = None) -> None:
        self.look = look_for(look)
        #: A captured companion (name, persona, saved) has legs: it walks; Atlas floats.
        self.gait = GAITS.get(self.look, "walk")
        if directory is None and self.look not in LOOKS:
            directory = captured_root()
        self.directory = (directory or frames_dir()) / self.look
        self._source: dict[str, Any] = {}
        self._cache: dict[tuple[str, int, bool], Frame] = {}
        self._posed: dict[tuple[str, int, bool, tuple[float, ...]], Frame] = {}
        self._tail_kept: dict[tuple[str, int, bool], tuple[Any, Any]] = {}
        self._pose_kept: dict[tuple[str, int, bool], Any] = {}
        self._occ: dict[int, tuple[Any, Any]] = {}
        self._spun_at: dict[tuple[int, int, bool], Frame] = {}
        self._canvas: dict[tuple[int, bool], tuple[Any, int, int]] = {}
        #: The quarter turn per dpi: {dpi: {step: (cropped premultiplied BGRA as an RGBA image, left, top)}}, built
        #: by `warm_spins` on a worker or on first use; the lock keeps the two from building one step twice.
        self._spin_bases: dict[int, dict[int, tuple[Any, int, int]]] = {}
        self._spin_lock = threading.Lock()
        self._spin_live = 0
        self.rotations = 0  # Pillow rotates done, for the tests and the log
        self._metrics: dict[int, dict[tuple[str, bool], tuple[int, int, int, int]]] = {}
        self._metrics_base: tuple[tuple[int, int], dict[tuple[str, bool], tuple[int, int, int, int]]] | None = None

    def _has(self, name: str) -> bool:
        return (self.directory / f"{name}.png").is_file()

    def missing(self) -> list[str]:
        """What a look must have to run: the frames an older, shorter set also had."""
        extra = {*WALK_FRAMES[OLD_WALK_COUNT:], *IDLE_FRAMES[OLD_IDLE_COUNT:], *WAVE_FRAMES, *EXTRA_FRAMES}
        return [n for n in FRAME_NAMES if n not in extra and not self._has(n)]

    def walk_count(self) -> int:
        """How many frames of the walk cycle are shipped (6 or 12), for the engine's stride."""
        return WALK_COUNT if all(self._has(n) for n in WALK_FRAMES) else OLD_WALK_COUNT

    def wave_count(self) -> int:
        """The wave's arm swing frames shipped (`WAVE_COUNT`), or 0: the one `wave` frame is drawn."""
        return WAVE_COUNT if all(self._has(n) for n in WAVE_FRAMES) else 0

    def extras(self) -> frozenset[str]:
        """Which of `EXTRA_FRAMES` are shipped: the engine draws the others' `EXTRA_FALLBACK`."""
        return frozenset(n for n in EXTRA_FRAMES if self._has(n))

    def idle_count(self) -> int:
        return IDLE_COUNT if all(self._has(n) for n in IDLE_FRAMES) else OLD_IDLE_COUNT

    def available(self) -> list[str]:
        return [n for n in FRAME_NAMES if self._has(n)]

    def _load(self, name: str) -> Any:
        if name not in self._source:
            from PIL import Image

            if name == LID_FRAME:
                self._source[name] = self._lidded()
                return self._source[name]
            with Image.open(self.directory / f"{name}.png") as im:
                loaded = tapered(graded(im.convert("RGBA"), self.look))
            # as shipped: the standing family already carries one shared nebula stream (render_desk_frames.py
            # `shared_stream`); a loader-side veil swap cut it away under the body and added a step (INBOX 1670)
            self._source[name] = loaded
        return self._source[name]

    def _lidded(self) -> Any:
        """`sit` with a closed lid over each eye: the eye box is matched from `stand` into the sit (the head is a
        few px off), each eye is filled with the skin beside it and a lash line is drawn across it, supersampled
        so its edge is soft like the art."""
        from PIL import Image, ImageChops, ImageDraw, ImageStat

        stand, sit = self._load("stand"), self._load("sit")
        if self.look not in LID_EYES:  # a captured figure's eyes are not charted: it sits with them open
            return sit
        box = LID_EYES[self.look]
        ref, best = stand.crop(box), None
        for dy in range(-LID_REACH, LID_REACH + 1):
            for dx in range(-LID_REACH, LID_REACH + 1):
                here = sit.crop((box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy))
                err = sum(ImageStat.Stat(ImageChops.difference(ref, here)).mean)
                if best is None or err < best[0]:
                    best = (err, dx, dy)
        _err, dx, dy = best
        x0, y0, x1, y1 = box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy
        up = 4
        patch = sit.crop((x0, y0, x1, y1)).resize(((x1 - x0) * up, (y1 - y0) * up), Image.Resampling.NEAREST)
        skin = sit.getpixel(((x0 + x1) // 2, (y0 + y1) // 2))  # between the eyes
        draw = ImageDraw.Draw(patch)
        for side in (0.25, 0.75):  # each eye: its centre is a quarter in from its side of the box
            cx, cy = (x1 - x0) * up * side, (y1 - y0) * up * 0.5
            rx, ry = 10 * up, 7 * up
            draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=skin)
            draw.arc((cx - rx * 0.8, cy - ry * 0.9, cx + rx * 0.8, cy + ry * 0.9), 20, 160, fill=(*LID_INK, 255), width=2 * up)
        done = sit.copy()
        done.paste(patch.resize((x1 - x0, y1 - y0), Image.Resampling.LANCZOS), (x0, y0))
        return done

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
        if name not in FRAME_NAMES and name not in DERIVED_FRAMES:
            raise KeyError(name)
        key = (name, int(dpi), bool(flip))
        cached = self._cache.pop(key, None)
        if cached is not None:
            self._cache[key] = cached  # most recent last
            return cached
        built = self._build(name, dpi, flip)
        self._cache[key] = built
        while len(self._cache) > FRAME_KEEP:
            del self._cache[next(iter(self._cache))]
        return built

    def keep_only(self, dpi: int) -> None:
        """A new size is the one in use: pictures at any other are dropped (a drag crosses many sizes and
        must not leave a set of frames behind at each)."""
        dpi = int(dpi)
        for store in (self._cache, self._posed, self._spun_at, self._tail_kept):
            for key in [k for k in store if k[1] != dpi]:
                del store[key]
        with self._spin_lock:
            self._spin_live = dpi
            for key in [k for k in self._canvas if k[0] != dpi]:
                del self._canvas[key]
            for d in [d for d in self._spin_bases if d != dpi]:
                del self._spin_bases[d]

    def _build(self, name: str, dpi: int, flip: bool) -> Frame:
        from PIL import Image, ImageOps

        image = self._load(SPIN_BASE if name in SPIN_FRAMES else name)
        if flip:
            image = ImageOps.mirror(image)
        width, height = self.size(dpi)
        if (width, height) != image.size:
            image = image.resize((width, height), Image.Resampling.LANCZOS)
        if name in SPIN_FRAMES:
            return self._spun(image, SPIN_FRAMES.index(name), width, height)
        clear = clear_faint_alpha(image)
        return Frame(width, height, premultiplied_bgra(clear), box=_drawn_box(clear))

    def posed(self, name: str, dpi: int, flip: bool, pose: tuple[float, float, float, float], flow: tuple[int, ...] | None = None) -> Frame:
        """The frame with a body pose over it: `pose` is (sx, sy, lean, drag), see
        `behaviour.Pose`. A bottom-anchored squash or stretch, a turn-about squeeze about the
        middle, a lean (the head moves by `lean` of the height, the feet stay) and a lag of the
        lower part (the tail and wisp trail by `drag` px, growing toward the bottom), by a mesh of
        horizontal strips. Cached by the pose, `POSED_KEEP` of them; the plain frame when the pose is."""
        flow = flow if flow and name not in SPIN_FRAMES and any(flow) else None
        if name not in SPIN_FRAMES:
            pose = capped_pose(self.frame(name, dpi, flip), pose)
        sx, sy, lean, drag = pose
        if (sx, sy, lean, drag) == (1.0, 1.0, 0.0, 0.0) and flow is None:
            return self.frame(name, dpi, flip)
        key = (name, int(dpi), bool(flip), (sx, sy, lean, drag), flow)
        hit = self._posed.pop(key, None)
        if hit is None:
            hit = self._warp(self.frame(name, dpi, flip), self._pose_image(name, dpi, flip), sx, sy, lean, drag, flow)
        self._posed[key] = hit  # most recent last
        while len(self._posed) > POSED_KEEP:
            del self._posed[next(iter(self._posed))]
        return hit

    def _pose_image(self, name: str, dpi: int, flip: bool) -> Any:
        """The straight RGBA picture at this size (mirrored when `flip`), kept: a cold pose reuses it, and `_occupancy` keys on it."""
        key = (name, int(dpi), bool(flip))
        image = self._pose_kept.get(key)
        if image is None:
            from PIL import Image, ImageOps

            image = self._load(SPIN_BASE if name in SPIN_FRAMES else name)
            if flip:
                image = ImageOps.mirror(image)
            width, height = self.size(dpi)
            image = image.resize((width, height), Image.Resampling.LANCZOS) if (width, height) != image.size else image
            self._pose_kept[key] = image
            while len(self._pose_kept) > 8:
                del self._pose_kept[next(iter(self._pose_kept))]
        return image

    def _warp(self, base: Frame, image: Any, sx: float, sy: float, lean: float, drag: float, flow: tuple[int, ...] | None = None) -> Frame:
        from PIL import Image

        if flow is not None:
            return self._flowed(base, image, sx, sy, lean, drag, flow)

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

    def _flowed(self, base: Frame, image: Any, sx: float, sy: float, lean: float, drag: float, flow: tuple[int, ...]) -> Frame:
        """`_warp` with the wisps and streams moving (INBOX 1683 c): the same strips cut into one column per
        strand across the drawn box, every corner moved by `flow_offsets` (the lower body from the waist down
        and the outer streams at any height; the head and the torso's middle stay put), then the nebula's
        sparkle (`_glint`). Sub-pixel, bilinear."""
        from PIL import Image

        w, h = image.size
        scale = w / (self._load("stand").size[0])
        left, top, right, bottom = base.box if base.box[2] else (0, 0, w, h)
        feet = bottom or h
        mid = (left + right) / 2
        bands = len(flow) // FLOW_FIELDS
        edges = [0.0] + [float(round(left + (right - left) * j / bands)) for j in range(1, bands)] + [float(w)]  # whole px: the cut and the map agree
        rows = [round(i * h / POSE_STRIPS) for i in range(POSE_STRIPS)] + [h]
        field = flow_offsets(flow, edges, rows, (left, top, right, feet), scale, (max(0.0, left - 1.0), max(0.0, w - right - 1.0), max(0.0, h - feet - 1.0)))
        occupied = self._occupancy(image)
        mesh = []
        cx0, cy0, cx1, cy1 = w, h, 0, 0  # the dest box the kept quads cover
        for i in range(POSE_STRIPS):
            y0, y1 = rows[i], rows[i + 1]
            ym = (y0 + y1) / 2
            shift = lean * (feet - ym) * 0.9 - drag * scale * (ym / h) ** 2
            for b in range(bands):
                src = []
                for side, yi, yd in ((0, i, y0), (0, i + 1, y1), (1, i + 1, y1), (1, i, y0)):
                    xd = edges[b + side]
                    fdx, fdy = field[yi][b + side]
                    src += [mid + (xd - mid - shift) / sx - fdx, feet + (yd - feet) / sy - fdy]
                if not occupied(min(src[0::2]), min(src[1::2]), max(src[0::2]), max(src[1::2])):
                    continue  # the quad samples only clear pixels: it draws nothing, so it is not transformed
                x0, x1 = int(edges[b]), int(edges[b + 1])
                mesh.append(((x0, y0, x1, y1), tuple(src)))
                cx0, cy0, cx1, cy1 = min(cx0, x0), min(cy0, y0), max(cx1, x1), max(cy1, y1)
        if not mesh:
            return Frame(w, h, bytes(w * h * 4), box=(0, 0, w, h))
        # Only the kept quads' box is warped, lit and cleared (all pixelwise); the rest of the picture is clear.
        mesh = [((a - cx0, b - cy0, c - cx0, d - cy0), q) for (a, b, c, d), q in mesh]
        warped = image.transform((cx1 - cx0, cy1 - cy0), Image.Transform.MESH, mesh, Image.Resampling.BILINEAR)
        warped = _glint(warped, flow, (left - cx0, top - cy0, right - cx0, feet - cy0))
        clear = clear_faint_alpha(warped)
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        canvas.paste(clear, (cx0, cy0))
        bbox = clear.getchannel("A").point(lambda a: 255 if a >= ALPHA_FLOOR else 0).getbbox()
        box = (bbox[0] + cx0, bbox[1] + cy0, bbox[2] + cx0, bbox[3] + cy0) if bbox else (0, 0, w, h)
        return Frame(w, h, premultiplied_bgra(canvas), box=box)

    def _occupancy(self, image: Any) -> Any:
        """A test `(x0, y0, x1, y1) -> bool` for "may any pixel of the picture at or above `ALPHA_FLOOR` lie within these source
        px": 4 px cells and their running sums, kept per picture (conservative: a cell is lit when any of its pixels is, the
        box is grown by 2 px for the bilinear taps), so a flow warp skips the quads that would sample clear pixels only."""
        key = id(image)
        hit = self._occ.get(key)
        if hit is None or hit[0] is not image:
            cell = 4
            mask = image.getchannel("A").point(lambda a: 255 if a >= ALPHA_FLOOR else 0).reduce(cell)
            cw, ch = mask.size
            data = mask.tobytes()
            sums = [[0] * (cw + 1) for _ in range(ch + 1)]
            for y in range(ch):
                run, above, row = 0, sums[y], sums[y + 1]
                for x in range(cw):
                    run += 1 if data[y * cw + x] else 0
                    row[x + 1] = above[x + 1] + run

            def occupied(x0: float, y0: float, x1: float, y1: float) -> bool:
                a, b = max(0, int((x0 - 2) // cell)), max(0, int((y0 - 2) // cell))
                c, d = min(cw, int((x1 + 2) // cell) + 1), min(ch, int((y1 + 2) // cell) + 1)
                return c > a and d > b and sums[d][c] - sums[b][c] - sums[d][a] + sums[b][a] > 0

            hit = (image, occupied)
            self._occ[key] = hit
            while len(self._occ) > 8:
                del self._occ[next(iter(self._occ))]
        return hit[1]

    def _tail_src(self, name: str, dpi: int, flip: bool) -> tuple[Any, Any]:
        """The tail source picture (straight RGBA, at this size) and the region's feather mask, kept: both are the same
        every tick."""
        key = (name, int(dpi), bool(flip))
        hit = self._tail_kept.get(key)
        if hit is None:
            image = self._pose_image(name, dpi, flip)
            w, h = image.size
            x0, y0, x1, y1 = self._tail_region(w, h, flip)
            feather = max(1, round(TAIL_FEATHER * w / self._load("stand").size[0]))
            mask = _feather_mask(x1 - x0, y1 - y0, feather, flip)
            hit = (image, mask)
            self._tail_kept[key] = hit
            while len(self._tail_kept) > 8:
                del self._tail_kept[next(iter(self._tail_kept))]
        return hit

    @staticmethod
    def _tail_region(w: int, h: int, flip: bool) -> tuple[int, int, int, int]:
        x0, y0, x1, y1 = TAIL_BOX
        a, b = round(x0 * w), round(x1 * w)
        return (w - b, round(y0 * h), w - a, round(y1 * h)) if flip else (a, round(y0 * h), b, round(y1 * h))

    def tailed(self, base: Frame, name: str, dpi: int, flip: bool, view: tuple[int, ...] | None) -> Frame:
        """`base` with the tail layer drawn over it (`behaviour.TailLayer.view`): the tail's region redrawn from the
        tail source with its control points moved, every byte outside the region the body's own (the body frame is not
        rebuilt: it is cut and spliced). The same frame when there is no layer for it."""
        source = tail_source(name)
        if source is None or not view or not any(view) or not self._has(source):
            return base
        from PIL import Image

        src, mask = self._tail_src(source, dpi, flip)
        w, h = src.size
        if (base.width, base.height) != (w, h):
            return base
        x0, y0, x1, y1 = self._tail_region(w, h, flip)
        scale = w / self._load("stand").size[0]
        sgn = -1.0 if flip else 1.0
        root = (x0 if not flip else x1)
        reach = (TAIL_SPAN - TAIL_BOX[0]) * w  # root to the tip's rest, px
        steps = len(view) // 2

        room = max(0.0, h - 2.0 - (self.frame(source, dpi, flip).box[3] or y1))  # canvas below the tail source's lowest row: it moves down no further

        def shift(x: float) -> tuple[float, float]:
            dx, dy = _tail_shift(view, abs(x - root) / reach)
            return sgn * dx * scale, min(room, dy * scale)

        edges = sorted({x0, x1, *(min(x1, max(x0, round(root + sgn * reach * i / steps))) for i in range(1, steps + 1))})
        mesh = []
        for a, b in zip(edges, edges[1:]):
            (ax, ay), (bx, by) = shift(a), shift(b)
            mesh.append(((a - x0, 0, b - x0, y1 - y0), (a - ax, y0 - ay, a - ax, y1 - ay, b - bx, y1 - by, b - bx, y0 - by)))
        moved = src.transform((x1 - x0, y1 - y0), Image.Transform.MESH, mesh, Image.Resampling.BILINEAR)
        row = (x1 - x0) * 4
        pixels = base.bgra
        old = Image.frombuffer("RGBA", (x1 - x0, y1 - y0), b"".join(pixels[((y0 + j) * w + x0) * 4:((y0 + j) * w + x1) * 4] for j in range(y1 - y0)), "raw", "BGRa", 0, 1)
        mixed = clear_faint_alpha(Image.composite(moved, old, mask))
        patch = premultiplied_bgra(mixed)
        out = bytearray(pixels)
        for j in range(y1 - y0):
            at = ((y0 + j) * w + x0) * 4
            out[at:at + row] = patch[j * row:(j + 1) * row]
        # The box: the body's own, grown by what the patch draws (the patch alone is scanned, not the whole picture), so a
        # swing of the tail never shrinks the hit box under the body.
        px0, py0, px1, py1 = _drawn_box(mixed)
        pb = (x0 + px0, y0 + py0, x0 + px1, y0 + py1)
        bx = base.box if base.box[2] else pb
        box = (min(bx[0], pb[0]), min(bx[1], pb[1]), max(bx[2], pb[2]), max(bx[3], pb[3]))
        return Frame(w, h, bytes(out), base.pad_x, base.pad_y, box)

    def metrics(self, dpi: int = 96) -> dict[tuple[str, bool], tuple[int, int, int, int]]:
        """The drawn box of every frame, both mirrors, in the engine's own coordinates: from
        where the window is placed (`out.x`, `out.y`), so a rotated frame's pad is taken off.
        The engine plants feet and keeps a ride inside the work area from these (INBOX 1670)."""
        dpi = int(dpi)
        if dpi in self._metrics:
            return self._metrics[dpi]
        if self._metrics_base is not None:
            # a new size of the same look: the first one's boxes, scaled (building ~100 frames per step of a drag would stall it)
            (base_w, base_h), base = self._metrics_base
            width, height = self.size(dpi)
            sx, sy = width / base_w, height / base_h
            found = {k: (round(a * sx), round(b * sy), round(c * sx), round(d * sy)) for k, (a, b, c, d) in base.items()}
            self._metrics = {dpi: found}
            return found
        found = {}
        step = SPIN_STEPS // SPIN_COARSE
        for name in (*self.available(), *DERIVED_FRAMES):
            if name in SPIN_FRAMES:  # a spin's box is its nearest 45 degree neighbour's: not 48 frames built up front
                near = SPIN_FRAMES[round(SPIN_FRAMES.index(name) / step) * step % SPIN_STEPS]
            else:
                near = name
            for flip in (False, True):
                f = self._build(near, dpi, flip)  # not kept: the cache holds what is drawn, not every frame of the set
                left, top, right, bottom = f.box
                found[(name, flip)] = (left - f.pad_x, top - f.pad_y, right - f.pad_x, bottom - f.pad_y)
        self._metrics = {dpi: found}
        self._metrics_base = (self.size(dpi), found)
        return found

    def spun_at(self, angle: float, dpi: int = 96, flip: bool = False) -> Frame:
        """The tumble turned by `angle` radians (clockwise on screen positive), on the canvas of `spin0`.
        Rounded to `SPIN_QUANT` degrees: a quarter-turn picture (`_spin_base`) transposed into place, the last
        `SPUN_KEEP` kept. The mirror is the unmirrored figure turned the other way and flipped."""
        from PIL import Image

        steps = round(360.0 / SPIN_QUANT)
        q = round(math.degrees(angle) / SPIN_QUANT) % steps
        key = (q, int(dpi), bool(flip))
        hit = self._spun_at.pop(key, None)
        if hit is None:
            side, pad_x, pad_y = self._spin_canvas(int(dpi))
            quarter, rest = divmod((-q) % steps if flip else q, SPIN_QUARTER)
            image, x, y = self._spin_base(rest, int(dpi))
            w, h = image.size
            if quarter:  # a quarter turn clockwise on screen moves (x, y) to (side - y, x)
                image = image.transpose((Image.Transpose.ROTATE_270, Image.Transpose.ROTATE_180, Image.Transpose.ROTATE_90)[quarter - 1])
                for _ in range(quarter):
                    x, y, w, h = side - (y + h), x, h, w
            if flip:  # mirrored about the canvas middle; when the side and the width differ by an odd number, the
                # mirrored figure would sit a pixel off its pad: that pixel, turned with it, is put back
                d = 2 * pad_x + self.size(int(dpi))[0] - side
                turn = math.radians(q * SPIN_QUANT)
                image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                x, y = side - (x + w) + round(d * math.cos(turn)), y + round(d * math.sin(turn))
            canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            canvas.paste(image, (x, y))
            hit = Frame(side, side, canvas.tobytes(), pad_x, pad_y, (x, y, x + w, y + h))
        self._spun_at[key] = hit
        while len(self._spun_at) > SPUN_KEEP:
            del self._spun_at[next(iter(self._spun_at))]
        return hit

    def _spin_base(self, step: int, dpi: int) -> tuple[Any, int, int]:
        """The tumble turned `step` of `SPIN_QUARTER` steps on the spin canvas, cropped to its drawn box: premultiplied
        BGRA held in an RGBA image (a transpose does not care which byte is which) and its top left on the canvas."""
        found = self._spin_bases.get(dpi, {}).get(step)
        if found is not None:
            return found
        from PIL import Image

        with self._spin_lock:
            found = self._spin_bases.get(dpi, {}).get(step)
            if found is not None:
                return found
            if (dpi, False) not in self._canvas:
                side, pad_x, pad_y = self._spin_canvas(dpi)  # the size and pad `spin0` has, without its cache (a worker runs this)
                canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
                canvas.paste(self._pose_image(SPIN_BASE, dpi, False), (pad_x, pad_y))
                self._canvas[(dpi, False)] = (canvas, pad_x, pad_y)
            canvas = self._canvas[(dpi, False)][0]
            turned = canvas.rotate(-step * SPIN_QUANT, resample=Image.Resampling.BILINEAR)
            self.rotations += 1
            clear = clear_faint_alpha(turned)
            left, top, right, bottom = _drawn_box(clear)
            cropped = clear.crop((left, top, right, bottom))
            found = (Image.frombytes("RGBA", cropped.size, premultiplied_bgra(cropped)), left, top)
            if dpi == self._spin_live or not self._spin_live:
                self._spin_bases.setdefault(dpi, {})[step] = found
            return found

    def _spin_canvas(self, dpi: int) -> tuple[int, int, int]:
        """The spin canvas's side and the figure's pad on it, as `_spun` makes them."""
        width, height = self.size(dpi)
        side = math.ceil(math.hypot(width, height))
        return side, (side - width) // 2, (side - height) // 2

    def warm_spins(self, dpi: int) -> int:
        """Every step of the quarter turn at `dpi` built now (a worker calls this after a size change, so a throw
        never rotates on the overlay thread). Stops when another size takes over. Returns how many it built."""
        dpi, built = int(dpi), 0
        for step in range(SPIN_QUARTER):
            if self._spin_live and dpi != self._spin_live:
                break
            if step not in self._spin_bases.get(dpi, {}):
                self._spin_base(step, dpi)
                built += 1
        return built

    def spins_ready(self, dpi: int) -> bool:
        return len(self._spin_bases.get(int(dpi), {})) >= SPIN_QUARTER

    def _spun(self, image: Any, step: int, width: int, height: int) -> Frame:
        """The picture turned by `step` of `SPIN_STEPS` turns on a square canvas big enough
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


#: Numbers a strand takes in a flow view (`behaviour.Flow.view`); the lower body starts at this share of the drawn
#: height, the torso's middle (share of the half width: still inside the first, free past the second) never sways,
#: and the outer streams take this share of a strand's sway at any height.
FLOW_FIELDS = 5
TAIL_Q = 8.0  # `behaviour.TAIL_Q`: steps a px in a tail view
FLOW_WAIST = 0.5
FLOW_CORE = (0.3, 0.6)
FLOW_RIBBON = 0.8
FLOW_Q = 8.0
FLOW_GLINT = 0.30


def _smooth(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def flow_offsets(flow: tuple[int, ...], edges: list[float], rows: list[int], box: tuple[int, int, int, int], scale: float, room: tuple[float, float, float] | None = None) -> list[list[tuple[float, float]]]:
    """Where each mesh corner (row boundary, column edge) moves, px of the picture: the strands' own values (a
    quadratic from nothing at the waist through the middle's lead to the tip's), a corner between two strands
    taking their mean, so the picture bends and never tears. The head and the torso's middle: nothing. `room` is the
    canvas left (left, right, below) the drawn box: no corner moves out by more than it (INBOX 1699, the hanging frame's
    tail coil ends 2 px above the canvas bottom, and a fall of the strands cut it with a straight edge)."""
    left, top, right, feet = box
    bands = len(flow) // FLOW_FIELDS
    half = max(1.0, (right - left) / 2)
    mid = (left + right) / 2
    waist = top + (feet - top) * FLOW_WAIST
    out = []
    for y in rows:
        u = max(0.0, min(1.0, (y - waist) / max(1.0, feet - waist)))
        below = y > waist
        line = []
        for j, x in enumerate(edges):
            near = [flow[k * FLOW_FIELDS:(k + 1) * FLOW_FIELDS] for k in (j - 1, j) if 0 <= k < bands]
            tip, middle, rise = (sum(n[f] for n in near) / len(near) / FLOW_Q * scale for f in range(3))
            lead, curve = 4 * middle - tip, 2 * tip - 4 * middle  # v(u) = lead u + curve u^2: 0, middle, tip at 0, 1/2, 1
            free = _smooth((abs(x - mid) / half - FLOW_CORE[0]) / (FLOW_CORE[1] - FLOW_CORE[0]))
            ribbon = FLOW_RIBBON * free * (1 - u) * (lead / 2 + curve / 4)
            dy = rise * u + 0.3 * rise * free * (1 - u)
            dx = lead * u + curve * u * u + ribbon if below else ribbon
            if room is not None:
                dx, dy = max(-room[0], min(room[1], dx)), min(dy, room[2])
            line.append((dx, dy))
        out.append(line)
    return out


@functools.lru_cache(maxsize=8)
def _glint_tables(bands: int) -> tuple[list[float], list[tuple[float, float, float]]]:
    """What `_glint` takes from the strand count alone: each strand's share (the outer streams above the waist too) and each
    row's lower-body ramp and wave phase."""
    levels = [0.6 * _smooth((abs((b + 0.5) / bands * 2 - 1) - FLOW_CORE[0] * 1.2) / 0.3) for b in range(bands)]
    waves = []
    for r in range(12):
        k = 2 * math.pi * 1.3 * r / 11
        waves.append((_smooth((r / 11 - FLOW_WAIST) / 0.12 + 0.5), math.cos(k), math.sin(k)))
    return levels, waves


def _glint(image: Any, flow: tuple[int, ...], box: tuple[int, int, int, int]) -> Any:
    """The nebula's sparkle: each strand's brightest parts take a wave of light toward white that runs down it
    (`flow`'s sine and cosine, tenths), so the particles glimmer along each stream instead of holding one
    value. Straight Pillow blends at C speed; the alpha is untouched, so no edge appears or goes."""
    from PIL import Image, ImageChops

    left, top, right, feet = box
    bands = len(flow) // FLOW_FIELDS
    if right <= left or feet <= top:
        return image
    levels, waves = _glint_tables(bands)
    cells = bytearray()
    for r in range(12):
        own, k_cos, k_sin = waves[r]
        for b in range(bands):
            s, c = flow[b * FLOW_FIELDS + 3] / 10.0, flow[b * FLOW_FIELDS + 4] / 10.0
            cells.append(max(0, min(255, round(255 * FLOW_GLINT * max(own, levels[b]) * (0.5 + 0.5 * (s * k_cos - c * k_sin))))))
    grid = Image.frombytes("L", (bands, 12), bytes(cells))
    mask = Image.new("L", image.size, 0)
    mask.paste(grid.resize((right - left, feet - top), Image.Resampling.BICUBIC), (left, top))
    gate = ImageChops.multiply(mask, image.convert("L"))
    r, g, b, a = image.split()
    return Image.merge("RGBA", (ImageChops.screen(r, gate), ImageChops.screen(g, gate), ImageChops.screen(b, gate), a))


#: The tail as a layer (atlascat-1108 C1, `behaviour.TailLayer`): the tail's region of a body frame (shares of the picture,
#: as shipped, facing right) is redrawn every display frame from a fixed tail source (`stand`, or `sit`), each of its
#: `TAIL_STEPS` control points moved by the view, so the tail moves smoothly and not at the idle cycle's 6 a second. The
#: region's edges feather over `TAIL_FEATHER` px of the shipped frame, so no seam shows against the body. The root end
#: (`TAIL_SPAN`: where the tail's tip rests, share of the width) never moves.
TAIL_BOX = (0.52, 0.53, 1.0, 1.0)
TAIL_SPAN = 0.82
TAIL_FEATHER = 10
TAIL_SOURCE = {"stand": "stand", "idle": "stand", "blink": "stand", "look": "stand", "sit": "sit", "sitblink": "sit"}


def tail_source(name: str) -> str | None:
    """The frame the tail is taken from for a body frame, or None when this one carries no layered tail."""
    return TAIL_SOURCE.get(name.rstrip("0123456789"))


def _feather_mask(width: int, height: int, feather: int, flip: bool) -> Any:
    """The tail region's mask: 0 at the root's edge and the top, rising to 255 over `feather` px. Not at the bottom: the region
    runs to the canvas's last row, so no straight edge crosses the tail or the ribbon below it (INBOX 1704: a diagonal cut
    where the tail layer met the unmoved body under it)."""
    from PIL import Image, ImageChops

    def ramp(n: int, reverse: bool) -> list[int]:
        out = []
        for i in range(n):
            j = n - 1 - i if reverse else i
            out.append(round(255 * min(1.0, (j + 1) / feather)))
        return out

    cols, rows = Image.new("L", (width, 1)), Image.new("L", (1, height))
    cols.putdata(ramp(width, flip))
    rows.putdata(ramp(height, False))
    return ImageChops.multiply(cols.resize((width, height), Image.Resampling.NEAREST), rows.resize((width, height), Image.Resampling.NEAREST))


def _tail_shift(view: tuple[int, ...], t: float) -> tuple[float, float]:
    """The control points' move at `t` (0 root, 1 tip; clamped), px of the shipped frame, by their straight line."""
    pts = [(0.0, 0.0)] + [(view[i] / TAIL_Q, view[i + 1] / TAIL_Q) for i in range(0, len(view), 2)]
    u = max(0.0, min(1.0, t)) * (len(pts) - 1)
    i = min(len(pts) - 2, int(u))
    f = u - i
    return pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f


#: Alpha under this share of the picture is gone altogether: no faint ghost, and no click lands on it.
FADE_CLEAR = 0.06
#: The portal's ring (nebula violet, a lighter rim) and the puff's smoke (soft grey-white).
PORTAL_RING = (150, 110, 255)
PORTAL_RIM = (210, 190, 255)
PUFF_SMOKE = (236, 238, 244)
SPARK = (255, 240, 190)
CLOUD = (240, 244, 252)
BUBBLE = (170, 214, 255)


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


def fx_margin(frame: Frame) -> int:
    """The room an effect needs around the figure, in px: a portal's ring, a cloud, a bubble or a sparkle reach past the
    picture's own edge (the ring spanned y 0 to 156 of a 151 px canvas and was clipped, INBOX 1692)."""
    left, top, right, bottom = frame.box if frame.box[2] else (0, 0, frame.width, frame.height)
    return int(0.15 * max(right - left, bottom - top)) + 20


def _star(draw: Any, x: float, y: float, r: float, tone: int) -> None:
    """A four-point sparkle."""
    q = r * 0.22
    draw.polygon([(x, y - r), (x + q, y - q), (x + r, y), (x + q, y + q), (x, y + r), (x - q, y + q), (x - r, y), (x - q, y - q)], fill=(*SPARK, tone))


def _draw_fx(draw: Any, kind: str, strength: float, face: int, cx: float, cy: float, bw: float, bh: float, phase: float) -> None:
    """The effect's shapes on a transparent layer (a portal ring, smoke, sparkles, a cloud, a bubble)."""
    if kind == "portal":
        ox = (1 if face >= 0 else -1) * bw * 0.18
        rx, ry = bw * 0.30 * (0.5 + 0.5 * strength), bh * 0.62 * (0.6 + 0.4 * strength)
        box = (cx + ox - rx, cy - ry, cx + ox + rx, cy + ry)
        tone = max(1, int(220 * strength))
        for grow, rgb in ((10, PORTAL_RING), (5, PORTAL_RING), (0, PORTAL_RIM)):
            draw.ellipse((box[0] - grow, box[1] - grow, box[2] + grow, box[3] + grow), outline=(*rgb, tone // (1 + grow // 5)), width=3)
    elif kind == "blink":
        tone = max(1, int(255 * strength))
        for i in range(7):  # sparkles ringed round the body, each turning on and off out of step
            a = i * 2.4 + phase * 3.0
            x, y = cx + math.cos(a) * bw * (0.42 + 0.08 * (i % 3)), cy + math.sin(a) * bh * (0.40 + 0.06 * (i % 2))
            _star(draw, x, y, max(4.0, bw * (0.07 + 0.03 * ((i + int(phase * 6)) % 3))) * (0.4 + 0.6 * strength), tone)
    elif kind == "cloud":
        tone = max(1, int(235 * strength))
        base = cy + bh * 0.5
        for dx, dy, rad in ((-0.34, 0.0, 0.17), (-0.12, -0.05, 0.22), (0.14, -0.04, 0.2), (0.34, 0.01, 0.16), (0.0, 0.05, 0.2)):
            r = bw * rad * (0.55 + 0.45 * strength)
            x, y = cx + dx * bw * 1.15, base + 0.02 * bh + dy * bh * 0.5
            draw.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(*CLOUD, tone))
    elif kind == "bubble":
        tone = max(1, int(200 * strength))
        r = max(bw, bh) * 0.62 * (0.7 + 0.3 * strength)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*BUBBLE, tone // 6), outline=(*BUBBLE, tone), width=3)
        draw.arc((cx - r * 0.78, cy - r * 0.78, cx + r * 0.78, cy + r * 0.78), 200, 260, fill=(255, 255, 255, tone), width=3)
        for i in range(3):  # small ones rising off it
            y = cy + r * (0.9 - ((phase * 2.0 + i / 3.0) % 1.0) * 1.9)
            x = cx + (i - 1) * r * 0.55
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), outline=(*BUBBLE, tone), width=2)
    else:
        tone = max(1, int(200 * strength))
        for dx, dy, rad in ((-0.3, 0.25, 0.30), (0.3, 0.2, 0.28), (0.0, -0.1, 0.36), (-0.2, -0.3, 0.24), (0.25, -0.3, 0.22)):
            r = max(bw, bh) * rad * (0.4 + 0.8 * strength)
            x, y = cx + dx * bw, cy + dy * bh
            draw.ellipse((x - r, y - r, x + r, y + r), fill=(*PUFF_SMOKE, tone))


#: A figure pressed against an edge (E6): its width loses up to this share at amount 1, about the edge it touches, and it
#: gains half that in height (about its middle), so the squash keeps its size to the eye. Amounts are on a 1/8 grid.
EDGE_SQUASH = 0.16


def squashed(frame: Frame, squash: tuple[float, int] | None) -> Frame:
    """The frame pressed against the wall `side` (-1 left, 1 right) by `amount` (0 to 1): narrower about the edge of its
    drawn box on that side, which does not move, and taller about the box's middle (kept inside the canvas). The box
    follows. Straight alpha through Pillow, then the halo guard, as `effect` does."""
    if not squash or not squash[0] or not frame.box[2]:
        return frame
    from PIL import Image

    amount, side = squash
    sx = 1.0 - EDGE_SQUASH * max(0.0, min(1.0, amount))
    left, top, right, bottom = frame.box
    w, h = frame.width, frame.height
    ax, cy = (left if side < 0 else right), (top + bottom) / 2.0
    # the stretch is held where the scaled box stays inside the canvas
    sy = max(1.0, min(1.0 + 0.5 * (1.0 - sx), cy / max(1.0, cy - top), (h - cy) / max(1.0, bottom - cy)))
    image = Image.frombytes("RGBA", (w, h), frame.bgra, "raw", "BGRa")
    # output (x, y) takes its colour from input (ax + (x - ax) / sx, cy + (y - cy) / sy)
    image = image.transform((w, h), Image.Transform.AFFINE, (1.0 / sx, 0.0, ax - ax / sx, 0.0, 1.0 / sy, cy - cy / sy), Image.Resampling.BILINEAR)
    clear = clear_faint_alpha(image)
    box = (round(ax + (left - ax) * sx), round(cy + (top - cy) * sy), round(ax + (right - ax) * sx), round(cy + (bottom - cy) * sy))
    return Frame(w, h, premultiplied_bgra(clear), frame.pad_x, frame.pad_y, box)


def effect(frame: Frame, fx: tuple[str, float, int] | None, alpha: float) -> Frame:
    """The frame as a vanish, an arrival or a ride shows it (INBOX 1670): the figure's alpha scaled by `alpha`
    (clear below FADE_CLEAR), with a portal ring, smoke, sparkles, a cloud or a bubble. `fx` is (kind, strength
    0..1, facing); the plain fade is `fx` None. The canvas grows by `fx_margin` all round while an effect shows
    (the window keeps its place through `pad`), so nothing is clipped. Straight alpha through Pillow, then the
    halo guard, so a faint edge takes no click. The box moves with the figure (the quick panel is placed from it)."""
    if fx is None and alpha >= 1.0:
        return frame
    from PIL import Image, ImageDraw, ImageFilter

    w, h = frame.width, frame.height
    image = Image.frombytes("RGBA", (w, h), frame.bgra, "raw", "BGRa")
    share = 0.0 if alpha < FADE_CLEAR else max(0.0, min(1.0, alpha))
    if share < 1.0:
        image.putalpha(image.getchannel("A").point(lambda a: int(a * share)))
    box = frame.box
    if fx is not None and fx[1] > 0.0:
        kind, strength, face = fx
        left, top, right, bottom = box if box[2] else (0, 0, w, h)
        m = fx_margin(frame)
        grown = Image.new("RGBA", (w + 2 * m, h + 2 * m), (0, 0, 0, 0))
        grown.paste(image, (m, m))
        image, box = grown, (box[0] + m, box[1] + m, box[2] + m, box[3] + m)
        layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        phase = strength  # a sparkle's turn and a bubble's rise follow the strength, so a step of it is a new picture
        _draw_fx(ImageDraw.Draw(layer), kind, strength, face, (left + right) / 2.0 + m, (top + bottom) / 2.0 + m, right - left, bottom - top, phase)
        layer = layer.filter(ImageFilter.GaussianBlur(1.5 if kind in ("portal", "blink", "bubble") else max(2.0, (right - left) * 0.04)))
        image = Image.alpha_composite(layer, image) if kind == "cloud" else Image.alpha_composite(image, layer)
        w, h = image.size
        frame = frame._replace(pad_x=frame.pad_x + m, pad_y=frame.pad_y + m)
    clear = clear_faint_alpha(image)
    return Frame(w, h, premultiplied_bgra(clear), frame.pad_x, frame.pad_y, box)
