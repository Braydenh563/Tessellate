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


def test_alt_equals_knows_an_editor_box_by_its_id_before_the_adapters_arrive():
    """About 1 s after a fresh note box's first focus, `editorSurfaceKind` is
    null (the library bundle carries the adapters), and Alt+= did nothing."""
    lazy = with_pieces("lazy-entries.js")
    handler = lazy[lazy.index('event.code !== "Equal"') :][:700]
    assert "?? (typeof EDITOR_SURFACES === \"object\" ? EDITOR_SURFACES[box?.id] ?? null : null)" in handler
    editor = with_pieces("math-editor.js")
    opener = editor[editor.index("function openMathEditor(") :][:600]
    #: The insert then writes through the adapter, never into a bare box.
    assert 'ensureModule("library")' in opener and "Promise.all(" in opener
