"""1679 (m): the bugs a fresh-eyes tester found on the diagram editor, and the visible kinds and boxes."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

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


KINDBAR = (JS / "diagram-kindbar.js").read_text(encoding="utf-8")


def test_the_kinds_are_four_worded_buttons_mounted_by_both_toolbars():
    # Before: a sequence diagram, mind map or timeline was only reachable through Suggest's templates.
    for word in ('"Flowchart"', '"Sequence"', '"Mind map"', '"Timeline"', '"sequenceDiagram"'):
        assert word in KINDBAR, word
    assert "diagramModel.kindbar?.mount(S, h)" in (JS / "diagram-bar.js").read_text(encoding="utf-8")
    assert "diagramModel.kindbar?.mount(S, kit)" in (JS / "diagram-kinds.js").read_text(encoding="utf-8")
    assert 'diagramKindbar: ["/js/diagram-kindbar.js"]' in (JS / "documents-mermaid.js").read_text(encoding="utf-8")
    assert 'ensureModule("diagramKindbar")' in BUILDER and ".dgm-kinds" in CSS
    assert "Undo, Ctrl+Z" in KINDBAR


@needs_node
def test_a_new_kind_starts_from_its_header_and_keeps_the_front_matter():
    script = (
        "const vm=require('vm');const ctx={diagramModel:{}};vm.createContext(ctx);"
        f"vm.runInContext(require('fs').readFileSync({json.dumps(str(JS / 'documents-mermaid.js'))},'utf8').split('\\n').join('\\n'),ctx);"
    )
    del script  # the kind bar reads the model's `front`; a stub of it is enough here
    run = (
        "const vm=require('vm');const ctx={diagramModel:{front:(t)=>{const m=/^---[ \\t]*\\n[\\s\\S]*?\\n---[ \\t]*(?:\\n|$)/.exec(t);return {front:m?m[0].replace(/\\n$/,'').split('\\n'):[],rest:m?t.slice(m[0].length):t}}}};vm.createContext(ctx);"
        f"vm.runInContext(require('fs').readFileSync({json.dumps(str(JS / 'diagram-kindbar.js'))},'utf8'),ctx);"
        "const f=ctx.diagramModel.kindbar.fresh;process.stdout.write(JSON.stringify([f('flowchart TD\\nA-->B\\n','sequence'),f('---\\ntitle: T\\n---\\nmindmap\\n  root\\n','timeline'),f('','flowchart')]));"
    )
    out = json.loads(subprocess.run(["node", "-e", run], capture_output=True, text=True, check=True).stdout)
    assert out == ["sequenceDiagram\n", "---\ntitle: T\n---\ntimeline\n", "flowchart TD\n"]


def test_a_block_can_be_boxed_from_its_menu_and_the_bar_says_box_them():
    assert "Box this block" in BUILDER and "diagramModel.outline.box(S, helpers, key)" in BUILDER
    assert "function box(S, h, key)" in (JS / "diagram-outline.js").read_text(encoding="utf-8")
    assert "ph:stack Box them" in (JS / "diagram-multi.js").read_text(encoding="utf-8")


def test_a_sequence_diagram_adds_parallel_critical_and_break_boxes():
    kinds = (JS / "diagram-kinds.js").read_text(encoding="utf-8")
    for tile in ('id: "par"', 'id: "critical"', 'id: "break"', '{ kw: "and", text: "Meanwhile" }'):
        assert tile in kinds, tile
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-kinds"))
    assert "parallel, critical and break (A, P, M, R, Y, X, T, L, G, O, U, C and B)" in body and "Sequence, Mind map and Timeline buttons" in body


def test_the_kind_switcher_hides_for_a_source_blocks_cannot_draw_and_never_calls_it_blank():
    # Reviewer: a Gantt showed Flowchart pressed, and Sequence wiped it with no Undo line (S.m is empty for it).
    assert ".dgm-plain .dgm-kinds" in CSS and "display: none" in CSS.split(".dgm-plain .dgm-kinds")[1][:40]
    assert "S.plain ? false" in KINDBAR


def test_the_kind_switcher_buttons_share_one_row_on_a_phone():
    assert ".dgm-kinds button" in CSS and "flex: 1 1 0" in CSS.split(".dgm-kinds button")[1][:120]


def test_the_dialogs_kind_bar_redraws_the_pane_when_the_kind_changes():
    # DD-1 (1107): the dialog's io.set stored history and the textarea but never called show(), so a press on Sequence
    # rewrote the source and left a flowchart pane with Flowchart pressed. The page's io.set re-shows through the document.
    embed = (JS / "diagram-embed.js").read_text(encoding="utf-8")
    start = embed.index("const io = {")
    body = embed[start : embed.index("undo:", start)]
    assert "if (diagramModel.builder.kindOf(next) !== kind) show();" in body


def test_a_drawing_error_keeps_the_last_good_picture_dimmed_and_says_the_line_once():
    # DD-4 (1107): `D[Oops --> A` replaced the picture with the sentence, left the "tall for this pane" offer beside it and
    # announced nothing. Now the image stays at 40% under the message, the offer hides, the message is an alert the first
    # time a given error shows (a status on a redraw of the same one) and names its line for a button that puts the caret there.
    start = BUILDER.index("function drawPicture")
    assert "diagramModel.picture.failure(S, result, source, smallButton)" in BUILDER[start : BUILDER.index("// --- the tree", start)]
    # Review 1107: the builder is at its size cap, so the failure view lives in diagram-picture.js; the assertions are unchanged.
    picture = (JS / "diagram-picture.js").read_text(encoding="utf-8")
    body = picture[picture.index("function failure(") :]
    assert 'S.fig.querySelector(":scope > .md-mermaid-img")' in body and "dgm-picture-stale" in body
    assert 'setAttribute("role", fresh ? "alert" : "status")' in body
    assert "S.sideways?.classList.add(\"hidden\")" in body
    assert "dataset.line" in body and "setSelectionRange" in body
    assert ".dgm-picture-stale > .md-mermaid-img" in CSS and "opacity: 0.4" in CSS.split(".dgm-picture-stale > .md-mermaid-img {", 1)[1].split("}", 1)[0]
