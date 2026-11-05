"""Frames for a companion that has none shipped (INBOX 1684): the person's own, drawn by the app.

The app window draws the figure (`frontend/js/desk-frames.js`, the same poses as the build script's
Atlas capture, done inside the page) and hands over one wide transparent PNG per frame. Here they are
cropped to one shared box, so every frame stays registered, given the reminder card frames, and kept
under the data folder as `desk_frames/<key>/<frame>.png`, where `sprites.SpriteSet` reads them as it
reads a shipped look. The key is a hash of what the figure looks like, so a change to the name, the
persona, the character's parts or its size is a new key, and the old set is left to be pruned.

Written to a temporary folder and renamed whole: a set is complete or not there, never half drawn.
Pillow is in the `desktop` extra: imported on use.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import re
import shutil
import time
from pathlib import Path
from typing import Any, Callable

from tessellate.core.overlay import sprites

logger = logging.getLogger(__name__)

#: A cache key: "c-" and twelve hex digits of the figure's signature.
KEY = re.compile(r"c-[0-9a-f]{12}")
#: Pixels of clear around the drawn pixels of every frame together, in the capture's 2x pixels.
PAD = 4
#: Sets kept: the newest by time, the rest pruned when a new one lands (a figure the person changed back and forth).
KEEP = 6
#: What the page captures; the rest (`card0`, `card1`) are drawn here, and the lidded sit is derived on load.
CAPTURED = tuple(n for n in sprites.FRAME_NAMES if n not in sprites.CARD_FRAMES)

#: Where the reminder card sits as a share of the frame (centre x, centre y), its size in 2x pixels and its lift.
CARD_CENTRE = (0.66, 0.60)
CARD_SIZE = (46, 58)
CARD_LIFT = (0, -5)


#: What the app window says of the companion it draws, as a JSON object's text (one expression, spliced into
#: `desk_companion.LOOK_SCRIPT`): `atlas` when the figure is Atlas (the chat's default persona is), and `sig`, a
#: hash of the figure's markup without what moves on its own (delays, the eyes' look, transforms), so the same
#: figure gives the same text across reloads and any change to a name, persona, part or size changes it.
FIGURE_JS = (
    "(function(){var f=document.querySelector('#nm-buddy .nm-figure');if(!f)return {atlas:false,sig:''};"
    "var t=f.outerHTML.replace(/(--nm-delay|--nm-l[xy]|--nm-[a-z]*-?delay|transform|translate|rotate|scale|opacity)\\s*:[^;\"]*;?/g,'');"
    "var h=2166136261,g=5381;for(var i=0;i<t.length;i++){var c=t.charCodeAt(i);h=Math.imul(h^c,16777619)>>>0;g=(Math.imul(g,33)+c)>>>0}"
    "return {atlas:!!(f.classList.contains('atl-figure-box')||f.querySelector('.atl-lw')),sig:h.toString(16)+g.toString(16)}})()"
)
#: Loads the capture module when it is not there yet; says "ready", "loading" or "error".
LOAD_SCRIPT = (
    "(function(){try{if(typeof deskFramesStart==='function')return 'ready';"
    "if(typeof lazyScript==='function'){lazyScript('/js/desk-frames.js');return 'loading'}return 'error'}catch(e){return 'error'}})()"
)
START_SCRIPT = "(function(){try{return String(deskFramesStart(null))}catch(e){return 'error'}})()"
NEXT_SCRIPT = "(function(){try{return deskFramesNext()}catch(e){return JSON.stringify({error:String(e)})}})()"
STOP_SCRIPT = "(function(){try{deskFramesStop()}catch(e){}return 'ok'})()"
#: How long the page gets to load the module, to answer a poll, and to draw every frame.
LOAD_WAIT = 10.0
POLL_EVERY = 0.05
FRAME_WAIT = 15.0
TOTAL_WAIT = 180.0
ASK_WAIT = 10.0


class CaptureError(Exception):
    """The app window could not give the frames; the message says why, for the log."""


def _frame_of(answer: str) -> tuple[str, Any] | None:
    """One poll's answer as (name, image), None at the end; CaptureError for anything else."""
    try:
        data = json.loads(answer)
    except (TypeError, ValueError) as exc:
        raise CaptureError("a frame answer was not readable") from exc
    if not isinstance(data, dict):
        raise CaptureError("a frame answer was not an object")
    if data.get("error"):
        raise CaptureError(str(data["error"])[:200])
    if data.get("done"):
        return None
    name = data.get("name")
    if name not in CAPTURED:
        raise CaptureError(f"an unknown frame {str(name)[:20]!r}")
    try:
        return name, decode(data.get("png"))
    except ValueError as exc:
        raise CaptureError(f"{name} was not a picture") from exc


def _started(ask: Callable[[str], Any], sleep: Callable[[float], Any], clock: Callable[[], float]) -> None:
    """The page's capture module loaded and a capture begun, or CaptureError."""
    deadline = clock() + LOAD_WAIT
    while ask(LOAD_SCRIPT) != "ready":
        if clock() > deadline:
            raise CaptureError("the capture module did not load")
        sleep(0.25)
    started = ask(START_SCRIPT)
    if not (isinstance(started, str) and started.isdigit()):
        raise CaptureError(f"the capture did not start ({started!r})")


def fetch_frames(ask: Callable[[str], Any], sleep: Callable[[float], Any] = time.sleep, clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    """Every captured frame of the figure in the app window, name to RGBA image. `ask(script)` runs a script
    there and returns its text, or None when the window did not answer. Raises `CaptureError`."""
    _started(ask, sleep, clock)
    frames: dict[str, Any] = {}
    end, waiting = clock() + TOTAL_WAIT, clock()
    while True:
        answer = ask(NEXT_SCRIPT)
        now = clock()
        if now > end or now - waiting > FRAME_WAIT:
            ask(STOP_SCRIPT)
            raise CaptureError("the capture took too long")
        if answer == "wait" or answer is None:
            sleep(POLL_EVERY)
            continue
        waiting = now
        got = _frame_of(answer)
        if got is None:
            return frames
        frames[got[0]] = got[1]


def key_for(signature: Any) -> str | None:
    """The cache key for the figure's signature the app window gave, or None when it gave none
    worth keying (empty, or too long to be one)."""
    text = str(signature or "")
    if not text or len(text) > 256:
        return None
    return "c-" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def is_key(look: Any) -> bool:
    return isinstance(look, str) and KEY.fullmatch(look) is not None


def cache_root() -> Path:
    """`desk_frames` in the data folder."""
    from tessellate.core.config import resolved_data_dir

    return resolved_data_dir() / "desk_frames"


def complete(key: str, root: Path | None = None) -> bool:
    """True when every frame a set needs is there."""
    folder = (root or cache_root()) / key
    return is_key(key) and all((folder / f"{name}.png").is_file() for name in sprites.FRAME_NAMES)


def draw_card(base: Any, lift: tuple[int, int]) -> Any:
    """`base` (RGBA) with a small reminder card held out in front of it: a bell on a light card with a shadow."""
    from PIL import Image, ImageDraw, ImageFilter

    w, h = base.size
    cx, cy = int(w * CARD_CENTRE[0]) + lift[0], int(h * CARD_CENTRE[1]) + lift[1]
    box = (cx - CARD_SIZE[0] // 2, cy - CARD_SIZE[1] // 2, cx + CARD_SIZE[0] // 2, cy + CARD_SIZE[1] // 2)
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((box[0] + 2, box[1] + 4, box[2] + 2, box[3] + 4), 7, fill=(40, 40, 80, 90))
    out = Image.alpha_composite(base, shadow.filter(ImageFilter.GaussianBlur(2)))
    d = ImageDraw.Draw(out)
    d.rounded_rectangle(box, 7, fill=(250, 248, 240, 255), outline=(120, 110, 170, 255), width=2)
    bx, by = (box[0] + box[2]) // 2, box[1] + 18
    d.pieslice((bx - 10, by - 10, bx + 10, by + 10), 180, 360, fill=(226, 168, 60, 255))
    d.rectangle((bx - 10, by, bx + 10, by + 6), fill=(226, 168, 60, 255))
    d.ellipse((bx - 3, by + 7, bx + 3, by + 13), fill=(180, 120, 30, 255))
    d.line((box[0] + 9, box[3] - 14, box[2] - 9, box[3] - 14), fill=(150, 145, 190, 255), width=2)
    d.line((box[0] + 9, box[3] - 8, box[2] - 17, box[3] - 8), fill=(150, 145, 190, 255), width=2)
    return out


def decode(png_base64: Any) -> Any:
    """One frame the page sent, as an RGBA image; ValueError when it is not a picture."""
    from PIL import Image

    try:
        raw = base64.b64decode(str(png_base64), validate=True)
        with Image.open(io.BytesIO(raw)) as im:
            return im.convert("RGBA")
    except Exception as exc:  # noqa: BLE001 - whatever the page sent, it is one answer: not a picture
        raise ValueError("not a picture") from exc


def common_box(images: list[Any]) -> tuple[int, int, int, int]:
    """One crop for every frame: the union of their drawn pixels (alpha at the halo floor or more) with `PAD`."""
    left = top = 10**9
    right = bottom = 0
    for im in images:
        box = im.getchannel("A").point(lambda a: 255 if a >= sprites.ALPHA_FLOOR else 0).getbbox()
        if box:
            left, top, right, bottom = min(left, box[0]), min(top, box[1]), max(right, box[2]), max(bottom, box[3])
    width, height = images[0].size
    if right <= left or bottom <= top:
        raise ValueError("nothing was drawn")
    return max(0, left - PAD), max(0, top - PAD), min(width, right + PAD), min(height, bottom + PAD)


def touches_edge(im: Any) -> bool:
    """True when a drawn pixel is on the left, right or bottom edge: the capture's box cut the figure."""
    box = im.getchannel("A").point(lambda a: 255 if a >= sprites.ALPHA_FLOOR else 0).getbbox()
    return bool(box) and (box[0] <= 0 or box[2] >= im.width or box[3] >= im.height)


def write_set(key: str, frames: dict[str, Any], root: Path | None = None) -> Path:
    """Crop `frames` (name to RGBA image, every name in `CAPTURED`) to one box, add the card frames, and
    write the set as `<root>/<key>/<frame>.png` in one rename. ValueError for a set that is short, empty
    or cut by its own capture box; the folder is not made then."""
    if not is_key(key):
        raise ValueError("bad key")
    missing = [n for n in CAPTURED if n not in frames]
    if missing:
        raise ValueError(f"frames missing: {missing[:3]}")
    sizes = {frames[n].size for n in CAPTURED}
    if len(sizes) != 1:
        raise ValueError("frames differ in size")
    cut = [n for n in CAPTURED if touches_edge(frames[n])]
    if cut:
        raise ValueError(f"the capture box cut {cut[:3]}")
    box = common_box([frames[n] for n in CAPTURED])
    cropped = {n: frames[n].crop(box) for n in CAPTURED}
    cropped["card0"] = draw_card(cropped["stand"], (0, 0))
    cropped["card1"] = draw_card(cropped["wave"], CARD_LIFT)
    base = root or cache_root()
    base.mkdir(parents=True, exist_ok=True)
    work = base / f".{key}.part"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    try:
        for name, im in cropped.items():
            im.save(work / f"{name}.png", optimize=True)
        final = base / key
        shutil.rmtree(final, ignore_errors=True)
        work.rename(final)
    except OSError:
        shutil.rmtree(work, ignore_errors=True)
        raise
    prune(base, keep=key)
    return final


def prune(root: Path, keep: str = "") -> None:
    """Sets beyond the newest `KEEP` are removed (never `keep`)."""
    try:
        sets = sorted((p for p in root.iterdir() if is_key(p.name) and p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return
    for old in sets[KEEP:]:
        if old.name != keep:
            shutil.rmtree(old, ignore_errors=True)
