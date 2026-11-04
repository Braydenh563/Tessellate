"""DOCUMENTS_PLAN 22.4 R8b (INBOX 1621): palette drop and node move on the canvas, and the marquee.

The pure half (the sweep, the node under a point) runs under node; the DOM half is read for what it must hold. The drag
against a real drawing (updates per second, `mermaidRequest` calls before the drop, the printed source) is measured in a
browser; docs/roadmap/HISTORY.md names the numbers.
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
CANVAS = (JS / "diagram-canvas.js").read_text(encoding="utf-8")
POINTER = (JS / "diagram-pointer.js").read_text(encoding="utf-8")
MERMAID_JS = (JS / "documents-mermaid.js").read_text(encoding="utf-8")
VIEW = (JS / "diagram-view.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

SVG = (
    '<svg id="m" viewBox="0 0 300 200"><g id="m-flowchart-A-0" transform="translate(60, 40)"><rect width="80" height="40"/></g>'
    '<g id="m-flowchart-B-1" transform="translate(220, 150)"><polygon points="0,0 60,0 60,50 0,50"/></g></svg>'
)


def _run(expr: str):
    script = (
        "const vm=require('vm');const ctx={diagramModel:{},document:{},requestAnimationFrame(){},cancelAnimationFrame(){}};vm.createContext(ctx);"
        f"for (const f of ['diagram-picture.js','diagram-overlay.js','diagram-canvas.js']) vm.runInContext(require('fs').readFileSync({json.dumps(str(JS))}+'/'+f,'utf8'),ctx);"
        f"const m=ctx.diagramModel.canvas.math;const hit=ctx.diagramModel.picture.boxes({json.dumps(SVG)});"
        f"process.stdout.write(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


IMG = "{left: 10, top: 20, width: 300, height: 200}"


@needs_node
def test_a_sweep_picks_the_nodes_it_touches_in_drawing_order():
    # A spans (20..100, 20..60) and B (190..250, 125..175) in drawing units; the image sits at (10, 20), so A is at client (30..110, 40..80).
    assert _run(f"m.sweep(hit, {IMG}, {{left: 0, top: 0, right: 60, bottom: 60}})") == ["A"]
    assert _run(f"m.sweep(hit, {IMG}, {{left: 0, top: 0, right: 400, bottom: 400}})") == ["A", "B"]
    assert _run(f"m.sweep(hit, {IMG}, {{left: 120, top: 90, right: 180, bottom: 110}})") == []


@needs_node
def test_a_sweep_may_be_dragged_up_and_left_and_an_undecoded_picture_sweeps_nothing():
    assert _run(f"m.sweep(hit, {IMG}, {{left: 60, top: 60, right: 0, bottom: 0}})") == ["A"]
    assert _run("m.sweep(hit, {left: 0, top: 0, width: 300, height: 0}, {left: 0, top: 0, right: 999, bottom: 999})") == []
    assert _run(f"m.sweep(null, {IMG}, {{left: 0, top: 0, right: 999, bottom: 999}})") == []


@needs_node
def test_the_node_under_a_press_is_the_overlays_answer():
    assert _run(f"m.nodeAt(hit, {IMG}, 70, 60)") == "A"
    assert _run(f"m.nodeAt(hit, {IMG}, 15, 25)") == ""


def test_the_canvas_is_one_lazy_file_with_one_export_and_no_new_global_name():
    assert CANVAS.lstrip().startswith("//") and "(() => {" in CANVAS and "diagramModel.canvas = " in CANVAS
    assert "diagramCanvas: [\"/js/diagram-canvas.js\"]" in MERMAID_JS
    assert 'ensureModule("diagramCanvas")' in (JS / "diagram-builder.js").read_text(encoding="utf-8")
    assert "\nfunction " not in CANVAS and "\nconst " not in CANVAS and "\nlet " not in CANVAS


def test_the_pointer_mode_drops_on_the_canvas_with_the_canvas_target_and_the_overlay_draws_it():
    # The drop needs the node under the point; the feedback is on the overlay box, so a drag never asks for a new picture.
    assert "diagramModel.canvas?.over(" in POINTER and "target.canvas" in POINTER
    assert "mermaidRequest" not in CANVAS and "drawPicture" not in CANVAS
    assert ".dgm-box.dgm-target" in CSS and ".dgm-marquee" in CSS and ".dgm-box.swept" in CSS


def test_a_tile_dropped_on_a_node_adds_after_it_and_connects():
    assert "from: target.from" in POINTER or "...(target.from" in POINTER


def test_the_marquee_is_shift_drag_on_empty_space_and_stops_the_pan():
    assert "shiftKey" in CANVAS and "stopImmediatePropagation" in CANVAS
    assert "obj-dragging" in VIEW  # a node being moved is not a pan


def test_the_multi_pane_offers_its_pick_to_the_marquee():
    assert "S.pick = show" in (JS / "diagram-multi.js").read_text(encoding="utf-8")


def test_the_canvas_gestures_are_in_the_guide_in_the_controls_words():
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-builder"))
    assert len(body) < 1900
    assert "drag a shape from the Add strip onto the picture" in body and "hold Shift and drag on empty space" in body
