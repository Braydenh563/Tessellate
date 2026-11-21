"""Source text: part of this reads the shipped CSS, markup or script, whose effect needs a browser this suite does not run; what was measured in the app is below.

A category header in the Map and Tessellation views starts clear of the minimap and zoom strip.

Seen in L-graph-12's side-by-side sweep (`scratchpad/ui-sweeps/tess-pair.js`):
the fitted Tessellation's top-left header, "Uncategorised (103)", was drawn
under the minimap. The fit leaves that corner furniture alone (INBOX 802), so
the header moves instead: it starts past any overlay on its band, with the
room left, and shows no text (the rectangle's tooltip names it) if none is.
"""

from __future__ import annotations

from pathlib import Path

from tests._js_scope import unwrapped

CANVAS = unwrapped((Path(__file__).resolve().parent.parent / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8"))


def test_the_header_starts_past_an_overlay_on_its_band() -> None:
    draw = CANVAS[CANVAS.index("function gcDrawTreemap(") :]
    draw = draw[: draw.index("\n}\n")]
    assert "const overlays = gcOverlayBoxes(s, s.transform || d3.zoomIdentity);" in draw
    assert "box.bottom > y && box.top < y + head / k && box.left <= start && box.right > start" in draw
    assert "room > 0 ? gcTess.fit(measure, rect.category, rect.count, room * k, lines * 15) : null" in draw
    assert "ctx.fillText(line, start," in draw
    # The minimap is among the overlays a drawn name keeps out from under.
    boxes = CANVAS[CANVAS.index("function gcOverlayBoxes(") :]
    assert '"#graph-minimap", "#graph-zoom"' in boxes[: boxes.index("\n}\n")]
