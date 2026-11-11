"""W26 graph at scale: three costs out of a 2,000-note open (INBOX W26, 1111).

Measured on the 2,000-note fixture (3,796 links), Chromium at 1x, a cold tab
switch to Graph, longtask observer plus per-function timing:

- the minimap's first paint made about 1,300 SVG elements one `createElementNS`
  at a time: a 47 ms task. One `insertAdjacentHTML` is one parse;
- the fit's second and third balance passes drew whole frames (22 to 67 ms each)
  in the middle of the settle; once the map is shown they wait for the frame at
  rest, which still holds `fitCheck`;
- the link grid cut every curved link into eight chords: 18 to 31 ms to build.
  Chords now follow the length (a cell each, 2 to 8).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
CANVAS = (JS / "graph-canvas.js").read_text(encoding="utf-8")
GRAPH = (JS / "graph.js").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _function(text: str, name: str) -> str:
    start = re.search(rf"\nfunction {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


def _node(script: str):
    run = subprocess.run([shutil.which("node"), "-e", script], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout.strip().splitlines()[-1])


def test_minimap_missing_elements_are_one_parse_not_one_create_each() -> None:
    body = _function(GRAPH, "graphMinimapChildren")
    assert body.count("insertAdjacentHTML(") == 1
    assert "createElementNS" not in body
    # Extra elements are removed one by one only when the count falls, as before.
    assert "group.lastElementChild.remove()" in body


@needs_node
def test_minimap_children_makes_exactly_the_count_asked_for() -> None:
    script = (
        "const made = [];\n"
        "const group = { children: made, lastElementChild: null,\n"
        "  insertAdjacentHTML(where, html) { const n = (html.match(/<line /g) || []).length; for (let i = 0; i < n; i++) made.push({ remove() {} }); this.html = html; } };\n"
        + _function(GRAPH, "graphMinimapChildren")
        + "\ngraphMinimapChildren(group, 3, 'line', 'graph-minimap-edge');\n"
        "graphMinimapChildren(group, 5, 'line', 'graph-minimap-edge');\n"
        "console.log(JSON.stringify({ n: made.length, html: group.html }));\n"
    )
    out = _node(script)
    assert out["n"] == 5
    assert out["html"] == '<line class="graph-minimap-edge"></line>' * 2


LIGHT = r"""
const GC_LIGHT_ITEMS = %s;
const gcTickSnaps = () => true;
const graphTrace = null;
let graphHighlightIds = null;
const gcEl = () => ({ value: "" });
%s
const base = () => ({ layoutRunning: true, size: "full", tree: null, dragNode: null, hoveredId: null, paintMode: null,
  fitCheck: 2, revealAfterFit: false, shown: false, nodes: new Array(2000), edges: new Array(3796) });
const out = {};
out.hiddenFit = gcLightFrame(base());
out.shownFit = gcLightFrame(Object.assign(base(), { shown: true }));
out.shownReveal = gcLightFrame(Object.assign(base(), { shown: true, revealAfterFit: true }));
console.log(JSON.stringify(out));
"""


@needs_node
def test_a_balance_pass_gets_a_whole_frame_only_until_the_map_is_shown() -> None:
    items = re.search(r"\nconst GC_LIGHT_ITEMS = (\d+);", CANVAS).group(1)
    out = _node(LIGHT % (items, _function(CANVAS, "gcLightFrame")))
    assert out == {"hiddenFit": False, "shownFit": True, "shownReveal": False}


GRID = r"""
const GC_LINE_CELL = 48;
const gcVisibleAtTime = () => true;
const gcBowPoint = (a, b) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 + 10 });
%s
const count = (len) => {
  const a = { x: 0, y: 0 }, b = { x: len, y: 0 };
  const s = { nodes: [a, b], edges: [{ source: a, target: b }] };
  const grid = gcLineGrid(s, true);
  let segs = 0;
  for (const list of grid.cells.values()) segs += list.length / 4;
  return segs;
};
console.log(JSON.stringify({ short: count(20), mid: count(150), long: count(900) }));
"""


@needs_node
def test_a_curved_link_is_filed_in_chords_of_about_a_cell_not_always_eight() -> None:
    out = _node(GRID % _function(CANVAS, "gcLineGrid"))
    # 2 chords for a short link; 8 for a long one (each filed under every cell it crosses).
    assert 2 <= out["short"] <= 4, out
    assert out["mid"] < out["long"], out
    assert out["long"] >= 8, out
