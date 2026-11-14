"""L-whiteboard-13: draw.io's `points` pixel offsets (`dx`, `dy`) and the perimeter flag as a shape's port fields, kept on
import, written back on export, checked on save; the Format panel's connection-point rows (list, add, remove, on outline,
nudge). Pure parts run in node against the source."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.api.wb_model import Said, check_sketch_data
from tests import _js_scope
from tests._app_js import frontend_text, script_file_text
from tests.test_wb_ports_more import _function, _node

ROOT = Path(__file__).resolve().parents[1]
INTERCHANGE = (ROOT / "frontend" / "js" / "whiteboard-interchange.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
PURE = INTERCHANGE[: INTERCHANGE.index("//: The rows inside an SVG")]
STYLE = "ellipse;points=[[0.5,0,0,0,0],[1,0.5,1,-10,5],[0,0.5,0,3,-4]];fillColor=#dae8fc;"
BOX = "box: (kind, item) => { const b = JSON.parse(item.data).box; return { minX: b[0], minY: b[1], maxX: b[2], maxY: b[3] }; }"


def _pure(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    out = subprocess.run([node, "-e", PURE + f"\nconsole.log(JSON.stringify({expr}));"], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


def test_a_points_style_is_read_as_ports_with_offsets_and_the_flag():
    got = _pure(f"wbDrawioStyle.points.read(wbDrawioStyle({json.dumps(STYLE)}))")
    assert got == [{"x": 0.5, "y": 0}, {"x": 1, "y": 0.5, "perimeter": True, "dx": -10, "dy": 5}, {"x": 0, "y": 0.5, "dx": 3, "dy": -4}]


def test_junk_in_points_is_left_out_and_the_count_is_capped():
    got = _pure("wbDrawioStyle.points.read({ points: '[[0.5,0],\"x\",[1,\"a\"],[2,0.5,1,0,0],[0.2,0.2,0,9999,0]]' })")
    assert got == [{"x": 0.5, "y": 0}, {"x": 2, "y": 0.5, "perimeter": True}, {"x": 0.2, "y": 0.2, "dx": 2000}]
    assert _pure("wbDrawioStyle.points.read({ points: 'not json' })") == []
    assert len(_pure("wbDrawioStyle.points.read({ points: JSON.stringify(Array.from({ length: 200 }, () => [0.5, 0.5])) })")) == 64


def test_an_imported_shape_keeps_its_ports_and_the_export_writes_them_back():
    cells = [{"id": "0"}, {"id": "1", "parent": "0"}, {"id": "a", "parent": "1", "vertex": True, "edge": False, "style": STYLE, "value": "A", "geo": {"x": 0, "y": 0, "width": 100, "height": 60}}]
    plan = _pure(f"wbDrawioPlan({json.dumps(cells)})")
    ports = plan["items"][0]["ports"]
    assert ports[1] == {"x": 1, "y": 0.5, "perimeter": True, "dx": -10, "dy": 5}
    state = {"sketches": [{"id": 1, "data": json.dumps({"d": "M 0 0 L 1 1", "shape": "circle", "ports": ports, "box": [0, 0, 100, 60]})}]}
    out = _pure(f"wbBoardToDrawio({json.dumps(state)}, {{ title: 'T', {BOX} }})")
    style = re.search(r'style="([^"]*points=[^"]*)"', out["xml"]).group(1)
    assert _pure(f"wbDrawioStyle.points.read(wbDrawioStyle({json.dumps(style)}))") == ports


def test_a_shape_without_ports_writes_no_points():
    state = {"sketches": [{"id": 1, "data": json.dumps({"d": "M 0 0 L 1 1", "shape": "circle", "box": [0, 0, 9, 9]})}]}
    assert "points=" not in _pure(f"wbBoardToDrawio({json.dumps(state)}, {{ title: 'T', {BOX} }})")["xml"]


def test_the_server_checks_a_shapes_ports():
    ok = {"d": "M 0 0 L 9 0 L 9 9 Z", "ports": [{"x": 0.5, "y": 0, "dx": -3, "dy": 4.5, "perimeter": True, "name": "N"}]}
    assert check_sketch_data(json.dumps(ok)) == json.dumps(ok)
    bad = [
        "nope",
        [{"x": "a", "y": 0}],
        [{"x": 0.5}],
        [{"x": 0.5, "y": 0, "dx": 99999}],
        [{"x": 0.5, "y": 0, "dy": True}],
        [{"x": 0.5, "y": 0, "perimeter": 1}],
        [{"x": 0.5, "y": 0, "name": "x" * 200}],
        [{"x": 9, "y": 0}],
        [{"x": 0.5, "y": 0}] * 65,
        ["not an object"],
    ]
    for ports in bad:
        with pytest.raises(Said):
            check_sketch_data(json.dumps({"d": "M 0 0", "ports": ports}))


def _module(body: str):
    return _node(
        "const wbFmtState = {}; const onSurface = () => {};"
        "const wbLinkMidpoint = (d) => (d ? { x: 0, y: 0 } : null);"
        #: A circle of radius 50 centred on (50, 50), starting at its right-most point, as a measuring path reports it.
        "const R = 50, L = 2 * Math.PI * R;"
        "const wbLinkMeasurePath = { getTotalLength: () => L, getPointAtLength: (n) => ({ x: 50 + R * Math.cos(n / R), y: 50 + R * Math.sin(n / R) }) };"
        + _function("wbPathBBox")
        + frontend_text("whiteboard-draw-more.js")
        + "\n"
        + body
    )


def test_the_nearest_outline_point_is_found_between_the_samples():
    got = _module(
        "const m = wbFmtState.drawMore; const d = 'M 0 50 A 50 50 0 1 0 100 50 A 50 50 0 1 0 0 50 Z';"
        "const near = m.outlineNear(d, 80, -20);"
        "const snapped = m.snapToOutline({ x: 0.5, y: -0.3, dx: 6, dy: -2, perimeter: true }, d);"
        "console.log(JSON.stringify({ near, snapped }));"
    )
    #: The circle's point toward (80, -20) is the centre plus 50 along that direction; a scan of 240 steps (1.3 px apart) alone is off it.
    norm = (30**2 + 70**2) ** 0.5
    assert abs(got["near"]["x"] - (50 + 50 * 30 / norm) / 100) < 0.0003 and abs(got["near"]["y"] - (50 - 50 * 70 / norm) / 100) < 0.0003
    #: The offsets ride along untouched: they are added where the port is drawn, after it has slid to the outline.
    assert got["snapped"]["dx"] == 6 and got["snapped"]["dy"] == -2 and got["snapped"]["perimeter"] is True


def test_a_perimeter_port_is_found_again_after_a_resize_and_keeps_its_offset():
    script = (
        "const wbFmtState = { drawMore: null }; const wbPortCache = new Map();"
        "const WB_FIXED_ANCHORS = []; const WB_FILLABLE_SHAPES = new Set(); const wbTableCells = () => [];"
        "let parsed = { d: 'M 0 0', shape: 'x', ports: [{ x: 1, y: 0.3, perimeter: true, dx: 5 }] };"
        "const wbSketchParsedData = () => parsed;"
        "wbFmtState.drawMore = { snapToOutline: (q, d) => ({ ...q, x: d === 'wide' ? 1 : 0.5 }) };"
        + _function("wbPortFractions")
        + "const item = { id: 3 };"
        "const a = wbPortFractions('sketch', item)[0]; parsed = { ...parsed, d: 'wide' };"
        "const b = wbPortFractions('sketch', item)[0];"
        "console.log(JSON.stringify([a, b]));"
    )
    a, b = _node(script)
    assert a["x"] == 0.5 and b["x"] == 1 and a["dx"] == b["dx"] == 5


def test_the_format_panel_has_the_connection_point_rows_for_a_shape_and_help_says_so():
    for ident in ("wb-fmt-port", "wb-fmt-port-add", "wb-fmt-port-del", "wb-fmt-port-perim", "wb-fmt-port-dx", "wb-fmt-port-dy"):
        assert f'id="{ident}"' in INDEX, ident
    assert INDEX.count('data-fmt="ports"') == 3
    fmt = frontend_text("whiteboard-format.js")
    assert '"ports"' in fmt.split("const WB_FMT_FIELDS")[1].split("shape: [")[1].split("]")[0]
    assert "syncPortsRow" in fmt
    assert "Connection points" in INDEX.split('id="wb-fmt-help-geometry"')[1].split("</div>")[0]


def test_draw_more_still_has_no_globals():
    src = script_file_text("whiteboard-draw-more.js")
    assert _js_scope.is_wrapped(src) and _js_scope.global_names(src) == set()


#: The rows' stand-ins: elements that keep their listeners and values, and a shape with two own ports.
ROWS = (
    "const els = {}; const mk = (id) => (els[id] = { id, value: '', checked: false, disabled: false, hidden: false, children: [], listeners: {},"
    "  addEventListener(n, f) { this.listeners[n] = f; }, replaceChildren(...c) { this.children = c; }, append(...c) { this.children.push(...c); } });"
    "for (const id of ['wb-fmt-port', 'wb-fmt-port-add', 'wb-fmt-port-del', 'wb-fmt-port-perim', 'wb-fmt-port-dx', 'wb-fmt-port-dy']) mk(id);"
    "const rows = [{ hidden: true }, { hidden: true }, { hidden: true }];"
    "const document = { getElementById: (id) => els[id] || null, querySelectorAll: (q) => (q === '[data-fmt=\"ports\"]' ? rows : []), activeElement: null,"
    "  createElement: (t) => ({ tag: t, value: '', textContent: '' }), addEventListener() {} };"
    "const calls = []; const toast = () => {}; const onSurface = (s, f) => f(); const wbFmtState = {};"
    "const wbAnnounce = (t) => calls.push(['say', t]); const wbClearAnchorHints = () => {}; const wbShowAnchorHints = () => {}; const wbScheduleRender = () => {};"
    "let raw = [{ x: 0.5, y: 0 }, { x: 1, y: 0.5, perimeter: true, dx: 4 }];"
    "let item = { id: 7 }; let parsed = { d: 'M 0 0 L 9 0 L 9 9 Z', get ports() { return raw; } };"
    "const wbSwapTarget = () => (item ? { item, parsed } : null);"
    "const wbPortFractions = () => raw || [{ x: 0, y: 0 }, { x: 1, y: 1 }];"
    "const wbFmtSketch = () => parsed;"
    "const wbRecordGesture = async (f) => { calls.push(['gesture']); await f(); };"
    "const wbSaveSketchProps = async (i, props) => { calls.push(['save', props.ports === undefined ? null : props.ports]); };"
    "const d3 = { zoomTransform: () => ({ k: 1 }) }; const wbClientToBoard = (x, y) => [x, y];"
    "const wbAnchorPositions = () => []; const wbNearestAnchor = () => null;"
    "const tick = () => new Promise((r) => setTimeout(r, 5));"
)


def _rows(body: str):
    return _node(
        ROWS
        + _function("wbPathBBox")
        + "const wbLinkMidpoint = (d) => (d ? { x: 0, y: 0 } : null); const wbLinkMeasurePath = null;"
        + frontend_text("whiteboard-draw-more.js")
        + "\nconst m = wbFmtState.drawMore; const sync = () => m.syncPortsRow(new Set(['ports']), item ? [{ kind: 'sketch', item }] : []);\n"
        + body
    )


def test_the_rows_show_for_one_shape_and_fill_from_the_chosen_port():
    got = _rows(
        "sync(); const shown = rows.map((r) => r.hidden);"
        "els['wb-fmt-port'].value = '1'; els['wb-fmt-port'].listeners.change({ target: els['wb-fmt-port'] }); sync();"
        "console.log(JSON.stringify({ shown, n: els['wb-fmt-port'].children.length, perim: els['wb-fmt-port-perim'].checked, dx: els['wb-fmt-port-dx'].value, dy: els['wb-fmt-port-dy'].value }));"
    )
    assert got == {"shown": [False, False, False], "n": 2, "perim": True, "dx": "4", "dy": ""}


def test_the_rows_hide_for_nothing_selected():
    got = _rows("item = null; sync(); console.log(JSON.stringify(rows.map((r) => r.hidden)));")
    assert got == [True, True, True]


def test_toggling_nudging_and_removing_are_one_undo_step_each():
    got = _rows(
        "(async () => {"
        "sync(); els['wb-fmt-port'].value = '0'; els['wb-fmt-port'].listeners.change({ target: els['wb-fmt-port'] });"
        "els['wb-fmt-port-perim'].checked = true; await els['wb-fmt-port-perim'].listeners.change({ target: els['wb-fmt-port-perim'] }); await tick();"
        "els['wb-fmt-port-dx'].value = '7'; await els['wb-fmt-port-dx'].listeners.change({ target: els['wb-fmt-port-dx'] }); await tick();"
        "els['wb-fmt-port-dy'].value = '99999'; await els['wb-fmt-port-dy'].listeners.change({ target: els['wb-fmt-port-dy'] }); await tick();"
        "await els['wb-fmt-port-del'].listeners.click(); await tick();"
        "console.log(JSON.stringify({ calls: calls.filter((c) => c[0] !== 'say') }));"
        "})();"
    )
    saves = [c[1] for c in got["calls"] if c[0] == "save"]
    assert [c[0] for c in got["calls"]].count("gesture") == 4 and len(saves) == 4
    assert saves[0][0] == {"x": 0.5, "y": 0, "perimeter": True}
    assert saves[1][0]["dx"] == 7
    assert saves[2][0]["dy"] == 2000
    assert saves[3] == [{"x": 1, "y": 0.5, "perimeter": True, "dx": 4}]


def test_add_starts_the_outline_editor_and_clearing_perimeter_drops_the_key():
    got = _rows(
        "(async () => {"
        "sync(); els['wb-fmt-port-add'].listeners.click(); const said = calls.filter((c) => c[0] === 'say').length;"
        "els['wb-fmt-port'].value = '1'; els['wb-fmt-port'].listeners.change({ target: els['wb-fmt-port'] });"
        "els['wb-fmt-port-perim'].checked = false; await els['wb-fmt-port-perim'].listeners.change({ target: els['wb-fmt-port-perim'] }); await tick();"
        "console.log(JSON.stringify({ said, saves: calls.filter((c) => c[0] === 'save') }));"
        "})();"
    )
    assert got["said"] == 1
    assert got["saves"][0][1][1] == {"x": 1, "y": 0.5, "dx": 4}


def test_port_edits_queue_so_none_is_lost():
    """A nudge's change fires on blur as On outline is pressed: two saves in flight shared one Undo step and the
    later PATCH could land first and lose the edit (sweep wbports-offsets.js, 2026-11-12). Edits queue, and a
    nudge to the value already stored saves nothing."""
    src = (ROOT / "frontend" / "js" / "whiteboard-draw-more.js").read_text(encoding="utf-8")
    body = src[src.index("function editChosenPort(") : src.index("function bindPortsRows(")]
    assert "portQueue = portQueue.then(" in body
    assert "change(q, ports) === false" in body
    assert "if ((Number(q[key]) || 0) === n) return false;" in src


def test_add_has_a_keyboard_path_that_puts_a_point_after_the_chosen_one() -> None:
    """Review 5883430964: Add opened the outline editor, which only a pointer can press. A key's click (detail 0)
    adds the point halfway along the outline to the next point, chooses it and puts the keys in the nudge field."""
    src = (ROOT / "frontend" / "js" / "whiteboard-draw-more.js").read_text(encoding="utf-8")
    assert 'addEventListener("click", (e) => (e?.detail === 0 ? addPortByKey() : editPorts()))' in src
    body = src[src.index("function addPortByKey()") : src.index("function bindPortsRows()")]
    assert "outlineNear(target.parsed.d" in body and "ports.splice(i + 1, 0," in body and "portRow.i = added" in body
    assert 'getElementById("wb-fmt-port-dx")?.focus()' in body and "editChosenPort(" in body, "one Undo step, queued"
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "from the keyboard, Enter adds one after the chosen point" in html
    guide = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")
    assert "Enter on Add puts one after the chosen point" in guide
