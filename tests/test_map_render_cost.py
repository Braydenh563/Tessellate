"""A map render repaints what changed (MINDMAP_PLAN 13a, the render pass).

`scratchpad/ui-sweeps/mapperf.js` is the real gate: it opens a 500-topic map
in a real Chromium and reports what a render costs after one topic has moved,
after every topic has moved, and when nothing has. This file cannot do that,
and nothing in it should be mistaken for the measurement. What it holds is the
*shape* those numbers came from, because each of these costs reads as ordinary
code and only shows up under a profiler:

    mapperf.js, 1440x900 light       50        200        500
    one topic moved, before       22.6ms    122.6ms    534.7ms
    one topic moved, after         7.9ms     19.8ms     47.8ms
    every topic changed, after    16.6ms     53.5ms    149.1ms
    open to painted, before      314.0ms    757.0ms   2022.3ms
    open to painted, after       393.1ms    537.2ms    965.6ms

Each rule here is one of those costs. They are written against the source
because the suite cannot open a board; if one fails, the question to ask is
"what does this do per render now", not "how do I word the rule differently".
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
#: whiteboard.js and whiteboard-map.js joined: the mind map layer moved into
#: whiteboard-map.js verbatim on 2026-09-24, and the renderer and the
#: gestures that call into it stayed in whiteboard.js.
WB = "\n".join(
    (ROOT / "frontend" / "js" / n).read_text(encoding="utf-8") for n in ("whiteboard.js", "whiteboard-map.js")
)


def _body(name: str) -> str:
    """One top-level function's text, from its `function` line to the next."""
    match = re.search(rf"^function {re.escape(name)}\(", WB, re.MULTILINE)
    assert match, f"{name} is gone; this lint is about its body"
    rest = WB[match.end() :]
    end = re.search(r"^function \w+\(", rest, re.MULTILINE)
    return rest[: end.start()] if end else rest


def _code(name: str) -> str:
    """The same, with the comment lines taken out.

    The comments beside these rules quote the very shapes the rules forbid, in
    order to say why they were forbidden, and a rule that read those would fail
    on its own explanation.
    """
    return "\n".join(
        line for line in _body(name).splitlines() if not line.lstrip().startswith("//")
    )


def test_an_object_that_has_not_changed_is_not_repainted() -> None:
    """The paint key is compared before anything is written, and the write
    path stores it: an object drawing what it already draws costs a string
    compare. Checked in order, because a key stored but never consulted, or
    consulted after the writes, is the cost this rule exists to stop."""
    body = _code("renderWbObjects")
    compare = body.index("this._wbPaintKey === key")
    store = body.index("this._wbPaintKey = key")
    #: The unchanged branch may still move the object (a drag changes its
    #: place, not its paint), so the full write is the first one after the
    #: key is stored.
    write = body.index("this.style.transform", store)
    assert compare < store < write


def test_the_paint_key_holds_what_a_topic_draws_from_off_its_own_row() -> None:
    """A map node's colour comes from its branch, its chevron from its
    children, its badge from the subtree folded under it, its spine from the
    parent's side and everything the strip sets from the map's theme merged
    under its data. All five change while the object's own row does not, so
    all five are inputs, and a key that misses one is a node that stops
    following a change."""
    body = _code("wbObjectPaintKey")
    for reads in ("ctx.colors", "childrenOf", "wbMapSubtree", "ctx.theme", "wbMapLabel"):
        assert reads in body, f"{reads} is an input to the paint and not in the key"
    # And the one input that is deliberately left out, with the measure pass
    # below as the reason: a map node's height is its text's.
    assert "d.data?.sized ? d.height" in body


def test_every_topic_is_measured_after_the_writes_never_between_them() -> None:
    """A style write invalidates layout for the whole document, so a read
    interleaved with the writes flushes a fresh layout of the entire board:
    500 nodes cost 500 full layouts, which is where this render's
    superlinearity lived. The reads happen once, after the last write."""
    body = _code("renderWbObjects")
    last_write = body.rindex("wbPaintMapNode(")
    exits = body.index("objectSelection.exit()")
    measure = body.index("this.offsetHeight")
    assert last_write < exits < measure
    # And the same reads fill the size cache, because `wbRenderMapEdges` runs
    # next and asks for both ends of every edge.
    assert "wbMapNodeSizeCache.set(d.id" in body


def test_a_topic_the_pass_did_not_repaint_keeps_its_own_measured_height() -> None:
    """OPEN.md's "94px" row, reproduced: a state fetched from the server hands
    every topic the server's placeholder height (120) while the element is what
    its text needs (44), and a topic this pass did not repaint took the 120
    into the size cache, so `wbMapNodeSize` was 38px out at 1440 and 12px at
    390 (`mapstrip.js`'s "first pan lands within 4px", 0 now). The element keeps
    the height it was last measured at and the cache takes that, not the
    stored one."""
    body = _code("renderWbObjects")
    assert "this._wbMeasuredH = h;" in body, "the live read must record what it measured"
    skip = body[body.index("const known = this._wbMeasuredH;") :][:500]
    assert "h: known || d.height" in skip, "the cache takes the measured height before the stored one"


def test_a_line_is_keyed_by_its_two_ends_and_updated_in_place() -> None:
    """Rebuilding the group made four SVG elements per edge and threw the
    previous four away: 499 edges is two thousand elements created and wired
    because one of them moved."""
    body = _code("wbRenderMapEdges")
    assert "replaceChildren" not in body, "the group is updated, not rebuilt"
    assert "cache.get(key)" in body
    assert "wbMapEdgeApply(" in body
    # The two things a keyed update has to do that a rebuild got for free: the
    # lines whose ends are no longer joined go, and the order stays the
    # tree's (SVG paints in document order, and mapstrip.js pairs the first
    # line with the first mid-line plus).
    assert "held.wrap.remove();" in body
    assert "group.insertBefore(wrap" in body


def test_an_edge_compares_before_it_writes() -> None:
    """The same rule as an object's paint key, for the same reason: the
    comparison is a string, the write is four attributes and a path."""
    body = _code("wbRenderMapEdges")
    assert "held.paint !== geom.paint" in body
    assert "paint:" in _code("wbMapEdgeGeometry")


def test_the_link_sketches_are_parsed_once_per_capture() -> None:
    """`wbCaptureBulkMoveOrigin` is handed every topic under the one grabbed,
    and each member used to ask `wbLinkedSketchesFor` for its own lines, which
    walked and JSON.parsed every sketch on the board: members x sketches with
    a parse in the middle, before the pointer had moved."""
    body = _code("wbCaptureBulkMoveOrigin")
    assert "wbLinkSketchIndex()" in body
    assert "wbLinkedSketchesFor(id, kind, linkIndex)" in body
    # One parse per sketch in the index, and the lookup is a lookup.
    # (audit 1028 B17: through `wbParsedLink`, which holds the one parse and
    # remembers it per version of the sketch's data.)
    assert "wbParsedLink(sketch)" in _code("wbLinkSketchIndex")
    assert _code("wbParsedLink").count("JSON.parse") == 1
    assert "if (index) return index.get(" in _code("wbLinkedSketchesFor")


def test_a_link_end_is_found_by_id_not_by_scanning_the_board() -> None:
    """`wbUpdateLinkedSketches` resolves both ends of every link touching a
    moved item on every frame of the gesture, and `wbLinkItem` was a `.find`
    over the whole list: measured on mapperf.js's link fixture at 500 topics,
    a branch drag over 300 link sketches had a 183.3ms worst frame with the
    list scanned and 33.3ms with it indexed."""
    body = _code("wbLinkItem")
    assert ".find(" not in body
    assert "wbLinkItemIndex.get(list)" in body
    # Keyed on the array, so a list replaced by a filter is a fresh index, and
    # the length guard covers a push. The one case neither covers drops the
    # entry by hand.
    assert "held.size !== list.length" in body
    assert "wbForgetLinkItems(wbState.nodes);" in WB


def test_a_link_finds_its_two_paths_once_per_gesture() -> None:
    """Three document-wide queries per link per frame is thousands of walks of
    the document a second, for elements a keyed render does not replace."""
    body = _code("wbUpdateLinkedSketches")
    assert "entry.el.isConnected" in body
    assert body.count("document.querySelector") == 1


def test_a_synchronous_render_calls_off_the_queued_one() -> None:
    """Opening a board queues a render, renders synchronously to measure the
    nodes for the fit, and used to pay for the whole board a second time one
    frame later: lowering the flag the callback checks does not stop the
    callback."""
    assert "cancelAnimationFrame(wbRenderFrame);" in _code("renderWhiteboardNow")
    assert "wbRenderFrame = requestAnimationFrame(" in _code("wbScheduleRender")
    # The one thing that frame did which the synchronous path does not.
    assert "if (cancelled) wbUpdateSelectionBar();" in _code("renderWhiteboardNow")


def test_the_fit_reads_the_boxes_the_render_just_measured() -> None:
    """`wbContentBounds` asks `wbItemBBox` about every item on the board, so
    the fit that runs on open was 500 document walks and 500 layout reads for
    boxes the render had measured in one pass moments earlier."""
    body = _code("wbItemBBox")
    cache_at = body.index("wbMapNodeSizeCache")
    query_at = body.index('wbItemElement("object"')
    assert cache_at < query_at, "the cache has to be consulted before the DOM"
