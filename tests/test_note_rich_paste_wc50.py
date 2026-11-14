"""L-world-class-50: pasted HTML becomes Markdown in the note composers, through the
document's own converter (`docHtmlToMarkdown`), not a second one.

The converter needs a DOM, so the behaviour was driven in the app: a text/html paste of a
heading, a list and a link into #entry-content (the rendering note surface) and into
#quick-note-text gave `## Plan`, `- one`, `- two [link](https://example.com)`. These pin the
wiring that made it happen.
"""

from __future__ import annotations

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
DOCUMENTS = (JS / "documents.js").read_text(encoding="utf-8")
QUICK = (JS / "quick-note.js").read_text(encoding="utf-8")


def test_the_note_surface_takes_the_documents_rich_paste():
    body = DOCUMENTS[DOCUMENTS.index("function noteSurfaceExtensions("):]
    body = body[: body.index("noteLiveSlot.of(")]
    assert "paste: (event, view) => docRichPasteEvent(event, view)" in body
    assert 'docPastePlain = (event.ctrlKey || event.metaKey) && event.shiftKey' in body


def test_the_quick_note_converts_with_the_same_converter_and_keeps_ctrl_shift_v_plain():
    assert 'box.addEventListener("paste"' in QUICK
    assert 'ensureModule("library")' in QUICK
    assert "docHtmlIsRich(html) ? docHtmlToMarkdown(html)" in QUICK
    assert "docRichPasteEvent.fit(" in QUICK
    assert 'event.key.toLowerCase() === "v"' in QUICK
    # no second converter anywhere outside documents.js
    assert "DOMParser" not in QUICK
