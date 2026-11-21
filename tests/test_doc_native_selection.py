"""The document editor draws its own selection only while it must (L342).

`drawSelection` cost 7 to 12 ms of main thread a key in a 20,000 word
document at 4x CPU (bisected by extension, LEDGER L342): its layers are
measured and redrawn on every key. With one range and the focus in the
editor the browser's own caret and selection look the same (one colour for
both, `docCmTheme`), so the drawn ones are a compartment that holds
`drawSelection` only for several ranges (Alt+drag, Ctrl+click) or a
selection kept while the focus is elsewhere (the find bar's matches).
"""

from __future__ import annotations

import re

from tests._app_js import documents_text

DOCS = documents_text()


def _extensions() -> str:
    start = DOCS.index("function docCmExtensions(CM) {")
    return DOCS[start : DOCS.index("\nfunction ", start + 10)]


def test_draw_selection_is_a_compartment_not_always_on():
    ext = _extensions()
    assert "docCmParts.select = new CM.state.Compartment();" in ext
    assert "docCmParts.select.of([])" in ext, "the editor starts on the native caret and selection"
    assert not re.search(r"^\s*CM\.view\.drawSelection\(\),", ext, re.M), "drawSelection is always on again"


def test_it_draws_for_several_ranges_or_a_selection_kept_without_focus():
    ext = _extensions()
    want = re.search(r"const drawWanted = \(sel, focused\) => ([^;]+);", ext)
    assert want, "the rule for when the selection is drawn"
    assert "sel.ranges.length > 1" in want.group(1) and "!focused && !sel.main.empty" in want.group(1)
    # A transaction that changes the range count, and a focus change, both re-decide.
    assert "CM.state.EditorState.transactionExtender.of(" in ext
    assert "CM.view.EditorView.focusChangeEffect.of(" in ext


def test_the_native_caret_and_selection_use_the_drawn_colours():
    theme = DOCS[DOCS.index("function docCmTheme(") :]
    assert 'caretColor: "var(--text)"' in theme and '".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--text)" }' in theme
    # The focused drawn rule out-ranks the library's fixed lavender, so a
    # multi-range selection and the native one share the accent colour.
    assert '"&.cm-editor.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection": {' in theme
