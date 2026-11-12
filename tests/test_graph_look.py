"""INBOX 443 (1), the owner: "the graph shape could look nicer as well": a
force layout of about thirty coloured dots with straight blue-grey edges,
labels cut with "...", big glowing hubs, notes with no link floating far from
the cluster, uneven spacing. Measured with `scratchpad/ui-sweeps/graphlook.js`
(60 notes, 5 categories, 10 unlinked, 1440x900); the numbers are in the
CHANGELOG line and in GRAPH_PLAN.md's decision.

The layout is tested for real: `tests/_graph_worker_harness.js` runs the
shipped worker with the vendored d3 under a `vm`, no browser. The rest is the
source (the lints cannot see a canvas) and `gcLabelCut` run under node."""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"
HARNESS = ROOT / "tests" / "_graph_worker_harness.js"

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _scenario(*, cross_category: bool) -> dict:
    """Five categories of eight linked notes (a hub and spokes, plus a ring
    of bridges between hubs), and two unlinked notes in each category."""
    nodes, edges = [], []
    cats = ["Work", "Reading", "Ideas", "Personal", "Research"]
    for c, cat in enumerate(cats):
        for i in range(8):
            nodes.append({"id": f"{cat}-{i}", "group": cat, "r": 12 if i == 0 else 7})
        for i in range(1, 8):
            # Linked within the category, or, for the adversarial case, to the
            # same slot in the next category so no link joins two of one.
            other = f"{cats[(c + 1) % 5]}-{i}" if cross_category else f"{cat}-0"
            edges.append({"source": f"{cat}-{i}", "target": other, "kind": "link"})
        for i in range(2):
            nodes.append({"id": f"{cat}-lone-{i}", "group": cat, "r": 5})
    for c in range(5):
        edges.append({"source": f"{cats[c]}-0", "target": f"{cats[(c + 1) % 5]}-0", "kind": "link"})
    return {"nodes": nodes, "edges": edges, "ticks": 400}


def _run(scenario: dict) -> dict[str, tuple[float, float]]:
    out = subprocess.run(
        ["node", str(HARNESS)],
        input=json.dumps(scenario),
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout
    return {k: tuple(v) for k, v in json.loads(out)["positions"].items()}


def _purity(scenario: dict, at: dict[str, tuple[float, float]]) -> float:
    group = {n["id"]: n["group"] for n in scenario["nodes"]}
    same = total = 0
    for a in at:
        near = sorted((math.dist(at[a], at[b]), b) for b in at if b != a)[:4]
        for _, b in near:
            total += 1
            same += group[a] == group[b]
    return same / total


@needs_node
def test_unlinked_notes_sit_close_to_the_cluster_not_far_off():
    scenario = _scenario(cross_category=False)
    at = _run(scenario)
    linked = [k for k in at if "lone" not in k]
    lone = [k for k in at if "lone" in k]
    # Each unlinked note's gap to its nearest linked note, over the median
    # gap between linked notes: the sweep's `isoGap`, 3.0 before this pass.
    nearest = lambda p, pool: min(math.dist(at[p], at[q]) for q in pool if q != p)  # noqa: E731
    median = sorted(nearest(k, linked) for k in linked)[len(linked) // 2]
    gaps = [nearest(k, linked) / median for k in lone]
    assert max(gaps) < 4.5, gaps
    assert sum(gaps) / len(gaps) < 3.0, gaps
    # And no two unlinked notes on top of each other: the ring seats them apart.
    for i, a in enumerate(lone):
        for b in lone[i + 1 :]:
            assert math.dist(at[a], at[b]) > 14, (a, b)


@needs_node
def test_categories_gather_when_the_links_are_category_shaped():
    scenario = _scenario(cross_category=False)
    assert _purity(scenario, _run(scenario)) >= 0.8


@needs_node
def test_the_gather_stands_down_when_links_ignore_categories():
    """The 300-note fixture doubled its crossings under a gather the links did
    not follow; the pull scales with the share of links inside a category, so
    here it is the old, weak one and the links decide the shape."""
    worker = (JS / "graph-worker.js").read_text(encoding="utf-8")
    assert "function groupCohesion(edges)" in worker
    assert "cohesion = groupCohesion(edges);" in worker
    scenario = _scenario(cross_category=True)
    gathered = _purity(scenario, _run(scenario))
    scenario_in = _scenario(cross_category=False)
    assert gathered < _purity(scenario_in, _run(scenario_in))


def test_only_the_tabs_map_turns_the_ring_on():
    canvas = unwrapped((JS / "graph-canvas.js").read_text(encoding="utf-8"))
    assert 'orbit: s.size === "full",' in canvas
    worker = (JS / "graph-worker.js").read_text(encoding="utf-8")
    assert "orbit.on = Boolean(params && params.orbit === true);" in worker


def test_the_size_scale_is_one_band_and_the_glow_is_calm():
    canvas = unwrapped((JS / "graph-canvas.js").read_text(encoding="utf-8"))
    assert "const GC_MIN_RADIUS = 5;" in canvas and "const GC_MAX_RADIUS = 15;" in canvas
    assert "hub ? 0.15 : 0.09" in canvas  # was 0.24 and 0.16


def test_links_wear_their_category_and_curve_by_default():
    canvas = unwrapped((JS / "graph-canvas.js").read_text(encoding="utf-8"))
    assert "const GC_EDGE_TINTED" in canvas
    assert 'prefs.get("graph-curved", null) !== "0"' in canvas
    graph = (JS / "graph.js").read_text(encoding="utf-8")
    assert '"graph-curved": true,' in graph
    # Restored when graph.js loads, not only by the SVG render the canvas
    # path never runs (a stored "off" came back on after a reload).
    stored = graph[graph.index("const GRAPH_STORED_SWITCHES") :].split("\n", 1)[0]
    for box in ("graph-curved", "graph-label-plates", "graph-nebula", "graph-length-score", "graph-group"):
        assert f'"{box}"' in stored, box
    assert "if (box) box.checked = prefs.get(id, null) !== \"0\";" in graph
    assert "\ngraphRestoreSwitches();\n" in graph
    assert 'id="graph-curved" checked' in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    # The pointer finds a link where it is drawn: the hit test samples the
    # same bow the paint strokes.
    assert canvas.count("gcBowPoint(a, b)") >= 2


def test_the_fit_glides_only_for_a_reader_who_has_not_asked_for_less_motion():
    graph = (JS / "graph.js").read_text(encoding="utf-8")
    fit = graph[graph.index("function fitGraphToView") :]
    fit = fit[: fit.index("\n}\n")]
    # Brief 100 (d): the glide (`graphGlide`) is `graphGlideMs` long, 0 under either reduced
    # motion setting (tests/test_graph_feel_100.py runs it).
    assert 'graphGlide(svg, zoomBehavior, "transform", [framed], 500)' in fit
    glide = graph[graph.index("function graphGlideMs") :]
    assert "gcStill()) return 0;" in glide[: glide.index("\n}\n")]


@needs_node
@pytest.mark.parametrize(
    ("text", "limit", "expected"),
    [
        ("Quarterly planning with the platform team", 26, "Quarterly planning…"),
        ("Fitness plan and the long run", 26, "Fitness plan…"),
        ("Short title", 26, "Short title"),
        ("Supercalifragilisticexpialidocious", 12, "Supercalifr…"),
    ],
)
def test_a_name_is_cut_at_a_word_and_never_on_a_small_one(text, limit, expected):
    canvas = unwrapped((JS / "graph-canvas.js").read_text(encoding="utf-8"))
    clip = re.search(r"^function clipText\(text, limit\) \{.*?^\}", (JS / "shell-reminders.js").read_text(encoding="utf-8"), re.S | re.M)
    words = re.search(r"^const GC_LABEL_SMALL_WORDS = new Set\(\[.*?\]\);", canvas, re.S | re.M)
    cut = re.search(r"^function gcLabelCut\(text, limit\) \{.*?^\}", canvas, re.S | re.M)
    assert clip and words and cut
    script = "\n".join([clip.group(0), words.group(0), cut.group(0), f"process.stdout.write(gcLabelCut({json.dumps(text)}, {limit}));"])
    assert subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout == expected


def test_names_stand_on_a_plate_and_the_palette_is_calmer():
    """INBOX 493, the owner: "is there a way to make my graphed notes look
    nicer??" with labels in white over the lines. Measured with
    `scratchpad/ui-sweeps/graphlook.js` (labelOverEdge, labelsOnALine)."""
    canvas = unwrapped((JS / "graph-canvas.js").read_text(encoding="utf-8"))
    draw = canvas[canvas.index("function gcDrawLabels") :]
    draw = draw[: draw.index("\n}\n")]
    # A plate in the card's colour under each name, not a stroked halo
    # around each glyph (which left the lines showing between the letters).
    assert "ctx.roundRect(" in draw and "ctx.fillStyle = gcTokens.card;" in draw
    assert draw.count("strokeText") == 1  # only the Label backgrounds off branch
    # The placement is told where the lines are, except while the layout moves.
    assert "gcPlaceLabels(items, discs, lines ?" in canvas
    assert "s.alpha > 0.03 ? null : gcLineGrid(s, curvedLinks)" in canvas
    # Every automatic palette on the map is the calmed one; a chosen colour is not.
    graph = (JS / "graph.js").read_text(encoding="utf-8")
    assert "c.s *= 0.78;" in graph
    assert "d3.schemeTableau10.concat(d3.schemeSet3)" not in canvas
    assert graph.count("d3.schemeTableau10.concat(d3.schemeSet3)") == 1  # inside graphCalmScheme
    assert "return (name) => categoryColour(name, scale(name));" in graph


def test_label_backgrounds_are_a_switch_and_off_is_the_old_halo():
    """The owner: "can we make the dark background behind the graph labels
    togglable??". On: the plate. Off: the 3px card-coloured halo; the
    placement (clear of lines) is the same either way."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    fold = html[html.index('id="graph-display"') : html.index("</details>", html.index('id="graph-display"'))]
    assert 'id="graph-label-plates" checked' in fold
    for moved in ("graph-labels", "graph-curved", "graph-nebula"):
        assert f'id="{moved}"' in fold, moved
    canvas = unwrapped((JS / "graph-canvas.js").read_text(encoding="utf-8"))
    assert 'prefs.get("graph-label-plates", null) !== "0"' in canvas
    draw = canvas[canvas.index("function gcDrawLabels") :]
    draw = draw[: draw.index("\n}\n")]
    assert "const plates = gcLabelPlates(s);" in draw
    # The halo is drawn by `say` in screen pixels since 2026-11-10 (labels set
    # at 12 screen px, not 12 / k under the zoom); the halo itself is unchanged.
    assert "say(draw.spot.text, x, y, true);" in draw and "ctx.strokeText(text, 0, 0);" in draw
    assert "ctx.lineWidth = 3 / k;" in draw
    graph = (JS / "graph.js").read_text(encoding="utf-8")
    assert '"graph-label-plates": true,' in graph
    assert 'prefs.set("graph-label-plates"' in graph
