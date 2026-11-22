"""A render repaints only the pen strokes whose look can have changed (audit 1028 B3, B4).

`renderWhiteboard` parsed and repainted every sketch on every render, so a
board of 300 strokes cost 90 ms per render at 4x CPU throttle whatever had
changed (a topic moved, an undo). A plain stroke (pen or highlighter) now
carries a paint key, as an object does (`wbObjectPaintKey`), and a render that
finds the same key and the same live path skips it.

W30 B4 (wb-1111) extended the key to shapes and connectors (see
test_wb_render_w30.py): a shape adds its id and the board's rough default, a
connector the ends it resolves to now. What no skip may do: skip when the
theme changed, skip a stroke whose drawn path was moved by a gesture and not
put back, or skip words that hold a placeholder.
"""

from __future__ import annotations

from tests._app_js import frontend_text
import re



def render_sketches() -> str:
    text = frontend_text("whiteboard.js")
    start = text.index("sketchUpdate.each(function(d) {")
    return text[start : start + 1800]


def test_a_stroke_has_a_paint_key_and_a_skip():
    body = render_sketches()
    assert "strokePaintKey(d)" in body
    assert "return;" in body.split("let pathData = d.data;")[0]


def test_the_key_keeps_the_pen_and_highlighter_branch_with_ink_and_mode():
    text = frontend_text("whiteboard.js")
    start = text.index("const strokePaintKey = (d) =>")
    fn = text[start : text.index("sketchUpdate.each(function(d) {", start)]
    assert "wbBoardBg()" in text[start - 600 : start]
    assert "draw|highlighter" in fn
    #: A connector's path comes from the items at its ends.
    assert "link-" in fn
    #: The theme decides the ink a black stroke is drawn in.
    assert "dataset.mode" in text[start - 600 : start]


def test_a_moved_live_path_is_not_skipped():
    body = render_sketches()
    skip = body.split("let pathData = d.data;")[0]
    assert re.search(r'getAttribute\("d"\)', skip), "the skip must compare the drawn path"
