"""A tab press does not settle style inside the press (INBOX 1534).

Measured at 4x CPU (`scratchpad/ui-sweeps/tabpaint1102.js`): a Chat press ran
13 to 16 style passes, most forced by the composer's focus in `switchTab`,
press to paint 245 to 433ms; with the focus after the first paint, 6 to 9
passes and 117 to 238ms. The accent colour read by the emblem is kept rather
than read from computed style on every draw."""

from __future__ import annotations

import re

from tests._app_js import app_js_text, frontend_text

JS = app_js_text()


def _body(name: str, text: str = JS) -> str:
    start = text.index(f"function {name}(")
    return text[start:text.index("\n}\n", start)]


def test_the_chat_press_focuses_the_composer_after_the_first_paint():
    body = _body("switchTab")
    chat = body[body.index('if (name === "chat")'):body.index('if (name === "dashboard")')]
    focus = chat.index('$("chat-input").focus(')
    held = chat.rfind("requestAnimationFrame(() => setTimeout(", 0, focus)
    assert held != -1, "the composer's focus runs inside the press"
    assert "activeTab" in chat[held:focus], "a press elsewhere in the gap would lose its own focus"


def test_the_accent_colour_is_kept_until_the_root_changes():
    """Intent unchanged (kept, not read on every draw); the means moved from a watcher of
    the root's attributes to a key of the values that set the colour (INBOX 1534)."""
    body = _body("currentAccentHex", frontend_text("settings.js"))
    assert "currentAccentHex.kept" in body and "MutationObserver" not in body
    assert re.search(r"kept\?\.key !== key", body)
    assert '"data-palette", "data-mode", "data-theme", "data-accent"' in body
