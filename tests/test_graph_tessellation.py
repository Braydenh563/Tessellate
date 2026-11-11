"""GRAPH_PLAN Q31: the Tessellation view (Cells and Hexes) and the Map's two fixes.

The owner's decision: one Tessellation view with two looks, Cells (a link-weighted
Voronoi, the default) and Hexes (hexagons grouped by category); the Map (treemap)
gets tile area by link weight and category names that are never cut. The layout
functions are pure and run here in node with the vendored d3 (as
`test_graph_treemap.py` does); the drawing, the picker, the lazy bundle and the
help are read from source. Real drawing is checked in a browser sweep, not here.
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
TESS = (JS / "graph-tessellate.js").read_text(encoding="utf-8") if (JS / "graph-tessellate.js").exists() else ""
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
APP = (JS / "app.js").read_text(encoding="utf-8")
D3 = ROOT / "frontend" / "vendor" / "d3.v7.min.js"

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _function(text: str, name: str) -> str:
    start = re.search(rf"\nfunction {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


def _run(body: str) -> dict:
    script = "\n".join(
        [
            f"const d3 = require({json.dumps(str(D3))});",
            "const prefs = { get: () => null };",
            _function(GRAPH, "layoutTreemap"),
            "globalThis.window = {};",
            TESS,
            "const { layout: layoutTessellation, fit: fitHeaderLabel } = window.gcTess;",
            """
const W = 1400, H = 800;
const counts = { Work: 220, Home: 130, Travel: 70, Ideas: 45, Money: 25, Reading: 10 };
function build(seed) {
  let s = seed;
  const rnd = () => ((s = (s * 1664525 + 1013904223) % 4294967296) / 4294967296);
  const nodes = [];
  let id = 1;
  for (const [category, n] of Object.entries(counts)) for (let i = 0; i < n; i++) nodes.push({ id: id++, category, preview: `${category} ${i}` });
  const degree = new Map();
  const near = new Map(nodes.map((n) => [n.id, new Set()]));
  for (let i = 0; i < nodes.length * 1.4; i++) {
    const a = nodes[Math.floor(rnd() * nodes.length)];
    const b = rnd() < 0.8 ? nodes.filter((n) => n.category === a.category)[Math.floor(rnd() * counts[a.category])] : nodes[Math.floor(rnd() * nodes.length)];
    if (a === b || near.get(a.id).has(b.id)) continue;
    near.get(a.id).add(b.id); near.get(b.id).add(a.id);
    degree.set(a.id, (degree.get(a.id) || 0) + 1);
    degree.set(b.id, (degree.get(b.id) || 0) + 1);
  }
  return { nodes, info: { degree, near } };
}
const area = (p) => Math.abs(d3.polygonArea(p));
""",
            body,
        ]
    )
    out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@needs_node
def test_cells_tile_each_category_with_no_gaps_and_follow_link_weight():
    r = _run(
        """
const { nodes, info } = build(7);
const t0 = Date.now();
const out = layoutTessellation(nodes.map((n) => ({ ...n })), W, H, info, "cells");
const ms = Date.now() - t0;
const cells = out.tess.cells;
const rects = new Map(out.treemap.map((c) => [c.category, c]));
const sums = {};
for (const c of cells) sums[c.category] = (sums[c.category] || 0) + area(c.poly);
const gaps = out.treemap.map((c) => {
  const box = (c.x1 - c.x0 - 4) * (c.y1 - c.y0 - c.head - 2);
  return Math.abs(sums[c.category] - box) / box;
});
const inside = cells.every((c) => {
  const r = rects.get(c.category);
  return c.poly.every(([x, y]) => x >= r.x0 - 0.01 && x <= r.x1 + 0.01 && y >= r.y0 - 0.01 && y <= r.y1 + 0.01);
});
const xs = cells.map((c) => 1 + (info.degree.get(c.id) || 0));
const ys = cells.map((c) => area(c.poly));
const mean = (a) => a.reduce((p, q) => p + q, 0) / a.length;
const mx = mean(xs), my = mean(ys);
let sxy = 0, sxx = 0, syy = 0;
for (let i = 0; i < xs.length; i++) { sxy += (xs[i] - mx) * (ys[i] - my); sxx += (xs[i] - mx) ** 2; syy += (ys[i] - my) ** 2; }
console.log(JSON.stringify({
  ms, notes: out.nodes.length, cells: cells.length, maxGap: Math.max(...gaps), inside,
  corr: sxy / Math.sqrt(sxx * syy),
  finite: out.nodes.every((n) => Number.isFinite(n.x) && Number.isFinite(n.y) && n.fx === n.x && n.cell.w > 0 && n.cell.h > 0),
  look: out.tess.look, links: out.links.length,
}));
"""
    )
    assert r["notes"] == r["cells"] == 500
    assert r["finite"] and r["inside"] and r["links"] == 0 and r["look"] == "cells"
    assert r["maxGap"] < 0.01, r
    assert r["corr"] > 0.5, r  # a well-linked note owns a bigger cell
    assert r["ms"] < 400, r


@needs_node
def test_cells_survive_one_two_and_three_notes():
    r = _run(
        """
const res = [1, 2, 3].map((n) => {
  const nodes = Array.from({ length: n }, (_, i) => ({ id: i + 1, category: "Solo", preview: "x" }));
  const out = layoutTessellation(nodes, 600, 400, { degree: new Map(), near: new Map() }, "cells");
  return out.tess.cells.length === n && out.nodes.every((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
});
console.log(JSON.stringify({ res, empty: layoutTessellation([], 600, 400, null, "cells").nodes.length }));
"""
    )
    assert r["res"] == [True, True, True] and r["empty"] == 0


@needs_node
def test_hexes_are_regular_grouped_by_category_and_linked_notes_sit_close():
    r = _run(
        """
const { nodes, info } = build(11);
const out = layoutTessellation(nodes.map((n) => ({ ...n })), W, H, info, "hexes");
const cells = out.tess.cells;
const rects = new Map(out.treemap.map((c) => [c.category, c]));
const side = (p) => Math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]);
const regular = cells.every((c) => c.poly.length === 6 && Math.abs(side(c.poly) - side(c.poly.slice(2))) < 1e-6);
const inside = cells.every((c) => { const r = rects.get(c.category); return c.poly.every(([x, y]) => x >= r.x0 && x <= r.x1 && y >= r.y0 && y <= r.y1); });
const sizes = new Set(cells.map((c) => Math.round(area(c.poly))));
const byId = new Map(out.nodes.map((n) => [n.id, n]));
let linked = 0, nl = 0, any = 0, na = 0;
for (const [a, set] of info.near) for (const b of set) {
  const p = byId.get(a), q = byId.get(b);
  if (p.category !== q.category) continue;
  linked += Math.hypot(p.x - q.x, p.y - q.y); nl++;
}
const inCat = out.nodes.filter((n) => n.category === "Work");
for (let i = 0; i < inCat.length; i++) for (let j = i + 1; j < inCat.length; j++) { any += Math.hypot(inCat[i].x - inCat[j].x, inCat[i].y - inCat[j].y); na++; }
const distinct = new Set(out.nodes.map((n) => `${Math.round(n.x)},${Math.round(n.y)}`)).size;
console.log(JSON.stringify({ n: cells.length, regular, inside, sizes: sizes.size, ratio: (linked / nl) / (any / na), distinct, look: out.tess.look }));
"""
    )
    assert r["n"] == 500 and r["regular"] and r["inside"] and r["look"] == "hexes"
    assert r["sizes"] == 1, r  # one hexagon size under every category
    assert r["distinct"] == 500
    assert r["ratio"] < 0.85, r  # linked notes are nearer than two notes of a category


@needs_node
def test_map_tile_area_follows_link_weight_and_defaults_to_the_count():
    r = _run(
        """
const { nodes, info } = build(3);
const flat = layoutTreemap(nodes.map((n) => ({ ...n })), W, H);
const weighted = layoutTreemap(nodes.map((n) => ({ ...n })), W, H, info);
const w = (id) => 1 + Math.min(info.degree.get(id) || 0, 12);
const want = {}; let total = 0;
for (const n of nodes) { want[n.category] = (want[n.category] || 0) + w(n.id); total += w(n.id); }
const err = weighted.treemap.map((c) => {
  const share = want[c.category] / total;
  const inner = (c.x1 - c.x0) * (c.y1 - c.y0);
  return { cat: c.category, count: c.count, share, got: inner / (W * H) };
});
console.log(JSON.stringify({ flat: flat.treemap.map((c) => c.count), counts, err }));
"""
    )
    assert sorted(r["flat"], reverse=True) == [220, 130, 70, 45, 25, 10]
    for row in r["err"]:
        assert row["count"] == r["counts"][row["cat"]]  # the header still counts notes
        assert abs(row["got"] - row["share"]) < 0.04 * max(row["share"], 0.05) + 0.01, row


@needs_node
def test_a_category_name_is_never_split_inside_a_word():
    """INBOX 1744 ("Literatur / e", "Eve / nts"): wrap at spaces only, two lines
    at most; the last resort is whole words and an ellipsis (Q31 said never an
    ellipsis; the owner's later words moved the means, the intent, no cut
    glyph, stands)."""
    r = _run(
        """
const measure = (t, size) => t.length * size * 0.56;
const names = ["Thoughts", "Literature", "Events", "Communication & Connection", "Thoughts and ideas worth keeping", "Extraordinarily-long-unbroken-category-name", "A"];
const rows = [];
for (const name of names) for (const w of [20, 40, 55, 70, 110, 220, 600]) for (const h of [14, 21, 30, 36, 60]) {
  const fit = fitHeaderLabel(measure, name, 7, w, h);
  if (!fit) { rows.push({ name, w, h, dropped: true }); continue; }
  const shown = fit.lines.join(" ").replace(/ \\(7\\)$/, "");
  const tail = shown.replace(/\\u2026$/, "");
  const widest = Math.max(...fit.lines.map((l) => measure(l, fit.size)));
  rows.push({
    name, w, h, size: fit.size, lines: fit.lines.length,
    whole: shown === name || (shown.endsWith("\\u2026") && name.startsWith(tail) && name[tail.length] === " "),
    wide: widest <= w + 1e-6,
    tall: fit.lines.length * (fit.size + 3) <= h + 1e-6,
  });
}
const f = (n, c, w, h) => { const x = fitHeaderLabel(measure, n, c, w, h); return x && x.lines; };
console.log(JSON.stringify({
  rows,
  roomy: f("Thoughts", 2, 400, 20),
  noCount: f("Literature", 4, 70, 15),
  wraps: f("Communication & Connection", 3, 120, 30),
  shrunkSize: fitHeaderLabel(measure, "Literature", 4, 62, 15).size,
  ellipsis: f("Thoughts and ideas worth keeping", 2, 90, 30),
  narrowWord: f("Literature", 4, 30, 30),
}));
"""
    )
    shown = [row for row in r["rows"] if not row.get("dropped")]
    assert len(shown) > 60
    for row in shown:
        assert row["whole"] and row["wide"] and row["tall"] and row["lines"] <= 2, row
    assert r["roomy"] == ["Thoughts (2)"]  # room: name and count on one line
    assert r["noCount"] == ["Literature"]  # no room for the count: dropped
    assert r["wraps"] == ["Communication &", "Connection"]
    assert r["shrunkSize"] < 12  # one step down before an ellipsis
    assert r["ellipsis"][-1].endswith("…") and r["ellipsis"][0].startswith("Thoughts")
    assert r["narrowWord"] is None  # a word wider than the room: left out, never split


def test_the_view_is_a_lazy_layout_beside_the_others():
    assert TESS, "frontend/js/graph-tessellate.js is the lazy module"
    assert "/js/graph-tessellate.js" in APP[APP.index("graph: [") : APP.index("graph: [") + 400]
    assert "graph-tessellate.js" not in HTML  # not a boot script
    options = HTML[HTML.index('<select id="graph-layout"') :]
    options = options[: options.index("</select>")]
    assert re.findall(r'value="(\w+)"', options)[-2:] == ["treemap", "tessellation"]
    assert '"tessellation"' in GRAPH[GRAPH.index("function graphLayout()") :][:300]
    assert 'if (kind === "tessellation") return gcTess.layout(' in GRAPH
    look = HTML[HTML.index('<select id="graph-tess-look"') :]
    look = look[: look.index("</select>")]
    assert re.findall(r'value="(\w+)"', look) == ["cells", "hexes"]
    assert re.search(r'id="graph-tess-row"[^>]*\bhidden\b|\bhidden\b[^>]*id="graph-tess-row"', HTML)
    assert '"graph-tess-look"' in GRAPH[GRAPH.index("const GRAPH_DEFAULTS") :][:900]


def test_the_drawing_and_hit_test_are_wired():
    assert "gcTess.paint(ctx, s, k);" in CANVAS
    assert "gcTess.nodeAt(" in _function(CANVAS, "gcNodeAtWorld")
    assert "gcTess.titleAt(" in CANVAS
    assert "gcTess.fit(" in _function(CANVAS, "gcDrawTreemap")
    assert "gcEllipsize(" not in _function(CANVAS, "gcDrawTreemap")
    assert "layoutHierarchy(visibleNodes.map((n) => ({ ...n })), s.layoutKind, width, height, gcTess.info(visibleEdges))" in CANVAS


def test_the_module_adds_one_name_to_the_shared_scope():
    """Wrapped whole (ranked row 37a): the global-names ratchet may not rise."""
    assert TESS.lstrip().split("\n")[-1] == "})();" or TESS.rstrip().endswith("})();")
    assert "Object.assign(window, {\n    gcTess: {" in TESS


def test_the_help_names_the_view():
    from tessellate.ai import help_topics_core

    text = Path(help_topics_core.__file__).read_text(encoding="utf-8")
    assert "Tessellation" in text and "Cells" in text and "Hexes" in text
    view_help = HTML[HTML.index('id="graph-view-help"') :][:1500]
    assert "Tessellation" in view_help and "Cells" in view_help and "Hexes" in view_help


def test_a_cell_pans_and_only_its_dot_is_a_node_for_a_gesture():
    """The owner, 2026-11-11: "it's hard to drag pan on the tessellation view".
    Cells tile the whole view, so a cell that refused the pan left only the
    borders to drag by. The pan filter and the lasso ask for the dot alone; a
    hover and a click still take the whole cell."""
    body = _function(CANVAS, "gcNodeAtWorld")
    assert "dotOnly = false" in body and "!dotOnly && s.tree && s.tree.tess" in body
    assert "!gcNodeAtWorld(x, y, s, true) && !(s.layoutKind" in CANVAS
    assert "if (gcNodeAtWorld(x, y, s, true)) return;" in CANVAS
    # A wobble under the drag threshold is still a click on the cell.
    assert ".clickDistance(GC_DRAG_THRESHOLD_PX)" in CANVAS
