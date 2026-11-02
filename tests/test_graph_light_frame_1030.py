"""Audit 1029 G3 / audit 1028 S2: a 2,000-note map is drawn plain while it moves, and settles in about 100 ticks.

Measured on a cold open of 2,000 notes and 3,796 links (Chromium, 1x, session
scratch `sgs/lt.js`): the main thread had 149 long tasks summing 15.7 s (max
559 ms) and the worker's end message came at 24.7 s. A tick drew curves, sprites
and names, and the worker spent 55 to 77 ms of each 83 to 124 ms tick in the
line-clearance force. Now:

- a map of 2,500 notes and links or more, while its layout runs, is drawn by
  `gcDrawLight` (the shortest links up to a length budget in one stroke, one
  dot path per colour), unless something needs the full frame;
- the clearance force reads the notes from cell-sorted typed arrays;
- a big map cools in about 100 ticks (`alphaDecayFor`).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
WORKER = (JS / "graph-worker.js").read_text(encoding="utf-8")
CANVAS = (JS / "graph-canvas.js").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _function(text: str, name: str) -> str:
    start = re.search(rf"\nfunction {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


def _node(script: str):
    run = subprocess.run([shutil.which("node"), "-e", script], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout.strip().splitlines()[-1])


LIGHT = r"""
const GC_LIGHT_ITEMS = %s;
const gcTickSnaps = (s) => s.snaps;
const graphTrace = null;
let graphHighlightIds = null;
const box = { value: "" };
const gcEl = () => box;
%s
const base = () => ({ layoutRunning: true, size: "full", tree: null, dragNode: null, hoveredId: null, paintMode: null,
  fitCheck: 0, revealAfterFit: false, nodes: new Array(2000), edges: new Array(3796), snaps: true });
const out = {};
out.running = gcLightFrame(base());
const no = (label, patch) => { out[label] = gcLightFrame(Object.assign(base(), patch)); };
no("settled", { layoutRunning: false });
no("pane", { size: "pane" });
no("tree", { tree: {} });
no("dragging", { dragNode: {} });
no("hover", { hoveredId: 3 });
no("layer", { paintMode: "rest" });
no("fitting", { fitCheck: 2 });
no("revealing", { revealAfterFit: true });
no("small", { nodes: new Array(300), edges: new Array(400) });
no("cheap", { snaps: false });
box.value = "graph";
out.searching = gcLightFrame(base());
box.value = "";
graphHighlightIds = new Set([1]);
out.spotlight = gcLightFrame(base());
console.log(JSON.stringify(out));
"""


@needs_node
def test_a_big_map_is_drawn_plain_only_while_its_layout_runs_and_nothing_needs_the_full_frame() -> None:
    items = re.search(r"\nconst GC_LIGHT_ITEMS = (\d+);", CANVAS).group(1)
    out = _node(LIGHT % (items, _function(CANVAS, "gcLightFrame")))
    running = out.pop("running")
    assert running is True
    assert not any(out.values()), out


def test_the_draw_hands_a_light_frame_over_before_the_composed_scene_and_costs_are_not_noted_for_it() -> None:
    draw = _function(CANVAS, "gcDraw")
    assert draw.index("gcLightFrame(s)") < draw.index("gcDrawComposed(s)")
    request = _function(CANVAS, "gcRequestDraw")
    assert "s.lightDrawn = false;" in request
    # A light frame says nothing about what a full one costs, or `gcTickSnaps` would flip back to gliding.
    assert "if (full && !s.lightDrawn) gcNoteDrawCost(" in request
    light = _function(CANVAS, "gcDrawLight")
    # The scene layers and fades are stale after it, so the frame at rest paints whole.
    for line in ("s.lightDrawn = true;", "s.scene = null;", "s.sceneStale = true;", "s.composed = false;"):
        assert line in light, line


def test_a_light_frame_strokes_one_path_whose_length_is_budgeted_not_every_link() -> None:
    light = _function(CANVAS, "gcDrawLight")
    assert light.count("ctx.stroke(") == 1
    assert "GC_LIGHT_LINE_PX" in light and "cutoff" in light
    assert not re.search(r"quadraticCurveTo|drawImage|gcPlaceLabels|fillText", light)
    assert int(re.search(r"const GC_LIGHT_LINE_PX = (\d+);", CANVAS).group(1)) <= 150000


@needs_node
def test_a_2000_note_map_cools_in_about_a_hundred_ticks_and_a_small_one_is_unchanged() -> None:
    start = WORKER.index("const SETTLE_FULL_TICKS_UP_TO")
    end = WORKER.index("\n}\n", WORKER.index("function alphaDecayFor")) + 3
    script = (
        "const ALPHA_DECAY = 0.0228;\n"
        + WORKER[start:end]
        + "\nconst ticks = (d) => Math.ceil(Math.log(0.001) / Math.log(1 - d));"
        + "\nconsole.log(JSON.stringify([ticks(alphaDecayFor(500)), ticks(alphaDecayFor(750)), ticks(alphaDecayFor(2000)), ticks(alphaDecayFor(5000))]));"
    )
    small, edge, big, huge = _node(script)
    assert small > 290 and edge > 290
    assert 90 <= big <= 125 and huge <= 125, (big, huge)


def test_the_clearance_scan_reads_flat_arrays_not_note_objects() -> None:
    force = _function(WORKER, "clearanceForce")
    assert "sx[k] - ax" in force and "sneed[k]" in force
    # A note's object is read only once it is within reach of the chord.
    assert force.index("sneed[k]") < force.index("const node = nodes[at];")
    assert "node._clear" not in force and "mark[at] === stamp" in force
