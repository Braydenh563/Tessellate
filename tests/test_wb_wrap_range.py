"""Bold and Italic from the Format panel wrap the selection by offsets, not the first match (wbdog-1026)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _wrap(text: str, frm: int, to: int, marker: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    start = WB.index("function wbWrapRange(")
    fn = WB[start : WB.index("\n}\n", start) + 3]
    script = fn + f"console.log(JSON.stringify(wbWrapRange({json.dumps(text)}, {frm}, {to}, {json.dumps(marker)})));"
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)


def test_the_second_occurrence_is_the_one_wrapped():
    text = "the cat and the cat"
    out = _wrap(text, 16, 19, "**")
    assert out["text"] == "the cat and the **cat**"


def test_wrapping_twice_takes_it_off_again():
    wrapped = _wrap("one two", 4, 7, "*")
    assert wrapped["text"] == "one *two*"
    again = _wrap(wrapped["text"], wrapped["from"], wrapped["to"], "*")
    assert again["text"] == "one two"
    inner = _wrap("**bold**", 0, 8, "**")
    assert inner["text"] == "bold"


def test_the_panel_buttons_go_through_the_editing_surface():
    start = WB.index("function wbWrapTextSelection(")
    body = WB[start : WB.index("\n}\n", start)]
    assert "surf.selection()" in body and "raw.replace(" not in body
