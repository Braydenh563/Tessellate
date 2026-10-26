"""The board's canvas is panned by its zoom transform, never by scrolling.

mapdog-1026: Tab under a deep topic moved the whole map 351px (627px in the
report) with the zoom transform unchanged, because the browser scrolls an
`overflow: hidden` box to bring a newly focused editor into view. Measured by
`scratchpad/ui-sweeps/mapdeeppan.js`. The class: any focus, caret or find that
scrolls the canvas. Pinned here as source because the behaviour needs a
browser; the sweep measures it in one.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
WB = (JS / "whiteboard.js").read_text(encoding="utf-8")
MAP = (JS / "whiteboard-map.js").read_text(encoding="utf-8")


def _fn(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start)]


def test_a_native_scroll_of_the_canvas_is_folded_into_the_zoom_transform():
    fold = _fn(WB, "wbFoldNativeScroll")
    assert "el.scrollLeft = 0" in fold and "el.scrollTop = 0" in fold
    assert "t.x - dx" in fold and "wbZoom.transform" in fold
    assert 'container.node().addEventListener("scroll", wbFoldNativeScroll)' in WB


def test_the_board_editors_focus_without_scrolling():
    begin = _fn(WB, "wbBeginTextEdit")
    assert "contentEl.focus({ preventScroll: true })" in begin
    assert "box.focus({ preventScroll: true })" in WB


def test_a_new_topic_is_revealed_by_the_least_move():
    reveal = _fn(MAP, "wbMapRevealTopic")
    assert "const slide = (lo, hi, a0, a1)" in reveal
    assert "wbCenterOn(want" in reveal  # still eases up to a legible zoom
