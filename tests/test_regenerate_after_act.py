"""Regenerate after an act ran (sm-1111 row 16): a card Confirmed in the answer marks that
answer as one that wrote, so Regenerate asks before sending the act sentence again (a second
note or reminder), as it already does for an act that ran at once."""

import json
import re
import shutil
import subprocess

import pytest

from tests._app_js import JS_DIR

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _confirm_marks_bubble() -> dict:
    src = (JS_DIR / "ask-compose.js").read_text(encoding="utf-8")
    match = re.search(r"^function renderActCard\(.*?^\}", src, re.S | re.M)
    assert match, "renderActCard is gone"
    script = f"""
const bubble = {{ dataset: {{}} }};
const mkEl = () => {{ const el = {{ dataset: {{}}, childElementCount: 1, classList: {{ add() {{}} }},
  append() {{}}, appendChild() {{}}, setAttribute() {{}}, replaceChildren() {{}}, replaceWith() {{}},
  get childNodes() {{ return []; }}, closest: (sel) => (sel === ".msg" ? bubble : null) }}; return el; }};
const document = {{ createElement: mkEl, querySelectorAll: () => [] }};
const buttons = {{}};
const smallButton = (label, _t, onClick) => {{ buttons[label] = onClick; return mkEl(); }};
const setLabel = () => {{}}, toolChip = mkEl, chatScrollToEnd = () => {{}}, toast = () => {{}};
const chatHistoryToSend = {{ settle() {{}} }}, refreshAfterToolChanges = () => {{}}, pushUndo = () => ({{}}), settleUndoFromToast = () => {{}};
const apiJson = async () => ({{ summary: "Done: made a note", undo: [] }});
const applyThemeSteps = (_steps, result) => result;
{match.group(0)}
renderActCard(mkEl(), {{ type: "act", label: "Make a note", notice: "n", steps: [{{}}] }});
const before = bubble.dataset.wrote || "";
buttons.Confirm();
setTimeout(() => process.stdout.write(JSON.stringify({{ before, after: bubble.dataset.wrote || "" }})), 20);
"""
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_confirming_an_act_card_marks_its_answer_as_written():
    got = _confirm_marks_bubble()
    assert got["before"] == ""
    assert got["after"] == "1"
