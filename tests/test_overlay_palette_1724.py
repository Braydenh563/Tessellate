"""INBOX 1724: the feminine desk companion read very purple or pink beside the in-app one.

Measured in HSL on the same pose (`stand`, calm) as pixels over the app's two surfaces. The figure is split by what
it is, not by where it is (the desk frames are a different scale and crop): `shade` (strands and rims, L under 0.70),
`mid` (body and skin, 0.70 to 0.82), `light` (highlights, 0.82 and up) at alpha 200 and over, and `glow` (the
translucent stream, alpha 24 to 199). `IN_APP` is the same split of the live figure in the app (feminine look,
Playwright at device scale 2, `scratchpad/ui-sweeps/lib.js` boot, `#nm-buddy` alone on a transparent page, composited
over white for the light theme and over (20, 22, 30) for the dark one).

Before the grade, over the same bands: the shipped frames sat 0.7 to 3.1 degrees more violet in the body bands, 4.4
(light) and 10.3 (dark) in the glow, because the desk capture leaves out the app's blue aura and rings (saturation
was already within 8 points in every band, so it is left alone). The loader grades the feminine frames (`sprites.GRADE`); these numbers pin the result.
Real Windows is unverified: this is the PNG pipeline up to the premultiplied bytes.
"""

from __future__ import annotations

import colorsys
import math
from pathlib import Path

import pytest

pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from tessellate.core.overlay import sprites  # noqa: E402

DIR = Path(__file__).resolve().parent.parent / "frontend" / "img" / "desk"
SURFACE = {"light": (255, 255, 255), "dark": (20, 22, 30)}
BANDS = {"shade": (0.0, 0.70), "mid": (0.70, 0.82), "light": (0.82, 1.01)}
#: (hue degrees, saturation percent) of the in-app feminine figure, per theme and band.
IN_APP = {
    "light": {"shade": (243.0, 36.9), "mid": (244.6, 45.6), "light": (238.3, 60.7), "glow": (243.3, 44.9)},
    "dark": {"shade": (243.7, 31.4), "mid": (242.6, 40.5), "light": (238.4, 53.7), "glow": (233.5, 21.1)},
}
HUE_TOL, SAT_TOL = 6.0, 8.0


def bands(image: Image.Image, surface: tuple[int, int, int]) -> dict[str, tuple[float, float]]:
    flat = Image.new("RGBA", image.size, (*surface, 255))
    flat.alpha_composite(image)
    acc: dict[str, list[float]] = {k: [0, 0.0, 0.0, 0.0] for k in (*BANDS, "glow")}
    for (r, g, b, _), a in zip(flat.get_flattened_data(), image.getchannel("A").get_flattened_data()):
        if a < 24:
            continue
        h, lum, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        key = "glow" if a < 200 else next(n for n, (lo, hi) in BANDS.items() if lo <= lum < hi)
        t = acc[key]
        t[0] += 1
        t[1] += math.cos(h * 2 * math.pi)
        t[2] += math.sin(h * 2 * math.pi)
        t[3] += s
    return {k: (math.degrees(math.atan2(t[2], t[1])) % 360, 100 * t[3] / t[0]) for k, t in acc.items() if t[0]}


def hue_gap(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_feminine_desk_palette_is_within_the_in_app_one(theme: str) -> None:
    stand = sprites.SpriteSet("feminine", DIR)._load("stand")
    got = bands(stand, SURFACE[theme])
    assert set(got) == set(IN_APP[theme])
    for band, (hue, sat) in IN_APP[theme].items():
        assert hue_gap(got[band][0], hue) <= HUE_TOL, (theme, band, "hue", got[band][0], hue)
        assert abs(got[band][1] - sat) <= SAT_TOL, (theme, band, "sat", got[band][1], sat)


def test_the_grade_only_touches_the_feminine_look() -> None:
    raw = Image.open(DIR / "masculine" / "stand.png").convert("RGBA")
    loaded = sprites.SpriteSet("masculine", DIR)._load("stand")
    assert list(loaded.get_flattened_data()) == list(sprites.tapered(raw).get_flattened_data())
    fem = Image.open(DIR / "feminine" / "stand.png").convert("RGBA")
    assert list(sprites.SpriteSet("feminine", DIR)._load("stand").getchannel("A").get_flattened_data()) == list(
        sprites.tapered(fem).getchannel("A").get_flattened_data()
    )  # colour moves, never the alpha (the click guard's edge stays put)
