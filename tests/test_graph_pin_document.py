"""B78 (INBOX 904): pinning a document node on the graph is saved.

The owner's console: `ERROR: browser: [HTTP 422] PUT /graph/pin/document:2:
Check the entry id and try again.` The route's path was an integer note id,
so a document node's id ("document:2"), which the graph draws and lets you
pin by double-click or drag, never parsed. A document now holds its own pin
(`documents.graph_pin_x`/`graph_pin_y`), the payload sends it back on the
node, and a clear releases it. A node with no row of its own (a tag, an
entity, a file) is refused with a clear 404, and the client no longer asks.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _document(client) -> int:
    made = client.post("/documents", json={"title": "Pinned doc", "content": "x"})
    assert made.status_code in (200, 201), made.text
    return made.json()["id"]


def _doc_node(client, document_id: int) -> dict:
    nodes = client.get("/graph", params={"include_documents": "true"}).json()["nodes"]
    return next(n for n in nodes if n["id"] == f"document:{document_id}")


def test_a_document_node_can_be_pinned_and_released(client):
    doc = _document(client)
    pinned = client.put(f"/graph/pin/document:{doc}", json={"x": 12.5, "y": -40})
    assert pinned.status_code == 200, pinned.text
    assert pinned.json()["graph_pin_x"] == 12.5
    node = _doc_node(client, doc)
    assert (node["graph_pin_x"], node["graph_pin_y"]) == (12.5, -40)
    released = client.put(f"/graph/pin/document:{doc}", json={"x": None, "y": None})
    assert released.status_code == 200
    node = _doc_node(client, doc)
    assert node.get("graph_pin_x") is None


def test_a_note_still_pins_by_its_plain_id(client):
    note = client.post("/entries", json={"content": "A note to pin"}).json()
    pinned = client.put(f"/graph/pin/{note['id']}", json={"x": 1, "y": 2})
    assert pinned.status_code == 200, pinned.text
    assert pinned.json()["graph_pin_x"] == 1


def test_a_topic_drag_pins_notes_and_documents_in_one_write(client):
    doc = _document(client)
    note = client.post("/entries", json={"content": "Another note"}).json()
    sent = client.put(
        "/graph/pins",
        json={"pins": [{"id": note["id"], "x": 3, "y": 4}, {"id": f"document:{doc}", "x": 5, "y": 6}, {"id": "entity:z", "x": 1, "y": 1}]},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json() == {"pinned": 2}
    assert _doc_node(client, doc)["graph_pin_x"] == 5


def test_a_node_with_no_row_of_its_own_is_refused_plainly(client):
    for bad in ("entity:alice", "attachment:3", "document:99999", "document:x"):
        refused = client.put(f"/graph/pin/{bad}", json={"x": 1, "y": 2})
        assert refused.status_code == 404, (bad, refused.status_code, refused.text)


def test_the_client_only_asks_for_pins_it_can_keep() -> None:
    graph = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")
    canvas = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")
    assert "function graphPinSave(" in graph
    assert graph.count("`/graph/pin/${") == 1, "every pin write goes through the one helper"
    assert canvas.count("`/graph/pin/${") == 0
    assert canvas.count("graphPinSave(") == 2
