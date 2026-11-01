"""INBOX 1509: Ctrl/Cmd zoom on the board, as InDesign has it.

The owner, 2026-11-01: "I want to be able to ctrl +/- to zoom out and zoom in
foccused on selected objects ot in general on the whiteboard if focused on it
like with adobe indesign". Measured before (agent board-1101): one Ctrl+= on
the board zoomed the board 1.2x and the whole app from 100% to 105%, because
the app zoom's capture listener (settings-panes.js) took the same key; Ctrl+1
did nothing. `wbZoomKey` runs on `window`, capturing, so it is first: while the
board has the focus it takes the key and stops it; while typing, or with a
dialog open, it leaves the key to the app zoom.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text


def _function(name: str) -> str:
    source = frontend_text("whiteboard.js")
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start) + 3]


def _const(name: str) -> str:
    source = frontend_text("whiteboard.js")
    start = source.index(f"const {name} = {{")
    return source[start : source.index("\n};\n", start) + 4]


def test_it_runs_first_and_the_old_bubbling_copy_is_gone():
    text = frontend_text("whiteboard.js")
    assert 'window.addEventListener("keydown", wbZoomKey, true);' in text
    assert 'e.code === "Digit0"' not in text and "wbZoomStep(1.2);" not in text
    assert "wbZoom.scaleTo, 1, wbZoomAnchor({ usePointer: false })" in _function("wbZoomTo100")


SCRIPT = r"""
const ran = [];
global.wbZoomStep = (f, o) => ran.push(`step ${f} ${o.usePointer}`);
global.wbZoomToFit = () => ran.push("fit");
global.wbZoomTo100 = () => ran.push("100");
const view = { classList: { contains: () => false }, getClientRects: () => [1], contains: (el) => el.inView };
let dialog = null;
global.document = {
  body: { tagName: "BODY" },
  activeElement: null,
  getElementById: () => view,
  querySelector: () => dialog,
};
__CODE__
const press = (code, mods = {}) => {
  const e = { code, ctrlKey: true, metaKey: false, altKey: false, shiftKey: false, ...mods, prevented: false, stopped: false,
    preventDefault() { this.prevented = true; }, stopPropagation() { this.stopped = true; } };
  ran.length = 0;
  wbZoomKey(e);
  return { ran: ran.slice(), taken: e.prevented && e.stopped };
};
const out = {};
document.activeElement = document.body;
out.plus = press("Equal");
out.cmdMinus = press("Minus", { ctrlKey: false, metaKey: true });
out.zero = press("Digit0");
out.one = press("Digit1");
out.shiftOne = press("Digit1", { shiftKey: true });
out.plainEqual = press("Equal", { ctrlKey: false });
document.activeElement = { tagName: "TEXTAREA", inView: true, isContentEditable: false };
out.typing = press("Equal");
document.activeElement = { tagName: "DIV", inView: true, isContentEditable: true };
out.editingBox = press("Equal");
document.activeElement = { tagName: "BUTTON", inView: true, isContentEditable: false };
out.boardButton = press("Equal");
document.activeElement = { tagName: "BUTTON", inView: false, isContentEditable: false };
out.outside = press("Equal");
document.activeElement = document.body;
dialog = {};
out.dialog = press("Equal");
console.log(JSON.stringify(out));
"""


def test_the_keys_zoom_the_board_only_while_it_has_the_focus():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    code = "\n".join([_const("WB_ZOOM_KEYS"), _function("wbBoardHasFocus"), _function("wbZoomKey")])
    out = subprocess.run([node, "-e", SCRIPT.replace("__CODE__", code)], capture_output=True, text=True, timeout=30, check=True)
    r = json.loads(out.stdout)
    assert r["plus"] == {"ran": ["step 1.2 false"], "taken": True}
    assert r["cmdMinus"] == {"ran": ["step 0.8 false"], "taken": True}
    assert r["zero"] == {"ran": ["fit"], "taken": True}
    assert r["one"] == {"ran": ["100"], "taken": True}
    for left in ("shiftOne", "plainEqual", "typing", "editingBox", "outside", "dialog"):
        assert r[left] == {"ran": [], "taken": False}, left
    assert r["boardButton"]["taken"] is True
