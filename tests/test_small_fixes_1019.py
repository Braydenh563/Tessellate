"""Pins for the small layout and access fixes of 2026-10-19 (OPEN 1278, 1435, 408, 1482, 1400, 587).

Each one was measured in Chromium (scratchpad/ui-sweeps/smallfix1019*.js); these keep the
rule that fixed it from being edited away.

Measured (sweeps kept untracked, scratchpad cap): 1435/1278 notes grid scrollWidth vs clientWidth
1412/1408 (1440), 1003/999 (1024), 368/364 (390) before, equal after; quick-links group 368/364
at 390 before, quick-links box 364/364 after.
"""

from __future__ import annotations

import re

from tests._css_paths import CSS_DIR


def _rules(css: str, selector: str) -> list[str]:
    """Bodies of every top-level-or-nested rule whose selector list is exactly `selector`."""
    found = []
    for m in re.finditer(r"(?m)^\s*" + re.escape(selector) + r"\s*\{([^{}]*)\}", css):
        found.append(m.group(1))
    return found


def _consistency() -> str:
    return (CSS_DIR / "08-consistency.css").read_text(encoding="utf-8")


def test_1435_notes_column_does_not_overflow_its_grid() -> None:
    bodies = _rules(_consistency(), "#tab-notes .layout > .tab-main")
    assert any(re.search(r"margin-right:\s*0\b", b) for b in bodies)


def test_1278_quicklinks_strip_does_not_overflow_its_group_on_phones() -> None:
    css = _consistency()
    m = re.search(
        r"@media \(max-width: 599\.98px\) \{\s*#dash-quicklinks \.launch-group > \.launch-row \{([^{}]*)\}",
        css,
    )
    assert m and re.search(r"margin-right:\s*0\b", m.group(1))
