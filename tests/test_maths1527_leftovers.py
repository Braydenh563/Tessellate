"""maths1527-1101 leftovers: the calculator sheet and a math field's own keys.

Escape in LaTeX mode closed the whole dialog (the sheet's capture-phase
handler ran before MathLive's, which returns to the formula), and a stray press
on the scrim dropped a half-written equation (the popover it replaced ignored
an outside press once something was typed).
"""

from __future__ import annotations

import re

from tests._app_js import with_pieces


def _sheet() -> str:
    text = with_pieces("phone-shell.js")
    start = text.index("function openSheet(")
    return text[start : text.index("\n}\n", start)]


def test_a_math_field_in_latex_mode_keeps_its_escape():
    sheet = _sheet()
    guard = sheet.index('field.mode === "latex") return;')
    #: Before the sheet stops the event, so MathLive still receives it.
    assert guard < sheet.index("event.stopPropagation();\n    //: An open '?' popover")
    assert "card.contains(field)" in sheet


def test_a_scrim_press_keeps_a_sheet_that_holds_work():
    sheet = _sheet()
    assert "hasWork = null" in sheet.split("\n", 1)[0]
    assert "wireBackdropClose(overlay, () => hasWork?.() || close());" in sheet
    #: Escape and the X still close it.
    assert 'closeButton.addEventListener("click", close);' in sheet


def test_the_calculator_says_a_written_equation_is_work():
    kit = with_pieces("reply-kit.js")
    call = kit[kit.index('label: "Calculator and equations"') :][:600]
    assert re.search(r"hasWork: \(\) => \[\.\.\.document\.querySelectorAll\('\[data-sheet=\"calculator\"\] math-field'\)\]\.some\(\(f\) => f\.value\?\.trim\(\)\)", call)
