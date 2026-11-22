"""L263: the converted draw.io stencils draw their lines as wide as draw.io does. A stencil's `strokewidth="inherit"`
takes the cell's strokeWidth, 1 by default; the .drawio import makes a board width of twice draw.io's
(`whiteboard-interchange.js`, `strokeWidth * 2`), so an inherit stencil carries width 2 and the library's shape and the same
shape read from a .drawio file match. A stencil with a fixed strokewidth keeps its own (twice it, at least 2)."""

from __future__ import annotations

import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_inherit_stencils_are_drawio_default_width_on_the_import_scale() -> None:
    src = (ROOT / "frontend" / "js" / "whiteboard-interchange.js").read_text(encoding="utf-8")
    assert "look.width = Math.max(1, Math.round((Number(s.strokeWidth) || 1) * 2));" in src
    widths = collections.Counter()
    for f in sorted((ROOT / "frontend" / "board-library" / "drawio").glob("*.json")):
        for item in json.loads(f.read_text(encoding="utf-8"))["items"]:
            for part in item["payload"]["items"]:
                widths[float(part["data"].get("width", 0))] += 1
    total = sum(widths.values())
    assert total > 500 and widths[2.0] / total > 0.9, widths
    #: Every width is an even number of board pixels: twice a whole draw.io width.
    assert all(w >= 2 and w % 2 == 0 for w in widths), widths
