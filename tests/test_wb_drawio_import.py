"""`.drawio` files onto a board (INBOX 797, canvasdepth; WHITEBOARD_PLAN
"canvasdepth, ranked" row 3, and the draw.io programme's decision 3 for the
style keys).

A file from draw.io could not be opened. The XML is read in the browser
(`DOMParser`, and `DecompressionStream` for a compressed page); what each
cell becomes is pure and runs here in node. The browser half is
`scratchpad/ui-sweeps/wbdrawio.js`.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import index_html_text

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "frontend" / "js" / "whiteboard-interchange.js").read_text(encoding="utf-8")
INDEX = index_html_text()


def _run(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    pure = SOURCE[: SOURCE.index("//: The rows inside an SVG")]
    out = subprocess.run([node, "-e", pure + f"\nconsole.log(JSON.stringify({expr}));"], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


def test_a_style_string_reads_as_keys() -> None:
    got = _run('wbDrawioStyle("ellipse;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;")')
    assert got["_kind"] == "ellipse" and got["fillColor"] == "#dae8fc" and got["html"] == "1"
    assert _run('wbDrawioStyle("")') == {}


CELLS = [
    {"id": "0"}, {"id": "1", "parent": "0"},
    {"id": "a", "parent": "1", "vertex": True, "value": "Start", "style": "rounded=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontColor=#112233;fontStyle=1;", "geo": {"x": 10, "y": 20, "width": 120, "height": 60}},
    {"id": "b", "parent": "1", "vertex": True, "value": "Ready?", "style": "rhombus;dashed=1;strokeWidth=2;", "geo": {"x": 200, "y": 20, "width": 80, "height": 80}},
    {"id": "c", "parent": "1", "vertex": True, "value": "A note", "style": "text;html=1;fontSize=18;", "geo": {"x": 10, "y": 200, "width": 100, "height": 30}},
    {"id": "lane", "parent": "1", "vertex": True, "value": "Team", "style": "swimlane;", "geo": {"x": 400, "y": 0, "width": 300, "height": 200}},
    {"id": "d", "parent": "lane", "vertex": True, "value": "Inside", "style": "ellipse;", "geo": {"x": 20, "y": 40, "width": 60, "height": 40}},
    {"id": "e1", "parent": "1", "edge": True, "source": "a", "target": "b", "value": "go", "style": "edgeStyle=orthogonalEdgeStyle;endArrow=classic;", "geo": {}},
    {"id": "e2", "parent": "1", "edge": True, "source": "b", "target": "d", "value": "", "style": "curved=1;endArrow=none;startArrow=oval;", "geo": {}},
    {"id": "l2", "parent": "e2", "vertex": True, "value": "yes", "style": "edgeLabel;", "geo": {"x": 0, "y": 0, "relative": True}},
    {"id": "e3", "parent": "1", "edge": True, "value": "", "style": "", "geo": {}, "sourcePoint": {"x": 0, "y": 300}, "targetPoint": {"x": 100, "y": 300}},
    {"id": "f", "parent": "1", "vertex": True, "value": "glass", "style": "glass=1;sketch=1;", "geo": {"x": 0, "y": 400, "width": 40, "height": 40}},
]


def _plan():
    return _run(f"wbDrawioPlan({json.dumps(CELLS)})")


def test_vertices_become_shapes_text_and_frames() -> None:
    plan = _plan()
    by = {i["id"]: i for i in plan["items"]}
    assert by["a"]["kind"] == "shape" and by["a"]["shape"] == "rounded" and by["a"]["label"] == "Start"
    assert by["a"]["look"] == {"color": "#6c8ebf", "fill": "#dae8fc", "fillOpacity": 1, "label_color": "#112233", "label_bold": True, "width": 2}
    assert by["b"]["shape"] == "diamond" and by["b"]["look"]["dash"] == "dashed" and by["b"]["look"]["width"] == 4
    assert by["c"]["kind"] == "text" and by["c"]["label"] == "A note" and by["c"]["look"]["font_size"] == 18
    assert by["lane"]["kind"] == "frame" and by["lane"]["label"] == "Team"
    #: A child's geometry is relative to its container; the board's is absolute.
    assert (by["d"]["x"], by["d"]["y"]) == (420, 40)


def test_edges_become_connectors_with_their_route_caps_and_labels() -> None:
    links = {link["id"]: link for link in _plan()["links"]}
    assert links["e1"]["source"] == "a" and links["e1"]["target"] == "b"
    assert links["e1"]["data"]["route"] == "elbow" and links["e1"]["data"]["endCap"] == "arrow" and links["e1"]["data"]["label"] == "go"
    assert links["e2"]["type"] == "link-curved" and "endCap" not in links["e2"]["data"] and links["e2"]["data"]["startCap"] == "circle"
    assert links["e2"]["data"]["label"] == "yes"
    assert links["e3"]["data"]["sourcePoint"] == {"x": 0, "y": 300} and links["e3"]["data"]["targetPoint"] == {"x": 100, "y": 300}


def test_what_has_no_counterpart_is_counted() -> None:
    plan = _plan()
    assert plan["dropped"]["glass"] == 1 and plan["dropped"]["sketch"] == 1


def test_html_labels_are_read_as_text() -> None:
    assert _run('wbDrawioText("<div>One<br>two &amp; <b>three</b></div>")') == "One\ntwo & three"


def test_the_import_dialog_takes_drawio_files() -> None:
    accept = INDEX[INDEX.index('id="wb-import-file"') :]
    accept = accept[: accept.index(">")]
    assert ".drawio" in accept
    body = SOURCE[SOURCE.index("async function wbImportText(") :]
    assert "wbImportDrawio(" in body[: body.index("\n}\n")]


def test_every_page_comes_in_each_in_a_frame() -> None:
    """canvasdepth2: pages after the first come in too, each in a frame named
    after its page, side by side (decision 22: a board's pages are its
    frames); a one-page file has no frame round it. The browser half is
    `scratchpad/ui-sweeps/wbdepth2.js wbdrawiopages`."""
    cells = SOURCE[SOURCE.index("async function wbDrawioCells(") :]
    cells = cells[: cells.index("\n}\n")]
    assert "all.push({ name:" in cells and "return { cells: all[0].cells, pages:" in cells
    imp = SOURCE[SOURCE.index("async function wbImportDrawio(") :]
    imp = imp[: imp.index("\n}\n")]
    assert "const framed = pages.length > 1;" in imp
    assert imp.index('wbCreateObject("frame", { content: page.name') < imp.index("wbDrawioPlace(page.plan")
    assert "wbRecordGesture(" in imp
