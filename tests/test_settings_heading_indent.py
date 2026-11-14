"""Settings has one heading indent (L-world-class-84).

Measured 2026-11-14 at 1440px over every pane (Playwright, getBoundingClientRect):
a pane's title in its dock sat 11px in from the pane edge (9.6px padding and a
1px border) while every group heading under it sat 17px in (1rem padding and
the group's 1px border). The title now takes the group's own 1rem inset.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "frontend" / "css" / "04-chat-dock-appearance.css").read_text(encoding="utf-8")


def _padding(selector: str) -> str:
    body = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert body, selector
    found = re.search(r"padding(?:-inline)?:\s*([^;]+);", body.group(1))
    assert found, selector
    return found.group(1).split()[-1] if "padding-inline" in body.group(1) else found.group(1).split()[1]


def test_a_pane_title_is_inset_as_far_as_the_groups_under_it():
    group = _padding(".settings-group")
    title = _padding(".settings-section > .dock")
    assert group == title == "1rem"
