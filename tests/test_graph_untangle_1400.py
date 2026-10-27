"""INBOX 1400 and 1306, round 2: the force view "feels very messy to look at".

Round 1 shaped the map and quietened the hub's spokes but left the crossings
where they were (64 on the 36-note seed, 331 to 348 on the 150-note one,
`gm.js` in the graph-1026 remaining file). The worker now orders Organic's
ring by the links between categories and, once a new layout is at rest,
untangles it (`untangleLayout`): moves that keep each category where it is
and are kept only when they lower the crossings. These run the real worker in
node, and the phone's shorter names in the label cut.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
WORKER = (FRONTEND / "js" / "graph-worker.js").read_text(encoding="utf-8")
CANVAS = (FRONTEND / "js" / "graph-canvas.js").read_text(encoding="utf-8")
REMINDERS = (FRONTEND / "js" / "shell-reminders.js").read_text(encoding="utf-8")


def _node(script: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    run = subprocess.run([node, "-e", script, str(FRONTEND)], capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout.strip().splitlines()[-1])


# Six categories of seven notes: a local hub and a chain in each, one note
# linked from every category, and bridges chosen by a fixed sequence (no
# random source, so the layout is the same every run).
UNTANGLE = r"""
const fs = require("fs"), path = require("path"), vm = require("vm");
const root = process.argv[1];
const sb = { console, Math, Date, Float32Array, Float64Array, Int32Array, Uint8Array, Map, Set,
  setTimeout: () => 1, clearTimeout: () => {}, setInterval: () => 1, clearInterval: () => {}, postMessage: () => {} };
sb.self = sb;
sb.importScripts = (u) => vm.runInContext(fs.readFileSync(path.join(root, u.replace(/^\//, "")), "utf8"), sb);
vm.createContext(sb);
vm.runInContext(fs.readFileSync(path.join(root, "js", "graph-worker.js"), "utf8"), sb);
const groups = ["Work", "Travel", "Cooking", "Reading", "Health", "Ideas"];
const nodes = [], edges = [];
groups.forEach((g, gi) => { for (let i = 0; i < 7; i++) nodes.push({ id: gi * 7 + i, group: g, r: i ? 8 : 12 }); });
groups.forEach((g, gi) => { for (let i = 1; i < 7; i++) edges.push({ source: gi * 7 + (i % 2 ? 0 : i - 1), target: gi * 7 + i, kind: "link" }); });
for (let gi = 1; gi < 6; gi++) for (const i of [1, 4]) edges.push({ source: gi * 7 + i, target: 0, kind: "link" });
let seq = 7;
for (let b = 0; b < 12; b++) { seq = (seq * 31 + 11) % 42; const a = seq; seq = (seq * 17 + 5) % 42; if (Math.floor(a / 7) !== Math.floor(seq / 7)) edges.push({ source: a, target: seq, kind: "link" }); }
nodes[9].fx = nodes[9].fy = null;
const pinned = 20;
sb.onmessage({ data: { type: "init", epoch: 1, nodes, edges, alpha: 1,
  params: { gravity: 50, spread: 50, linkForce: 50, lengthByScore: true, groupBy: true, orbit: true, curved: true, shape: "organic" },
  world: { left: -900, top: -700, right: 900, bottom: 700, aspect: 0.6 } } });
const run = (code) => vm.runInContext(code, sb);
for (let t = 0; t < 2000 && run("simulation.alpha() >= simulation.alphaMin()"); t++) run("simulation.tick(); clampToWorld();");
run(`nodes[${pinned}].fx = nodes[${pinned}].x; nodes[${pinned}].fy = nodes[${pinned}].y;`);
const count = () => run("crossingsOn(untangle.edges.map((_, i) => i))");
const before = count();
const pinAt = run(`[nodes[${pinned}].x, nodes[${pinned}].y]`);
const moved = run("untangleLayout()");
const glideStart = run("nodes.filter((n) => n.tx !== undefined).length");
run("for (const n of nodes) if (n.tx !== undefined) { n.x = n.tx; n.y = n.ty; n.tx = undefined; n.ty = undefined; }");
const after = count();
const again = run("untangleLayout()");
const pinEnd = run(`[nodes[${pinned}].x, nodes[${pinned}].y]`);
const touching = run("(() => { let c = 0; for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) if (Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y) < nodes[i].r + nodes[j].r) c++; return c; })()");
const strays = run("nodes.filter((n) => !untangleInside(n) && n.fx == null).length");
console.log(JSON.stringify({ before, after, moved, glideStart, again, pinAt, pinEnd, touching, strays }));
"""


CLEANUP = UNTANGLE.split("const run = (code)")[0] + r"""
const run = (code) => vm.runInContext(code, sb);
for (let t = 0; t < 2000 && run("simulation.alpha() >= simulation.alphaMin()"); t++) run("simulation.tick(); clampToWorld();");
run("untangle.passes = 1");
// A note put dead on the middle of a long line it does not join.
const put = run(`(() => {
  const k = untangle.edges.findIndex(([a, b]) => Math.hypot(nodes[a].x - nodes[b].x, nodes[a].y - nodes[b].y) > 120);
  const [a, b] = untangle.edges[k];
  const i = nodes.findIndex((n, j) => j !== a && j !== b && n.fx == null && !untangle.incident[j].length);
  const at = i >= 0 ? i : nodes.findIndex((n, j) => j !== a && j !== b && n.fx == null);
  clearNearest(nodes[at], clearCurve(nodes[a], nodes[b]));
  nodes[at].x = clearPts[4]; nodes[at].y = clearPts[5];
  return [at, nodes[at].x, nodes[at].y];
})()`);
const onBefore = run(`untangleOnLine(${put[0]})`);
const moved = run("untangleCleanup()");
const holding = run("untangle.holding");
run("for (const n of nodes) if (n.tx !== undefined) { n.x = n.tx; n.y = n.ty; n.tx = undefined; n.ty = undefined; }");
const onAfter = run(`untangleOnLine(${put[0]})`);
const travelled = run(`Math.hypot(nodes[${put[0]}].x - ${put[1]}, nodes[${put[0]}].y - ${put[2]})`);
console.log(JSON.stringify({ onBefore, onAfter, moved, holding, travelled }));
"""


def test_a_note_left_on_a_line_is_pushed_off_it_and_the_map_ends_there() -> None:
    out = _node(CLEANUP)
    assert out["onBefore"] is True, out
    assert out["onAfter"] is False, out
    assert out["moved"] > 0 and out["holding"] is True, out
    # It clears the line, it does not travel across the map.
    assert out["travelled"] <= 40, out
    loop = WORKER[WORKER.index("\nfunction loop() {") :]
    loop = loop[: loop.index("\n}\n")]
    # Once, after the last pass has rested, never after a drag, and no tick after it.
    # At any size (round 5): above `UNTANGLE_BIG` notes it was skipped for its cost, a grid of lines made it cheap.
    # The passes and the cleanup now run together out of sight (`settleUntangled`, the
    # owner 2026-10-27: no burst a pass), so the cleanup's gate is read there.
    settle = WORKER[WORKER.index("\nfunction settleUntangled(") :]
    settle = settle[: settle.index("\n}\n")]
    assert "if (untangle.passes > 0 && !untangle.cleaned) {" in settle
    assert settle.index("untangleCleanup()") < settle.index("untangle.holding = true;")
    assert "settled && !dragging && untangleOwed()" in loop
    assert "nodes.length <= UNTANGLE_BIG" not in loop and "nodes.length <= UNTANGLE_BIG" not in settle
    assert loop.index("if (untangle.holding) {") < loop.index("simulation.tick();")
    drag = WORKER[WORKER.index('if (message.phase === "start") {') :]
    drag = drag[: drag.index('} else if (message.phase === "move")')]
    assert "untangle.cleaned = true;" in drag and "untangle.holding = false;" in drag


def test_a_settled_map_is_untangled_without_moving_a_category_or_a_pin() -> None:
    out = _node(UNTANGLE)
    # Measured: 25 crossings at rest, 0 after the pass.
    assert out["before"] >= 10, out
    assert out["after"] <= 0.7 * out["before"], out
    # The move is a glide (targets set, positions back at the start), once per layout.
    assert out["moved"] > 0 and out["glideStart"] == out["moved"], out
    assert out["again"] == 0, out
    # A pinned note stays; no two notes touch; every note stays in its category's reach.
    assert out["pinAt"] == out["pinEnd"], out
    assert out["touching"] == 0, out
    assert out["strays"] == 0, out


def test_the_untangle_waits_for_rest_and_never_follows_a_drag() -> None:
    loop = WORKER[WORKER.index("\nfunction loop() {") :]
    loop = loop[: loop.index("\n}\n")]
    # At rest, out of sight, then one glide of every note together (the owner,
    # 2026-10-27: a glide per pass and one for the cleanup read as notes
    # "sliding instantly into position one after the other";
    # tests/test_graph_open_flow.py measures it).
    assert "settled && !dragging && untangleOwed()" in loop
    assert "pendingStart(false, false, false);" in loop
    step = WORKER[WORKER.index("\nfunction pendingStep(") :]
    assert "settleGlideFrom(pending.sx, pending.sy);" in step[: step.index("\n}\n")]  # glides, not jumps
    drag = WORKER[WORKER.index('case "drag": {') :][:600]
    assert "untangle.done = true" in drag
    for case in ('case "params":', 'case "reshuffle":'):
        assert "untangle.done = false" in WORKER[WORKER.index(case) :][:200]


def test_a_new_layout_cools_several_ticks_a_frame_but_a_drag_one() -> None:
    loop = WORKER[WORKER.index("\nfunction loop() {") :]
    # The relax after a pass is no longer cooled live (it runs out of sight), so
    # "owed an untangle" is what marks a new layout's cooling.
    assert "const quick = !dragging && untangleOwed() && simulation.alpha() < WARM_ALPHA;" in loop
    assert re.search(r"^const LIVE_STEP_MS = 8;$", WORKER, re.M)


def test_organic_orders_its_ring_by_the_links_between_categories() -> None:
    order = WORKER[WORKER.index("\nfunction groupOrder() {") :]
    order = order[: order.index("\n}\n")]
    # The size-only ring of Organic is gone: one ordering, by shared lines.
    assert "if (!clustered()" not in order
    assert "ring.affinity" in order


def _fn(text: str, name: str) -> str:
    start = re.search(rf"\nfunction {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


def test_a_phone_cuts_names_shorter_so_more_of_them_fit() -> None:
    consts = "".join(
        re.search(rf"^const {name} = [\s\S]*?;$", CANVAS, re.M).group(0) + "\n"
        for name in ("GC_LABEL_NARROW_W", "GC_LABEL_NARROW_CUT", "GC_LABEL_FULL", "GC_LABEL_SMALL_WORDS")
    )
    script = (
        consts
        + _fn(REMINDERS, "clipText")
        + _fn(CANVAS, "gcLabelCut")
        + _fn(CANVAS, "gcLabelText")
        + "const gcKeyboardId = () => null;"
        + "const adj = new Map([[1, { size: 1 }], [2, { size: 6 }]]);"
        + "const text = 'Portugal trip overview and the route between cities';"
        + "const at = (w) => ({ adj, dims: { w, h: 800 }, nodes: [] });"
        + "const out = { wide: gcLabelText({ id: 1, preview: text }, at(1440)), phone: gcLabelText({ id: 1, preview: text }, at(390)),"
        + " hub: gcLabelText({ id: 2, preview: text }, at(390)) };"
        + "console.log(JSON.stringify(out));"
    )
    out = _node(script)
    assert len(out["wide"]) > 20, out
    assert len(out["phone"]) <= 15 and out["phone"].endswith("…"), out
    assert len(out["phone"]) < len(out["hub"]) <= 21, out


def test_the_untangle_runs_three_passes_with_the_relax_between_and_never_after_a_drag() -> None:
    """INBOX 1400: the second pass starts from where the first one's relax rested
    and the relax is cooled several ticks a frame so the map rests sooner. A
    third lowers the crossings further (36 notes, mean of 6 layouts offline: 53
    to 50); a map over `UNTANGLE_BIG` notes gets two, a pass that gains little
    ends them. The notes the passes leave on a line are cleared at the end
    (`test_graph_layout.py` counted 7 on lines after three passes)."""
    assert "const UNTANGLE_PASSES = 3;" in WORKER
    # The passes now run back to back out of sight (`settleUntangled`, 2026-10-27
    # "smooth and flowy"), so the loop that repeats them moved there; there is no
    # shown relax left for a drag to stop, so the drag marks the cleanup spent too.
    assert (
        "while (!untangle.done || (untangle.passes > 0 && untangle.passes < untanglePasses())) {"
        in WORKER
    )
    assert "nodes.length > UNTANGLE_BIG ? UNTANGLE_BIG_PASSES : UNTANGLE_PASSES" in WORKER
    assert "untangle.gain < Math.max(2, untangle.total * UNTANGLE_MIN_SHARE)" in WORKER
    # A drag marks the passes spent, so the ease after a drop is never untangled.
    drag = WORKER[WORKER.index('if (message.phase === "start") {') :]
    drag = drag[: drag.index('} else if (message.phase === "move")')]
    assert "untangle.passes = UNTANGLE_PASSES;" in drag and "untangle.cleaned = true;" in drag
    # Anything that lays the map out again starts the count over.
    assert WORKER.count("untangle.passes = 0;") == 3


def test_a_pass_gets_time_by_the_size_of_the_map_up_to_a_cap() -> None:
    budget = _fn(WORKER, "untangleBudget")
    assert "UNTANGLE_MS_PER_NOTE" in budget and "UNTANGLE_MS_MAX" in budget and "Math.max(UNTANGLE_MS," in budget
    assert "Date.now() + untangleBudget()" in _fn(WORKER, "untangleLayout")
    script = (
        "const UNTANGLE_MS = 200, UNTANGLE_MS_PER_NOTE = 2, UNTANGLE_MS_MAX = 600; let nodes = [];"
        + budget
        + "const at = (n) => { nodes = new Array(n); return untangleBudget(); };"
        + "console.log(JSON.stringify([at(36), at(100), at(186), at(2000)]));"
    )
    assert _node(script) == [200, 200, 372, 600]


# Round 5 (INBOX 1400): the note-on-line cleanup runs above 100 notes, on a grid of lines.
# 150 notes: six categories of 25 with a local hub and a chain in each, and bridges between them.
GRID = r"""
const fs = require("fs"), path = require("path"), vm = require("vm");
const root = process.argv[1];
const sb = { console, Math, Date, Float32Array, Float64Array, Int32Array, Uint8Array, Uint32Array, Map, Set,
  setTimeout: () => 1, clearTimeout: () => {}, setInterval: () => 1, clearInterval: () => {}, postMessage: () => {} };
sb.self = sb;
sb.importScripts = (u) => vm.runInContext(fs.readFileSync(path.join(root, u.replace(/^\//, "")), "utf8"), sb);
vm.createContext(sb);
vm.runInContext(fs.readFileSync(path.join(root, "js", "graph-worker.js"), "utf8"), sb);
const groups = ["Work", "Travel", "Cooking", "Reading", "Health", "Ideas"];
const per = 25;
const nodes = [], edges = [];
groups.forEach((g, gi) => { for (let i = 0; i < per; i++) nodes.push({ id: gi * per + i, group: g, r: i ? 8 : 12 }); });
groups.forEach((g, gi) => { for (let i = 1; i < per; i++) edges.push({ source: gi * per + (i % 3 ? 0 : i - 1), target: gi * per + i, kind: "link" }); });
let seq = 7;
for (let b = 0; b < 40; b++) { seq = (seq * 31 + 11) % 150; const a = seq; seq = (seq * 17 + 5) % 150; if (Math.floor(a / per) !== Math.floor(seq / per)) edges.push({ source: a, target: seq, kind: "link" }); }
sb.onmessage({ data: { type: "init", epoch: 1, nodes, edges, alpha: 1,
  params: { gravity: 50, spread: 50, linkForce: 50, lengthByScore: true, groupBy: true, orbit: true, curved: true, shape: "organic" },
  world: { left: -1400, top: -1000, right: 1400, bottom: 1000, aspect: 0.6 } } });
const run = (code) => vm.runInContext(code, sb);
for (let t = 0; t < 2000 && run("simulation.alpha() >= simulation.alphaMin()"); t++) run("simulation.tick(); clampToWorld();");
"""

GRID_EXACT = (
    GRID
    + r"""
// Every (note, line) pair, both ways: the grid's candidates hold every line the exact test says is near.
run("untangleReach();");
const check = (margin) => run(`(() => {
  untangle.margin = ${margin};
  lineGridBuild(untangle.widest + 15);
  let near = 0, missed = 0, disagree = 0, offered = 0;
  for (let i = 0; i < nodes.length; i++) {
    const cands = new Set(lineGridNear(nodes[i].x, nodes[i].y));
    offered += cands.size;
    for (let k = 0; k < untangle.ea.length; k++) {
      const a = untangle.ea[k], b = untangle.eb[k];
      if (a === i || b === i) continue;
      const exact = untangleNear(nodes[i], nodes[a], nodes[b]);
      if (exact) { near++; if (!cands.has(k)) missed++; }
      if (exact !== lineGridTouches(nodes[i], k)) disagree++;
    }
  }
  return { near, missed, disagree, offered, all: nodes.length * untangle.ea.length };
})()`);
const first = check(0), second = check(15);
// A note that moved takes its lines with it: filed again, the grid still holds every near line.
const moved = run(`(() => {
  untangle.margin = 3;
  const i = 40;
  nodes[i].x += 55; nodes[i].y -= 35;
  lineGridRefile(i);
  let missed = 0, disagree = 0;
  for (let j = 0; j < nodes.length; j++) {
    const cands = new Set(lineGridNear(nodes[j].x, nodes[j].y));
    for (let k = 0; k < untangle.ea.length; k++) {
      const a = untangle.ea[k], b = untangle.eb[k];
      if (a === j || b === j) continue;
      const exact = untangleNear(nodes[j], nodes[a], nodes[b]);
      if (exact && !cands.has(k)) missed++;
      if (exact !== lineGridTouches(nodes[j], k)) disagree++;
    }
  }
  return { missed, disagree };
})()`);
console.log(JSON.stringify({ first, second, moved, edges: edges.length, count: nodes.length }));
"""
)

GRID_CLEAN = (
    GRID
    + r"""
// Put free notes dead on the middle of long lines they do not join, then clean up: 150 notes is above UNTANGLE_BIG.
run("untangle.passes = 1");
const put = run(`(() => {
  const out = [];
  const used = new Set();
  for (let k = 0; k < untangle.edges.length && out.length < 12; k++) {
    const [a, b] = untangle.edges[k];
    if (Math.hypot(nodes[a].x - nodes[b].x, nodes[a].y - nodes[b].y) < 140 || used.has(a) || used.has(b)) continue;
    const i = nodes.findIndex((n, j) => j !== a && j !== b && !used.has(j) && n.fx == null && untangle.incident[j].length < 3);
    if (i < 0) continue;
    nodes[i].x = (nodes[a].x + nodes[b].x) / 2; nodes[i].y = (nodes[a].y + nodes[b].y) / 2;
    used.add(a); used.add(b); used.add(i);
    out.push(i);
  }
  return out;
})()`);
const onLines = () => run(`(() => { untangle.margin = 0; return nodes.filter((_, i) => untangleOnLine(i)).length; })()`);
const before = onLines();
const t0 = Date.now();
const moved = run("untangleCleanup()");
const ms = Date.now() - t0;
run("for (const n of nodes) if (n.tx !== undefined) { n.x = n.tx; n.y = n.ty; n.tx = undefined; n.ty = undefined; }");
const after = onLines();
const budget = run("untangleBudget()");
console.log(JSON.stringify({ n: run("nodes.length"), planted: put.length, before, after, moved, ms, budget, live: run("lineGrid.live") }));
"""
)


def test_the_grid_of_lines_offers_every_line_the_exact_test_finds_near() -> None:
    """The grid is candidates only: nothing near may be missing from it, its cached
    test agrees with `untangleNear` pair for pair, and a note that moved takes its
    lines with it (`lineGridRefile`)."""
    out = _node(GRID_EXACT)
    assert out["count"] == 150, out
    for key in ("first", "second"):
        assert out[key]["near"] > 0, out
        assert out[key]["missed"] == 0 and out[key]["disagree"] == 0, out
        # It is a grid, not a list: far fewer pairs offered than the all-pairs scan.
        assert out[key]["offered"] < out[key]["all"] / 4, out
    assert out["moved"] == {"missed": 0, "disagree": 0}, out


def test_a_map_of_150_notes_has_its_notes_cleared_off_lines_inside_the_budget() -> None:
    out = _node(GRID_CLEAN)
    assert out["n"] == 150 and out["planted"] >= 8, out
    assert out["before"] >= out["planted"], out
    assert out["after"] <= max(1, out["before"] // 4), out
    assert out["moved"] > 0, out
    # One cleanup is two halves of a pass's budget; the grid is dropped when it ends (`untangleOnLine` scans again).
    assert out["ms"] <= out["budget"] * 1.5, out
    assert out["live"] is False, out
