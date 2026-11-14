"""A diagram is a document with the `mmd` file type (1546 D5, P1).

The type is one row of the file-type table, so history, versions, search, the
bin, autosave and export come with it and nothing migrates. The Library tells
it apart as it tells a board apart: `kind: "diagram"`, counted under its own
chip. The editor side (an `.mmd` opens in Split, the picture beside the source)
is read from documents.js and library.js.
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.core import filetypes
from tessellate.core.database import Document
from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def test_mmd_is_one_row_of_the_file_type_table():
    row = filetypes.get("mmd")
    assert row.ext == "mmd" and row.label == "Diagram"
    assert row.group == "Documents" and row.icon == "flow-arrow" and row.line_comment == "%%"
    # The server says previewable only for markdown; the editor draws a diagram's picture itself.
    assert not row.previewable
    assert filetypes.normalise("flow.mmd") == "mmd" and filetypes.normalise("MMD") == "mmd"
    groups = [ft.group for ft in filetypes.FILE_TYPES]
    assert groups.index("Data") > max(i for i, ft in enumerate(filetypes.FILE_TYPES) if ft.ext == "mmd")


def test_the_served_table_lists_it(client):
    types = client.get("/documents/file-types").json()["types"]
    assert any(t["ext"] == "mmd" and t["group"] == "Documents" for t in types)


def test_a_diagram_document_saves_and_comes_back(client):
    made = client.post("/documents", json={"title": "Flow", "content": "flowchart TD\n  A --> B\n", "file_type": "mmd"})
    assert made.status_code in (200, 201), made.text
    body = made.json()
    assert body["file_type"] == "mmd"
    saved = client.put(f"/documents/{body['id']}", json={"content": "flowchart LR\n  A --> B\n  B --> C\n"})
    assert saved.status_code == 200, saved.text
    again = client.get(f"/documents/{body['id']}").json()
    assert again["file_type"] == "mmd" and "B --> C" in again["content"]


def test_the_library_lists_a_diagram_as_its_own_kind_and_counts_it(client, session):
    session.add(Document(title="Plan", content="one two three"))
    session.add(Document(title="Flow", content="flowchart TD\n  A --> B\n", file_type="mmd"))
    session.add(Document(title="Flow two", content="flowchart TD\n  X --> Y\n", file_type="mmd"))
    session.commit()
    body = client.get("/library").json()
    kinds = {item["title"]: item["kind"] for item in body["items"] if item["kind"] in ("document", "diagram")}
    assert kinds == {"Plan": "document", "Flow": "diagram", "Flow two": "diagram"}
    assert body["counts"]["diagram"] == 2 and body["counts"]["document"] == 1
    assert body["overview"]["documents"] == 1
    found = client.get("/library", params={"q": "Flow"}).json()
    assert {i["title"] for i in found["items"] if i["kind"] == "diagram"} == {"Flow", "Flow two"}


def test_a_library_with_no_diagram_has_no_diagram_count(client, session):
    session.add(Document(title="Plan", content="one"))
    session.commit()
    assert "diagram" not in client.get("/library").json()["counts"]


def test_the_library_chip_and_the_open_path_know_the_kind():
    library = (JS / "library.js").read_text(encoding="utf-8")
    assert '{ key: "diagram", icon: "ph:flow-arrow", label: "Diagrams" }' in library
    # After Mind maps, as the plan puts it.
    keys = re.findall(r'^  \{ key: "(\w+)", icon:', library[library.index("const LIBRARY_KINDS = ["):], re.M)
    assert keys.index("diagram") == keys.index("map") + 1
    opener = library[library.index("function openLibraryItem(item) {") :]
    opener = opener[: opener.index("\n}\n")]
    assert 'item.kind === "document" || item.kind === "diagram"' in opener
    # The menu, delete and its undo take the same document routes.
    assert library.count('item.kind === "document" || item.kind === "diagram"') >= 4


def test_an_mmd_document_opens_in_blocks_and_its_view_is_never_stored():
    # 1546 P2 moved the intent: the diagram's own view is Blocks (the Read button, relabelled), with
    # Split and Source beside it, so the opening view and the fallback changed from Split.
    docs = documents_text()
    state = docs[docs.index("const docViewState = {") :]
    state = state[: state.index("\n};")]
    assert 'type.ext === "mmd" && ["split", "rendered", "canvas", "blocks"].includes(mode)' in state and "type.previewable" in state
    sync = docs[docs.index("function syncDocFileType(") :]
    sync = sync[: sync.index("\n  docCmSyncFileType();")]
    assert 'setDocView(type.ext === "mmd" ? "canvas" : "source")' in sync and "docViewState.allows(type, docView)" in sync
    assert "A diagram has Picture, List, Split and Source." in sync
    setter = docs[docs.index("function setDocView(") :]
    setter = setter[: setter.index("\n}\n")]
    # held means "not written to the prefs a markdown document reads".
    assert 'docViewState.held = !type.previewable && (docView === "source" || type.ext === "mmd")' in setter
    assert "if (!docViewState.held) prefs.set(DOC_VIEW_KEY, docView)" in setter
    preview = docs[docs.index("function renderDocPreview() {") :]
    preview = preview[: preview.index("\n}\n")]
    # The preview is the block pane (it keeps its own DOM), not a fence drawn through the frame.
    assert 'ensureModule("diagramBuilder")' in preview and '"```mermaid\\n" + text' not in preview
