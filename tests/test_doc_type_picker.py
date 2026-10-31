"""INBOX 1482: one grouped type picker, drawn in two places.

The owner's screenshots showed a type button in a document's foot opening a
list grouped by kind, each row with its glyph. Here that is `docTypeMenu`, a
`kebabMenu` of the served file-type table (groups Documents, Data, Code), used
by the foot's button and by New's caret and by nothing else.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
DOCS_JS = (ROOT / "frontend/js/documents.js").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = DOCS_JS.index(f"function {name}(")
    return DOCS_JS[start : DOCS_JS.index("\n}\n", start)]


def test_the_picker_is_a_kebab_menu_of_the_served_table() -> None:
    body = _function("docTypeMenu")
    assert "kebabMenu(docTypeItems(" in body
    items = _function("docTypeItems")
    assert "docFileTypes.map" in items and "type.group" in items and "type.icon" in items


def test_both_places_draw_the_one_picker_and_the_select_is_gone() -> None:
    mount = _function("docTypeMount")
    assert mount.count("docTypeMenu(") == 2
    assert 'id="doc-type-slot"' in HTML and 'id="doc-new-type-slot"' in HTML
    assert "doc-file-type" not in HTML and "doc-file-type" not in DOCS_JS
    # No second hand-built list of types anywhere in the app's code.
    assert not re.search(r'createElement\("option"\)', _function("loadDocFileTypes"))
    assert "docTypeMenu(" not in app_js_text()


def test_new_is_a_split_button_whose_caret_starts_a_file_of_a_type() -> None:
    assert 'class="split-button doc-new-split"' in HTML
    assert "startBlankDocument(ext)" in _function("docTypeMount")
    assert "docTypeState.pending" in _function("ensureDocumentExists")
    assert "file_type" in _function("ensureDocumentExists")


def test_the_foot_button_saves_the_type_of_an_open_document_at_once() -> None:
    body = _function("docTypeChoose")
    assert "saveDocument({ silent: true })" in body
    assert "docTypeState.pending" in body  # a blank page keeps the choice for its first keystroke


def test_the_picker_is_filterable_through_the_one_filter_recipe_and_keyboard_reachable() -> None:
    body = _function("docTypeFilter")
    assert 'listFilter(menu, { label: "Filter types"' in body
    assert 'type = "search"' not in body  # no second hand-built field
    # Enter takes the first row left; the arrows ride the menu's own keys.
    assert "click()" in _function("docTypeFilterKey")


def test_a_sync_with_the_same_type_writes_nothing() -> None:
    """lagfix-1031 measured `syncDocFileType` at 26 to 364 ms on an open; the
    type button's label and check are rewritten only when the type changed."""
    assert "opener.dataset.ext === type.ext" in _function("docTypeSync")
