"""The block pane on a phone (1546 P2 leftovers).

Read for what each piece must hold; the numbers (the dock's height, a two-finger pinch's zoom, a drag
from the top of a short window to the bottom of the list) are in the browser sweeps
named in agent-remaining/a30y-1103.md. Touch is driven there with CDP touch points, never by tapping alone.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
TOUCH = (JS / "diagram-touch.js").read_text(encoding="utf-8")
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
KINDS = (JS / "diagram-kinds.js").read_text(encoding="utf-8")
DRAG = (JS / "obj-drag.js").read_text(encoding="utf-8")
MERMAID = (JS / "documents-mermaid.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def test_the_touch_code_is_its_own_lazy_file_asked_for_only_on_a_narrow_window_or_a_touch_screen():
    assert 'diagramTouch: ["/js/diagram-touch.js"]' in MERMAID
    assert 'const COMPACT = "(max-width: 599.98px), (pointer: coarse)"' in BUILDER and "matchMedia(COMPACT).matches" in BUILDER and 'ensureModule("diagramTouch")' in BUILDER
    assert "diagramModel.touch = { wire }" in TOUCH
    #: One wiring per pane, whichever pane it is (a flowchart's or a kind's).
    assert "S.root.dataset.touch" in TOUCH


def test_the_phone_palette_is_one_button_and_a_sheet_that_presses_the_tiles():
    assert "openSheet({" in TOUCH and "sheetRow(" in TOUCH and 'label: "Add a block"' in TOUCH
    #: Pressing a row presses the tile, so a block is added one way only.
    assert "tile.click()" in TOUCH and "close();" in TOUCH
    assert "dgm-add" in TOUCH and 'smallButton("ph:plus Add"' in TOUCH
    #: Hidden until the module runs and only in a narrow pane; the tiles stay in the page for the sheet.
    assert ".dgm-add {\n  display: none;\n}" in CSS
    narrow = CSS[CSS.index("@container (max-width: 599.98px)") :]
    assert ".dgm-compact :is(.dgm-palette, .dgm-lib-hint, .dock-group:has(> .dgm-dirs)) {\n    display: none;" in narrow
    assert ".dgm-compact .dgm-add {\n    display: inline-flex;" in narrow


def test_the_picture_pinches_pans_and_fits_on_a_double_tap_and_keeps_its_zoom_across_a_redraw():
    #: 1614: the pinch moved out of diagram-touch.js into diagram-view.js, which every window gets (the same technique:
    #: a width on the image, put back by the paint listeners, and the figure's own scroll).
    view = (JS / "diagram-view.js").read_text(encoding="utf-8")
    assert "zoomable" not in TOUCH and "MAX_ZOOM" not in TOUCH and "fig.onpaint" not in TOUCH
    # 1679 l: a pinch and a double tap aim a scale (painted as a transform next frame, committed after) instead of calling zoomTo.
    for needle in ('event.pointerType !== "touch"', "start.scale * (mid.d / start.d)", "fig.scrollLeft -=", "aim(f * 2", "img.style.width"):
        assert needle in view, needle
    assert "(fig.onpaint ||= []).push(paint)" in view and "for (const paint of S.fig.onpaint || []) paint();" in BUILDER
    assert ".dgm-compact .dgm-picture {\n  touch-action: none;" in CSS
    #: A pan or a pinch is not a press on a block.
    assert "travel > 12" in view

def test_a_drag_scrolls_the_pane_and_the_page_around_it_at_the_edge_of_what_is_on_screen():
    tick = DRAG[DRAG.index("function objDragTick") : DRAG.index("function objDragUp")]
    assert "Math.min(box.bottom, innerHeight)" in tick and "Math.max(box.top, 0)" in tick
    assert "OBJ_MODES[g.mode].ancestors" in tick and "el.scrollTop + el.clientHeight >= el.scrollHeight - 1" in tick
    assert "ancestors: true" in (JS / "diagram-pointer.js").read_text(encoding="utf-8") and "ancestors: true" in KINDS



def test_a_phone_keeps_the_picture_and_opens_the_blocks_list_as_a_sheet_once_there_is_an_arrow():
    # 1679 slice 11: the list moves into an openSheet card and back; the empty walkthrough stays in the page until the first arrow.
    assert 'label: "Blocks"' in TOUCH and 'name: "diagram-blocks"' in TOUCH and "card.append(S.pane)" in TOUCH
    assert "home.insertBefore(S.pane, before)" in TOUCH and "dgm-listbtn" in TOUCH and "dgm-phonelist" in TOUCH
    steps = (JS / "diagram-steps.js").read_text(encoding="utf-8")
    assert 'S.root.classList.toggle("dgm-listless", m.edges.length > 0)' in steps
    rule = CSS[CSS.index(".dgm-phonelist.dgm-listless .dgm-body > .dgm-pane") :].split("}", 1)[0]
    assert "display: none" in rule
    assert ".dgm-phonelist.dgm-listless .dgm-body {" in CSS and "grid-template-rows: minmax(0, 1fr)" in CSS and ".sheet-card > .dgm-pane" in CSS


def test_grips_are_44_pixels_on_a_touch_screen():
    coarse = CSS[CSS.index("@media (pointer: coarse), (max-width: 599.98px) {") :].split("\n}\n", 1)[0]
    assert ".dgm-grip" in coarse and "min-inline-size: 2.75rem" in coarse and "min-block-size: 2.75rem" in coarse


def test_a_tap_on_connect_to_puts_the_cursor_in_the_search_field_and_the_keyboard_path_keeps_the_card():
    joins = (JS / "diagram-joins.js").read_text(encoding="utf-8")
    assert "S.tapped" in joins and "shell.search.focus(" in joins and "shell.card.focus(" in joins
    assert "S.tapped = event.detail > 0" in BUILDER
