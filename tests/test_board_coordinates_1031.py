"""Bounded board coordinates (audit 1031 BD1).

`y: 1e308` was stored (201). Two such objects put every item at y = -33 million
at 100% zoom, zoom to fit showed nothing, and PNG export failed. `"x": "NaN"`
answered 500 because SQLite stores NaN as NULL. The route now refuses what no
board can show (422 naming the field), and an old row already out of range is
clamped when it is read, so it cannot blank the board again."""

from __future__ import annotations

import pytest

LIMIT = 1_000_000.0
def _named(resp) -> list[str]:
    """The fields the 422 names (a substring check would match "text")."""
    return [f["field"] for f in resp.json().get("fields", [])]


def _entry(client) -> int:
    return client.post("/entries", json={"content": "a card"}).json()["id"]


def _bodies(client):
    yield "/whiteboard/objects", {"kind": "text", "data": {"content": "hi"}}
    yield "/whiteboard/sketches", {"data": "M0 0L1 1"}
    yield "/whiteboard/nodes", {"entry_id": _entry(client)}


@pytest.mark.parametrize("field", ["x", "y"])
@pytest.mark.parametrize("value", [1e308, -1e308, LIMIT + 1, -LIMIT - 1, "NaN", "Infinity"])
def test_a_coordinate_no_board_can_show_is_refused_naming_the_field(client, field, value):
    for path, body in _bodies(client):
        resp = client.post(path, json={**body, field: value})
        assert resp.status_code == 422, (path, field, value, resp.text)
        assert field in _named(resp), resp.text


def test_the_limit_itself_and_ordinary_values_are_accepted(client):
    for path, body in _bodies(client):
        for value in (0, -250.5, LIMIT, -LIMIT):
            resp = client.post(path, json={**body, "x": value, "y": value})
            assert resp.status_code in (200, 201), (path, value, resp.text)


def test_a_put_is_bounded_too(client):
    created = client.post("/whiteboard/objects", json={"kind": "text", "data": {"content": "hi"}}).json()
    resp = client.put(f"/whiteboard/objects/{created['id']}", json={"kind": "text", "data": {"content": "hi"}, "y": 1e308})
    assert resp.status_code == 422
    assert _named(resp) == ["y"], resp.text


def test_a_layer_number_is_bounded(client):
    resp = client.post("/whiteboard/objects", json={"kind": "text", "data": {"content": "hi"}, "z": 10**30})
    assert resp.status_code == 422
    assert _named(resp) == ["z"], resp.text


def test_a_map_node_position_is_bounded(client):
    board = client.post("/whiteboard/boards", json={"name": "Map"}).json()
    resp = client.post(
        f"/whiteboard/boards/{board['id']}/nodes",
        json={"text": "far", "x": 1e308, "y": 0},
    )
    assert resp.status_code == 422, resp.text
    assert _named(resp) == ["x"], resp.text


def test_an_old_row_out_of_range_is_clamped_when_the_board_loads(client):
    from tessellate.core import deps
    from tessellate.core.database import WhiteboardObject

    created = client.post("/whiteboard/objects", json={"kind": "text", "data": {"content": "far"}}).json()
    session = deps.get_db().session()
    try:
        row = session.get(WhiteboardObject, created["id"])
        row.x, row.y = 1e308, -1e308
        session.commit()
    finally:
        session.close()
    state = client.get("/whiteboard/").json()
    far = next(o for o in state["objects"] if o["id"] == created["id"])
    assert far["x"] == LIMIT and far["y"] == -LIMIT
