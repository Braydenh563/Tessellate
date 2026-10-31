"""Audit 1031 perf class rows (ranked 16 to 55): each test names the cost it keeps out."""

from tests._app_js import frontend_text


def _between(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i)]


def test_focus_settles_the_keyboard_inset_only_where_a_keyboard_can_cover_the_page():
    # Four `innerHeight` reads per focus were a forced layout of the whole page each
    # (1.2 s at 4x with the companion out) in a window that has no on-screen keyboard.
    js = frontend_text("phone-shell.js")
    body = _between(js, "function initKeyboardInset() {", "document.addEventListener(\"focusin\"")
    assert '(any-pointer: coarse)' in body
    assert "touchy.matches &&" in body.split("const settle")[1]


def test_the_rail_spy_ignores_scrollers_that_do_not_hold_the_list():
    # The capture box's own scroller woke a pick (a rect per visible card) per key.
    js = frontend_text("notes-rail-spy.js")
    block = _between(js, "document.addEventListener(\"scroll\"", "list.addEventListener(\"focusin\"")
    assert "target.contains?.(list)" in block
