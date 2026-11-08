"""The settings section index reads the tree, not layout (laglist-1108 item 1).

`getClientRects` in `settingsIndexHeads` made the first read of a section
settle the pane's pending style (70 to 103 ms at 4x CPU on Help). The heads it
lists must not change, so the tree walk is held to the cases layout used to
answer, run in node against stub elements; the same walk was compared with
`getClientRects` on every section at 1440 and 390 in the running app.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend" / "js" / "settings-find.js").read_text(encoding="utf-8")
node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _function(name: str) -> str:
    start = JS.index(f"function {name}(")
    return JS[start : JS.index("\n}\n", start) + 2]


def _shown() -> str:
    start = JS.index("settingsIndexHeads.shown = ")
    return JS[start : JS.index("\n};\n", start) + 4]


def test_the_index_build_asks_layout_nothing():
    for name in ("settingsIndexHeads", "settingsPaneTitleHead"):
        assert "getClientRects" not in _function(name), name
    assert "getClientRects" not in _shown()


@node
def test_a_head_is_listed_unless_it_or_an_ancestor_is_hidden_or_closed():
    script = (
        "function settingsIndexHeads() {}\n"
        + _shown()
        + """
const el = (tag, parent, extra = {}) => {
  const node = { tagName: tag, parentElement: parent || null, hidden: false, open: false, classList: { contains: (c) => (extra.cls || []).includes(c) }, ...extra };
  return node;
};
const pane = el("DIV", null);
const shown = el("H3", pane);
const group = el("DIV", pane, { cls: ["hidden"] });
const inGroup = el("H3", group);
const attr = el("H3", pane, { hidden: true });
const closed = el("DETAILS", pane);
const summary = el("SUMMARY", closed);
const body = el("H3", closed);
const open = el("DETAILS", pane, { open: true });
const inOpen = el("H3", open);
const nested = el("DETAILS", open);
const inNested = el("DIV", nested);
console.log(JSON.stringify([shown, inGroup, attr, summary, body, inOpen, inNested].map((n) => settingsIndexHeads.shown(n, pane))));
"""
    )
    out = subprocess.run(["node", "-"], input=script, capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(out.stdout) == [True, False, False, True, False, True, False]
