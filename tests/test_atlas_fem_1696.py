"""Her design pass (INBOX 1696 r, ff): what read wrong at 64 px.

Measured with `scratchpad/ui-sweeps/atlasm1108.js` (the masculine pass's
measure) on the feminine look, light theme, 64 and 128 px: her forehead
stood 1.13:1 off the page and her chest 1.21:1 (his 1.21 and 1.41), the
weakest tenth of her head's outline 1.31:1 (his 1.71), so she melted into a
light page. And her brows, at opacity 0.22, did not show at 64 px, so sad,
worried and calm wore the same face. The fixes live in the lazy Atlas sheet
(`frontend/css/atlas-lazy.css`), not boot CSS, but for the four
colours, which belong in a colour file.
"""

from __future__ import annotations

import re
from pathlib import Path
from tests._css_paths import sheets

ROOT = Path(__file__).resolve().parents[1]
LAZY = (ROOT / "frontend" / "css" / "atlas-lazy.css").read_text(encoding="utf-8")
BOOT = sheets("07-whiteboard-misc.css", "characters-lazy.css")
#: Colour literals live in the colour files (test_style_scale): her light palette is there.
THEMES = (ROOT / "frontend" / "css" / "05-sidebars-themes.css").read_text(encoding="utf-8")
LIGHT_HER = ':root:not([data-mode="dark"]) .nm-atlas[data-atlas-look="feminine"]'


def _luma(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i : i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = out
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _block(css: str, selector: str) -> str:
    at = css.index(selector + " {")
    return css[at : css.index("}", at)]


def _vars(block: str) -> dict[str, str]:
    return dict(re.findall(r"(--atl-\w+):\s*(#[0-9a-fA-F]{6})", block))


def test_her_skin_is_a_shade_deeper_on_a_light_page() -> None:
    dark = _vars(_block(BOOT, '.nm-atlas[data-atlas-look="feminine"]'))
    light = _vars(_block(THEMES, LIGHT_HER))
    for key in ("--atl-hi", "--atl-lt", "--atl-md", "--atl-dp"):
        assert key in light, key
        # Deeper, still lilac: blue stays the strongest channel.
        assert _luma(light[key]) < _luma(dark[key]) * 0.93, (key, light[key], dark[key])
        r, g, b = (int(light[key][i : i + 2], 16) for i in (1, 3, 5))
        assert b >= max(r, g), (key, light[key])
    # Her rim is not touched: the outline is what the edge is drawn with.
    assert "--atl-rim" not in light


def test_her_outline_holds_on_a_light_page_but_not_on_the_small_busts() -> None:
    sel = LIGHT_HER + ":not(.atl-head, .atl-tiny) .atl-edge"
    block = _block(LAZY, sel)
    assert "stroke: var(--atl-rim)" in block
    width = float(re.search(r"stroke-width:\s*([\d.]+)", block).group(1))
    opacity = float(re.search(r"opacity:\s*([\d.]+)", block).group(1))
    assert 1.6 <= width <= 2.2, width
    assert 0.4 <= opacity <= 0.6, opacity


def test_her_brows_show_at_64px_and_stay_soft() -> None:
    block = _block(LAZY, ".nm-atlas .atl-brow-arch")
    opacity = float(re.search(r"opacity:\s*([\d.]+)", block).group(1))
    width = float(re.search(r"stroke-width:\s*([\d.]+)", block).group(1))
    assert 0.45 <= opacity <= 0.6, opacity
    # Softer than his (1.5): a fine arch, not a bar.
    assert width <= 1.3, width
    # The small busts keep their bold brows: that rule must outrank this one.
    assert ".nm-atlas:is(.atl-head, .atl-tiny) .atl-brow-line { opacity: 0.85;" in LAZY


def test_her_upper_lid_line_is_bolder_at_64px_but_lighter_than_his() -> None:
    """Her light-theme mood change at 64 px stayed flat (mean 17.7 of 255 on
    the calm face): the upper lid line (0.9 at opacity 0.85) vanished in a
    thumbnail. At 1.3 and full opacity it reads 18.3 to 19.3 at 1x light (two runs); 2x and dark
    held within 0.2 (atlasm1108's mood measure). His is 1.5."""
    block = _block(LAZY, '.nm-atlas[data-atlas-look="feminine"] .atl-liner:not(.atl-liner-low)')
    width = float(re.search(r"stroke-width:\s*([\d.]+)", block).group(1))
    assert 1.2 <= width < 1.5, width
    assert "opacity: 1" in block
    # The lower lid line is a hint and stays one.
    assert ".atl-liner-low { stroke: var(--atl-dp); stroke-width: 0.6" in BOOT
