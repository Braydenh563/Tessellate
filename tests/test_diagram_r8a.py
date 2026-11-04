"""DOCUMENTS_PLAN 22.4 R8a (INBOX 1621): the canvas overlay, one box over each drawn node.

The mapping is pure and runs under node; the DOM half (diagram-overlay.js, lazy) is read for what it must hold. The
overlay against a real drawing at three zooms is measured in a browser (docs/roadmap/HISTORY.md names the numbers).
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
OVERLAY = (JS / "diagram-overlay.js").read_text(encoding="utf-8")
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
MERMAID_JS = (JS / "documents-mermaid.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

SVG = (
    '<svg id="m" viewBox="0 0 300 200"><g id="m-flowchart-A-0" transform="translate(60, 40)"><rect width="80" height="40"/></g>'
    '<g id="m-flowchart-B-1" transform="translate(220, 150)"><polygon points="0,0 60,0 60,50 0,50"/></g></svg>'
)


def _run(expr: str):
    script = (
        "const vm=require('vm');const ctx={diagramModel:{},document:{},requestAnimationFrame(){},cancelAnimationFrame(){}};vm.createContext(ctx);"
        f"for (const f of ['diagram-picture.js','diagram-overlay.js']) vm.runInContext(require('fs').readFileSync({json.dumps(str(JS))}+'/'+f,'utf8'),ctx);"
        f"const m=ctx.diagramModel.overlay.math;const hit=ctx.diagramModel.picture.boxes({json.dumps(SVG)});"
        f"process.stdout.write(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
@pytest.mark.parametrize("scale", [0.25, 1, 4])
def test_overlay_boxes_match_the_picture_boxes_within_one_pixel_at_three_zooms(scale):
    # The image sits 30px right and 12px down of the overlay; a box is its drawn centre and size times the scale.
    got = _run(f"m.place(hit, {{left: 130, top: 112, width: 300 * {scale}, height: 200 * {scale}}}, {{left: 100, top: 100}})")
    want = {"A": (60 - 40, 40 - 20, 80, 40), "B": (220 - 30, 150 - 25, 60, 50)}
    assert [b["id"] for b in got] == ["A", "B"]
    for b in got:
        x, y, w, h = want[b["id"]]
        assert b["x"] == pytest.approx(30 + x * scale, abs=1)
        assert b["y"] == pytest.approx(12 + y * scale, abs=1)
        assert b["w"] == pytest.approx(w * scale, abs=1)
        assert b["h"] == pytest.approx(h * scale, abs=1)


@needs_node
def test_the_hover_lookup_agrees_with_the_boxes_and_an_undecoded_image_places_nothing():
    # Node A's centre at zoom 2, image at (10, 20): client (10 + 120, 20 + 80).
    assert _run("m.at(hit, {left: 10, top: 20, width: 600, height: 400}, 130, 100)") == "A"
    assert _run("m.at(hit, {left: 10, top: 20, width: 600, height: 400}, 15, 25)") == ""
    assert _run("m.place(hit, {left: 0, top: 0, width: 300, height: 0}, {left: 0, top: 0})") == []
    assert _run("m.place(null, {left: 0, top: 0, width: 300, height: 200}, {left: 0, top: 0})") == []


def test_the_overlay_is_one_lazy_file_a_sibling_of_the_figure_that_never_takes_a_press():
    assert 'diagramOverlay: ["/js/diagram-overlay.js"]' in MERMAID_JS
    assert 'ensureModule("diagramOverlay")' in BUILDER and "diagramModel.overlay.wire(S)" in BUILDER
    assert OVERLAY.count("diagramModel.overlay =") == 1 and OVERLAY.lstrip().startswith("// diagram-overlay.js")
    assert "stage.append(layer)" in OVERLAY and "fig.append" not in OVERLAY
    assert "(fig.onpaint ||= []).push(draw)" in OVERLAY
    assert "aria-selected" in OVERLAY and "Observer" not in OVERLAY and "requestAnimationFrame" not in OVERLAY  # read from the list; no new wake source
    assert "(fig.onzoom ||= []).push(draw)" in OVERLAY and "fig.onzoom" in (JS / "diagram-view.js").read_text(encoding="utf-8")
    start = CSS.index(".dgm-overlay {")
    assert "pointer-events: none" in CSS[start : CSS.index("}", start)]
    box = CSS[CSS.index(".dgm-box.on {") :].split("}")[0]
    assert "var(--accent)" in box and "var(--accent-soft)" in box


def test_the_overlay_is_in_the_guide_in_the_controls_words():
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-builder"))
    assert len(body) < 1900 and "the picture outlines the block you point at and the ones picked" in body


@needs_node
def test_a_pill_drawn_as_one_path_takes_its_size_from_the_path_not_the_default():
    svg = (
        '<svg viewBox="0 0 300 200"><g id="m-flowchart-D-1" transform="translate(100, 50)"><g><path d="M-63.5 -22 C-19 -22, 23 -22, 63.5 -22 '
        'C66 -21, 67 -20, 68 -10 C68 0, 68 10, 63.5 22 C20 22, -20 22, -63.5 22 C-68 10, -68 -10, -63.5 -22" fill="none"/></g></g>'
        '<g id="m-flowchart-E-2" transform="translate(200, 50)"><rect width="30" height="20"/></g></svg>'
    )
    script = (
        "const vm=require('vm');const ctx={diagramModel:{}};vm.createContext(ctx);"
        f"vm.runInContext(require('fs').readFileSync({json.dumps(str(JS / 'diagram-picture.js'))},'utf8'),ctx);"
        f"process.stdout.write(JSON.stringify(ctx.diagramModel.picture.boxes({json.dumps(svg)}).boxes));"
    )
    got = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    d, e = got
    assert (d["w"], d["h"]) == pytest.approx((136, 44))  # 68 to -68 wide; the pill's own height
    assert (e["w"], e["h"]) == (30, 20)  # the next node's rect is not read for D
