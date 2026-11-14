"""The owner, 2026-10-10: "text gets cut off on the note sidebar in the
whiteboard". The board sidebar's note row was the title and body run
together and line-clamped on the padded row itself; a clamp paints the next
line on into the bottom padding, so a sliced third line showed under every
long row (`scratchpad/ui-sweeps/wbnoterows.js`: every row "clamp over
padding 8px" at 1440 and 1024 on base, 6/6 after). Now a name over one quiet
line, each ellipsised by the stylesheet."""

from tests._app_js import frontend_text
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WB = frontend_text("whiteboard.js")
CSS = (ROOT / "frontend" / "css" / "06-timeline-dialogs.css").read_text(encoding="utf-8")
LAZY = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert m, selector
    return m.group(1)


def test_the_row_is_a_name_over_one_quiet_line():
    assert 'title.className = "wb-library-item-title"' in WB
    assert 'more.className = "wb-library-item-preview"' in WB


def test_no_clamp_on_the_padded_row():
    row = _rule(".wb-library-item")
    assert "line-clamp" not in row
    both = LAZY[LAZY.index(".wb-library-item-title,\n.wb-library-item-preview {"):]
    both = both[:both.index("}")]
    assert "text-overflow: ellipsis" in both and "white-space: nowrap" in both
