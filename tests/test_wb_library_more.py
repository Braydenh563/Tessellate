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


def test_a_drawn_table_shape_is_drawn_again_for_the_box_not_stretched_l_whiteboard_28():
    shape_table = frontend_text("whiteboard-shape-table.js")
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    body = (
        "const m = wbFmtState.libraryMore, t = wbFmtState.shapeTable, calls = [];"
        "const tile = t.shapePath('cylinder', 100, 100);"
        "const data = { d: tile, shape: 'custom', shapeKind: 'cylinder' };"
        "const box = { minX: 300, minY: 50, width: 240, height: 90 };"
        "const next = m.replaceData({ d: 'M 0 0 L 9 0 L 9 9 Z', shape: 'triangle' }, data, box, { minX: 0, minY: 0, width: 100, height: 100 }, (d, o) => { calls.push(o); return 'T'; });"
        "console.log(JSON.stringify([calls.length, next.d === t.shapePathAt('cylinder', 300, 50, 240, 90), next.shapeKind]));"
    )
    script = STAND_INS + shape_table + "\n" + frontend_text("whiteboard-library-more.js") + "\n(async () => {" + body + "})();"
    out = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)
    assert out == [0, True, "cylinder"]  # the board's stretch is never called: the table's own outline for 240 by 90


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


def test_the_search_stems_plurals_ing_ed_and_er_and_leaves_the_typed_order_alone():
    got = _run(
        "const rows = [{ name: 'Arrow', tags: [], set: 'Arrows' }, { name: 'Connector', tags: [], set: 'General' }, { name: 'Run', tags: [], set: 'General' },"
        " { name: 'Box', tags: [], set: 'General' }, { name: 'Category', tags: [], set: 'General' }, { name: 'Dashed arrow', tags: [], set: 'Arrows' }];"
        "const m = wbFmtState.libraryMore, q = (s) => m.rankEntries(rows, s).map((e) => e.name);"
        "console.log(JSON.stringify([q('arrows'), q('connecting'), q('running'), q('boxes'), q('categories'), q('dashing arrow'), q('arrow'), q('ass'), m.wordForms('arrows'), m.wordForms('cat')]));"
    )
    assert got[0] == ["Arrow", "Dashed arrow"]  # the stem finds what the plural does not
    assert got[1] == ["Connector"] and got[2] == ["Run"] and got[3] == ["Box"] and got[4] == ["Category"]
    assert got[5] == ["Dashed arrow"]
    assert got[6] == got[0]  # the unstemmed word ranks as before
    assert got[7] == []
    assert got[8] == ["arrows", "arrow"] and got[9] == ["cat"]  # a short word is left alone


def test_an_item_dropped_on_a_line_splits_it_at_the_item_ports_and_the_second_half_is_not_a_library_copy():
    got = _run(
        "const m = wbFmtState.libraryMore;"
        "const line = { type: 'link-straight', sourceId: 1, sourceKind: 'sketch', targetId: 2, targetKind: 'sketch', color: '#333', endCap: 'arrow', bend: 4, targetPoint: { x: 1, y: 2 }, library_ref: { id: 9 } };"
        "const right = m.splitPorts({ x: 0, y: 0 }, { x: 100, y: 10 }), left = m.splitPorts({ x: 100, y: 0 }, { x: 0, y: 10 });"
        "const down = m.splitPorts({ x: 0, y: 0 }, { x: 5, y: 90 }), up = m.splitPorts({ x: 0, y: 90 }, { x: 5, y: 0 });"
        "const [a, b] = m.splitData(line, 'sketch', 7, right);"
        "console.log(JSON.stringify([right, left, down, up, a, b]));"
    )
    right, left, down, up, a, b = got
    assert right == {"into": {"x": 0, "y": 0.5}, "out": {"x": 1, "y": 0.5}}
    assert left["into"] == {"x": 1, "y": 0.5} and down["into"] == {"x": 0.5, "y": 0} and up["into"] == {"x": 0.5, "y": 1}
    assert (a["sourceId"], a["targetId"], a["targetKind"], a["targetAnchor"]) == (1, 7, "sketch", right["into"])
    assert (b["sourceId"], b["targetId"], b["sourceAnchor"]) == (7, 2, right["out"])
    assert "bend" not in a and "bend" not in b and "targetPoint" not in a and a["endCap"] == b["endCap"] == "arrow"
    assert "library_ref" in a and "library_ref" not in b


def test_a_linked_copy_is_told_from_its_source_by_a_signature_of_the_payload():
    got = _run(
        "const c = wbFmtState.libraryMore.copies;"
        "const p = { box: { w: 1, h: 1 }, items: [{ data: { d: 'M 0 0' } }] }, q = { box: { w: 1, h: 1 }, items: [{ data: { d: 'M 0 1' } }] };"
        "console.log(JSON.stringify([c.sigOf(p) === c.sigOf(JSON.parse(JSON.stringify(p))), c.sigOf(p) === c.sigOf(q), typeof c.sigOf(p)]));"
    )
    assert got == [True, False, "string"]


def test_update_from_the_library_and_unlink_are_board_commands_with_a_menu_row_and_a_linked_placement():
    cmds = frontend_text("whiteboard-commands.js")
    for cid, need in (("update-from-library", "libraryCopy"), ("unlink-library", "libraryLinked")):
        row = cmds.split(f'id: "{cid}"')[1].split("\n")[0]
        assert f'needs: "{need}"' in row and 'group: "Library"' in row and 'surface: "board"' in row
    board = frontend_text("whiteboard.js")
    assert '"update-from-library"' in board and '"unlink-library"' in board and "libraryMore?.copies.refresh()" in board
    lib = frontend_text("whiteboard-library.js")
    assert "Place linked" in lib and "Shape libraries" in lib and "intoLink" in lib


def test_a_shape_set_that_is_off_is_not_fetched_listed_or_searched():
    lib = frontend_text("whiteboard-library.js")
    assert 'isOff: (key) => !["templates", "maps"].includes(key)' in lib
    assert lib.count("wbLibState.isOff(") >= 4
