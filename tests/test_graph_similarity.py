"""Similarity on the graph reads as a few faint, graded lines, not a hairball.

INBOX 412, the owner: "when I tick similarity on the graph, this happens, is
there a way to make it more visually understandable or parsable??". Measured
on a 42-note notebook: 200 similarity lines (the server's cap) against 24
links, up to 20 on one note, every one the same dotted blue and drawn over
the links, and 1,701 crossings.

The model lives between `GRAPH-SIM-BEGIN` and `GRAPH-SIM-END` in
graph-canvas.js and is pure (no DOM, no app globals), so python runs it in
node the way the document models are tested. Three pieces:

- `gcPruneSimilarity`: each note keeps only its `k` strongest similarity
  lines above a cutoff (a k-nearest-neighbour backbone, which is how Gephi
  and InfraNodus thin a weighted network before drawing it); every other
  kind of edge passes through untouched.
- `gcSimilarityBand`: the score becomes one of three strengths, relative to
  the range actually drawn, so the strongest line on the map is always the
  most visible whatever the embedding model's baseline is.
- `gcPlaceLabels`: a label is drawn only where it covers neither a label
  already placed nor another note's dot, except the one pointed at and a
  handful of search hits, which were asked for.

The static checks hold the wiring the model cannot see: similarity is drawn
beneath the links, the worker lays a similarity line out by its score, the
cutoff slider and the reset exist in the options panel.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CANVAS_JS = ROOT / "frontend" / "js" / "graph-canvas.js"
WORKER_JS = ROOT / "frontend" / "js" / "graph-worker.js"
GRAPH_JS = ROOT / "frontend" / "js" / "graph.js"
INDEX = ROOT / "frontend" / "index.html"

BEGIN = "// GRAPH-SIM-BEGIN"
END = "// GRAPH-SIM-END"


def model_source() -> str:
    text = CANVAS_JS.read_text(encoding="utf-8")
    start = text.find(BEGIN)
    stop = text.find(END)
    assert start != -1, f"{BEGIN} marker is missing from graph-canvas.js"
    assert stop > start, f"{END} marker is missing or before {BEGIN}"
    return text[start + len(BEGIN) : stop]


DRIVER = r"""
const results = [];
function check(name, ok, detail) {
  results.push({ name, ok: !!ok, detail: detail === undefined ? null : detail });
}
const id = (end) => (end && end.id != null ? end.id : end);

// A complete graph on ten notes, every pair similar, scores all distinct.
const complete = [];
for (let a = 0; a < 10; a++) {
  for (let b = a + 1; b < 10; b++) {
    complete.push({ source: a, target: b, kind: 'similar', score: 0.56 + ((a * 7 + b * 3) % 40) / 100 });
  }
}
const links = [{ source: 0, target: 1, kind: 'link' }, { source: 2, target: 3, kind: 'thread' }];

// --- top-k -----------------------------------------------------------------
{
  const kept = gcPruneSimilarity(complete.concat(links), { k: 2, threshold: 0.55 });
  const sim = kept.filter((e) => e.kind === 'similar');
  check('topk/every other kind of edge passes through', kept.filter((e) => e.kind !== 'similar').length === 2, kept.length);
  check('topk/at most k per note, counted from the note that chose it', sim.length <= 10 * 2, sim.length);
  check('topk/far fewer than all pairs', sim.length < complete.length / 2, [sim.length, complete.length]);
  // Every kept line is among the k strongest of at least one of its ends.
  const topOf = (n, k) =>
    complete
      .filter((e) => e.source === n || e.target === n)
      .sort((x, y) => y.score - x.score)
      .slice(0, k);
  const bad = sim.filter((e) => !topOf(e.source, 2).includes(e) && !topOf(e.target, 2).includes(e));
  check('topk/every kept line is a top-k line of one of its ends', bad.length === 0, bad.length);
  // Every note keeps its own k strongest.
  const missing = [];
  for (let n = 0; n < 10; n++) for (const e of topOf(n, 2)) if (!sim.includes(e)) missing.push([n, e.score]);
  check('topk/every note keeps its own k strongest', missing.length === 0, JSON.stringify(missing));
  const again = gcPruneSimilarity(complete.concat(links), { k: 2, threshold: 0.55 });
  check('topk/deterministic', JSON.stringify(again) === JSON.stringify(kept), '');
  const k3 = gcPruneSimilarity(complete, { k: 3, threshold: 0.55 });
  check('topk/a larger k keeps more', k3.length > sim.length, [k3.length, sim.length]);
}

// --- the cutoff --------------------------------------------------------------
{
  const kept = gcPruneSimilarity(complete, { k: 5, threshold: 0.8 });
  check('cutoff/nothing below it survives', kept.every((e) => e.score >= 0.8), '');
  check('cutoff/something above it does', kept.length > 0, kept.length);
  const none = gcPruneSimilarity(complete.concat(links), { k: 2, threshold: 0.99 });
  check('cutoff/links survive a cutoff that drops every similarity line', none.length === 2, none.length);
  const noScore = gcPruneSimilarity([{ source: 1, target: 2, kind: 'similar' }], { k: 2, threshold: 0.5 });
  check('cutoff/a line with no score is dropped, not drawn at full strength', noScore.length === 0, noScore.length);
}

// --- ends given as objects (the renderer resolves them) ---------------------
{
  const nodes = Array.from({ length: 4 }, (_, i) => ({ id: `n${i}` }));
  const edges = [
    { source: nodes[0], target: nodes[1], kind: 'similar', score: 0.9 },
    { source: nodes[0], target: nodes[2], kind: 'similar', score: 0.8 },
    { source: nodes[0], target: nodes[3], kind: 'similar', score: 0.7 },
    { source: nodes[1], target: nodes[2], kind: 'similar', score: 0.6 },
  ];
  const kept = gcPruneSimilarity(edges, { k: 1, threshold: 0.5 });
  const pairs = kept.map((e) => `${id(e.source)}-${id(e.target)}`).sort();
  // n0 keeps n1; n1 keeps n0; n2 keeps n0 (0.8); n3 keeps n0 (0.7).
  check('objects/k=1 keeps each end\'s best', JSON.stringify(pairs) === JSON.stringify(['n0-n1', 'n0-n2', 'n0-n3']), JSON.stringify(pairs));
  check('objects/defaults are k=2 and no extra cutoff', gcPruneSimilarity(edges).length === 4, gcPruneSimilarity(edges).length);
}

// --- strength bands ------------------------------------------------------------
{
  check('band/lowest is 0', gcSimilarityBand(0.6, 0.6, 0.9) === 0, gcSimilarityBand(0.6, 0.6, 0.9));
  check('band/highest is 2', gcSimilarityBand(0.9, 0.6, 0.9) === 2, gcSimilarityBand(0.9, 0.6, 0.9));
  check('band/middle is 1', gcSimilarityBand(0.75, 0.6, 0.9) === 1, gcSimilarityBand(0.75, 0.6, 0.9));
  let last = -1;
  let monotonic = true;
  for (let s = 0.6; s <= 0.9; s += 0.01) {
    const b = gcSimilarityBand(s, 0.6, 0.9);
    if (b < last) monotonic = false;
    last = b;
  }
  check('band/monotonic in the score', monotonic, '');
  check('band/one score on the map is the strongest', gcSimilarityBand(0.7, 0.7, 0.7) === 2, gcSimilarityBand(0.7, 0.7, 0.7));
  check('band/out of range clamps', gcSimilarityBand(2, 0.6, 0.9) === 2 && gcSimilarityBand(-1, 0.6, 0.9) === 0, '');
  const styles = [0, 1, 2].map((b) => GC_SIMILAR_BANDS[b]);
  check('band/stronger is more visible', styles[0].alpha < styles[1].alpha && styles[1].alpha < styles[2].alpha, JSON.stringify(styles));
  check('band/stronger is wider', styles[0].width < styles[1].width && styles[1].width < styles[2].width, JSON.stringify(styles));
  check('band/never as loud as a link at its strongest', styles[2].alpha <= 0.5, styles[2].alpha);
  check('band/one dash for every band', new Set(styles.map((s) => JSON.stringify(s.dash))).size === 1, '');
}

// --- label placement -----------------------------------------------------------
{
  const box = (id, left, top, rank = 2) => ({ id, rank, force: false, left, right: left + 40, top, bottom: top + 10 });
  const placed = gcPlaceLabels(
    [box('a', 0, 0), box('b', 20, 5), box('c', 100, 0)],
    [],
  );
  check('labels/a clash is skipped', placed.map((p) => p.id).join() === 'a,c', placed.map((p) => p.id).join());
  const onDisc = gcPlaceLabels(
    [box('a', 0, 0), box('b', 200, 0)],
    [{ id: 'x', x: 20, y: 5, r: 4 }, { id: 'b', x: 220, y: 5, r: 6 }],
  );
  check('labels/a label over another note is skipped, its own note is not an obstacle', onDisc.map((p) => p.id).join() === 'b', onDisc.map((p) => p.id).join());
  const nearDisc = gcPlaceLabels([box('a', 0, 0)], [{ id: 'x', x: 20, y: 30, r: 4 }]);
  check('labels/a note beside the box is not a clash', nearDisc.length === 1, nearDisc.length);
  const forced = gcPlaceLabels(
    [box('a', 0, 0), { ...box('h', 10, 2, 0), force: true }],
    [{ id: 'x', x: 15, y: 5, r: 4 }],
  );
  check('labels/a forced label is drawn through anything', forced.map((p) => p.id).join() === 'h', forced.map((p) => p.id).join());
  // A grid is used for the dots; a big map must still find the one under the box.
  const many = [];
  for (let i = 0; i < 2000; i++) many.push({ id: `d${i}`, x: 5000 + i * 3, y: 5000, r: 2 });
  many.push({ id: 'under', x: 30, y: 5, r: 3 });
  const found = gcPlaceLabels([box('a', 0, 0)], many);
  check('labels/the dot under a label is found among many', found.length === 0, found.length);
  // INBOX 493: a name goes to its first place that crosses no line, else to
  // the one crossing the fewest; without a count, the first free place.
  const spots = (id) => ({ ...box(id, 0, 0), alts: [{ left: 0, right: 40, top: -30, bottom: -20 }, { left: 50, right: 90, top: 0, bottom: 10 }] });
  const lines = (counts) => (b) => counts[b.top === -30 ? 1 : b.left === 50 ? 2 : 0];
  const clear = gcPlaceLabels([spots('a')], [], lines([2, 0, 0]));
  check('labels/a line under the first place sends the name to the next clear one', clear[0].top === -30, JSON.stringify(clear[0]));
  // INBOX 693, the owner's decision "labels never over dots or lines": with
  // no clear place an ordinary name is left off; a landmark (a hub the map is
  // read by) takes the place crossing the fewest.
  const fewest = gcPlaceLabels([{ ...spots('a'), landmark: true }], [], lines([3, 2, 1]));
  check('labels/a landmark with no clear place takes the one crossing the fewest lines', fewest[0].left === 50, JSON.stringify(fewest[0]));
  const dropped = gcPlaceLabels([spots('a')], [], lines([3, 2, 1]));
  check('labels/an ordinary name with no clear place is left off', dropped.length === 0, JSON.stringify(dropped));
  // A landmark takes a place on no dot, or none (the waiver of 2026-09-26 ends).
  const offDot = gcPlaceLabels([{ ...spots('a'), landmark: true }], [{ id: 'b', x: 10, y: 5, r: 3 }]);
  check('labels/a landmark steps off a dot when it can', offDot[0].top === -30, JSON.stringify(offDot[0]));
  const onDots = gcPlaceLabels([{ ...box('a', 0, 0), landmark: true }], [{ id: 'b', x: 10, y: 5, r: 3 }]);
  check('labels/a landmark with no place off a dot is left off', onDots.length === 0, JSON.stringify(onDots));
  const plain = gcPlaceLabels([spots('a')], []);
  check('labels/without a line count the first free place, as always', plain[0].left === 0 && plain[0].top === 0, JSON.stringify(plain[0]));
  // The line grid's count: a horizontal segment through a box, one past it.
  const cells = new Map();
  const fileSeg = (ax, ay, bx, by) => {
    for (let cx = Math.floor(Math.min(ax, bx) / GC_LINE_CELL); cx <= Math.floor(Math.max(ax, bx) / GC_LINE_CELL); cx++) {
      const key = cx * 100003 + Math.floor(ay / GC_LINE_CELL);
      if (!cells.has(key)) cells.set(key, []);
      cells.get(key).push(ax, ay, bx, by);
    }
  };
  fileSeg(-10, 5, 30, 5);
  fileSeg(-10, 30, 30, 30);
  const grid = { cells };
  check('lines/a segment through the box counts', gcBoxLineCount(grid, { left: 0, right: 20, top: 0, bottom: 10 }) === 1, '');
  check('lines/a segment beside the box does not', gcBoxLineCount(grid, { left: 0, right: 20, top: 12, bottom: 20 }) === 0, '');
}

// --- score pills -----------------------------------------------------------------
{
  const a = { x: 0, y: 0 };
  const b = { x: 100, y: 0 };
  const open = gcPlacePill(a, b, 20, 10, [], []);
  check('pill/an open line takes its first stop, nearer the match', open.placed && open.x === 62, JSON.stringify(open));
  const blocked = gcPlacePill(a, b, 20, 10, [{ left: 55, right: 70, top: -5, bottom: 5 }], []);
  check('pill/a label in the way moves it along the line', blocked.placed && blocked.x !== 62 && blocked.y === 0, JSON.stringify(blocked));
  const onDot = gcPlacePill(a, b, 20, 10, [], [{ x: 62, y: 0, r: 4 }]);
  check('pill/a dot in the way moves it too', onDot.placed && Math.abs(onDot.x - 62) > 10, JSON.stringify(onDot));
  const everywhere = [{ left: -10, right: 110, top: -20, bottom: 20 }];
  const full = gcPlacePill(a, b, 20, 10, everywhere, []);
  check('pill/nowhere free says so, so it is left out rather than stacked', !full.placed, JSON.stringify(full));
}

process.stdout.write(JSON.stringify(results));
"""


@pytest.fixture(scope="module")
def model_checks(tmp_path_factory) -> list[dict]:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path_factory.mktemp("graphsim") / "run.js"
    script.write_text(model_source() + DRIVER, encoding="utf-8")
    out = subprocess.run(
        [node, str(script)], capture_output=True, text=True, timeout=60, check=False
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_model_runs_without_a_browser(model_checks: list[dict]) -> None:
    assert len(model_checks) > 25, "the driver did not reach the end"


def test_the_model_holds_its_properties(model_checks: list[dict]) -> None:
    failed = [c for c in model_checks if not c["ok"]]
    assert not failed, "\n".join(f"{c['name']}: {c['detail']}" for c in failed[:20])


def test_similarity_is_drawn_beneath_the_links() -> None:
    """The edge pass strokes every similarity bucket before any other.

    Measured before: the buckets were stroked in the order their first edge
    arrived, and the server appends similarity lines after the links, so the
    faint inferred lines were painted over the solid ones they are meant to
    sit behind.
    """
    text = CANVAS_JS.read_text(encoding="utf-8")
    draw = text[text.find("function gcDraw(") :]
    draw = draw[: draw.find("\n}\n")]
    # Graded once per render in `gcEdgeLook` (Brief 100), which gcDraw calls.
    look = text[text.find("function gcEdgeLook(") :]
    look = look[: look.find("\n}\n")]
    assert "gcEdgeLook(" in draw and "gcSimilarityBand(" in look, "gcDraw does not grade similarity lines by score"
    under = draw.find("simBuckets")
    over = draw.find("for (const bucket of buckets.values())")
    assert under != -1 and over != -1
    assert draw.find("for (const bucket of simBuckets.values())") < over, (
        "similarity buckets must be stroked before the links"
    )


def test_the_render_prunes_before_the_layout_sees_the_edges() -> None:
    """Pruned in `renderGraphCanvas`, so the springs, the degree (node size)
    and the stats line all see the backbone, not the hairball."""
    text = CANVAS_JS.read_text(encoding="utf-8")
    render = text[text.find("async function renderGraphCanvas(") :]
    render = render[: render.find("\n}\n")]
    assert "gcPruneSimilarity(" in render


def test_the_worker_lays_similarity_out_by_its_score() -> None:
    """Length by similarity was a no-op on the canvas renderer: the worker
    was never sent a score, so its link length was a constant per kind."""
    worker = WORKER_JS.read_text(encoding="utf-8")
    at = worker.find("linkDistance:")
    assert at != -1 and "edge.score" in worker[at : at + 500], "the worker ignores the score"
    assert "score: e.score" in worker, "the worker drops the score when it builds its edges"
    canvas = CANVAS_JS.read_text(encoding="utf-8")
    init = canvas[canvas.find('type: "init"') :]
    init = init[: init.find("}, s);")]
    # The switches ride `gcWorkerParams`, which the init sends (and a
    # Curved links change sends again on its own, INBOX 693).
    assert "score" in init and "params: gcWorkerParams(s)" in init
    params = canvas[canvas.find("function gcWorkerParams(") :]
    assert "lengthByScore" in params[: params.find("\n}\n")]


def test_the_cutoff_and_the_key_are_in_the_options_panel() -> None:
    html = INDEX.read_text(encoding="utf-8")
    panel = html[html.find('id="graph-options"') :]
    panel = panel[: panel.find('<!-- Trace:')]
    assert 'id="graph-similarity-min"' in panel, "no similarity cutoff slider"
    # INBOX 1400: Show is a closed fold, so the slider sits with the controls that
    # are always open (View, under Size), not inside the fold it would be hidden in.
    slider = panel.index('id="graph-similarity-min-row"')
    assert panel.index('id="graph-view-section"') < slider < panel.index('id="graph-toggle-group"'), (
        "the strength slider must be in the View section, before the closed Show fold"
    )
    assert "Match strength" in panel[slider : slider + 400]
    help_body = panel[panel.find('id="graph-show-help"') :]
    help_body = help_body[: help_body.find("</div>")]
    assert "Similarity" in help_body and "solid" in help_body.lower(), (
        "the Show section's '?' must say what the two line styles mean"
    )



def test_the_reset_covers_every_persisted_graph_setting() -> None:
    """Every `graph-*` key the options panel or the View menu persists is in
    the reset's list, so a setting added later without joining it fails here
    rather than surviving a reset silently."""
    js = GRAPH_JS.read_text(encoding="utf-8")
    start = js.find("const GRAPH_DEFAULTS")
    assert start != -1, "graph.js has no GRAPH_DEFAULTS table"
    table = js[start : js.find("};", start)]
    for control in (
        "graph-gravity",
        "graph-spread",
        "graph-similarity",
        "graph-similarity-min",
        "graph-entities",
        "graph-documents",
        "graph-maps",
        "graph-hide-orphans",
        "graph-labels",
        "graph-curved",
        "graph-label-plates",
        "graph-nebula",
        "graph-length-score",
        "graph-time-slider",
        "graph-minimap-corner",
        "graph-minimap-size",
        "graph-colour",
    ):
        assert f'"{control}"' in table, f"{control} is missing from GRAPH_DEFAULTS"
    assert "layout" in table
