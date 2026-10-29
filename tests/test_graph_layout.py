"""Graph layout: the intentional force layout and Reshuffle, the layout chip, layouts independent of note order, and the fitted view after a switch."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest


# A more intentional force layout and a Reshuffle: the real worker run in node, settled geometry measured (browser half: scratchpad/ui-sweeps/graph692.js).


ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
WORKER = (JS / "graph-worker.js").read_text(encoding="utf-8")

HARNESS = r"""
const vm = require("vm");
const fs = require("fs");
const [workerPath, d3Path, optsJson] = process.argv.slice(1);
const opts = JSON.parse(optsJson);
const out = [];
// The loop is stepped by hand below, so no timer ever fires.
const ctx = { console, setTimeout: () => 1, clearTimeout: () => {}, setInterval: () => 1, clearInterval: () => {} };
ctx.self = ctx;
// The main thread hands every frame's buffer back (`recycle`), or the worker
// stops posting frames once two are in flight.
ctx.postMessage = (m) => {
  out.push(m);
  if (m.type === "tick") ctx.onmessage({ data: { type: "recycle" } });
};
ctx.importScripts = () => vm.runInContext(fs.readFileSync(d3Path, "utf8"), ctx);
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(workerPath, "utf8"), ctx);
let seed = 7;
const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
const cats = ["Work", "Travel", "Cooking", "Reading", "Health", "Home", "Ideas"];
const sizes = [14, 11, 10, 9, 8, 7, 9];
const nodes = [];
const edges = [];
const byCat = {};
cats.forEach((cat, c) => {
  byCat[cat] = [];
  for (let i = 0; i < sizes[c]; i++) {
    const id = `${cat}-${i}`;
    byCat[cat].push(id);
    nodes.push({ id, r: 6, group: cat });
  }
});
const link = (a, b, kind = "link") => edges.push({ source: a, target: b, kind });
// Work and Travel: a hub and a dense web; Cooking: two hubs; Reading: a
// chain; Health: a star; Home: mostly loose; Ideas: bridges between them.
for (const cat of ["Work", "Travel"]) {
  const ids = byCat[cat];
  for (let i = 1; i < ids.length - 1; i++) link(ids[0], ids[i]);
  for (let i = 2; i < ids.length - 1; i++) link(ids[i], ids[1 + Math.floor(rnd() * (i - 1))]);
}
const cook = byCat.Cooking;
for (let i = 2; i < cook.length; i++) link(cook[i % 2], cook[i]);
link(cook[0], cook[1]);
const read = byCat.Reading;
for (let i = 1; i < read.length - 1; i++) link(read[i - 1], read[i]);
const health = byCat.Health;
for (let i = 1; i < health.length; i++) link(health[0], health[i]);
link(byCat.Home[0], byCat.Home[1]);
const ideas = byCat.Ideas;
const hubs = ["Work-0", "Travel-0", "Cooking-0", "Reading-3", "Health-0"];
ideas.slice(0, 6).forEach((id, i) => { link(id, hubs[i % hubs.length]); link(id, hubs[(i + 2) % hubs.length]); });
link(ideas[6], ideas[7]);
const pinned = opts.pin ? { id: "Home-4", x: 40, y: 40 } : null;
const world = { left: -1200, top: -900, right: 1200, bottom: 900, aspect: 900 / 1440 };
const init = {
  type: "init", epoch: 1, nodes: nodes.map((n) => (pinned && n.id === pinned.id ? { ...n, fx: pinned.x, fy: pinned.y, x: pinned.x, y: pinned.y } : n)),
  edges, world, alpha: 1,
  params: { gravity: 50, spread: 50, linkForce: 50, lengthByScore: true, groupBy: true, orbit: true, curved: opts.curved !== false, shape: opts.shape || "organic" },
};
// Place as the main thread does (the phyllotaxis spiral), so the run is the
// app's own start.
const golden = Math.PI * (3 - Math.sqrt(5));
init.nodes.forEach((n, i) => {
  if (n.x != null) return;
  n.x = 10 * Math.sqrt(0.5 + i) * Math.cos(i * golden);
  n.y = 10 * Math.sqrt(0.5 + i) * Math.sin(i * golden);
});
const send = (m) => ctx.onmessage({ data: m });
const settle = () => {
  for (let i = 0; i < 4000; i++) {
    const ends = out.filter((m) => m.type === "end").length;
    vm.runInContext("timer = null; loop();", ctx);
    if (out.filter((m) => m.type === "end").length > ends) return i;
  }
  return -1;
};
send(init);
const firstTicks = settle();
const snap = () => vm.runInContext("nodes.map((n) => [n.id, n.x, n.y, n.r, n.group])", ctx);
const result = { firstTicks, first: snap() };
if (opts.reshuffle) {
  out.length = 0;
  send({ type: "reshuffle", seed: opts.reshuffle, animate: true });
  // The animated move posts frames before the layout restarts.
  vm.runInContext("timer = null; loop();", ctx);
  result.firstFrameAlpha = out.find((m) => m.type === "tick").alpha;
  result.shuffleTicks = settle();
  result.after = snap();
}
result.edges = edges.map((e) => [e.source, e.target]);
console.log(JSON.stringify(result));
"""


def _run(**opts) -> dict:
    out = subprocess.run(
        [
            "node",
            "-e",
            HARNESS,
            str(JS / "graph-worker.js"),
            str(ROOT / "frontend" / "vendor" / "d3.v7.min.js"),
            json.dumps(opts),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _bow(a, b):
    """The renderer's own curve (`gcBowPoint`, graph-canvas.js)."""
    dx, dy = b[1] - a[1], b[2] - a[2]
    length = (dx * dx + dy * dy) ** 0.5 or 1
    side = 1 if str(a[0]) < str(b[0]) else -1
    bow = min(length * 0.14, 48) * side
    return ((a[1] + b[1]) / 2 - dy / length * bow, (a[2] + b[2]) / 2 + dx / length * bow)


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy or 1
    u = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length))
    return ((px - ax - u * dx) ** 2 + (py - ay - u * dy) ** 2) ** 0.5


def _geometry(positions, edges, curved=True):
    at = {p[0]: p for p in positions}
    touching = 0
    for i, a in enumerate(positions):
        for b in positions[i + 1 :]:
            gap = ((a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5 - a[3] - b[3]
            if gap < 2:
                touching += 1
    through = 0
    for s, t in edges:
        a, b = at[s], at[t]
        if curved:
            c = _bow(a, b)
            pts = [
                (
                    (1 - u) ** 2 * a[1] + 2 * (1 - u) * u * c[0] + u * u * b[1],
                    (1 - u) ** 2 * a[2] + 2 * (1 - u) * u * c[1] + u * u * b[2],
                )
                for u in (i / 16 for i in range(17))
            ]
        else:
            pts = [(a[1], a[2]), (b[1], b[2])]
        for n in positions:
            if n[0] in (s, t):
                continue
            d = min(_seg_dist(n[1], n[2], *pts[i - 1], *pts[i]) for i in range(1, len(pts)))
            if d < n[3]:
                through += 1
    return touching, through


def _hub_central(positions, edges):
    """Each category's best-connected note within it (four or more lines to
    its own category, so a chain has no hub): its distance from the middle
    of the category's linked notes, over their mean distance from it."""
    group_of = {p[0]: p[4] for p in positions}
    degree: dict = {}
    for s, t in edges:
        if group_of[s] != group_of[t]:
            continue
        degree[s] = degree.get(s, 0) + 1
        degree[t] = degree.get(t, 0) + 1
    ratios = []
    for group in {p[4] for p in positions}:
        # The cluster is its linked notes: a loose note sits on the orbit
        # round the whole map (INBOX 443), not in its category's middle.
        members = [p for p in positions if p[4] == group and degree.get(p[0], 0)]
        top = max(members, key=lambda p: degree.get(p[0], 0))
        if degree.get(top[0], 0) < 4:
            continue
        cx = sum(p[1] for p in members) / len(members)
        cy = sum(p[2] for p in members) / len(members)
        mean = sum(((p[1] - cx) ** 2 + (p[2] - cy) ** 2) ** 0.5 for p in members) / len(members)
        ratios.append((((top[1] - cx) ** 2 + (top[2] - cy) ** 2) ** 0.5) / mean)
    return sum(ratios) / len(ratios)


def _moat(positions, edges):
    """The 10th percentile, over notes, of the gap to the nearest note of
    another category that it is not linked to: the narrow end of the space
    between clusters."""
    linked = {(s, t) for s, t in edges} | {(t, s) for s, t in edges}
    gaps = []
    for a in positions:
        best = min(
            (
                ((a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5 - a[3] - b[3]
                for b in positions
                if b[4] != a[4] and (a[0], b[0]) not in linked
            ),
            default=None,
        )
        if best is not None:
            gaps.append(best)
    gaps.sort()
    return gaps[len(gaps) // 10]


node_only = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


@node_only
@pytest.mark.parametrize(
    "shape,curved",
    [("organic", True), ("organic", False), ("clusters", True), ("galaxy", True)],
)
def test_no_link_runs_through_a_note_it_does_not_join_and_no_two_notes_touch(shape, curved):
    """In every Shape (the owner, 693: "all shapes keep 0 overlap")."""
    run = _run(curved=curved, shape=shape)
    assert run["firstTicks"] > 0
    # Only Organic draws its lines curved (`_straight`, `clearCurve`).
    touching, through = _geometry(run["first"], run["edges"], curved and shape == "organic")
    assert touching == 0
    assert through == 0


@node_only
def test_hubs_sit_at_the_heart_of_their_category_with_space_between_categories():
    run = _run(shape="clusters")
    assert _hub_central(run["first"], run["edges"]) < 0.4
    assert _moat(run["first"], run["edges"]) >= 24


@node_only
def test_reshuffle_reseeds_the_unpinned_notes_animates_and_settles_clean():
    run = _run(reshuffle=12345, pin=True, shape="clusters")
    before = {p[0]: p for p in run["first"]}
    after = {p[0]: p for p in run["after"]}
    moved = sum(
        1
        for key, p in before.items()
        if ((p[1] - after[key][1]) ** 2 + (p[2] - after[key][2]) ** 2) ** 0.5 > 20
    )
    assert moved > len(before) * 0.6
    # A pinned note is where it was pinned.
    assert after["Home-4"][1:3] == [40, 40]
    # The first frame is the start of a glide, not the jump to the new seed,
    # and it reports a hot layout so the main thread's fit waits for it.
    assert run["firstFrameAlpha"] >= 0.9
    assert run["shuffleTicks"] > 20
    touching, through = _geometry(run["after"], run["edges"], curved=False)
    assert (touching, through) == (0, 0)
    # The same seed lays the same map out: a reshuffle is a choice, not noise.
    again = _run(reshuffle=12345, pin=True, shape="clusters")
    assert again["after"] == run["after"]


def test_the_reshuffle_control_sits_beside_unpin_all_and_is_explained():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    physics = html[html.index('id="graph-physics"') :]
    physics = physics[: physics.index("</details>")]
    assert 'id="graph-reshuffle"' in physics
    assert physics.index('id="graph-unpin-all"') < physics.index('id="graph-reshuffle"')
    wiring = (JS / "graph.js").read_text(encoding="utf-8")
    assert '$("graph-reshuffle")' in wiring
    canvas = (JS / "graph-canvas.js").read_text(encoding="utf-8")
    assert "function gcReshuffle(" in canvas
    assert 'type: "reshuffle"' in canvas
    assert 'case "reshuffle"' in WORKER
    help_text = (ROOT / "src" / "tessellate" / "ai" / "help_chat.py").read_text(encoding="utf-8")
    assert "Reshuffle layout" in help_text


@node_only
def test_loose_notes_sit_together_and_the_bridging_category_in_the_middle():
    """The owner's second pass (693): "orphans gathered into a tidy group per
    category or at their cluster's rim", and no note "floating between
    clusters with no clear home"."""
    run = _run(shape="clusters")
    positions, edges = run["first"], run["edges"]
    linked = {s for s, _ in edges} | {t for _, t in edges}
    loose = [p for p in positions if p[4] == "Home" and p[0] not in linked]
    spread = max(
        ((a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5 for a in loose for b in loose
    )
    assert len(loose) >= 4 and spread < 160
    # Ideas links to five other categories and hardly to itself: it stands in
    # the middle, so its lines run one ring-radius rather than across the map.
    cx = sum(p[1] for p in positions) / len(positions)
    cy = sum(p[2] for p in positions) / len(positions)
    middle = {}
    for group in {p[4] for p in positions}:
        members = [p for p in positions if p[4] == group and p[0] in linked]
        if members:
            gx = sum(p[1] for p in members) / len(members)
            gy = sum(p[2] for p in members) / len(members)
            middle[group] = ((gx - cx) ** 2 + (gy - cy) ** 2) ** 0.5
    assert min(middle, key=middle.get) == "Ideas"


def test_the_shape_control_is_saved_and_reaches_the_worker():
    """INBOX 693: "different preferred shapes or ways of structuring the
    force graph", one control, Organic (the layout the notebook had) first
    and the default."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    view = html[html.index('id="graph-view-section"') :]
    view = view[: view.index("</div>\n            <!-- GRAPH_PLAN Phase 3")]
    assert 'id="graph-shape"' in view
    options = view[view.index('id="graph-shape"') :]
    options = options[: options.index("</select>")]
    assert [part.split('"')[0] for part in options.split('value="')[1:]] == ["organic", "clusters", "galaxy"]
    graph = (JS / "graph.js").read_text(encoding="utf-8")
    assert 'prefs.set("graph-shape", shape.value)' in graph
    canvas = (JS / "graph-canvas.js").read_text(encoding="utf-8")
    assert "shape: gcShape(s)," in canvas
    assert 'const SHAPES = new Set(["organic", "clusters", "galaxy"]);' in WORKER
    help_text = (ROOT / "src" / "tessellate" / "ai" / "help_chat.py").read_text(encoding="utf-8")
    assert "Shape (Organic, Clusters or Galaxy;" in help_text


def test_link_styles_carry_meaning_on_three_channels_with_a_key():
    """INBOX 693, the owner: "should links visualise differently or have a
    different style based on distance, similarity, type of link etc??"."""
    canvas = (JS / "graph-canvas.js").read_text(encoding="utf-8")
    # Strength: a deduced reason draws its link thinner and fainter.
    assert 'edge.kind === "link" && typeof edge.reason_confidence === "number"' in canvas
    # Between categories: faint, in Clusters, and keyed.
    assert "GC_CROSS_WIDTH" in canvas and "GC_CROSS_ALPHA" in canvas
    key = canvas[canvas.index("function gcLegendEdgeKey(") :]
    key = key[: key.index("\n}\n")]
    assert 'swatch("cross", "Between categories")' in key
    css = (ROOT / "frontend" / "css" / "02-chat-graph.css").read_text(encoding="utf-8")
    assert ".legend-line-cross {" in css


def test_shape_is_dimmed_with_its_reason_off_the_force_layout():
    """The owner, 2026-10-10: "the graph shape options shouldnt be enabled
    when on a view other than force". `setGraphPhysicsEnabled` runs on every
    layout change and on arrival, so it is where the Shape list follows the
    layout, dimmed with a reason like the Physics sliders beside it."""
    graph = (JS / "graph.js").read_text(encoding="utf-8")
    start = graph.index("\nfunction setGraphPhysicsEnabled(")
    body = graph[start : graph.index("\n}\n", start)]
    assert "shape.disabled = !applies;" in body
    assert "Shape applies to the Force layout only" in body
    assert '$("graph-shape-row")?.classList.toggle("is-disabled", !applies);' in body
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'class="graph-option-row graph-physics" id="graph-shape-row"' in html
    help_text = (ROOT / "src" / "tessellate" / "ai" / "help_chat.py").read_text(encoding="utf-8")
    assert "the Force layout's own, dimmed under the others" in help_text


# The graph names a fixed layout with a chip, and notes leaving the picture fade out.


CANVAS = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")


def test_the_dock_chip_is_hidden_under_force_and_opens_the_layout_choice():
    assert re.search(r'<button id="graph-layout-chip" class="[^"]*\bhidden\b[^"]*" type="button"', HTML)
    body = CANVAS[CANVAS.index("function graphSyncLayoutChip(") :]
    body = body[: body.index("\n}\n")]
    assert 'layoutKind !== "force"' in body and 'classList.toggle("hidden", !named)' in body
    assert "setGraphOptionsOpen(true)" in body and "openGraphControlsSheet(chip)" in body
    assert 'focusSelect(document.getElementById("graph-layout"))' in body
    # The stats line calls it, so it never leaves a stale chip.
    assert "graphSyncLayoutChip(layoutKind);" in CANVAS


def test_the_chip_survives_the_phone_dock_that_hides_every_other_chip():
    assert re.search(r"\.dock-identity > #graph-layout-chip:not\(\.hidden\) \{\s*display: inline-flex;", CSS)


def test_a_note_leaving_the_picture_fades_instead_of_vanishing():
    mark = CANVAS[CANVAS.index("function gcMarkLeaving(") :]
    mark = mark[: mark.index("\n}\n")]
    assert "gcStill()" in mark, "less motion keeps the cut"
    assert "staying.has(n.id)" in mark
    draw = CANVAS[CANVAS.index("function gcDrawLeaving(") :]
    draw = draw[: draw.index("\n}\n")]
    assert "GC_BORN_MS" in draw and "s.bornPending = true" in draw, "the fade must keep the frame loop going"
    assert "gcMarkLeaving(s, graphNodesRef, nodes);\n  s.epoch += 1;" in CANVAS, "marked before graphNodesRef is replaced"
    assert "gcDrawLeaving(ctx, s, bornAt);" in CANVAS


# Computed layouts do not depend on the order /graph lists notes.


GRAPH = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")
D3 = ROOT / "frontend" / "vendor" / "d3.v7.min.js"


def _graph_function(name: str) -> str:
    start = GRAPH.index(f"\nfunction {name}(") + 1
    return GRAPH[start : GRAPH.index("\n}\n", start) + 2]


def _const(name: str) -> str:
    return re.search(rf"^const {name} = [^\n]*", GRAPH, re.M).group(0)


ORDER_SCRIPT = "\n".join(
    [
        f"const d3 = require({json.dumps(str(D3))});",
        *(_const(name) for name in ("TREE_ROW", "TREE_COL", "RADIAL_ARC", "RADIAL_LABEL", "RADIAL_GAP", "REPLY_RING", "ARC_STEP")),
        _graph_function("graphGroupNode"),
        _graph_function("radialRings"),
        _graph_function("replyLoops"),
        _graph_function("layoutHierarchy"),
        """
const n = (id, extra = {}) => ({ id, category: "A", preview: String(id), ...extra });
const cases = {
  replyFirst: [n(3, { parent_id: 2 }), n(2, { parent_id: 1 }), n(1), n(4, { category: "B" })],
  selfReply: [n(1, { parent_id: 1 }), n(2)],
  cycle: [n(1, { parent_id: 2 }), n(2, { parent_id: 1 }), n(3)],
};
const out = {};
for (const [name, nodes] of Object.entries(cases)) {
  for (const kind of ["tree", "radial", "arc"]) {
    try {
      const r = layoutHierarchy(nodes.map((x) => ({ ...x })), kind, 1200, 800);
      const notes = r.nodes.filter((p) => typeof p.id === "number");
      out[`${name}/${kind}`] = {
        ids: notes.map((p) => p.id).sort(),
        finite: notes.every((p) => Number.isFinite(p.x) && Number.isFinite(p.y)),
        threads: r.links.filter((l) => l.kind === "thread").map((l) => [l.source.id, l.target.id]),
      };
    } catch (e) {
      out[`${name}/${kind}`] = { error: String(e) };
    }
  }
}
console.log(JSON.stringify(out));
""",
    ]
)


@pytest.fixture(scope="module")
def laid():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    run = subprocess.run([node, "-e", ORDER_SCRIPT], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


@pytest.mark.parametrize("kind", ["tree", "radial", "arc"])
def test_a_reply_listed_before_the_note_it_answers_is_laid_out_under_it(laid, kind):
    got = laid[f"replyFirst/{kind}"]
    assert "error" not in got, got
    assert got["ids"] == [1, 2, 3, 4] and got["finite"]
    assert sorted(got["threads"]) == [[1, 2], [2, 3]]


@pytest.mark.parametrize("case", ["selfReply", "cycle"])
@pytest.mark.parametrize("kind", ["tree", "radial", "arc"])
def test_a_reply_chain_that_loops_is_filed_under_its_category_not_lost(laid, case, kind):
    got = laid[f"{case}/{kind}"]
    assert "error" not in got, got
    expected = [1, 2] if case == "selfReply" else [1, 2, 3]
    assert got["ids"] == expected and got["finite"]
    assert got["threads"] == []


def _layout() -> str:
    start = GRAPH.index("function layoutHierarchy(")
    return GRAPH[start : GRAPH.index("d3.hierarchy(", start)]


def test_every_child_list_exists_before_any_is_filled():
    body = _layout()
    seed = body.index("for (const node of nodes) children.set(node.id, []);")
    assert seed < body.index("children.get(parent.id).push(node)")


def test_a_reply_loop_hangs_off_its_category():
    assert "!replyLoops(node, byId)" in _layout()


# A layout switch ends on the fitted view of the new layout.


def _function(text: str, name: str) -> str:
    start = re.search(rf"\n(async )?function {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


def test_the_render_decides_to_frame_before_its_first_await():
    body = _function(CANVAS, "renderGraphCanvas")
    first_await = body.index("await ")
    decided = body.index("const reframe = !gcAutoFitDone(s)")
    assert decided < first_await
    # And the decision, not the flag a stale tick can spend, is what frames
    # both kinds of layout.
    assert "if (reframe || !gcAutoFitDone(s))" in body
    assert "if (reframe) gcSetAutoFitDone(s, false);\n    gcStartWorker(" in body


FIT_SCRIPT = "\n".join(
    [
        _function(GRAPH, "graphMinimapFinite"),
        _function(GRAPH, "frameTree"),
        _function(GRAPH, "graphGlideMs"),
        """
let got = null;
const gcStill = () => false;
const d3 = { zoomIdentity: { translate(x, y) { return { scale(k) { return { x, y, k }; } }; } } };
const svg = { transition() { return { duration() { return { call(_f, t) { got = t; } }; } }; } };
// A ring of twelve notes round (600, 400), every one at radius 150.
const ring = Array.from({ length: 12 }, (_, i) => ({
  x: 600 + 150 * Math.cos((i / 12) * 2 * Math.PI),
  y: 400 + 150 * Math.sin((i / 12) * 2 * Math.PI),
  depth: 1,
}));
frameTree(svg, { transform: null }, ring, 1400, 800, true, false);
const mid = { x: got.x + got.k * 600, y: got.y + got.k * 400 };
console.log(JSON.stringify({ k: got.k, mid }));
""",
    ]
)


@pytest.fixture(scope="module")
def framed():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    run = subprocess.run([node, "-e", FIT_SCRIPT], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def test_a_radial_is_centred_in_the_view(framed):
    assert abs(framed["mid"]["x"] - 700) < 1
    assert abs(framed["mid"]["y"] - 400) < 1
