"""Picking a map topic up costs its branch, not the board (MINDMAP_PLAN 13a).

`scratchpad/ui-sweeps/mapperf.js` is the real gate here: it drives a pointer
across a 500-topic map in a real Chromium and reports the worst frame of the
gesture. This file cannot do that, and nothing in it should be mistaken for
the measurement. What it can do is hold the *shape* the measurement came from,
because every one of the costs below reads as ordinary code and only shows up
as a number under a profiler:

    worst drag frame, mapperf.js        50        200        500
    before                           83.3ms    416.6ms   1650.0ms
    after                            16.8ms     33.3ms     66.7ms

Each rule here is one of those costs. They are written against the source
because the suite cannot open a board; if one fails, the question to ask is
"what does this do per frame now", not "how do I word the rule differently".
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
    """One top-level function's text, from its `function` line to the next one.

    Crude on purpose: every function this file asks about is declared at the
    left margin, and the next left-margin `function` is where it ends.
    """
    match = re.search(rf"^function {re.escape(name)}\(", WB, re.MULTILINE)
    assert match, f"{name} is gone; this lint is about its body"
    rest = WB[match.end() :]
    end = re.search(r"^function \w+\(", rest, re.MULTILINE)
    return rest[: end.start()] if end else rest


def _code(name: str) -> str:
    """The same, with the comment lines taken out.

    This file's rules are about what runs. The comments beside them quote the
    very shapes the rules forbid, in order to say why they were forbidden, and
    a rule that read those would fail on its own explanation.
    """
    return "\n".join(
        line for line in _body(name).splitlines() if not line.lstrip().startswith("//")
    )


def test_a_topic_is_measured_from_a_cache_before_the_dom() -> None:
    """`wbMapNodeSize` is asked for both ends of every edge, and a branch drag
    redraws every edge it carries on every frame. The DOM query and the layout
    read underneath it were the largest self-time entries in a CPU profile of
    one 500-topic drag, ahead of all of the edge maths that calls them."""
    body = _body("wbMapNodeSize")
    cache_at = body.index("wbMapNodeSizeCache")
    query_at = body.index("document.querySelector")
    assert cache_at < query_at, "the cache has to be consulted before the DOM"


def test_the_measurements_are_dropped_when_they_could_go_stale() -> None:
    """Three moments, and only three, can change a topic's drawn box: a render
    (which replaces the element), the size grip (which changes one box while
    it drags), and the end of any gesture. Miss one and the edges follow a box
    the topic no longer has."""
    assert "wbClearMapNodeSizeCache();" in _body("renderWhiteboard")
    assert 'window.addEventListener("pointerup", wbClearMapNodeSizeCache, true);' in WB
    assert 'window.addEventListener("pointercancel", wbClearMapNodeSizeCache, true);' in WB
    # The grip drops its own node only: clearing the whole cache there would
    # put the board-wide re-measure back into every frame of a resize.
    assert "wbForgetMapNodeSize(d.id);" in WB


def test_the_pick_up_does_not_scan_the_board_once_per_member() -> None:
    """`wbCaptureBulkMoveOrigin` is handed every topic under the one grabbed.
    A `.find` per member is the whole object list walked once per member."""
    body = _code("wbCaptureBulkMoveOrigin")
    assert ".find(" not in body, "a lookup table, not a scan per member"
    assert "itemFor(kind, id)" in body


def test_an_edge_is_redrawn_once_a_frame_not_once_per_end() -> None:
    """A tree edge joins two topics, so inside a dragged branch it used to be
    recomputed and rewritten from both of them. Both ends move by the same
    delta, so one of the two was always wasted."""
    body = _body("wbCaptureBulkMoveOrigin")
    assert "claimed.has(edgeKey)" in body
    assert "claimed.add(edgeKey)" in body


def test_the_moved_elements_are_found_once_not_once_a_frame() -> None:
    """`wbApplyBulkMove` runs for every moved item on every frame. A document
    query per item per frame is five hundred walks of the document a frame for
    elements that cannot have changed."""
    body = _code("wbApplyBulkMove")
    assert "document.querySelector(" not in body
    assert "wbBulkMoveElement(entry" in body
    # And the re-lookup still has to be real: a render between frames replaces
    # the element, and a stale reference would be updated invisibly forever.
    assert "entry.el.isConnected" in _body("wbBulkMoveElement")


def test_an_edge_finds_its_three_lines_in_one_pass() -> None:
    """`wbMapEdgesFor` is called once per member of a capture. Three
    document-wide attribute queries per edge inside it is thousands of walks
    before the pointer has moved."""
    body = _code("wbMapEdgesFor")
    assert "document.querySelector" not in body
    assert "els.get(" in body
    # And the index, the layout and the elements come in from the caller, so a
    # capture builds them once rather than once per member.
    assert re.search(r"^function wbMapEdgesFor\(id, ctx\)", WB, re.MULTILINE)


def test_a_map_takes_every_element_and_box_in_one_walk() -> None:
    """The frame that picks a branch up wants all of them at once, and one
    `querySelectorAll` plus one batch of reads is one walk and one layout
    flush instead of a thousand of each."""
    body = _body("wbIndexMapNodeElements")
    assert 'document.querySelectorAll(".wb-object[data-id]")' in body
    assert "wbIndexMapNodeElements()" in _body("wbCaptureBulkMoveOrigin")


def test_the_canvas_box_is_measured_once_per_gesture() -> None:
    """Every frame writes SVG geometry before the drop-target test asks for
    this, and an SVG attribute write dirties layout, so the call was re-laying
    out the whole board once a frame. It cannot move while a pointer is down
    on it; it can move between gestures, which is what the listeners cover."""
    assert "if (wbCanvasRectCache) return wbCanvasRectCache;" in _body("wbCanvasOriginRect")
    for event in ("pointerdown", "pointerup", "pointercancel"):
        assert f'window.addEventListener("{event}", wbClearCanvasRectCache, true);' in WB
    assert 'window.addEventListener("resize", wbClearCanvasRectCache);' in WB
    # And the gap the five leave: a keyboard shortcut can move the canvas with
    # no pointer event at all, so a hovering pointer re-measures, which is what
    # it did before the cache, while a gesture (buttons non-zero) keeps it.
    assert "if (!event.buttons) wbClearCanvasRectCache();" in WB
    # The map's drop target reads the pointer through the shared conversion,
    # whose origin is the same per-gesture box (OPEN row 842).
    drop = _body("wbMapDropTargetAt")
    assert "wbClientToBoard(clientX, clientY)" in drop and "invert(" not in drop
    assert "wbCanvasOriginRect()" in _body("wbCanvasOrigin")


def test_an_object_is_raised_once_a_gesture_not_once_a_frame() -> None:
    """The card drag took this fix in INBOX 114 and the object drag did not.
    `raise()` reappends the element even when it is already last, and a DOM
    move invalidates layout, so the next `getBoundingClientRect` in the same
    frame paid for a full re-layout of the board."""
    assert WB.count('d3.select(this.closest(".wb-object")).raise();') == 1
    assert (
        """    if (!d._raised) {
      d3.select(this.closest(".wb-object")).raise();
      d._raised = true;
    }"""
        in WB
    )


# --- INBOX 424a: a group drag on a 250-object board ---------------------------
#
# Measured by the 424 audit at 4x CPU: forty moves of a 20-item selection spent
# 8.6s in long tasks, 2.6s of it in `querySelector`, because the selection bar
# was placed on every move and asked `wbItemBBox` about every member, each ask
# a document-wide query. After: `objDragMove` 5,167ms to 167ms, longest task
# 901ms to 213ms (scratchpad perf harness, board:drag20).


def test_a_drag_places_the_selection_bar_once_a_frame() -> None:
    """Every drag-move handler queues the bar; none places it inline."""
    move =WB[WB.index("function objDragMove(") : WB.index("async function objDragEnd(")]
    assert "wbQueueSelectionBar();" in move
    assert "wbUpdateSelectionBar();" not in move
    queue = _code("wbQueueSelectionBar")
    assert "requestAnimationFrame(" in queue
    # A direct placement calls a queued one off rather than placing twice.
    assert "cancelAnimationFrame(wbSelectionBarFrame)" in _code("wbUpdateSelectionBar")


def test_an_item_box_finds_its_element_once() -> None:
    """`wbItemBBox` goes through the element cache, which re-queries only for an
    element a render has replaced, and every render empties it."""
    bbox = _code("wbItemBBox")
    assert "document.querySelector(" not in bbox
    element = _code("wbItemElement")
    assert "isConnected" in element
    assert "wbItemElCache.clear();" in _code("renderWhiteboard")


def test_the_selection_chrome_is_found_once_per_gesture() -> None:
    chrome = _code("wbTranslateSelectionChrome")
    assert "origin.chromeGroups" in chrome and "isConnected" in chrome
    assert "wbTranslateSelectionChrome(dx, dy, origin);" in _code("wbApplyBulkMove")
    # The bar's own editing check asks the board, not the whole page.
    assert 'container.querySelector(".wb-object.wb-text-editing")' in _code("wbUpdateSelectionBar")


def _translator_js() -> str:
    """The text of `wbTransformPathD.translator`, from its assignment to its closing `};`."""
    match = re.search(r"^wbTransformPathD\.translator = function \(d\) \{.*?^\};\n(?://[^\n]*\n)*wbTransformPathD\.translator\.fractions = .*?^\};", WB, re.M | re.S)
    assert match, "wbTransformPathD.translator is gone"
    return match.group(0)


def test_a_link_inside_the_moved_branch_is_translated_not_recomputed() -> None:
    """Source text: wbCaptureBulkMoveOrigin and wbApplyBulkMove (L-ui-modernisation-61).

    Traced on a 200-topic branch drag carrying 300 cross-links (mapperf.js):
    every link was recomputed from its two topics on every move, and from
    both of them, since a link is listed under each end: the ribbon outline,
    `wbMapRibbonD` and `wbMapSmoothThrough`, was 49ms of each move against 33ms
    for the tree lines, and the linked drag's worst frame was 383ms to the
    plain drag's 117ms. A link with both ends in the moved set keeps its shape
    and only travels, so its drawn `d` is compiled once at the pick-up and
    offset per frame; any other link is claimed by one end only.
    """
    capture = _code("wbCaptureBulkMoveOrigin")
    assert "claimedLinks.has(pair.sketch.id)" in capture and "claimedLinks.add(pair.sketch.id)" in capture
    assert "wbTransformPathD.translator(" in capture and "origin.rigidLinks" in capture
    apply = _code("wbApplyBulkMove")
    assert "entry.movedLinks" in apply and "origin.rigidLinks" in apply
    # The turn about a frame is not a translation: it keeps every link live.
    assert "entry.linked" in _code("wbApplyFrameTurn")


def test_a_rigid_link_moves_by_its_group_and_is_written_once_at_the_end() -> None:
    """Source text: wbCaptureBulkMoveOrigin, wbApplyBulkMove and wbSaveBulkMove (L-ui-modernisation-61).

    A linked branch drag rewrote two `d` attributes per rigid link each move,
    a 1143-element style recalc of 30ms on a 50-topic map. The link's group
    now takes one `transform` per move (a bare page wrote 300 of them in 0.5ms
    against 600 `d`s in 1.7ms); the gesture's end, a cancel and a render that
    replaced the path all write the same `d` a full recompute would.
    """
    capture = _code("wbCaptureBulkMoveOrigin")
    assert "group: el" in capture
    apply = _code("wbApplyBulkMove")
    assert 'rigid.group.setAttribute("transform"' in apply
    assert "origin.rigidAt = dx || dy ? [dx, dy] : null" in apply
    start = WB.index("async function wbSaveBulkMove(")
    save = WB[start:WB.index("\n}\n", start)]
    assert "origin.rigidAt" in save and 'rigid.group.removeAttribute("transform")' in save
    assert "rigid.at(" in save


def test_the_translator_offsets_every_point_and_refuses_what_is_not_a_point_list(tmp_path) -> None:
    """Source text: wbTransformPathD.translator, run in node against three paths."""
    import json
    import shutil
    import subprocess

    import pytest

    if not shutil.which("node"):
        pytest.skip("needs node")
    script = tmp_path / "t.js"
    script.write_text(
        "function wbTransformPathD() {}\n" + _translator_js() + "\n"
        "const t = wbTransformPathD.translator;\n"
        "const ribbon = t('M10 20C1.5 2.5 3 4 -5 6L7 8.25Z');\n"
        "console.log(JSON.stringify([ribbon(0, 0), ribbon(100, -10), t('M0 0A5 5 0 0 1 10 10'), t('M0 0h10'), t(null),\n"
        "  t('M0.05 -0.3L-12.5 1')(-0.1, 0.3), t('M1.004 2')(0, 0)]));\n",
        encoding="utf-8",
    )
    out = json.loads(subprocess.run(["node", str(script)], capture_output=True, text=True, check=True).stdout)
    assert out[0] == "M10 20C1.5 2.5 3 4 -5 6L7 8.25Z"
    assert out[1] == "M110 10C101.5 -7.5 103 -6 95 -4L107 -1.75Z"
    assert out[2:5] == [None, None, None]
    # Hundredths either side of zero, which the whole-number writing has to sign
    # and pad by hand, and a third decimal place, which it rounds away.
    assert out[5] == "M-0.05 0L-12.6 1.3"
    assert out[6] == "M1 2"


def test_the_edge_pan_reads_the_canvas_box_from_the_gesture_cache() -> None:
    """Source text: the edge pan's frame reads the per-gesture canvas box.

    It runs as an animation frame during every drag, after the drag has
    written transforms and link paths, so its own `getBoundingClientRect` laid
    out the whole board again each frame: 1,569ms of a 25-move linked branch
    drag at 200 topics (L-ui-modernisation-61). The pointer is down for as long
    as it runs, which is exactly when the cached box cannot be stale."""
    match = re.search(r"^  function wbEdgePanTick\(\) \{\n(.*?)^  \}\n", WB, re.MULTILINE | re.DOTALL)
    assert match, "wbEdgePanTick is gone; this lint is about its body"
    tick = "\n".join(line for line in match.group(1).splitlines() if not line.lstrip().startswith("//"))
    assert "wbCanvasOriginRect()" in tick
    assert "containerEl.getBoundingClientRect()" not in tick


def test_a_tree_line_inside_the_moved_branch_is_translated_not_recomputed() -> None:
    """Source text: wbCaptureBulkMoveOrigin and wbApplyBulkMove (L-ui-modernisation-61).

    Once the links travelled, the tree lines were the largest script cost of a
    200-topic branch drag: `wbUpdateMapEdges` redrew each one from its two
    topics every move, 1,392ms of the 25-move drag, 747ms of it the ribbon's
    spline. A line with both topics in the moved set only travels, like a
    link, so its paths, its two end dots, its handle and its label are read
    once at the pick-up and offset per frame."""
    capture = _code("wbCaptureBulkMoveOrigin")
    assert "origin.rigidEdges" in capture and "rigidEdge(edge)" in capture
    apply = _code("wbApplyBulkMove")
    assert "origin.rigidEdges" in apply and "_wbMoved = true" in apply
