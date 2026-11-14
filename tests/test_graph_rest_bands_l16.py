"""L-graph-16: a big map's settle repaint is painted in bands, a frame apart.

At 2,000 notes and CPU 4x each wheel stop repainted the whole rest layer 160 ms
later as one task (a 110 ms long task). The scaled layer stays on screen while
the new one is built a band per composed draw; small maps keep the immediate repaint so
their rest frame is the same pixels at the same moment.
"""

from __future__ import annotations

from pathlib import Path

JS = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")


def _between(start: str, end: str) -> str:
    a = JS.index(start)
    return JS[a : JS.index(end, a)]


def test_the_settle_repaint_of_a_big_map_is_built_in_bands_not_at_once():
    composed = _between("function gcDrawComposed(s) {", "const hovering")
    assert "s.nodes.length >= GC_SLICE_NODES" in composed
    assert "gcRestBuild(s, scene)" in composed
    # a layer that no longer covers the frame, or is scaled past 2x, still repaints at once
    assert "!covers || r > 2 || r < 0.5" in composed


def test_a_build_is_dropped_when_the_camera_moves_or_the_frame_repaints():
    build = _between("function gcRestBuild(", "function gcDrawComposed(")
    for guard in ("b.scene === scene", "b.t.k === t.k", "b.t.x === t.x", "b.t.y === t.y", "b.w === s.dims.w", "b.tokens === gcTokens"):
        assert guard in build, guard
    # one band per composed draw, which asks for the next itself: no frame loop of its own
    assert "requestAnimationFrame" not in build and "gcRequestDraw" not in build
    # a band frame that owes the screen nothing does not compose the layer again
    composed = _between("function gcDrawComposed(s) {", "const hovering")
    assert "sh.k === t.k" in composed and "settle(0)" in composed
    assert "|| Boolean(s.restBuild)" in JS


def test_a_band_is_held_by_a_clip_that_is_dropped_with_the_layer():
    paint = _between("function gcPaintLayer(", "const GC_SLICE_NODES")
    assert "ctx.save();" in paint and "ctx.restore();" in paint
    draw = _between("function gcDraw(s = gcTab) {", "const hl = gcHighlight(s)")
    assert "ctx.clip();" in draw and "s.paintBand" in draw
