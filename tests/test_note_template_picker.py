"""The Capture box's template picker confirms before it fills (INBOX 410).

The owner, 2026-09-24, deciding it: the Capture box's note templates get the
same confirm step as New from a template in Documents. The picker was a native
`<select>` whose `change` filled the box the moment a name was touched, so
arrowing through the list to read the names rewrote the note once per name.
Now it is the recipe DESIGN.md's index names for "a dialog of choices that each
make something": radio rows, a preview drawn by the function that fills, and
one filled button (Use this template) that makes it. Measured in Chromium by
`scratchpad/ui-sweeps/notetemplatepick.js`.
"""

from __future__ import annotations

import re
from pathlib import Path
from tests._app_js import app_js_text
from tests._app_js import index_html_text

ROOT = Path(__file__).resolve().parents[1]
APP = app_js_text()
HTML = index_html_text()


def _body(name: str) -> str:
    start = APP.index(f"function {name}(")
    return APP[start : APP.index("\n}\n", start)]


def test_the_picker_is_a_button_that_opens_a_dialog_not_a_select() -> None:
    assert not re.search(r'<select id="entry-template"', HTML)
    opener = re.search(r'<button id="entry-template"[^>]*>', HTML)
    assert opener and 'aria-haspopup="dialog"' in opener.group(0)
    assert '$("entry-template").addEventListener("change"' not in APP


def test_the_dialog_is_the_template_recipe() -> None:
    dialog = re.search(r'<dialog id="note-template-dialog"[^>]*>(.*?)</dialog>', HTML, re.S)
    assert dialog, "the picker's dialog is missing"
    body = dialog.group(0)
    assert "doc-template-dialog" in body and "doc-template-body" in body
    assert re.search(r'id="note-template-list"[^>]*role="radiogroup"', body)
    pane = re.search(r'<div id="note-template-preview"[^>]*>', body)
    assert pane and 'aria-hidden="true"' in pane.group(0) and "inert" in pane.group(0)
    assert 'id="note-template-use"' in body and "Use this template" in body
    assert "Cancel" in body


def test_choosing_is_not_making() -> None:
    """A click chooses and previews; only Use, Enter or a double click fills."""
    choose = _body("chooseNoteTemplate")
    assert "entry-content" not in choose and "aria-checked" in choose
    assert "showNoteTemplatePreview(" in choose
    use = _body("useNoteTemplate")
    #: The fill and the preview read one function (`noteTemplateText`); the
    #: fill adds the clipboard and the caret (WORLD_CLASS_PLAN 5 item 4).
    assert "noteTemplateForUse(" in use and "entry-content" in use
    assert "noteTemplateText(" in _body("noteTemplateFill") and "noteTemplateText(" in _body("noteTemplateForUse")
    opener = _body("openNoteTemplateDialog")
    assert 'addEventListener("dblclick", useNoteTemplate)' in opener
    assert 'addEventListener("click", () => chooseNoteTemplate(' in opener


def test_the_preview_is_the_text_the_button_would_write() -> None:
    preview = _body("showNoteTemplatePreview")
    assert "noteTemplateFill(template)" in preview


def test_what_is_typed_is_never_silently_replaced() -> None:
    assert "confirmDialog(" in _body("useNoteTemplate")
