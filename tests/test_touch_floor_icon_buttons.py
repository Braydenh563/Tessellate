"""The icon-only buttons that stood under 44px at 1024x768 touch (iconfloor.js: 51 of 188).

Each takes the floor through `--target-min` (28px for a mouse, 44px under a coarse pointer or below
820), written as `max(<its own size>, var(--target-min))` so the desktop size is untouched:
the header's squares (notifications, theme, settings, lock), the Local chip, the capture bar's icons and
the board menu's caret. The sweep measures it; these hold the rule where a sweep is not run.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "frontend" / "css"


def _rule(file: str, selector: str) -> str:
    text = (CSS / file).read_text(encoding="utf-8")
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", text)
    assert match, f"{selector} not in {file}"
    return match.group(1)


def test_the_header_squares_are_as_wide_as_the_touch_floor():
    body = _rule("05-sidebars-themes.css", "#top-bar :is(.header-cluster, .notif-wrap) > button.icon-only")
    assert "width: max(var(--header-control-h), var(--target-min));" in body
    assert "min-width: max(var(--header-control-h), var(--target-min));" in body


def test_the_local_chip_takes_the_touch_floor_wide_and_tall():
    text = (CSS / "06-timeline-dialogs.css").read_text(encoding="utf-8")
    assert "min-height: var(--target-min);" in _rule("06-timeline-dialogs.css", "#top-bar .header-cluster > .privacy-chip")
    assert "width: max(var(--header-control-h), var(--target-min));" in text


def test_the_capture_bar_row_takes_the_touch_floor_under_a_finger():
    text = (CSS / "08-consistency.css").read_text(encoding="utf-8")
    block = re.search(
        r"@media \(max-width: 819\.98px\), \(pointer: coarse\) \{\s*\.capture-bar-row :is\(\.capture-bar-input, \.capture-bar-icon\) \{([^}]*)\}",
        text,
    )
    assert block and "min-height: max(var(--control-h-body), var(--target-min));" in block.group(1)


def test_the_split_buttons_caret_takes_the_touch_floor():
    #: The selector heads two rules (the shared height, then the width): the width is in the second.
    text = (CSS / "library-lazy.css").read_text(encoding="utf-8")
    assert re.search(r"\.split-button \.split-button-caret \{[^}]*width: max\(calc\(var\(--control-h\) - 4px\), var\(--target-min\)\);", text)
