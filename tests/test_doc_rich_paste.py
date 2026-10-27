"""A paste from a web page, Word or Google Docs keeps its structure as
Markdown (audit FEAT-04, 2026-10-05).

The converter needs a DOM (`DOMParser`), so its behaviour is driven in a
browser by `scratchpad/ui-sweeps/mmdoc1005-richpaste.js` (a web page, a
Google Docs copy, an unsafe link with a script, a code editor's copy, and
Ctrl+Shift+V). These pin the wiring and the two safety rules.
"""

from __future__ import annotations

from pathlib import Path

DOCS = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")


def test_the_editor_tries_the_table_paste_then_the_smart_one_then_the_rich_one():
    # docpaste-1026 put the smart paste (web address, several lines, Paste special) between them.
    assert "docTablePasteEvent(event, view) || docSmartPasteEvent(event, view) || docRichPasteEvent(event, view)" in DOCS


def test_only_safe_link_schemes_are_written():
    start = DOCS.index("function docHtmlToMarkdown(")
    body = DOCS[start:DOCS.index("\nfunction docRichPasteEvent(", start)]
    assert "/^(https?:|mailto:)/i" in body
    assert "javascript" not in body.lower()


def test_ctrl_shift_v_pastes_plain_text():
    assert 'docPastePlain = (event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "v"' in DOCS


def test_word_list_paragraphs_become_a_list():
    # Word has no <ul>: a list item is a <p style="mso-list:l0 level2"> with a nested marker span
    # (mso-list:Ignore). Browser check (docdog-1026): bullets, a level-2 bullet and "1." items.
    assert "|mso-list/i;" in DOCS
    body = DOCS[DOCS.index("function docWordListLine("):DOCS.index("function docHtmlToMarkdown(")]
    assert "level(" in body and '"ignore"' in body
    assert "docWordListLine(child, styleOf, inline)" in DOCS


def test_a_picture_pasted_or_dropped_into_a_document_is_uploaded():
    # Before (docdog-1026): nothing happened: the document editor sits under #doc-editor, not a
    # .note-surface, so the drop and paste listeners never answered it. After: a pasted 120x80 png
    # became ![shot.png](/media/<id>.png) at the caret, a dropped one at the pointer.
    from tests._app_js import app_js_text

    code = app_js_text()
    assert 'el?.closest?.("#doc-editor")' in code
    assert 'box.kind === "codemirror" && e.clipboardData.getData("text/plain")' in code
    assert "box.view.posAtCoords({ x: e.clientX, y: e.clientY })" in code


def test_emphasis_kept_only_in_a_span_style_is_a_rich_paste_unless_it_is_code():
    # dog3d-1026:7: a lone <span style="font-weight:700"> arrived as plain text. Browser check
    # (scratchpad/ui-sweeps/mmdoc1005-richpaste.js): "**Heavy words**", "*Soft words*", and a
    # monospace white-space:pre copy with a bold token stays plain.
    body = DOCS[DOCS.index("const DOC_RICH_STYLE"):DOCS.index("let docPastePlain")]
    assert "font-weight" in body and "font-style" in body
    assert "white-space" in body and "consolas" in body
    assert "DOC_RICH_TAGS.test(html) || (DOC_RICH_STYLE.test(html) && !DOC_CODE_HTML.test(html))" in body
    # Both paste handlers ask the one question.
    prose = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "documents-prose.js").read_text(encoding="utf-8")
    assert "docHtmlIsRich(html)" in DOCS and "docHtmlIsRich(html)" in prose
