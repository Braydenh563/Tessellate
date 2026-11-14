"""F2, draw.io's layer rows that were still open: a layer's menu brings the whole layer to the front or sends it to
the back (its items keep their order among themselves) and duplicates it onto a layer of its own.

The module runs in node against a stand-in for the board's lists; the board's own stacking functions are cut out of
whiteboard.js, so the order it sets is the order the board paints."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests import _js_scope
from tests._app_js import frontend_text, script_file_text

ROOT = Path(__file__).resolve().parents[1]
WB = frontend_text("whiteboard.js")


def _function(name: str) -> str:
    start = WB.index(f"function {name}(")
    return WB[start : WB.index("\n}\n", start) + 3]


SCRIPT = """
const WB_KIND_INFO = { sketch: { payload: (i) => ({ z: i.z }) }, object: { payload: (i) => ({ z: i.z }) }, node: { payload: (i) => ({ z: i.z }) } };
const wbState = %(state)s;
const WB_STACK_KIND_RANK = { sketch: 0, node: 1, object: 2 };
%(fns)s
const wbNamedLayerItems = (id) => [["sketch", "sketches"], ["object", "objects"]].flatMap(([kind, list]) => (wbState[list] || []).filter((i) => i.layer === id).map((i) => [kind, i]));
const log = { toasts: [], said: [], saved: [], undo: [] };
const toast = (t) => log.toasts.push(t);
const wbAnnounce = (t) => log.said.push(t);
const wbCommitMoves = async (rows, entries) => { log.saved = rows.map((r) => r.kind + ":" + r.item.id); log.undo = entries.length; };
const wbFmtState = {};
%(src)s
wbFmtState.layersMore.sendLayer({ id: "L", name: "Walls" }, %(front)s).then((n) => {
  const order = wbStackOrder().map((e) => e.key);
  console.log(JSON.stringify({ n, order, z: Object.fromEntries(wbStackOrder().map((e) => [e.key, e.item.z])), log }));
});
"""


def _run(state: dict, *, front: bool) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    fns = "".join(_function(n) for n in ("wbStackBand", "wbStackCompare", "wbStackOrder", "wbZOrderPeers", "wbSetZOrder", "wbWriteZ"))
    script = SCRIPT % {"state": json.dumps(state), "fns": fns, "src": frontend_text("whiteboard-layers-more.js"), "front": json.dumps(front)}
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


STATE = {
    "sketches": [
        {"id": 1, "z": 1, "layer": "L"},
        {"id": 2, "z": 2},
        {"id": 3, "z": 3, "layer": "L"},
        {"id": 4, "z": 4},
    ],
    "objects": [{"id": 10, "z": 5, "kind": "text"}, {"id": 11, "z": 2, "kind": "frame", "layer": "L"}],
    "nodes": [],
}


def test_bring_the_layer_to_the_front_keeps_its_own_order():
    got = _run(STATE, front=True)
    assert got["n"] == 3
    #: The two shapes were 1 under 3 and still are; both are over the text (5) now. The frame stays among frames.
    order = [k for k in got["order"] if k in ("sketch:1", "sketch:3", "sketch:2", "sketch:4", "object:10")]
    assert order == ["sketch:2", "sketch:4", "object:10", "sketch:1", "sketch:3"]
    assert got["z"]["sketch:1"] < got["z"]["sketch:3"] and got["z"]["sketch:1"] > 5
    assert got["log"]["undo"] == 3 and "Walls brought to the front." in got["log"]["toasts"]


def test_send_the_layer_to_the_back_keeps_its_own_order():
    got = _run(STATE, front=False)
    order = [k for k in got["order"] if k.startswith("sketch") or k == "object:10"]
    assert order == ["sketch:1", "sketch:3", "sketch:2", "sketch:4", "object:10"]
    assert got["z"]["sketch:1"] < got["z"]["sketch:3"] < 0
    assert "Walls sent to the back." in got["log"]["toasts"]


def test_an_empty_layer_says_so_and_changes_nothing():
    state = {"sketches": [{"id": 2, "z": 2}], "objects": [], "nodes": []}
    got = _run(state, front=True)
    assert got["n"] == 0 and got["log"]["toasts"] == ["Walls has nothing on it."] and got["log"]["saved"] == []


def test_the_layer_menu_the_bundle_and_the_help_agree():
    library = script_file_text("whiteboard-library.js")
    menu = library[library.index("function wbNamedLayerMenu(") :]
    menu = menu[: menu.index("\n}\n")]
    assert "...wbFmtState.layersMore.rows(layer)," in menu
    src = script_file_text("whiteboard-layers-more.js")
    for words in ("Bring the layer to the front", "Send the layer to the back", "Duplicate the layer"):
        assert words in src
    assert "/js/whiteboard-layers-more.js" in script_file_text("lazy-entries.js")
    assert _js_scope.is_wrapped(src) and _js_scope.global_names(src) == set()
    #: Duplicate is one Undo step: the copy, the new layer and the move are bundled.
    assert 'action: "batch"' in src and "wbUndoStack.splice(mark)" in src
