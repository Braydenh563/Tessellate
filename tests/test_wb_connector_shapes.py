"""Connector shapes and text on path (WHITEBOARD_PLAN section 4): a link's `shape` is drawn as an outline round its centre line.

`connectorOutline` (whiteboard-shape-more.js) is pure and run in node; the .drawio import and export are read in node
from whiteboard-interchange.js. The browser half (each shape drawn, textPath on and off) is
`scratchpad/ui-sweeps/wbconnectors3.js`."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tests._app_js import frontend_text

SHAPES = ["double", "block", "flex", "tapered", "pipe", "wire"]


def _node(script: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


def _outline(shape, pts, width=3, heads=None):
    script = (
        "const wbFmtState = {}; const onSurface = () => {};\n" + frontend_text("whiteboard-shape-more.js")
        + f"\nconsole.log(JSON.stringify(wbFmtState.shapeMore.connectorOutline({json.dumps(shape)}, {json.dumps(pts)}, {width}, {json.dumps(heads or {'start': False, 'end': True})})));"
    )
    return _node(script)


def _box(d):
    #: Only the polygon part (before any arc) is read for the box.
    poly = d.split(" M ", 1)[0]
    nums = [float(n) for n in re.findall(r"-?\d+\.?\d*", poly)]
    xs, ys = nums[0::2], nums[1::2]
    return min(xs), min(ys), max(xs), max(ys)


LINE = [{"x": 0, "y": 0}, {"x": 200, "y": 0}]


@pytest.mark.parametrize("shape", SHAPES)
def test_each_shape_is_a_closed_outline_round_the_centre_line(shape):
    out = _outline(shape, LINE)
    assert out and out["d"].startswith("M ") and " Z" in out["d"]
    x0, y0, x1, y1 = _box(out["d"])
    assert y1 - y0 > 2 and y0 < 0 < y1  # it has width on both sides of the line
    assert x0 >= -0.5 and x1 <= 200.5  # and does not run past the ends
    assert out["paint"] in {"outline", "tube", "solid"}


def test_the_plain_line_and_a_line_with_no_length_have_no_outline():
    assert _outline("line", LINE) is None
    assert _outline("block", [{"x": 5, "y": 5}, {"x": 5, "y": 5}]) is None


def test_an_arrow_head_is_wider_than_its_body_and_ends_in_a_point_at_the_end():
    out = _outline("block", LINE)
    x0, y0, x1, y1 = _box(out["d"])
    nums = [float(n) for n in re.findall(r"-?\d+\.?\d*", out["d"].split(" Z")[0])]
    pts = list(zip(nums[0::2], nums[1::2]))
    tip = max(pts, key=lambda p: p[0])
    assert tip == (200.0, 0.0)
    assert x0 < 1 and x1 == tip[0] and y0 < 0 < y1  # the outline spans the line and sits on both sides of it
    body = [p for p in pts if p[0] < 60]
    assert max(abs(p[1]) for p in pts) > max(abs(p[1]) for p in body) + 2


def test_a_tapered_arrow_grows_toward_its_end_and_a_head_can_sit_at_the_start_too():
    out = _outline("tapered", LINE)
    nums = [float(n) for n in re.findall(r"-?\d+\.?\d*", out["d"].split(" Z")[0])]
    pts = list(zip(nums[0::2], nums[1::2]))
    near = max(abs(p[1]) for p in pts if p[0] < 20)
    far = max(abs(p[1]) for p in pts if p[0] > 180)
    assert far > near * 3
    both = _outline("flex", LINE, heads={"start": True, "end": True})
    nums = [float(n) for n in re.findall(r"-?\d+\.?\d*", both["d"].split(" Z")[0])]
    xs = nums[0::2]
    assert min(xs) == 0 and max(xs) == 200


def test_an_outline_follows_a_bend():
    out = _outline("double", [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 100}])
    x0, y0, x1, y1 = _box(out["d"])
    assert x1 > 100 and y1 >= 100 and y0 < 0


def test_a_wire_ends_in_round_terminals():
    assert " a " in _outline("wire", LINE)["d"]


# --- .drawio ---------------------------------------------------------------------------------------------------------


def _interchange(expr: str):
    src = frontend_text("whiteboard-interchange.js")
    pure = src[: src.index("//: The rows inside an SVG")]
    return _node(pure + f"\n(async () => console.log(JSON.stringify(await ({expr}))))();")


EDGE = '<mxCell id="4" value="" style="{style}" edge="1" parent="1" source="2" target="3"><mxGeometry relative="1" as="geometry"/></mxCell>'
CELLS = [
    {"id": "2", "parent": "1", "vertex": True, "value": "A", "style": "rounded=1;", "geo": {"x": 0, "y": 0, "width": 80, "height": 40}},
    {"id": "3", "parent": "1", "vertex": True, "value": "B", "style": "rounded=1;", "geo": {"x": 200, "y": 0, "width": 80, "height": 40}},
]


@pytest.mark.parametrize("draw, ours", [("link", "double"), ("arrow", "block"), ("flexArrow", "flex"), ("taperedArrow", "tapered"), ("pipe", "pipe"), ("wire", "wire")])
def test_the_drawio_import_maps_edge_shapes_and_the_export_writes_them_back(draw, ours):
    cell = {"id": "4", "parent": "1", "edge": True, "source": "2", "target": "3", "style": f"shape={draw};edgeStyle=orthogonalEdgeStyle;", "value": "", "points": []}
    plan = _interchange(f"wbDrawioPlan({json.dumps(CELLS + [cell])})")
    data = plan["links"][0]["data"]
    assert data["shape"] == ours and data["route"] == "elbow"
    state = {
        "nodes": [], "objects": [],
        "sketches": [
            {"id": 1, "data": json.dumps({"d": "M 0 0 L 9 9", "shape": "rect", "box": [0, 0, 90, 60]})},
            {"id": 2, "data": json.dumps({"d": "M 0 0 L 9 9", "shape": "rect", "box": [300, 0, 390, 60]})},
            {"id": 3, "data": json.dumps({"type": "link-straight", "sourceId": 1, "sourceKind": "sketch", "targetId": 2, "targetKind": "sketch", "shape": ours, "route": "elbow", "width": 2})},
        ],
    }
    out = _interchange(f"wbBoardToDrawio({json.dumps(state)}, {{ box: (k, item) => {{ const b = JSON.parse(item.data).box; return {{ minX: b[0], minY: b[1], maxX: b[2], maxY: b[3] }}; }} }})")
    styles = [c.get("style") for c in ET.fromstring(re.search(r"<mxGraphModel.*</mxGraphModel>", out["xml"], re.S).group(0)).iter("mxCell") if c.get("edge") == "1"]
    assert f"shape={draw};" in styles[0] and "edgeStyle=orthogonalEdgeStyle;" in styles[0], styles


# --- wiring ------------------------------------------------------------------------------------------------------------


def test_the_format_rows_exist_and_are_wired_through_the_undoable_apply():
    index = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")
    for needle in ('id="wb-fmt-edgeshape"', 'id="wb-fmt-textpath"', 'data-fmt="edgeshape"', 'data-fmt="textpath"'):
        assert needle in index
    fmt = frontend_text("whiteboard-format.js")
    assert 'wbFmtApply("edgeshape"' in fmt and 'wbFmtApply("textpath"' in fmt
    board = frontend_text("whiteboard.js")
    assert "shapedLink(parsed, endpoints)" in board and "groupEl.dataset.labelPath" in board and "textPath" in board


def test_text_on_path_runs_the_label_along_a_copy_of_the_line_and_keeps_the_words_when_it_is_off():
    board = frontend_text("whiteboard.js")
    body = board[board.index("function wbLayoutLinkLabel") :][:3600]
    assert 'startOffset' in body and "if (own) label.textContent = own.textContent" in body
