"""Graph round 6 (graph-1026.md): a grid of notes for the cleanup, curves cached in its pushes, nearest-first step-off.

Round 5 filed the lines in a grid so the note-on-line cleanup could run on big
maps. What was left (400 notes): `untangleFree` and `untangleLineOver` asked
every note about every spot the step-off tried, the pushes rebuilt a curve for
each near pair on every turn, and the step-off went in index order. These run the
real worker in node on the 150-note map of `test_graph_untangle_1400.py`, the
grid's answer against the scan it replaces, pair for pair.
"""

import re
from pathlib import Path

from tests.test_graph_untangle_1400 import GRID, WORKER, _node

ROOT = Path(__file__).resolve().parent.parent


def _fn(text: str, name: str) -> str:
    start = re.search(rf"\nfunction {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


# Every spot near a note and a few outside the map, the grid's answer against the scan.
GRID_NODES = (
    GRID
    + r"""
run("untangleReach();");
const out = run(`(() => {
  untangle.margin = 1;
  const gap = COLLIDE_PAD / 2;
  nodeGridBuild(untangle.widest + gap + 3);
  const probe = (label, list) => {
    let free = 0, freeDisagree = 0, over = 0, overDisagree = 0, missed = 0;
    for (const [i, x, y] of list) {
      const node = nodes[i];
      const was = [node.x, node.y];
      node.x = x; node.y = y;
      nodeGrid.live = true;
      const g = untangleFree(node, x, y, gap), go = untangleLineOver(i);
      const near = new Set(nodeGridNear(x, y));
      nodeGrid.live = false;
      const s = untangleFree(node, x, y, gap), so = untangleLineOver(i);
      if (g !== s) freeDisagree++;
      if (go !== so) overDisagree++;
      if (!s) free++;
      if (so) over++;
      // Every note within the cell of the spot is among the 3 by 3 cells' notes.
      for (let j = 0; j < nodes.length; j++) {
        if (j !== i && Math.hypot(nodes[j].x - x, nodes[j].y - y) <= nodeGrid.cell && !near.has(j)) missed++;
      }
      node.x = was[0]; node.y = was[1];
      nodeGrid.live = true;
    }
    return { label, free, freeDisagree, over, overDisagree, missed, count: list.length };
  };
  const spots = [];
  for (let i = 0; i < nodes.length; i++) {
    for (const [dx, dy] of [[0, 0], [9, -4], [-20, 14], [31, 31], [-48, -12]]) spots.push([i, nodes[i].x + dx, nodes[i].y + dy]);
  }
  const first = probe("inside", spots);
  // Beyond the cells the grid was built over: clamped to the edge cell, the way a note is.
  const lo = nodes.reduce((p, n) => [Math.min(p[0], n.x), Math.min(p[1], n.y)], [Infinity, Infinity]);
  const hi = nodes.reduce((p, n) => [Math.max(p[0], n.x), Math.max(p[1], n.y)], [-Infinity, -Infinity]);
  const outside = [];
  for (let i = 0; i < nodes.length; i += 3) outside.push([i, lo[0] - 25 - (i % 7) * 11, nodes[i].y], [i, nodes[i].x, hi[1] + 20 + (i % 5) * 9], [i, hi[0] + 3, lo[1] - 40]);
  const second = probe("outside", outside);
  // A note that moved is in its new cell: the answers still agree.
  let moves = 0;
  for (let i = 0; i < nodes.length; i += 4) { nodes[i].x += 37 - (i % 5) * 20; nodes[i].y -= 23 - (i % 3) * 25; nodeGridMove(i); moves++; }
  const third = probe("moved", spots.filter((_, n) => n % 3 === 0));
  return { first, second, third, cell: nodeGrid.cell, cols: nodeGrid.across, rows: nodeGrid.down, moves, count: nodes.length };
})()`);
console.log(JSON.stringify(out));
"""
)


def test_the_grid_of_notes_answers_free_and_line_over_as_the_scan_does() -> None:
    out = _node(GRID_NODES)
    assert out["count"] == 150 and out["moves"] > 30, out
    # It is a grid, not one cell: the map is many cells wide.
    assert out["cols"] > 8 and out["rows"] > 5, out
    for key in ("first", "second", "third"):
        part = out[key]
        assert part["freeDisagree"] == 0 and part["overDisagree"] == 0 and part["missed"] == 0, out
    # The probes meet crowded spots and lines over notes, so agreeing on "no" everywhere would prove nothing.
    assert out["first"]["free"] > 50 and out["first"]["over"] > 5, out
    assert out["second"]["count"] > 30, out


GRID_ORDER = (
    GRID
    + r"""
run("untangle.passes = 1");
// Free notes put on long lines they do not join, each a little deeper than the last.
run(`(() => {
  const used = new Set();
  let depth = 0;
  for (let k = 0; k < untangle.edges.length && depth < 8; k++) {
    const [a, b] = untangle.edges[k];
    if (Math.hypot(nodes[a].x - nodes[b].x, nodes[a].y - nodes[b].y) < 140 || used.has(a) || used.has(b)) continue;
    const i = nodes.findIndex((n, j) => j !== a && j !== b && !used.has(j) && n.fx == null && untangle.incident[j].length < 3);
    if (i < 0) continue;
    clearNearest(nodes[i], clearCurve(nodes[a], nodes[b]));
    const mid = clearPts[4], midY = clearPts[5];
    const nx = (nodes[b].y - nodes[a].y), ny = -(nodes[b].x - nodes[a].x), len = Math.hypot(nx, ny) || 1;
    nodes[i].x = mid + (nx / len) * (1 + depth * 1.6); nodes[i].y = midY + (ny / len) * (1 + depth * 1.6);
    used.add(a); used.add(b); used.add(i);
    depth++;
  }
})()`);
const out = run(`(() => {
  untangleReach();
  untangle.margin = 1;
  lineGridBuild(untangle.widest + 15);
  const free = (n) => n.fx == null && !n.placed;
  const order = untangleStepOrder(free);
  // The depth of each, from every line (the scan): the radius and margin less the distance to the nearest line over it, the deepest.
  const depthOf = (i) => {
    const node = nodes[i];
    let deepest = 0;
    for (let k = 0; k < untangle.ea.length; k++) {
      if (untangle.ea[k] === i || untangle.eb[k] === i) continue;
      const a = nodes[untangle.ea[k]], b = nodes[untangle.eb[k]];
      clearNearest(node, clearCurve(a, b));
      const d = Math.sqrt(Math.min(clearNear[0], untangleChordD2(node, a, b)));
      deepest = Math.max(deepest, (node.r || 8) + untangle.margin - d);
    }
    return deepest;
  };
  const depths = order.map(depthOf);
  const onLine = nodes.map((n, i) => i).filter((i) => free(nodes[i]) && untangleOnLine(i));
  const sorted = depths.every((d, n) => !n || depths[n - 1] <= d + 1e-9);
  return { order: order.length, onLine: onLine.length, sameNotes: JSON.stringify([...order].sort((p, q) => p - q)) === JSON.stringify(onLine), sorted, first: depths[0], last: depths[depths.length - 1], positive: depths.every((d) => d > 0) };
})()`);
console.log(JSON.stringify(out));
"""
)


def test_the_step_off_goes_to_the_notes_least_into_a_line_first() -> None:
    out = _node(GRID_ORDER)
    # Every note on a line is in the order, once, and only those.
    assert out["order"] >= 8 and out["sameNotes"] is True, out
    assert out["positive"] is True, out
    assert out["sorted"] is True and out["first"] < out["last"], out


GRID_CURVES = (
    GRID
    + r"""
run("untangleReach();");
const out = run(`(() => {
  untangle.margin = 3;
  lineGridBuild(untangle.widest + 15);
  const cells = lineGrid.cells.size;
  const k = untangle.edges.findIndex(([a, b]) => Math.hypot(nodes[a].x - nodes[b].x, nodes[a].y - nodes[b].y) > 100);
  const [a, b] = untangle.edges[k];
  nodes[a].x += 41; nodes[a].y -= 17;
  const points = lineCurveFile(k);
  const fresh = clearCurve(nodes[a], nodes[b]);
  let same = points === fresh && lineGrid.count[k] === fresh;
  for (let i = 0; i < fresh * 2; i++) if (lineGrid.pts[k * 10 + i] !== clearPts[i]) same = false;
  // Without the cells: the curve is filed, the grid keeps the cells it had.
  const kept = lineGrid.cells.size === cells;
  // The cached test agrees with the scan for every note, on the moved line.
  let disagree = 0;
  for (let i = 0; i < nodes.length; i++) {
    if (i === a || i === b) continue;
    if (lineGridTouches(nodes[i], k) !== untangleNear(nodes[i], nodes[a], nodes[b])) disagree++;
  }
  return { same, kept, disagree, points };
})()`);
console.log(JSON.stringify(out));
"""
)


def test_a_moved_lines_curve_is_filed_again_without_touching_the_cells() -> None:
    out = _node(GRID_CURVES)
    assert out["same"] is True and out["kept"] is True and out["disagree"] == 0, out


GRID_CLEAN = (
    GRID
    + r"""
run("untangle.passes = 1");
const planted = run(`(() => {
  const used = new Set(); const out = [];
  for (let k = 0; k < untangle.edges.length && out.length < 12; k++) {
    const [a, b] = untangle.edges[k];
    if (Math.hypot(nodes[a].x - nodes[b].x, nodes[a].y - nodes[b].y) < 140 || used.has(a) || used.has(b)) continue;
    const i = nodes.findIndex((n, j) => j !== a && j !== b && !used.has(j) && n.fx == null && untangle.incident[j].length < 3);
    if (i < 0) continue;
    nodes[i].x = (nodes[a].x + nodes[b].x) / 2; nodes[i].y = (nodes[a].y + nodes[b].y) / 2;
    used.add(a); used.add(b); used.add(i); out.push(i);
  }
  return out.length;
})()`);
const onLines = () => run(`(() => { untangle.margin = 0; return nodes.filter((_, i) => untangleOnLine(i)).length; })()`);
const before = onLines();
run("untangleCleanup()");
run("for (const n of nodes) if (n.tx !== undefined) { n.x = n.tx; n.y = n.ty; n.tx = undefined; n.ty = undefined; }");
const after = onLines();
console.log(JSON.stringify({ planted, before, after, nodeGridLive: run("nodeGrid.live"), lineGridLive: run("lineGrid.live"), stillInside: run("nodes.filter((n) => !untangleInside(n) && n.fx == null).length") }));
"""
)


def test_the_cleanup_drops_both_grids_and_still_clears_planted_notes() -> None:
    out = _node(GRID_CLEAN)
    assert out["planted"] >= 8 and out["before"] >= out["planted"], out
    assert out["after"] <= max(1, out["before"] // 4), out
    # Left live, the next move of a note by the forces would be asked of stale cells.
    assert out["nodeGridLive"] is False and out["lineGridLive"] is False, out


def test_the_pushes_use_the_filed_curve_and_the_step_off_the_grid_in_order() -> None:
    cleanup = _fn(WORKER, "untangleCleanup")
    # The push turns read the points filed with each line and refile one only when an end moved.
    push = cleanup[cleanup.index("for (let iter = 0;") : cleanup.index("// A note that travelled too far")]
    assert "lineCurveFile(k)" in push and "lineGridTouches(node, k)" in push and "stale[k]" in push, push
    assert "untangleNear(" not in push and "clearCurve(" not in push, push
    assert push.count("touched(") >= 4, push
    # The step-off builds the grid of notes, goes in order, and moves a note's cell with it.
    assert "nodeGridBuild(" in cleanup and "untangleStepOrder(free)" in cleanup and "nodeGridMove(i)" in cleanup
    assert "nodeGrid.live = false;" in cleanup
    # `untangleFree` and `untangleLineOver` ask the grid only when it is live and wide enough for the question.
    assert "nodeGrid.live && wide <= nodeGrid.cell" in _fn(WORKER, "untangleFree")
    assert "nodeGrid.live" in _fn(WORKER, "untangleLineOver")
    # One curve per line in the line-over test, not one per note near it.
    assert _fn(WORKER, "untangleLineOver").count("clearCurve(") == 1
    # The fallback (no grid) is still the scan: passes and tests that never build a grid.
    assert "for (let i = 0; i < nodes.length; i++) {\n    const other = nodes[i];" in _fn(WORKER, "untangleFree")
