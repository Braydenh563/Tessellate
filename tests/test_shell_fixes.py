"""App-shell audit 1028 fixes (S1, S4 to S10): source-level guards.

The behaviour was measured in the running app (see the commit messages); these
keep the wiring from being removed.
"""

from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parent.parent


def test_flash_entry_renders_through_the_target():
    js = app_js_text()
    assert "let pendingJumpId = null;" in js
    assert "pendingJumpId = id;" in js
    assert "No such note." in js


def test_lock_screen_is_a_dialog_that_takes_focus():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    card = html[html.index('id="lock-card"') - 40 : html.index('id="lock-card"') + 120]
    assert 'role="dialog"' in card and 'aria-modal="true"' in card
    assert 'aria-labelledby="lock-title"' in card
    js = app_js_text()
    assert "lockReturn ||= document.activeElement;" in js
    assert "lockReturn = lockReturn?.focus()" in js


def test_ask_controls_wrap_on_a_phone():
    css = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    rule = css[css.index("\n.ask-controls {") :].split("}", 1)[0]
    assert "flex-wrap: wrap;" in rule
