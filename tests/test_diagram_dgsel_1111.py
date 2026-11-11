"""INBOX 1740 (dgsel-1111): the diagram picture picks as the whiteboard does.

Plain drag on empty picture is a marquee (Shift or Ctrl adds), Shift+click toggles a block, Ctrl+Arrow extends the pick from
the keyboard, Escape clears; a mouse pan moved to Space+drag and the middle button (touch keeps its one-finger pan). The
geometry is run under node; the wiring is read for what it must hold; the measured picks are in the remaining list."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CANVAS = (JS / "diagram-canvas.js").read_text(encoding="utf-8")
VIEW = (JS / "diagram-view.js").read_text(encoding="utf-8")
MULTI = (JS / "diagram-multi.js").read_text(encoding="utf-8")
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _math(expr: str):
    script = (
        "const vm=require('vm');const ctx={diagramModel:{}};vm.createContext(ctx);"
        f"vm.runInContext(require('fs').readFileSync({json.dumps(str(JS / 'diagram-canvas.js'))},'utf8'),ctx);"
        f"const m=ctx.diagramModel.canvas.math;process.stdout.write(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_a_marquee_replaces_the_pick_and_an_added_one_keeps_it_in_order():
    assert _math("m.merge(['n:a','n:b'], ['n:c'], false)") == ["n:c"]
    assert _math("m.merge(['n:a','n:b'], ['n:b','n:c'], true)") == ["n:a", "n:b", "n:c"]
    assert _math("m.merge([], ['n:c'], true)") == ["n:c"]


@needs_node
def test_a_press_is_a_drag_only_past_a_few_pixels():
    assert _math("[m.dragged(0,0,3,0), m.dragged(0,0,3,4), m.dragged(10,10,10,16)]") == [False, True, True]


def test_a_plain_mouse_drag_on_empty_space_is_the_marquee_and_touch_is_left_to_the_pan():
    assert "!event.shiftKey ||" not in CANVAS.split("fig.addEventListener(\"pointerdown\"")[1].split("}, true);")[0]
    assert 'pointerType === "touch"' in CANVAS
    assert "event.button !== 0" in CANVAS


def test_the_pan_moved_to_space_and_the_middle_button():
    assert "event.button !== 1" in VIEW
    assert "S.hand" in CANVAS and "dgm-hand" in CANVAS and ".dgm-hand" in CSS


def test_shift_click_on_a_drawn_block_toggles_it_in_the_shared_pick():
    assert "S.pickAt = (key) => toggle(key)" in MULTI
    assert "S.pickAt(key)" in BUILDER and "event.shiftKey && !(" not in BUILDER


def test_the_marquee_adds_to_the_pick_with_shift_or_ctrl_and_an_empty_one_clears():
    assert "shiftKey || event.ctrlKey || event.metaKey" in CANVAS
    assert "math.merge(" in CANVAS and "S.clear()" in CANVAS


def test_ctrl_arrow_extends_the_pick_from_the_picture():
    assert "diagramModel.view.math.reach" in CANVAS
    assert "ctrlKey || event.metaKey" in CANVAS and "Arrow" in CANVAS


def test_the_help_says_the_new_gestures():
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-builder"))
    assert "drag on empty space" in body and "Shift adds" in body and "Space and drag" in body
    sheet = (JS / "diagram-style.js").read_text(encoding="utf-8")
    for row in ("Drag on empty picture", "Space + drag on the picture", "Ctrl + arrows on the picture", "Shift + click on a block"):
        assert row in sheet
