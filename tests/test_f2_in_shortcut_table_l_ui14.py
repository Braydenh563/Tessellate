"""Source text: the shortcut table and its listener are read as text; the keypress itself is driven in Chromium at merge (no browser in this suite).

L-ui-modernisation-14: F2 (rename the list item you are on) is a row in the
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
    row = JS[JS.index("    renameRow: () => {") :][:300]
    assert "closest(ROW_MENU_HOSTS)" in row and "Rename" in row and ".run()" in row


def test_turning_single_keys_off_leaves_a_named_key_on():
    """Moving F2 into the table put it behind the single-key switch (WCAG
    2.1.4), which is about character keys speech input types; before, F2
    worked with the switch off. A named key (more than one character) stays
    on; a character key ("/", "?") still waits for the switch."""
    start = JS.index("if (!burst && !boardOwns) {")
    loop = JS[start : start + 600]
    assert "(singleKeys || def.keys.length > 1)" in loop
