"""Source text: the calculator's palette must not force a layout when it opens (L702).

Measured in Chromium on 2026-11-12: `mathEditorMount` took 66, 29, 23, 26 and
34 ms over five mounts when its draw marked the jump chips at once (17 rects
read straight after the DOM was rebuilt); 28, 11, 7, 10 and 13 ms with the
marking on the next frame and the pane's height read only when scrolled.
A browser timing would flake in CI, so the shape is pinned instead.
"""

from __future__ import annotations

import re

from tests._app_js import frontend_text


def _draw_body() -> str:
    text = frontend_text("math-editor.js")
    start = text.index("const draw = () => {")
    return text[start : text.index("\n  };", start)]


def test_the_draw_marks_chips_on_the_next_frame():
    body = _draw_body()
    #: A chip's own click still marks at once: it has just scrolled.
    after = body[body.index("band.hidden") :]
    assert re.match(r"band\.hidden = [^\n]+\n\s*markSoon\(\);", after)


def test_the_pane_height_is_read_only_when_scrolled():
    body = _draw_body()
    assert "const before = top > 0 ? scroller.scrollHeight : 0;" in body
