"""Leaving a presentation puts focus on something you can see (boardfix-1108).

Present frames starts from a menu item, so the element focused at the start is
in a menu that has closed by the time the presentation ends. Focusing it does
nothing and focus fell to `<body>` (Chromium: `BODY#` after Esc, and the next
Tab began at the page's first control). The saved element is used only while it
is on screen; otherwise the canvas takes focus.
"""

from __future__ import annotations

from tests._app_js import frontend_text

SRC = frontend_text("whiteboard.js")


def test_the_saved_focus_must_be_on_screen() -> None:
    start = SRC.index("function wbStopPresenting()")
    block = SRC[start : start + 1400]
    assert "focus.getClientRects().length" in block
    assert "(back ?? container)?.focus" in block or "back.focus" in block
