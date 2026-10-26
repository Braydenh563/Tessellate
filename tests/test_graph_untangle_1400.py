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
    assert "settled && !untangle.done && untangleLayout()" in loop
    assert "shuffle.left = SHUFFLE_STEPS" in loop  # glides, not jumps
    drag = WORKER[WORKER.index('case "drag": {') :][:600]
    assert "untangle.done = true" in drag
    for case in ('case "params":', 'case "reshuffle":'):
        assert "untangle.done = false" in WORKER[WORKER.index(case) :][:200]


def test_a_new_layout_cools_several_ticks_a_frame_but_a_drag_one() -> None:
    loop = WORKER[WORKER.index("\nfunction loop() {") :]
    assert "const quick = !dragging && !untangle.done && simulation.alpha() < WARM_ALPHA;" in loop
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
