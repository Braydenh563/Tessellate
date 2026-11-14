"""Repeat last (L-whiteboard-6): the board keeps the last move, turn or resize as a delta and Ctrl+Alt+Y does it
again to the current selection. The module runs in node against a stand-in for the board's functions."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests import _js_scope
from tests._app_js import frontend_text, script_file_text

SCRIPT = """
const log = { nudged: [], turned: [], sized: [], toasts: [], said: [], rendered: 0 };
const view = { classList: { contains: () => false } };
const document = { getElementById: (id) => (id === "library-view-whiteboard" ? view : { id }), activeElement: null };
const handlers = {};
const window = { addEventListener: (t, fn, cap) => (handlers[t] = { fn, cap }) };
const d3 = {};
const toast = (t) => log.toasts.push(t);
const wbAnnounce = (t) => log.said.push(t);
const wbIsMap = () => false;
const wbSelectedKeys = () => new Set(%(sel)s);
const wbNudgeSelection = (dx, dy) => log.nudged.push([dx, dy]);
const wbTurnSelection = async (deg) => log.turned.push(deg);
const wbFmtEntries = () => [{ kind: "object", item: {}, bbox: { minX: 0, minY: 0, maxX: 200, maxY: 100 } }];
const wbIsLocked = () => false;
const wbFmtBox = (entries) => entries[0].bbox;
const wbFmtSizeAxis = async (axis, target) => log.sized.push([axis, target]);
const wbRecordGesture = async (run) => { await run(); };
const wbScheduleRender = () => { log.rendered += 1; };
const wbFmtState = {};
%(src)s
const k = wbFmtState.keys;
const ev = (o) => ({ ctrlKey: true, metaKey: false, altKey: true, shiftKey: false, key: "y", target: { closest: () => null },
  preventDefault() { this.stopped = 1; }, stopImmediatePropagation() {}, ...o });
(async () => {
  for (const step of %(steps)s) {
    if (step.record) k.record(step.record);
    if (step.press) { handlers.keydown.fn(ev(step.press)); await new Promise((r) => setTimeout(r, 5)); }
  }
  console.log(JSON.stringify({ ...log, can: k.canRepeat() }));
})();
"""


def _run(steps: list, sel: list | None = None) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = SCRIPT % {"sel": json.dumps(sel if sel is not None else ["node:1"]), "steps": json.dumps(steps), "src": frontend_text("whiteboard-keys.js")}
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


PRESS = {"press": {}}


def test_repeat_replays_the_last_move_on_the_selection():
    got = _run([{"record": {"kind": "move", "dx": 12, "dy": -4}}, PRESS, PRESS])
    assert got["nudged"] == [[12, -4], [12, -4]]


def test_the_last_delta_wins_and_a_zero_one_is_ignored():
    got = _run([{"record": {"kind": "move", "dx": 5, "dy": 5}}, {"record": {"kind": "turn", "deg": 90}},
                {"record": {"kind": "move", "dx": 0, "dy": 0}}, PRESS])
    assert got["turned"] == [90] and got["nudged"] == []


def test_scale_repeats_as_a_factor_of_the_current_size():
    got = _run([{"record": {"kind": "scale", "axis": "w", "factor": 1.5}}, PRESS])
    assert got["sized"] == [["w", 300]]


def test_nothing_recorded_or_nothing_selected_says_so():
    assert "Move, turn or resize something first, then repeat it." in _run([PRESS])["toasts"]
    got = _run([{"record": {"kind": "turn", "deg": 15}}, PRESS], sel=[])
    assert got["turned"] == [] and "Select something to repeat the last change on." in got["toasts"]


def test_a_repeat_does_not_record_itself():
    got = _run([{"record": {"kind": "move", "dx": 3, "dy": 3}}, PRESS])
    assert got["can"] is True and got["nudged"] == [[3, 3]]


def test_the_chord_is_free_listed_and_every_end_of_a_gesture_records():
    cmds = script_file_text("whiteboard-commands.js")
    row = cmds[cmds.index('id: "repeat-last"') :].split("\n", 1)[0]
    assert 'keys: "Ctrl+Alt+Y"' in row and "wbFmtState.keys.repeat()" in row
    assert script_file_text("settings-wiring.js").count("Ctrl+Alt+Y") == 0
    assert cmds.count("Ctrl+Alt+Y") == 1
    js = frontend_text("whiteboard.js") + script_file_text("whiteboard-format.js")
    for needle in ('keys?.record({ kind: "move", dx, dy })', "keys?.recordDrag(primary)", 'record({ kind: "turn", deg: degrees })', 'record({ kind: "scale"'):
        assert needle in js, needle
    assert js.count('record({ kind: "turn", deg: (d.rotation') == 2
    src = script_file_text("whiteboard-keys.js")
    assert _js_scope.is_wrapped(src) and _js_scope.global_names(src) == set()


def test_the_drawn_shapes_rotate_grip_records_its_turn_when_the_drag_ends():
    #: L-whiteboard-18: the grip bakes the turn into the path, so the delta is what the drag turned by (rotateLiveAngle).
    js = frontend_text("whiteboard.js")
    end = js.split("let rotateOriginalD = null")[1].split(".on(\"end\"")[1].split("shapeGrip.append(\"title\")")[0]
    assert end.count("keys?.record({ kind: \"turn\", deg: rotateLiveAngle })") == 1
    assert end.index("keys?.record") > end.index("wbSaveSketchProps") and end.index("keys?.record") < end.index("wbScheduleRender()")
