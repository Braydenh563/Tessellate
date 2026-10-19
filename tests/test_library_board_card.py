"""Library board and map cards keep their structure when a stored thumbnail
replaces the SVG preview (INBOX 1331, a regression from INBOX 1317)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "frontend" / "css"


def _rule(text: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", text)
    assert match, f"no rule for {selector}"
    return match.group(1)


def test_card_children_are_header_title_picture_footer_in_order():
    js = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    assert "card.append(top, title, minimap, meta);" in js


def test_picture_spans_the_grid_whatever_element_it_is():
    css = (CSS / "08-consistency.css").read_text(encoding="utf-8")
    sel = ".library-grid:not(.library-list) .library-board-card > :is(.board-minimap, .library-card-meta)"
    assert "grid-column: 1 / -1" in _rule(css, sel)
    # The old `svg`-only selector let the <img> into the title's track.
    assert ":is(svg, .library-card-meta)" not in css


def test_title_truncates_and_footer_is_one_line():
    css = (CSS / "08-consistency.css").read_text(encoding="utf-8")
    base = ".library-grid:not(.library-list) .library-board-card > "
    title = _rule(css, base + ".library-card-title")
    for need in ("text-overflow: ellipsis", "white-space: nowrap", "min-width: 0"):
        assert need in title
    assert "white-space: nowrap" in _rule(css, base + ".library-card-meta")
    assert "flex: 0 0 auto" in _rule(css, base + ".library-card-meta > .library-card-when")


def test_thumbnail_fills_the_box():
    css = (CSS / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    assert "object-fit: cover" in _rule(css, "img.board-minimap")
