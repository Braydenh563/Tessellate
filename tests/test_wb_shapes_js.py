"""Insert, Polygon and the JS-drawn shape classes (WHITEBOARD_PLAN sections 11 and 14): `whiteboard-shapes-js.js` is pure at its
core and run in node; the browser half is `scratchpad/ui-sweeps/wbtext3.js`."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CMDS = frontend_text("whiteboard-commands.js")


def _node(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = "const wbFmtState = {}; const window = {};\n" + frontend_text("whiteboard-shapes-js.js") + "\n" + body
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


def test_polygon_is_in_the_insert_menu_and_the_command_table():
    assert 'data-wb-cmd="insert-polygon"' in HTML
    assert re.search(r'id: "insert-polygon", group: "Insert".*polygonStart', CMDS)
    assert "/js/whiteboard-shapes-js.js" in frontend_text("lazy-entries.js")


def test_clicked_corners_close_into_one_path():
    out = _node('console.log(JSON.stringify(wbFmtState.shapesJs.polygonD([[0,0],[100,0],[50,80]])));')
    assert out == "M 0 0 L 100 0 L 50 80 Z"


def test_a_double_click_does_not_add_a_second_corner():
    out = _node('console.log(JSON.stringify(wbFmtState.shapesJs.polygonD([[0,0],[100,0],[50,80],[50,80],[50.5,80.5]])));')
    assert out == "M 0 0 L 100 0 L 50 80 Z"


def test_fewer_than_three_corners_make_nothing():
    assert _node('console.log(JSON.stringify(wbFmtState.shapesJs.polygonD([[0,0],[100,0]])));') is None
    assert _node('console.log(JSON.stringify(wbFmtState.shapesJs.polygonD([[0,0],[1,1],[2,0]])));') is None


def test_escape_cancels_enter_closes_and_the_shape_is_one_undo_step():
    src = frontend_text("whiteboard-shapes-js.js")
    assert 'event.key === "Escape"' in src and 'event.key === "Enter"' in src
    assert src.count("wbPushUndo(") == 1
