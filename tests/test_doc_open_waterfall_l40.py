"""L-world-class-40: the first document open was a waterfall.

Measured at 2,000 notes and 6 documents of 80 sections (1440 wide, cold page,
Library, Documents, 6.5 s idle, then `openDocument`): the library bundle's 26
files at 0 to 150 ms, then documents-ide.js at about 200 ms, then the editor
bundle at about 205 ms, and only then `/documents/<id>` at 330 to 400 ms: a
first open of 419, 445 and 518 ms against 84 to 109 ms for the second. The
fetch had nothing to wait for, so it starts with the open and the modules load
beside it.
"""

from __future__ import annotations

from tests._app_js import documents_text


def _body() -> str:
    text = documents_text()
    start = text.index("async function openDocument(id) {")
    return text[start : text.index("\n}\n", start)]


def test_the_document_is_asked_for_before_the_modules_and_the_editor_load():
    body = _body()
    early = body.index("const early = ")
    assert early < body.index('await ensureModule("library")') < body.index("await ensureDocEditor()")
    assert "apiJson(`/documents/${id}`)" in body[early - 120 : early + 200]


def test_a_pending_save_still_comes_first():
    """The same document, saved and then fetched, is the saved one: the early
    ask is only made when nothing is waiting to be saved."""
    body = _body()
    assert "const early = docDirty ? null :" in body
    assert "const doc = await (early ||" in body
