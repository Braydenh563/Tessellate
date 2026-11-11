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
