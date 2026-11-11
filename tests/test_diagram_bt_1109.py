"""Blind test of the diagram builder (dgbt-1109): one test per finding, each failing before its fix.

Pure model behaviour runs under node (as tests/test_diagram_outline_1679.py does); the rest reads the source, and the browser
numbers are in the CHANGELOG lines and docs/roadmap/agent-remaining/dgbt-1109.md.
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
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def _run(files: list[str], expr: str):
    script = (
        "const vm=require('vm');const ctx={diagramModel:{},structuredClone,console};vm.createContext(ctx);"
        f"for (const f of {json.dumps(files)}) vm.runInContext(require('fs').readFileSync({json.dumps(str(JS))}+'/'+f,'utf8'),ctx);"
        f"const ops=ctx.diagramModel.ops;const o=ctx.diagramModel.outline;"
        "const chain=(ids)=>({nodes: ids.map((id)=>({id,text:id})), subgraphs: [], kept: [], edges: ids.slice(1).map((to,i)=>({from: ids[i], to, label:'', style:'solid', arrow:true}))});"
        f"process.stdout.write(JSON.stringify({expr}));"
    )
    return json.loads(
        subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    )


FILES = ["diagram-ops.js", "diagram-outline.js"]
LISTED = "o.order(m, ops.layout(m)).map((i) => i.id).join('')"


@needs_node
def test_move_up_on_the_last_block_of_a_chain_swaps_it_with_the_one_above_by_rewiring_the_arrows():
    got = _run(
        FILES,
        f"(() => {{ const m = chain(['A','B','C','D','E']); const ok = o.swap(m, 'n:E', -1); return [ok, {LISTED}, m.edges.map((e) => e.from + e.to).join()]; }})()",
    )
    assert got == [True, "ABCED", "AB,BC,CE,ED"]


@needs_node
def test_move_down_swaps_with_the_one_below_and_a_branch_or_an_end_refuses():
    down = _run(
        FILES,
        f"(() => {{ const m = chain(['A','B','C','D']); const ok = o.swap(m, 'n:B', 1); return [ok, {LISTED}]; }})()",
    )
    assert down == [True, "ACBD"]
    # The first block has nothing above; a block that has two arrows out is a branch, and swapping it would say something else.
    ends = _run(
        FILES,
        "(() => { const m = chain(['A','B','C']); const b = chain(['A','B','C']); b.edges.push({from:'A',to:'C',label:'',style:'solid',arrow:true}); return [o.swap(m, 'n:A', -1), o.swap(m, 'n:C', 1), o.swap(b, 'n:B', -1)]; })()",
    )
    assert ends == [False, False, False]


@needs_node
def test_a_grip_dropped_before_or_after_its_chain_neighbour_swaps_the_two():
    got = _run(
        FILES,
        f"(() => {{ const m = chain(['A','B','C','D']); const a = o.drop(m, 'n:D', {{op: 'before', key: 'n:C'}}); const b = {LISTED}; "
        f"const far = o.drop(m, 'n:A', {{op: 'after', key: 'n:D'}}); return [a, b, far]; }})()",
    )
    assert got == [True, "ABDC", False]


def test_the_row_menu_and_the_drop_go_through_the_outline_so_the_list_really_changes():
    builder = _js("diagram-builder.js")
    assert "diagramModel.outline.move(S, helpers, key, dir)" in builder
    assert "diagramModel.outline.drop(m, g.key, target)" in _js("diagram-pointer.js")


@needs_node
def test_a_new_block_joins_the_picked_block_or_else_the_last_one():
    got = _run(
        FILES,
        "(() => { const m = chain(['A','B','C']); return [o.tail(m, 'n:B'), o.tail(m, null), o.tail(m, 'g:G'), o.tail({nodes: [], edges: []}, null)]; })()",
    )
    assert got == ["B", "C", None, None]


def test_add_block_connects_what_it_adds_unless_a_drop_a_group_or_a_caller_said_otherwise():
    builder = _js("diagram-builder.js")
    assert (
        "from = !group && !into && before === undefined ? diagramModel.outline.tail(m, sel) : null"
        in builder
    )
    # The default is "not said"; a caller that passes no `from` gets the join, one that passes null does not.
    assert "from = undefined" in builder.split("function addBlock(", 1)[1].split(") {", 1)[0]


def test_switching_kind_on_the_untouched_starter_does_not_ask():
    bar = _js("diagram-kindbar.js")
    assert (
        "const untouched = (S) =>" in bar
        and "diagramModel.starter" in bar.split("const untouched", 1)[1].split("\n", 1)[0]
    )
    # The confirm is only for content the person made; the starter is three boxes nobody wrote.
    assert "const blank = blankOf(S) || untouched(S);" in bar


def test_undo_and_redo_name_themselves_and_their_shortcut_on_every_kind():
    kinds = _js("diagram-kinds.js")
    # The flowchart's bar already read "Undo, Ctrl+Z"; the three other kinds' icons said only "Undo".
    assert (
        '["ph:arrow-counter-clockwise", "Undo", "Undo, Ctrl+Z",' in kinds
        and '["ph:arrow-clockwise", "Redo", "Redo, Ctrl+Y",' in kinds
    )
    assert "smallButton(name, tip, run)" in kinds
    assert '["ph:arrow-counter-clockwise", "Undo", "Undo, Ctrl+Z",' in _js("diagram-bar.js")


def test_a_document_that_embeds_a_diagram_previews_a_readable_label_not_the_embed_syntax():
    """Blind test: the Library read "!Diagram 2026-11-09 19:11" (the `!` of `![[...]]` left behind), and the Documents list the raw brackets."""
    from tessellate.api.routes_documents import _preview
    from tessellate.api.routes_library import _clip
    from tessellate.entry.manager_text import readable_embeds

    assert readable_embeds("a ![[Trip map]] b") == "a Diagram: Trip map b"
    # A title that already says Diagram is not said twice; an image embed and a plain link are left to their own readers.
    assert readable_embeds("![[Diagram 2026-11-09 19:11]]") == "Diagram 2026-11-09 19:11"
    assert readable_embeds("![[pic.png]] [[Trip map]]") == "![[pic.png]] [[Trip map]]"
    assert _clip("Intro line\n\n![[Trip map]]\n\nafter") == "Intro line · Diagram: Trip map · after"
    assert _clip("![[Diagram 2026-11-09 19:11]]") == "Diagram 2026-11-09 19:11"
    assert (
        _preview("Intro line\n\n![[Trip map]]\n\nafter") == "Intro line · Diagram: Trip map · after"
    )


def test_a_diagram_opened_from_a_document_offers_the_way_back_to_that_document():
    docs = (JS / "documents.js").read_text(encoding="utf-8")
    assert (
        "const from = openDocument.back && currentDoc && currentDoc.id !== id ?" in docs
        and "openDocument.back = false;" in docs
    )
    # The crumb names the parent, and a press goes there; every other open says Documents again.
    assert 'crumb.dataset.from = from ? from.id : "";' in docs
    assert "openDocument(Number(crumb.dataset.from))" in docs
    # The three ways an embedded diagram (or a link to a document) opens another document ask for it.
    assert (JS / "mermaid-draw.js").read_text(encoding="utf-8").count(
        "openDocument.back = true;"
    ) == 2
    assert "openDocument.back = true;\n      openDocument(target.doc.id);" in (
        JS / "documents-embeds.js"
    ).read_text(encoding="utf-8")
    assert ".doc-back-label {\n  max-width:" in (
        ROOT / "frontend" / "css" / "library-lazy.css"
    ).read_text(encoding="utf-8")


def test_every_kind_starts_with_the_same_word_the_toolbar_button_wears():
    kinds = _js("diagram-kinds.js")
    for kind in ("mindmap", "timeline", "sequence"):
        line = kinds.split(f"    {kind}: [", 1)[1].split("\n", 1)[0]
        assert '"Press Add, then ' in line, kind
    assert "Press Add above to start the diagram." in _js("diagram-builder.js")
    assert "Press a shape above" not in _js("diagram-builder.js")
    # The timeline names both first rows of its Add sheet (Section is the first row, Period the usual start).
    assert "Press Add, then Section or Period to begin" in kinds


def test_a_blank_mind_map_gets_its_central_idea_named_first_and_branch_twice_makes_sisters():
    kinds = _js("diagram-kinds.js")
    start = kinds.split("if (A.start && !m.root) {", 1)[1].split("\n    }\n", 1)[0]
    assert (
        'kit.commit(S, "Added the central idea. Name it, then add branches.");' in start
        and "return name(), S.sel;" in start
    )
    # Branch pressed again with the block it made still the pick lands beside it; a pick by hand, or a key on a block, nests.
    assert (
        "picked === S.fresh ? find(S, picked)?.parent : null" in kinds
        and "asked === undefined" in kinds
    )
    assert "S.fresh = tile.into && !spot ? S.sel : null;" in kinds
    assert "const pick = (S, key, focus) => ((S.fresh = null), kit.select(S, key, focus));" in kinds
    assert "S.fresh = null;" in _js("diagram-multi.js")
    # The line says where it landed, and the tile's own hint says what Branch does.
    assert '` ${tile.into ? "under" : "next to"} ${A.text(place.parent)}`' in kinds
    assert "or beside the last branch you added" in kinds


def test_a_shelf_tile_names_itself_in_its_tooltip_as_well_as_its_label():
    lib = _js("diagram-library.js")
    assert (
        "`${t.name}. ${t.hint} Press to add it, or drag it into the blocks or onto the picture.`"
        in lib
    )
    assert "`${t.name}. ${t.hint} Tap to add it.`" in lib


def test_a_flowchart_rows_name_wraps_to_two_lines_before_it_is_cut():
    block = CSS[CSS.index(".dgm-card:has(> .dgm-connect) > .dgm-label:not(.dgm-editing) {") :][:300]
    assert (
        "-webkit-line-clamp: 2;" in block
        and "white-space: normal;" in block
        and "overflow-wrap: anywhere;" in block
    )


def test_the_sideways_offer_is_a_row_under_the_picture_not_a_layer_over_it():
    block = CSS[CSS.index(".dgm-sideways {") :][:900].split("}", 1)[0]
    assert "position: absolute" not in block and "flex: none;" in block
    assert ".dgm-stage {\n  position: relative;\n  display: flex;\n  flex-direction: column;" in CSS


def test_the_phone_shelf_keeps_its_caret_on_screen_and_the_words_say_tap_not_click():
    # 390 px: fold, six tiles and the caret ran to 468; fold, three tiles and the caret end at 312.
    block = CSS[CSS.index(".dgm-shelf .dgm-tile:nth-child(n + 5) {") :][:120]
    assert "display: none;" in block
    steps = _js("diagram-steps.js")
    assert (
        'touch() ? "Double-tap the name to rename it."' in steps and '["Double-tap", ""]' in steps
    )
    assert (
        'titleField.placeholder = matchMedia("(max-width: 599.98px)").matches ? "Name it (optional)"'
        in _js("diagram-embed.js")
    )


def test_a_touch_screen_fits_the_drawing_short_of_the_edge_so_a_handle_does_not_lean_back_over_a_block():
    view = _js("diagram-view.js")
    assert 'const gap = matchMedia("(pointer: coarse)").matches ? 32 : 0;' in view
    assert "box.width - 2 * fig.clientLeft - gap, box.height - 2 * fig.clientTop - gap" in view
