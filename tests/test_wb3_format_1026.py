"""Format panel text spacing (WHITEBOARD_PLAN 1355 item 6)."""

from __future__ import annotations


def _board(client):
    return client.post("/whiteboard/boards", json={"name": "Fmt", "type": "board"}).json()


def test_text_spacing_round_trips(client):
    board = _board(client)
    body = {"board_id": board["id"], "kind": "text", "x": 0, "y": 0, "width": 200, "height": 100,
            "data": {"content": "hi", "line_height": 1.8, "letter_spacing": 3}}
    made = client.post("/whiteboard/objects", json=body)
    assert made.status_code in (200, 201), made.text
    got = made.json()
    assert got["data"]["line_height"] == 1.8
    assert got["data"]["letter_spacing"] == 3


def test_text_spacing_is_bounded(client):
    board = _board(client)
    for bad in ({"line_height": 9}, {"letter_spacing": -50}):
        body = {"board_id": board["id"], "kind": "text", "x": 0, "y": 0, "width": 200, "height": 100,
                "data": {"content": "hi", **bad}}
        res = client.post("/whiteboard/objects", json=body)
        assert res.status_code == 422
