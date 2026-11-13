"""Source text: part of this reads the shipped CSS, markup or script, whose effect needs a browser this suite does not run; what was measured in the app is below.

A saved view and Reset carry the link-kind chips (audit 1029 L12 re-run, 2026-11-12).

Live: a view saved with Contradicts off came back with the chip on and 240
links drawn instead of 200 (scratchpad sweep a3.js, port 8803).
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._js_scope import unwrapped

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _fn(source: str, name: str) -> str:
    found = re.search(rf"(?s)function {name}\(.*?\n\}}", source)
    assert found, name
    return found.group(0)


def test_view_and_reset_carry_the_hidden_link_kinds():
    graph = unwrapped((JS / "graph.js").read_text(encoding="utf-8"))
    assert "hiddenLinkKinds" in _fn(graph, "graphCaptureView")
    assert "graph-hidden-link-kinds" in _fn(graph, "graphApplyView")
    assert "hiddenLinkKinds: []" in graph
    assert "graph-hidden-link-kinds" in _fn(graph, "graphCaptureSettings")
    assert "graph-hidden-link-kinds" in _fn(graph, "graphApplySettings")


def test_the_chip_render_reads_the_pref_back():
    canvas = (JS / "graph-canvas.js").read_text(encoding="utf-8")
    body = re.search(r"(?s)function gcRenderFilterChips\(data\) \{.*?\n  \}\n", canvas)
    assert body and "graphHiddenLinkKinds.clear()" in body.group(0)


def test_the_popup_topic_chip_gets_the_touch_floor():
    css = (JS.parent / "css" / "graph-lazy.css").read_text(encoding="utf-8")
    assert re.search(r"(?s)@media \(pointer: coarse\) \{\s*\.graph-popup-topic > \.chip-interactive \{\s*min-height: var\(--target-min\)", css)
