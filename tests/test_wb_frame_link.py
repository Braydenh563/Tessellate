"""F2, draw.io's link to a page (`data:page/id,`): a shape's `link` may be `frame:<id>`, because a frame is a page on this board
(WHITEBOARD_PLAN decision 22). Its mark opens it with `wbPageGo`, shows the frame's title, and goes when the frame does.

The module's own functions run in node against small stand-ins; the board's hooks are checked in whiteboard.js's text."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests import _js_scope
from tests._app_js import frontend_text, script_file_text

ROOT = Path(__file__).resolve().parents[1]
WB = frontend_text("whiteboard.js")


def _function(name: str) -> str:
    start = WB.index(f"function {name}(")
    return WB[start : WB.index("\n}\n", start) + 3]


def _node(script: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


STAND_INS = (
    "const wbFmtState = {}; const onSurface = () => {};"
    "const wbState = { objects: [{ id: 20, kind: 'frame', title: 'Intro' }, { id: 21, kind: 'frame', title: 'Plan' }, { id: 22, kind: 'image' }] };"
    "const wbFrameTitle = (f) => f.title; const wbFramesInOrder = () => wbState.objects.filter((o) => o.kind === 'frame');"
    "const makeMenuItem = (label, title, run) => ({ label, title, run }); const opened = [];"
    "const openMenuAtPoint = (items, label, x, y) => opened.push({ items, label, x, y });"
)


def _module(body: str):
    return _node(STAND_INS + frontend_text("whiteboard-draw-more.js") + "\nconst m = wbFmtState.drawMore;\n" + body)


def test_a_frame_link_names_a_frame_of_this_board_and_nothing_else():
    got = _module(
        "console.log(JSON.stringify([m.frameOf('frame:21'), m.frameOf('frame:22'), m.frameOf('frame:99'), m.frameOf('frame:'), m.frameOf('https://x.test'), m.frameOf(undefined)]));"
    )
    assert got == [{"id": 21, "kind": "frame", "title": "Plan"}, None, None, None, None, None]


def test_the_marks_words_are_the_frames_title_and_empty_for_any_other_link():
    got = _module("console.log(JSON.stringify([m.linkWords('frame:20'), m.linkWords('#/notes/3'), m.linkWords('frame:99')]));")
    assert got == ["Intro", "", ""]


def test_the_link_menu_row_lists_the_frames_and_sets_the_one_picked():
    got = _module(
        "const set = []; const row = m.pageLinkItem((link) => set.push(link), 10, 20);"
        "row.run();"
        "setTimeout(() => { const menu = opened[0]; menu.items[1].run();"
        "  console.log(JSON.stringify({ row: row.label, label: menu.label, at: [menu.x, menu.y], items: menu.items.map((i) => i.label), set })); }, 20);"
    )
    assert got["row"].endswith("A page of this board…")
    assert got["label"] == "Pages" and got["at"] == [10, 20]
    assert [i.split(" ", 1)[1] for i in got["items"]] == ["Intro", "Plan"]
    assert got["set"] == ["frame:21"]


def test_a_board_with_no_frame_offers_no_row():
    got = _module("wbState.objects.length = 0; console.log(JSON.stringify(m.pageLinkItem(() => {}, 0, 0)));")
    assert got is None


def test_the_board_reads_opens_and_paints_the_link_through_the_module():
    item = _function("wbItemLink")
    assert "wbFmtState.drawMore?.frameOf(link)" in item
    opener = _function("wbOpenItemLink")
    assert "const page = wbFmtState.drawMore?.frameOf(link);" in opener and "wbPageGo(page.id)" in opener
    marks = _function("wbPaintLinkMarks")
    assert "wbFmtState.drawMore?.linkWords(link)" in marks and "ph-presentation" in marks
    editor = _function("wbEditItemLink")
    assert "wbFmtState.drawMore?.pageLinkItem(" in editor


def test_the_module_is_still_one_wrapped_file_with_no_globals():
    src = script_file_text("whiteboard-draw-more.js")
    assert _js_scope.is_wrapped(src) and _js_scope.global_names(src) == set()
