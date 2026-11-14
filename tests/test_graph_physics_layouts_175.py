"""L-world-class-175 (IDEAS.md "Still open"): Gravity and Spread change the
Tree, Radial and Arc layouts too, not only Force. Spread is the room between
neighbouring notes; Gravity is how close a note sits to what it is filed under.
Both sliders at 50 lay the map out exactly as before."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests.test_graph_layout import D3, GRAPH, _const, _graph_function

SCRIPT = "\n".join(
    [
        f"const d3 = require({json.dumps(str(D3))});",
        *(_const(name) for name in ("TREE_ROW", "TREE_COL", "RADIAL_ARC", "RADIAL_LABEL", "RADIAL_GAP", "REPLY_RING", "ARC_STEP")),
        _graph_function("graphGroupNode"),
        _graph_function("radialRings"),
        _graph_function("replyLoops"),
        _graph_function("layoutHierarchy"),
        """
const notes = [];
for (let i = 0; i < 24; i += 1) notes.push({ id: i + 1, category: "C" + (i % 4), preview: "n" + i });
const out = {};
for (const kind of ["tree", "radial", "arc"]) {
  for (const [g, s] of [[50, 50], [0, 50], [100, 50], [50, 0], [50, 100], [null, null]]) {
    const r = layoutHierarchy(notes.map((x) => ({ ...x })), kind, 1200, 800, null, g == null ? undefined : { gravity: g, spread: s });
    const leaf = r.nodes.filter((p) => typeof p.id === "number").sort((a, b) => a.id - b.id);
    const group = r.nodes.filter((p) => p.isGroup && p.id !== "root");
    const key = `${kind}/${g}/${s}`;
    if (kind === "tree") {
      const ys = leaf.map((p) => p.y).sort((a, b) => a - b);
      out[key] = { depth: leaf[0].x - group[0].x, row: Math.min(...ys.slice(1).map((y, i) => y - ys[i]).filter((d) => d > 0.01)) };
    } else if (kind === "radial") {
      out[key] = { ratio: group[0].radius / leaf[0].radius, notes: leaf[0].radius };
    } else {
      const xs = r.nodes.map((p) => p.x + p.y).sort((a, b) => a - b);
      out[key] = { step: xs[1] - xs[0] };
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
    run = subprocess.run([node, "-e", SCRIPT], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


@pytest.mark.parametrize("kind", ["tree", "radial", "arc"])
def test_both_at_fifty_lays_out_exactly_as_before(laid, kind):
    assert laid[f"{kind}/50/50"] == laid[f"{kind}/null/null"]


def test_tree_spread_widens_rows_and_gravity_draws_notes_to_their_category(laid):
    assert laid["tree/50/0"]["row"] < laid["tree/50/50"]["row"] < laid["tree/50/100"]["row"]
    assert laid["tree/100/50"]["depth"] < laid["tree/50/50"]["depth"] < laid["tree/0/50"]["depth"]
    # A row never gets shorter than a label is tall.
    assert laid["tree/50/0"]["row"] >= 24


def test_radial_gravity_brings_the_category_ring_toward_its_notes(laid):
    assert laid["radial/0/50"]["ratio"] < laid["radial/50/50"]["ratio"] < laid["radial/100/50"]["ratio"]


def test_radial_spread_opens_the_notes_ring(laid):
    assert laid["radial/50/0"]["notes"] <= laid["radial/50/50"]["notes"] < laid["radial/50/100"]["notes"]


def test_arc_spread_sets_the_step_along_the_line(laid):
    assert laid["arc/50/0"]["step"] < laid["arc/50/50"]["step"] < laid["arc/50/100"]["step"]


def test_the_sliders_stay_live_where_they_apply():
    start = GRAPH.index("\nfunction setGraphPhysicsEnabled(")
    body = GRAPH[start : GRAPH.index("\n}\n", start)]
    assert 'tree: ["graph-gravity", "graph-spread"]' in body
    assert 'arc: ["graph-spread"]' in body
