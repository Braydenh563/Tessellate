"""Documents audit 1102 DX22: the slash menu failed axe in both themes.

label-content-name-mismatch on the rows (the name left out the keycap and the
row's two spans ran together as "Heading 1The title") and
scrollable-region-focusable on the list (a combobox pattern, recorded as such).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PICKER = (ROOT / "frontend/js/rich-picker.js").read_text(encoding="utf-8")


def test_a_row_name_starts_with_its_label_and_holds_every_word_it_shows():
    assert '[title.textContent, about, keys].filter(Boolean).join(", ")' in PICKER
    # The visible text must not run words together either.
    assert 'text.append(" ", line);' in PICKER
    assert 'row.append(" ", cap);' in PICKER


def test_the_slash_list_is_recorded_as_a_combobox_pattern():
    axe = (ROOT / "scratchpad/ui-sweeps/axe.js").read_text(encoding="utf-8")
    assert "'scrollable-region-focusable|#editor-menu-list'" in axe
    editor = (ROOT / "frontend/js/editor.js").read_text(encoding="utf-8")
    assert 'box.setAttribute("aria-controls", "editor-menu-list");' in editor
    assert 'box.setAttribute("aria-haspopup", "listbox");' in editor
