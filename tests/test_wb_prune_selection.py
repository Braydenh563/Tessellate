"""A board's selection never outlives its items (wbdog-1026: Export > Selection threw after an undone paste)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _run(state: dict, lone, multi: list[str]):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    start = WB.index("function wbPruneSelection(")
    fn = WB[start : WB.index("\n}\n", start) + 3]
    script = (
        "const WB_LIST_BY_KIND = { sketch: 'sketches', node: 'nodes', object: 'objects' };"
        f"const wbState = {json.dumps(state)}; let wbSelectedItem = {json.dumps(lone)};"
        f"const wbMultiSelection = new Set({json.dumps(multi)}); let calls = 0;"
        "const wbFindItem = (k, id) => (wbState[WB_LIST_BY_KIND[k]] || []).find((i) => i.id === id) || null;"
        "const wbApplySelectionHighlight = () => calls++, wbSyncMapToolState = () => {}, wbUpdateSelectionBar = () => {};"
        + fn
        + "wbPruneSelection(); console.log(JSON.stringify({ lone: wbSelectedItem, multi: [...wbMultiSelection], calls }));"
    )
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)


def test_a_lone_selection_whose_item_is_gone_is_dropped():
    out = _run({"objects": [{"id": 1}]}, {"kind": "object", "id": 2}, [])
    assert out["lone"] is None and out["calls"] == 1


def test_a_multi_selection_keeps_only_what_is_there():
    out = _run({"objects": [{"id": 1}], "sketches": [{"id": 5}]}, None, ["object:1", "object:9", "sketch:5"])
    assert sorted(out["multi"]) == ["object:1", "sketch:5"] and out["calls"] == 1


def test_a_valid_selection_is_left_alone_and_costs_no_repaint():
    out = _run({"objects": [{"id": 1}]}, {"kind": "object", "id": 1}, ["object:1"])
    assert out["lone"] == {"kind": "object", "id": 1} and out["calls"] == 0


def test_every_render_prunes_first():
    start = WB.index("function renderWhiteboard() {")
    assert WB[start : start + 80].split("\n")[1].strip() == "wbPruneSelection();"
