"""A focus the app gives back after a redraw is not a person's press (BACKLOG 1682).

The "held answers" E2E specs flaked under load: a change poll redrew the list,
the edit form's tags field lost the keyboard with its row and `restoreFocusTo`
gave it back (a focus with no relatedTarget); that focus cleared the field's "a tag was just entered" flag and
opened the tag list over Save changes. Only a press, a key or a focus the
person caused may open it.
"""

from __future__ import annotations

from tests._app_js import app_js_text


def test_the_tagged_flag_survives_a_focus_from_nowhere():
    js = app_js_text()
    # The edit form's "tag just entered" flag is cleared by a press or a focus
    # that comes from another control, not by the app giving the keyboard back
    # (no relatedTarget); the list (tag-suggest.js) stays shut while the flag
    # stands with nothing typed.
    assert '(e.type === "focus" && !e.relatedTarget) || delete tagEntry.dataset.tagged' in js
