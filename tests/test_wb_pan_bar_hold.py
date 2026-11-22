"""A pan holds the selection bar's measurements (owner, 2026-10-12, third
report of a laggy mind map with a node selected). Measured on a 40-topic map:
placing the topic strip cost 30 ms a frame (rects, offsets and the strip's
controls refilled); held, 0.15 ms (a Playwright page.evaluate loop over
`wbUpdateSelectionBar(panning)` with one topic selected)."""

from tests._app_js import frontend_text
import re

JS = frontend_text("whiteboard.js")


def test_the_pan_frame_places_the_bar_from_held_measurements():
    frame = JS[JS.index("function wbZoomFrameWork"):]
    assert "wbUpdateSelectionBar(true)" in frame[:3000]


def test_the_hold_is_cleared_by_any_other_placement_and_by_the_pans_end():
    body = JS[JS.index("function wbUpdateSelectionBar("):]
    assert re.search(r"if \(!panning\) wbAddGate\.panBarHold = null", body[:600])
    end = JS[JS.index("function wbEndPanShield"):]
    assert "wbAddGate.panBarHold" in end[:1200] and "wbUpdateSelectionBar()" in end[:1200]


def test_the_exact_placement_waits_for_the_pan_to_go_quiet():
    """A wheel gesture ends whenever frames come slower than d3's 150 ms, so a
    placement at every end ran a full measure per step (19 ends in 20 steps on
    a 120-topic map: 72 ms each, 71 s for 80 steps at a 4x throttle; with the
    wait, 0.1 s). The next pan frame cancels the wait."""
    end = JS[JS.index("function wbEndPanShield"):][:1200]
    assert "setTimeout(" in end and "wbAddGate.panBarTimer" in end
    frame = JS[JS.index("function wbZoomFrameWork"):][:3500]
    assert "clearTimeout(wbAddGate.panBarTimer)" in frame


def test_the_selection_box_is_held_through_a_pan_too():
    body = JS[JS.index("function wbUpdateSelectionBar("):]
    assert "let box = panHeld ? panHeld.box : null;" in body
    assert "sideEdges, box }" in body


def test_a_held_pan_does_not_refill_the_strip_or_walk_the_board():
    body = JS[JS.index("function wbUpdateSelectionBar("):]
    assert "mapNode && !panHeld) wbSyncMapStrip" in body
    assert "!panHeld && container.querySelector" in body
