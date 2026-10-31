"""INBOX 1486: a fill and a line with an opacity of their own, a press inside a
selection's bounds that drags the selection, and a drawing tool's cursor that
holds over every item. Static checks on the sources, plus the one round trip
the server owns; the measured Playwright numbers are in the commit message."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
FORMAT_JS = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
INTERCHANGE_JS = (ROOT / "frontend" / "js" / "whiteboard-interchange.js").read_text(encoding="utf-8")
WB_CSS = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
#: What only the board draws is in the lazy bundle's sheet, out of the boot budget.
LAZY_CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def _wb_js() -> str:
    return (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


# --- opacity of the fill and of the line ----------------------------------------

def test_fill_and_line_opacity_have_a_slider_that_reaches_zero():
    for name in ("fillalpha", "strokealpha"):
        tag = re.search(rf'<input type="range" id="wb-fmt-{name}"[^>]*>', INDEX)
        assert tag, name
        assert 'min="0"' in tag.group(0) and 'max="100"' in tag.group(0), tag.group(0)


def test_fill_and_line_opacity_have_the_five_presets():
    for name in ("fillalpha", "strokealpha"):
        got = re.findall(rf'data-alpha-for="{name}" data-alpha-preset="(\d+)"', INDEX)
        assert got == ["0", "25", "50", "75", "100"], (name, got)


def test_a_zero_percent_slider_is_not_read_as_a_hundred():
    # `Number(0) || 100` turned "see through" into "solid" the moment it was chosen.
    line = next(row for row in FORMAT_JS.splitlines() if "const alphaPct" in row)
    assert "|| 100" not in line and "Number.isFinite" in line
    assert "Math.max(5," not in FORMAT_JS.split("const setFillAlpha")[1][:900]


def test_the_line_opacity_row_is_offered_to_shapes_and_lines_and_stored_as_opacity():
    for kind in ("shape", "line", "arrow"):
        row = re.search(rf"^  {kind}: \[(.*?)\],$", FORMAT_JS, re.M).group(1)
        assert '"strokealpha"' in row, kind
    assert 'case "strokealpha"' in FORMAT_JS
    assert re.search(r'wbFmtApply\("strokealpha"[^;]*opacity:', FORMAT_JS)


def test_opacity_travels_with_a_copied_style_and_a_reset():
    src = _wb_js()
    for const in ("WB_SKETCH_STYLE_KEYS", "WB_SKETCH_RESET_KEYS"):
        body = src.split(f"const {const} = [")[1].split("];")[0]
        assert '"opacity"' in body, const


def test_the_drawio_file_carries_both_opacities_out_and_in():
    assert "fillOpacity=" in INTERCHANGE_JS and "strokeOpacity=" in INTERCHANGE_JS
    look = INTERCHANGE_JS.split("function wbDrawioLook(s)")[1].split("\n}\n")[0]
    assert "s.fillOpacity" in look and "s.strokeOpacity" in look


def test_a_shape_keeps_its_opacities_through_the_server(client):
    board = client.post("/whiteboard/boards", json={"name": "Fill", "type": "board"}).json()
    data = {"d": "M 0 0 L 10 0 L 10 10 Z", "shape": "rect", "color": "#22aa66", "width": 3,
            "fill": "#22aa66", "fillOpacity": 0, "opacity": 0.5}
    made = client.post("/whiteboard/sketches", json={"data": json.dumps(data), "x": 0, "y": 0, "z": 1, "board_id": board["id"]})
    assert made.status_code in (200, 201), made.text
    row = made.json()
    changed = {**data, "fillOpacity": 0.25, "opacity": 0}
    again = client.put(f"/whiteboard/sketches/{row['id']}", json={"data": json.dumps(changed)})
    assert again.status_code == 200, again.text
    for body in (row, again.json()):
        got = json.loads(body["data"])
        assert got["fillOpacity"] in (0, 0.25) and got["opacity"] in (0.5, 0)
    assert json.loads(again.json()["data"])["opacity"] == 0


def test_the_help_names_the_new_rows():
    topics = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8") + (
        ROOT / "src" / "tessellate" / "ai" / "help_chat.py").read_text(encoding="utf-8")
    assert "line opacity" in topics.lower()


# --- a press inside a selection's bounds ------------------------------------------

def test_a_press_inside_the_selections_bounds_drags_the_whole_selection():
    src = _wb_js()
    assert "function wbPointInSelectionBounds(" in src
    down = src.split('containerEl.addEventListener("pointerdown", (e) => {\n    //: A new press is a new gesture')[1].split("\n  });")[0]
    assert "wbPointInSelectionBounds(" in down and "pending: true, place, move" in down


def test_a_click_inside_the_bounds_does_not_clear_the_selection():
    src = _wb_js()
    click = src.split('containerEl.addEventListener("click", (e) => {')[1].split("// A text box is placed by clicking")[0]
    assert "wbPointInSelectionBounds(" in click


def test_the_selection_drag_ends_in_one_undo_step():
    src = _wb_js()
    assert "function wbEndSelectionDrag(" in src
    body = src.split("function wbEndSelectionDrag(")[1].split("\n  }\n")[0]
    assert "wbFinishDrag(null," in body


# --- a drawing tool's cursor holds over every item --------------------------------

def test_a_drawn_shape_hands_the_cursor_back_to_the_tool():
    src = _wb_js()
    enter = src.split('.attr("class", "sketch-group")')[1][:400]
    assert '.style("cursor"' not in enter, "an inline cursor written once, at creation, outlives the tool"
    rule = re.search(r'#whiteboard-container:not\(\[data-current-tool="select"\]\):not\(\[data-current-tool="pan"\]\)\s*:is\(([^)]*)\)\s*\{\s*cursor: inherit;', WB_CSS)
    # the path and hit band inherit it from their group, which has no cursor of its own now
    assert rule and ".sketch-group" in rule.group(1)
    assert re.search(r'\[data-current-tool="select"\][^{]*\.sketch-group[^{]*\{\s*cursor: pointer', LAZY_CSS)


def test_the_opacity_presets_are_styled_by_the_lazy_sheet_not_boot_css():
    assert ".wb-fmt-presets button" in LAZY_CSS and ".wb-fmt-presets" not in WB_CSS
