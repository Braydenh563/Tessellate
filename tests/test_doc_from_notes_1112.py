"""Many notes become one draft document (L-graph-1): structure from the
notes alone, no model."""

from __future__ import annotations


def _note(client, content, **extra):
    return client.post("/entries", json={"content": content, **extra}).json()


def test_several_notes_make_one_document_with_a_section_each(client):
    a = _note(client, "# Kiln plan\nFire on Friday")
    b = _note(client, "# Glaze tests\nCeladon is runny")
    r = client.post("/documents/from-notes", json={"note_ids": [b["id"], a["id"]]})
    assert r.status_code == 201
    doc = r.json()
    assert doc["title"] == "Draft from 2 notes"
    body = doc["content"]
    assert body.index("## Kiln plan") < body.index("## Glaze tests")  # oldest first
    assert "Fire on Friday" in body and "Celadon is runny" in body
    assert f"#{a['id']}" in body and f"#{b['id']}" in body
    saved = client.get(f"/entries/{a['id']}").json()
    assert saved["content"].startswith("# Kiln plan")


def test_a_note_with_no_heading_gets_its_first_line_as_title(client):
    a = _note(client, "buy clay\nand glaze")
    b = _note(client, "# Second\nbody")
    doc = client.post("/documents/from-notes", json={"note_ids": [a["id"], b["id"]]}).json()
    assert "## buy clay" in doc["content"] and "and glaze" in doc["content"]


def test_private_and_missing_notes_are_left_out(client):
    a = _note(client, "# Open\nfine")
    gone = _note(client, "# Gone\nx")
    client.delete(f"/entries/{gone['id']}")
    r = client.post("/documents/from-notes", json={"note_ids": [a["id"], gone["id"], 9999]})
    assert r.status_code == 201
    assert "Gone" not in r.json()["content"]


def test_nothing_usable_is_a_422(client):
    missing = client.post("/documents/from-notes", json={"note_ids": [9999]})
    assert missing.status_code == 422


def test_a_given_title_is_kept(client):
    a = _note(client, "# One\nx")
    b = _note(client, "# Two\ny")
    doc = client.post("/documents/from-notes", json={"note_ids": [a["id"], b["id"]], "title": "Pottery"}).json()
    assert doc["title"] == "Pottery"


def test_the_graph_selection_menu_offers_it_and_the_document_path_takes_a_list():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "frontend"
    graph = (root / "js" / "graph.js").read_text()
    docs = (root / "js" / "documents.js").read_text()
    assert "Compose into a draft" in graph and "expandNoteIntoDocument(ids)" in graph
    assert 'id="graph-selection-more"' in (root / "index.html").read_text()
    assert "Array.isArray(entry)" in docs and "/documents/from-notes" in docs
