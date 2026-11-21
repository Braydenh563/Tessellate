"""The shortcuts sheet's "t then" rows are generated from the chord's tables
(L-world-class-120, WORLD_CLASS_PLAN:3609 "the sheet must be generated from
the table"). They were typed into index.html and named 10 of the 17 keys
`TAB_JUMP_KEYS` and `CHORD_ACTIONS` hold; the renderer runs here in node over
the real tables, with a stub DOM, and every key must come out."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parent.parent
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _block(src: str, head: str) -> str:
    start = src.index(head)
    depth, i = 0, src.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        i += 1
        if depth == 0:
            return src[start:i]


def test_the_sheet_types_no_chord_row_by_hand():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "<kbd>t</kbd> then" not in html
    assert 'id="shortcut-list-chord"' in html
    assert 'renderChordShortcutRows($("shortcut-list-chord"))' in _block(app_js_text(), "function openShortcuts()")


@needs_node
def test_every_chord_key_is_on_the_sheet():
    src = app_js_text()
    tables = _block(src, "const TAB_JUMP_KEYS = ") + ";\n" + _block(src, "const CHORD_ACTIONS = ") + ";\n"
    harness = r"""
class El { constructor(t) { this.tag = t; this.kids = []; this.textContent = ""; }
  append(...k) { this.kids.push(...k); } replaceChildren() { this.kids = []; }
  text() { return this.textContent + this.kids.map((k) => typeof k === "string" ? k : k.text()).join(""); } }
const document = { createElement: (t) => new El(t) };
const list = new El("ul");
"""
    script = harness + tables + _block(src, "function renderChordShortcutRows(") + (
        "\nrenderChordShortcutRows(list);"
        "process.stdout.write(JSON.stringify({rows: list.kids.map((li) => li.text()),"
        " keys: [...Object.keys(TAB_JUMP_KEYS), ...Object.keys(CHORD_ACTIONS)],"
        " labels: Object.values(CHORD_ACTIONS).map((a) => a.label)}));"
    )
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert len(out["keys"]) >= 17, out["keys"]
    sheet = " ".join(out["rows"])
    shown = re.findall(r"(?:then |/)(\w)", sheet)
    assert sorted(shown) == sorted(out["keys"]), (shown, out["keys"])
    assert all(label in sheet for label in out["labels"]), sheet
    assert out["rows"][0].startswith("t then d/") and "Go to: Dashboard" in out["rows"][0]
