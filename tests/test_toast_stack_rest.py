"""Stacked notifications: one card at rest, the rest counted (INBOX 1300 C33).

The owner: "stacking notifications need to be cleaned up and not as intrusive
and obscuring". Four toasts stood 186x205 px. Now the newest shows, the ones
behind it hide until a pointer or the keyboard is on the stack, and the
"+N more" card counts everything not shown. Measured by
`scratchpad/ui-sweeps/toast1300.js` (in git at d4dbd2f).
"""

from __future__ import annotations

import re

from tests._app_js import JS_DIR
from tests._css_paths import CSS_DIR

STATUS = (JS_DIR / "status.js").read_text(encoding="utf-8")
FORMS = (CSS_DIR / "01-forms-settings.css").read_text(encoding="utf-8")


def _layout() -> str:
    return STATUS.split("function toastLayout", 1)[1].split("\nfunction ", 1)[0]


def test_the_cards_behind_the_newest_are_marked():
    body = _layout()
    assert "live.slice(1, TOAST_VISIBLE)" in body
    assert 'classList.toggle("is-behind"' in body


def test_the_more_card_counts_both_ways():
    body = _layout()
    assert "toast-more-rest" in body and "toast-more-folded" in body
    assert "folded.length + behind.length" in body


def test_at_rest_only_the_newest_shows_and_the_stack_opens_on_hover_or_focus():
    assert re.search(r":not\(:hover, :focus-within\)\s*>\s*\.toast\.is-behind\s*\{\s*display:\s*none", FORMS)
    assert ":is(:hover, :focus-within) .toast-more-rest" in FORMS
    assert ":not(:hover, :focus-within) .toast-more-folded" in FORMS
