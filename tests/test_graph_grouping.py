"""INBOX 431 (6), the owner: the graph's default layout "looks messy and is
distributed weirdly". Measured on a 150-note, 8-category fixture
(`scratchpad/ui-sweeps/graphgroup.js`): the mean distance of a note from its
category's centre, over its distance from the map's, went from 0.85 to 0.38,
and the loose notes' ring round the map from 1.61x the linked notes'
distance from the centre to 1.24x. Off with View, Group by category."""

from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"


def test_the_worker_gathers_a_category_and_its_loose_notes():
    worker = (FRONTEND / "js" / "graph-worker.js").read_text(encoding="utf-8")
    assert 'force("groupX"' in worker and 'force("groupY"' in worker
    assert "function applyGrouping(params)" in worker
    # Loose notes firmly, linked ones gently.
    assert "node.degree === 0" in worker[worker.index("const pull = (node)"):]
    # Re-tuned with the sliders, not only at a rebuild.
    apply = worker[worker.index("function applyForces(params)"):]
    assert "applyGrouping(params)" in apply[:200]


def test_it_is_a_setting_and_only_on_the_tabs_map():
    canvas = (FRONTEND / "js" / "graph-canvas.js").read_text(encoding="utf-8")
    assert 'groupBy: s.size === "full" && prefs.get("graph-group", null) !== "0"' in canvas
    assert 'id="graph-group"' in (FRONTEND / "index.html").read_text(encoding="utf-8")
    graph = (FRONTEND / "js" / "graph.js").read_text(encoding="utf-8")
    assert '"graph-group": true' in graph
