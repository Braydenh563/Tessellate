"""Settings, Keyboard shortcuts: the key chip shows it changes the shortcut.

INBOX 1300 C22, the owner: "It's hard to figure out that you need to press the
shortcut command itself to change it in the settings page". The chip keeps
being the button (INBOX 810, `test_a_shortcuts_keys_are_its_rebind_button`);
a pencil after the keys says so, an x while it waits for keys, and the help
lines name it. Measured by `scratchpad/ui-sweeps/shortcut1300.js` (in git at d4dbd2f).
"""

from __future__ import annotations

from tests._app_js import JS_DIR
from tests._css_paths import CSS_DIR

ROOT = JS_DIR.parents[1]


def test_the_chip_carries_a_pencil_and_an_x_while_capturing():
    js = (JS_DIR / "reveal-targets.js").read_text(encoding="utf-8")
    body = js.split("function buildShortcutList", 1)[1].split("\nfunction ", 1)[0]
    assert '`ph ${capturing ? "ph-x" : "ph-pencil-simple"} shortcut-edit`' in body
    assert "change.append(combo, pen)" in body


def test_the_pencil_is_quiet_until_aimed_at():
    css = (CSS_DIR / "05-sidebars-themes.css").read_text(encoding="utf-8")
    assert ".shortcut-list .shortcut-edit {" in css
    assert ".shortcut-list .shortcut-key:is(:hover, :focus-visible) .shortcut-edit" in css


def test_the_help_lines_name_the_pencil():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert html.count("Press a shortcut's keys, marked with a pencil") == 2
    guide = (ROOT / "src" / "tessellate" / "ai" / "help_chat.py").read_text(encoding="utf-8")
    assert "marked with a pencil" in guide
