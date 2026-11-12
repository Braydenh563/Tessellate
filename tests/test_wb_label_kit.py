"""F2, the Format gaps (WHITEBOARD_PLAN "Placed from INBOX, 2026-11-01", rows 1, 4, 5, 7): a shape's words get a
background and outline, a place outside the shape, a width of their own, word wrap off and spacing per side.

The rules are in `whiteboard-label.js` (a wrapped file in the `boards` bundle that adds no name to the shared scope);
whiteboard.js paints and lays out through `wbFmtState.label`. Here: the pure rules run in node, and the wiring is read.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text, script_file_text


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start) + 3]


def _kit(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    label = frontend_text("whiteboard-label.js")
    stubs = (
        _function(frontend_text("whiteboard.js"), "wbHexColour")
        + "const WB_FMT_FIELDS = { shape: [] }, WB_TEXT_LOOK_KEYS = { shape: [] }, WB_SKETCH_RESET_KEYS = [];"
        + "const wbFmtState = {}; const onSurface = () => {}; const wbCoreInkFor = (c) => (c === '#000000' ? '#fff' : '#111');"
    )
    script = stubs + label + f"\nconsole.log(JSON.stringify({expr}));"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


BOX = "{ minX: 100, minY: 50, maxX: 300, maxY: 150, width: 200, height: 100 }"
GIVEN = "{ cx: 200, cy: 100, w: 184, h: 84 }"


def test_nothing_set_changes_nothing():
    assert _kit(f"wbFmtState.label.area(wbFmtState.label.look({{}}), {GIVEN}, {BOX})") == {"cx": 200, "cy": 100, "w": 184, "h": 84}
    lk = _kit("wbFmtState.label.look({})")
    assert lk == {"pos": "", "pad": [0, 0, 0, 0], "width": 0, "wrap": True, "bg": "", "border": ""}


def test_only_named_values_are_read():
    lk = _kit(
        "wbFmtState.label.look({ label_pos: 'diagonal', label_width: 'x', label_wrap: 0, label_bg: 'red; x', label_border: '#abc', label_pad: [1, 'a', -5, 900] })"
    )
    assert lk["pos"] == "" and lk["width"] == 0 and lk["bg"] == "" and lk["border"] == "#abc"
    assert lk["wrap"] is True, "only a stored false turns wrapping off"
    assert lk["pad"] == [1, 0, 0, 80]
    assert _kit("wbFmtState.label.look({ label_wrap: false, label_width: 5000 })")["wrap"] is False
    assert _kit("wbFmtState.label.look({ label_width: 5000 })")["width"] == 2000
    assert _kit("wbFmtState.label.look({ label_width: 3 })")["width"] == 24


def test_a_width_wraps_at_its_own_number_around_the_same_centre():
    area = _kit(f"wbFmtState.label.area(wbFmtState.label.look({{ label_width: 90 }}), {GIVEN}, {BOX})")
    assert area == {"cx": 200, "cy": 100, "w": 90, "h": 84}


def test_spacing_per_side_pulls_the_band_in():
    area = _kit(f"wbFmtState.label.area(wbFmtState.label.look({{ label_pad: [10, 4, 0, 20] }}), {GIVEN}, {BOX})")
    assert area == {"cx": 208, "cy": 105, "w": 160, "h": 74}
    tiny = _kit(f"wbFmtState.label.area(wbFmtState.label.look({{ label_pad: [80, 80, 80, 80] }}), {GIVEN}, {BOX})")
    assert tiny["w"] == 24 and tiny["h"] == 0, "spacing never leaves less than a word's width"


def test_words_outside_sit_against_the_edge():
    def at(pos):
        return _kit(f"wbFmtState.label.area(wbFmtState.label.look({{ label_pos: '{pos}' }}), {GIVEN}, {BOX})")

    above, below, left, right = at("above"), at("below"), at("left"), at("right")
    # Above: the band ends 6 above the shape's top edge, and the last line sits on it.
    assert above["valign"] == "bottom" and above["cy"] + above["h"] / 2 == 50 - 6 and above["w"] == 200
    assert below["valign"] == "top" and below["cy"] - below["h"] / 2 == 150 + 6
    # Left and right hug the shape and wrap at 120.
    assert left["align"] == "right" and left["cx"] + left["w"] / 2 == 100 - 6 and left["w"] == 120 and left["cy"] == 100
    assert right["align"] == "left" and right["cx"] - right["w"] / 2 == 300 + 6
    narrow = _kit(f"wbFmtState.label.area(wbFmtState.label.look({{ label_pos: 'above' }}), {GIVEN}, {{ minX: 0, minY: 0, maxX: 40, maxY: 40, width: 40, height: 40 }})")
    assert narrow["w"] == 96, "a small shape still gives its words room"


def test_the_editor_opens_where_the_words_are():
    inside = _kit(f"wbFmtState.label.editBox(wbFmtState.label.look({{}}), {GIVEN}, {BOX})")
    assert inside == {"x": 108, "y": 50, "w": 184, "h": 100}
    above = _kit(f"wbFmtState.label.editBox(wbFmtState.label.look({{ label_pos: 'above' }}), {GIVEN}, {BOX})")
    assert above["y"] + above["h"] == 50 - 6
    below = _kit(f"wbFmtState.label.editBox(wbFmtState.label.look({{ label_pos: 'below' }}), {GIVEN}, {BOX})")
    assert below["y"] == 150 + 6


def test_the_look_joins_the_panels_lists():
    out = _kit("[WB_FMT_FIELDS.shape, WB_TEXT_LOOK_KEYS.shape, WB_SKETCH_RESET_KEYS, Object.keys(wbFmtState.label).sort()]")
    keys = ["label_bg", "label_border", "label_pos", "label_width", "label_wrap", "label_pad"]
    assert out[0] == [] and out[1] == keys and out[2] == keys
    assert out[3] == ["KEYS", "area", "backdrop", "drop", "editBox", "look", "paint", "sync"]


def test_the_ink_follows_the_colour_behind_the_words():
    assert _kit("(() => { const l = { style: {} }; wbFmtState.label.paint(l, { label_bg: '#000000' }); return l.style.fill; })()") == "#fff"
    assert _kit("(() => { const l = { style: {} }; wbFmtState.label.paint(l, { label_bg: '#000000', label_color: '#ff0000' }); return l.style.fill ?? null; })()") is None, "a chosen ink wins"
    assert _kit("(() => { const l = { style: {} }; wbFmtState.label.paint(l, {}); return l.style.fill === undefined; })()") is True


def test_the_board_paints_and_lays_out_through_the_kit():
    board = frontend_text("whiteboard.js")
    layout = _function(board, "wbLayoutShapeLabel")
    assert "label.__wbLook?.wrap === false ? Infinity : area.w" in layout
    assert "wbFmtState.label?.backdrop(groupEl, label)" in layout
    assert "area.align || label.dataset.align" in layout and "area.valign ? area.valign ===" in layout
    paint = _function(board, "wbPaintShapeLabel")
    assert "wbFmtState.label?.paint(label, parsed)" in paint and "wbFmtState.label?.drop(groupEl)" in paint
    assert "wbFmtState.label?.area(label.__wbLook, area, bbox)" in _function(board, "wbShapeLabelPlace")
    assert '"shapelabel"' in frontend_text("whiteboard-format.js")
    assert "kit.editBox(kit.look(parsed)" in _function(board, "wbEditShapeLabel")
    # Words outside the shape are not a reason to grow it.
    assert "!parsed.label_pos" in board
    # A drag moves the box with the words, on both paths a move takes.
    assert ".sketch-label-bg" in _function(board, "wbNudgeShapeLabel")
    assert "entry.labelBgEl?.setAttribute" in _function(board, "wbApplyBulkMove")
    assert "label_pos" in _function(frontend_text("whiteboard-format.js"), "wbGrowShapeToLabel")


def test_the_panel_has_every_row_with_help_and_a_script_to_wire_them():
    html = frontend_text("index.html")
    for ident in (
        "wb-fmt-lbg-on", "wb-fmt-lbg", "wb-fmt-lborder-on", "wb-fmt-lborder", "wb-fmt-lpos", "wb-fmt-lwidth", "wb-fmt-lwrap",
        "wb-fmt-lpad0", "wb-fmt-lpad1", "wb-fmt-lpad2", "wb-fmt-lpad3",
    ):
        assert f'id="{ident}"' in html, ident
    assert 'data-help-for="wb-fmt-help-shapelabel"' in html and 'id="wb-fmt-help-shapelabel"' in html
    for word in ("Background, Outline", "Position", "Width", "Wrap words", "Spacing"):
        assert f"<b>{word}</b>" in html, word
    entries = frontend_text("lazy-entries.js")
    assert entries.index("whiteboard-format.js") < entries.index("whiteboard-label.js") < entries.index("whiteboard-interchange.js")
    label = frontend_text("whiteboard-label.js")
    for ident in ("wb-fmt-lbg", "wb-fmt-lborder", "wb-fmt-lpos", "wb-fmt-lwidth", "wb-fmt-lwrap", "wb-fmt-lpad"):
        assert ident in label, ident
    assert "wbFmtState.label?.sync(takes, sharing)" in frontend_text("whiteboard-format.js")


def test_the_file_adds_no_name_to_the_shared_scope():
    from tests import _js_scope

    assert _js_scope.is_wrapped(script_file_text("whiteboard-label.js"))
    assert _js_scope.global_names(script_file_text("whiteboard-label.js")) == set()
