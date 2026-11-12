"""The graph popup's header (owner, 2026-11-10, a screenshot): the title drops a heading's own colon,
the category chip and the filing confidence share one row level with the meta lines, the confidence
says what it is ("95% sure"), and the created date is spelled out, not "03/08/2026"."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = "".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "css").glob("*.css")))


def _function(name: str) -> str:
    start = JS.index(f"function {name}(")
    end = JS.find("\nfunction ", start + 9)
    return JS[start : end if end > 0 else None]


def test_the_title_drops_trailing_punctuation():
    head = _function("renderGraphPopupHeader")
    assert re.search(r"\.replace\(/\[\\s:;,\.", head), "a trailing colon or full stop is cut from the title"


def test_the_confidence_says_what_it_is():
    assert "% sure`" in _function("renderGraphPopupHeader")


def test_chip_and_confidence_share_a_row_level_with_the_meta_lines():
    filed = re.search(r'<span class="graph-popup-filed">(.*?)</span></span>', HTML, re.S)
    assert filed and 'id="graph-popup-category"' in filed.group(1) and 'id="graph-popup-confidence"' in filed.group(1)
    rule = CSS[CSS.index(".graph-popup-ident > .graph-popup-filed {") :][:200]
    assert "grid-area: 2 / 1 / auto / -1" in rule, "from the glyph's column, as the meta lines below"


def test_the_created_date_is_spelled_out():
    info = _function("renderGraphPopupInfo")
    assert "Created ${shortDate(entry.created_at)}" in info and "toLocaleDateString()" not in info
