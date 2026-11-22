"""L-world-class-17: find and replace inside a note, through the engine's own search panel."""
from __future__ import annotations

from pathlib import Path

from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]
DOCS = documents_text()
LAZY_CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    at = source.index(start)
    return source[at : source.index(end, at)]


def test_a_note_box_carries_the_search_panel_and_its_chords():
    #: One implementation with L-world-class-127 (test_note_find_replace_127.py): the panel and the engine's own keymap
    #: for the edit box and the graph's note popup, Ctrl+H on the replace field.
    extensions = _between(DOCS, "function noteSurfaceExtensions(", "\n  }\n")
    assert "CM.search.search({ top: true })" in extensions
    assert "CM.search.searchKeymap" in extensions
    assert 'key: "Mod-h"' in extensions
    assert "openSearchPanel" in extensions and "input[name=replace]" in extensions


def test_the_panel_is_styled_in_a_note_as_it_is_in_a_document():
    assert ":is(.doc-editor, .note-surface) .cm-search" in LAZY_CSS
    assert "  .doc-editor .cm-search" not in LAZY_CSS
