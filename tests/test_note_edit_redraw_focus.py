"""A list redraw keeps the edit form's caret (notes.spec.js:61 on CI, #224).

Filing's refresh just after a capture redrew the list with the edit form open; the form was rebuilt
and the caret in it went with the old one, so nothing was focused and the editor never mounted.
The redraw hands the caret to the new form (`focusBodyAfterRender`, or the tag field's flag).
Driven in scratchpad/ui-sweeps/note-edit-rerender.js (5 of 5 lost the caret before, 0 after).
"""

import re

from tests._app_js import app_js_text

JS = app_js_text()


def _render_entries() -> str:
    start = JS.index("function renderEntries(appendOnly = false) {")
    return JS[start : JS.index("const keep = grown ? null : resetNoteList(list);", start)]


def test_a_redraw_with_the_form_focused_gives_the_new_form_the_caret():
    body = _render_entries()
    assert "const held = document.activeElement;" in body
    assert re.search(r'held\?\.closest\?\.\(`#entry-list > li\[data-id="\$\{editingId\}"\]`\)', body)
    assert "focusBodyAfterRender = editingId;" in body
    assert 'held.matches(".note-edit-tag-input")) focusTagsAfterRender = editingId;' in body


def test_an_append_only_draw_leaves_the_caret_alone():
    # A grown list keeps its rows (and the form), so it must not re-aim the caret.
    assert "if (!grown && editingId !== null" in _render_entries()
