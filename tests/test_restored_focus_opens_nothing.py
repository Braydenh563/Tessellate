"""A focus the app gives back after a redraw is not a person's press (BACKLOG 1682).

The behaviour is pinned end to end by the "redraw of the list" spec in
tests-e2e/specs/notes.spec.js (it runs the app's own redraw). This pins the
wiring the spec relies on: `restoreFocusTo` raises `restoreFocusTo.giving` around its
focus and gives focus at once, and the tags field reads that flag, not a
missing relatedTarget (which a Tab in from the page also has).
"""

from __future__ import annotations

import re

from tests._app_js import app_js_text


def test_restore_focus_flags_its_focus_and_gives_it_at_once():
    js = app_js_text()
    body = js[js.index("function restoreFocusTo(target)"):]
    body = body[: body.index("\n//: The control of a note")]
    assert re.search(r"(?s)restoreFocusTo\.giving\s*=\s*true;.*el\.focus\(.*restoreFocusTo\.giving\s*=\s*false", body)
    assert re.search(r"\n\s*give\(\);[^\n]*\n\s*requestAnimationFrame\(give\)", body)


def test_the_tags_field_reads_the_flag_not_a_missing_related_target():
    js = app_js_text()
    handler = js[js.index("The app giving focus back"):]
    handler = handler[:handler.index("function drawTagChips")]
    assert "restoreFocusTo.giving" in handler
    assert "relatedTarget" not in handler
