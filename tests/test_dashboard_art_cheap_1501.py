"""INBOX 1501 (audit PF9): the Dashboard's constellation is cheap.

Measured at 4x CPU with 150 notes: the art was about 60 percent of the script
a Dashboard click ran in its first 2.5 s (a redraw of 7.7 ms median, thirty a
second, forever), most of it a colour string and a stroke or two fills for each
of a few hundred lines and a hundred stars. Now the lines and the stars fall
into colour buckets drawn as one `Path2D` and one fill or stroke each, and the
sketch draws only while somebody is looking: a few seconds after it mounts, is
regenerated or has the pointer on it, then it rests. The numbers are in
CHANGELOG.md; this holds the shape.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

#: Moved from dashboard.js (INBOX 1530 d), read at the margin: one IIFE, indented two spaces.
SOURCE = re.sub(r"(?m)^  ", "", (Path(__file__).resolve().parents[1] / "frontend" / "js" / "dash-art.js").read_text(encoding="utf-8"))
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _top(kind: str, name: str) -> str:
    match = re.search(rf"^{kind} {name}\b.*?^(?:\}}|\);|;)\s*$", SOURCE, re.S | re.M)
    assert match, f"{name} is gone from dash-art.js"
    return match.group(0)


def _node(body: str):
    parts = [
        "const ART_CSS = new Map();",
        re.search(r"^const artCss = .*?^};", SOURCE, re.S | re.M).group(0),
        re.search(r"^const ART_LINK = .*$", SOURCE, re.M).group(0),
        re.search(r"^const ART_LINE_STEP = .*$", SOURCE, re.M).group(0),
        re.search(r"^const ART_TWINKLE_STEPS = .*$", SOURCE, re.M).group(0),
        re.search(r"^const artBucket = .*?^};", SOURCE, re.S | re.M).group(0),
        "const artCoreLight = () => 50;",
        _top("function", "artDrawLines"),
        _top("function", "artDrawStars"),
        """
class Path2D { constructor() { this.n = 0; } moveTo() {} lineTo() { this.n += 1; } arc() { this.n += 1; } }
const calls = { stroke: 0, fill: 0, segments: 0, styles: new Set() };
const ctx = {
  set strokeStyle(v) { calls.styles.add(v); }, set fillStyle(v) { calls.styles.add(v); },
  set lineWidth(v) {},
  stroke(p) { calls.stroke += 1; calls.segments += p.n; }, fill(p) { calls.fill += 1; calls.segments += p.n; },
};
""",
        body,
    ]
    out = subprocess.run(["node", "-e", "\n".join(parts)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@needs_node
def test_every_near_pair_is_a_line_but_the_strokes_are_one_per_colour_step():
    out = _node(
        """
const dots = [];
for (let i = 0; i < 80; i++) dots.push({ x: (i % 10) * 20, y: Math.floor(i / 10) * 20, vis: 1, hue: i % 2 ? 120 : 200 });
artDrawLines(ctx, dots, 1, false);
let near = 0;
for (let i = 0; i < dots.length; i++) for (let j = i + 1; j < dots.length; j++)
  if (Math.hypot(dots[i].x - dots[j].x, dots[i].y - dots[j].y) < 70) near += 1;
process.stdout.write(JSON.stringify({ near, calls: { stroke: calls.stroke, segments: calls.segments } }));
"""
    )
    assert out["near"] > 200, "the grid has hundreds of near pairs"
    assert out["calls"]["segments"] == out["near"], "no pair is lost to the bucketing"
    assert out["calls"]["stroke"] <= 2 * 16, "one stroke per hue and alpha step, not per line"


@needs_node
def test_a_hidden_line_layer_draws_nothing_and_stars_are_two_fills_per_colour_step():
    out = _node(
        """
artDrawLines(ctx, [{ x: 0, y: 0, vis: 1, hue: 10 }, { x: 5, y: 5, vis: 1, hue: 10 }], 0, true);
const none = calls.stroke;
const dots = [];
for (let i = 0; i < 100; i++) dots.push({ x: i, y: i, vis: 1, hue: (i % 4) * 90, phase: i * 0.1, drawSize: 3 });
artDrawStars(ctx, dots, 1.5, true);
process.stdout.write(JSON.stringify({ none, fills: calls.fill, arcs: calls.segments }));
"""
    )
    assert out["none"] == 0, "lines at zero strength (mid-glide) draw nothing"
    assert out["arcs"] == 200, "a halo and a core for each of the 100 stars"
    assert out["fills"] <= 2 * 4 * (12 + 1), "two fills per hue and twinkle step, not 200"


def test_the_scene_draws_through_the_batches_and_no_colour_is_built_per_shape():
    scene = SOURCE[SOURCE.index("const scene = (t, settled = false) => {") : SOURCE.index("p.regenerate = ")]
    assert "artDrawLines(ctx, particles, lines, dark)" in scene
    assert "artDrawStars(ctx, leaving.concat(particles), t, dark)" in scene
    assert "ctx.arc(" not in scene and "ctx.stroke()" not in scene, "a shape drawn on its own is the cost this removed"


def test_the_sketch_draws_only_while_attended_and_wakes_on_the_card():
    sketch = SOURCE[SOURCE.index("const sketch = (p) =>") : SOURCE.index("artInstance = live ? new p5(sketch, holder)")]
    assert "let attendUntil = performance.now() + ART_SETTLE_MS;" in sketch
    draw = sketch[sketch.index("p.draw = () => {") :]
    assert "performance.now() > attendUntil" in draw[:400] and "rest();" in draw[:400]
    assert "!glide && !fade" in draw[:400], "a glide or a fade in hand keeps the loop"
    for event in ("pointerenter", "pointermove", "focusin", "touchstart"):
        assert f'"{event}"' in sketch
    regen = sketch[sketch.index("p.regenerate = () => {") :]
    assert "attend();" in regen[:120], "Regenerate wakes a resting sketch"
    # The listeners go with the sketch: a theme change mounts a new one on the same holder.
    assert "holder.removeEventListener(type, attend)" in sketch
    assert 6000 <= int(re.search(r"^const ART_ATTEND_MS = (\d+);", SOURCE, re.M).group(1)) <= 12000
    assert int(re.search(r"^const ART_SETTLE_MS = (\d+);", SOURCE, re.M).group(1)) <= 2500, "a visit to the tab mounts a sketch; its glimpse stays short"
