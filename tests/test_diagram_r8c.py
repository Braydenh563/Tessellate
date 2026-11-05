"""DOCUMENTS_PLAN 22.4 R8c (INBOX 1621): groups and arrows read off the picture, the edge handle, and rename in place.

The pure half (the boxes read off a recorded SVG, the group and arrow under a point) runs under node; the DOM half is read
for what it must hold. The gesture check (the decision and two branches from canvas gestures only, in fewer than 12) is a
browser run: docs/roadmap/HISTORY.md names the numbers.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
EDGES = (JS / "diagram-edges.js").read_text(encoding="utf-8")
CANVAS = (JS / "diagram-canvas.js").read_text(encoding="utf-8")
FIXTURE = ROOT / "tests" / "fixtures" / "diagram_groups_arrows.svg"
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _run(expr: str):
    script = (
        "const vm=require('vm');const ctx={diagramModel:{},document:{},requestAnimationFrame(){},cancelAnimationFrame(){}};vm.createContext(ctx);"
        f"for (const f of ['diagram-picture.js','diagram-overlay.js','diagram-canvas.js','diagram-edges.js']) vm.runInContext(require('fs').readFileSync({json.dumps(str(JS))}+'/'+f,'utf8'),ctx);"
        f"const hit=ctx.diagramModel.picture.boxes(require('fs').readFileSync({json.dumps(str(FIXTURE))},'utf8'));const o=ctx.diagramModel.overlay.math;const e=ctx.diagramModel.edges.math;"
        f"process.stdout.write(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


# The recorded drawing is 408 by 489 units from (4, 4); an image of 408 by 489 at (0, 0) maps a unit to a pixel, shifted by (-4, -4).
IMG = "{left: 4, top: 4, width: 408, height: 489}"


@needs_node
def test_the_groups_are_read_off_the_drawing_by_the_subgraphs_own_id():
    assert _run("hit.clusters") == [{"id": "S1", "x": 112, "y": 390.5, "w": 200, "h": 189}]
    assert _run("hit.boxes.map((b) => b.id)") == ["A", "B", "C", "D"]


@needs_node
def test_each_arrow_is_found_by_mermaids_id_at_a_point_on_its_path():
    assert _run("hit.edges.map((x) => x.id)") == ["L_A_B_0", "L_A_C_0", "L_B_D_0"]
    # Half way along L_B_D_0 (111.99, 387 to 407) is its middle; the elbowed ones sit on their own path, not beside it.
    mid = _run("hit.edges[2]")
    assert round(mid["x"]) == 112 and round(mid["y"]) == 397
    ab = _run("hit.edges[0]")
    assert round(ab["x"]) == 112 and 200 <= ab["y"] <= 339


@needs_node
def test_the_group_under_a_point_is_the_innermost_and_a_node_outside_it_is_not_in_it():
    assert _run(f"o.clusterAt(hit, {IMG}, 112 - 4 + 4, 450)") == "S1"
    assert _run(f"o.clusterAt(hit, {IMG}, 330, 100)") == ""
    assert _run(f"o.clusterAt(null, {IMG}, 112, 450)") == ""


@needs_node
def test_the_arrow_nearest_a_point_within_reach_is_the_one_picked():
    assert _run(f"e.edgeAt(hit, {IMG}, 112, 397)") == "L_B_D_0"
    assert _run(f"e.edgeAt(hit, {IMG}, 112, 397, 2)") == "L_B_D_0"
    assert _run(f"e.edgeAt(hit, {IMG}, 400, 30)") == ""
    assert _run(f"e.edgeAt(null, {IMG}, 112, 397)") == ""


@needs_node
def test_an_arrows_id_counts_the_arrows_with_the_same_two_ends():
    m = "{edges: [{from:'A',to:'B'},{from:'A',to:'B'},{from:'B',to:'A'}]}"
    assert _run(f"(() => {{ const m = {m}; return m.edges.map((x) => e.edgeId(m, x)); }})()") == ["L_A_B_0", "L_A_B_1", "L_B_A_0"]


def test_the_edge_handle_is_one_lazy_file_with_one_export_and_no_new_global_name():
    assert EDGES.lstrip().startswith("//") and "(() => {" in EDGES and "diagramModel.edges = " in EDGES
    assert 'diagramEdges: ["/js/diagram-edges.js"]' in (JS / "documents-mermaid.js").read_text(encoding="utf-8")
    assert 'ensureModule("diagramEdges")' in (JS / "diagram-builder.js").read_text(encoding="utf-8")
    assert "\nfunction " not in EDGES and "\nconst " not in EDGES and "\nlet " not in EDGES


def test_a_drag_from_the_handle_never_asks_for_a_picture_before_the_change_is_made():
    assert "mermaidRequest" not in EDGES and "drawPicture" not in EDGES
    # A press with no drag, or Enter, arms it; Escape puts it back; empty space adds a block that is already connected.
    assert 'aria-pressed' in EDGES and '"Escape"' in EDGES and "from," in EDGES
    assert "event.detail === 0" in EDGES


def test_the_canvas_drops_into_the_group_under_the_pointer_but_never_into_a_dragged_group():
    assert "groupAt" in CANVAS and "h.ops.inside(S.m, cl" in CANVAS and ".dgm-cluster" in CANVAS


def test_the_handle_is_a_44px_target_on_a_touch_screen_and_the_overlay_otherwise_takes_no_press():
    rule = CSS[CSS.index("@media (pointer: coarse) {\n  .dgm-handle {") :]
    assert "inline-size: 44px;" in rule[:200]
    assert "pointer-events: auto;" in CSS[CSS.index(".dgm-handle {") : CSS.index("}", CSS.index(".dgm-handle {"))]
    assert "pointer-events: none;" in CSS[CSS.index(".dgm-rubber {") : CSS.index("}", CSS.index(".dgm-rubber {"))]


def test_the_new_gestures_are_in_the_guide_in_the_controls_words():
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-builder"))
    assert len(body) < 1900
    assert "drag the round handle" in body and "double-click" in body


def test_a_picked_block_shows_four_handles_one_a_side_that_keep_the_ghost_class_and_an_accent_ink():
    """INBOX 1679: the handle was filled-button ink on the canvas colour (1.1:1) and only on the right, on hover. Four sides now,
    `ghost small` kept, glyph and ring in the accent (measured 7.7 to 8.8:1 glyph to disc, 5.9 light and 7.0 dark ring to canvas)."""
    assert '["top", "right", "bottom", "left"]' in EDGES and 'b.className = "dgm-handle ghost small hidden"' in EDGES
    assert "b.dataset.side = side" in EDGES and "anchor(at, handle.dataset.side)" in EDGES
    rule = CSS[CSS.index(".dgm-handle.ghost.small {") : CSS.index("}", CSS.index(".dgm-handle.ghost.small {"))]
    assert "color: var(--accent-text);" in rule and "border: 2px solid var(--accent);" in rule
    for side in ("top", "bottom", "left"):
        assert f'.dgm-handle[data-side="{side}"]' in CSS
