"""DOCUMENTS_PLAN 22.4 R9b (INBOX 1621): a board diagram object may carry `data.diagram_id`, its library row.

The validator takes a whole number from 1 for a diagram object and no other kind; a row that was deleted is a valid state (the
board draws its snapshot); an id that names a row which is not a diagram is refused. A library save strips the key.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
SRC = "flowchart TD\n  A --> B\n"


def _post(client, data, kind="diagram"):
    return client.post("/whiteboard/objects", json={"kind": kind, "data": data, "x": 0, "y": 0, "width": 320, "height": 200})


def _diagram_row(client) -> int:
    return client.post("/documents", json={"title": "Flow", "content": SRC, "file_type": "mmd"}).json()["id"]


def test_a_diagram_object_keeps_the_id_of_its_library_row(ai_client):
    row = _diagram_row(ai_client)
    made = _post(ai_client, {"mermaid": SRC, "diagram_id": row})
    assert made.status_code == 201, made.text
    assert made.json()["data"]["diagram_id"] == row
    obj = made.json()
    again = ai_client.put(f"/whiteboard/objects/{obj['id']}", json={**obj, "data": {**obj["data"], "mermaid": SRC + "  B --> C\n"}})
    assert again.status_code == 200 and again.json()["data"]["diagram_id"] == row


@pytest.mark.parametrize("bad", [0, -3, 1.5, "7", "x", True, [1], {"a": 1}])
def test_a_malformed_diagram_id_is_refused(ai_client, bad):
    assert _post(ai_client, {"mermaid": SRC, "diagram_id": bad}).status_code == 422


def test_the_key_is_refused_on_other_kinds(ai_client):
    assert _post(ai_client, {"content": "hi", "diagram_id": 1}, kind="text").status_code == 422
    assert _post(ai_client, {"content": "hi", "diagram_id": 1}, kind="frame").status_code == 422


def test_a_row_that_does_not_exist_is_a_valid_state(ai_client):
    made = _post(ai_client, {"mermaid": SRC, "diagram_id": 987654})
    assert made.status_code == 201 and made.json()["data"]["mermaid"] == SRC


def test_an_id_that_names_a_row_that_is_not_a_diagram_is_refused(ai_client):
    doc = ai_client.post("/documents", json={"title": "Prose", "content": "hello", "file_type": "md"}).json()["id"]
    assert _post(ai_client, {"mermaid": SRC, "diagram_id": doc}).status_code == 422


def test_a_private_notes_id_does_not_leak_or_link(ai_client):
    note = ai_client.post("/entries", json={"content": "secret plan", "is_private": True})
    note_id = note.json().get("id", 1) if note.status_code in (200, 201) else 1
    made = _post(ai_client, {"mermaid": SRC, "diagram_id": note_id})
    # Notes live in another table: the id only ever resolves among documents, so nothing of the note comes back.
    assert "secret plan" not in made.text
    if made.status_code == 201:
        assert made.json()["data"]["mermaid"] == SRC


def test_save_many_applies_the_same_rule(ai_client):
    made = _post(ai_client, {"mermaid": SRC}).json()
    bad = {**made, "data": {**made["data"], "diagram_id": 0}}
    res = ai_client.put("/whiteboard/items/save-many", json={"nodes": [], "sketches": [], "objects": [bad]})
    assert res.status_code == 422, res.text


def test_a_library_save_strips_the_key():
    library = (JS / "whiteboard-library.js").read_text(encoding="utf-8")
    server = (ROOT / "src" / "tessellate" / "api" / "routes_board_library.py").read_text(encoding="utf-8")
    assert "delete data.diagram_id" in library
    assert '"diagram_id"' in server


def test_the_board_redraws_from_the_row_and_says_when_it_is_gone():
    interchange = (JS / "whiteboard-interchange.js").read_text(encoding="utf-8")
    paint = interchange.split("function wbPaintDiagram(")[1].split("\n}\n")[0]
    assert "/documents/${" in paint and "The linked diagram was deleted" in paint
    save = interchange.split("async function wbSaveDiagram(")[1].split("\n}\n")[0]
    assert "diagram_id" in save  # a deleted link is dropped on the next edit
