"""The Library's Documents list can import a file as a document (BACKLOG
section 99: "an upload documents option in the documents tab in the library").

`POST /documents/import` (tests/test_document_import.py) already turned a Word
file, PDF, spreadsheet, Markdown or code file into a Document, but only the
chat's paperclip reached it. These checks hold the door the Library now has:
the markup, the handler that talks to the route, and the two help surfaces that
name it (standing order 13: help moves with the UI). The DOM itself is
exercised by the sweep `scratchpad/ui-sweeps/bl1005-docsimport.js`.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import app_js_text
from tests._app_js import index_html_text

ROOT = Path(__file__).resolve().parent.parent
INDEX = index_html_text()
LIBRARY = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")


def _more_menu() -> str:
    match = re.search(
        r'<details[^>]*id="library-docs-more-menu".*?</details>', INDEX, re.S
    )
    assert match, "the Documents list's more menu is gone"
    return match.group(0)


def test_the_import_button_and_its_file_input_are_in_the_more_menu():
    menu = _more_menu()
    assert 'id="library-docs-import"' in menu
    assert 'id="library-docs-import-input"' in menu
    # Several files at once, picked from a hidden input the button opens.
    input_tag = re.search(r'<input[^>]*id="library-docs-import-input"[^>]*>', menu, re.S)
    assert input_tag and "multiple" in input_tag.group(0) and 'type="file"' in input_tag.group(0)
    assert "aria-label" in input_tag.group(0)


def test_the_handler_posts_each_file_to_documents_import_with_both_headers():
    assert '"library-docs-import-input"' in LIBRARY
    body = LIBRARY[LIBRARY.index("async function importLibraryDocuments") :]
    body = body[: body.index("async function renderLibraryDocuments")]
    assert '"/documents/import"' in body
    # `api()` replaces its default headers when `headers` is given, so the
    # workspace has to be named or the document lands in the default space.
    assert "authHeaders()" in body or ("X-Workspace-ID" in body and "X-Auth-Token" in body)
    # A FormData body must not carry a hand-set Content-Type.
    assert "Content-Type" not in body
    # One file that cannot be read must not stop the rest.
    assert "catch (error)" in body and "for (const file of files)" in body
    # The list is redrawn so the new document shows without a reload.
    assert "renderLibraryDocuments()" in body


def test_the_help_surfaces_name_the_new_control():
    popover = re.search(r'id="library-docs-help"[^>]*>(.*?)</div>', INDEX, re.S)
    assert popover and "Import a file" in popover.group(1)
    from tessellate.ai.help_topics_more import MORE_TOPICS

    topic = next(t for t in MORE_TOPICS if t["id"] == "import-export")
    assert "as a document" in topic["body"]
    assert "import as a document" in topic["keywords"]


def test_the_new_copy_has_no_em_dash_and_no_exclamation():
    menu = _more_menu()
    assert chr(0x2014) not in menu and "Import a file as a document!" not in menu
    assert chr(0x2014) not in LIBRARY[LIBRARY.index("async function importLibraryDocuments") :][:1800]


def test_app_js_text_still_assembles():
    # `app_js_text()` reads every piece; a syntax slip in library.js would
    # surface in `node --check` (gate.sh), this just keeps the helper honest.
    assert "importLibraryDocuments" in LIBRARY
    assert app_js_text()
