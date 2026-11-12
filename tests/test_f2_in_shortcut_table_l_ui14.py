"""L-ui-modernisation-14: F2 (rename the list item you are on) is a row in the
shortcut table, not a loose listener in navigation.js, so the shortcuts sheet,
the rebinding list and the collision check all see it."""

from tests._app_js import app_js_text

JS = app_js_text()


def test_f2_is_declared_in_the_table():
    start = JS.index("const DEFAULT_SHORTCUTS")
    table = JS[start : JS.index("\n};", start)]
    assert 'renameRow: { keys: "F2"' in table


def test_the_loose_f2_listener_is_gone():
    assert 'event.key !== "F2"' not in JS
    assert "renameRow: renameFocusedRow" in JS
