"""Draw the reminder card frames, `card0` and `card1` (overlay roam and carry).

    PYTHONPATH=src .venv/bin/python scripts/render_card_frames.py

Needs the frames `render_desk_frames.py` made: it takes each look's `stand` and
`wave` frame, draws a small reminder card (a bell on a light card with a shadow)
in the figure's hand, and writes `card0.png` and `card1.png` beside them, same
size, same registration, so the pair swaps like any other frame. Pillow only; no
browser, so it can run at build time. The two differ by a lift of the card and
the pose underneath, which is what makes the pair read as a small bob.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from tessellate.core.overlay import capture  # noqa: E402

DESK = ROOT / "frontend" / "img" / "desk"
LIFT = capture.CARD_LIFT


def render_look(look: str) -> None:
    folder = DESK / look
    for name, under, lift in (("card0", "stand", (0, 0)), ("card1", "wave", LIFT)):
        base = Image.open(folder / f"{under}.png").convert("RGBA")
        capture.draw_card(base, lift).save(folder / f"{name}.png", optimize=True)


def main() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from tessellate.core.overlay import sprites

    for look in sprites.LOOKS:
        render_look(look)
        print(look, "card0, card1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
