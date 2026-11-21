"""A pinned topic's dashed box never dashes its Edge bar (INBOX 569, the
owner: "it says the edge bar is solid even though it is dashed").

`.wb-map-pinned { border-style: dashed }` came later in the file than the
bar's own `border-left: 4px solid` and at the same weight, so a dragged
topic's Solid bar drew dashed while the Shape menu said Solid. The pixels are
checked by `scratchpad/ui-sweeps/mmdoc1005-spinebar.js` (every Box by Edge bar
combination in three layouts); this pins the cascade that fixes it.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = "".join(  # L-ui-modernisation-31: Library-only rules live in library-lazy.css
    (Path(__file__).resolve().parents[1] / "frontend" / "css" / n).read_text(encoding="utf-8")
    for n in ("07-whiteboard-misc.css", "library-lazy.css")
)
CSS = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)


def _at(selector: str) -> int:
    at = CSS.find(selector)
    assert at != -1, selector
    return at


def test_the_solid_bar_is_restored_after_the_pin_dash():
    pin = _at(".wb-map-pinned {")
    bar = _at(".wb-map-node.wb-map-pinned:not([data-spine]):not(.wb-map-node-mirrored) {")
    assert bar > pin
    body = CSS[bar:CSS.index("}", bar)]
    assert "border-left-style: solid" in body


def test_the_hairline_sides_take_the_dash_in_the_other_layouts():
    rule = _at(".wb-map-down .wb-map-node.wb-map-pinned:not([data-shape=\"none\"])")
    # Later than the bar rules it has to outrank on the left edge.
    assert rule > _at(".wb-map-down .wb-map-node[data-spine=\"dashed\"]")
    assert rule > _at(".wb-map-node-mirrored[data-spine=\"dashed\"]")
    assert "border-left-style: dashed" in CSS[rule:CSS.index("}", rule)]
