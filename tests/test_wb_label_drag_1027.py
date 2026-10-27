"""A connector's label slides by its own words (INBOX 1404). The 10px grip at
its leading edge is gone (replace, not layer): the text takes the press,
`label_t` is saved as before, one undo step restores it, a click still
selects and a double-click edits."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
CSS = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "frontend" / "css").glob("*.css"))


def _body(signature: str, size: int = 2300) -> str:
    return WB[WB.index(signature):][:size]


def test_the_separate_grip_is_gone():
    assert "wbRenderLinkLabelGrip" not in WB
    assert "wb-link-label-handle" not in WB
    assert "wb-link-label-handle" not in CSS


def test_the_painted_label_is_wired_and_takes_the_press():
    body = _body("function wbPaintLinkLabel(", 1500)
    assert 'setAttribute("pointer-events", "none")' not in body
    assert "wbWireLinkLabelDrag(label, groupEl)" in body


def test_the_words_take_the_press_and_slide_along_the_line():
    body = _body("function wbWireLinkLabelDrag(")
    assert 'setAttribute("pointer-events", "none")' not in body
    assert "d3.drag()" in body
    assert "wbLinkNearestT(" in body
    assert "label_t" in body
    assert 'wbPushUndo({ action: "move", kind: "sketch"' in body


def test_a_press_that_did_not_move_saves_nothing_and_the_click_still_selects():
    body = _body("function wbWireLinkLabelDrag(")
    assert "clickDistance(WB_CLICK_SLOP)" in body
    assert "if (!moved)" in body or "if (moved)" in body
    # The click bubbles to the connector's own handler (selection); not stopped here.
    assert '.on("click"' not in body


def test_a_double_click_on_the_words_edits_the_label_not_a_bend():
    body = _body("function wbWireLinkLabelDrag(")
    assert 'on("dblclick"' in body
    assert "wbEditLinkLabel(" in body
    assert "stopPropagation()" in body


def test_only_the_select_tool_drags_a_label():
    body = _body("function wbWireLinkLabelDrag(")
    assert 'window.currentTool === "select"' in body
