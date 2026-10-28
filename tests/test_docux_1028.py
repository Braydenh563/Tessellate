"""Audit 1028 Documents UX rows U7, U8, U10, U11, U43 (find panel) and D7.

Browser checks: the docux agent's sweeps (code font, phone mode, find panel
sizes, a 100k-character prose pass); these pin the source that makes them so.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_JS = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")
LAZY_CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
EDITOR_CSS = (ROOT / "frontend" / "css" / "09-editor.css").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _fn(name: str, source: str = DOCS_JS) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start)]


def _rule(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, f"{selector} has no rule"
    return match.group(1)


def test_u7_code_documents_use_a_monospace_stack():
    body = _rule(LAZY_CSS, ".doc-editor .cm-editor.doc-content-code :is(.cm-content, .cm-gutters)")
    assert "font-family: var(--mono, ui-monospace" in body and "monospace)" in body


def test_u8_a_blank_document_opens_in_edit_without_changing_the_stored_view():
    assert "function setDocView(mode, { persist = true } = {})" in DOCS_JS
    assert "if (persist) try {\n    if (!docViewState.held) prefs.set(DOC_VIEW_KEY, docView);" in DOCS_JS
    blank = _fn("showNoDocument")
    assert 'if (docView === "rendered") setDocView("live", { persist: false });' in blank


def test_u10_image_opens_a_picker_and_uploads_to_the_media_store():
    assert 'if (action.custom === "image") {\n    docImagePick(box, boxId);' in DOCS_JS
    pick = _fn("docImagePick")
    assert 'type = "file"' in pick and 'accept = "image/*"' in pick
    upload = _fn("docImageUpload")
    assert '"/media/upload"' in upload and "authHeaders()" in upload
    # The old stub is the fallback when the upload fails.
    assert "docImageStub(box, boxId" in upload and "function docImageStub(" in DOCS_JS


def test_u11_the_two_insert_menus_are_distinct():
    menus = DOCS_JS[DOCS_JS.index("const EDITOR_TOOLBAR_MENUS") : DOCS_JS.index("const EDITOR_TOOLBAR_BUTTONS")]
    assert 'label: "Links and media"' in menus and 'label: "Insert"' not in menus
    assert '["ol", "Numbered list"]' not in menus
    block = INDEX[INDEX.index('id="doc-toolbar-insert"') :]
    block = block[: block.index("</details>")]
    assert 'data-md="ol"' in block


def test_find_panel_is_tokened_with_a_tappable_close_button():
    assert ".cm-search" not in EDITOR_CSS  # moved to the lazy sheet, boot bytes down
    for selector in (".doc-editor .cm-search .cm-textfield", ".doc-editor .cm-search .cm-button"):
        assert "border-radius: var(--radius-md)" in _rule(LAZY_CSS, selector)
    close = _rule(LAZY_CSS, '.doc-editor .cm-search button[name="close"]')
    assert "min-width: 24px" in close and "min-block-size: 24px" in close
    coarse = LAZY_CSS[LAZY_CSS.index('.doc-editor .cm-search button[name="close"] {') :]
    assert re.search(r"@media \(pointer: coarse\) \{[^@]*cm-search button\[name=\"close\"\][^}]*min-block-size: 44px", coarse)


def test_d7_large_documents_check_a_window_not_the_whole_text():
    assert re.search(r"const DOC_PROSE_WINDOW_CHARS = \d+;", DOCS_JS)
    window = _fn("docProseWindow")
    assert "text.length <= DOC_PROSE_WINDOW_CHARS" in window and "visibleRanges" in window
    render = _fn("renderDocProse")
    assert "docProseWindow(text)" in render and "text.slice(win.from, win.to)" in render
    assert "docProseScrolled" in DOCS_JS
