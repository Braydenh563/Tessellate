"""A board preview's labels are measured on a canvas, never by layout.

INBOX 496 ("it takes a while to load the boards and maps library subtab"),
profiled on a first visit to 34 boards: 172ms inside `mapPreviewTextWidth` and
most of 475ms of layout, because each new label (and, through
`mapPreviewFitText`, every shorter cut of a long one) was a fresh
`getComputedTextLength`, each forcing a layout of a page that the gallery was
still building. The font is read once; `measureText` lays nothing out.
"""

from __future__ import annotations

from pathlib import Path

from tests import _js_scope

NOTE_CARDS = _js_scope.unwrapped(
    (Path(__file__).resolve().parent.parent / "frontend" / "js" / "map-preview.js").read_text(encoding="utf-8")
)


def _body(signature: str) -> str:
    start = NOTE_CARDS.index(signature)
    return NOTE_CARDS[start : NOTE_CARDS.index("\n}\n", start)]


def test_width_is_measured_on_a_canvas_in_the_drawn_font() -> None:
    width = _body("function mapPreviewTextWidth(text, fontSize)")
    assert "measureText(body)" in width
    assert "getComputedTextLength" not in width and "getSubStringLength" not in width
    measurer = _body("function mapPreviewMeasurer()")
    # The font is the preview's own, read once from an element that carries it.
    assert "board-minimap map-preview-measure" in measurer
    assert "getComputedStyle(node)" in measurer
    assert "font.fontFamily" in measurer and "font.fontWeight" in measurer


def test_fitting_a_label_touches_no_layout() -> None:
    fit = _body("function mapPreviewFitText(text, fontSize, room)")
    assert "getComputedTextLength" not in fit and "getBBox" not in fit
