"""INBOX 716: resetting a mind map topic's size.

The owner double-clicked a hand-resized topic's grip and the line did not
follow, then moved the node and the manual size came back. The server log was
`[HTTP 422] PUT /whiteboard/objects/57: Check the height and try again.`
followed by `object 57 is stale: reloading the board`: the reset wrote
`height: null`, the schema (`WhiteboardObjectBase.height`) has no null, the
save was refused, the board reloaded from the server, and the server still had
the manual size.

Two halves, because the suite cannot open a board: the schema's side is
pinned here with real requests, and the frontend's side is pinned as text.
"""

from __future__ import annotations

from tests._app_js import frontend_text
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WB = frontend_text("whiteboard.js")


def _topic(client):
    board = client.post("/whiteboard/boards", json={"name": "Reset", "type": "map"}).json()
    root = client.post(
        f"/whiteboard/boards/{board['id']}/nodes",
        json={"kind": "topic", "parent_id": None, "text": "Root"},
    ).json()
    return board, root


def _put(client, board, node, **fields):
    body = {
        "kind": node["kind"],
        "board_id": board["id"],
        "data": {**node["data"], "sized": False},
        "x": node["x"],
        "y": node["y"],
        "z": node["z"],
        "width": node["width"],
        "height": node["height"],
    }
    body.update(fields)
    return client.put(f"/whiteboard/objects/{node['id']}", json=body)


def test_a_reset_with_a_real_height_is_stored(client):
    board, node = _topic(client)
    # Hand-sized first, then reset: the unsized flag and the natural height
    # are what the reset sends.
    big = _put(client, board, node, height=164, width=290, data={**node["data"], "sized": True})
    assert big.status_code == 200, big.text
    reset = _put(client, board, node, height=44, width=290)
    assert reset.status_code == 200, reset.text
    assert reset.json()["height"] == 44
    assert reset.json()["data"].get("sized") in (False, None)


def test_the_smallest_height_the_server_accepts_is_twenty(client):
    board, node = _topic(client)
    assert _put(client, board, node, height=20).status_code == 200
    assert _put(client, board, node, height=19).status_code == 422


def test_a_null_height_is_refused_so_a_reset_must_never_send_one(client):
    """The reset used to send `height: null`. The refusal is the schema's
    contract (the column is not nullable), so it is pinned: the fix is on the
    sending side, never a server that quietly invents a height."""
    board, node = _topic(client)
    refused = _put(client, board, node, height=None)
    assert refused.status_code == 422
    assert "height" in refused.json()["detail"]


@pytest.mark.parametrize("value", [0, "auto", -1])
def test_other_stand_ins_for_no_height_are_refused_too(client, value):
    board, node = _topic(client)
    assert _put(client, board, node, height=value).status_code == 422


def _fit_body() -> str:
    start = WB.index("async function wbFitToText(el)")
    return WB[start : WB.index("//: **The card's own `scrollHeight`", start)]


def test_the_reset_sends_the_natural_height_never_null() -> None:
    body = _fit_body()
    assert "item.height = null" not in body
    # Measured off the node once its floor is gone, floored at what the server
    # accepts, so the PUT cannot be a 422.
    assert 'el.style.removeProperty("min-height");' in body
    assert "WB_MAP_HEIGHT_FLOOR" in body
    assert "el.offsetHeight" in body


def test_the_floor_the_reset_uses_is_the_servers_own() -> None:
    assert "const WB_MAP_HEIGHT_FLOOR = 20;" in frontend_text("whiteboard-map.js")


def test_the_reset_redraws_the_branch_line_and_can_be_undone() -> None:
    body = _fit_body()
    #: The line follows the box the same frame, before the render.
    assert "wbForgetMapNodeSize(item.id);" in body
    assert "wbUpdateMapEdges(wbMapEdgesFor(item.id));" in body
    #: One Undo step puts the manual size back.
    assert "wbPushUndo({ action: \"move\", kind: \"object\", id: item.id, before });" in body
