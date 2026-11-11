"""F2, draw.io's shape picker and "replace a shape": the library as a search at the pointer, and a shape that takes a library outline.

`whiteboard-library-more.js` is run in node: the pure parts (what can replace a shape, the data a replaced shape has, the ranking and the
starting list) are read back as numbers; the popup itself is measured in Chromium (HISTORY, "f2-1111 batch 3")."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]

STAND_INS = "const wbFmtState = {};\n"


def _run(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = STAND_INS + frontend_text("whiteboard-library-more.js") + "\n(async () => {" + body + "})();"
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


def _entry(**over):
    entry = {
        "ref": "builtin:flowchart/process", "name": "Process", "kind": "element", "set": "Flowchart", "tags": ["step"],
        "payload": {"box": {"w": 160, "h": 80}, "links": [], "items": [{"key": "s", "kind": "sketch", "data": {"d": "M 0 0 L 160 0 L 160 80 L 0 80 Z", "shape": "custom"}}]},
    }
    entry.update(over)
    return json.dumps(entry)


def test_only_one_closed_drawing_can_stand_in_for_a_shape():
    got = _run(
        f"const r = wbFmtState.libraryMore.replacement, e = {_entry()};"
        "const clone = (f) => { const c = JSON.parse(JSON.stringify(e)); f(c); return c; };"
        "console.log(JSON.stringify([r(e) && r(e).d, r(clone((c) => { c.kind = 'shape'; })) !== null,"
        " r(clone((c) => { c.kind = 'style'; })), r(clone((c) => { c.payload.items.push(c.payload.items[0]); })),"
        " r(clone((c) => { c.payload.items[0].data.icon = 'star'; })), r(clone((c) => { c.payload.items[0].data.d = 'M 0 0 L 9 9'; })),"
        " r(clone((c) => { c.payload.items[0].kind = 'object'; })), r(clone((c) => { c.payload.links = [{}]; })), r(null)]));"
    )
    assert got == ["M 0 0 L 160 0 L 160 80 L 0 80 Z", True, None, None, None, None, None, None, None]


def test_a_replaced_shape_keeps_its_words_and_look_and_takes_the_outline_stretched_over_its_box():
    got = _run(
        "const m = wbFmtState.libraryMore, data = { d: 'M 24 0 L 160 0 L 136 80 L 0 80 Z', shape: 'custom', shapeKind: 'data', label_area: { x: 0.15, y: 0, w: 0.7, h: 1 }, color: 'red' };"
        "const calls = [];"
        "const next = m.replaceData({ d: 'M 200 100 L 400 100 L 400 220 L 200 220 Z', shape: 'rect', color: '#335599', width: 2, label: 'Hello', fill: '#eee', label_area: { x: 0, y: 0, w: 1, h: 1 }, shapeKind: 'old' },"
        " data, { minX: 200, minY: 100, width: 200, height: 120 }, { minX: 0, minY: 0, width: 160, height: 80 }, (d, o) => { calls.push(o); return 'T(' + d + ')'; });"
        "console.log(JSON.stringify([calls, next]));"
    )
    assert got[0] == [{"dx": 200, "dy": 100, "sx": 1.25, "sy": 1.5, "anchorX": 0, "anchorY": 0}]
    nxt = got[1]
    assert nxt["d"] == "T(M 24 0 L 160 0 L 136 80 L 0 80 Z)"
    # The words, colour, width and fill stay; the outline's kind and label area come from the entry (the old ones go).
    assert (nxt["label"], nxt["color"], nxt["width"], nxt["fill"]) == ("Hello", "#335599", 2, "#eee")
    assert (nxt["shape"], nxt["shapeKind"], nxt["label_area"]) == ("custom", "data", {"x": 0.15, "y": 0, "w": 0.7, "h": 1})


def test_an_entry_without_a_label_area_or_kind_leaves_none_behind():
    got = _run(
        "const m = wbFmtState.libraryMore;"
        "const next = m.replaceData({ d: 'M 0 0 L 9 0 L 9 9 Z', shape: 'triangle', label_area: { x: 0 }, shapeKind: 'old' }, { d: 'M 0 0 L 5 0 L 5 5 Z' },"
        " { minX: 0, minY: 0, width: 0, height: 0 }, { minX: 0, minY: 0, width: 0, height: 0 }, (d, o) => JSON.stringify(o));"
        "console.log(JSON.stringify(next));"
    )
    assert "label_area" not in got and "shapeKind" not in got and got["shape"] == "custom"
    #: A zero-size box is stretched by one, never by zero or infinity.
    assert json.loads(got["d"])["sx"] == 1 and json.loads(got["d"])["sy"] == 1


def test_the_search_puts_a_name_that_starts_with_the_words_first_then_the_name_then_a_tag():
    got = _run(
        "const rows = [{ name: 'Gateway, decision', tags: [], set: 'BPMN' }, { name: 'Diamond', tags: ['decision'], set: 'General' },"
        " { name: 'Decision', tags: ['choice'], set: 'Flowchart' }, { name: 'Decision (manual)', tags: [], set: 'Flowchart' }, { name: 'Process', tags: ['step'], set: 'Flowchart' }];"
        "const q = (s, n) => wbFmtState.libraryMore.rankEntries(rows, s, n).map((e) => e.name);"
        "console.log(JSON.stringify([q('decision'), q('dec'), q('flowchart step'), q('nothing'), q(''), q('decision', 2)]));"
    )
    assert got[0] == ["Decision", "Decision (manual)", "Gateway, decision", "Diamond"]
    assert got[1] == got[0]  # a prefix of a word finds the same rows
    assert got[2] == ["Process"]
    assert got[3] == [] and got[4] == []
    assert got[5] == ["Decision", "Decision (manual)"]


def test_before_anything_is_typed_the_last_placed_come_first_then_the_favourites_then_the_rest_without_a_repeat():
    got = _run(
        "const rows = ['a', 'b', 'c', 'd', 'e'].map((k) => ({ ref: 'builtin:x/' + k, name: k, favourite: k === 'd' }));"
        "const names = (recent, n) => wbFmtState.libraryMore.startEntries(rows, recent, n).map((e) => e.name);"
        "console.log(JSON.stringify([names(['builtin:x/c', 'builtin:x/zz'], 4), names([], 3), names(['builtin:x/e', 'builtin:x/e'], 9)]));"
    )
    assert got == [["c", "d", "a", "b"], ["d", "a", "b"], ["e", "d", "a", "b", "c"]]


def test_the_picker_is_a_command_in_the_insert_menu_and_the_replace_row_is_beside_change_shape():
    cmds = frontend_text("whiteboard-commands.js")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    picker = cmds.split('id: "shape-picker"')[1].split("\n")[0]
    assert 'group: "Insert"' in picker and 'surface: "board"' in picker and "libraryMore.open" in picker
    replace = cmds.split('id: "replace-library"')[1].split("\n")[0]
    assert 'needs: "swappable"' in replace and 'mode: "replace"' in replace
    assert html.count('data-wb-cmd="shape-picker"') == 1 and html.count('data-wb-cmd="replace-library"') == 1
    assert '"replace-library"' in frontend_text("whiteboard.js")  # also in the right-click Arrange list


def test_the_replace_is_one_undo_step_and_a_drag_from_a_copy_arrow_opens_the_picker_with_the_source_selected_again():
    source = frontend_text("whiteboard-library-more.js")
    assert source.count('wbPushUndo({ action: "move"') == 1
    assert "if (from) selectWbItem(from.kind, from.id);" in source
    board = frontend_text("whiteboard.js")
    assert "libraryMore?.gripPress(e, name)" in board and "async function wbCloneConnect(dirName, at = null)" in board
    assert "/js/whiteboard-library-more.js" in frontend_text("lazy-entries.js")
