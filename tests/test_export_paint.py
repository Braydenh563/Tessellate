"""A board or map exported as a picture is painted in the colours on screen.

The owner, 2026-09-24: "I exported a mindmap selection as an image to the
library, the mindmap nodes turned white??" `wbBuildExportSvg` drew every
topic and card as `#ffffffee` with `#1f2430` ink, the light theme's look, and
forced every branch to `fill="none"` with a grey stroke. Measured with
`scratchpad/ui-sweeps/exportcolours.js` in dark mode: topics 30,30,28 on
screen and 240,240,239 in the PNG, a text box's ink 236,235,232 on screen and
31,36,48 in the PNG. After: the same pixels in both, light and dark.

The suite cannot rasterise, so this holds the shape: the builder reads each
box's paint off the live element, and the old constants are fallbacks only.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parent.parent
JS = "\n".join(unwrapped(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "frontend" / "js").glob("*.js")))


def _body(name: str) -> str:
    match = re.search(rf"^(?:async )?function {re.escape(name)}\(", JS, re.MULTILINE)
    assert match, f"{name} is gone; this lint is about its body"
    rest = JS[match.end():]
    end = re.search(r"^(?:async )?function \w+\(", rest, re.MULTILINE)
    return rest[: end.start()] if end else rest


def test_the_export_reads_the_paint_on_screen() -> None:
    body = _body("wbBuildExportSvg")
    look = _body("wbExportLook")
    #: L272: the reads moved into `wbExportLook`; the builder asks it.
    assert look.count("wbExportPaint(") >= 3, "cards and topics take their paint from the live element"
    assert "look.card(" in body and "look.topic(" in body, "the builder takes that paint from the look"
    assert 'fill="#ffffffee"' not in body and 'fill="#ffffffcc"' not in body, (
        "a hard-coded white fill is the light theme's look, painted into every theme"
    )
    assert 'setAttribute("fill", "none")' not in body, "a branch is a filled ribbon; forcing no fill draws its outline"


def test_a_computed_colour_becomes_plain_srgb() -> None:
    body = _body("wbExportColour")
    assert "color\\(srgb" in body, "a color-mix() surface computes to color(srgb ...), parsed here"
    assert "getImageData" in body, "anything else goes through a canvas pixel"


def test_the_background_rect_reads_the_chosen_board_colour() -> None:
    """Coordinator ask: "the export (PNG/SVG) [uses] that background colour
    or a chosen one." Verified live in Chromium (a mind map, its background
    set to #112233 through the View menu's picker): the exported SVG's own
    background `<rect>` came back `fill="rgb(17, 34, 51)"`, the exact colour,
    because it reads the *computed* style of `#whiteboard-container`, which
    is where the picker's `--wb-board-bg` custom property lands. Kept here so
    a rewrite of the builder cannot go back to a hard-coded background."""
    body = _body("wbBuildExportSvg")
    assert "getComputedStyle(container).backgroundColor" in _body("wbExportLook")
    assert "look.background" in body
    assert re.search(r'fill="\$\{bgColor\}"', body), "the background rect must paint bgColor, not a constant"


def test_a_nodes_own_colour_survives_into_its_branch_and_export() -> None:
    """The map strip's colour well (`#wb-map-strip-color`) writes
    `node.data.color`; the export paints a node's branch bar straight from
    it. Verified live: picking #ff3366 on a topic wrote `node.data.color`
    and the exported SVG carried a `fill="#ff3366"` rect for that node's
    branch bar."""
    wiring = "\n".join(p.read_text(encoding="utf-8") for p in sorted(ROOT.glob("frontend/js/*.js")))
    start = wiring.index('$("wb-map-strip-color")?.addEventListener("change"')
    strip_change = wiring[start : start + 600]
    assert "node.data = { ...node.data, color: e.target.value }" in strip_change
    assert "wbSaveObject(node)" in strip_change
