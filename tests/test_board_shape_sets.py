"""The converted draw.io shape sets in the Library (INBOX 797, canvasdepth).

WHITEBOARD_PLAN "The draw.io programme", phases 1 and 2: the five sets in
`frontend/board-library/drawio/` (196 shapes) were on disk and never listed.
The API lists them as `shape_sets`, places them like any built-in, finds them
by search; a placed shape keeps its stencil ports, and `wbPortFractions`
reads them before guessing from the path. The browser half is
`scratchpad/ui-sweeps/wbshapesets.js`.
"""

from __future__ import annotations

from tests._app_js import frontend_text
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIB = (ROOT / "frontend" / "js" / "whiteboard-library.js").read_text(encoding="utf-8")
WB = frontend_text("whiteboard.js")


def _board(client):
    return client.post("/whiteboard/boards", json={"name": "Shapes", "type": "board"}).json()


def test_the_five_sets_are_listed_with_their_counts(ai_client):
    sets = ai_client.get("/board-library").json()["shape_sets"]
    got = {s["key"]: s["count"] for s in sets}
    assert got == {"drawio-basic": 30, "drawio-flowchart": 36, "drawio-arrows": 34, "drawio-bpmn": 39, "drawio-networks": 57}
    for s in sets:
        assert s["path"].startswith("drawio/") and s["path"].endswith(".json")
        assert "mxgraph" not in s["name"].lower()


def test_no_two_library_sections_share_a_name(ai_client):
    """bw-1111: the panel showed two "BPMN" and two near-identical cloud and network sections."""
    lib = ai_client.get("/board-library").json()
    names = [s["name"].lower() for s in lib["sets"]] + [s["name"].lower() for s in lib["shape_sets"]]
    assert len(names) == len(set(names)), sorted(n for n in names if names.count(n) > 1)
    by_key = {s["key"]: s["name"] for s in lib["shape_sets"]}
    assert by_key["drawio-bpmn"] == "BPMN, more"
    assert by_key["drawio-networks"] == "Cloud and network, more"


def test_a_draw_io_shape_places_and_keeps_its_ports(ai_client):
    board = _board(ai_client)
    out = ai_client.post(f"/whiteboard/boards/{board['id']}/place",
                         json={"builtin": "drawio-flowchart/decision", "x": 0, "y": 0, "ink": "#224466"})
    assert out.status_code == 201, out.text
    data = json.loads(out.json()["sketches"][0]["data"])
    assert data["library_ref"] == {"builtin": "drawio-flowchart/decision"}
    names = {p["name"] for p in data["ports"]}
    assert {"N", "S", "E", "W"} <= names


def test_search_finds_a_draw_io_shape(ai_client):
    found = ai_client.get("/board-library", params={"q": "router"}).json()["builtins"]
    assert any(b["key"].startswith("drawio-networks/") for b in found)


def _function(name: str) -> str:
    start = WB.index(f"function {name}(")
    return WB[start : WB.index("\n}\n", start) + 3]


def test_ports_from_the_shape_come_first():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    body = _function("wbPortFractions")
    assert "parsed.ports" in body
    script = (
        "const WB_FIXED_ANCHORS=[{x:0,y:0}]; const WB_FILLABLE_SHAPES=new Set(['custom']);"
        "const wbPortCache=new Map(); const wbSketchParsedData=(i)=>JSON.parse(i.data);"
        "function wbPortsForPath(){return [{x:9,y:9}];}"
        + body
        + "const item={id:1,data:JSON.stringify({d:'M 0 0 L 10 0 L 10 10 Z',shape:'custom',"
        "ports:[{x:0.5,y:0,name:'N'},{x:1,y:0.5,name:'E'},{x:'bad',y:0}]})};"
        "console.log(JSON.stringify(wbPortFractions('sketch', item)));"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    got = json.loads(out.stdout)
    assert got == [{"x": 0.5, "y": 0, "name": "N"}, {"x": 1, "y": 0.5, "name": "E"}]


def test_the_panel_lists_the_sets_closed_and_fetches_on_open_or_search():
    render = LIB[LIB.index("function wbRenderLibrary(") :]
    render = render[: render.index("\n}\n")]
    assert "shape_sets" in render
    assert re.search(r"wbLoadShapeSets\(", LIB)
    loader = LIB[LIB.index("async function wbLoadShapeSets(") :]
    assert "board-library/${s.path}" in loader[: loader.index("\n}\n")]
