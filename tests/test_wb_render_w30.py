"""W30: a board render does not repeat reads whose answer cannot have changed."""

from pathlib import Path

WB = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


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
    assert "if (hasLinks && wbState.sketches?.length) wbIndexMapNodeElements();" in render
    #: Off a map the sizes were taken before the objects were repainted, so none outlives the pass.
    assert "if (!wbIsMap()) wbClearMapNodeSizeCache();" in render
    assert render.index("wbIndexMapNodeElements();") < render.index("sketchUpdate.each(") < render.index("wbClearMapNodeSizeCache();", render.index("sketchUpdate.each("))


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
    start = WB.index("function wbBuildExportSvg(")
    build = WB[start : WB.index("\nfunction ", start + 10)]
    #: One index per kind, built before the first item is drawn.
    for part in ('idIndex("#wb-html-layer .wb-object")', 'idIndex(".sketch-group")', 'idIndex(".node-card")'):
        assert part in build, part
    assert build.index("const objectEls") < build.index("drawFrame(e.item)")
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
