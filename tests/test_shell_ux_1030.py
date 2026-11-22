"""Audit 1028 S26: the search-by-meaning question stays up until answered, so
on a phone it is the small toast (178px tall over the Ask box's own button at
390x667 and 360x640, 152px after), not the body-size one."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_semantic_question_toast_is_small_on_a_phone():
    #: In the lazy sheet semantic-notice.js loads, not the boot CSS (one byte over its budget).
    #: Keyed on the body class settings.js sets while open, not body:has() (test_css_body_has).
    css = (ROOT / "frontend" / "css" / "semantic-notice-lazy.css").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    assert '"/css/semantic-notice-lazy.css", "/js/semantic-notice.js"' in app
    phone = re.search(r"@media \(max-width: 599\.98px\) \{\s*\.toast\.semantic-install-toast \{([^}]*)\}", css)
    assert phone, "the phone rule for the persistent question toast is gone"
    assert "font-size: var(--text-sm)" in phone.group(1) and "--toast-line: 1.25rem" in phone.group(1)


def test_the_semantic_question_steps_aside_while_settings_is_open_on_a_phone():
    #: L-world-class-394: 341x173px over the lower quarter of every Settings
    #: section at 360x740; Settings, Search and index holds the same switch.
    #: Keyed on the body class settings.js sets while open, not body:has() (test_css_body_has).
    css = (ROOT / "frontend" / "css" / "semantic-notice-lazy.css").read_text(encoding="utf-8")
    assert re.search(
        r"@media \(max-width: 599\.98px\) \{[^@]*body\.settings-open \.toast\.semantic-install-toast \{\s*display: none;",
        css,
    )
