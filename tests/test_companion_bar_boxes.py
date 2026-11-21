"""The companion's kept control boxes go stale when a window bar's control
changes size (L-general-44).

perchall failed 3 of 6 runs with the companion on the status bar at
1044,791, over #status-agent and #status-guide. Those buttons are empty,
0 by 0, until status.js fills them, and the boxes kept in `nmb.covers` were
dropped only by a change inside a `.tab-page`: a sweep taken before the fill
kept the bar without them for up to `NMB_COVERS_MAX_MS`, so a perch over them
scored clear. The bars' controls are watched for a size change instead (a
text update that keeps the size costs no new sweep).
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
AV = unwrapped((ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8"))


def test_the_bars_the_boxes_read_are_the_bars_watched_for_a_size_change() -> None:
    read = re.search(r"function nameMarkBuddyControlBoxes\(tab\) \{.*?\n  \}", AV, re.S).group(0)
    bars = re.search(r"for \(const id of \[`tab-\$\{tab\}`, ([^\]]+)\]\)", read).group(1)
    bar_ids = re.findall(r'"([a-z-]+)"', bars)
    assert {"top-bar", "status-bar"} <= set(bar_ids)
    start = AV.index("const barSizes = new ResizeObserver(")
    block = AV[start : AV.index("\n  }\n", start)]
    assert "nmb.covers = null" in block
    # Every element, not only the controls the sweep keeps a box for: a control
    # moved by a word beside it growing keeps its own size (#status-nav-history).
    assert 'bar.querySelectorAll("*")' in block
    for bar in bar_ids:
        assert f'"{bar}"' in block, bar


def test_a_bar_change_does_not_count_as_a_view_change() -> None:
    """Only the boxes are dropped: the companion is not sent to a new place
    because a status word changed."""
    start = AV.index("const barSizes = new ResizeObserver(")
    callback = AV[start : AV.index("});", start)]
    assert "nameMarkBuddyViewChanged" not in callback
    assert "nameMarkBuddyIndexReset" not in callback
