"""1679 (m): the bugs a fresh-eyes tester found on the diagram editor, and the visible kinds and boxes."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._app_js import app_js_text  # noqa: F401  (the helper every frontend test reads through)
from tests.test_mermaid_frame import FRAME_JS, _run_region

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
STEPS = (JS / "diagram-steps.js").read_text(encoding="utf-8")
VIEW = (JS / "diagram-view.js").read_text(encoding="utf-8")
EDGES = (JS / "diagram-edges.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")


def _overlay(expr: str):
    script = (
        "const vm=require('vm');const ctx={diagramModel:{}};vm.createContext(ctx);"
        f"vm.runInContext(require('fs').readFileSync({json.dumps(str(JS / 'diagram-overlay.js'))},'utf8'),ctx);"
        f"const m=ctx.diagramModel.overlay.math;process.stdout.write(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_an_entity_in_a_drawn_label_becomes_its_character():
    # Mermaid hands back `&amp;quot;` for a written `#quot;`; the picture must show the quote (measured: it showed the entity).
    out = _run_region(
        FRAME_JS, "// MERMAID-ENTITY-BEGIN", "// MERMAID-ENTITY-END",
        'function mermaidFrameSized() {}\n' + 'const f = (t) => mermaidFrameSized.entities(t);\nconsole.log(JSON.stringify([f("say &quot;hi&quot; &lt;b&gt; x&amp;y &#35;1"), f("plain & text"), f("&#99999999;")]));',
    )
    assert out == ['say "hi" <b> x&y #1', "plain & text", "&#99999999;"]
    assert "mermaidFrameSized.entities(node.nodeValue)" in FRAME_JS.read_text(encoding="utf-8")


@needs_node
def test_a_handle_shrinks_with_its_block_and_keeps_a_floor():
    # At 25% a block is 38 x 20 px: the four 24 px handles covered it. Half the smaller side, 14 px at least (24 on touch).
    assert _overlay("[m.handleSize({w:38,h:20},24,14), m.handleSize({w:150,h:44},24,14), m.handleSize({w:70,h:30},44,24), m.handleSize({w:300,h:90},44,24)]") == [14, 22, 24, 44]
    assert "overlay().handleSize(at, full" in EDGES and "style.inlineSize" in EDGES


def test_an_emptied_name_is_put_back_in_its_row_and_an_empty_row_says_unnamed():
    assert "return (label.textContent = nameOf(S, key)), render(S);" in BUILDER
    assert '.dgm-label:empty::before' in CSS and 'content: "Unnamed"' in CSS


def test_the_empty_hint_goes_before_the_first_draw_so_it_and_the_pending_line_never_show_together():
    start = BUILDER.index("function drawPicture")
    body = BUILDER[start : BUILDER.index("// --- the tree", start)]
    assert body.index('.dgm-hint")?.remove()') < body.index('ensureModule("mermaid")')


def test_the_first_step_says_box_in_lower_case_and_the_buttons_leave_once_the_foot_has_them():
    assert "Add a box" in STEPS and "Add a Box" not in STEPS
    assert ".dgm-empty.dgm-started .dgm-step button" in CSS


def test_a_drag_on_a_picture_that_fits_says_why_nothing_moved():
    assert "dgm-pan-note" in VIEW and "Zoom in to pan" in VIEW and ".dgm-pan-note" in CSS
    assert "wasted > 24" in VIEW
