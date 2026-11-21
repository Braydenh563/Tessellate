"""The skip-link observer in phone-shell.js must not run before the page has
finished parsing: `tabFromTop` calls `afterFrames` (dashboard.js, loaded
later), and a body mutation during parse with the splash already gone threw
"afterFrames is not defined" on 2 of 6 fresh boots (measured 2026-11-21)."""

import re

from tests._app_js import app_js_text


def test_the_tab_from_top_observer_waits_for_the_parse_to_finish():
    js = app_js_text()
    m = re.search(r"new MutationObserver\(\(_, seen\) => \{(.*?)\}\)\.observe\(document\.body", js, re.S)
    assert m, "the tabFromTop observer moved"
    body = m.group(1)
    guard = body.index('document.readyState === "loading"')
    assert guard < body.index("seen.disconnect()") < body.index("tabFromTop()")
