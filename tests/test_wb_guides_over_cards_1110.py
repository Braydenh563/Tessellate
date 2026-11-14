"""Alignment guides are drawn above note cards (owner, 2026-11-10, INBOX 1725: "whiteboard alignment
bars go behind objects like notes"). Cards are HTML in `#wb-html-layer`, which sits over the base SVG,
so the guides go in the overlay SVG that index.html places after the card layer."""

from __future__ import annotations

from tests._app_js import frontend_text
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WB = frontend_text("whiteboard.js")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_the_guides_go_in_the_overlay_layer():
    start = WB.index("function wbShowAlignmentGuides(")
    body = WB[start : WB.index("\nfunction ", start + 10)]
    first = body.index('getElementById("wb-overlay-zoom-group")')
    assert first < body.index('getElementById("wb-zoom-group")'), "the overlay first, the base layer only as a fallback"


def test_the_overlay_layer_comes_after_the_card_layer():
    assert HTML.index('id="wb-html-layer"') < HTML.index('id="wb-overlay-layer"')
