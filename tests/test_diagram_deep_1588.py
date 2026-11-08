"""The Diagram builder's deep dive and lag pass (INBOX 1588 parts 2 and 3).

Driven with Playwright in both themes at 1280 and 390 (scratchpad notes in agent-remaining/a31h-1103.md): every kind
through add, rename, delete, undo, Done, Cancel (which asks first when there are changes), a 119-block diagram, an
invalid source and the phone dock. One bug came out of it, the Hexagon tile, drawn as a solid accent block while its
neighbours are outlined (it read as the selected tile). The lag numbers are in the same notes; the code that moved them
is pinned here so a later render cannot go back to rebuilding every row.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend" / "js" / "diagram-builder.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def test_the_hexagon_tile_is_an_outline_like_its_neighbours_not_a_solid_block():
    rule = CSS.split('.dgm-shape[data-shape="hexagon"] {', 1)[1].split("}", 1)[0]
    # A clip-path cuts the border away, so the outline is the accent behind and the soft fill is laid inside it.
    assert "background: var(--accent);" in rule and "clip-path: polygon(" in rule and "position: relative;" in rule
    inner = CSS.split('.dgm-shape[data-shape="hexagon"]::after {', 1)[1].split("}", 1)[0]
    assert "inset: 1px;" in inner and "var(--accent-soft)" in inner and "clip-path: polygon(" in inner


def test_a_render_keeps_the_rows_that_did_not_change_and_moves_only_what_is_out_of_place():
    render = JS.split("function render(S) {", 1)[1].split("\n  }\n", 1)[0]
    assert "reconcile(S.tree, rows)" in render and "S.tree.replaceChildren" not in render
    assert "S.cache = fresh" in render and "buildBlock(S, item, 1, edgesFrom, fresh)" in render
    build = JS.split("function buildBlock(", 1)[1].split("function buildRow(", 1)[0]
    # The signature is what the row reads: its words, shape, connectors (with the names at both ends) and its kids.
    assert "hit.sig === sig" in build and "titleOf(S, e.from)" in build and "titleOf(S, e.to)" in build and "e.label" in build
    assert "node(S.m, item.id).shape" in build and "kids.map((k) => fresh.get(k.dataset.key).sig)" in build
    reconcile = JS.split("function reconcile(parent, rows) {", 1)[1].split("\n  }\n", 1)[0]
    assert "child.remove()" in reconcile and "parent.insertBefore(row, parent.children[i] || null)" in reconcile


def test_a_kept_row_reads_its_connector_from_the_model_when_pressed_not_from_when_it_was_drawn():
    chip = JS.split("function joinChip(S, edge, index) {", 1)[1].split("\n  }\n", 1)[0]
    assert "S.m.edges[index] || edge" in chip
    assert "{ e, i }" in JS.split("function render(S) {", 1)[1].split("\n  }\n", 1)[0]


def test_selection_and_focus_write_only_what_differs_and_never_refocus_what_has_focus():
    stops = JS.split("function stops(S, stop) {", 1)[1].split("\n  }\n", 1)[0]
    assert 'getAttribute("tabindex") !== index' in stops and 'getAttribute("aria-selected") !== on' in stops
    assert "stops(S, blockEl(S, key))" in JS.split("function select(", 1)[1].split("\n  }\n", 1)[0]
    render = JS.split("function render(S) {", 1)[1].split("\n  }\n", 1)[0]
    assert "if (had && document.activeElement !== stop) stop?.focus();" in render
    end = JS.split("const end = (keep", 1)[1].split("\n    };", 1)[0]
    assert "document.activeElement !== block" in end
    # A row is found by its key in one query, not by walking every row.
    assert 'S.tree.querySelector(`.dgm-block[data-key="' in JS


def test_the_picture_waits_half_as_long_as_the_last_draw_took_so_a_big_diagram_is_not_drawn_per_keystroke():
    draw = JS.split("function drawPicture(S) {", 1)[1].split("// --- the tree", 1)[0]
    assert "S.drawWait = Math.min(600, Math.max(120, (performance.now() - began) / 2))" in draw
    assert "}, S.drawWait || 120);" in draw
