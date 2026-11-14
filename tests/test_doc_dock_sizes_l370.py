"""UX audit sizes, document dock and graph zoom (L-world-class-370 to 374).

Measured at 390/1024/1440 with getBoundingClientRect; these pin the cascade
that produced each number, since a lint cannot see a rendered page.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS_DIR = Path("frontend/css")


def _css(name: str) -> str:
    return (CSS_DIR / name).read_text(encoding="utf-8")


def _rule(text: str, selector: str) -> str:
    start = text.index(selector + " {")
    return text[start : text.index("}", start)]


def test_view_seg_buttons_are_a_finger_wide_and_tall_on_a_phone_370():
    """Edit and Read measured 37.1x36 in a 44px seg beside 44x44 neighbours."""
    css = _css("10-responsive.css")
    start = css.rindex("  #tab-documents #doc-view-seg > button {")
    rule = css[start : css.index("}", start)]
    assert "(max-width: 599.98px)" in css[css.rindex("@media", 0, start) :][:40]
    assert "min-height: var(--target-min)" in rule
    assert "min-width: var(--target-min)" in rule
