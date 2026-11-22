"""The board overview costs little per pan frame (INBOX 431).

The owner, 2026-09-28: "the fit drag mini fit map on the whiteboard and
mindmap is reallllly glitchy and laggy." The overview (`#wb-navigator`) is one
widget on both surfaces. Measured before the fix on a 150-card board at a 4x
CPU throttle (`scratchpad/ui-sweeps/minimapdrag.js`): a one-second drag of
its viewport rectangle took 9.7 seconds to deliver, with 9,222 forced layouts
and a p95 frame of 183ms. The drawing half of that, pinned here:

* `wbRenderNavigator` read every card's size (`offsetWidth`) between appends
  to the overview's SVG, so every item forced a fresh layout of the page: 151
  layouts per redraw of 150 items. It reads everything first now and writes
  once.
* That full redraw ran on every pan and zoom frame. A pan frame now moves the
  viewport rectangle (and, when the map rescales, sets one transform on the
  items group); the items are redrawn after a board render.

Static checks, because the suite cannot drive a pointer; the sweep is the
measurement.
"""

from __future__ import annotations

from tests._app_js import frontend_text
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WB_JS = frontend_text("whiteboard.js")


def function_text(name: str) -> str:
    """The text of a top-level `function name(...) {...}` in whiteboard.js."""
    match = re.search(rf"^function {re.escape(name)}\(", WB_JS, re.M)
    assert match, f"{name} is missing from whiteboard.js"
    end = re.search(r"^\}", WB_JS[match.start():], re.M)
    assert end
    return WB_JS[match.start(): match.start() + end.end()]


def code(text: str) -> str:
    """Strip `//` comments, so prose about a call is not mistaken for one."""
    return "\n".join(line.split("//", 1)[0] for line in text.splitlines())


def test_full_redraw_reads_before_it_writes() -> None:
    body = code(function_text("wbRenderNavigator"))
    # One write of the SVG's children, of a fragment built off the document,
    # never an append per item between the size reads.
    assert "svg.append(" not in body
    assert "createDocumentFragment" in body
    assert body.count("replaceChildren(") == 1
    assert body.index("wbNavigatorSnapshot(") < body.index("replaceChildren(")
    snapshot = code(function_text("wbNavigatorSnapshot"))
    for write in ("append(", "setAttribute(", "classList", "replaceChildren("):
        assert write not in snapshot


def test_pan_frame_moves_the_rectangle_and_does_not_redraw() -> None:
    frame = code(function_text("wbZoomFrameWork"))
    assert "wbNavigatorUpdateViewport(" in frame
    assert "wbRenderNavigator(" not in frame
    handler = code(function_text("handleWbZoom"))
    assert "wbRenderNavigator(" not in handler
    assert "requestAnimationFrame(wbZoomFrameWork)" in handler
    update = code(function_text("wbNavigatorUpdateViewport"))
    # No measurement of the board's items on a pan frame.
    assert "wbContentBounds(" not in update
    assert "wbItemBBox(" not in update
    assert "getBoundingClientRect" not in update


def test_a_render_marks_the_overview_stale() -> None:
    assert "wbNavState.stale = true" in code(function_text("renderWhiteboard"))


def test_frame_reads_the_canvas_size_before_it_writes() -> None:
    frame = code(function_text("wbZoomFrameWork"))
    read = frame.index("clientWidth")
    for write in ("wbSyncGridToTransform(", "wbCullNow(", "wbNavigatorUpdateViewport("):
        assert read < frame.index(write), f"{write} runs before the size read"
    assert "wbCullNow(t, size)" in frame
    assert "wbNavigatorUpdateViewport(t, size)" in frame


def test_an_animated_fit_draws_its_destination_once_and_holds_the_cull() -> None:
    fit = code(function_text("wbZoomToFit"))
    # The destination is drawn before the animation starts, and the hold is
    # lifted on both ways an animation stops.
    assert fit.index("wbCullNow(target)") < fit.rindex(".transition()")
    assert '.on("end.cullhold", release)' in fit
    assert '.on("interrupt.cullhold", release)' in fit
    assert "if (wbCullHeld) return;" in code(function_text("wbCullNow"))


def test_the_inverse_zoom_is_written_onto_the_grips_that_read_it() -> None:
    """Every rule that reads `--wb-inv-zoom` is a grip the sheet writes to.

    The property used to be written on `#whiteboard-container` and inherited
    by every element on the board, so one write after each zoom re-styled
    the lot (290ms on a 150-topic map at 4x). It is written into a
    constructed sheet naming the grips now; a grip rule added to the CSS
    without its selector in `WB_INV_ZOOM_GRIPS` would stay at the root's 1
    and grow with the board, which this catches.
    """
    #: The board's rules are in the boot sheet and in library-lazy.css (the
    #: boot CSS budget moved the ones only the Library bundle draws).
    css_text = "\n".join(
        (ROOT / "frontend" / "css" / name).read_text(encoding="utf-8")
        for name in ("07-whiteboard-misc.css", "library-lazy.css")
    )
    css_text = re.sub(r"/\*.*?\*/", "", css_text, flags=re.S)
    readers: set[str] = set()
    for selectors, body in re.findall(r"(?:(?<=[{}])|\A)([^{}]+)\{([^{}]*)\}", css_text):
        if "var(--wb-inv-zoom)" in body:
            readers.update(s.strip() for s in selectors.split(","))
    listed = re.search(r"const WB_INV_ZOOM_GRIPS = \[(.*?)\];", WB_JS, re.S)
    assert listed
    grips = set(re.findall(r'"([^"]+)"', listed.group(1)))
    assert readers and readers == grips
    sync = code(function_text("wbSyncGridToTransform"))
    assert 'setProperty("--wb-inv-zoom"' not in sync
    publish = code(function_text("wbPublishInvZoom"))
    assert "replaceSync(" in publish and "adoptedStyleSheets" in publish
