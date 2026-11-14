"""W30: a board render does not repeat reads whose answer cannot have changed."""

from tests._app_js import frontend_text, script_file_text
import json
import shutil
import subprocess

import pytest

WB = frontend_text("whiteboard.js")


def test_the_board_colour_is_read_once_per_render_pass():
    helper = WB[WB.index("function wbBoardBg()") :].split("\n}\n", 1)[0]
    assert helper.split("\n", 2)[1].strip() == "if (wbBoardBgCache.pass) return wbBoardBgCache.out;"
    render = WB[WB.index("function renderWhiteboard()") :]
    ink = render[: render.index("const strokeInk")]
    #: A second render in one task must read afresh (a theme change between them).
    assert ink.rstrip().endswith("wbBoardBgCache.pass = false; // a second render in one task re-reads the colour")
    assert "queueMicrotask(() => { wbBoardBgCache.pass = false; });" in render


def test_connectors_read_their_ends_in_one_batch_and_a_board_keeps_none():
    render = WB[WB.index("function renderWhiteboard()") :]
    assert 'includes("link-")' in render
    #: Off a map the batch is only the objects a connector ends on (no walk of all 500; W30 left-line 3).
    assert "if (hasLinks && wbState.sketches?.length) wbIndexMapNodeElements(!wbIsMap());" in render
    #: Off a map the sizes were taken before the objects were repainted, so none outlives the pass.
    assert "if (!wbIsMap()) wbClearMapNodeSizeCache();" in render
    assert render.index("wbIndexMapNodeElements(!wbIsMap());") < render.index("sketchUpdate.each(") < render.index("wbClearMapNodeSizeCache();", render.index("sketchUpdate.each("))


def test_opening_a_board_drops_what_the_last_one_left_in_the_render_state():
    opener = WB[WB.index("async function openWhiteboardBoard(") :][:1900]
    for part in ("cancelAnimationFrame(wbRenderFrame)", "wbRenderQueued = false", "wbItemElCache.clear()", "wbClearMapNodeSizeCache()", "wbNavState.stale = true", "wbBoardBgCache"):
        assert part in opener, part


def test_shapes_and_connectors_repaint_only_when_their_look_can_have_changed():
    render = WB[WB.index("function renderWhiteboard()") :]
    key = render[render.index("const strokePaintKey = (d) =>") : render.index("sketchUpdate.each(function(d) {")]
    #: A shape keys on its data, its id (the rough seed), the ink and the board's rough default.
    assert "${d.data}|${d.id}|${strokeInk}|${wbBoardBackground().rough}" in key
    #: A connector keys on the ends it resolves to now, so a moved or resized end repaints it.
    assert "wbResolveLinkEndpoints(parsed)" in key and "JSON.stringify(ends)" in key
    #: Words with a placeholder (%date%, %page%, %length%), a map's cross-links and a raw path never skip.
    assert 'includes("%")' in key and "wbMapCrossLinkLook(parsed)" in key and 'startsWith("{")' in key
    #: The body reuses the ends the key resolved rather than resolving them twice.
    body = render[render.index("sketchUpdate.each(function(d) {") :][:9000]
    assert "linkEnds.has(d.id) ? linkEnds.get(d.id) : wbResolveLinkEndpoints(parsed)" in body
    assert "this._wbStrokeD = strokeKey ? pathData : null;" in body


def test_the_export_finds_each_items_element_in_one_walk_not_one_walk_per_item():
    #: L272: the indexes live in `wbExportLook`, built once before the builder draws an item.
    start = WB.index("function wbExportLook(")
    build = WB[start : WB.index("\nfunction ", start + 10)]
    builder = WB[WB.index("function wbBuildExportSvg(") :][:20000]
    assert builder.index("const look = wbExportLook()") < builder.index("drawFrame(e.item)")
    #: One index per kind, built before the first item is drawn.
    for part in ('idIndex("#wb-html-layer .wb-object")', 'idIndex(".sketch-group")', 'idIndex(".node-card")'):
        assert part in build, part
    assert "if (!found.has(el.dataset.id)) found.set(el.dataset.id, el)" in build
    #: No per-item page walk by id remains in the export.
    assert 'document.querySelector(`' not in build


def test_the_board_bounds_find_cards_and_sketches_in_one_walk_each():
    start = WB.index("function wbBoardBounds(")
    bounds = WB[start : WB.index("\n}\n", start)]
    assert 'idIndex(".node-card")' in bounds and 'idIndex(".sketch-group")' in bounds
    assert "document.querySelector(`" not in bounds


def test_a_sketch_class_is_written_only_when_it_changes():
    #: d3's `classed` re-sets the class attribute even when the token is right: 1,060 writes for 530 idle sketches.
    render = WB[WB.index("function renderWhiteboard()") :]
    helper = render[render.index("const classIfChanged =") :].split("\n  });\n", 1)[0]
    assert "if (this.classList.contains(name) !== on) this.classList.toggle(name, on);" in helper
    body = render[: render.index("sketchExit") if "sketchExit" in render else 60000]
    for name in ("wb-link-sketch", "wb-map-crosslink"):
        assert f'classIfChanged(sketchUpdate, "{name}"' in body, name
        assert f'sketchUpdate.classed("{name}"' not in body, name


def test_the_selection_highlight_walks_the_elements_it_marked_not_the_page():
    #: The class is written only here, so the set of marked elements is known without asking the page (W30: the scan was 1.2 ms a render).
    body = WB[WB.index("function wbApplySelectionHighlight()") :].split("\n}\n", 1)[0]
    assert 'querySelectorAll(".sketch-group.wb-selected' not in body
    assert "for (const el of marked)" in body and "marked.delete(el)" in body and "marked.add(el)" in body
    assert "const marked = (wbApplySelectionHighlight.marked ??= new Set());" in body


def test_one_stack_order_serves_the_bands_the_cards_and_the_objects():
    render = WB[WB.index("function renderWhiteboard()") :].split("\n}\n", 1)[0]
    assert render.count("wbStackOrder()") == 1 and render.count("wbStackRanks()") == 0
    assert "wbPlaceSketchBands(sketchGroups, stackOrder)" in render and "renderWbObjects(canvas, stackRank)" in render
    assert "function renderWbObjects(canvas, stackRank = wbStackRanks())" in WB


def test_a_jumping_connector_keeps_its_drawn_path_so_the_paint_skip_holds():
    pass_ = WB[WB.index("function wbApplyLineJumps(") :].split("\n}\n", 1)[0]
    #: The skip compares the drawn `d` with `_wbStrokeD`, so the jump pass records what it drew.
    assert "settle(el, path," in pass_ and "el._wbPlainD" in pass_
    assert "if (el._wbStrokeD != null) el._wbStrokeD = d;" in pass_
    assert "this._wbPlainD = strokeKey ? pathData : null;" in WB[WB.index("this._wbStrokeKey = strokeKey;") :][:400]


def _grab(src: str, name: str) -> str:
    start = src.index(f"function {name}(")
    depth, i = 0, src.index(") {", start) + 2
    while True:
        depth += src[i] == "{"
        depth -= src[i] == "}"
        i += 1
        if depth == 0:
            return src[start:i]


JUMP_HARNESS = r"""
const writes = [];
const mk = (id, data, plain) => {
  const attrs = { "sketch-hitbox": plain, "sketch-path": plain };
  const part = (cls) => ({
    getAttribute: (n) => (n === "d" ? attrs[cls] : null),
    setAttribute: (n, v) => { attrs[cls] = v; writes.push(`${id}:${cls}:${n}`); },
  });
  const parts = { ".sketch-hitbox": part("sketch-hitbox"), ".sketch-path": part("sketch-path") };
  return { __data__: { id, data: JSON.stringify(data) }, querySelector: (s) => parts[s], _wbPlainD: plain, _wbStrokeD: plain, attrs };
};
const a = mk(1, { type: "link-straight", jumps: "arc" }, "M0 50L100 50");
const b = mk(2, { type: "link-straight", jumps: "arc" }, "M50 0L50 100");
"""


def test_the_jump_pass_writes_nothing_on_an_unchanged_render_and_records_what_it_drew():
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = "\n".join([_grab(WB, name) for name in ("wbJumpSize", "wbCubicAt", "wbSegmentCross", "wbShaftPoints", "wbLineJumpsD", "wbApplyLineJumps")] + [
        "const wbMapCrossLinkLook = () => null;", JUMP_HARNESS,
        """
wbApplyLineJumps([a, b]);
const first = writes.splice(0).length;
const jumped = b.attrs["sketch-path"];
wbApplyLineJumps([a, b]);
const second = writes.splice(0).length;
const recorded = b._wbStrokeD === jumped;
wbApplyLineJumps([a, b]);
//: The line under it goes: the one that hopped has nothing to hop and returns to its plain path.
wbApplyLineJumps([b]);
console.log(JSON.stringify({ first, second, jumpedDiffers: jumped !== "M50 0L50 100", recorded, back: b.attrs["sketch-path"], backRecorded: b._wbStrokeD, third: writes.length }));
""",
    ])
    proc = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr[-800:]
    out = json.loads(proc.stdout)
    assert out["first"] == 1 and out["jumpedDiffers"] and out["recorded"]
    assert out["second"] == 0
    assert out["back"] == "M50 0L50 100" and out["backRecorded"] == "M50 0L50 100"


def test_a_boards_connector_batch_measures_only_the_objects_its_ends_are_on():
    index = frontend_text("whiteboard-map.js")
    body = index[index.index("function wbIndexMapNodeElements(linkEndsOnly = false)") :].split("\n}\n", 1)[0]
    head = body[: body.index("for (const el of document.querySelectorAll")]
    assert 'wbItemElement("object", id)' in head and "if (linkEndsOnly) {" in head
    assert 'parsed.sourceKind === "object"' in body and 'parsed.targetKind === "object"' in body


def test_an_objects_z_index_is_kept_on_its_element_not_read_back_from_style():
    body = script_file_text("whiteboard.js")[script_file_text("whiteboard.js").index("function renderWbObjects(") :]
    assert "if (this._wbRank !== rank) {" in body and "this.style.zIndex = String(rank);" in body
    #: The only writers of an object's z-index are the enter and this pass; a new one must go through the cache.
    assert body.count(".style.zIndex") == 1
