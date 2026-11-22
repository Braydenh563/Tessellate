"""A board's pictures are written into its export, not named by address.

The export SVG referenced each picture by its `/media/...` url. An SVG drawn
through `<img>` (`wbRasterizeSvg`) loads nothing outside itself, so every PNG,
PDF and library copy of a board had a blank where its pictures were; measured
in Chromium by `scratchpad/ui-sweeps/wbexportimage.js` (the pixel in the middle
of a red picture read the board's white before, red after). The saved .svg
pointed at an address that means nothing outside the app. Both now go through
`wbInlineSvgImages`.
"""

from tests._app_js import frontend_text
from pathlib import Path

WHITEBOARD = Path(__file__).resolve().parent.parent / "frontend" / "js" / "whiteboard.js"


def _function(text: str, header: str) -> str:
    start = text.index(header)
    return text[start : text.index("\n}\n", start) + 3]


def test_every_rasterised_export_inlines_its_pictures_first():
    text = frontend_text("whiteboard.js")
    body = _function(text, "async function wbRasterizeSvg(")
    assert "await wbInlineSvgImages(" in body


def test_the_saved_svg_is_self_contained_too():
    text = frontend_text("whiteboard.js")
    body = _function(text, "async function wbExportSvg(")
    assert "wbInlineSvgImages(svg)" in body


def test_a_picture_that_cannot_be_fetched_keeps_its_address():
    text = frontend_text("whiteboard.js")
    body = _function(text, "async function wbInlineSvgImages(")
    # `api()` throws on a refusal (F5), and the catch keeps the address.
    assert "api(unescapeAttr(escaped), { silent: true })" in body
    assert "catch {" in body
    assert "data:" in body
