"""The owner, 2026-11-07 (INBOX 1692 j): hanging, the size handle sits at the bottom right, so its cursor is the
top-left to bottom-right arrow, not the standing handle's bottom-left to top-right one."""

from __future__ import annotations

import re
from tests._css_paths import sheets

CSS = sheets("07-whiteboard-misc.css", "characters-lazy.css")


def _rule(selector: str) -> str:
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert m, selector
    return m.group(1)


def test_the_hanging_handle_at_the_bottom_right_points_its_own_diagonal():
    hang = _rule('#nm-buddy[data-pose="hang"] .nmb-size-grip')
    assert "bottom:" in hang and "cursor: nwse-resize" in hang
    # The handle at the top right everywhere else keeps the other diagonal.
    assert "cursor: nesw-resize" in _rule("#nm-buddy .nmb-size-grip")
