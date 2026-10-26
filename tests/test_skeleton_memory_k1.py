"""K1: a skeleton stands for what the last render drew in its container.

The row count and the shown rows' mean height are kept per container id in
`skeleton-seen` (read through prefs.js), recorded once real rows replace the
skeletons, and capped at what was on screen. A container with no id keeps the
caller's guess. The swap gap was measured by a one-off sweep (owner-1026b K1).
"""

from __future__ import annotations

import re

from tests._app_js import app_js_text


def _show() -> str:
    text = app_js_text()
    return re.search(r"function showSkeletons\(.*?\n}\n\nfunction skeletonRemember.*?\n}\n", text, re.S).group(0)


def test_the_last_render_sets_count_and_height():
    body = _show()
    assert 'prefs.json("skeleton-seen", {})[container.id]' in body
    assert "seen?.[0] || count" in body and "el.style.height = `${seen[1]}px`" in body


def test_it_records_only_what_was_on_screen_and_only_once():
    body = _show()
    assert "getBoundingClientRect().top < innerHeight" in body
    assert "Math.min(shown.length, 30)" in body
    assert "skeletonWatch?.disconnect()" in body and "skeletonWatch.disconnect()" in body
    assert 'prefs.setJSON("skeleton-seen", seen)' in body
