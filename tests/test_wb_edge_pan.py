"""INBOX 608: a marquee or an item dragged to the board's edge pans it.

The owner: "when I drag select off the screen on the whiteboard and mind map
... it doesnt scroll down or up or the way I am dragging". The browser
measurement is scratchpad/ui-sweeps/bm1005-edgepan.js (a held marquee and a
held item each pan hundreds of pixels a second; the item stays under the
pointer). These pin the wiring that measurement depends on.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _section() -> str:
    start = WB.index("const wbEdgePan = {")
    return WB[start:WB.index("// Anchor points weren't discoverable", start)]


def test_edge_pan_runs_for_a_marquee_and_an_item_drag_only():
    body = _section()
    assert "wbMarqueeEl && wbMarqueeStart && !wbMarqueeStart.pending" in body
    # Not while the dragged item is over the delete target (INBOX 660): the
    # board scrolling under it would carry it off the target.
    assert "wbGesture && !wbGesture.cancelled && !wbGesture.overTrash && !wbEdgePan.turn" in body
    # Not for the pen tools or the hand, and not for a rotation.
    assert "WB_BRUSH_TOOLS.has(window.currentTool)" in body
    assert ".wb-rotate-handle, .wb-sketch-rotate-handle" in body


def test_speed_grows_with_depth_into_the_band():
    body = _section()
    assert "share * share" in body
    assert "wbZoom.translateBy" in body


def test_the_pointer_is_replayed_after_each_step():
    body = _section()
    # The marquee is redrawn from the pointer; an item drag gets a move at
    # the same screen point, so it travels with the board.
    assert "wbMarqueeAt = getLogicalMouse(at)" in body
    # Called on d3-drag's listener, never broadcast to every mousemove
    # listener (audit B16).
    assert 'd3.select(window).on("mousemove.drag")?.call(window, new MouseEvent("mousemove", at))' in body
    assert "dispatchEvent" not in body


def test_help_says_so():
    help_text = (ROOT / "src" / "tessellate" / "ai" / "help_chat.py").read_text(encoding="utf-8")
    assert "a drag to an edge pans" in help_text
