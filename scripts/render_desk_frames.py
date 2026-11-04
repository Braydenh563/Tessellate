"""Render the desktop companion's overlay frames (BACKLOG 16, O2).

    PYTHONPATH=src BASE=http://127.0.0.1:8828 .venv/bin/python scripts/render_desk_frames.py

Boots nothing itself: `BASE` is a running app (`bash scratchpad/ui-sweeps/serve.sh
8828 <dir>`). `scripts/render_desk_frames.js` captures every frame of Atlas, both
looks, with a transparent background at device scale 2; this script zeroes the
faint alpha (the halo guard `sprites.py` also applies), crops every frame of a
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

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from tessellate.core.overlay import sprites  # noqa: E402

PAD = 2
#: Fewer colours with their alpha kept: a quarter of the bytes for frames that are soft gradients.
COLOURS = 256


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
        subprocess.run(["node", str(ROOT / "scripts" / "render_desk_frames.js"), raw], check=True, env=env, cwd=ROOT)
        total = 0
        for look in sprites.LOOKS:
            images = {name: Image.open(Path(raw) / look / f"{name}.png").convert("RGBA") for name in sprites.FRAME_NAMES}
            box = crop_box(list(images.values()))
            target = out / look
            if target.exists():
                shutil.rmtree(target)
            target.mkdir(parents=True)
            for name, im in images.items():
                im = im.crop(box)
                alpha = im.getchannel("A").point(lambda a: 0 if a < sprites.ALPHA_FLOOR else a)
                im.putalpha(alpha)
                small = im.quantize(colors=COLOURS, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
                small.save(target / f"{name}.png", optimize=True)
                total += (target / f"{name}.png").stat().st_size
            print(f"{look}: {len(images)} frames, {box[2] - box[0]}x{box[3] - box[1]} px")
        print(f"total {total / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
