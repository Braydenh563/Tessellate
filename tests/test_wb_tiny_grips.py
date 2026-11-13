"""A box too small on screen to hold its grips drags instead (L-whiteboard-15).

Measured, wb500perf.js: on a 500-box board at the fit zoom (0.23) a text box
is 42 by 16 px on screen and its ten-pixel resize grips, which keep their
screen size at every zoom, covered it, so a press on it landed on a grip and
the box did not move. The cull pass, which already walks every item once a
pan or zoom frame with the zoom in hand, marks such an item `wb-tiny`, and
the grips are absent on it.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _cull_body() -> str:
    src = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    start = src.index("function wbCullNow(")
    return src[start:src.index("\n}\n", start)]


def test_the_cull_pass_marks_items_too_small_for_their_grips():
    body = _cull_body()
    assert 'classList.toggle("wb-tiny"' in body
    assert re.search(r"WB_TINY_SCREEN_W", body) and re.search(r"WB_TINY_SCREEN_H", body)


def test_a_tiny_item_has_no_resize_grips():
    css = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    rule = re.search(r"(?:(?<=[{}])|\A)([^{}]*\.wb-tiny[^{}]*\.wb-resize-handle[^{}]*)\{([^}]*)\}", css)
    assert rule, "no rule hides a tiny item's grips"
    assert "display: none" in rule.group(2)
    # Two ids, so it outranks every reveal rule (one id each).
    assert rule.group(1).count("#") >= 2
