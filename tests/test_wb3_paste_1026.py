"""One-request board paste (WHITEBOARD_PLAN 1355): copied things are made in
one transaction and a copied link is pointed at the copies' new ids."""

from __future__ import annotations

import json


def _board(client):
    return client.post("/whiteboard/boards", json={"name": "Paste", "type": "board"}).json()


def _obj(content, x=0):
    return {"kind": "text", "x": x, "y": 0, "z": 1, "width": 200, "height": 100, "data": {"content": content}}


def test_paste_makes_items_and_rewires_links(client):
    board = _board(client)
    body = {"items": [
        {"key": "a", "object": _obj("A")},
        {"key": "b", "object": _obj("B", 300)},
        {"key": "s", "sketch": {"data": json.dumps({"d": "M 0 0 L 10 10"}), "x": 0, "y": 0, "z": 0}},
        {"key": "l", "src": "a", "dst": "b", "sketch": {"data": json.dumps({"type": "link-straight", "sourceId": 999, "sourceKind": "object", "targetId": 998, "targetKind": "object"})}},
    ]}
    res = client.post(f"/whiteboard/boards/{board['id']}/paste", json=body)
    assert res.status_code == 201, res.text
    out = res.json()
    assert len(out["objects"]) == 2 and len(out["sketches"]) == 2
    link = next(s for s in out["sketches"] if "link-straight" in s["data"])
    data = json.loads(link["data"])
    assert data["sourceId"] == out["keys"]["a"]["id"] and data["targetId"] == out["keys"]["b"]["id"]
    assert data["sourceKind"] == "object"


def test_paste_refuses_an_empty_list_and_a_missing_board(client):
    board = _board(client)
    empty = client.post(f"/whiteboard/boards/{board['id']}/paste", json={"items": []})
    missing = client.post("/whiteboard/boards/999999/paste", json={"items": [{"key": "a", "object": _obj("A")}]})
    assert empty.status_code == 422
    assert missing.status_code == 404


def test_an_object_carrying_stray_link_ends_is_still_made(client):
    # Review, 2026-10-27: an object with src or dst was neither made nor refused.
    board = _board(client)
    body = {"items": [{"key": "a", "object": _obj("A")}, {"key": "b", "src": "a", "object": _obj("B", 300)}]}
    res = client.post(f"/whiteboard/boards/{board['id']}/paste", json=body)
    assert res.status_code == 201, res.text
    assert set(res.json()["keys"]) == {"a", "b"} and len(res.json()["objects"]) == 2
