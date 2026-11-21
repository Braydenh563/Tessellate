"""Source text: ui-modernisation 60. From 820 to 1199 the tab buttons keep the
44px floor (10-responsive.css) and the strip adds 2px of well each side, so the
strip is 48px; the bar was 44 since Phase 12 (`--topbar-h` 2.75rem), and the
centred strip stuck out of it by 2.5px at the top (tour.js at 1184x760 measured
`#tab-bar` at top -2.5, height 48, in a 44px bar; at 1280 it is 36 inside 44).
The band raises `--topbar-h` so its padding leaves room for the strip."""

import re

from tests._css_paths import css_text


def _band() -> str:
    css = css_text()
    start = css.index("@media (min-width: 820px) and (max-width: 1199.98px) {\n  #tab-bar button {\n    gap")
    return css[start : css.index("\n}\n", start)]


def test_the_band_keeps_the_44px_floor_on_the_strip():
    assert "--target-min: max(2.75rem, 44px);" in _band()


def test_the_bar_in_the_band_is_tall_enough_for_the_strip():
    # strip = floor (44) + 2 * 2px well; bar = 2 * pad-y + control (36) + 1px border,
    # with pad-y = (topbar-h - control - 1) / 2, so the bar is `--topbar-h`.
    match = re.search(r"header#top-bar\.tabs-centred:not\(\.tabs-wrapped\) \{\s*--topbar-h: ([\d.]+)rem;", _band())
    assert match, "the band does not set --topbar-h on the header"
    assert float(match.group(1)) * 16 >= 44 + 2 * 2 + 1
