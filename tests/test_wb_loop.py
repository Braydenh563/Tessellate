"""F2, draw.io's self-loop and its side (`addLoopDirection`): a curved connector from a shape back to itself is drawn as a
loop out of one side (top, right, bottom or left) and Format's Loop side moves it.

The module runs in node against a stand-in for the board; the board's own `wbLinkShape` is cut out of whiteboard.js."""

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


def _node(body: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        "const wbFmtState = {};\nconst onSurface = () => {};\n" + frontend_text("whiteboard-draw-more.js") + "\n" + body
    )
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


def test_a_loop_leaves_by_its_side_and_comes_back_to_it():
    got = _node(
        "const m = wbFmtState.drawMore; const out = {};"
        "for (const side of ['top', 'right', 'bottom', 'left']) {"
        "  const s = m.SIDES[side]; const a = { x: 100 + 100 * s.start.x, y: 100 + 60 * s.start.y }, b = { x: 100 + 100 * s.end.x, y: 100 + 60 * s.end.y };"
        "  out[side] = { seg: m.loopSegs(side, a, b)[0], a, b };"
        "} console.log(JSON.stringify(out));"
    )
    for side, (dx, dy) in {"top": (0, -1), "right": (1, 0), "bottom": (0, 1), "left": (-1, 0)}.items():
        seg, a, b = got[side]["seg"], got[side]["a"], got[side]["b"]
        assert seg["a"] == a and seg["b"] == b
        #: Both control points are out along the side's normal, equally far, so the loop is symmetrical and outside.
        for control, end in ((seg["c1"], a), (seg["c2"], b)):
            assert (control["x"] - end["x"]) * dx + (control["y"] - end["y"]) * dy >= 36
            assert (control["x"] - end["x"]) * dy == 0 and (control["y"] - end["y"]) * dx == 0


def test_the_ends_of_every_side_sit_on_that_side_of_the_box():
    sides = _node("console.log(JSON.stringify(wbFmtState.drawMore.SIDES));")
    for name, side in sides.items():
        for end in (side["start"], side["end"]):
            assert {"top": end["y"] == 0, "bottom": end["y"] == 1, "left": end["x"] == 0, "right": end["x"] == 1}[name]
        assert side["start"] != side["end"]


def test_only_a_curved_connector_from_a_shape_to_itself_is_a_loop():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        "const wbFmtState = {};\nconst onSurface = () => {};\n" + frontend_text("whiteboard-draw-more.js") + "\n"
        + "function wbLinkRouteName(p) { return p?.type === 'link-straight' ? 'straight' : 'curved'; }\n"
        + "const wbLinkLabelT = () => 0.5;\nfunction wbLinkGap() { return null; }\n"
        + _function("wbLinkShape")
        + "const same = { type: 'link-curved', sourceId: 4, targetId: 4 };"
        + "console.log(JSON.stringify({"
        + " loop: wbLinkShape({ ...same, loop: 'right' }), top: wbLinkShape(same),"
        + " other: wbLinkShape({ ...same, targetId: 5 }), kinds: wbLinkShape({ ...same, sourceKind: 'sketch' }),"
        + " elbow: wbLinkShape({ ...same, route: 'elbow' }), straight: wbLinkShape({ ...same, type: 'link-straight' }) }));"
    )
    got = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)
    assert got["loop"]["route"] == "loop" and got["loop"]["side"] == "right" and got["top"]["side"] == "top"
    #: A connector between two things, a mixed-kind pair, an elbow and a straight line keep their own shapes.
    assert got["other"] is None and got["kinds"] is None
    assert got["elbow"]["route"] == "elbow" and got["straight"] is None


def test_add_a_loop_takes_the_first_free_side_and_joins_the_shape_to_itself():
    got = _node(
        "const posted = []; const sketches = [];"
        "const window = {}; const wbCloneSource = () => ({ kind: 'sketch', id: 7 });"
        "const toast = () => {}; const wbAnnounce = (t) => posted.push(['said', t]);"
        "const wbIsLinkSketch = (s) => true; const wbSketchParsedData = (s) => JSON.parse(s.data);"
        "const wbState = { sketches }; const wbStackNewZ = () => 3; const wbScheduleRender = () => {}; const selectWbItem = () => {};"
        "const wbRecordGesture = async (fn) => { await fn(); };"
        "let n = 0; const apiJson = async (url, init) => { const body = JSON.parse(init.body); return { id: ++n, data: body.data }; };"
        "(async () => {"
        "  await wbFmtState.drawMore.addLoop(); await wbFmtState.drawMore.addLoop();"
        "  const sides = sketches.map((s) => JSON.parse(s.data));"
        "  console.log(JSON.stringify(sides));"
        "})();"
    )
    assert [d["loop"] for d in got] == ["top", "right"]
    first = got[0]
    assert first["type"] == "link-curved" and first["sourceId"] == first["targetId"] == 7
    assert first["sourceKind"] == first["targetKind"] == "sketch" and first["sourceAnchor"] != first["targetAnchor"]


def test_the_board_the_panel_the_command_and_the_help_agree():
    path = _function("wbLinkPathD")
    assert 'shape?.route === "loop"' in path and "wbFmtState.drawMore.loopSegs(shape.side, sPt, tPt)" in path
    assert '["er", "iso", "loop"].includes(wbLinkShape(parsed)?.route)' in _function("wbRenderWaypointHandles")
    assert '["er", "iso", "loop"].includes(shape?.route)' in _function("wbWaypointAddSpots")
    fmt = script_file_text("whiteboard-format.js")
    assert '"tip", "loop", "label2"' in fmt and "wbFmtState.drawMore?.syncLoopRow(takes, sharing);" in fmt
    commands = script_file_text("whiteboard-commands.js")
    assert 'id: "loop"' in commands and "wbFmtState.drawMore.addLoop()" in commands and 'needs: "clone"' in commands.split('id: "loop"')[1].split("\n")[0]
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    block = html[html.index('id="wb-fmt-loop"') :]
    block = block[: block.index("</select>")]
    for side in ("top", "right", "bottom", "left"):
        assert f'value="{side}"' in block
    assert "<b>Loop side</b>" in html
    src = script_file_text("whiteboard-draw-more.js")
    assert _js_scope.is_wrapped(src) and _js_scope.global_names(src) == set()
