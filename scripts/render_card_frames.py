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

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "frontend" / "img" / "desk"
#: Where the card sits as a share of the frame (centre x, centre y) and its size,
#: in the shipped 2x pixels: held out in front of the body on the figure's right.
CENTRE = (0.66, 0.60)
CARD = (46, 58)
LIFT = (0, -5)


def draw_card(base: Image.Image, lift: tuple[int, int]) -> Image.Image:
    w, h = base.size
    cx, cy = int(w * CENTRE[0]) + lift[0], int(h * CENTRE[1]) + lift[1]
    box = (cx - CARD[0] // 2, cy - CARD[1] // 2, cx + CARD[0] // 2, cy + CARD[1] // 2)
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((box[0] + 2, box[1] + 4, box[2] + 2, box[3] + 4), 7, fill=(40, 40, 80, 90))
    out = Image.alpha_composite(base, shadow.filter(ImageFilter.GaussianBlur(2)))
    d = ImageDraw.Draw(out)
    d.rounded_rectangle(box, 7, fill=(250, 248, 240, 255), outline=(120, 110, 170, 255), width=2)
    # A bell: dome, rim, clapper; and two lines of "text".
    bx, by = (box[0] + box[2]) // 2, box[1] + 18
    d.pieslice((bx - 10, by - 10, bx + 10, by + 10), 180, 360, fill=(226, 168, 60, 255))
    d.rectangle((bx - 10, by, bx + 10, by + 6), fill=(226, 168, 60, 255))
    d.ellipse((bx - 3, by + 7, bx + 3, by + 13), fill=(180, 120, 30, 255))
    d.line((box[0] + 9, box[3] - 14, box[2] - 9, box[3] - 14), fill=(150, 145, 190, 255), width=2)
    d.line((box[0] + 9, box[3] - 8, box[2] - 17, box[3] - 8), fill=(150, 145, 190, 255), width=2)
    return out


def render_look(look: str) -> None:
    folder = DESK / look
    for name, under, lift in (("card0", "stand", (0, 0)), ("card1", "wave", LIFT)):
        base = Image.open(folder / f"{under}.png").convert("RGBA")
        draw_card(base, lift).save(folder / f"{name}.png", optimize=True)


def main() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from tessellate.core.overlay import sprites

    for look in sprites.LOOKS:
        render_look(look)
        print(look, "card0, card1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
