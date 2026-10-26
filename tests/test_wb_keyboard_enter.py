"""Enter places a held tool's box and edits a selected one (wbdog-1026: N then Enter did nothing, WCAG 2.1.1)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _run(tool: str, selected: dict | None, focus_id: str | None = "whiteboard-container"):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    a = WB.index("function wbKeyboardEnter(")
    b = WB.index("async function wbCreateSticky(")
    script = (
        "const calls = [];"
        f"global.window = {{ currentTool: {json.dumps(tool)}, getSelection: () => ({{ removeAllRanges() {{}}, addRange() {{}} }}) }};"
        f"const focus = {json.dumps(focus_id)} === null ? {{ id: 'wb-undo' }} : {{ id: {json.dumps(focus_id)} }};"
        "const words = {};"
        "global.document = { body: {}, activeElement: focus, querySelector: () => words, createRange: () => ({ selectNodeContents() {}, collapse() {} }) };"
        "const wbCreateTextBox = (x, y) => calls.push(['text', x, y]);"
        "const wbCreateSticky = (x, y) => calls.push(['sticky', x, y]);"
        "const wbCreateFrame = (x, y) => calls.push(['frame', x, y]);"
        "const wbViewCentre = () => [500, 300];"
        f"const wbSelectedItem = {json.dumps(selected and {'kind': 'object', 'id': 7})};"
        "const wbMultiSelection = new Set();"
        f"const wbFindItem = () => ({json.dumps(selected)});"
        "const wbIsLocked = () => false;"
        "const wbBeginTextEdit = () => calls.push(['edit']);"
        + WB[a:b]
        + "console.log(JSON.stringify({ acted: wbKeyboardEnter(), calls }));"
    )
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)


def test_a_held_placing_tool_drops_its_box_at_the_view_centre():
    assert _run("sticky", None) == {"acted": True, "calls": [["sticky", 500, 300]]}
    assert _run("text", None)["calls"] == [["text", 500, 300]]
    assert _run("frame", None)["calls"] == [["frame", 500, 300]]


def test_a_selected_text_box_takes_the_caret():
    assert _run("select", {"kind": "text", "data": {}}) == {"acted": True, "calls": [["edit"]]}


def test_an_emoji_sticker_or_a_picture_is_not_edited():
    assert _run("select", {"kind": "text", "data": {"sticker": True}})["acted"] is False
    assert _run("select", {"kind": "image", "data": {}})["acted"] is False


def test_a_focused_toolbar_button_keeps_its_own_enter():
    assert _run("sticky", None, focus_id=None) == {"acted": False, "calls": []}


def test_the_canvas_key_handler_asks_it_first():
    assert "wbKeyboardEnter()" in WB
    handler = WB[WB.index("&& !wbIsMap() && wbKeyboardEnter()") - 160 :]
    assert 'e.key === "Enter"' in handler[:260]
