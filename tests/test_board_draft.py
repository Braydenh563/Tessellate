"""A board's frames written as a document draft (L-documents-4).

`POST /whiteboard/boards/{id}/draft` returns `{title, body, frames, items}` and
saves nothing; the client makes the document. A heading per frame, a paragraph per
sticky or text box inside it (top to bottom, then left to right), what lies outside
every frame last.
"""

from __future__ import annotations


def _object(client, board_id, kind, x, y, w, h, content):
    made = client.post(
        "/whiteboard/objects",
        json={"board_id": board_id, "kind": kind, "x": x, "y": y, "width": w, "height": h, "data": {"content": content}},
    )
    assert made.status_code in (200, 201), made.text


def _board(client):
    return client.post("/whiteboard/boards", json={"name": "Launch plan"}).json()


def test_a_heading_per_frame_and_a_paragraph_per_item_in_reading_order(client):
    board = _board(client)
    bid = board["id"]
    _object(client, bid, "frame", 500, 0, 400, 300, "Risks")
    _object(client, bid, "frame", 0, 0, 400, 300, "Goals")
    _object(client, bid, "text", 20, 150, 100, 60, "Ship in March")
    _object(client, bid, "text", 20, 20, 100, 60, "Fewer bugs")
    _object(client, bid, "text", 520, 20, 100, 60, "Vendor slips")
    _object(client, bid, "text", 2000, 2000, 100, 60, "Stray idea")
    got = client.post(f"/whiteboard/boards/{bid}/draft")
    assert got.status_code == 200, got.text
    out = got.json()
    assert out["title"] == "Launch plan"
    assert out["body"] == "## Goals\n\nFewer bugs\n\nShip in March\n\n## Risks\n\nVendor slips\n\n## Outside the frames\n\nStray idea"
    assert (out["frames"], out["items"]) == (2, 4)
    documents = client.get("/documents").json()
    assert len(documents) == 0


def test_a_board_with_no_frames_is_one_list_of_its_items(client):
    bid = _board(client)["id"]
    _object(client, bid, "text", 0, 0, 100, 60, "Only idea")
    out = client.post(f"/whiteboard/boards/{bid}/draft").json()
    assert out["body"] == "Only idea" and out["frames"] == 0


def test_an_empty_board_has_nothing_to_draft(client):
    bid = _board(client)["id"]
    got = client.post(f"/whiteboard/boards/{bid}/draft")
    assert got.status_code == 422 and "nothing" in got.json()["detail"].lower()
