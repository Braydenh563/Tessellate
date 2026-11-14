"""draw.io interchange, the rest (WHITEBOARD_PLAN section 14 and 8): rotation, a picture inside the file,
gradient and shadow both ways; the `mxlibrary` reader and writer; the CSV import; a plan as a library entry.

The pure parts run in node against the source (the browser half, with the DOM reader and the upload, is
`scratchpad/ui-sweeps/wbdrawio3.js`).
"""

import base64
import json
import re
import shutil
import subprocess
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "frontend" / "js" / "whiteboard-interchange.js").read_text(encoding="utf-8")
LIBRARY = (ROOT / "frontend" / "js" / "whiteboard-library.js").read_text(encoding="utf-8")


def _run(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    pure = SOURCE[: SOURCE.index("//: The rows inside an SVG")]
    script = pure + f"\n(async () => console.log(JSON.stringify(await ({expr}))))();"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


def cells_of(xml: str) -> list[dict]:
    """The reader's cells (`wbDrawioModelCells`) for an `mxGraphModel`, in python."""
    cells = []
    for el in ET.fromstring(xml).iter("mxCell"):
        geo = el.find("mxGeometry")
        cells.append({
            "id": el.get("id"), "parent": el.get("parent"), "vertex": el.get("vertex") == "1", "edge": el.get("edge") == "1",
            "source": el.get("source"), "target": el.get("target"), "style": el.get("style") or "", "value": el.get("value") or "",
            "geo": {k: geo.get(k) for k in ("x", "y", "width", "height")} if geo is not None else {},
            "sourcePoint": None, "targetPoint": None, "points": [],
        })
    return cells


def plan_of(xml: str) -> dict:
    return _run(f"wbDrawioPlan({json.dumps(cells_of(xml))})")


def vertex(id_: str, style: str, x=0, y=0, w=100, h=60, value="") -> dict:
    return {"id": id_, "parent": "1", "vertex": True, "value": value, "style": style, "geo": {"x": x, "y": y, "width": w, "height": h}}


ROOT_CELLS = [{"id": "0"}, {"id": "1", "parent": "0"}]
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 40).decode()


# --- row 1: rotation, picture, gradient, shadow ---------------------------------------------------


def test_rotation_gradient_shadow_and_a_picture_are_no_longer_dropped() -> None:
    cells = ROOT_CELLS + [
        vertex("a", "rounded=1;fillColor=#dae8fc;gradientColor=#7ea6e0;gradientDirection=east;shadow=1;rotation=30;", value="Boxed"),
        vertex("b", "text;rotation=-90;", value="Tilted"),
        vertex("c", f"shape=image;image=data:image/png,{PNG};rotation=15;", w=80, h=50),
    ]
    plan = _run(f"wbDrawioPlan({json.dumps(cells)})")
    assert plan["dropped"] == {}
    by = {i["id"]: i for i in plan["items"]}
    look = by["a"]["look"]
    assert look["gradient"] == {"to": "#7ea6e0", "dir": "e"} and look["shadow"] is True and by["a"]["rotation"] == 30
    assert by["b"]["rotation"] == 270
    assert by["c"]["kind"] == "image" and by["c"]["inline"]["mime"] == "image/png" and by["c"]["rotation"] == 15
    assert _run("WB_DRAWIO_DROPPED") == ["sketch", "glass", "comic"]


def test_an_outside_picture_address_is_still_refused_and_counted() -> None:
    plan = _run(f"wbDrawioPlan({json.dumps(ROOT_CELLS + [vertex('p', 'shape=image;image=https://example.com/a.png;')])})")
    assert plan["dropped"] == {"shape image": 1} and plan["items"][0]["kind"] == "shape"


def test_a_gradient_needs_its_fill() -> None:
    plan = _run(f"wbDrawioPlan({json.dumps(ROOT_CELLS + [vertex('a', 'gradientColor=#ffffff;')])})")
    assert "gradient" not in plan["items"][0]["look"]


def test_a_turned_shape_has_its_turn_in_its_path() -> None:
    got = _run('wbDrawioStyle.more.turn("M 0 0 L 100 0 L 100 50 L 0 50 Z", 90, 50, 25)')
    # A quarter turn about the centre swaps the box's sides: x 25..75, y -25..75.
    nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", got)]
    xs, ys = nums[0::2], nums[1::2]
    assert (min(xs), max(xs), min(ys), max(ys)) == (25, 75, -25, 75)
    data = _run('wbDrawioStyle.more.shapeData({shape: "rect", x: 0, y: 0, w: 100, h: 50, look: {}, rotation: 90}, 0, 0, "#000000")')
    assert data["shape"] == "custom"


def test_the_writer_gives_gradient_shadow_and_rotation_and_the_reader_takes_them_back() -> None:
    state = {
        "nodes": [],
        "objects": [{"id": 1, "kind": "text", "x": 0, "y": 0, "width": 120, "height": 40, "z": 1, "rotation": 45, "data": {"content": "Turned", "bg": "#ffeeaa", "shadow": True, "gradient": {"to": "#ffffff", "dir": "s"}}}],
        "sketches": [{"id": 5, "data": json.dumps({"d": "M 0 0 L 9 9", "shape": "circle", "fill": "#00ff00", "gradient": {"to": "#003300", "dir": "radial"}, "shadow": True, "box": [0, 0, 90, 60]})}],
    }
    node = f"wbBoardToDrawio({json.dumps(state)}, {{ box: (k, item) => {{ const b = JSON.parse(item.data).box; return {{ minX: b[0], minY: b[1], maxX: b[2], maxY: b[3] }}; }} }})"
    out = _run(node)
    styles = re.findall(r'style="([^"]*)" vertex', out["xml"])
    assert any("rotation=45;" in s and "shadow=1;" in s and "gradientColor=#ffffff;gradientDirection=south;" in s for s in styles), styles
    assert any("gradientColor=#003300;gradientDirection=radial;" in s and "shadow=1;" in s for s in styles), styles
    plan = plan_of(re.search(r"<mxGraphModel.*</mxGraphModel>", out["xml"], re.S).group(0))
    assert plan["dropped"] == {} and len(plan["items"]) == 2
    #: A filled text box is written (and read back) as a box.
    turned = next(i for i in plan["items"] if i["label"] == "Turned")
    assert turned["rotation"] == 45 and turned["look"]["gradient"]["dir"] == "s"
    shape = next(i for i in plan["items"] if i["label"] != "Turned")
    assert shape["look"]["gradient"] == {"to": "#003300", "dir": "radial"} and shape["look"]["shadow"] is True


# --- row 2: mxlibrary --------------------------------------------------------------------------------


def pack(xml: str) -> str:
    raw = urllib.parse.quote(xml, safe="").encode()
    comp = zlib.compressobj(wbits=-15)
    return base64.b64encode(comp.compress(raw) + comp.flush()).decode()


MODEL = ('<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
         '<mxCell id="2" value="One" style="ellipse;fillColor=#dae8fc;rotation=20;" vertex="1" parent="1"><mxGeometry x="10" y="10" width="80" height="80" as="geometry"/></mxCell>'
         '<mxCell id="3" value="Two" style="rounded=1;" vertex="1" parent="1"><mxGeometry x="200" y="10" width="80" height="40" as="geometry"/></mxCell>'
         '<mxCell id="4" value="to" style="endArrow=classic;" edge="1" parent="1" source="2" target="3"><mxGeometry relative="1" as="geometry"/></mxCell>'
         '</root></mxGraphModel>')


def test_an_mxlibrary_file_is_read_plain_or_packed() -> None:
    body = json.dumps([{"xml": MODEL, "w": 280, "h": 90, "title": "Plain"}, {"xml": pack(MODEL), "w": 280, "h": 90, "title": "Packed"}, {"data": "data:image/png;base64,AAAA", "w": 5, "h": 5}])
    text = "<mxlibrary>" + body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") + "</mxlibrary>"
    entries = _run(f"wbDrawioStyle.more.mxlibrary.read({json.dumps(text)})")
    assert [e["title"] for e in entries] == ["Plain", "Packed", ""] and entries[0]["xml"] == MODEL
    assert _run(f"wbDrawioStyle.more.mxlibrary.read({json.dumps('<mxfile/>')})") is None
    assert _run(f"wbDrawioStyle.more.inflate({json.dumps(pack(MODEL))})") == MODEL


def test_an_entry_becomes_a_library_element_the_server_accepts() -> None:
    from tessellate.api.routes_board_library import _clean_payload

    made = _run(f"wbDrawioStyle.more.payload(wbDrawioPlan({json.dumps(cells_of(MODEL))}))")
    payload = made["payload"]
    assert len(payload["items"]) == 2 and len(payload["links"]) == 1 and made["skipped"] == 0
    assert payload["box"] == {"w": 270, "h": 80}
    first = next(i for i in payload["items"] if i["kind"] == "sketch" and i["data"]["shape"] == "custom")
    assert first["data"]["color"] == "ink"
    assert _clean_payload("element", payload)["links"][0]["data"]["type"] == "link-straight"


def test_a_library_goes_out_as_an_mxlibrary_and_reads_back_with_its_shapes_and_links() -> None:
    lib = {"items": [
        {"kind": "element", "name": "Pair", "payload": _run(f"wbDrawioStyle.more.payload(wbDrawioPlan({json.dumps(cells_of(MODEL))}))")["payload"]},
        {"kind": "palette", "name": "Colours", "payload": {"colours": ["#ffffff"]}},
    ]}
    out = _run(f"wbDrawioStyle.more.mxlibrary.write({json.dumps(lib)})")
    assert out["count"] == 1 and out["left"] == 1 and out["xml"].startswith("<mxlibrary>")
    entries = _run(f"wbDrawioStyle.more.mxlibrary.read({json.dumps(out['xml'])})")
    model = _run(f"wbDrawioStyle.more.inflate({json.dumps(entries[0]['xml'])})")
    plan = plan_of(model)
    assert entries[0]["title"] == "Pair" and len(plan["items"]) == 2 and len(plan["links"]) == 1


# --- row 3: CSV -------------------------------------------------------------------------------------

CSV = """# label: %name%<br><i>%role%</i>
# style: rounded=1;whiteSpace=wrap;html=1;fillColor=%fill%;
## connect: {"from":"manager","to":"name","invert":true,"label":"manages","style":"endArrow=blockThin;"}
# width: auto
# layout: verticaltree
## a comment line
name,role,fill,manager
Ada,Lead,#dae8fc,
Bo,"Dev, senior",#d5e8d4,Ada
Cy,Dev,#d5e8d4,Ada
"""


def test_a_csv_builds_vertices_from_its_templates_and_connectors_from_connect() -> None:
    assert _run(f"wbDrawioStyle.more.csv.is({json.dumps(CSV)})") is True
    assert _run('wbDrawioStyle.more.csv.is("name,role\\nAda,Lead")') is False
    read = _run(f"wbDrawioStyle.more.csv.read({json.dumps(CSV)})")
    verts = [c for c in read["cells"] if c.get("vertex")]
    edges = [c for c in read["cells"] if c.get("edge")]
    assert [v["value"] for v in verts] == ["Ada<br><i>Lead</i>", "Bo<br><i>Dev, senior</i>", "Cy<br><i>Dev</i>"]
    assert verts[1]["style"].endswith("fillColor=#d5e8d4;")
    # invert: the manager is the source of an edge to each report.
    assert [(e["source"], e["target"], e["value"]) for e in edges] == [("csv0", "csv1", "manages"), ("csv0", "csv2", "manages")]
    plan = _run(f"wbDrawioPlan({json.dumps(read['cells'])})")
    assert len(plan["items"]) == 3 and len(plan["links"]) == 2 and plan["items"][0]["look"]["fill"] == "#dae8fc"
    assert plan["items"][0]["label"] == "Ada\nLead"
    # verticaltree: the manager above the two reports, the reports side by side.
    y = {i["id"]: i["y"] for i in plan["items"]}
    x = {i["id"]: i["x"] for i in plan["items"]}
    assert y["csv0"] < y["csv1"] == y["csv2"] and x["csv1"] != x["csv2"]


def test_a_horizontal_layout_runs_the_other_way_and_none_is_a_grid() -> None:
    flat = CSV.replace("verticaltree", "horizontaltree")
    plan = _run(f"wbDrawioPlan(wbDrawioStyle.more.csv.read({json.dumps(flat)}).cells)")
    mid = {i["id"]: i["x"] + i["w"] / 2 for i in plan["items"]}
    assert mid["csv0"] < mid["csv1"] == mid["csv2"]
    grid = _run(f"wbDrawioStyle.more.csv.read({json.dumps(CSV.replace('# layout: verticaltree', ''))})")
    assert grid["layout"] == "auto" and len({c["geo"]["y"] for c in grid["cells"] if c.get("vertex")}) == 2
    organic = _run(f"wbDrawioStyle.more.csv.read({json.dumps(CSV.replace('verticaltree', 'organic'))})")
    assert organic["dropped"] == {"layout organic": 1}


def test_a_csv_with_no_rows_is_nothing() -> None:
    assert _run('wbDrawioStyle.more.csv.read("# label: %a%\\na,b")') is None


# --- the board's own paths ----------------------------------------------------------------------------


def test_the_import_dialog_and_the_library_reach_the_new_readers() -> None:
    assert "wbDrawioStyle.more.csv.is(text)" in SOURCE and "wbImportDrawio(text, wbViewCentre(), csv)" in SOURCE
    assert "/<mxlibrary[\\s>]/i.test(text)" in LIBRARY and "wbDrawioStyle.more.mxlibrary.body" in LIBRARY
    assert "wbLibExport.drawio(lib)" in LIBRARY
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert re.search(r'id="wb-import-file" accept="[^"]*\.csv', index) and re.search(r'id="wb-lib-import" accept="[^"]*\.xml', index)


def test_a_saved_template_can_be_placed_on_the_open_board() -> None:
    assert 'entry.kind === "template" && !here' in LIBRARY and "{ here: true }" in LIBRARY


def test_an_svg_picture_is_drawn_to_png_before_upload_and_a_lost_one_is_counted() -> None:
    """Review 5883430964: `/media/upload` takes no `.svg` (MEDIA_SUFFIXES), so an inline SVG was accepted by the
    reader and then dropped without a word. It is drawn to a PNG on a canvas; one that still fails is named."""
    picture = SOURCE[SOURCE.index("async picture(") :]
    picture = picture[: picture.index("async inflate(")]
    assert 'mime === "image/svg+xml"' in picture and "svgToPng(file, box)" in picture
    assert 'canvas.toBlob(done, "image/png")' in picture
    assert '"svg"' not in picture, "no .svg ever goes to the upload"
    place = SOURCE[SOURCE.index("async function wbDrawioPlace(") :]
    place = place[: place.index("for (const item of plan.items.filter((i) => i.kind === \"text\"))")]
    assert "plan.dropped.pictures = (plan.dropped.pictures || 0) + 1" in place
    files = (ROOT / "src" / "tessellate" / "api" / "routes_files.py").read_text(encoding="utf-8")
    suffixes = files[files.index("MEDIA_SUFFIXES = frozenset(") :]
    assert '".svg"' not in suffixes[: suffixes.index(")")]
