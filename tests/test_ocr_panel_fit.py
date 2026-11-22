"""The OCR workspace's text column keeps room for what was read (L806, the owner 2026-11-12):
"its bottom scroll section is crushed very short by the sections above it (caption, description,
model read)". Measured with scratchpad/ui-sweeps/ocrpanelfit.js (a long caption, 28 sections and a
Tesseract reading beside them): the section list was 0px tall at 1366x768 and 1280x720, 30px at
1440x900, with the column's overflow cut off. The list now keeps a floor and the column scrolls as
one when the sections above it do not leave that much.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "frontend" / "css"


def _rule(file: str, selector: str) -> str:
    text = (CSS / file).read_text(encoding="utf-8")
    m = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", text)
    assert m, f"{selector} not found in {file}"
    return m.group(1)


def test_the_section_list_keeps_a_floor() -> None:
    body = _rule("library-lazy.css", ".ocr-region-list")
    m = re.search(r"min-height:\s*(\d+(?:\.\d+)?)%", body)
    assert m and float(m.group(1)) >= 35, "the list may be crushed to nothing again (0px at 1366x768)"


def test_the_column_scrolls_as_one_when_it_overflows() -> None:
    body = _rule("07-whiteboard-misc.css", ".ocr-regions")
    assert re.search(r"overflow-y:\s*auto", body), "the column's overflow was cut off, not scrolled"
