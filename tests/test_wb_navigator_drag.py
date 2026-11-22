"""Dragging the board overview's rectangle tracks the pointer (INBOX 431).

The owner, 2026-09-28: "the fit drag mini fit map on the whiteboard and
mindmap is reallllly glitchy and laggy." The drag half of it: every pointer
move ran the whole jump (the content bounds measured from the DOM, the
overview's own box measured, a fresh projection that could rescale under the
pointer, a transform), and a press on the rectangle jumped its centre to the
pointer rather than picking it up where it was held. Now the press measures
once and freezes the projection, the moves are coalesced into one animation
frame, and the grab point is kept.

Static checks; `scratchpad/ui-sweeps/minimapdrag.js` is the measurement.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.test_wb_navigator_cost import WB_JS, code, function_text

ROOT = Path(__file__).resolve().parents[1]
CSS = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))


def test_drag_is_coalesced_into_one_frame() -> None:
    move = code(function_text("wbNavigatorDragMove"))
    assert "requestAnimationFrame(" in move
    assert "wbZoom.transform" not in move
    frame = code(function_text("wbNavigatorDragFrame"))
    assert "wbZoom.transform" in frame
    # The grid, the cull and the rectangle land in the same frame as the
    # transform, not one frame behind it.
    assert "wbFlushZoomFrame(" in frame
    assert "getBoundingClientRect" not in frame
    assert "wbContentBounds(" not in frame


def test_drag_freezes_its_projection_and_keeps_the_grab_point() -> None:
    start = code(function_text("wbNavigatorDragStart"))
    assert "wbBoardState.capture(svg, event.pointerId)" in start  # the one capture helper (L271)
    assert "getBoundingClientRect" in start  # measured once, at the press
    assert "grab" in start
    update = code(function_text("wbNavigatorUpdateViewport"))
    assert "wbNavState.drag" in update


def test_drag_ends_on_every_way_out() -> None:
    for name in ("pointerup", "pointercancel", "lostpointercapture"):
        assert re.search(
            rf'navMap\.addEventListener\("{name}", wbNavigatorDragEnd\)', WB_JS
        ), f"the overview drag does not end on {name}"
    end = code(function_text("wbNavigatorDragEnd"))
    assert "cancelAnimationFrame(" in end
    assert "wbRenderNavigator(" in end


def test_old_per_event_jump_is_gone() -> None:
    assert "function wbNavigatorJump(" not in WB_JS


def test_dragging_cursor_and_no_transition_on_the_rectangle() -> None:
    assert re.search(r"\.wb-navigator-map\.is-dragging\s*\{[^}]*cursor:\s*grabbing", CSS)
    rule = re.search(r"\.wb-nav-viewport\s*\{([^}]*)\}", CSS)
    assert rule and "transition" not in rule.group(1)
