"""L-world-class-127: find and replace inside a note.

The note edit box (and the graph's note popup) carries the same CodeMirror
search panel the document editor has: Ctrl+F opens it, Ctrl+H opens it on the
replace field, and the app's own page find stands aside when the box answered
the chord first. The panel wears the document's restyle, not the library's."""

from __future__ import annotations

from pathlib import Path

from tests._app_js import app_js_text, documents_text

ROOT = Path(__file__).resolve().parents[1]
JS = app_js_text()
DOCS = documents_text()
LAZY_CSS = (ROOT / "frontend/css/library-lazy.css").read_text(encoding="utf-8")


def _body(name: str) -> str:
    start = DOCS.index(f"function {name}(")
    return DOCS[start : DOCS.index("\n}\n", start)]


def test_the_edit_box_mounts_the_search_panel():
    body = _body("noteSurfaceExtensions")
    assert '"entry-edit-content"' in body and '"graph-popup-content"' in body
    assert "CM.search.search({ top: true })" in body
    assert "CM.search.searchKeymap" in body


def test_ctrl_h_opens_on_the_replace_field():
    body = _body("noteSurfaceExtensions")
    assert 'key: "Mod-h"' in body
    assert 'input[name=replace]' in body


def test_page_find_yields_to_an_editor_that_answered():
    assert 'if (id === "find" && e.defaultPrevented) continue;' in JS


def test_the_panel_wears_the_document_restyle_in_a_note():
    for sel in (".cm-panels {", ".cm-search {", ".cm-search .cm-textfield {", ".cm-search .cm-button {"):
        # The one rule reaches both editors through :is() (the pair of selectors was folded, same rule).
        assert f":is(.doc-editor, .note-surface) {sel}" in LAZY_CSS, sel
