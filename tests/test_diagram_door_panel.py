"""The Diagram builder opened from a list with no text box shows the builder (the owner, 2026-11-03).

"searching up and clicking the diagram builder in the find anything search took me to the documents
editor and did nothing else, it didnt even show the panel". The door started a blank .mmd page, which
is made only by its first keystroke, so the last document showed and no builder did. Now the builder
opens at once and Done saves a new .mmd document with what it shows; Cancel makes nothing.
"""

from __future__ import annotations

from pathlib import Path

JS = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "documents-mermaid.js").read_text(encoding="utf-8")


def _door() -> str:
    start = JS.index("async function diagramDoor(")
    return JS[start : JS.index("\n  }\n", start)]


def test_no_text_box_opens_the_builder_not_a_blank_page():
    door = _door()
    rest = door[door.index("if (!box) {") :]
    assert rest.lstrip("if (!box) {").lstrip().startswith("return openDiagramBuilder(")
    assert 'libraryNewDocument("mmd")' not in door


def test_done_saves_a_mmd_document_with_the_builders_source():
    rest = _door()[_door().index("if (!box) {") :]
    assert 'content: next, file_type: "mmd"' in rest and "loadDocuments(made.id)" in rest
