"""Resizing a topic by its grip must not touch its text size (mapstrip.js, the
two checks that failed on the base: OPEN 814).

The drag started from the stylesheet's default (14) rather than the size the
topic is drawn at, so a topic whose 17px came from its level or the map theme
lost its inline size on the first pixel of the drag, fell to 13.6px while it
was resized and snapped back on release. The drag itself needs a browser
(`scratchpad/ui-sweeps/mapstrip.js`: grip and Shift checks, 40 of 43 before,
42 of 43 after); this holds the shape of the fix.
"""

from __future__ import annotations

from pathlib import Path

MAP_JS = Path(__file__).resolve().parents[1] / "frontend" / "js" / "whiteboard-map.js"


def _drag() -> str:
    text = MAP_JS.read_text(encoding="utf-8")
    body = text[text.index("function wbMapStartResizeDrag(") :]
    return body[: body.index("\n}\n")]


def test_the_drag_starts_from_the_size_the_words_are_drawn_at():
    body = _drag()
    assert "const startInline = node.style.fontSize;" in body
    assert "parseFloat(startInline)" in body and "parseFloat(getComputedStyle(node).fontSize)" in body


def test_an_unscaled_drag_hands_the_inline_size_back_rather_than_clearing_it():
    body = _drag()
    assert "node.style.fontSize = font === startFont ? startInline : `${font}px`;" in body
    assert 'node.style.fontSize = font === startFont && !d.data?.font_size ? ""' not in body
