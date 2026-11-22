"""Named layers on a board (INBOX 797, canvasdepth; WHITEBOARD_PLAN section 6
and "canvasdepth, ranked" row 5). draw.io's layers: a named set of items that
shows, hides and locks together. Stored as `layers [{id, name, hidden,
locked}]` in the board's settings; an item names its layer in `data.layer`.
The browser half is `scratchpad/ui-sweeps/wbnamedlayers.js`."""

from __future__ import annotations

from tests._app_js import frontend_text
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WB = frontend_text("whiteboard.js")
LIB = (ROOT / "frontend" / "js" / "whiteboard-library.js").read_text(encoding="utf-8")


def _board(client):
    return client.post("/whiteboard/boards", json={"name": "Layered", "type": "board"}).json()


def test_layers_save_read_back_and_clean(ai_client):
    board = _board(ai_client)
    layers = [{"id": "l1", "name": "Background", "hidden": True, "locked": False}, {"id": "l2", "name": " Notes ", "locked": True}]
    out = ai_client.put(f"/whiteboard/boards/{board['id']}", json={"layers": layers})
    assert out.status_code == 200, out.text
    assert out.json()["layers"] == [{"id": "l1", "name": "Background", "hidden": True, "locked": False, "current": False},
                                    {"id": "l2", "name": "Notes", "hidden": False, "locked": True, "current": False}]
    state = ai_client.get("/whiteboard/", params={"board_id": board["id"]}).json()
    assert [layer["id"] for layer in state["layers"]] == ["l1", "l2"]
    #: A rename alone leaves the layers as they are.
    ai_client.put(f"/whiteboard/boards/{board['id']}", json={"title": "Renamed"})
    assert len(ai_client.get("/whiteboard/", params={"board_id": board["id"]}).json()["layers"]) == 2
    bad = ai_client.put(f"/whiteboard/boards/{board['id']}", json={"layers": [{"id": "has space", "name": "x"}]})
    assert bad.status_code == 422
    ai_client.put(f"/whiteboard/boards/{board['id']}", json={"layers": []})
    assert ai_client.get("/whiteboard/", params={"board_id": board["id"]}).json()["layers"] == []


def test_an_object_carries_its_layer(ai_client):
    board = _board(ai_client)
    made = ai_client.post("/whiteboard/objects", json={"kind": "text", "data": {"content": "Hi", "layer": "l1"}, "board_id": board["id"],
                                                      "x": 0, "y": 0, "width": 100, "height": 40}).json()
    assert made["data"]["layer"] == "l1"


def test_hidden_and_locked_read_the_layer():
    for name in ("wbItemHidden", "wbIsLocked"):
        start = WB.index(f"function {name}(")
        body = WB[start : WB.index("\n}\n", start)]
        assert "wbNamedLayerFlag(" in body, name
    assert "function wbRenderNamedLayers(" in LIB
    menu = LIB[LIB.index("function wbNamedLayerMenu(") :]
    assert "kebabMenu(" in menu[: menu.index("\n}\n")]


def test_the_state_schema_keeps_layers():
    src = (ROOT / "src" / "tessellate" / "api" / "wb_model.py").read_text(encoding="utf-8")
    assert "layers: list[dict] = []" in src
    assert json.dumps  # keeps the import honest
