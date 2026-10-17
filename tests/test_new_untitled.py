"""INBOX 904 B17: a new document, board or map is named for you, the name selected.

The owner: "when making new documents I shouldn't have to enter a title, it
should fill it with Untitled ... and then have it preselected and highlighted
for the user to replace it". The names themselves (INBOX 739) and the selected
title on a new document and on the quick New board were already there; what
was left is the template gallery's name field (a bare placeholder, so nothing
to replace) and the selection popup that opened over every preselected title.
Browser check: `scratchpad/ui-sweeps/newuntitled.js`.
"""

from __future__ import annotations

import re

from tests._app_js import with_pieces


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start)]


def test_a_whole_title_selected_for_replacing_draws_no_selection_popup():
    body = _function(with_pieces("selection.js"), "fieldSelection")
    assert re.search(r'el\.tagName === "INPUT"[^\n]*selectionStart === 0[^\n]*selectionEnd === el\.value\.length', body)


def test_the_template_gallery_prefills_and_selects_the_default_name():
    source = with_pieces("whiteboard-templates.js")
    gallery = source[source.index("async function wbOpenTemplateGallery("):]
    assert 'nameField.value = choice.ref ? choice.name : untitled[kind === "map" ? "map" : "board"]' in gallery
    assert re.search(r"nameField\.focus\(\);\s*nameField\.select\(\);", gallery)
