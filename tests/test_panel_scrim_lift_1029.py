"""The owner 2026-10-29: "there's no point in dragging windows if the background
is darkened right?? I feel it should only be dark in the default position. also
the ocr workspace is difficult and annoing to drag and I keep accidentally
highlighting things on it".

A moved, docked or resized panel marks its scrim (`data-panel-moved`) and the
scrim goes clear; reset puts the dim back. The OCR head sits one level down
(`.ocr-head > .dialog-head`), so it had no grab cursor, no no-select rule and no
reset button; the head is now found one level down and tagged
`panel-drag-head`. Measured in Chromium at 1440x900, a (+120,+80) drag on the
OCR title: card (29,54) to (149,134), scrim rgba(17,20,32,0.45) to transparent,
selection 0 characters, head cursor grab and user-select none; reset: card back
to (29,54), scrim 0.45.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend" / "js" / "panel-movable.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "panel-movable-lazy.css").read_text(encoding="utf-8")


def _body(name: str) -> str:
    start = JS.index(f"function {name}(")
    return JS[start : JS.index("\n}\n", start)]


def test_every_save_and_apply_sets_the_scrim_state():
    assert "data-panel-moved" in _body("panelScrimLift")
    assert "st.x || st.y || st.dock || st.w !== null" in _body("panelScrimLift")
    assert "panelScrimLift(panel, st)" in _body("panelSave")
    assert "panelScrimLift(panel, st)" in _body("panelApply")


def test_moved_scrim_is_clear_for_overlays_and_dialogs():
    assert '[data-panel-moved]:is(.modal-overlay, [id$="-overlay"])' in CSS
    assert "dialog[data-panel-moved]::backdrop" in CSS
    assert CSS.count("background: transparent") >= 2


def test_head_is_found_one_level_down_and_cannot_select_text():
    assert ":scope > * > .dialog-head" in _body("panelHeadOf")
    assert 'classList.add("panel-drag-head")' in _body("panelAdopt")
    rule = CSS[CSS.index(".panel-movable-on .panel-drag-head {") :]
    rule = rule[: rule.index("}")]
    assert "user-select: none" in rule and "cursor: grab" in rule and "touch-action: none" in rule
    # `.panel-head` is the h3 recipe (DESIGN.md); the drag tag must not reuse it.
    assert "panel-head\"" not in JS
