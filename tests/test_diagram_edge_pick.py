"""INBOX 1679 slices 3 and 4: the picture answers to a right-click, an arrow can be picked, and its ends drag.

The pure half (the distance from a point to an arrow's path, the arrow under a point) runs under node on the recorded drawing
of tests/fixtures/diagram_groups_arrows.svg; the DOM half is read for what it must hold. The gesture numbers (right-click item
counts, a pick 40 px along an arrow, one undo step) are a browser run named in docs/roadmap/agent-remaining/diagram-1679-1104.md.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
PICK = (JS / "diagram-edge-pick.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
FIXTURE = ROOT / "tests" / "fixtures" / "diagram_groups_arrows.svg"
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")
# The drawing is 408 by 489 units from (4, 4); an image of that size at (4, 4) maps a unit to a pixel.
IMG = "{left: 4, top: 4, width: 408, height: 489}"


def _run(expr: str):
    script = (
        "const vm=require('vm');const ctx={diagramModel:{},document:{},requestAnimationFrame(){},cancelAnimationFrame(){}};vm.createContext(ctx);"
        f"for (const f of ['diagram-picture.js','diagram-overlay.js','diagram-canvas.js','diagram-edges.js','diagram-edge-pick.js']) vm.runInContext(require('fs').readFileSync({json.dumps(str(JS))}+'/'+f,'utf8'),ctx);"
        f"const hit=ctx.diagramModel.picture.boxes(require('fs').readFileSync({json.dumps(str(FIXTURE))},'utf8'));const p=ctx.diagramModel.edgepick.math;"
        f"process.stdout.write(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_the_drawing_keeps_each_arrows_path_for_the_pick():
    assert _run("hit.edges.every((e) => e.pts.length >= 2 && e.d.startsWith('M'))") is True


@needs_node
def test_a_point_is_near_an_arrow_by_its_path_not_its_midpoint():
    # L_B_D_0 runs straight down from (112, 387) to (112, 407): 20 units, the midpoint at 397.
    assert _run("p.near([[0, 0], [0, 100]], 5, 40)") == 5
    assert _run("p.near([[0, 0], [0, 100]], 0, 150)") == 50
    assert _run("p.near([[0, 0]], 3, 4)") == 5


@needs_node
def test_forty_pixels_along_an_arrow_from_its_midpoint_still_picks_it():
    # L_A_B_0 is a long arrow; the old 16 px midpoint disc missed a click 40 px along it.
    assert _run("(() => { const e = hit.edges[0]; const q = e.pts[0]; return [e.y - q[1], e.id]; })()")[0] > 40
    assert _run(f"(() => {{ const e = hit.edges[2]; return p.at(hit, {IMG}, e.x, e.y - 8, 8); }})()") == "L_B_D_0"
    assert _run(f"(() => {{ const e = hit.edges[0]; const q = e.pts[0]; return p.at(hit, {IMG}, q[0], q[1] + 40, 8); }})()") in ("L_A_B_0", "L_A_C_0")


@needs_node
def test_far_from_every_path_picks_nothing_and_no_drawing_picks_nothing():
    assert _run(f"p.at(hit, {IMG}, 400, 30)") == ""
    assert _run(f"p.at(null, {IMG}, 112, 397)") == ""
    assert _run(f"p.at(hit, {IMG}, 112 + 20, 397, 8)") == ""
    assert _run(f"p.at(hit, {IMG}, 112 + 6, 397, 8)") == "L_B_D_0"


def test_the_pick_is_one_lazy_file_with_one_export_and_no_new_global_name():
    assert PICK.lstrip().startswith("//") and "(() => {" in PICK and "diagramModel.edgepick = " in PICK
    assert 'diagramEdgePick: ["/js/diagram-edge-pick.js"]' in (JS / "documents-mermaid.js").read_text(encoding="utf-8")
    builder = (JS / "diagram-builder.js").read_text(encoding="utf-8")
    assert 'ensureModule("diagramEdgePick")' in builder
    # Wired after the edges (it reads their rename), before the split.
    assert builder.index('ensureModule("diagramEdges")') < builder.index('ensureModule("diagramEdgePick")') < builder.index('ensureModule("diagramSplit")')
    assert "\nfunction " not in PICK and "\nconst " not in PICK and "\nlet " not in PICK


def test_the_picture_opens_the_blocks_menu_and_the_arrows_menu_on_a_right_click_and_a_long_press():
    assert '"contextmenu"' in PICK and "wireLongPress(fig" in PICK
    assert "h.items(S," in PICK and "diagramModel.joins.items(" in PICK and "openMenuAtPoint(" in PICK
    # The builder hands the block menu's rows over; nothing else is added to its helpers but the pick.
    assert "items: blockItems" in (JS / "diagram-builder.js").read_text(encoding="utf-8")


def test_a_picked_arrow_is_drawn_two_pixels_in_the_accent_and_deletes_in_one_commit():
    rule = CSS[CSS.index(".dgm-edge-on {") : CSS.index("}", CSS.index(".dgm-edge-on {"))]
    assert "stroke: var(--accent);" in rule and "stroke-width: 2px;" in rule and "vector-effect: non-scaling-stroke;" in rule
    assert "pointer-events: none;" in rule
    assert '"Delete"' in PICK and '"Enter"' in PICK and '"Escape"' in PICK
    assert PICK.count("h.commit(") >= 1 and "h.ops.unjoin(" in PICK and "S.renameEdge" in PICK
    # The picked arrow is looked up by Mermaid's id on every draw, so an undo that rebuilds the model cannot leave a stale one.
    assert "edgeId(S.m" in PICK
    assert "S.renameEdge = renameEdge" in (JS / "diagram-edges.js").read_text(encoding="utf-8")


MODEL = "{nodes: [{id:'A',text:'A'},{id:'B',text:'B'},{id:'E',text:'E'}], subgraphs: [], edges: [{from:'E',to:'B',label:'yes',style:'dotted',arrow:true}], kept: []}"


def _ops(expr: str):
    script = (
        "const vm=require('vm');const ctx={diagramModel:{},document:{},requestAnimationFrame(){},cancelAnimationFrame(){}};vm.createContext(ctx);"
        f"for (const f of ['diagram-ops.js','diagram-picture.js','diagram-overlay.js','diagram-edges.js','diagram-edge-pick.js']) vm.runInContext(require('fs').readFileSync({json.dumps(str(JS))}+'/'+f,'utf8'),ctx);"
        f"const p=ctx.diagramModel.edgepick.math;const ops=ctx.diagramModel.ops;const m={MODEL};"
        f"process.stdout.write(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_moving_an_arrows_end_is_one_arrow_out_and_one_in_with_its_words_line_and_arrow_kept():
    # E --> B becomes E --> A: the edge count is unchanged, the words survive, the old arrow is gone.
    out = _ops("(() => { const r = p.reconnect(ops, m, m.edges[0], 'to', 'A'); return [r, m.edges]; })()")
    assert out[0] == {"from": "E", "to": "A", "label": "yes", "style": "dotted", "arrow": True}
    assert out[1] == [out[0]]
    start = _ops("(() => { p.reconnect(ops, m, m.edges[0], 'from', 'A'); return m.edges.map((e) => e.from + e.to + e.label); })()")
    assert start == ["ABYes".replace("Y", "y")]


@needs_node
def test_a_refused_reconnect_leaves_the_old_arrow_where_it_was():
    same = _ops("(() => [p.reconnect(ops, m, m.edges[0], 'to', 'B'), m.edges.length])()")
    assert same == ["same", 1]
    loop = _ops("(() => [p.reconnect(ops, m, m.edges[0], 'to', 'E'), m.edges.length, m.edges[0].to])()")
    assert loop == ["self", 1, "B"]
    twin = _ops(
        "(() => { m.edges.push({from:'E',to:'A',label:'yes',style:'dotted',arrow:true}); return [p.reconnect(ops, m, m.edges[0], 'to', 'A'), m.edges.length, m.edges[0].to]; })()"
    )
    assert twin == ["twin", 2, "B"]


def test_an_arrow_end_drags_to_another_block_and_the_reconnect_is_one_change():
    assert ".dgm-end" in PICK and "dot.dataset.end = end" in PICK
    assert PICK.count("h.commit(") == 2  # Delete, and the reconnect: each one change, one undo step
    assert "math.reconnect(h.ops, S.m, edge, end, to)" in PICK
    # Joined first with the old words, style and arrow, so a refusal leaves the old arrow where it was.
    assert PICK.index("ops.join(m,") < PICK.index("ops.unjoin(m,")
    assert "label: edge.label, style: edge.style, arrow: edge.arrow" in PICK
    assert "is already connected to" in PICK and '"Escape"' in PICK and "setPointerCapture" in PICK
    end = CSS[CSS.index(".dgm-end {") : CSS.index("}", CSS.index(".dgm-end {"))]
    assert "pointer-events: auto;" in end and "touch-action: none;" in end and "inline-size: 12px;" in end
    assert "inline-size: 44px;" in CSS[CSS.index("@media (pointer: coarse) {\n  .dgm-end {") :][:120]
