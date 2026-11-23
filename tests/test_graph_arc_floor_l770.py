"""Source text: the Arc layout opens no smaller than the mind map's readable
zoom (L770, owner decided 2026-11-12). Measured at 1024x768 with 52 notes:
framed whole it opened at 0.26; with the floor, 0.45, the baseline at y 490 of
a 661px canvas and the line centred (-167 to 1164)."""

import re
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "graph.js").read_text()


def _frame_tree():
    start = SRC.index("function frameTree(")
    return SRC[start : SRC.index("\n}\n", start)]


def test_an_arc_has_the_mind_maps_floor():
    body = _frame_tree()
    assert re.search(r"const floor = arc \? 0\.45\b", body)
    assert "Math.max(floor, Math.min(1, fit))" in body


def test_an_arc_too_long_for_the_view_is_centred():
    assert "spanX * scale <= width - 20 || arc" in _frame_tree()
