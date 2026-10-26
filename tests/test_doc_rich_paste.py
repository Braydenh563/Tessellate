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
