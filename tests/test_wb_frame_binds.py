"""L-whiteboard-12: a frame can be bound to a note property
(`binds: {property, value}`). A card dropped inside it writes that value to
its note ("a kanban that edits your notebook"), and the board's bind sync
moves a card whose note now holds another bound frame's value into that frame.
One field per frame."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _note(client, text="# Ship the release\nWrite the notes."):
    out = client.post("/entries", json={"content": text})
    assert out.status_code in (200, 201), out.text
    return out.json()["id"]


def _board(client):
    return client.post("/whiteboard/boards", json={"name": "Kanban", "type": "board"}).json()["id"]


def _frame(client, bid, title, x, binds):
    body = {"kind": "frame", "data": {"content": title, "binds": binds}, "board_id": bid, "x": x, "y": 0, "z": 0, "width": 300, "height": 400}
    out = client.post("/whiteboard/objects", json=body)
    assert out.status_code in (200, 201), out.text
    return out.json()


def _props(client, eid):
    return client.get(f"/entries/{eid}/properties").json()["properties"]


def _move(client, node, x, y):
    out = client.put(f"/whiteboard/nodes/{node['id']}", json={"entry_id": node["entry_id"], "board_id": node["board_id"], "x": x, "y": y})
    assert out.status_code == 200, out.text
    return out.json()


def test_a_frame_keeps_its_binding_and_refuses_a_bad_name(client):
    bid = _board(client)
    frame = _frame(client, bid, "Done", 0, {"property": "status", "value": "Done"})
    assert frame["data"]["binds"] == {"property": "status", "value": "Done"}
    bad = {"kind": "frame", "data": {"content": "X", "binds": {"property": "a:b", "value": "x"}}, "board_id": bid, "x": 0, "y": 0, "width": 100, "height": 100}
    out = client.post("/whiteboard/objects", json=bad)
    assert out.status_code == 422


def test_a_card_dropped_in_a_bound_frame_writes_the_value_to_its_note(client):
    bid = _board(client)
    _frame(client, bid, "Doing", 0, {"property": "status", "value": "Doing"})
    _frame(client, bid, "Done", 400, {"property": "status", "value": "Done"})
    eid = _note(client)
    node = client.post("/whiteboard/nodes", json={"entry_id": eid, "board_id": bid, "x": 900, "y": 50}).json()
    assert "status" not in _props(client, eid)
    _move(client, node, 450, 50)
    assert _props(client, eid)["status"] == ["Done"]
    _move(client, node, 20, 50)
    assert _props(client, eid)["status"] == ["Doing"]
    body = client.get(f"/entries/{eid}").json()["content"]
    assert "Write the notes." in body


def test_a_card_outside_every_bound_frame_leaves_its_note_alone(client):
    bid = _board(client)
    _frame(client, bid, "Done", 0, {"property": "status", "value": "Done"})
    _frame(client, bid, "Loose", 400, None)
    eid = _note(client)
    node = client.post("/whiteboard/nodes", json={"entry_id": eid, "board_id": bid, "x": 900, "y": 50}).json()
    _move(client, node, 450, 50)
    assert "status" not in _props(client, eid)


def test_the_sync_moves_a_card_whose_note_changed_into_its_frame(client):
    bid = _board(client)
    _frame(client, bid, "Doing", 0, {"property": "status", "value": "Doing"})
    done = _frame(client, bid, "Done", 400, {"property": "status", "value": "Done"})
    eid = _note(client)
    node = client.post("/whiteboard/nodes", json={"entry_id": eid, "board_id": bid, "x": 20, "y": 50}).json()
    _move(client, node, 20, 60)
    put = client.put(f"/entries/{eid}/properties", json={"properties": {"status": "Done"}})
    assert put.status_code == 200, put.text
    out = client.post(f"/whiteboard/boards/{bid}/binds/sync")
    assert out.status_code == 200, out.text
    assert out.json()["moved"] == [node["id"]]
    state = client.get(f"/whiteboard/?board_id={bid}").json()
    card = next(n for n in state["nodes"] if n["id"] == node["id"])
    assert done["x"] <= card["x"] <= done["x"] + done["width"] and done["y"] <= card["y"] <= done["y"] + done["height"]
    again = client.post(f"/whiteboard/boards/{bid}/binds/sync").json()
    assert again["moved"] == []


def test_the_board_syncs_on_open_and_the_frame_menu_binds():
    js = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    assert "/binds/sync" in js
    assert "Bind to a property" in js
