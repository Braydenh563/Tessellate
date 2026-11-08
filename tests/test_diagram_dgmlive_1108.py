"""What the real-browser run of the diagram fixes (dgmlive 1108) found; these read the source for what has to stay true."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")


def test_a_rename_ended_by_a_press_on_another_field_does_not_pull_focus_back_to_the_block():
    """Measured in Chromium: Add box, then a click on the dialog's title put focus on the block and the typing went nowhere."""
    body = BUILDER.split("function beginEdit(")[1].split("\n  function stepBlock(")[0]
    assert "const onBlur = (event) => end(true, event.relatedTarget)" in body
    assert "const end = (keep, movedTo = null) =>" in body
    assert "if (block && !movedTo && document.activeElement !== block) block.focus();" in body


OUTLINE = (JS / "diagram-outline.js").read_text(encoding="utf-8")


def test_keep_on_the_sideways_offer_is_remembered_by_diagram_only_never_on_the_reused_pane():
    """Measured in Chromium: Keep on one document hid the offer on the next, because the pane (and its flag) is reused across documents."""
    body = OUTLINE.split("function offer(")[1].split("\n  }\n")[0]
    assert "sidewaysAsked" not in body
    assert "!answered.has(whose(S))" in body
    assert "answered.add(whose(S))" in body
