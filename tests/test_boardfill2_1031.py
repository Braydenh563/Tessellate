"""INBOX 1486, second pass: the Fill colour and Fill opacity (and Line opacity)
rows reach a Mermaid diagram object, and the Fill opacity row reaches text
boxes, stickies and cards. The owner: "I should be able to make the fill
actually opaque and not partially transparent, transparency should be easily
changable as with colour". The measured Playwright numbers are in the commit
messages; the colour maths is run in node here."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
FORMAT_JS = (JS / "whiteboard-format.js").read_text(encoding="utf-8")
INTER = (JS / "whiteboard-interchange.js").read_text(encoding="utf-8")
WB = (JS / "whiteboard.js").read_text(encoding="utf-8")
DRAW = JS / "mermaid-draw.js"
SOURCE = "sequenceDiagram\n  A->>B: hi"


def _run_look(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    text = DRAW.read_text(encoding="utf-8")
    region = text[text.index("// MERMAID-LOOK-BEGIN") : text.index("// MERMAID-LOOK-END")]
    assert "document." not in region and "window." not in region
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(region + "\n" + body)
    try:
        out = subprocess.run([node, handle.name], capture_output=True, text=True, timeout=30, check=True)
    finally:
        Path(handle.name).unlink(missing_ok=True)
    return json.loads(out.stdout)


# --- the colour maths ------------------------------------------------------------

def test_a_diagram_with_no_stored_look_keeps_todays_mix():
    got = _run_look("""
const ground = [255, 255, 255], accent = [70, 100, 240];
const f = mermaidFills(ground, accent, false, null);
console.log(JSON.stringify({ soft: f.soft, softer: f.softer, note: f.note, mix: mermaidMix(ground, accent, 0.16), mix8: mermaidMix(ground, accent, 0.08) }));
""")
    assert got["soft"] == got["mix"] and got["softer"] == got["mix8"] and got["note"] == got["mix8"]


def test_a_hundred_percent_fill_is_the_colour_itself_and_zero_is_the_ground():
    got = _run_look("""
const ground = [255, 255, 255], accent = [70, 100, 240], red = [200, 30, 30];
const opaque = mermaidFills(ground, accent, false, { fill: red, fillAlpha: 1 });
const none = mermaidFills(ground, accent, false, { fillAlpha: 0 });
const half = mermaidFills(ground, accent, false, { fill: red, fillAlpha: 0.5 });
console.log(JSON.stringify({ opaque: opaque.soft, note: opaque.note, none: none.soft, half: half.soft, group: half.softer }));
""")
    assert got["opaque"] == [200, 30, 30] and got["note"] == [200, 30, 30]
    assert got["none"] == [255, 255, 255]
    assert got["half"] == [227.5, 142.5, 142.5]
    # the grouping fills (clusters, sections) stay one step lighter than the boxes
    assert got["group"] == [241.25, 198.75, 198.75]


def test_a_fill_colour_alone_takes_the_default_strength():
    got = _run_look("""
const ground = [255, 255, 255], accent = [70, 100, 240], red = [200, 30, 30];
const f = mermaidFills(ground, accent, false, { fill: red });
console.log(JSON.stringify({ soft: f.soft, want: mermaidMix(ground, red, 0.16), strongShare: mermaidFillShare(true), share: mermaidFillShare(false) }));
""")
    assert got["soft"] == got["want"] and got["share"] == 0.16 and got["strongShare"] == 0.28


def test_line_opacity_fades_toward_the_ground_and_one_is_unchanged():
    got = _run_look("""
const ground = [255, 255, 255], ink = [0, 0, 0];
console.log(JSON.stringify({ same: mermaidFaded(ground, ink, null), full: mermaidFaded(ground, ink, 1), half: mermaidFaded(ground, ink, 0.5), gone: mermaidFaded(ground, ink, 0) }));
""")
    assert got["same"] == [0, 0, 0] and got["full"] == [0, 0, 0]
    assert got["half"] == [127.5, 127.5, 127.5] and got["gone"] == [255, 255, 255]


def test_words_on_a_solid_box_keep_their_contrast():
    got = _run_look("""
const ink = [28, 28, 26], ground = [255, 255, 255];
console.log(JSON.stringify({
  none: mermaidInkOn([47, 91, 211], ink, ground, null),
  dark: mermaidInkOn([47, 91, 211], ink, ground, { fillAlpha: 1 }),
  pale: mermaidInkOn([222, 229, 248], ink, ground, { fillAlpha: 0.16 }),
  night: mermaidInkOn([240, 240, 240], [235, 235, 235], [20, 20, 24], { fillAlpha: 1 }),
}));
""")
    assert got["none"] == [28, 28, 26], "no stored look keeps the ink"
    assert got["dark"] == [255, 255, 255] and got["pale"] == [28, 28, 26]
    assert got["night"] == [20, 20, 24], "light words on a light solid box in the dark theme go dark"


# --- a diagram takes the look and draws through it ---------------------------------

def test_the_theme_and_the_drawing_take_a_look_and_key_it():
    draw = DRAW.read_text(encoding="utf-8")
    for sig in ("function mermaidTheme(look", "function mermaidThemeNow(look", "function mermaidKnown(source, look", "function mermaidRequest(source, look"):
        assert sig in draw, sig
    assert "mermaidFills(" in draw.split("function mermaidTheme(")[1].split("\n}\n")[0]
    assert "themeVariables: theme.variables" in draw


def test_the_board_asks_for_a_diagram_in_its_own_look_and_exports_that_picture():
    assert "function wbDiagramLook(" in INTER
    url = INTER.split("function wbDiagramDataUrl(")[1].split("\n}\n")[0]
    assert "wbDiagramLook(obj)" in url
    paint = INTER.split("function wbPaintDiagram(")[1].split("\n}\n")[0]
    assert "wbDiagramLook(d)" in paint
    # export reads the same already-drawn picture, so the look travels
    assert "wbDiagramDataUrl(obj)" in WB


def test_a_diagram_object_keeps_its_fill_and_opacities_through_the_server(ai_client):
    data = {"mermaid": SOURCE, "bg": "#cc3333", "bg_alpha": 1, "line_alpha": 0.5}
    made = ai_client.post("/whiteboard/objects", json={"kind": "diagram", "data": data, "x": 0, "y": 0, "width": 320, "height": 200})
    assert made.status_code in (200, 201), made.text
    got = made.json()["data"]
    assert got["bg"] == "#cc3333" and got["bg_alpha"] == 1 and got["line_alpha"] == 0.5
    obj = made.json()
    zero = ai_client.put(f"/whiteboard/objects/{obj['id']}", json={**obj, "data": {**obj["data"], "bg_alpha": 0}})
    assert zero.status_code == 200 and zero.json()["data"]["bg_alpha"] == 0
    for bad in (1.5, -0.1):
        refused = ai_client.put(f"/whiteboard/objects/{obj['id']}", json={**obj, "data": {**obj["data"], "bg_alpha": bad}})
        assert refused.status_code == 422, bad


# --- the panel rows ----------------------------------------------------------------

def _fields(kind: str) -> str:
    return re.search(rf"^  {kind}: \[(.*?)\],$", FORMAT_JS, re.M).group(1)


def test_the_fill_opacity_row_is_its_own_field_offered_to_shapes_and_diagrams():
    row = re.search(r'<div class="wb-fmt-row" data-fmt="(\w+)" role="group" aria-label="Fill opacity">', INDEX)
    assert row and row.group(1) == "fillalpha"
    for kind in ("shape", "diagram"):
        assert '"fillalpha"' in _fields(kind), kind
    for kind in ("diagram",):
        assert '"fill"' in _fields(kind) and '"strokealpha"' in _fields(kind)
    for kind in ("image", "table", "frame", "link"):
        assert '"fillalpha"' not in _fields(kind), kind
    # the hatch and gradient rows stay a shape's alone
    assert '"fillstyle"' not in _fields("text") and '"fillstyle"' not in _fields("diagram")


def test_a_diagram_is_a_kind_the_panel_knows_and_reads_its_defaults():
    kind = FORMAT_JS.split("function wbFmtKind(")[1].split("\n}\n")[0]
    assert '"diagram"' in kind
    value = FORMAT_JS.split("function wbFmtValue(")[1].split("\n}\n")[0]
    assert "bg_alpha" in value and "line_alpha" in value


def test_one_recipe_writes_the_opacity_of_a_shape_a_text_box_and_a_diagram():
    # no second recipe: the same setters and presets, a key table by item
    assert FORMAT_JS.count("const setFillAlpha") == 1 and FORMAT_JS.count("const alphaSetters") == 1
    assert "function wbFmtAlphaKeys(" in FORMAT_JS
    keys = FORMAT_JS.split("function wbFmtAlphaKeys(")[1].split("\n}\n")[0]
    assert "fillOpacity" in keys and "bg_alpha" in keys and "line_alpha" in keys
    assert INDEX.count('data-alpha-for="fillalpha"') == 5


def test_help_names_the_opacity_for_diagrams():
    topics = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8") + (
        ROOT / "src" / "tessellate" / "ai" / "help_chat.py").read_text(encoding="utf-8")
    low = topics.lower()
    assert "diagram" in low and "fill opacity" in low
