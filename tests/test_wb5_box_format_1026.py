"""Format panel box rows: per-corner radius, padding, shadow offset and blur (WHITEBOARD_PLAN 1355, wb5)."""

from __future__ import annotations


def _body(client, **data):
    board = client.post("/whiteboard/boards", json={"name": "Box", "type": "board"}).json()
    return {"board_id": board["id"], "kind": "text", "x": 0, "y": 0, "width": 200, "height": 100,
            "data": {"content": "hi", **data}}


def test_box_rows_round_trip_and_survive_an_update(client):
    made = client.post("/whiteboard/objects", json=_body(
        client, radii=[0, 12, 24, 36], pad=18, shadow=True, shadow_x=4, shadow_y=-6, shadow_blur=20))
    assert made.status_code in (200, 201), made.text
    got = made.json()["data"]
    assert got["radii"] == [0, 12, 24, 36] and got["pad"] == 18
    assert (got["shadow_x"], got["shadow_y"], got["shadow_blur"]) == (4, -6, 20)
    oid = made.json()["id"]
    again = {k: v for k, v in got.items() if v is not None}
    put = client.put(f"/whiteboard/objects/{oid}", json={**_body(client), "data": {**again, "pad": 0}})
    assert put.status_code == 200, put.text
    assert put.json()["data"]["radii"] == [0, 12, 24, 36] and put.json()["data"]["pad"] == 0


def test_box_rows_are_bounded(client):
    for bad in ({"radii": [1, 2, 3]}, {"radii": [1, 2, 3, 999]}, {"pad": 500},
                {"shadow_x": 90}, {"shadow_blur": -1}):
        res = client.post("/whiteboard/objects", json=_body(client, **bad))
        assert res.status_code == 422, bad
