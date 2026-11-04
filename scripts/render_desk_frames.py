"""Render the desktop companion's overlay frames (BACKLOG 16, O2).

    PYTHONPATH=src BASE=http://127.0.0.1:8828 .venv/bin/python scripts/render_desk_frames.py

Boots nothing itself: `BASE` is a running app (`bash scratchpad/ui-sweeps/serve.sh
8828 <dir>`). `scripts/render_desk_frames.js` captures every frame of Atlas, both
looks, with a transparent background at device scale 2; this script zeroes the
faint alpha (the halo guard `sprites.py` also applies) and stretches the rest so the figure is solid (`solidify`), crops every frame of a
look to the same box (so they stay registered), and writes
`frontend/img/desk/<look>/<frame>.png`. Needs Pillow (the `desktop` extra).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from tessellate.core.overlay import sprites  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
import render_card_frames  # noqa: E402

PAD = 2
#: Fewer colours with their alpha kept: a quarter of the bytes for frames that are soft gradients.
COLOURS = 256
#: The figure's glass, glow and wisp fades come out of the capture as soft
#: translucent washes that read as a pale ghost over a wallpaper. Alpha is
#: stretched so what is at least `SOLID_HI` is fully opaque and what is under
#: `SOLID_LO` is clear, with a short ramp between: a solid body with a soft edge.
SOLID_LO = 24
SOLID_HI = 120


def solidify(a: int) -> int:
    if a <= SOLID_LO:
        return 0
    return min(255, (a - SOLID_LO) * 255 // (SOLID_HI - SOLID_LO))


#: The nebula stream (INBOX 1660): `render_desk_frames.js` captures each frame twice, without
#: (`<name>.png`) and with (`<name>.neb.png`) the app's nebula washes. What the second adds
#: to the first is the stream; it is kept as its own soft layer under the solid body, at
#: `STREAM_SOFT` of its alpha (a pale veil, not a second body), and anything fainter than
#: `STREAM_LO` is dropped (the click guard would clear it anyway).
STREAM_LO = 10
STREAM_SOFT = 0.85


def with_stream(body: Image.Image, neb: Image.Image) -> Image.Image:
    """`body` (the capture without the nebula) solidified, with the stream the `neb`
    capture adds under it. Both are RGBA captures of the same frame."""
    extra = ImageChops.subtract(neb.getchannel("A"), body.getchannel("A"))
    extra = extra.point(lambda a: 0 if a < STREAM_LO else min(255, round(a * STREAM_SOFT)))
    veil = neb.copy()
    veil.putalpha(extra)
    solid = body.copy()
    solid.putalpha(body.getchannel("A").point(solidify))
    return Image.alpha_composite(veil, solid)


def touches_edge(im: Image.Image) -> bool:
    """True when a drawn pixel (alpha at the floor or more) is on the image's left, right or bottom edge."""
    box = im.getchannel("A").point(lambda a: 255 if a >= sprites.ALPHA_FLOOR else 0).getbbox()
    if not box:
        return False
    return box[0] <= 0 or box[2] >= im.width or box[3] >= im.height


def crop_box(images: list[Image.Image]) -> tuple[int, int, int, int]:
    left = top = 10**9
    right = bottom = 0
    for im in images:
        box = im.getchannel("A").point(lambda a: 255 if a >= sprites.ALPHA_FLOOR else 0).getbbox()
        if box:
            left, top = min(left, box[0]), min(top, box[1])
            right, bottom = max(right, box[2]), max(bottom, box[3])
    width, height = images[0].size
    return max(0, left - PAD), max(0, top - PAD), min(width, right + PAD), min(height, bottom + PAD)


def main() -> int:
    out = ROOT / "frontend" / "img" / "desk"
    with tempfile.TemporaryDirectory() as raw:
        env = {**os.environ, "BASE": os.environ.get("BASE", "http://127.0.0.1:8828"), "SCRATCH": raw}
        env.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
        if not os.environ.get("DESK_RAW"):  # DESK_RAW: reuse the captures of an earlier run (a folder of <look>/<frame>.png and .neb.png)
            subprocess.run(["node", str(ROOT / "scripts" / "render_desk_frames.js"), raw], check=True, env=env, cwd=ROOT)
        raw = os.environ.get("DESK_RAW") or raw
        total = 0
        for look in sprites.LOOKS:
            captured = {name: Image.open(Path(raw) / look / f"{name}.png").convert("RGBA") for name in sprites.FRAME_NAMES if name not in sprites.CARD_FRAMES}
            images = {name: with_stream(im, Image.open(Path(raw) / look / f"{name}.neb.png").convert("RGBA")) for name, im in captured.items()}
            #: A capture can come out blank (seen once on a cold page: eight idle frames
            #: of one look): refuse to ship it rather than a figure that vanishes.
            blank = [n for n, im in captured.items() if sum(im.getchannel("A").histogram()[128:]) < 1000]
            if blank:
                raise SystemExit(f"{look}: blank captures {blank}; run it again")
            #: A capture whose drawn pixels reach the clip's edge was cut by the clip (INBOX
            #: 1663: half an Atlas shipped): widen `BOX` in the script, never crop around it.
            cut = [n for n, im in captured.items() if touches_edge(im)]
            if cut:
                raise SystemExit(f"{look}: captures {cut} touch the clip edge; widen BOX in render_desk_frames.js")
            box = crop_box(list(images.values()))
            target = out / look
            if target.exists():
                shutil.rmtree(target)
            target.mkdir(parents=True)
            for name, im in images.items():
                im = im.crop(box)
                small = im.quantize(colors=COLOURS, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
                small.save(target / f"{name}.png", optimize=True)
                total += (target / f"{name}.png").stat().st_size
            render_card_frames.render_look(look)
            print(f"{look}: {len(images)} frames, {box[2] - box[0]}x{box[3] - box[1]} px")
        print(f"total {total / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
