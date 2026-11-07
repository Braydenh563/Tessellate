"""1107 diagram builder, round 2 (docs/roadmap/agent-remaining/diagbuild-1107.md): DD-6, DD-8a, DD-8, DD-4, DD-5, DD-10 to DD-13.

Source assertions for what the code must hold; the browser numbers (rects, key counts) are in each commit and in the remaining file.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


EMBED = _js("diagram-embed.js")
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def _phone_css() -> str:
    start = CSS.index("/* A phone's builder is a full-screen sheet")
    return CSS[start - 120 : start + 2600]


def test_a_phone_builder_is_a_full_screen_sheet_with_the_views_on_top_and_a_one_row_foot():
    # DD-6: 390 x 844 measured before: dialog 342 wide, dock 18 px outside it, foot three rows (153 px), Source under the foot.
    assert 'const viewbar = el("div", "dgm-viewbar")' in EMBED
    assert 'matchMedia("(max-width: 599.98px)")' in EMBED and "(phone.matches ? viewbar : foot).prepend(seg)" in EMBED
    assert "dialog.append(head, viewbar, body, foot)" in EMBED
    css = _phone_css()
    assert ".modal-overlay > .card.dgm-dialog" in css and "max-width: none" in css and "max-height: none" in css
    # Out of the notch and off the home indicator, as 10-responsive.css band 2 does for every other dialog.
    assert "env(safe-area-inset-top, 0px)" in css and "env(safe-area-inset-bottom, 0px)" in css
    assert ".dgm-dialog .space-dialog-actions" in css and "flex-wrap: nowrap" in css
    # The door's "Open an existing diagram" is its glyph on a phone, and keeps its name.
    assert ".dgm-known .ph-text" in css and 'known.setAttribute("aria-label", "Open an existing diagram")' in EMBED
    # An empty diagram's picture is a strip so the steps and the template button stay on the screen.
    assert ".dgm-picture-empty" in css[css.index("grid-template-rows: auto minmax(0, 1fr)") - 200 :]
