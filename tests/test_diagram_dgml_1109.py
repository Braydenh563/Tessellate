"""INBOX 1661 (l), its last three parts, built: the shelf on the picture for a mind map and a timeline, a tile dropped on their
picture, and the folded shelf button clear of the drawing. Numbers measured: docs/roadmap/agent-remaining/dgml-1109.md."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_the_shelf_has_tiles_for_a_mind_map_and_a_timeline():
    lib = _js("diagram-library.js")
    assert 'mindmap: ["branch", "leaf"]' in lib
    assert 'timeline: ["section", "period", "event"]' in lib


def test_a_tile_dropped_on_a_mind_map_or_timeline_picture_adds_after_the_selection():
    kinds = _js("diagram-kinds.js")
    assert "pictureDrop(" in kinds
    assert "target.canvas && !(\"parent\" in target)" in kinds


def test_the_folded_shelf_button_is_not_over_the_drawing():
    # Folded, the picture still starts below the button, as open (one margin for both states).
    assert ".dgm-stage.dgm-shelved > .dgm-picture" in CSS
    lib = _js("diagram-library.js")
    assert 'stage.classList.add("dgm-shelved")' in lib and 'toggle("dgm-shelved"' not in lib


def test_a_block_added_with_the_list_folded_is_named_on_the_picture_not_in_a_hidden_row():
    # Blind task (b): the list's own name field in a folded panel held the picture's redraw (`diagramModel.picture.idle`
    # waits while a label is edited) and nothing showed. With no list in view the field opens over the new box instead.
    build = _js("diagram-builder.js")
    assert "function nameOnPicture(S, id)" in build
    assert "S.pane.offsetParent === null" in build
    assert "nameOnPicture(S, id)" in build.split("function addBlock(")[1].split("function relabel(")[0]
    assert "S.askNode = " in _js("diagram-edges.js")


def test_an_arrow_asked_for_after_its_new_box_was_named_is_found_again_by_its_ends():
    edges = _js("diagram-edges.js")
    assert "S.m.edges.find((e) => e.from === next.edge.from && e.to === next.edge.to)" in edges


def test_a_field_is_not_opened_over_a_picture_that_a_newer_draw_is_about_to_replace():
    # The new image re-inserts the overlay and blurs a field in it: the arrow's words, asked for after the new box was named,
    # opened on the old picture and closed 300 ms later (blind task b).
    assert "S.drawing = true" in _js("diagram-builder.js")
    assert "editing || S.drawing" in _js("diagram-edges.js")
