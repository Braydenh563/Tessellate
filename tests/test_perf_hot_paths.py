"""The hot paths INBOX 424's audit measured, held to the shape that fixed them.

The measurement itself lives outside the suite: a CDP CPU profile at 4x
throttle on a 400-note, 1,200-link, 250-object-board, 120-topic-map fixture,
one gesture per row (the perf harness the 424 audit wrote). The suite cannot
drive a pointer through a real layout, so what it holds here is the *shape*
each number came from: every rule below is one cost that reads as ordinary
code and only shows up under a profiler. If one fails, the question is "what
does this do per frame now", not "how do I word the rule differently".

    gesture at 4x CPU            the cost                      before   after
    graph node drag, 40 moves    graphMinimapPaint             1,502ms  514ms
    graph wheel zoom, 16 steps   measureText                     165ms    0ms
    graph revisit, first 12s     main-thread task time         6,746ms  1,382ms
    map expand of the root       wbBuildMapNode                  321ms    0ms
    lightbox next, 5 presses     show (scrollTo inside)          457ms   37ms
    typing 50 characters         autoGrow                        492ms   16ms
"""

from __future__ import annotations

import re
from pathlib import Path
from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"


def _source(name: str) -> str:
    return frontend_text(name)


def _body(source: str, name: str) -> str:
    """One top-level function's text, comment lines dropped.

    Crude on purpose: every function asked about is declared at the left
    margin, and the next left-margin `function` is where it ends. Comments go
    because they quote the very shapes the rules forbid, to say why.
    """
    match = re.search(rf"^(?:async )?function {re.escape(name)}\(", source, re.MULTILINE)
    assert match, f"{name} is gone; this lint is about its body"
    rest = source[match.end() :]
    end = re.search(r"^(?:async )?function \w+\(", rest, re.MULTILINE)
    body = rest[: end.start()] if end else rest
    return "\n".join(line for line in body.splitlines() if not line.lstrip().startswith("//"))


# --- 424b: the graph minimap during a layout ---------------------------------


def test_layout_ticks_queue_the_minimap_rather_than_paint_it() -> None:
    """A tick asks for a paint; the frame runs at most one."""
    canvas = _source("graph-canvas.js")
    graph = _source("graph.js")
    assert "graphMinimapTick % 8 === 0) graphMinimapQueuePaint();" in canvas
    assert 'if (s.size === "full") graphMinimapQueuePaint();' in canvas
    # graph.js held the SVG renderer's copy of the tick until that renderer
    # was removed (audit 1029 row 60); the canvas tick above is the one left.
    queue = _body(graph, "graphMinimapQueuePaint")
    assert "requestAnimationFrame(" in queue
    assert "graphMinimapCanShow()" in queue


def test_a_hidden_minimap_is_not_painted() -> None:
    """Switched off, on a hidden tab or in a hidden window: marked stale, not
    painted, and painted when the window comes back."""
    graph = _source("graph.js")
    can_show = _body(graph, "graphMinimapCanShow")
    assert "document.hidden" in can_show
    assert "GRAPH_MINIMAP_CORNER_KEY" in can_show and '"off"' in can_show
    assert 'getElementById("tab-graph")' in can_show
    assert "graphMinimapStale = true;" in _body(graph, "graphMinimapQueuePaint")
    assert 'addEventListener("visibilitychange"' in graph


def test_a_paint_moves_the_dots_it_has() -> None:
    """No fresh elements per paint once the count is right: the dots and lines
    are reused and an unchanged attribute is not written again."""
    paint = _body(_source("graph.js"), "graphMinimapPaint")
    assert "dots.replaceChildren(" not in paint
    assert "edgesGroup.replaceChildren(" not in paint
    assert 'graphMinimapChildren(dots,' in paint
    assert 'graphMinimapChildren(edgesGroup,' in paint
    assert "createElementNS" not in paint.split("const here")[0]
    assert "el[key] === value" in _body(_source("graph.js"), "graphMinimapSet")


# --- 424c: the graph's labels on a wheel zoom ----------------------------------


def test_a_label_is_measured_once_per_text_not_per_zoom_step() -> None:
    """The label font is `12 / k` px, so a zoom makes every size new: the
    width is measured at one reference size and scaled, and the cache is
    dropped when the font changes."""
    canvas = _source("graph-canvas.js")
    assert "node._labelWidth = gcLabelWidth(text, size);" in canvas
    assert "node._labelWidth = ctx.measureText(" not in canvas
    width = _body(canvas, "gcLabelWidth")
    assert "GC_LABEL_REF_PX" in width
    assert "gcLabelWidths.clear();" in width
    assert "font !== gcLabelWidthFont" in width


# --- 424c/d: a settled layout on a revisit -----------------------------------


def test_a_settled_layout_is_held_when_nothing_it_depends_on_changed() -> None:
    """A visit to Graph refetched and re-settled a map that had already come
    to rest (about 7s of main-thread work per visit at 4x CPU). The layout's
    inputs are signed; the same signature as the last layout to settle, with
    every note starting where it left off, starts at rest."""
    canvas = _source("graph-canvas.js")
    start = _body(canvas, "gcStartWorker")
    assert "viewSeed?.holdIfSettled && s.settledSig === sig" in start
    assert "s.settledSig = null;" in start
    # Only a layout that really came to rest may be held.
    assert "s.settledSig = s.layoutSig;" in start
    render = _body(canvas, "renderGraphCanvas")
    assert "holdIfSettled: !viewPositions &&" in render
    # A tree leaves tree positions behind: nothing is held from them.
    assert render.index("s.settledSig = null;") > render.index("if (s.tree) {")


# --- 424e: a mind map expand -------------------------------------------------


def test_a_folded_topic_is_taken_back_not_rebuilt() -> None:
    """A collapse takes the branch out of the DOM; the expand used to build
    every topic in it again. The exit keeps the elements of folded topics,
    the enter takes them back (only for the very datum they were built for,
    since the node's controls close over it), and a taken-back element skips
    the build and repaints in full."""
    wb = _source("whiteboard.js")
    render = _body(wb, "renderWbObjects")
    assert ".append((d) => wbMapNodeTakeBack(d) || document.createElement(\"div\"))" in render
    assert "wbMapNodePool.set(d.id, this)" in render
    assert "if (this._wbTakenBack) {" in render
    assert "this._wbPaintKey = undefined;" in render
    # The pool is trimmed after the enter, never before it: trimming first
    # dropped every element the expand was about to take back.
    assert render.index("wbMapNodePool.delete(id)") > render.index("wbMapNodePool.set(d.id, this)")
    take = _body(wb, "wbMapNodeTakeBack")
    assert "kept.__data__ !== d" in take


# --- 424f: the lightbox's next and previous -----------------------------------


def test_fit_scrolls_only_a_scroller_that_is_away_from_its_origin() -> None:
    """`show()` sets fit for every picture, and a `scrollTo` against a stage
    whose picture was just swapped is a forced layout, for a stage already at
    its origin (375ms of five presses at 4x CPU). The scroll listeners keep
    the answer, so asking costs no layout read."""
    app = _source("app.js")
    start = app.index("const applyZoom = () => {")
    block = app[start : app.index("const setZoom = (next, anchor = null) => {", start)]
    assert "scrolledAway.has(scroller)" in block
    assert "scrollTarget().scrollTo(" not in block
    assert "trackScrolledAway(stage);" in block
    assert "trackScrolledAway(doc);" in app
    # A pan marks it at once, not a frame later at its scroll event.
    pan = app[app.index("const movePan = (e) => {") :]
    # The picture pans by translate (no scroller involved) and returns early;
    # the scroll-based pan below it, for PDF pages, still marks its scroller.
    assert "scrolledAway.add(scroller);" in pan[: pan.index("\n  };")]


# --- 424h and 424i: autogrow on a tab switch and while typing ------------------


def test_a_mirrored_note_box_is_not_grown() -> None:
    """Once the capture box's editor has mounted, the textarea is an invisible
    mirror sized by the stylesheet, and every keystroke's `input` grew it with
    a forced layout (448ms of a typing run at 4x CPU)."""
    grow = _body(_source("app.js"), "autoGrow")
    mirror_at = grow.index('el.classList.contains("note-surface-mirror")')
    assert mirror_at < grow.index("el.offsetParent"), "the class check comes before any layout read"
    mount = _source("documents.js")
    at = mount.index('host.classList.add("note-surface-mirror");')
    assert 'host.style.height = "";' in mount[at : at + 400]


def test_a_tab_switch_grows_only_the_boxes_that_could_be_wrong() -> None:
    """Every visible box was grown on every switch, write-read-write per box.
    Now every check is read in one pass and only a box measured while hidden,
    or whose text, width, font or caps changed, is grown after it."""
    app = _source("app.js")
    visible = _body(app, "autoGrowVisible")
    assert "box._autoGrownValue !== box.value" in visible
    assert "box._autoGrownFor !== autoGrowInputs(box)" in visible
    assert visible.index("due.push(box)") < visible.index("for (const box of due) autoGrow(box);")
    assert "autoGrowVisible();" in _body(app, "revealTab")
    grow = _body(app, "autoGrow")
    assert "el._autoGrownFor = autoGrowInputs(el);" in grow


def test_a_keystroke_that_changes_no_height_writes_nothing() -> None:
    """The performance pass, 2026-09-27: every key in the chat composer ran
    autoGrow's full path (height to auto, measure, write, measure, then the
    dock fit), 82 forced style recalcs and 82 layouts for 40 keys, and 11ms
    of event dispatch per key. Text that only grew at its end and still fits
    the height already set changes nothing, so it is answered with one read
    before anything is written (`scratchpad/ui-sweeps/autogrowfast.js` holds
    the heights equal to the full path's)."""
    app = _source("app.js")
    grow = _body(app, "autoGrow")
    assert grow.index("autoGrowStillFits(el)") < grow.index('el.style.height = "auto"')
    fits = _body(app, "autoGrowStillFits")
    assert "now.startsWith(before)" in fits and "el.dataset.maxPx" in fits
    assert "el.style.height =" not in fits, "the fast path only reads"
