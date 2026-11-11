"""D52 (audit 1028): the code editor's open files as a tab strip.

The behaviour is measured by `scratchpad/ui-sweeps/doctabs.js` (strip shows
with two code files, a click and an arrow key switch, Close file and a
middle-click close, a prose document or the list hides it). What a sweep does
not see is the wiring: the file must load after documents.js in the Library
bundle, documents.js must call it where a document opens and where the page
goes blank, and the markup must be a `.tabs-line` with words only.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
APP = (JS / "app.js").read_text(encoding="utf-8")
DOCS = (JS / "documents.js").read_text(encoding="utf-8")
TABS = (JS / "documents-tabs.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_the_tabs_file_loads_in_the_library_bundle_after_documents_js() -> None:
    assert APP.index('"/js/documents.js"') < APP.index('"/js/documents-tabs.js"')
    assert '/js/documents-tabs.js' not in HTML, "lazy: not a boot script"


def test_documents_js_calls_it_when_a_document_opens_and_when_the_page_goes_blank() -> None:
    opened = DOCS.index("async function openDocument(id) {")
    body = DOCS[opened : DOCS.index("\n}\n", opened)]
    shown = 'new CustomEvent("doc-shown", { detail: doc })'
    assert shown in body
    assert body.index("currentDoc = doc;") < body.index(shown) < body.index("docRestorePosition(doc.id);")
    blank = DOCS.index("function showNoDocument() {")
    assert 'new CustomEvent("doc-shown", { detail: null })' in DOCS[blank : DOCS.index("\n}\n", blank)]


def test_a_tab_keeps_its_place_and_only_code_files_enter() -> None:
    note = TABS[TABS.index("function docTabsNote(doc) {") :]
    note = note[: note.index("\n  }\n")]
    assert "docIsCodeFile()" in note
    assert "if (!ids.includes(doc.id))" in note, "choosing a tab again must not move it"
    assert "MAX = 8" in TABS


def test_the_strip_is_a_words_only_tabs_line_with_a_close_button() -> None:
    tag = re.search(r'<div id="doc-tabs"[^>]*>', HTML)
    assert tag and "tabs-line" in tag.group(0) and 'role="tablist"' in tag.group(0)
    assert 'id="doc-tab-end"' in HTML
    assert "<i " not in HTML[tag.end() : HTML.index("</div>", tag.end())]


def test_the_unlisted_ids_are_dropped_not_offered() -> None:
    """A deleted file's id is pruned against the list on every render, and a
    tab holds the id only: no title or text is stored in the browser."""
    assert "docs.some((d) => d.id === id)" in TABS
    assert "JSON.stringify(ids" in TABS
