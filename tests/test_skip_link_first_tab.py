"""INBOX 1326: the first Tab after the app loads lands on "Skip to content".

Removing the boot splash or hiding the lock screen left the browser's
sequential-focus starting point mid-page, so Tab went to the Local chip.
Measured in Chromium: Tab 1 was #privacy-chip before, #skip-link after.
"""

from tests._app_js import app_js_text

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_skip_link_is_the_first_thing_in_the_body():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    body = html[html.index("<body"):]
    first_focusable = min(i for i in (body.find("<a "), body.find("<button"), body.find("<input")) if i >= 0)
    assert 'id="skip-link"' in body[first_focusable:first_focusable + 80]


def test_splash_and_lock_both_put_tab_back_at_the_top():
    js = app_js_text()
    assert "function tabFromTop()" in js
    assert "seen.disconnect();\n  tabFromTop();" in js
    assert 'if ($("lock-overlay").classList.contains("hidden")) tabFromTop();' in js
