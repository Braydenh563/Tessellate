"""dog1-1025 leftovers (fixa2). Browser checks: scratchpad/ui-sweeps/capturesave.js."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAZY_CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def test_capture_box_scrolls_inside_so_save_stays_in_view():
    # The stretch rule frees a scroller from its max-height; the capture box is
    # a stretched item too, and 30 lines pushed Save to y=981 at 800 high.
    assert "#capture .note-surface-stretch .cm-editor .cm-scroller" in LAZY_CSS
    assert "#capture .capture-commit-row {\n  position: sticky;" in LAZY_CSS


DOCS_JS = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")


def _body(head: str) -> str:
    start = DOCS_JS.index(head)
    return DOCS_JS[start : DOCS_JS.index("\n}\n", start)]


def test_blank_new_document_makes_no_row_until_the_first_edit():
    body = _body("async function createDocument(")
    # The blank path returns before the POST; only a template posts.
    assert body.index("startBlankDocument()") < body.index('apiJson("/documents"')
    blank = _body("async function startBlankDocument(")
    assert "/documents" not in blank, "a blank draft must not POST"
    assert "showNoDocument()" in blank


def test_document_sidebar_is_newest_edit_first():
    body = _body("function renderDocList(")
    assert "updated_at" in body and "sort(" in body


def test_settings_search_phone_ranks_other_devices_first():
    # Browser: scratchpad/ui-sweeps/settingsphone.js (findSettings("phone")[0]).
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<h3 data-synonyms="phone phones tablet lan wifi">Other devices</h3>' in index
    find = (ROOT / "frontend" / "js" / "settings-find.js").read_text(encoding="utf-8")
    assert "row.synonyms.includes(w)" in find

