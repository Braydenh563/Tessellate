"""The recorder's name label keeps a gap above the field's focus ring (the owner, 2026-11-22).

Source text: "Voice recorder popup, 'What is this recording?' field: when focused, the label text
and the input's focus ring clash or overlap." The label had no bottom margin, so the 2px ring at
a 2px offset drew 4px into it. Measured (scratchpad/ui-sweeps/recfield1122.js): label to ring
-4px, now 2.4px at 1440 and 10.4px at 390, the same token as the New space dialog's label.
"""

from __future__ import annotations

import re

from tests._css_paths import css_text


def _rule(selector: str) -> str:
    found = re.search(rf"(?:^|\}})\s*(?:/\*.*?\*/\s*)*{re.escape(selector)}\s*\{{([^}}]*)\}}", css_text(), re.S)
    assert found, selector
    return found.group(1)


def test_the_label_has_the_stacked_label_gap():
    assert "margin-bottom: var(--space-2)" in _rule(".meeting-title-label")
    assert "margin-bottom: var(--space-2)" in _rule(".space-dialog label")
