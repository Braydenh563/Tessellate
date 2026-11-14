"""The Diagram builder's side section reads as the diagram and connecting is one act (INBOX 1594).

The owner: "make this side section on the diagram maker and also the library of things I can add and how to do connectors
and all that more easy to understand and use". Four faults, one class each: a connector was a bare chip that looked like a
block; the shape strip was seven unlabelled glyphs; connecting was a menu item two levels down; an empty list said nothing
about the next step. Measured at 1280 and 390 (scratchpad notes in a31h-1103.md): a connected pair took 7 acts and now 4 (3
with the default names); the strip's last tile is on screen at both widths (the phone's sheet ends at 831 of 844).
"""

from __future__ import annotations

import gzip
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def _read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_the_add_library_is_grouped_by_meaning_and_every_tile_has_a_hint():
    library = _read("diagram-library.js")
    flow = library.split("const FLOW = [", 1)[1].split("\n  ];", 1)[0]
    for group in ("Steps", "Decisions", "Start and end", "Notes and groups"):
        assert f'["{group}", [' in flow, group
    shapes = re.findall(r'\["(rect|round|hexagon|cylinder|parallelogram|diamond|stadium|circle|note|group)", "([^"]+)"\]', flow)
    assert sorted(s for s, _ in shapes) == sorted(["rect", "round", "hexagon", "cylinder", "parallelogram", "diamond", "stadium", "circle", "note", "group"])
    assert all(hint.endswith(".") and len(hint) < 60 for _, hint in shapes), shapes
    # One builder for every kind: the other kinds' tiles carry a group and a hint too.
    kinds = _read("diagram-kinds.js")
    assert "diagramModel.library.build(" in kinds and "tiles.hint" in kinds
    for tile in re.findall(r'\{ id: "(\w+)", (group: "[^"]+", )?name:', kinds):
        assert tile[1], f"the {tile[0]} tile has no group"
    # The hint of the pointed-at tile shows under the strip, and is also in the tile's name for a screen reader.
    assert 'strip.addEventListener("pointerover", say)' in library and 'strip.addEventListener("focusin", say)' in library
    assert "tile.setAttribute(\"aria-label\", t.label)" in library and "label: `Add a ${name.toLowerCase()}. ${hint}`" in library
    assert "strip.hint = hint" in library and "tiles.hint" in _read("diagram-kinds.js")  # 1661 D2: the flowchart has the Add menu, not the strip
    # Wrapping, so the last tile is never cut off; the hint line is not shown on a phone, where the sheet carries the hints.
    assert ".dgm-lib-tiles {\n  display: flex;\n  flex-wrap: wrap;" in CSS and ".dgm-palette {\n  flex-wrap: wrap;" in CSS
    assert ".dgm-compact :is(.dgm-palette, .dgm-lib-hint" in CSS


def test_the_phone_add_sheet_lists_the_same_groups_with_a_hint_on_every_row():
    touch = _read("diagram-touch.js")
    assert '.dgm-palette .dgm-lib-group' in touch and "dgm-add-head" in touch and "dgm-add-hint" in touch and "tile.dataset.hint" in touch
    assert 'className = "sheet-list dgm-add-list"' in touch
    # The sheet is tall enough that its last row is on screen without a scroll.
    assert '.sheet-overlay[data-sheet="diagram-add"] .sheet-card {\n  max-height: 88dvh;' in CSS


def test_a_connector_reads_as_start_to_next_with_its_label_and_is_not_a_chip():
    builder = _read("diagram-builder.js")
    chip = builder.split("function joinChip(S, edge, index) {", 1)[1].split("\n  }\n", 1)[0]
    # 1679 slice 6: the row hangs under its source, so it reads "to Next, words" (the full sentence stays in the aria-label).
    assert 'el("span", "dgm-join-to", to)' in chip and "edge.label" in chip and "dgm-join-label" in chip
    assert "Connector from ${from} to ${to}" in chip and "Change this connector" in chip
    row = CSS.split(".dgm-join {", 1)[1].split("}", 1)[0]
    assert "border-radius: var(--radius-pill)" not in row and "border-inline-start: 2px solid" in row
    assert ".dgm-join-label::before" in CSS


def test_connect_to_is_on_every_row_and_in_the_menu_and_the_picker_can_make_the_block():
    builder = _read("diagram-builder.js")
    card = builder.split("function buildBlock(", 1)[1].split("function groupGlyph", 1)[0]
    assert 'smallButton("ph:arrow-bend-down-right Connect to…"' in card and "joinPick(S, key)" in card
    assert 'connect.setAttribute("aria-label", `Connect to…, from ${text}`)' in card
    assert '"ph:arrow-bend-down-right Connect to…"' in builder.split("function blockItems(", 1)[1]
    assert "Join to" not in builder and "Join to" not in _read("diagram-joins.js")
    # The same press is not a select or a drag start.
    assert builder.count(".menu-wrap, .dgm-join, .dgm-connect") == 2 and "c: () => key[0] !== \"k\" && joinPick(S, key)" in builder
    assert ".menu-wrap, .dgm-join, .dgm-connect, [contenteditable]" in _read("diagram-pointer.js")
    # A drop on a block's middle connects, and its Connect to… says so.
    assert ".dgm-card:is(:hover, :focus-within, .dgm-connecting) .dgm-connect .ph-text" in CSS
    pointer = _read("diagram-pointer.js")
    assert 'toggle("dgm-connecting", target.op === "join")' in pointer and "Connected ${h.name(S, g.key)} to" in pointer
    joins = _read("diagram-joins.js")
    # Intent moved (1661 blind test, bug 7): a block made from Connect's "A new block" is a box, not the shape in hand.
    assert 'value: NEW' in joins and 'h.add(S, { after: key, from, shape: "rect", text: typed || undefined' in joins
    assert "Connect ${nameOf(h, S, key)} to" in joins
    # Making the block and the connector is one change, so one undo.
    add = builder.split("function addBlock(", 1)[1].split("function relabel", 1)[0]
    assert "if (from) diagramOps.join(m, from, id, { label });" in add and add.count("commit(S,") == 1


def test_the_empty_list_and_the_space_under_the_blocks_say_what_to_do_next():
    builder = _read("diagram-builder.js")
    # 1615 f (DOCUMENTS_PLAN 22.4 R4): the empty pane's sentence became three numbered steps, in diagram-steps.js.
    assert "diagramModel.steps.build(S" in builder
    assert '"Add a shape"' in _read("diagram-steps.js")
    render = builder.split("function render(S) {", 1)[1].split("\n  }\n", 1)[0]
    # The sentence moved to diagram-steps.js `next` (dgbt-1109 3: a touch variant); the render still writes it to the line.
    assert "S.next.textContent" in render and "diagramModel.steps.next(S)" in render
    assert "Press Connect to… on a block, or drag its grip onto another block" in _read("diagram-steps.js")
    assert 'S.pane.append(S.tree, S.next, S.empty' in builder
    assert ".dgm-next {" in CSS


def test_the_dock_is_one_row_at_every_width_because_direction_is_one_button_and_suggest_folds_on_a_phone():
    # 1661 D2 (was: the four direction buttons fold into the more menu on a phone): Direction is one button now, so only Suggest folds.
    # The fold's rows moved to diagram-kindbar.js (builder gzip budget); the builder's more() calls it.
    more = _read("diagram-kindbar.js").split("function fold(S", 1)[1].split("\n  }\n", 1)[0]
    assert "matchMedia(COMPACT).matches" in more and '"ph:compass Direction"' not in more and "Suggest…" in more
    # Intent moved (DD-2, 1107): one row is the flowchart dock's, so the nowrap is scoped to it; the kinds' docks wrap.
    assert "flex-wrap: nowrap" in CSS.split(".dgm-dock:has(> .dgm-addsplit) {", 1)[1].split("}", 1)[0]
    assert "gap: var(--space-1);" in CSS.split(".dgm-compact .dock-actions {", 1)[1].split("}", 1)[0]


def test_the_builder_is_under_its_size_target_because_its_lazy_halves_are_files_of_their_own():
    builder = JS / "diagram-builder.js"
    assert len(gzip.compress(builder.read_bytes(), 9)) <= 12000
    text = builder.read_text(encoding="utf-8")
    for file in ("diagram-library.js", "diagram-pointer.js", "diagram-ops.js"):
        assert f'"/js/{file}"' in text, file
        assert (JS / file).is_file()
    # None of them is a boot script.
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for file in ("diagram-library.js", "diagram-pointer.js", "diagram-ops.js"):
        assert file not in html, file


def test_a_name_being_typed_keeps_its_row_and_a_tight_list_shows_connects_words_only_on_a_drop():
    # The owner, 2026-11-04 ("the text box got crushed in the diagram builder"): renaming a block focuses its row, which showed
    # Connect to…'s words (121 px), and in a 241 px row the box being typed in was left 15 px. Measured with
    # scratchpad dgm-rename.js at 1440 and 900. While a name is typed the words go; in a tight list they show only on a drop.
    assert ".dgm-card:has(> .dgm-editing) .dgm-connect .ph-text {\n  display: none;" in CSS
    assert ".dgm-tight .dgm-card:is(:hover, :focus-within):not(.dgm-connecting) .dgm-connect .ph-text {\n  display: none;" in CSS
    # After the rule that shows them, so they win at equal or higher specificity.
    shows = CSS.index(".dgm-card:is(:hover, :focus-within, .dgm-connecting) .dgm-connect .ph-text")
    assert CSS.index(".dgm-card:has(> .dgm-editing) .dgm-connect .ph-text") > shows
