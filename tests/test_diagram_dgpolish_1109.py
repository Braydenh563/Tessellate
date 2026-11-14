"""INBOX 1661 close-out (dgpolish-1109): the shelf on touch, the drop marker of a mind map and a timeline, a new part named on
the picture with the list folded. Source reads; the browser numbers are in the CHANGELOG lines and the remaining file."""

from __future__ import annotations
from tests._app_js import frontend_text

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _js(name: str) -> str:
    return frontend_text(name) if name == "documents.js" else (JS / name).read_text(encoding="utf-8")


def test_a_shelf_tile_dropped_off_every_part_rings_the_box_it_lands_beside_not_the_whole_picture():
    tree = _js("diagram-tree-canvas.js")
    kinds = _js("diagram-kinds.js")
    # The landing is the press's own place (`ops.spot`), named by the box it is beside.
    assert "function landing(S, tile)" in tree and "ops.spot(S.k, S.m, tile.type, S.sel" in tree
    assert 'word: `${op} ${diagramModel.kinds.act.name(S, key)}`' in tree
    assert "diagramModel.treeCanvas?.landing(S, tile) ||" in kinds
    # Only a picture with no box to ring keeps the whole-picture mark.
    assert 'card: S.fig, add: {}, word: S.sel ? "After the selection" : "Add it here"' in kinds


def test_a_new_part_with_the_list_folded_is_named_on_the_picture():
    kinds = _js("diagram-kinds.js")
    assert "S.seq || (S.hitAt && S.pane.offsetParent === null) ? (S.seqOpen = S.sel) : relabel(S, S.sel)" in kinds


CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def test_a_phones_toolbar_scrolls_so_redo_and_the_menu_are_reachable():
    """390 px: 8 controls of 44 px in 296 left Redo and the menu 90 px beyond the screen with overflow visible (out of reach)."""
    block = CSS[CSS.index("A phone's one row is wider than the page") :][:1000]  # the comment grew (wrapzoom 2026-11-11)
    # The pane decides, not the window (wrapzoom 2026-11-11): a container query, so a narrow Split pane scrolls too.
    assert "@container (max-width: 599.98px)" in block and "overflow-x: auto" in block and "flex: none" in block


def test_the_phone_page_grows_with_the_picture_instead_of_the_picture_lying_over_the_status_line():
    block = CSS[CSS.index("#tab-documents :is(.doc-layout, .doc-main, #doc-panes):has(.dgm-phonelist.dgm-listless)") :][:200]
    assert "flex: none" in block and "block-size: auto" in block


def test_undo_and_redo_dim_with_the_history_on_every_kind_and_the_documents_page_says_what_it_has():
    lib = _js("diagram-library.js")
    assert "function hist(S)" in lib and "undo.disabled = S.io?.canUndo === false" in lib and "redo.disabled = S.io?.canRedo === false" in lib
    assert "diagramModel.library.hist(S)" in _js("diagram-bar.js") and "diagramModel.library.hist(S)" in _js("diagram-kinds.js")
    # Both docks' buttons carry the class the dimmer finds them by.
    assert '"icon-only", "dgm-hist"' in _js("diagram-kinds.js") and 'classList.add("dgm-hist")' in _js("diagram-bar.js")
    assert "get canUndo() { return docCanUndo(); }, get canRedo() { return docCanRedo(); }" in _js("documents.js")
    assert "get canRedo() { return at < history.length - 1; }" in _js("diagram-embed.js")


def test_the_shelf_is_first_in_the_stage_one_tab_stop_and_its_focus_has_a_ring():
    """Tab met the shelf at stop 18 of 26, after the picture and its zoom bar, though it lies above them; 8 stops are one now."""
    lib = _js("diagram-library.js")
    assert "stage.prepend(bar);\n    wireToolbarRoving(bar);" in lib
    assert ".dgm-shelf .dgm-tile:focus-visible {\n  outline-color: var(--accent);" in CSS


def test_a_diagram_that_will_not_draw_on_the_documents_page_offers_edit_in_source():
    pic = _js("diagram-picture.js")
    assert 'if (!field && typeof setDocView === "function") note.prepend(smallButton("ph:code Edit in Source"' in pic
    assert 'setDocView("source", { persist: false })' in pic


def test_a_timelines_axis_takes_the_themes_line_colour_in_both_themes():
    """Mermaid's sheet draws a timeline's axis and event lines with the slices' label colour (`.lineWrapper line`: #111111 in dark,
    white in light), so the axis was black on the dark ground and white on the light; its arrowhead is a bare path (black)."""
    draw = _js("mermaid-draw.js")
    assert r"replace(/(\.lineWrapper line\{stroke:)#[0-9a-f]{6}(;\})/g, `$1${theme.variables.lineColor}$2`)" in draw
    assert "split('V 4 L6,2 Z\"/>').join(`V 4 L6,2 Z\" fill=\"${theme.variables.lineColor}\"/>`)" in draw
