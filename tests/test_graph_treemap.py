"""GRAPH_PLAN VC11: D3's hierarchy layouts as a category overview.

The Layout picker's Treemap draws the notebook's categories as rectangles whose
areas are in proportion to how many notes each holds, the notes as dots in
their category's cells. The plan's measure: at 1,000 notes the layout takes
under 100 ms and every category rectangle's area is within 1% of its share of
the notes. `layoutTreemap` (graph.js) is the pure part, run here in node with
the vendored d3; the drawing, the picker and the help are read from source.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"
GRAPH = (JS / "graph.js").read_text(encoding="utf-8")
CANVAS = (JS / "graph-canvas.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
D3 = ROOT / "frontend" / "vendor" / "d3.v7.min.js"


def _function(text: str, name: str) -> str:
    start = re.search(rf"\nfunction {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


SCRIPT = "\n".join(
    [
        f"const d3 = require({json.dumps(str(D3))});",
        _function(GRAPH, "layoutTreemap"),
        """
const W = 1400, H = 800;
const counts = { Work: 420, Home: 260, Travel: 150, Ideas: 90, Money: 55, Reading: 25 };
const nodes = [];
let id = 1;
for (const [category, n] of Object.entries(counts)) for (let i = 0; i < n; i++) nodes.push({ id: id++, category, preview: `${category} ${i}` });
const t0 = Date.now();
const r = layoutTreemap(nodes.map((n) => ({ ...n })), W, H);
const ms = Date.now() - t0;
const total = nodes.length;
const shares = r.treemap.map((c) => ({
  category: c.category,
  count: c.count,
  area: (c.x1 - c.x0) * (c.y1 - c.y0),
  want: (counts[c.category] / total) * W * H,
}));
const inside = r.nodes.every((n) => {
  const c = r.treemap.find((x) => x.category === n.category);
  return n.x >= c.x0 && n.x <= c.x1 && n.y >= c.y0 && n.y <= c.y1;
});
console.log(JSON.stringify({
  ms, notes: r.nodes.length, links: r.links.length, shares, inside,
  finite: r.nodes.every((n) => Number.isFinite(n.x) && Number.isFinite(n.y) && n.fx === n.x && n.fy === n.y),
  cells: r.nodes.every((n) => n.cell && n.cell.w > 0 && n.cell.h > 0),
  radial: r.radial, arc: r.arc,
}));
""",
    ]
)


@pytest.fixture(scope="module")
def laid() -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    run = subprocess.run([node, "-e", SCRIPT], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def test_every_category_rectangle_is_in_proportion_to_its_notes(laid) -> None:
    assert len(laid["shares"]) == 6
    for share in laid["shares"]:
        assert abs(share["area"] - share["want"]) / share["want"] <= 0.01, share


def test_a_thousand_notes_lay_out_in_under_a_hundred_milliseconds(laid) -> None:
    assert laid["notes"] == 1000
    assert laid["ms"] < 100, laid["ms"]


def test_each_note_stands_in_its_category_and_is_held_there(laid) -> None:
    assert laid["inside"] and laid["finite"] and laid["cells"]
    assert laid["links"] == 0, "a treemap draws no filing lines: the rectangles are the filing"
    assert not laid["radial"] and not laid["arc"]


def test_the_picker_the_layout_list_and_the_drawing_know_the_treemap() -> None:
    picker = HTML[HTML.index('<select id="graph-layout"') : HTML.index("</select>", HTML.index('<select id="graph-layout"'))]
    assert '<option value="treemap">Treemap</option>' in picker
    assert '"treemap"' in _function(GRAPH, "graphLayout")
    assert "layoutTreemap(" in _function(GRAPH, "layoutHierarchy")
    assert "function gcDrawTreemap(" in CANVAS and "gcDrawTreemap(ctx, s, k);" in CANVAS
    # A note's dot never outgrows its cell.
    assert "node.cell" in CANVAS[CANVAS.index("node.r = gcRadius(") :][:600]


def test_the_help_names_the_treemap() -> None:
    chat = (ROOT / "src" / "tessellate" / "ai" / "help_chat.py").read_text(encoding="utf-8")
    assert "Force, Tree, Radial, Arc or Treemap" in chat
    assert "Treemap" in HTML[HTML.index('id="graph-help-panel"') :][:2600]
