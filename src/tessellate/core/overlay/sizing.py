"""The desk figure's size handle, at parity with the in-app one (`nameMarkBuddySetSize`, the grip in
avatars.js): the same range, the same pull rate, a double press back to Medium. The size is a multiplier
on the monitor's dpi, so every frame, box and metric the figure already has follows it.

Pure functions and constants here; the runner owns the state (`OverlayRunner._size_*`)."""

from __future__ import annotations

import math
from typing import Any

from tessellate.core.overlay.sprites import Frame, premultiplied_bgra

#: The app keeps 0.7 to 1.6 (`nameMarkBuddyScaleSaved`); Medium is 1.
MIN_SCALE, MAX_SCALE, MEDIUM = 0.7, 1.6, 1.0
#: A size is one of these steps: a drag changes the window at most once per step, and the frame cache
#: holds the current step only (`SpriteSet.keep_only`).
STEP = 0.05
#: Two presses this close in time and place are a double (the app's grip: 400 ms, 12 px).
DOUBLE_S, DOUBLE_PX = 0.4, 12
#: The pull must move this far before it is a drag (the app's 4 px).
SLOP_PX = 4
#: The handle shows this long after the pointer last moved over the figure, and while it is held.
SHOW_S = 1.2
#: A pull with no pointer event for this long is over (a release that never arrived: a lost grab, a lock screen).
PULL_IDLE_S = 8.0
#: A size just pulled is kept against the page's older value for this long, while the write-back reaches it.
PENDING_S = 6.0
#: The least hit box of the handle, in px at 96 dpi (scaled with the monitor), and the gap kept from the figure's corner.
HIT_PX, GAP_PX = 24, 2
#: Ring colour (the app's accent) and fill (its card), as straight RGBA.
RING, FILL = (79, 70, 229, 255), (255, 255, 255, 255)
#: Alpha of the hit box under the ring: above `sprites.ALPHA_FLOOR` (8), so it takes the press, and too faint to see.
HIT_ALPHA = 12


def clamp(scale: Any) -> float:
    """A size the app could hold, on the step grid; Medium for anything that is not a number."""
    try:
        value = float(scale)
    except (TypeError, ValueError):
        return MEDIUM
    if not math.isfinite(value):
        return MEDIUM
    return round(round(min(MAX_SCALE, max(MIN_SCALE, value)) / STEP) * STEP, 2)


def pulled(was: float, start_dist: float, dist: float, dpi: int) -> float:
    """The size after a pull from `start_dist` to `dist` (physical px from the stand or hang point): the
    app's formula, `was * (1 + (dist - from) / max(from, 100))`, in CSS px (so `dpi / 96` of them)."""
    k = max(0.25, dpi / 96.0)
    start = max(8.0, start_dist / k)
    return was * (1 + (dist / k - start) / max(start, 100.0))


def hit_side(dpi: int) -> int:
    return max(HIT_PX, round(HIT_PX * dpi / 96.0))


#: The least alpha that counts as the figure for the handle's corner: the glow and wisps below it are drawn but faint
#: (the drawn box keeps them, for hit testing), and a handle hung on their corner floats in empty space (INBOX 1692 h).
SOLID_ALPHA = 128


def solid_box(frame: Frame) -> tuple[int, int, int, int]:
    """The box of the frame's solid pixels (left, top, right, bottom): where the handle's corner is. The drawn box
    when nothing is that solid."""
    from PIL import Image

    alpha = Image.frombytes("L", (frame.width, frame.height), bytes(frame.bgra[3::4]))
    box = alpha.point(lambda a: 255 if a >= SOLID_ALPHA else 0).getbbox()
    if box:
        return tuple(box)  # type: ignore[return-value]
    return frame.box if frame.box[2] else (0, 0, frame.width, frame.height)


def hit_box(box: tuple[int, int, int, int], hanging: bool, dpi: int, left: bool = False) -> tuple[int, int, int, int]:
    """The handle's hit box (left, top, right, bottom) in the frame's own pixels: GAP_PX off the figure's drawn
    corner, top right when it stands and bottom right when it hangs (the app's, since 9d5fd92). It may lie outside
    the canvas; `with_handle` grows the canvas to hold it, since the layered window takes no click outside it.
    `left`: on the figure's left corner instead, when the right one would put the window off the monitor."""
    side, gap = hit_side(dpi), max(GAP_PX, round(GAP_PX * dpi / 96.0))
    top = box[3] + gap if hanging else box[1] - gap - side
    x = box[0] - gap - side if left else box[2] + gap
    return x, top, x + side, top + side


def pulls_nwse(box: tuple[int, int, int, int], hit: tuple[int, int, int, int], hanging: bool) -> bool:
    """Whether the handle at `hit` pulls along the top-left to bottom-right diagonal (bottom right hanging, top left
    standing) rather than bottom-left to top-right: the cursor shown over it, as on the app's grip (1692 j)."""
    return hanging != (hit[0] < box[0])


#: The ring is drawn this many times larger and scaled down, so its edge is smooth like the app's CSS circle
#: (the owner, 2026-11-07: "the resize circle is different with the desktop companion compared to the in-app one").
RING_SS = 4


def ring_tile(side: int, hot: bool) -> "Any":
    """The handle's ring on a transparent `side` square: the app's grip (a 12 CSS px circle, a 2 px accent border,
    a card fill) at the monitor's dpi, antialiased. A held handle grows by 1.5 px, as before."""
    from PIL import Image, ImageDraw

    big = side * RING_SS
    tile = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    r = (side * 0.25 + (1.5 if hot else 0.0)) * RING_SS
    c = big / 2.0
    ImageDraw.Draw(tile).ellipse((c - r, c - r, c + r, c + r), fill=FILL, outline=RING, width=max(2, round(side / 12)) * RING_SS)
    return tile.resize((side, side), Image.LANCZOS)


def with_handle(frame: Frame, hit: tuple[int, int, int, int], hot: bool) -> tuple[Frame, tuple[int, int, int, int]]:
    """`frame` with the handle drawn over it, on a canvas grown (transparent, with `pad` keeping the window's
    place) where the hit box lies outside it, and the hit box in the new canvas: a faint box (so the whole of it
    takes the press) and the ring."""
    from PIL import Image, ImageDraw

    image = Image.frombytes("RGBA", (frame.width, frame.height), frame.bgra, "raw", "BGRa")
    lead, up, right, down = max(0, -hit[0]), max(0, -hit[1]), max(0, hit[2] - frame.width), max(0, hit[3] - frame.height)
    if lead or up or right or down:
        grown = Image.new("RGBA", (frame.width + lead + right, frame.height + up + down), (0, 0, 0, 0))
        grown.paste(image, (lead, up))
        image = grown
    hit = (hit[0] + lead, hit[1] + up, hit[2] + lead, hit[3] + up)
    draw_on = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(draw_on)
    draw.rectangle((hit[0], hit[1], hit[2] - 1, hit[3] - 1), fill=(*RING[:3], HIT_ALPHA))
    side = hit[2] - hit[0]
    draw_on.alpha_composite(ring_tile(side, hot), (hit[0], hit[1]))
    image = Image.alpha_composite(image, draw_on)
    box = frame.box
    moved = (box[0] + lead, box[1] + up, box[2] + lead, box[3] + up)
    return Frame(image.width, image.height, premultiplied_bgra(image), frame.pad_x + lead, frame.pad_y + up, moved), hit
