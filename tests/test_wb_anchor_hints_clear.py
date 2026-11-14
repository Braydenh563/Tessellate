"""The link tool's anchor dots go when the link tool does (INBOX 573, the
owner: "these anchor points appeared and wont go away").

The hover listener drew a topic's eight dots under the cross-link tool and
returned early under every other tool, so after Select (V, Escape) the dots
stayed through a press on the canvas, Undo, a tab switch and the Shape menu.
`scratchpad/ui-sweeps/mmdoc1005-handlesleft.js` deselects five ways and counts
what is left (0/5 before, 5/5 after); these pin the four places that clear.
"""

from __future__ import annotations

from tests._app_js import frontend_text

WB = frontend_text("whiteboard.js")


def _body(signature: str, size: int = 900) -> str:
    return WB[WB.index(signature):][:size]


def test_the_hover_listener_clears_off_a_link_tool():
    start = WB.index('if (!window.currentTool || !window.currentTool.startsWith("link-")) {')
    assert "wbClearAnchorHints();" in WB[start:start + 200]


def test_a_tool_switch_deselect_and_overlay_clear_take_the_dots():
    assert "wbClearAnchorHints()" in _body("function selectWbTool(tool) {", 300)
    assert "wbClearAnchorHints()" in _body("function clearWbSelection() {", 300)
    assert "wbClearAnchorHints()" in _body("function wbClearSelectionOverlays() {", 400)


def test_a_map_topic_has_no_free_resize_handles():
    """Its size is its text's and its own grips' (MINDMAP_PLAN): the eight
    handles are for boxes and cards."""
    #: Armed only for a box (the handles are built on first need, BD3), never for a topic.
    armed = WB[WB.index('    if (WB_MAP_KINDS.has(d.kind)) return;\n    wbArmHandles('):][:200]
    assert "wbBuildObjectHandles(el, d.kind)" in armed
    build = WB[WB.index("function wbBuildObjectHandles("):][:200]
    assert "wb-resize-handle" in build
