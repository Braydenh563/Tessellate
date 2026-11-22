"""L806: the OCR workspace's right panel scrolls as one.

The owner (2026-11-12): its bottom scroll section is crushed very short by the
sections above it (caption, description, model read). Measured with a long
caption, a vision reading and a Tesseract reading beside it: the section list
was 0 px tall at 1366x768 and 1280x720 and 84 px at 1440x900 (scrollHeight
3,202), because it was the only thing in the column allowed to shrink. Now the
column is the scroller, the list keeps its own height, and the reading's
actions stick to the column's foot on the stuck-ground recipe.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAZY = (ROOT / "frontend/css/library-lazy.css").read_text(encoding="utf-8")
RECIPE = (ROOT / "frontend/css/08-consistency.css").read_text(encoding="utf-8")


def _body(css: str, selector: str) -> str:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    found = [m.group(1) for m in re.finditer(r"(?:^|[}\s])" + re.escape(selector) + r"\s*\{([^{}]*)\}", css)]
    assert found, selector
    return "\n".join(found)


def test_the_column_scrolls_and_the_list_is_not_crushed():
    column = _body(LAZY, ".ocr-regions")
    assert "overflow-y: auto" in column
    listing = _body(LAZY, ".ocr-region-list")
    assert "flex: none" in listing and "overflow-y: auto" not in listing, (
        "the list is a second scroller again: the sections above crush it to 0 px at laptop heights"
    )


def test_the_actions_stay_in_reach_on_the_stuck_ground_recipe():
    foot = _body(LAZY, ".ocr-card .ocr-regions-foot")
    assert "position: sticky" in foot and "bottom: 0" in foot
    start = RECIPE.index("@supports (container-type: scroll-state)")
    assert ".ocr-card .ocr-regions-foot" in RECIPE[start : start + 4000]
