"""INBOX 1738 and review 5850946759: the fold buttons and scrollbars of the diagram builder, the gap "+" by keyboard, glyphs by shape id.

Source checks; the measured edges (1440, 2000, 390, light and dark) are in docs/roadmap/HISTORY.md.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
SPLIT = (JS / "diagram-split.js").read_text(encoding="utf-8")
SEQ = (JS / "diagram-seq-canvas.js").read_text(encoding="utf-8")
LIB = (JS / "diagram-library.js").read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    m = re.search(re.escape(selector) + r" \{([^}]*)\}", CSS)
    assert m, selector
    return m.group(1)


def test_the_list_head_is_outside_the_scroller() -> None:
    wire = SPLIT[SPLIT.index("function wireFold") :]
    assert "dgm-listcol" in SPLIT
    assert "S.pane.prepend(head)" not in wire
    assert "S.pane.before(head)" in wire
    head = _rule(".dgm-panehead")
    assert "sticky" not in head


def test_the_column_is_the_frame_and_the_pane_the_scroller_from_600() -> None:
    assert "@media (min-width: 600px) {\n  .dgm-listcol {" in CSS
    col = CSS[CSS.index("@media (min-width: 600px) {\n  .dgm-listcol {") :][:1200]
    assert "overflow: hidden" in col and "border:" in col
    assert ".dgm-listcol > .dgm-pane" in col and "border: 0" in col


def test_below_600_the_column_is_not_a_box() -> None:
    assert re.search(r"\.dgm-listcol \{\s*display: contents;", CSS)


def test_a_folded_list_hides_the_column_and_an_unparsed_pane_hides_it_too() -> None:
    assert ".dgm-body.dgm-fold-left > :is(.dgm-listcol, .dgm-split-handle)" in CSS
    assert ".dgm-listcol:has(> .dgm-pane.hidden)" in CSS


def test_the_picture_fold_clears_the_scrollbar_only_when_the_picture_is_under_it() -> None:
    wire = SPLIT[SPLIT.index("function wireFold") :]
    assert "getBoundingClientRect().top" in wire
    assert ".dgm-zoom" in wire
    assert "insetInlineEnd" in wire
    # No longer an unconditional bar offset.
    assert "calc(var(--space-2) + ${bar}px)" not in wire


def test_the_gap_plus_has_a_key() -> None:
    assert 'event.key !== "+"' in SEQ
    assert "plusMenu(" in SEQ
    # The menu anchors to something that exists without a hover.
    assert "function plusMenu(anchor" in SEQ


def test_the_shelf_menu_glyphs_are_found_by_shape_id() -> None:
    assert "glyphOf" in LIB
    assert "dataset.tile" in LIB
