"""F2, draw.io's stencil ports and custom ports with an offset: a shape's own ports (`data.ports`) may carry a pixel offset
(`dx`, `dy`), a flag holding the port on the outline (`perimeter`) and a name that shows beside its dot while it is lit.

The board's own functions are cut out of whiteboard.js and run in node against small stand-ins."""

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


def _node(script: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


#: A square outline, 100 wide, drawn from its top-left corner round clockwise, as the page's measuring path reports it.
SQUARE = (
    "const wbFmtState = {}; const onSurface = () => {};"
    "const wbLinkMidpoint = (d) => (d ? { x: 0, y: 0 } : null);"
    "const wbLinkMeasurePath = { getTotalLength: () => 400, getPointAtLength: (n) => {"
    "  if (n <= 100) return { x: n, y: 0 }; if (n <= 200) return { x: 100, y: n - 100 };"
    "  if (n <= 300) return { x: 300 - n, y: 100 }; return { x: 0, y: 400 - n }; } };"
)


def _module(body: str):
    return _node(SQUARE + _function("wbPathBBox") + frontend_text("whiteboard-draw-more.js") + "\n" + body)


def test_a_perimeter_port_is_held_on_the_outline_and_the_rest_of_it_is_kept():
    got = _module(
        "const m = wbFmtState.drawMore; const d = 'M 0 0 L 100 0 L 100 100 L 0 100 Z';"
        "console.log(JSON.stringify([m.snapToOutline({ x: 0.5, y: -0.3, name: 'N' }, d), m.snapToOutline({ x: 1.4, y: 0.5 }, d), m.snapToOutline({ x: 0.25, y: 0.5 }, d)]));"
    )
    top, right, inside = got
    assert top["x"] == 0.5 and top["y"] == 0 and top["name"] == "N"
    assert right["x"] == 1 and right["y"] == 0.5
    #: A point inside goes to the nearest side, here the left one (25 away against 75 from the right).
    assert inside["x"] == 0 and inside["y"] == 0.5


def test_a_shape_without_a_drawn_outline_keeps_the_port_as_it_was():
    got = _module(
        "const m = wbFmtState.drawMore; console.log(JSON.stringify(m.snapToOutline({ x: 0.5, y: -0.3 }, '')));"
    )
    assert got == {"x": 0.5, "y": -0.3}


def _fractions(ports, snap="(q, d) => ({ ...q, x: 0.9 })"):
    return _node(
        "const WB_FIXED_ANCHORS = [{ x: 0, y: 0 }]; const WB_FILLABLE_SHAPES = new Set(['custom']);"
        "const wbPortCache = new Map(); const wbSketchParsedData = (i) => JSON.parse(i.data);"
        f"const wbFmtState = {{ drawMore: {{ snapToOutline: {snap} }} }}; function wbPortsForPath() {{ return [{{ x: 9, y: 9 }}]; }}"
        + _function("wbPortFractions")
        + f"const item = {{ id: 1, data: JSON.stringify({{ d: 'M 0 0 L 10 0 L 10 10 Z', shape: 'custom', ports: {json.dumps(ports)} }}) }};"
        "console.log(JSON.stringify([wbPortFractions('sketch', item), wbPortFractions('sketch', item)]));"
    )


def test_only_the_flagged_ports_of_a_shape_are_snapped():
    first, again = _fractions([{"x": 0.5, "y": 0, "name": "N"}, {"x": 1.2, "y": 0.5, "name": "E", "perimeter": True}])
    assert first == [{"x": 0.5, "y": 0, "name": "N"}, {"x": 0.9, "y": 0.5, "name": "E", "perimeter": True}]
    assert again == first


def test_ports_with_no_flag_never_touch_the_outline():
    first, _ = _fractions([{"x": 0.5, "y": 0}], snap="() => { throw new Error('snapped'); }")
    assert first == [{"x": 0.5, "y": 0}]


def test_an_offset_moves_the_port_in_pixels_and_turns_with_the_item():
    got = _node(
        "const wbItemBBox = () => ({ minX: 0, minY: 0, maxX: 100, maxY: 50 }); let rotation = 0;"
        "const wbItemRotation = () => rotation; const wbBoxCenter = (b) => ({ x: (b.minX + b.maxX) / 2, y: (b.minY + b.maxY) / 2 });"
        "const wbPortFractions = () => [{ x: 1, y: 0.5, dx: 10, dy: -5 }, { x: 0, y: 0 }, { x: 0.5, y: 0.5, dx: 'x' }];"
        + _function("wbRotatePoint") + _function("wbAnchorPositions") + _function("wbAnchorPoint")
        + "const flat = wbAnchorPositions('sketch', {}).map((p) => [p.x, p.y]); const point = wbAnchorPoint('sketch', {}, { x: 1, y: 0.5, dx: 10, dy: -5 });"
        "rotation = 90; const turned = wbAnchorPoint('sketch', {}, { x: 1, y: 0.5, dx: 10, dy: 0 });"
        "console.log(JSON.stringify({ flat, point, turned }));"
    )
    #: Right-middle of a 100 by 50 box is (100, 25); the offset adds (10, -5). A bad offset is none.
    assert got["flat"] == [[110, 20], [0, 0], [50, 25]]
    assert got["point"] == {"x": 110, "y": 20}
    #: Turned a quarter about the centre (50, 25): the point (110, 25) lies 60 to the right, so it ends 60 below.
    assert round(got["turned"]["x"]) == 50 and round(got["turned"]["y"]) == 85


def test_a_named_port_says_so_on_its_dot_and_beside_it_when_lit():
    hints = _function("wbShowAnchorHints")
    assert "if (a.name) {" in hints and "title.textContent = a.name;" in hints
    assert "if (near && a.name) wbFmtState.drawMore?.nameBeside(hints, a.name, x, y);" in hints
    got = _node(
        "const wbFmtState = {}; const onSurface = () => {};"
        "const d3 = { zoomTransform: () => ({ k: 2 }) };"
        "const document = { getElementById: () => ({}), createElementNS: () => ({ attrs: {}, setAttribute(k, v) { this.attrs[k] = v; } }) };"
        + frontend_text("whiteboard-draw-more.js")
        + "\nconst layer = { kids: [], appendChild(c) { this.kids.push(c); } }; wbFmtState.drawMore.nameBeside(layer, 'Out', 100, 50);"
        "console.log(JSON.stringify(layer.kids.map((k) => [k.attrs.class, k.attrs.x, k.attrs.y, k.attrs['font-size'], k.textContent])));"
    )
    #: At zoom 2 the label is half a board unit per screen pixel: 12px of text is 6 units, and it sits 4.5 up and across.
    assert got == [["wb-port-name", "104.5", "45.5", "6", "Out"]]


def test_the_module_is_still_one_wrapped_file_with_no_globals():
    src = script_file_text("whiteboard-draw-more.js")
    assert _js_scope.is_wrapped(src) and _js_scope.global_names(src) == set()


#: The editor's stand-ins: a container and document that keep their listeners, one square shape, and the board calls it makes.
EDITOR = (
    "const calls = []; const listeners = {}; const toast = () => {};"
    "const wbAnnounce = (t) => calls.push(['say', t]); const wbClearAnchorHints = () => calls.push(['clear']);"
    "const wbShowAnchorHints = (k, i, n) => calls.push(['hints', n]); const wbScheduleRender = () => {};"
    "let item = { id: 7 }; let parsed = { d: 'M 0 0 L 100 0 L 100 100 L 0 100 Z' }; let fractions = [{ x: 0, y: 0 }, { x: 1, y: 1 }];"
    "const wbSwapTarget = () => (item ? { item, parsed } : null);"
    "const wbPortFractions = () => fractions; const wbNearestAnchor = () => null;"
    "const wbAnchorPositions = () => fractions.map((q) => ({ ...q, x: q.x * 100, y: q.y * 100 }));"
    "const wbClientToBoard = (x, y) => [x, y]; const wbRecordGesture = async (f) => f();"
    "const wbSaveSketchProps = async (i, props) => { calls.push(['save', props.ports === undefined ? null : props.ports]); };"
    "const d3 = { zoomTransform: () => ({ k: 1 }) };"
    "const container = { addEventListener: (n, f) => { listeners[n] = f; } };"
    "const document = { getElementById: () => container, addEventListener: (n, f) => { listeners['doc-' + n] = f; } };"
    "const wbFmtState = {}; const onSurface = (s, f) => f();"
    "const press = (x, y) => { let stopped = false; listeners.pointerdown({ button: 0, clientX: x, clientY: y, preventDefault() {}, stopPropagation() { stopped = true; } }); return stopped; };"
)


def _editor(body: str):
    return _node(
        EDITOR
        + _function("wbPathBBox")
        + "const wbLinkMidpoint = (d) => (d ? { x: 0, y: 0 } : null);"
        "const wbLinkMeasurePath = { getTotalLength: () => 400, getPointAtLength: (n) => {"
        "  if (n <= 100) return { x: n, y: 0 }; if (n <= 200) return { x: 100, y: n - 100 };"
        "  if (n <= 300) return { x: 300 - n, y: 100 }; return { x: 0, y: 400 - n }; } };"
        + frontend_text("whiteboard-draw-more.js")
        + "\nconst m = wbFmtState.drawMore; const tick = () => new Promise((r) => setTimeout(r, 5));\n"
        + body
    )


def test_a_press_before_the_editor_is_on_does_nothing():
    got = _editor("(async () => { const stopped = press(50, 0); await tick(); console.log(JSON.stringify({ stopped, calls })); })();")
    assert got == {"stopped": False, "calls": []}


def test_pressing_the_outline_adds_a_point_there_keeping_the_ones_it_has():
    got = _editor(
        "m.editPorts(); calls.length = 0;"
        "(async () => { const stopped = press(30, 2); await tick(); console.log(JSON.stringify({ stopped, calls })); })();"
    )
    assert got["stopped"] is True
    saved = [c for c in got["calls"] if c[0] == "save"]
    assert saved == [["save", [{"x": 0, "y": 0}, {"x": 1, "y": 1}, {"x": 0.3, "y": 0}]]]


def test_pressing_a_point_takes_it_out_and_the_last_one_restores_the_standard_points():
    got = _editor(
        "m.editPorts(); calls.length = 0; fractions = [{ x: 1, y: 1 }];"
        "(async () => { press(99, 99); await tick(); console.log(JSON.stringify(calls.filter((c) => c[0] === 'save'))); })();"
    )
    #: No `ports` at all is how the shape asks for its standard points again.
    assert got == [["save", None]]


def test_pressing_away_from_the_shape_ends_the_editor_and_lets_the_press_through():
    got = _editor(
        "m.editPorts(); calls.length = 0;"
        "(async () => { const stopped = press(50, 50); await tick(); console.log(JSON.stringify({ stopped, calls })); })();"
    )
    assert got["stopped"] is False
    assert [c[0] for c in got["calls"]] == ["clear", "say"]


def test_the_editor_toggles_and_needs_a_shape():
    got = _editor(
        "m.editPorts(); const on = calls.map((c) => c[0]); calls.length = 0; m.editPorts(); const off = calls.map((c) => c[0]);"
        "item = null; calls.length = 0; m.editPorts(); console.log(JSON.stringify({ on, off, none: calls.length }));"
    )
    assert got == {"on": ["hints", "say"], "off": ["clear", "say"], "none": 0}


def test_reset_gives_the_standard_points_back_only_when_the_shape_has_its_own():
    got = _editor(
        "(async () => { await m.resetPorts(); const none = calls.length;"
        "parsed = { d: 'M 0 0', ports: [{ x: 0, y: 0 }] }; await m.resetPorts(); console.log(JSON.stringify({ none, calls: calls.filter((c) => c[0] === 'save') })); })();"
    )
    assert got == {"none": 0, "calls": [["save", None]]}


def test_the_outline_search_returns_the_nearest_point_as_fractions_with_its_distance():
    got = _module(
        "const m = wbFmtState.drawMore; const d = 'M 0 0 L 100 0 L 100 100 L 0 100 Z';"
        "console.log(JSON.stringify(m.outlineNear(d, 30, 4)));"
    )
    assert got["x"] == 0.3 and got["y"] == 0 and round(got["dist"]) == 4
