"""sm-1111 row 27, the drags: a card, object, shape or link drag whose pointer is
taken away is put back and let go, and a move that could not be saved (offline)
goes back where it was. Measured before in Chromium (a real board, a card and a
text box, lost `mouseup`): after a pointercancel or a blur the gesture stayed
live, the item followed a buttonless hover and the delete target stayed up
(3 orphans each); an offline release left the item 90px from the server's copy
with no word. drag-edge.js: a pointercancel or native drag left its zone, press
and frame loop running (3 orphans)."""

from tests._app_js import frontend_text
from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend/js"
WB = frontend_text("whiteboard.js")
EDGE = (JS / "drag-edge.js").read_text(encoding="utf-8")


def _body(src: str, head: str) -> str:
    body = src[src.index(head) :]
    return body[: body.index("\n  }\n")]


def test_a_lost_pointer_cancels_the_gesture_and_lets_d3_go():
    body = _body(WB, "function wbDropLostGesture()")
    assert "wbCancelGesture()" in body
    assert 'new MouseEvent("mouseup"' in body  # d3-drag lets go of its window listeners only on mouseup
    assert 'window.addEventListener("pointercancel", wbDropLostGesture, true)' in WB
    assert 'window.addEventListener("blur", wbDropLostGesture)' in WB
    assert 'wbGesture && e.pointerType === "mouse" && e.buttons === 0' in WB


def test_a_tool_switch_drops_a_drag_in_flight():
    sw = WB[WB.index("function selectWbTool(tool)") :][:500]
    assert "wbDropLostGesture()" in sw


def test_a_move_that_cannot_be_saved_goes_back():
    for head in ("async function wbSaveNode(", "async function wbSaveObject("):
        body = WB[WB.index(head) :]
        body = body[: body.index("\n}\n")]
        assert "delete " in body and "._unsaved = true" in body, head
    for head in ("async function dragEndNode(", "const reallyMoved = "):
        end = WB[WB.index(head) :][:9000]
        assert "if (d._unsaved) {" in end and "toast(" in end and "wbScheduleRender()" in end, head


def test_drag_edge_lets_go_when_the_pointer_is_taken_away():
    assert 'for (const event of ["pointercancel", "dragstart", "dragend"]) document.addEventListener(event, release, true)' in EDGE
