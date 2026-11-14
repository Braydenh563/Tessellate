"""The numeric waypoint list (WHITEBOARD_PLAN section 4, draw.io's `addEdgeWaypoints`): a connector's bends as one
text field of "x, y" pairs in the Style tab. The parse and write functions are pure and run in node."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _run(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        "const wbFmtState = {}; const onSurface = () => {};\n" + frontend_text("whiteboard-shape-more.js")
        + f"\nconst m = wbFmtState.shapeMore; console.log(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


def test_the_list_round_trips():
    points = [{"x": 120, "y": 80}, {"x": 200.4, "y": -5}]
    text = _run(f"m.waypointsText({json.dumps(points)})")
    assert text == "120, 80; 200, -5"
    assert _run(f"m.parseWaypoints({json.dumps(text)})") == [{"x": 120, "y": 80}, {"x": 200, "y": -5}]


def test_empty_clears_and_nonsense_is_refused():
    assert _run('m.parseWaypoints("")') == []
    assert _run('m.parseWaypoints("  ;  ")') == []
    assert _run('m.parseWaypoints("120, abc")') is None
    assert _run('m.parseWaypoints("1, 2, 3")') is None
    assert _run('m.parseWaypoints("50")') is None
    assert _run('m.waypointsText(undefined)') == ""


def test_spaces_or_newlines_separate_and_a_long_list_is_refused():
    assert _run('m.parseWaypoints("10 20\\n30,40")') == [{"x": 10, "y": 20}, {"x": 30, "y": 40}]
    many = "; ".join(f"{i}, {i}" for i in range(51))
    assert _run(f"m.parseWaypoints({json.dumps(many)})") is None


def test_the_panel_has_the_field_for_a_connector_only():
    fmt = frontend_text("whiteboard-format.js")
    link = fmt[fmt.index("  link: ["):].split("\n", 1)[0]
    assert '"waypoints"' in link
    for kind in ("shape", "line", "arrow", "text"):
        assert '"waypoints"' not in fmt[fmt.index(f"  {kind}: ["):].split("\n", 1)[0]
    assert 'id="wb-fmt-waypoints"' in HTML and 'data-fmt="waypoints"' in HTML
    assert 'case "waypoints":' in fmt and 'on("wb-fmt-waypoints", "change"' in fmt
    body = fmt[fmt.index('on("wb-fmt-waypoints", "change"'):][:900]
    assert 'wbFmtApply("waypoints"' in body and "points: points.length ? points : undefined" in body
