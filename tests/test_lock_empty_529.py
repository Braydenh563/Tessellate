"""L529, the lock screen driven: an empty Unlock said "Use at least 4
characters.", a rule for choosing a password, on a screen that only asks for
one. An unlock with nothing typed asks for the password; a short one is
wrong without a round trip; only setup states the length rule."""

from __future__ import annotations

import re

from tests._app_js import app_js_text


def _submit() -> str:
    text = app_js_text()
    start = text.index("async function submitLockForm()")
    return text[start : start + 1400]


def test_an_empty_unlock_asks_for_the_password():
    body = _submit()
    assert 'lockFail("Type your password.")' in body
    assert 'lockFail("That password is wrong.")' in body
    assert re.search(r'mode === "setup"[^\n]*\n?[^\n]*Use at least 8 characters', body)
    assert "Use at least ${floor}" not in body
