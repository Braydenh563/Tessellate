"""The one preparation step every Tesseract read goes through (INBOX 1568).

**Why it exists.** A region drawn round the "Goal" box of a board export came
back "No text was found in that region", and the whole page read as garbage:
the labels are about 8 px tall, dark on a light box, over a dark canvas.
Tesseract is trained on text about 30 px tall (its own documentation says
below roughly 20 px accuracy falls off a cliff), and it assumes dark text on a
light ground. A screenshot, a canvas export or a phone photo of a slide breaks
both assumptions at once, and nothing in the read said so: an empty answer
looks exactly like a page with no words on it.

So before Tesseract sees a picture it is made to look like the pages it was
trained on: grey, light ground, text near 30 px, two tones found by Otsu. The
decisions are plain numbers over a grey histogram (`otsu_threshold`,
`is_dark_ground`, `scale_factor`), so they are tested without Pillow or the
binary; only `prepare` touches pixels.

**Otsu stretches, it does not cut.** The first version cut at Otsu's level (a
hard black and white). Measured on an 8 px label (tests/test_ocr_prep_1568.py
renders it): once enlarged, a thin anti-aliased stroke is a mid grey, and a
hard cut at the level between a dark canvas and a light box threw those strokes
away, so "Goal" read as "Gel", "ool" or "Gal" at every scale from 3 to 5. Mapping
the two Otsu class means to black and white keeps the strokes and still gives
Tesseract the full two-tone contrast, and "Goal" reads every time. Pillow is imported where it is used:
this file has to stay importable without it, like the rest of `ocr.py`.

The text height is measured, not assumed: a row-to-row edge map's rows are grouped into
bands (a line of text is a run of rows with edges in them) and the median band
height is the text height. A band that is not text, such as a box border, is a
run of one or two rows and is dropped, which is why a label inside a drawn box
is still measured as a label.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

#: Tesseract's sweet spot for a capital letter's height is about 30 px; the
#: bands measured here include ascenders and descenders, a little taller, so
#: the target is the band height and not the cap height.
TARGET_TEXT_PX = 30.0

#: Never blow a picture up by more than this: a mis-measured band (noise read
#: as 1 px text) must not turn a page into a 100-megapixel buffer.
MAX_SCALE = 6.0

#: Below this ratio a resample costs more (blur) than it earns.
MIN_USEFUL_SCALE = 1.25

#: The largest picture handed to Tesseract after scaling. Its memory use grows
#: with the pixel count and a slow read is worse than a slightly smaller one.
MAX_PIXELS = 16_000_000

#: A ground whose median grey is below this is dark. 128 is the midpoint of
#: the 0 to 255 range; a screenshot in a dark theme sits well under it and a
#: scanned page well over it, so the exact value is not delicate.
DARK_GROUND_BELOW = 128

#: An edge response (0 to 255) at or above this counts as an edge.
EDGE_LEVEL = 48

#: A row is "inked" when at least this fraction of its pixels are edges. Low on
#: purpose: a single 8 px label on a wide board covers a few percent of a row.
ROW_INK_FRACTION = 0.006

#: Runs of fewer rows than this are borders and rules, not lines of text.
MIN_BAND_ROWS = 3

#: A band taller than this many rows is a picture or a merged block, not one
#: line of text, and is left out of the measurement.
MAX_BAND_ROWS = 160


def _total(hist: Sequence[int]) -> int:
    return int(sum(hist))


def median_grey(hist: Sequence[int]) -> int:
    """The grey level half the pixels are at or below (the ground, when the
    ground is most of the picture)."""
    total = _total(hist)
    if total <= 0:
        return 255
    half, seen = total / 2, 0
    for level, count in enumerate(hist):
        seen += count
        if seen >= half:
            return level
    return len(hist) - 1


def is_dark_ground(hist: Sequence[int]) -> bool:
    """True when most of the picture is dark, so the read should be inverted
    to the dark-text-on-light page Tesseract expects."""
    return _total(hist) > 0 and median_grey(hist) < DARK_GROUND_BELOW


def otsu_threshold(hist: Sequence[int]) -> int:
    """Otsu's level: the grey that best splits the histogram in two (maximum
    between-class variance). Pixels at or below it are one tone, above it the
    other. A flat picture (one grey) returns that grey, so nothing splits."""
    total = _total(hist)
    if total <= 0:
        return 128
    weighted_all = sum(level * count for level, count in enumerate(hist))
    below = 0
    weighted_below = 0
    best_level, best_variance = 0, -1.0
    for level, count in enumerate(hist):
        below += count
        if below == 0:
            continue
        above = total - below
        if above == 0:
            break
        weighted_below += level * count
        mean_below = weighted_below / below
        mean_above = (weighted_all - weighted_below) / above
        variance = below * above * (mean_below - mean_above) ** 2
        if variance > best_variance:
            best_variance, best_level = variance, level
    return best_level


def class_means(hist: Sequence[int], level: int) -> tuple[float, float]:
    """The mean grey at or below `level` and the mean above it: the two tones
    Otsu found (dark ink or canvas, light ground)."""
    low = sum(hist[: level + 1])
    high = sum(hist[level + 1 :])
    mean_low = sum(i * c for i, c in enumerate(hist[: level + 1])) / low if low else 0.0
    mean_high = (
        sum((i + level + 1) * c for i, c in enumerate(hist[level + 1 :])) / high if high else 255.0
    )
    return mean_low, mean_high


def stretch_table(hist: Sequence[int]) -> list[int]:
    """A 256-entry lookup mapping Otsu's dark tone to 0 and its light tone to
    255, linear between and clamped outside. A flat picture (the tones are the
    same grey) maps to itself rather than dividing by zero."""
    low, high = class_means(hist, otsu_threshold(hist))
    span = high - low
    if span < 8:
        return list(range(256))
    return [int(min(255, max(0, (v - low) / span * 255))) for v in range(256)]


def scale_factor(text_px: float, width: int, height: int) -> float:
    """How much to enlarge a picture whose text is `text_px` tall.

    1.0 when the text is already big enough (or could not be measured, `0`),
    never more than `MAX_SCALE`, and cut back so the result stays under
    `MAX_PIXELS`. A ratio under `MIN_USEFUL_SCALE` is not worth a resample.
    """
    if text_px <= 0 or width <= 0 or height <= 0:
        return 1.0
    wanted = min(TARGET_TEXT_PX / text_px, MAX_SCALE)
    room = (MAX_PIXELS / (width * height)) ** 0.5
    scale = min(wanted, room)
    if scale < MIN_USEFUL_SCALE:
        return 1.0
    return round(scale, 3)


def band_heights(row_ink: Sequence[float]) -> list[int]:
    """Heights of the runs of inked rows, in order. `row_ink` is the fraction
    of edge pixels in each row; a run is consecutive rows at or above
    `ROW_INK_FRACTION`."""
    heights: list[int] = []
    run = 0
    for value in row_ink:
        if value >= ROW_INK_FRACTION:
            run += 1
        elif run:
            heights.append(run)
            run = 0
    if run:
        heights.append(run)
    return heights


def text_height_from_bands(heights: Sequence[int]) -> float:
    """The median of the bands that can be a line of text, or 0.0."""
    lines = sorted(h for h in heights if MIN_BAND_ROWS <= h <= MAX_BAND_ROWS)
    if not lines:
        return 0.0
    return float(lines[len(lines) // 2])


def estimate_text_height(grey) -> float:
    """The height in pixels of a line of text in a grey Pillow image, or 0.0
    when none can be told apart. Edges, then row bands (see the module note)."""
    from PIL import Image, ImageChops  # noqa: PLC0415  # optional extra, imported where it is used

    width, height = grey.size
    if width < 4 or height < 4:
        return 0.0
    #: Each row against the one above it: a letter's tops, bottoms and bowls
    #: change between rows, a box's left and right sides never do, so a drawn
    #: box is not mistaken for a line of text as tall as itself.
    edges = ImageChops.difference(grey, ImageChops.offset(grey, 0, 1)).point(
        lambda v: 255 if v >= EDGE_LEVEL else 0
    )
    rows = edges.resize((1, height), resample=Image.Resampling.BOX)  # averaging: the inked share of each row
    ink = [value / 255.0 for value in rows.tobytes()]
    return text_height_from_bands(band_heights(ink))


def to_grey(img):
    """Grey, with transparency flattened onto white: a PNG whose ground is
    transparent keeps black under the alpha, which would read as a dark page."""
    from PIL import Image  # noqa: PLC0415  # optional extra, imported where it is used

    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        flat = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        flat.alpha_composite(rgba)
        return flat.convert("L")
    return img.convert("L")


class Prepared(NamedTuple):
    """The picture to read and how much bigger than the original it is, so a
    box Tesseract reports on it can be put back on the original."""

    image: object
    scale: float


def prepare(img) -> Prepared:
    """The picture Tesseract should read: grey, dark text on a light ground,
    text near `TARGET_TEXT_PX`, the two Otsu tones at full contrast. Pure: the
    input is untouched."""
    from PIL import Image, ImageOps  # noqa: PLC0415  # optional extra, imported where it is used

    grey = to_grey(img)
    if is_dark_ground(grey.histogram()):
        grey = ImageOps.invert(grey)
    scale = scale_factor(estimate_text_height(grey), *grey.size)
    if scale > 1.0:
        size = (max(1, round(grey.width * scale)), max(1, round(grey.height * scale)))
        grey = grey.resize(size, resample=Image.Resampling.LANCZOS)
    return Prepared(grey.point(stretch_table(grey.histogram())), scale)
