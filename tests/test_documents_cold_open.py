"""L-documents-47: the cold open of Documents (DOCUMENTS_PLAN section 24 row 5).

Measured with scratchpad/ui-sweeps/docscold47.js. The three changes that cut
the path are guarded here by shape, because the numbers need a browser.
"""

from pathlib import Path
from tests._app_js import documents_text

JS = documents_text()


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


# L-documents-83: the chain before the bundle's code runs.
JS_DIR = Path(__file__).resolve().parent.parent / "frontend" / "js"
APP = (JS_DIR / "app.js").read_text()
WARM = (JS_DIR / "documents-warm.js").read_text()


def test_the_warm_file_is_the_first_of_the_library_bundle():
    library = APP.split("  library: [", 1)[1].split("],", 1)[0]
    first = [line for line in library.splitlines() if line.strip().startswith('"')][0]
    assert first.strip().startswith('"/js/documents-warm.js"')


def test_the_warm_file_asks_for_what_the_open_needs_while_the_bundle_arrives():
    for ask in ('"/documents/file-types"', "/documents?limit=${DOCUMENTS_PAGE_SIZE}&offset=0", "/documents/${rows[0].id}",
                "/vendor/codemirror/codemirror.min.js", "/js/documents-ide.js"):
        assert ask in WARM, ask
    #: Never for a note box's first focus, which loads the same bundle on another tab.
    assert 'getElementById("tab-documents")' in WARM and "return;" in WARM
    #: The same options the callers use, so a 401 behaves as it does for them.
    assert '{ silent: true }' in WARM


def test_api_hands_a_warmed_read_to_its_caller_once():
    #: In the lazy file, not app.js: the boot gzip cap (test_static_compression.py) has no room.
    assert "!options?.method && warm[path]?.()" in WARM  # a write is never answered from the warm map
    assert "delete warm[path]" in WARM and "4000" in WARM  # taken once, and dropped when nobody took it
    assert "Object.assign(" in WARM and "real)" in WARM  # api's own properties (epoch, retries, upload) stay
