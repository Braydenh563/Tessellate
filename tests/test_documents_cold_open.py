"""L-documents-47: the cold open of Documents (DOCUMENTS_PLAN section 24 row 5).

Measured with scratchpad/ui-sweeps/docscold47.js. The three changes that cut
the path are guarded here by shape, because the numbers need a browser.
"""

from pathlib import Path

JS = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "documents.js").read_text()


def _body(start: str, end: str) -> str:
    return JS.split(start, 1)[1].split(end, 1)[0]


def test_the_engine_is_warmed_on_phones_too_unless_data_or_memory_is_short():
    body = _body("function warmDocumentEngine() {", "\n}\n")
    assert "max-width" not in body
    assert "saveData" in body
    assert "deviceMemory" in body


def test_the_list_is_fetched_beside_the_file_type_table():
    body = _body("async function loadDocumentsNow(selectId) {", "\n}\n")
    assert body.index("apiPagedList(") < body.index("await loadDocFileTypes()")


def test_the_document_is_fetched_beside_the_engine_bundle():
    body = _body("async function openDocument(id) {", "\n}\n")
    assert body.index("apiJson(`/documents/${id}`)") < body.index("await ensureDocEditor()")
