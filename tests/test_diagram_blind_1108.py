"""Blind test of the diagram builder (1108): what each fix must keep.

The numbers (glyph slots, drop targets, the caption's place) are in the browser sweep named in
agent-remaining/dgmfix-1108.md; these read the source for what has to stay true.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
LIB = (JS / "diagram-library.js").read_text(encoding="utf-8")
TOUCH = (JS / "diagram-touch.js").read_text(encoding="utf-8")
KINDBAR = (JS / "diagram-kindbar.js").read_text(encoding="utf-8")
CANVAS = (JS / "diagram-canvas.js").read_text(encoding="utf-8")
POINTER = (JS / "diagram-pointer.js").read_text(encoding="utf-8")
EMBED = (JS / "diagram-embed.js").read_text(encoding="utf-8")
MERMAID = (JS / "documents-mermaid.js").read_text(encoding="utf-8")
WB = (JS / "whiteboard-interchange.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def test_a_tile_draws_a_copy_of_its_glyph_so_the_shelf_cannot_take_the_librarys():
    """The shelf and the Add library draw the same specs; one node cannot sit in two tiles, and the sheet printed the name."""
    assert "t.glyph.cloneNode(true)" in LIB
    assert "tile.append(t.glyph," not in LIB


def test_the_add_sheet_picks_the_glyph_by_what_it_is_not_by_its_place():
    assert "firstElementChild.cloneNode" not in TOUCH
    assert ':scope > :not(.dgm-tile-name)' in TOUCH


def test_the_shelf_menu_rows_wear_the_tiles_glyphs():
    assert "dgm-menu-glyph" in LIB and ".dgm-menu-glyph {" in CSS


def test_a_tile_tooltip_says_the_picture_takes_the_drop():
    assert "drag it into the blocks or onto the picture" in LIB
    assert "drag it into the blocks.`" not in LIB


def test_a_kind_change_with_content_asks_first_in_the_confirm():
    assert "async function choose" in KINDBAR
    assert "confirmDialog(" in KINDBAR and 'confirmLabel: "Switch"' in KINDBAR and "Keep ${NOUN[here]}" in KINDBAR
    #: The ask comes before the source is replaced, and a blank diagram skips it.
    assert KINDBAR.index("confirmDialog(") < KINDBAR.index("S.io.set(fresh(S.source, to))")
    assert "if (!blank) {" in KINDBAR


def test_a_tile_dropped_on_empty_picture_joins_the_nearest_box_or_the_selected_one():
    assert "nearest: (hit, img, x, y, within = 120" in CANVAS
    assert "math.nearest(S.hit, img.getBoundingClientRect(), g.x, g.y, Infinity" in CANVAS
    assert 'S.sel?.[0] === "n"' in CANVAS and "word: `Add, joined from" in CANVAS
    #: The drop applies `from` as the over-a-box drop does.
    assert "...(target.from ? { from: target.from } : {})" in POINTER


def test_the_drop_caption_stays_inside_the_picture_frame():
    assert "function word(text, r, host, frame)" in POINTER
    assert "frame.bottom - 28" in POINTER and "g.S.fig.getBoundingClientRect()" in POINTER


def test_the_dialog_keeps_a_draft_per_target_and_gives_it_back_in_the_confirm():
    assert 'const DRAFTS = "diagram-drafts"' in EMBED
    assert 'window.addEventListener("pagehide", keep)' in EMBED
    assert "draft = \"\"" in EMBED and "${draft}:${hashOf(first)}" in EMBED
    #: Done and a confirmed Discard forget it; the offer is the confirm, not a toast the dialog's buttons hide.
    assert EMBED.count("draftForget(draftId)") >= 3
    assert 'confirmLabel: "Put them back"' in EMBED
    for caller, text in (("the Live figure", MERMAID), ("the board", WB)):
        assert "draft:" in text, caller
    assert 'draft: "new"' in MERMAID and 'draft: "new-embed"' in MERMAID


def test_a_handle_never_leaves_the_pictures_scroll_area():
    edges = (JS / "diagram-edges.js").read_text(encoding="utf-8")
    assert "[wide, tall] = [fig.scrollWidth, fig.scrollHeight]" in edges and "room(x0, x1, x - size / 2" in edges and "room(y0, y1, y - size / 2" in edges
    assert "Math.max(from, Math.min(at, to - size))" in edges


def test_the_sideways_offer_is_out_of_the_flow_so_it_moves_no_pane():
    # Intent kept (the offer moves no pane: the blocks and the stage keep their size), the means moved (dgbt-1109 2): it was a layer
    # over the picture and covered the last block, so it is now a row inside the stage, which stays the grid cell's size and gives
    # the picture the rest.
    start = CSS.index(".dgm-sideways {")
    rule = CSS[start : CSS.index("}", start)]
    assert "position: absolute" not in rule and "flex: none;" in rule
    assert ".dgm {\n  position: relative;" in CSS
