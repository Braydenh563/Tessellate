"""The graph note popup's rows never overlap (INBOX 1769).

The head, the Save row and the dock sat in a column flex box as shrinkable
items. Past the popup's max-height the Save row (min-height 0) squeezed to its
19px status line while the 32px button kept its height, so Save stood 6px up
over the body's last line and the textarea looked cut off by it. Measured at
1440x900 before: body bottom 752.9, Save top 746.5; after: both 752.9.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "frontend" / "css" / "graph-lazy.css").read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert match, selector
    return match.group(1)


def test_head_save_row_and_dock_do_not_shrink():
    block = re.search(
        r"#graph-popup > \.graph-popup-head,\s*#graph-popup > \.graph-popup-saverow,\s*#graph-popup > \.graph-popup-actions\s*\{([^}]*)\}",
        CSS,
    )
    assert block and "flex: none" in block.group(1)


def test_the_body_is_the_one_scroller_and_clears_the_rows_around_it():
    body = _rule(".graph-popup-body")
    assert "overflow-y: auto" in body
    assert "min-height: 0" in body
    assert "padding-block: var(--space-2)" in body
    assert "mask-image" in body
