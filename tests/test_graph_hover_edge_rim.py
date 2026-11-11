"""A lit link starts and ends at each dot's rim, not its centre (the owner,
2026-11-03, a screenshot of the hover line crossing into the pink dot)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from tests._js_scope import unwrapped

GRAPH = unwrapped((Path(__file__).resolve().parents[1] / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8"))


def _rim(node, toward, k=1):
    start = GRAPH.index("gcDrawEdgeHover.rim = function gcEdgeRim(")
    fn = GRAPH[start : GRAPH.index("\n};\n", start) + 3]
    script = f"const GC_MIN_DOT_PX = 3;\nfunction gcDrawEdgeHover() {{}}\n{fn}\nconsole.log(JSON.stringify(gcDrawEdgeHover.rim({json.dumps(node)}, {json.dumps(toward)}, {k})));"
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


def test_the_end_sits_on_the_rim_toward_the_other_end():
    end = _rim({"x": 0, "y": 0, "r": 10, "_grow": 2}, {"x": 100, "y": 0})
    assert end == {"x": 13, "y": 0}


def test_a_line_shorter_than_the_dot_keeps_the_centre():
    end = _rim({"x": 0, "y": 0, "r": 10}, {"x": 5, "y": 0})
    assert (end["x"], end["y"]) == (0, 0)


def test_the_hover_painter_uses_the_rim_at_both_ends():
    start = GRAPH.index("function gcDrawEdgeHover(")
    body = GRAPH[start : GRAPH.index("\n}\n", start)]
    assert "gcDrawEdgeHover.rim(a, bow || b, k)" in body and "gcDrawEdgeHover.rim(b, bow || a, k)" in body
    assert "ctx.moveTo(a.x, a.y)" not in body
