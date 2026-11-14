"""L-world-class-17: find and replace inside a note, through the engine's own search panel."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")
LAZY_CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    at = source.index(start)
    return source[at : source.index(end, at)]


def test_a_note_box_carries_the_search_panel_and_its_chords():
    extensions = _between(DOCS, "function noteSurfaceExtensions(", "\n}\n")
    # The panel sits at the top and every match is marked, as in the document editor.
    assert "CM.search.search({ top: true })" in extensions
    assert "CM.search.highlightSelectionMatches()" in extensions
    keymap = _between(DOCS, "function noteSurfaceKeymap(", "\n}\n")
    for key in ('"Mod-f"', '"Mod-h"', '"F3"', '"Shift-F3"', '"Escape"'):
        assert key in keymap, key
    # Ctrl+F is the note's own, not also the page's find bar behind it.
    assert "stopPropagation: true" in keymap
    assert "openSearchPanel" in keymap and "input[name=replace]" in keymap


def test_the_panel_is_styled_in_a_note_as_it_is_in_a_document():
    assert ":is(.doc-editor, .note-surface) .cm-search" in LAZY_CSS
    assert "  .doc-editor .cm-search" not in LAZY_CSS
