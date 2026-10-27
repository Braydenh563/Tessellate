"""The graph note popup follows its node and its head drags it (INBOX 1413).

The owner, 2026-10-27: "can it be possible to drag the graph popups?? or have
them move with the node it showed for". Measured by
`scratchpad/ui-sweeps/graphpopupfollow.js`: the popup-to-node offset holds
across a 200px pan and a 1.6x zoom, the popup never overlaps its node, a drag
moves it by the pointer's travel (clamped to the map) and it then stays put.
These pin the wiring those numbers rest on.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")
CANVAS = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "04-chat-dock-appearance.css").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = GRAPH.index(f"function {name}(")
    return GRAPH[start : GRAPH.index("\n}\n", start) + 2]


def test_the_popup_is_placed_again_by_the_canvas_frame_not_a_second_loop():
    assert "placeGraphPopup();" in CANVAS[CANVAS.index("gcHoverCardFrame(s);\n") :][:300]
    assert "requestAnimationFrame" not in _fn("graphPopupFollowSpot")


def test_an_undragged_popup_stands_clear_of_its_node_and_hides_off_view():
    body = _fn("graphPopupFollowSpot")
    assert "const clear = (x, y)" in body
    assert 'classList.toggle("graph-popup-away", gone)' in body
    place = _fn("placeGraphPopup")
    assert "graphLate.popupDragged" in place and "graphPopupFollowSpot(box, room, size)" in place


def test_the_head_drags_and_a_dragged_popup_stays_until_closed():
    assert 'closest("button, input, textarea, a")' in _fn("graphPopupDragStart")
    assert "graphLate.popupDragged = true;" in _fn("graphPopupDragMove")
    assert "graphLate.popupDragged = false;" in _fn("closeGraphPopup")
    assert "graphLate.popupDragged = false;" in _fn("openGraphPopup")


def test_the_head_is_a_grab_handle_that_touch_does_not_scroll():
    assert "cursor: grab;" in CSS and "touch-action: none;" in CSS
    assert ".graph-popup.graph-popup-away" in CSS
