"""A boundary round a lasso'd set of topics (MINDMAP_PLAN 12.2 item 1, decision 19 extended)."""

from tests._app_js import frontend_text
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.api.wb_model import WhiteboardObjectData

ROOT = Path(__file__).resolve().parents[1]
MORE = (ROOT / "frontend" / "js" / "whiteboard-map-more.js").read_text(encoding="utf-8")
MAP = frontend_text("whiteboard-map.js")
WB = frontend_text("whiteboard.js")
CMD = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = MORE.index(f"function {name}(")
    return MORE[start : MORE.index("\n  }\n", start) + 5]


def test_the_model_keeps_a_set_of_topic_ids_and_refuses_junk() -> None:
    data = WhiteboardObjectData(boundary="dashed", boundary_set=[3, 5, 8])
    assert data.model_dump(exclude_none=True)["boundary_set"] == [3, 5, 8]
    with pytest.raises(ValueError):
        WhiteboardObjectData(boundary_set=["a"])
    with pytest.raises(ValueError):
        WhiteboardObjectData(boundary_set=list(range(300)))


def test_the_box_is_the_union_of_the_showing_members_only() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    code = (
        "const wbMapNodeSize = () => ({w: 100, h: 40});"
        + _function("wbBoundarySetBox")
        + "const index = {byId: new Map([[1, {id: 1, x: 0, y: 0}], [2, {id: 2, x: 300, y: 200}], [3, {id: 3, x: 900, y: 900}]])};"
        + "console.log(JSON.stringify([wbBoundarySetBox(index, new Set(), [1, 2, 99]), wbBoundarySetBox(index, new Set([2]), [1, 2]),"
        + " wbBoundarySetBox(index, new Set([1, 2]), [1, 2])]));"
    )
    out = json.loads(subprocess.run([node, "-e", code], capture_output=True, text=True, check=True).stdout)
    assert out[0] == {"minX": 0, "minY": 0, "maxX": 400, "maxY": 240}
    assert out[1] == {"minX": 0, "minY": 0, "maxX": 100, "maxY": 40}
    assert out[2] is None


def test_the_draw_is_one_undo_step_and_removal_clears_the_set() -> None:
    assert "wbMapLazy.setBox(" in MAP and "boundary_set" in MAP
    draw = MORE.split("async function wbBoundaryDraw(")[1].split("\n  }\n")[0]
    assert "wbMapSetStructure(" in draw and "boundary_set" in draw
    assert "boundary: null, boundary_label: null, boundary_set: null" in WB
    assert 'id: "boundary-set"' in CMD and "wbMapLazy.boundaryDraw()" in CMD
