"""L-documents-64: a Today button in the Library's Documents dock (DOCUMENTS_PLAN section 14).

It reuses the Daily template row (no second create-or-return endpoint) and adds no top-level name.
Measured 2026-11-14 on a fresh data dir (scratchpad t646-today.js): two presses made one document titled
with the day, 1 row after each; at 390 px the button's right edge was 297.6 against a dock 328 wide.
"""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
LIB = (JS / "library.js").read_text(encoding="utf-8")
DOCS = (JS / "documents.js").read_text(encoding="utf-8")


def _mount() -> str:
    start = LIB.index("function libraryDocsNewMount()")
    return LIB[start : LIB.index("\nasync function renderLibraryDocuments", start)]


def test_today_uses_the_daily_template_and_finds_the_days_document_by_its_title():
    mount = _mount()
    assert 'b.id = "library-docs-today"' in mount
    assert 'DOC_TEMPLATES.find((t) => t.id === "daily")' in mount
    # The title is the template's own, so the button and the gallery row cannot disagree about the day.
    assert "window.docTemplateFill(template).title" in mount
    assert "window.createDocument(template)" in mount and "openDocument(doc.id)" in mount
    # Matches the exact title: a search hit on content is not today's page.
    assert '(d.title || "").trim() === day' in mount


def test_the_daily_row_still_titles_the_document_with_the_iso_day():
    row = re.search(r'id: "daily".*?content:', DOCS, re.S).group(0)
    assert 'docTitle: "{{isodate}}"' in row


def test_today_is_in_the_help_and_adds_no_global_name():
    assert "Today, beside New document" in (JS.parent / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"^(?:async )?function \w*[Tt]oday\w*\(", LIB, re.M)
