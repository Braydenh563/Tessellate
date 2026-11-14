"""INBOX 1661, the owner 2026-11-08 (screenshot: the diagram's "Add a block" sheet, each name drawn over the hint
of the row above): "these rows clash with each other and dont have appropriate heights ro spacing". A sheet list
is a scrolling flex column, so a long list shrank its rows below their content; a row keeps its own height."""

from __future__ import annotations

import re
from tests._css_paths import FORMER_10, sheets

CSS = sheets(*FORMER_10)


def test_a_sheet_lists_rows_never_shrink_below_their_content() -> None:
    rule = re.search(r"\.sheet-list > \* \{([^}]*)\}", CSS)
    assert rule and "flex-shrink: 0" in rule.group(1), "a long sheet list squeezes its rows into each other"
