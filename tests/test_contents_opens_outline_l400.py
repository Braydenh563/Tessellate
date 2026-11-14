"""Source text: a document with headings opened from the Library's Contents
opens on its Outline tab, so the editor's outline is three clicks deep, not
four (L400).

Measured at 1440 with the sidebar left on Documents: a click on the document's
row in Contents opened it with the Outline tab selected and its two headings
listed.
"""

from __future__ import annotations

import re

from tests._app_js import script_file_text

JS = script_file_text("library.js")


def test_contents_rows_with_headings_open_the_outline():
    body = re.search(r"function contentsOpenDocument\(docId, line, outline = false\) \{(.*?)\n\}", JS, re.S)
    assert body and 'if (outline) showDocSidebarSection("outline")' in body.group(1)
    assert "contentsOpenDocument(doc.id, head.line, true)" in JS
    assert "else contentsOpenDocument(doc.id, null, true)" in JS
