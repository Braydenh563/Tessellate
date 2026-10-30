"""A free board out as a `.drawio` file (OPEN 807: the import had no way back).

The pure writer runs in node against the source; the browser half (the

driven in a browser (7 of 7 at 1440 and 390 wide).
"""

import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "frontend" / "js" / "whiteboard-interchange.js").read_text(encoding="utf-8")
BOARD = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _export(state: dict, options: str = "") -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    pure = SOURCE[: SOURCE.index("//: The rows inside an SVG")]
    box = "box: (kind, item) => { const b = JSON.parse(item.data).box; return { minX: b[0], minY: b[1], maxX: b[2], maxY: b[3] }; }"
    script = pure + f"\nconsole.log(JSON.stringify(wbBoardToDrawio({json.dumps(state)}, {{ title: 'Plan', {box}{options} }})));"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


def _sketch(id_: int, **data) -> dict:
    return {"id": id_, "data": json.dumps(data)}


STATE = {
    "nodes": [{"id": 9, "entry_id": 3}],
    "objects": [
        {"id": 1, "kind": "text", "x": 10, "y": 20, "width": 200, "height": 80, "z": 3, "data": {"content": "A < B & \"C\"\nsecond line", "bold": True, "color": "#112233"}},
        {"id": 2, "kind": "frame", "x": 0, "y": 0, "width": 600, "height": 400, "z": 9, "data": {"content": "Lane"}},
        {"id": 3, "kind": "text", "x": 300, "y": 40, "width": 120, "height": 90, "z": 4, "data": {"content": "Sticky", "bg": "#FFEE88", "border_color": "#e8d56a"}},
        {"id": 4, "kind": "image", "x": 0, "y": 0, "width": 50, "height": 50, "data": {}},
        {"id": 5, "kind": "table", "x": 0, "y": 0, "width": 50, "height": 50, "data": {}},
    ],
    "sketches": [
        _sketch(10, d="M 0 0 L 1 1", shape="circle", color="#ff0000", fill="#00ff00", width=4, dash="dashed", label="Round", box=[100, 200, 180, 260]),
        _sketch(11, d="M 0 0 L 9 0 L 9 9 Z", shape="custom", box=[0, 0, 9, 9]),
        _sketch(12, d="M 0 0 L 50 50", box=[0, 0, 50, 50]),
        _sketch(20, type="link-curved", sourceKind="object", sourceId=1, targetKind="sketch", targetId=10, endCap="arrow", label="go", color="#334455", width=2),
        _sketch(21, type="link-straight", sourceKind="object", sourceId=1, targetKind="object", targetId=99),
        _sketch(22, type="link-straight", sourceKind="object", sourceId=1, sourcePoint={"x": 1, "y": 2}, targetPoint={"x": 30, "y": 40}, route="elbow"),
    ],
}


def test_a_board_is_written_as_one_well_formed_drawio_page() -> None:
    made = _export(STATE)
    root = ET.fromstring(made["xml"].split("\n", 1)[1])
    assert root.tag == "mxfile" and root.find("diagram").get("name") == "Plan"
    cells = {c.get("id"): c for c in root.iter("mxCell")}
    assert {"0", "1"} <= set(cells)
    # frame, plain text, sticky, circle, custom shape: five vertices; one edge joined at both ends and one with a free end (the third has none: skipped).
    vertices = [c for c in cells.values() if c.get("vertex") == "1"]
    edges = [c for c in cells.values() if c.get("edge") == "1"]
    assert (made["shapes"], made["links"]) == (5, 2) and (len(vertices), len(edges)) == (5, 2)
    assert made["skipped"] == {"pictures": 1, "tables": 1, "cards": 1, "shapes drawn as boxes": 1, "drawn lines": 1, "loose connectors": 1}


def test_labels_survive_escaping_and_a_frame_sits_behind_what_is_on_it() -> None:
    made = _export(STATE)
    root = ET.fromstring(made["xml"].split("\n", 1)[1])
    vertices = [c for c in root.iter("mxCell") if c.get("vertex") == "1"]
    assert vertices[0].get("style").startswith("swimlane") and vertices[0].get("value") == "Lane"
    plain = next(c for c in vertices if c.get("value", "").startswith("A < B"))
    assert plain.get("value") == 'A < B & "C"\nsecond line'
    assert "fontStyle=1" in plain.get("style") and "fontColor=#112233" in plain.get("style")
    geo = plain.find("mxGeometry")
    assert (geo.get("x"), geo.get("y"), geo.get("width"), geo.get("height")) == ("10", "20", "200", "80")


def test_shapes_and_connectors_keep_their_look_and_their_joins() -> None:
    made = _export(STATE)
    root = ET.fromstring(made["xml"].split("\n", 1)[1])
    cells = list(root.iter("mxCell"))
    sticky = next(c for c in cells if c.get("value") == "Sticky")
    assert "fillColor=#ffee88" in sticky.get("style") and "strokeColor=#e8d56a" in sticky.get("style")
    circle = next(c for c in cells if c.get("value") == "Round")
    style = circle.get("style")
    assert style.startswith("ellipse;") and "fillColor=#00ff00" in style and "strokeColor=#ff0000" in style
    assert "strokeWidth=2" in style and "dashed=1" in style
    geo = circle.find("mxGeometry")
    assert (geo.get("x"), geo.get("y"), geo.get("width"), geo.get("height")) == ("100", "200", "80", "60")
    joined = next(c for c in cells if c.get("edge") == "1" and c.get("value") == "go")
    assert joined.get("source") and joined.get("target") and joined.get("source") != joined.get("target")
    assert "endArrow=classic" in joined.get("style") and "startArrow=none" in joined.get("style") and "curved=1" in joined.get("style")
    free = next(c for c in cells if c.get("edge") == "1" and not c.get("target"))
    assert free.get("source") and "edgeStyle=orthogonalEdgeStyle" in free.get("style")
    assert [p.get("as") for p in free.iter("mxPoint")] == ["targetPoint"]


def test_hidden_items_are_left_out() -> None:
    made = _export(STATE, ", hidden: (kind, item) => kind === 'object' && item.id === 1")
    assert "A &lt; B" not in made["xml"] and made["shapes"] == 4


def test_the_dialog_offers_it_for_a_free_board_only() -> None:
    row = BOARD[BOARD.index('value: "drawio"') :][:400]
    assert 'label: "draw.io"' in row and "board: true" in row and "wbExportDrawio()" in row
    assert "async function wbExportDrawio" in SOURCE


def test_a_plain_text_cell_is_kept_as_typed_and_an_html_one_is_still_stripped() -> None:
    pure = SOURCE[: SOURCE.index("//: The rows inside an SVG")]
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = pure + 'console.log(JSON.stringify([wbDrawioText("a <b> &amp; c", false), wbDrawioText("a<br>b &amp; <i>c</i>")]));'
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    assert json.loads(out.stdout) == ["a <b> &amp; c", "a\nb & c"]
