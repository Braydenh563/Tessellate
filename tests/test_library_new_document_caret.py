"""typepick-1031: the Library's New document takes the same type caret as the
Documents list's New (`docTypeMenu`), so a script or a sheet can be started
from where documents are listed, not only from the editor's own page."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
LIBRARY = (JS / "library.js").read_text(encoding="utf-8")
DOCUMENTS = (JS / "documents.js").read_text(encoding="utf-8") + (JS / "documents-view.js").read_text(encoding="utf-8")


def test_library_new_document_is_a_split_button_with_a_type_slot():
    split = re.search(r'<div class="split-button[^"]*">\s*<button id="library-docs-new"[^>]*split-button-main[^>]*>.*?</div>', HTML, re.S)
    assert split, "New document is the main half of a split button"
    assert 'id="library-docs-new-slot"' in split.group(0)
    assert "split-button-slot" in split.group(0)


def test_the_type_picker_lives_with_the_table_the_library_loads_alone():
    # library.js is the one file the Library loads alone; documents.js loads after it.
    assert "function docTypeMenu(" in LIBRARY
    assert "function docTypeMenu(" not in DOCUMENTS


def test_the_caret_starts_a_document_of_the_type_chosen():
    start = LIBRARY.index("function libraryDocsNewMount(")
    body = LIBRARY[start : LIBRARY.index("\n}\n", start)]
    assert "docTypeMenu(" in body and "library-docs-new-slot" in body
    assert "split-button-caret" in body
    handler = LIBRARY[LIBRARY.index("async function libraryNewDocument(") :]
    handler = handler[: handler.index("\n}\n")]
    assert "startBlankDocument(fileType)" in handler and 'ensureModule("library")' in handler
    assert handler.index('ensureModule("library")') < handler.index("startBlankDocument(")
    assert "libraryDocsNewMount()" in LIBRARY[LIBRARY.index("async function renderLibraryDocuments(") :]


def test_an_empty_code_document_does_not_say_markdown_works_here():
    """typepick-1031: the placeholder follows the file type, on the engine's own
    compartment (CodeMirror builds its placeholder once, so a later
    `docSetPlaceholder` has to reconfigure it) and on every type change."""
    assert "docCmParts.placeholder = new CM.state.Compartment()" in DOCUMENTS
    assert "docCmParts.placeholder.reconfigure(" in DOCUMENTS
    body = DOCUMENTS[DOCUMENTS.index("function docPlaceholderFor(") :]
    body = body[: body.index("\n}\n")]
    assert "previewable" in body and "docBlankPlaceholder()" in body
    sync = DOCUMENTS[DOCUMENTS.index("function syncDocFileType(") :]
    sync = sync[: sync.index("\n}\n")]
    assert "docSetPlaceholder(docPlaceholderFor(type))" in sync
