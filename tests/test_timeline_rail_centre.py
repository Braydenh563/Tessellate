"""The feed's spine runs through the middle of every kind mark.

The owner, 2026-10-10: "the circle on the vertical line on the left isnt in
line with the text line". Measured 2026-11-02 on a seeded 48-note fixture
(a snippet under every title) at 1440 and 390: the mark's centre sits on the
title's first line (0px), and the spine was 1px left of the mark's centre
(its left edge at the row's padding plus half a mark, while the row also has a
1px transparent border and the spine is 1px wide). The rule has to count both.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "frontend" / "css" / "06-timeline-dialogs.css").read_text(encoding="utf-8")


def _block(selector: str) -> str:
    match = re.search(re.escape(selector) + r" \{([^}]*)\}", CSS)
    assert match, selector
    return match.group(1)


def test_the_spine_is_centred_on_the_marks_by_the_rows_border_and_its_own_width() -> None:
    row = _block(".timeline-feed .timeline-row")
    assert re.search(r"border:\s*1px solid transparent", row)
    spine = _block(".timeline-rows::before")
    assert re.search(r"width:\s*1px", spine)
    left = re.search(r"left:\s*calc\(([^;]*)\);", spine)
    assert left, "the spine's left is a calc"
    #: row padding + row border + half a mark - half the spine's own width
    assert left.group(1) == "var(--space-3) + 1px + (var(--timeline-mark) / 2) - 0.5px"
