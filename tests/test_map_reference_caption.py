"""B38 (INBOX 904): a map node that points at a file or bookmark can be given
its own caption and can be opened.

The owner: "Attaching a file or thing to a mind map node makes a node that I
cant edit or even go to the thing attached."

Measured by `scratchpad/ui-sweeps/mapfile1017-b38.js` on a map with a file, a
bookmark and a document node: a double-click on the file and the bookmark
toasted "open it from the Library" and opened nothing, F2 on all three said
the name comes from the item, and the typed caption could not even be stored
(a field the schema does not name is dropped silently).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_JS = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")


def _map(client):
    board = client.post("/whiteboard/boards", json={"name": "Caption", "type": "map", "layout": "tree-right"}).json()
    root = client.post(f"/whiteboard/boards/{board['id']}/nodes", json={"text": "Root"}).json()
    return board, root


def test_a_reference_node_keeps_the_caption_it_was_given(client):
    board, root = _map(client)
    mark = client.post("/bookmarks", json={"url": "https://example.org/x", "title": "Example page"}).json()
    node = client.post(
        f"/whiteboard/boards/{board['id']}/nodes",
        json={"kind": "link", "ref_id": mark["id"], "parent_id": root["id"]},
    ).json()
    saved = client.put(
        f"/whiteboard/objects/{node['id']}",
        json={"kind": "link", "board_id": board["id"], "parent_id": root["id"], "x": node["x"], "y": node["y"], "data": {**node["data"], "caption": "Where I read it"}},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["caption"] == "Where I read it"
    again = [o for o in client.get("/whiteboard/", params={"board_id": board["id"]}).json()["objects"] if o["id"] == node["id"]]
    assert again, client.get("/whiteboard/", params={"board_id": board["id"]}).json()
    assert again[0]["data"]["caption"] == "Where I read it"
    # The item's own name is still what the tree resolves; the caption is the map's.
    tree = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"][0]["children"][0]
    assert tree["text"] == "Example page"


def test_a_file_or_bookmark_node_is_opened_not_sent_to_the_library() -> None:
    start = MAP_JS.index("function wbMapOpenReference(")
    body = MAP_JS[start : MAP_JS.index("\n}\n", start)]
    assert "open it from the Library" not in body
    assert 'd.kind === "file"' in body and "openLightbox(" in body
    assert 'd.kind === "link"' in body and "noopener" in body


def test_a_reference_node_renames_through_its_caption() -> None:
    label = MAP_JS[MAP_JS.index("function wbMapLabel(") :][:420]
    assert "caption" in label, "the caption is what the node says when it has one"
    edit = MAP_JS[MAP_JS.index("function wbMapEditNode(") :][:900]
    assert "wbMapEditCaption(" in edit
    assert "This node's name comes from the item it points at." not in edit
