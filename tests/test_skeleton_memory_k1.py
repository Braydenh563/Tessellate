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
    return re.search(r"function showSkeletons\(.*?\nfunction clearSkeletons.*?\n}\n", text, re.S).group(0)


def test_the_last_render_sets_count_and_height():
    body = _show()
    assert 'prefs.json("skeleton-seen", {})[container.id]' in body
    assert "seen?.[0] || count" in body and "el.style.height = `${seen[1]}px`" in body


def test_it_records_only_what_was_on_screen_and_only_once():
    body = _show()
    assert "getBoundingClientRect().top < innerHeight" in body
    assert "Math.min(shown.length, 30)" in body
    assert 'prefs.setJSON("skeleton-seen", seen)' in body


def test_it_records_after_the_swap_without_a_new_wake_source():
    body = _show()
    assert "queueMicrotask(() => skeletonRemember(container))" in body
    assert "MutationObserver" not in body and "requestAnimationFrame" not in body


def test_skeletons_cover_the_span_the_rows_did():
    body = _show()
    assert "seen?.[2]" in body and "seen[container.id] = [n, height, Math.round(span)]" in body
    assert "if (drawn > 0)" in body
