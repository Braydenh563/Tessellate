"""sm-1111 row 27: a pen stroke in flight is dropped when its gesture is taken
away. Measured before (r27 sweep, pen down, `v`, release): the live path stayed
in `#wb-overlay-zoom-group` (1 orphan, 0 sketches) and, with the pen picked
again, a bare hover kept extending it because `isDrawing` was still true."""

from tests._app_js import frontend_text

WB = frontend_text("whiteboard.js")


def test_abandon_helper_clears_every_piece_of_the_stroke():
    body = WB[WB.index("function wbAbandonStroke()") :]
    body = body[: body.index("\n  }\n")]
    #: L634 moved the four pen `let`s into one `wbPen` holder (whiteboard-strokes.js reads it).
    for part in ("wbPen.drawing = false", "wbPen.path?.remove()", "wbPen.path = null", "wbPen.data = []"):
        assert part in body


def test_tool_switch_and_lost_gesture_abandon_the_stroke():
    sw = WB[WB.index("function selectWbTool(tool)") :]
    #: L634: the stroke helpers live in whiteboard-strokes.js and are reached through `wbPen`.
    assert "wbPen.abandon?.()" in sw[:400]
    assert 'window.addEventListener("pointercancel", wbAbandonStroke)' in WB
    assert 'window.addEventListener("pointerup", wbAbandonStroke)' in WB
