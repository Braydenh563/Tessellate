"""The board's finishing effects (LEDGER L-whiteboard-37, 38, 40 and 47): text shadow, glass, a picture as a shape's fill,
a mirror for a sticky, a picture or a frame, frame opacity and a status bar. `whiteboard-effects.js` is run in node for its
pure parts; the drawn half is measured by `scratchpad/ui-sweeps/wbeffects.js`."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tessellate.api.routes_whiteboard import WhiteboardObjectData
from tessellate.api.wb_model import check_sketch_data
from tessellate.core.validation_copy import Said
from tests._app_js import frontend_text


def _node(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = "const wbFmtState = {}; const onSurface = () => {};\n" + frontend_text("whiteboard-effects.js") + "\n" + body
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


# --- L-whiteboard-38: text shadow ------------------------------------------------------------------------------
def test_text_shadow_is_a_flag_the_server_keeps():
    assert WhiteboardObjectData(text_shadow=True).text_shadow is True
    assert WhiteboardObjectData().text_shadow is None


def test_a_boxs_words_take_text_shadow_and_a_shapes_svg_label_takes_a_drop_shadow():
    out = _node(
        "const f = wbFmtState.effects.textShadowStyle;"
        "console.log(JSON.stringify([f(false, true), f(true, true), f(false, false), f(true, false)]));"
    )
    assert out[0]["textShadow"].startswith("1px 1px") and out[0]["filter"] == ""
    assert out[1]["textShadow"] == "" and out[1]["filter"].startswith("drop-shadow(")
    assert out[2] == out[3] == {"textShadow": "", "filter": ""}


def test_the_panel_has_the_switch_with_help_and_the_board_paints_it():
    html = frontend_text("index.html")
    assert 'id="wb-fmt-tshadow"' in html and "<b>Text shadow</b>" in html
    fmt = frontend_text("whiteboard-format.js")
    assert '"tshadow"' in fmt and 'case "tshadow": case "glass": case "fillimg"' in fmt
    board = frontend_text("whiteboard.js")
    assert "wbFmtState.effects?.paintObject(this, d)" in board and "wbFmtState.effects?.paintShape(this, shapeData, pathData, d.id)" in board
    effects = frontend_text("whiteboard-effects.js")
    assert '"label_shadow" : "text_shadow"' in effects


def test_a_reset_of_the_words_look_clears_the_shadow():
    # Clear formatting must take the shadow off with the rest of the text look.
    fmt = frontend_text("whiteboard-format.js")
    assert '"label_shadow", "label_dir", "label_alpha"' in fmt and '"text_shadow", "text_dir", "text_alpha"' in fmt
    board = frontend_text("whiteboard.js")
    assert '"label_dir", "label_alpha",\n];' in board and '"glass", "fill_image"' in board and '"text_shadow", "text_dir", "text_alpha", "alpha",' in board


# --- L-whiteboard-37: glass --------------------------------------------------------------------------------------
def test_glass_is_a_shape_field_next_to_shadow():
    fmt = frontend_text("whiteboard-format.js")
    assert '"glass"' in fmt.split("const WB_FMT_FIELDS")[1].split("\n  line:")[0]
    html = frontend_text("index.html")
    assert html.index('id="wb-fmt-shadow"') < html.index('id="wb-fmt-glass"') < html.index('id="wb-fmt-help-box"')
    assert "<b>Glass</b>" in html
    assert 'box.checked = value(sharing[0], field) === true' in frontend_text("whiteboard-effects.js")


def test_glass_is_stored_only_as_a_flag():
    assert check_sketch_data(json.dumps({"d": "M 0 0 L 10 0 L 10 10 Z", "glass": True}))
    with pytest.raises(Said):
        check_sketch_data(json.dumps({"d": "M 0 0 L 10 0 L 10 10 Z", "glass": "url(#x)"}))


def test_the_gloss_is_built_from_attributes_and_takes_no_click():
    src = frontend_text("whiteboard-effects.js")
    assert "innerHTML" not in src and "insertAdjacentHTML" not in src and 'setAttribute("style"' not in src
    assert '"pointer-events": "none"' in src


# --- L-whiteboard-40: a picture as a shape's fill ----------------------------------------------------------------
def test_only_a_saved_media_address_may_fill_a_shape():
    base = {"d": "M 0 0 L 10 0 L 10 10 Z"}
    assert check_sketch_data(json.dumps({**base, "fill_image": "/media/abc123.png"}))
    for bad in ("https://example.com/x.png", "/media/../../etc/passwd", "data:image/png;base64,AAAA", "javascript:alert(1)", 7):
        with pytest.raises(Said):
            check_sketch_data(json.dumps({**base, "fill_image": bad}))


def test_the_picture_fill_row_reuses_the_upload_and_clips_to_the_outline():
    html = frontend_text("index.html")
    for ident in ("wb-fmt-fillimg", "wb-fmt-fillimg-clear", "wb-fmt-fillimg-file"):
        assert f'id="{ident}"' in html, ident
    assert "<b>Picture fill</b>" in html
    src = frontend_text("whiteboard-effects.js")
    assert '"/media/upload"' in src and 'body.append("board", "true")' in src
    assert '"clip-path": `url(#${clipId})`' in src and "MEDIA.test(url)" in src


# --- L-whiteboard-47: mirror, frame opacity, status bar ----------------------------------------------------------
def test_flip_words_and_the_mirror_of_a_box_about_a_frame():
    out = _node(
        "const e = wbFmtState.effects;"
        "const frame = { minX: 0, maxX: 100, minY: 0, maxY: 60 };"
        "console.log(JSON.stringify([e.flipWord({}), e.flipWord({ flip_x: true }), e.flipWord({ flip_y: true }), e.flipWord({ flip_x: true, flip_y: true }),"
        "e.mirrorShift({ minX: 10, maxX: 30, minY: 5, maxY: 15 }, frame, 'h'), e.mirrorShift({ minX: 10, maxX: 30, minY: 5, maxY: 15 }, frame, 'v')]));"
    )
    assert out[:4] == ["", "x", "y", "xy"]
    # A box 10..30 across a 0..100 frame lands on 70..90: it moves 60 to the right, and not at all up or down.
    assert out[4] == {"dx": 60, "dy": 0} and out[5] == {"dx": 0, "dy": 40}


def test_flip_is_on_notes_pictures_and_frames_and_a_frame_takes_opacity():
    fmt = frontend_text("whiteboard-format.js")
    fields = fmt.split("const WB_FMT_FIELDS")[1].split("};")[0]
    for kind in ("text", "image", "frame"):
        row = next(line for line in fields.splitlines() if line.strip().startswith(f"{kind}:"))
        assert '"flip"' in row, kind
    frame = next(line for line in fields.splitlines() if line.strip().startswith("frame:"))
    assert '"alpha"' in frame
    assert "wbFmtState.effects?.flipObjects(axis, objects)" in fmt


def test_a_flipped_note_turns_the_card_not_the_words():
    css = frontend_text("library-lazy.css") if False else open("frontend/css/library-lazy.css", encoding="utf-8").read()
    assert '.wb-object-text.wb-sticky[data-flip~="x"]::after' in css
    # Nothing in the paint touches the text's own transform.
    src = frontend_text("whiteboard-effects.js")
    assert "scaleX" not in src and "scale(-1" not in src


def test_the_status_bar_says_zoom_tool_and_selection():
    out = _node("const f = wbFmtState.effects.statusParts; console.log(JSON.stringify([f(100, 'Select', 0), f(149.6, 'Draw', 3), f(50, '', 1)]));")
    assert out == [["100%", "Select", "Nothing selected"], ["150%", "Draw", "3 selected"], ["50%", "Select", "1 selected"]]


def test_the_status_bar_is_a_plain_dock_off_by_default_behind_a_view_toggle():
    html = frontend_text("index.html")
    bar = html[html.index('id="wb-status-bar"') - 20 : html.index('id="wb-status-bar"') + 200]
    assert "dock wb-status-bar hidden" in bar and "data-dock-name" not in bar and "glass" not in bar
    assert 'id="wb-view-status"' in html and "<input type=\"checkbox\" id=\"wb-view-status\">" in html
    src = frontend_text("whiteboard-effects.js")
    assert 'prefs.get(STATUS_PREF, null) === "on"' in src
    board = frontend_text("whiteboard.js")
    assert board.count("wbFmtState.effects?.refreshStatus()") == 3


def test_the_file_is_in_the_boards_bundle():
    assert "/js/whiteboard-effects.js" in frontend_text("lazy-entries.js")


def test_an_exported_label_keeps_its_shadow_and_loses_the_rest_of_its_style():
    out = _node(
        "const mk = (style) => ({ style: { filter: style } });"
        "const on = mk('drop-shadow(1px 1px 1px rgb(0 0 0 / 0.5))'), off = mk('');"
        "wbFmtState.effects.keepShadow(on, on); wbFmtState.effects.keepShadow(off, off);"
        "const c1 = mk(''), c2 = mk(''); wbFmtState.effects.keepShadow(on, c1); wbFmtState.effects.keepShadow(off, c2); console.log(JSON.stringify([c1.style, c2.style]));"
    )
    assert out[0] == {"filter": "drop-shadow(1px 1px 1px rgb(0 0 0 / 0.5))"} and out[1] == {"filter": ""}
    board = frontend_text("whiteboard.js")
    assert board.index('copy.removeAttribute("style");') < board.index("wbFmtState.effects?.keepShadow(label, copy)")
