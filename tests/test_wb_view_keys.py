"""F2, draw.io's keyboard rows: Home goes back to the top left of the board, Shift+Home resets the view to 100%
there, and Shift+Delete clears the labels of the selected shapes and connectors but keeps the things.

The module runs in node against a stand-in for the page and the board's functions it calls; the command rows and
the bundle are read from the source."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests import _js_scope
from tests._app_js import frontend_text, script_file_text

SCRIPT = """
const log = { zoom: [], saved: [], said: [], toasts: [], gestures: 0, rendered: 0 };
const view = { classList: { contains: (c) => c === "hidden" && %(hidden)s } };
const document = {
  getElementById: (id) => (id === "library-view-whiteboard" ? view : id === "whiteboard-container" ? { id } : null),
  activeElement: %(active)s,
};
const handlers = {};
const window = { addEventListener: (t, fn, cap) => (handlers[t] = { fn, cap }) };
const d3 = {
  zoomTransform: () => ({ k: %(k)s }),
  zoomIdentity: { translate(x, y) { return { scale: (k) => ({ x, y, k }) }; } },
  select: () => ({ transition: () => ({ duration: () => ({ call: (f, t) => log.zoom.push(t) }) }) }),
};
const wbZoom = { transform: "t" };
const wbContentBounds = () => (%(bounds)s);
const wbFreeArea = () => ({ left: 10, top: 20, right: 900, bottom: 700 });
const wbAnnounce = (t) => log.said.push(t);
const toast = (t) => log.toasts.push(t);
const wbIsMap = () => false;
const wbState = { sketches: %(sketches)s };
const wbSelectedKeys = () => new Set(%(keys)s);
const wbSketchData = (s) => JSON.parse(s.data);
const wbItemHidden = () => false;
const wbIsLocked = (kind, s) => Boolean(JSON.parse(s.data).locked);
//: The writes moved from one save per connector to a merge (wbSketchSetProps) and one wbSaveMany (test_board_selection_batches); the patch each gets is read here as before.
const wbSketchSetProps = (s, patch) => { log.saved.push([s.id, Object.keys(patch).sort()]); return true; };
const wbSaveMany = async () => true;
const wbRecordGesture = async (run) => { log.gestures += 1; await run(); };
const wbScheduleRender = () => { log.rendered += 1; };
const WB_COMMAND_BY_ID = new Map();
const wbFmtState = {};
%(src)s
const inList = %(in_list)s;
const e = { ctrlKey: false, metaKey: false, altKey: false, shiftKey: false, ...%(event)s,
  target: { closest: () => inList }, preventDefault() { this.stopped = 1; }, stopImmediatePropagation() { this.halted = 1; } };
(async () => {
  handlers.keydown.fn(e);
  await new Promise((r) => setTimeout(r, 5));
  console.log(JSON.stringify({ ...log, handled: Boolean(e.stopped && e.halted), capture: handlers.keydown.cap }));
})();
"""


def _run(event: dict, *, bounds: dict | None = None, k: float = 1.7, sketches: list | None = None, keys: list | None = None,
         hidden: bool = False, active: str = "null", in_list: bool = False) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = SCRIPT % {
        "hidden": json.dumps(hidden), "active": active, "k": json.dumps(k), "bounds": json.dumps(bounds),
        "sketches": json.dumps(sketches or []), "keys": json.dumps(keys or []), "event": json.dumps(event),
        "in_list": json.dumps(in_list), "src": frontend_text("whiteboard-keys.js"),
    }
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


BOX = {"minX": 100, "minY": 60, "maxX": 500, "maxY": 400}


def _sk(i, **data):
    return {"id": i, "data": json.dumps(data)}


def test_home_keeps_the_zoom_and_puts_the_top_left_of_the_drawing_in_view():
    got = _run({"key": "Home"}, bounds=BOX)
    assert got["handled"] and got["capture"] is True
    # free left 10 + 48 padding - 1.7 * 100, free top 20 + 48 - 1.7 * 60
    assert got["zoom"] == [{"x": pytest.approx(-112), "y": pytest.approx(-34), "k": 1.7}]


def test_shift_home_resets_to_one_hundred_percent_at_the_same_corner():
    got = _run({"key": "Home", "shiftKey": True}, bounds=BOX)
    assert got["zoom"] == [{"x": -42, "y": 8, "k": 1}]
    assert got["said"] == ["View reset to 100%."]


def test_an_empty_board_goes_to_the_origin():
    got = _run({"key": "Home", "shiftKey": True}, bounds=None)
    assert got["zoom"] == [{"x": 58, "y": 68, "k": 1}]


def test_home_in_a_field_a_list_or_a_hidden_board_is_left_alone():
    assert _run({"key": "Home"}, bounds=BOX, active='{ tagName: "INPUT", offsetParent: {} }')["handled"] is False
    assert _run({"key": "Home"}, bounds=BOX, hidden=True)["handled"] is False
    assert _run({"key": "Home", "ctrlKey": True}, bounds=BOX)["handled"] is False
    assert _run({"key": "Home"}, bounds=BOX, in_list=True)["handled"] is False


def test_shift_delete_clears_labels_in_one_step_and_keeps_the_items():
    sketches = [_sk(1, label="Box", d="M0 0"), _sk(2, type="link-straight", label="yes"), _sk(3, d="M1 1"), _sk(4, label="locked", locked=True, d="M2")]
    got = _run({"key": "Delete", "shiftKey": True}, sketches=sketches, keys=["sketch:1", "sketch:2", "sketch:3", "sketch:4", "node:9"])
    assert got["handled"] and got["gestures"] == 1 and got["rendered"] == 1
    assert got["saved"] == [[1, ["label", "label2"]], [2, ["label", "label2"]]]
    assert "Cleared the label on 2 items." in got["toasts"]


def test_shift_delete_with_nothing_to_clear_says_so_and_changes_nothing():
    got = _run({"key": "Delete", "shiftKey": True}, sketches=[_sk(3, d="M1 1")], keys=["sketch:3"])
    assert got["handled"] and got["saved"] == [] and got["gestures"] == 0
    assert got["toasts"] == ["The selection has no labels to clear."]


def test_a_plain_delete_is_not_this_modules():
    assert _run({"key": "Delete"}, sketches=[_sk(1, label="x", d="M")], keys=["sketch:1"])["handled"] is False


def test_the_rows_the_help_and_the_bundle_agree():
    commands = script_file_text("whiteboard-commands.js")
    for ident, keys in (("view-home", '"Home"'), ("view-reset", '"Shift+Home"'), ("clear-labels", '"Shift+Del"')):
        row = commands[commands.index(f'id: "{ident}"') :].split("\n", 1)[0]
        assert f"keys: {keys}" in row and "wbFmtState.keys." in row
    assert "/js/whiteboard-keys.js" in script_file_text("lazy-entries.js")
    src = script_file_text("whiteboard-keys.js")
    assert _js_scope.is_wrapped(src) and _js_scope.global_names(src) == set()
