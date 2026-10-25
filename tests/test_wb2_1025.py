"""Whiteboard and mind map upgrade, agent wb2 (2026-10-25).

Source-level checks the suite can see; the browser numbers are in the
commit messages and `docs/roadmap/agent-remaining/wb2-1025.md`.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
LAZY_CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def _function(src: str, name: str) -> str:
    start = src.index(f"function {name}(")
    return src[start : src.index("\n}\n", start) + 3]


def test_context_bar_folds_into_more_before_it_wraps():
    # The wrap check folds first, so a narrow bar stays one row (720: two rows
    # of 44px controls before, one after).
    place = _function(WB, "wbUpdateSelectionBar")
    assert place.index("wbFoldContextBar(active)") < place.index("const wrapped = active.offsetHeight > 60")
    fold = _function(WB, "wbFoldContextBar")
    # Restored on every placement, so a wider window gets the groups back.
    assert fold.index("bar.insertBefore(g") < fold.index("bar.offsetHeight <= 60")
    assert 'order: ["order", "stroke", "arrange", "caps", "route"]' in WB
    assert ".wb-context-overflow > .wb-context-group:not(.hidden)" in LAZY_CSS


def test_sketch_rotate_turns_its_selection_box_live():
    # The handle group turns about the shape's centre on every frame (the box
    # stayed upright round a shape swinging out of it), and Escape undoes it.
    handles = _function(WB, "wbDrawSketchHandles")
    assert "group.attr(\"transform\", `rotate(${currentAngle} ${centerX} ${centerY})`)" in handles
    assert 'rotateLiveD = null;\n            group.attr("transform", null);' in handles


def test_group_resize_carries_member_outlines_links_and_readout():
    multi = _function(WB, "wbRenderMultiSelectionHandles")
    assert "wbFollowMultiOutline(row.entry.item.id, newD)" in multi
    assert "if (sizeLinks.length) wbUpdateLinkedSketches(null, sizeLinks)" in multi
    assert "wbShowSizeReadout({ x: live.minX" in multi
    # The turn follows links to shapes too, not only to cards.
    assert "spinLinks = wbMultiLiveLinks(rows)" in multi
    # The follow path is dropped on save and on Escape, never left behind.
    assert "delete row.entry.item._dragLiveD" in _function(WB, "wbSaveMultiSnapshot")
    assert "delete item._dragLiveD" in _function(WB, "wbRestoreMultiSnapshot")
