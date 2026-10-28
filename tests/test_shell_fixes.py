"""App-shell audit 1028 fixes (S1, S4 to S10): source-level guards.

The behaviour was measured in the running app (see the commit messages); these
keep the wiring from being removed.
"""

from tests._app_js import app_js_text


def test_flash_entry_renders_through_the_target():
    js = app_js_text()
    assert "let pendingJumpId = null;" in js
    assert "pendingJumpId = id;" in js
    assert "Note not found." in js
