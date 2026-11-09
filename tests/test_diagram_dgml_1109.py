"""INBOX 1661 (l), what was left open: the shelf on the picture for a mind map and a timeline, a tile dropped on their
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
