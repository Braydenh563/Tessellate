#!/usr/bin/env python3
"""Write the manual's WebP pictures (L-world-class-785) from the README shots.

    bash scratchpad/ui-sweeps/serve.sh 8861 /tmp/mm-a861
    .venv/bin/python scratchpad/ui-sweeps/seed-showcase.py 8861 /tmp/mm-a861
    BASE=http://127.0.0.1:8861 OUT=/tmp/shots ONLY=graph,timeline,whiteboard \
      PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/readmeshots.js
    .venv/bin/python scratchpad/ui-sweeps/help-images.py /tmp/shots

Reads `HELP_IMAGES` (src/tessellate/ai/help_images.py), so the list lives in one place.
"""
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from tessellate.ai.help_images import HEIGHT, HELP_IMAGES, WIDTH  # noqa: E402

shots = Path(sys.argv[1])
out = ROOT / "frontend" / "img" / "help"
out.mkdir(parents=True, exist_ok=True)
for entry in HELP_IMAGES.values():
    img = Image.open(shots / f"{entry['shot']}.png").convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS)
    img.save(out / entry["file"], "WEBP", quality=50, method=6)
    print(entry["file"], (out / entry["file"]).stat().st_size)
