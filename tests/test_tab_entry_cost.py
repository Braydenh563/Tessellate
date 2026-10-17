"""Tab entry cost (perf sweep 2026-10-17, scratchpad/ui-sweeps/tabenter.js).

The frame spikes on a tab press were measured with the companion off at 4x
CPU, on a 2,000-note notebook, and traced by Chromium event
(scratchpad/ui-sweeps/tabtrace.js). Each test here holds one win that a
source-level check can hold; the numbers are in the commit that added it.
"""

import re
from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"
CANVAS = (JS / "graph-canvas.js").read_text(encoding="utf-8")


def _body(source: str, signature: str) -> str:
    start = source.index(signature)
    return source[start : source.index("\n}\n", start)]


def test_a_hidden_graph_tab_draws_nothing():
    """Leaving the Graph tab left the canvas drawing for about a second (37
    draws, 60 ms at 1x, 240 ms at 4x) into the next tab's entry window: the
    worker's last ticks still arrived and each asked for a frame of a map
    nobody could see. A draw for the tab's own map is dropped while the page
    is hidden; the next visit renders the map in full (`switchTab`)."""
    hidden = _body(CANVAS, "function gcTabHidden(")
    assert 'tab-graph' in hidden and 'classList.contains("hidden")' in hidden
    request = _body(CANVAS, "function gcRequestDraw(")
    assert request.index("gcTabHidden(s)") < request.index("requestAnimationFrame")
    draw = _body(CANVAS, "function gcDraw(")
    assert re.search(r"if \(gcTabHidden\(s\)\)", draw[:400])
