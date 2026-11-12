"""L-documents-15: the diagram builder at 390 (R11 blind test).

Re-measured 2026-11-12 on the served app (390 x 844 touch, a four-block flowchart in a document):
the dialog's dock is there 152 to 257 ms after the tap and the picture 233 to 261 ms (the R11 report said
about 1 s); five Tab stops reach the first block in the list sheet (it said 27); a tap on a block moved
neither the dock (top 129 before and after) nor the page; every target in the dialog and the list sheet
(kind button, shelf, grips, swatches, Connect, tabs) is 44 px or more except the join handles, whose 44 px
hit area is their `::after` (24 x 44 drawn), and the zoom readout, which was 42 x 54 and is now 44 wide
on a touch screen (this file's one rule).
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def test_the_zoom_readout_is_44_px_wide_on_a_touch_screen() -> None:
    rule = re.search(r"@media \(pointer: coarse\) \{\s*\.dgm-zoom \.dgm-zoom-level \.value-field-input \{([^}]*)\}", CSS)
    assert rule and "min-inline-size: 2.75rem" in rule.group(1)


def test_a_join_handle_keeps_its_44_px_hit_area() -> None:
    coarse = CSS[CSS.index("@media (pointer: coarse) {\n  .dgm-handle {") :]
    assert "inline-size: 44px" in coarse[:200]
    assert re.search(r"\.dgm-handle::after \{\s*inset: -12px;", coarse)
