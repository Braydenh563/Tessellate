"""The diagram block pane (1546 P2; DOCUMENTS_PLAN "1546 design" D5 to D10).

`DIAGRAM-OPS-BEGIN` to `-END` in diagram-ops.js (it was in diagram-builder.js until 1594) is the pure half: the model
changes a gesture makes (place, move, nest, join, relabel, delete), run here in
node beside the model's own region (documents-mermaid.js). The invariants are
D2's: every change prints to a source that parses back to the same blocks, and a
line the reader keeps stays where it stood. The rest of the file (the DOM, the
pointer mode, the keys) is read for what it must and must not contain; the
browser run is scratchpad numbers in the commit, not a test.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from tests import _js_scope

from tests._app_js import lazy_modules_source, documents_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
BUILDER = JS / "diagram-builder.js"
OPS = JS / "diagram-ops.js"
MERMAID = JS / "documents-mermaid.js"


def _region(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    return text[text.index(f"// {name}-BEGIN") : text.index(f"// {name}-END")]


def _run(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    ops = _region(OPS, "DIAGRAM-OPS")
    assert "document." not in ops and "window." not in ops, "the pure region reached for the DOM"
    code = _region(MERMAID, "DIAGRAM-MODEL") + "\n" + ops + "\n" + body
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(code)
    try:
        out = subprocess.run([node, handle.name], capture_output=True, text=True, timeout=60, check=True)
    finally:
        Path(handle.name).unlink(missing_ok=True)
    return json.loads(out.stdout)


def _script(source: str, steps: str):
    """Parse `source`, run `steps` (JS using `m` and `o`), answer what it returns plus the printed source."""
    return _run(
        f"const m = diagramModel.parse({json.dumps(source)}); const o = diagramOps;\n"
        f"const result = (() => {{ {steps} }})();\n"
        "console.log(JSON.stringify({ result, src: diagramModel.print(m), again: diagramModel.print(diagramModel.parse(diagramModel.print(m))) }));"
    )


NESTED = """flowchart TD
  subgraph S1 ["Build"]
    B["Compile"]
    subgraph S2 ["Ship"]
      D["Deploy"]
    end
    C["Test"]
  end
  A["Start"]
  E["Lone"]
  A --> B
  B --> C
  C --> D
"""


def test_ids_run_a_to_z_then_n27_and_groups_are_g():
    got = _script("flowchart TD\n", "const ids = []; for (let i = 0; i < 28; i++) ids.push(o.addNode(m)); const g = o.addGroup(m); return [ids.slice(0, 3), ids.slice(25), g];")
    assert got["result"][0] == ["A", "B", "C"]
    assert got["result"][1] == ["Z", "N27", "N28"] and got["result"][2] == "G1"
    assert got["src"] == got["again"]


def test_a_diagram_holds_at_most_120_blocks():
    got = _script("flowchart TD\n", "let n = 0; while (o.addNode(m)) n++; return [n, o.addNode(m)];")
    assert got["result"] == [120, None]


def test_reorder_steps_over_its_own_kind_only():
    got = _script(NESTED, "const out = []; out.push(o.step(m, 'n:A', 1)); out.push(o.step(m, 'n:A', 1)); out.push(o.step(m, 'n:A', -1)); return [out, o.sisters(m, 'n:A').keys];")
    assert got["result"][0] == [True, False, True]
    # A went below E, could go no further, then came back up: the top level reads S1, A, E.
    assert got["result"][1] == ["g:S1", "n:A", "n:E"]
    assert got["src"] == got["again"]


def test_a_node_dropped_before_a_group_goes_first_among_the_nodes_and_a_group_before_a_node_goes_last():
    got = _script(NESTED, "o.move(m, 'n:A', null, 'g:S1'); o.move(m, 'g:S2', null, 'n:E'); return [o.sisters(m, 'n:A').keys, o.parentOf(m, 'g:S2')];")
    assert got["result"][0] == ["g:S1", "g:S2", "n:A", "n:E"]
    assert got["result"][1] is None
    assert got["src"] == got["again"]


def test_nest_goes_into_the_nearest_group_above_and_lift_comes_out_after_it():
    got = _script(NESTED, "const a = o.nest(m, 'n:E'); const p = o.parentOf(m, 'n:E'); const b = o.lift(m, 'n:E'); return [a, p, b, o.parentOf(m, 'n:E'), o.lift(m, 'n:E')];")
    assert got["result"] == [True, "S1", True, None, False]
    assert got["src"] == got["again"]


def test_a_group_cannot_go_inside_itself_or_what_it_holds():
    got = _script(NESTED, "return [o.move(m, 'g:S1', 'S1'), o.move(m, 'g:S1', 'S2'), o.move(m, 'g:S2', 'S2'), o.move(m, 'g:S2', 'S1')];")
    assert got["result"] == [False, False, False, True]


def test_a_join_needs_two_blocks_and_is_never_made_twice():
    got = _script(NESTED, "return [!!o.join(m, 'A', 'E'), !!o.join(m, 'A', 'E'), !!o.join(m, 'A', 'nope'), !!o.join(m, 'A', 'S2'), !!o.join(m, 'A', 'E', { label: 'yes' })];")
    assert got["result"] == [True, False, False, True, True]
    assert "A --> E" in got["src"] and "A --> S2" in got["src"] and '|"yes"|' in got["src"]
    assert got["src"] == got["again"]


def test_deleting_a_node_takes_its_joins_and_deleting_a_group_lifts_its_blocks():
    got = _script(NESTED, "const a = o.remove(m, 'n:B'); const b = o.remove(m, 'g:S1'); return [a, b, m.nodes.map((n) => [n.id, n.group]), m.subgraphs.map((g) => [g.id, g.parent]), m.edges.length];")
    assert got["result"][0] == {"joins": 2, "lifted": 0}
    assert got["result"][1] == {"joins": 0, "lifted": 2}
    assert sorted(got["result"][2]) == sorted([["C", None], ["D", "S2"], ["A", None], ["E", None]])
    assert got["result"][3] == [["S2", None]] and got["result"][4] == 1
    assert got["src"] == got["again"]


def test_a_label_is_set_in_place_and_an_empty_one_is_refused():
    got = _script(NESTED, "return [o.relabel(m, 'n:A', '  Say \"hi\" | #1  '), o.relabel(m, 'n:A', '   '), o.relabel(m, 'g:S1', 'Phase one'), o.relabel(m, 'n:zz', 'x')];")
    assert got["result"] == [True, False, True, False]
    assert got["src"] == got["again"]
    assert 'Phase one' in got["src"] and "#quot;hi#quot;" in got["src"]


KEPT = """flowchart TD
  subgraph S ["Box"]
    direction LR
    A --> B
  end
  style A fill:#f9f
  C --> A
"""


def test_a_kept_line_stays_in_its_group_when_blocks_are_added_above_it():
    got = _script(KEPT, "o.addGroup(m, { before: 'g:S' }); o.addNode(m, { group: null }); o.move(m, 'n:C', null, null); return m.kept.map((k) => [k.at, k.line]);")
    inside = got["src"].split("subgraph S")[1].split("end")[0]
    assert "direction LR" in inside, got["src"]
    assert "style A fill:#f9f" in got["src"]
    assert got["src"] == got["again"]


def test_the_layout_places_each_kept_line_where_it_stood():
    """Since L-documents-60 a group's `direction` is the group's own `dir`, read
    and printed inside it (not a kept line); the lines still kept stay put."""
    got = _script(KEPT, "return JSON.stringify([o.layout(m), m.subgraphs[0].dir]);")
    layout, way = json.loads(got["result"])
    kids = layout[0]["kids"]
    assert [k["type"] for k in kids] == ["n", "n"] and way == "LR"
    assert any(x["type"] == "k" and x["line"].startswith("style A") for x in layout)


def test_a_long_run_of_gestures_always_prints_a_source_that_parses_back_the_same():
    body = """
let seed = 7;
const rnd = (n) => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed % n; };
const m = diagramModel.parse(CORPUS);
const o = diagramOps;
const all = () => [...m.nodes.map((n) => 'n:' + n.id), ...m.subgraphs.map((g) => 'g:' + g.id)];
const bad = [];
for (let i = 0; i < 400; i++) {
  const keys = all();
  const k = keys[rnd(keys.length)];
  const t = keys[rnd(keys.length)];
  const op = rnd(9);
  if (op === 0) o.addNode(m, { shape: o.SHAPES[rnd(6)], group: m.subgraphs.length && rnd(2) ? m.subgraphs[rnd(m.subgraphs.length)].id : null });
  else if (op === 1) o.addGroup(m, { parent: m.subgraphs.length && rnd(2) ? m.subgraphs[rnd(m.subgraphs.length)].id : null });
  else if (op === 2) o.step(m, k, rnd(2) ? 1 : -1);
  else if (op === 3) o.nest(m, k);
  else if (op === 4) o.lift(m, k);
  else if (op === 5) o.move(m, k, t[0] === 'g' ? t.slice(2) : null, rnd(2) ? t : null);
  else if (op === 6) o.join(m, k.slice(2), t.slice(2), rnd(2) ? { label: 'l' + i } : {});
  else if (op === 7 && keys.length > 4) o.remove(m, k);
  else o.relabel(m, k, 'L' + i + ' "q" <b>');
  const once = diagramModel.print(m);
  const back = diagramModel.parse(once);
  if (!back || diagramModel.print(back) !== once) bad.push([i, op, once]);
  const ids = new Set(); for (const n of m.nodes) ids.add(n.id);
  if (ids.size !== m.nodes.length) bad.push([i, 'dup ids']);
  for (const g of m.subgraphs) if (o.inside(m, g.parent, g.id) && g.parent) bad.push([i, 'cycle']);
}
console.log(JSON.stringify({ bad: bad.slice(0, 2), nodes: m.nodes.length, groups: m.subgraphs.length }));
"""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    for seed_source in (NESTED, KEPT):
        code = (
            _region(MERMAID, "DIAGRAM-MODEL") + "\n" + _region(OPS, "DIAGRAM-OPS") + f"\nconst CORPUS = {json.dumps(seed_source)};\n" + body
        )
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
            handle.write(code)
        try:
            out = subprocess.run([node, handle.name], capture_output=True, text=True, timeout=60, check=True)
        finally:
            Path(handle.name).unlink(missing_ok=True)
        got = json.loads(out.stdout)
        assert got["bad"] == [], got


# --- what the DOM half must and must not hold ----------------------------------------------------


def test_the_builder_builds_its_dom_without_markup_strings_and_exports_one_name():
    code = BUILDER.read_text(encoding="utf-8")
    body = re.sub(r"//.*", "", code)
    for banned in ("innerHTML", "insertAdjacentHTML", "outerHTML", "document.write", "DOMParser", ".setAttribute(\"style\"", "onclick"):
        assert banned not in body, banned
    assert body.count("diagramModel.builder =") == 1
    assert re.findall(r"^(?:async\s+)?function\s", body, re.M) == [], "a top-level name joins the shared scope"
    assert re.findall(r"^(?:const|let|var)\s", body, re.M) == []
    assert body.count('role", "tree"') == 1, "one tree"


def test_the_pane_is_one_tree_of_cards_with_the_dock_recipe_and_kebab_menus():
    code = BUILDER.read_text(encoding="utf-8")
    #: The dock is built by diagram-bar.js since 1661 D2; the recipe (the dock class and name) is unchanged.
    bar = (BUILDER.parent / "diagram-bar.js").read_text(encoding="utf-8")
    assert 'dataset.dockName = "diagram"' in bar and 'el("div", "dock dgm-dock")' in bar
    assert "lazyKebab(() => blockItems(S, key)" in code and "openMenuAtPoint" in code and "wireLongPress(S.tree" in code
    # Relabel in place is the board's pattern: plaintext-only, Enter commits, Escape reverts.
    assert '"contenteditable", "plaintext-only"' in code and 'event.key !== "Enter" && event.key !== "Escape"' in code
    # The keys of the plan's keyboard row.
    for key in ('ArrowDown: () => go', "Enter: () => relabel", "Insert:", "Delete:", "ContextMenu:", "Alt", "j: ()"):
        assert key in code or key.lower() in code.lower(), key
    # One polite live region, and a text-only DOM for every label.
    assert 'aria-live", "polite"' in code and code.count("aria-live") == 1
    assert "textContent" in code


def test_the_pointer_mode_is_ahead_of_carry_and_the_drag_asks_it_first():
    #: obj-drag.js is one closure now (ranked row 37a); these tests slice or run its private functions, so they read it as it was before it was wrapped (`_js_scope.unwrapped`): same code, same assertions.
    drag = _js_scope.unwrapped((JS / "obj-drag.js").read_text(encoding="utf-8"))
    seed = drag[drag.index("function objDragSeed(event) {") :]
    seed = seed[: seed.index("\n}\n")]
    # A mode with its own cards answers before the generic grab, which carry (taking every card) would win.
    assert seed.index("OBJ_MODES[name].seed?.(event)") < seed.index("OBJ_MODES[name].grab?.(hit)")
    carry = (JS / "obj-carry.js").read_text(encoding="utf-8")
    assert "grab: () => ({})" in carry and "OBJ_MODES.carry" in carry
    #: The mode is made by diagram-pointer.js (1594) and set where the builder shows.
    code = BUILDER.read_text(encoding="utf-8")
    pointer = (JS / "diagram-pointer.js").read_text(encoding="utf-8")
    assert "OBJ_MODES.diagram = diagramModel.pointer.make(helpers)" in code and "seed: seedBlock" in pointer
    assert 'block: "ph-squares-four"' in drag


def test_the_bundle_is_named_where_the_library_is_and_never_at_boot():
    rows = lazy_modules_source()
    assert 'diagramBuilder: ["/css/diagram-lazy.css", "/js/diagram-builder.js"]' in rows
    for boot in ("app.js", "lazy-entries.js"):
        assert "diagramBuilder" not in (JS / boot).read_text(encoding="utf-8"), boot
    assert 'src="/js/diagram-builder.js' not in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert (ROOT / "frontend" / "css" / "diagram-lazy.css").is_file()


def test_the_document_shows_blocks_for_a_diagram_and_hands_its_edits_to_the_history():
    docs = documents_text()
    state = docs[docs.index("const docViewState = {") :]
    state = state[: state.index("\n};")]
    assert '["split", "rendered", "canvas", "blocks"].includes(mode)' in state
    preview = docs[docs.index("function renderDocPreview() {") :]
    preview = preview[: preview.index("\n}\n")]
    pane = preview[preview.index('docFileType().ext === "mmd"') :]
    pane = pane[: pane.index("return;")]
    # One history step per gesture, undo and redo through the editor's own.
    assert "docUndoBreak()" in pane and "docSurface().text = next" in pane and "docUndo()" in pane and "docRedo()" in pane
    assert 'ensureModule("diagramBuilder")' in pane and "diagramModel.builder.show(preview, io, text)" in pane
    # Before the preview is emptied: the pane keeps its own DOM between changes.
    assert preview.index('docFileType().ext === "mmd"') < preview.index("preview.replaceChildren()")
    assert "function docDiagramPane" not in docs, "a named function is a new global name"


def test_a_diagram_over_the_block_limit_stays_in_source_with_one_line_saying_so():
    # P1 left this to the pane (D3 and the 120-node cap): the picture is drawn, the blocks are not.
    code = BUILDER.read_text(encoding="utf-8")
    sync = code[code.index("function sync(host, text") :]
    sync = sync[: sync.index("\n  }\n")]
    assert "read.nodes.length > diagramOps.MAX" in sync and "more than ${diagramOps.MAX} blocks" in sync
    assert 'classList.toggle("dgm-plain", !parsed)' in sync
    # And the picture is still drawn for it: only a source with no block and nothing but its header is "empty" (1596 b:
    # a kept line the blocks could not place is drawn, so the picture says why it cannot be).
    assert "S.plain = !parsed" in sync
    draw = code[code.index("function drawPicture(S)") :]
    draw = draw[: draw.index("\n  }\n")]
    assert "S.m && !S.m.nodes.length" in draw and "!S.plain && blank && bare" in draw



# --- INBOX 1613 / DOCUMENTS_PLAN 22.4 R1: the shape menu and the row's swatch ---------------------

SHAPE_BRACKETS = [("rect", "[", "]"), ("round", "(", ")"), ("stadium", "([", "])"), ("circle", "((", "))"), ("diamond", "{", "}"), ("hexagon", "{{", "}}"), ("cylinder", "[(", ")]"), ("parallelogram", "[/", "/]")]


@pytest.mark.parametrize(("shape", "open_", "close"), SHAPE_BRACKETS)
def test_each_shape_prints_its_mermaid_brackets_and_has_a_glyph_in_the_swatch_and_the_menu_row(shape, open_, close):
    got = _script("flowchart TD\n  A[\"Step\"]\n", f"o.node(m, 'A').shape = {json.dumps(shape)};")
    assert f'A{open_}"Step"{close}' in got["src"], got["src"]
    assert got["again"] == got["src"]
    code = BUILDER.read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
    # The glyph is drawn from data-shape; the swatch and the menu row both come from shapeGlyph.
    assert shape == "rect" or f'.dgm-shape[data-shape="{shape}"]' in css
    # The label table moved to diagram-ops.js (DGB_LABEL) to keep the builder under its size cap; the pane copies it on open.
    assert shape in re.search(r"DGB_LABEL = \{([^}]*)\}", OPS.read_text(encoding="utf-8")).group(1)
    assert code.count("shapeGlyph(") >= 3, "the definition, the swatch button and the menu row each use it"


def test_the_row_swatch_is_a_named_button_and_the_shape_menu_rows_draw_their_shape_and_a_check():
    code = BUILDER.read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
    assert "`Shape: ${SHAPE_LABEL[shape]}`" in code and '"aria-haspopup", "menu"' in code
    # A real button, and the row click leaves it alone (it opens the menu, it does not select).
    assert 'el("button", "dgm-swatch")' in code and ".dgm-swatch" in code.split("S.tree.addEventListener(\"click\"")[1][:300]
    # The menu rows are made here because setLabel takes only ph: icons.
    assert "shapeRow(" in code and "ph-check" in code and "ph:square" not in code
    assert ".dgm-swatch" in css and "min-inline-size: 1.5rem" in css and ".dgm-swatch:focus-visible" in css

