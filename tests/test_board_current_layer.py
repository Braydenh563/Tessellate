"""The current layer (INBOX 797, canvasdepth2; WHITEBOARD_PLAN section 6 and
"canvasdepth, ranked" row 5's open half, draw.io's). A board's named layer
marked `current` is where every new item lands, set by the server on each
create (`_on_current_layer`), so the hand, paste, import and library paths
all agree. The browser half is `scratchpad/ui-sweeps/wbdepth2.js wbcurrentlayer`."""

from __future__ import annotations

from tests._app_js import frontend_text
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = (ROOT / "frontend" / "js" / "whiteboard-library.js").read_text(encoding="utf-8")
WB = frontend_text("whiteboard.js")


def _board(client, **layer):
    board = client.post("/whiteboard/boards", json={"name": "Layered", "type": "board"}).json()
    layers = [{"id": "a", "name": "A"}, {"id": "b", "name": "B", "current": True, **layer}, {"id": "c", "name": "C", "current": True}]
    out = client.put(f"/whiteboard/boards/{board['id']}", json={"layers": layers})
    assert out.status_code == 200, out.text
    return board["id"], out.json()["layers"]


def _text(client, board_id, **data):
    made = client.post("/whiteboard/objects", json={"kind": "text", "data": {"content": "x", **data}, "board_id": board_id, "x": 0, "y": 0, "width": 100, "height": 40})
    assert made.status_code in (200, 201), made.text
    return made.json()["data"].get("layer")


def test_one_current_layer_and_new_items_land_on_it(ai_client):
    board_id, layers = _board(ai_client)
    assert [layer["current"] for layer in layers] == [False, True, False]
    assert _text(ai_client, board_id) == "b"
    #: An item that names its layer, or says none on purpose, keeps it.
    assert _text(ai_client, board_id, layer="a") == "a"
    assert _text(ai_client, board_id, layer="") is None
    sketch = ai_client.post("/whiteboard/sketches", json={"data": json.dumps({"d": "M0 0 L1 1"}), "board_id": board_id}).json()
    assert json.loads(sketch["data"])["layer"] == "b"
    placed = ai_client.post(f"/whiteboard/boards/{board_id}/place", json={"builtin": "flowchart/decision", "x": 0, "y": 0}).json()
    rows = [o["data"] for o in placed["objects"]] + [json.loads(s["data"]) for s in placed["sketches"]]
    assert rows and all(row.get("layer") == "b" for row in rows)


def test_a_hidden_or_locked_current_layer_takes_nothing(ai_client):
    for flag in ("hidden", "locked"):
        board_id, _ = _board(ai_client, **{flag: True})
        assert _text(ai_client, board_id) is None, flag


def test_the_client_switch_and_the_undo_path():
    switch = LIB[LIB.index("function wbSetCurrentLayer(") :][:400]
    assert "current: x.id === id" in switch and "wbSaveNamedLayers(" in switch
    render = LIB[LIB.index("function wbRenderNamedLayers(") :]
    assert 'name.setAttribute("aria-pressed", String(Boolean(layer.current)));' in render
    assert "JSON.stringify(wbKeepOwnLayer(entry.kind, entry.payload))" in WB
    keep = LIB[LIB.index("function wbKeepOwnLayer(") :][:600]
    assert 'layer: ""' in keep
