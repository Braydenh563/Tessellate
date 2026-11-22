"""INBOX 609: a long map branch is a smooth curve, not a polyline.

The owner: "on longer mind map links, I can actually see the hard bends in
the line and it isnt a smooth curve". The ribbon's two sides were the
samples joined by `L`; they are now a Catmull-Rom spline through the same
samples (`wbMapSmoothThrough`), and a longer branch gets more samples.
The browser measurement is scratchpad/ui-sweeps/bm1005-curve.js.
"""

from tests._app_js import frontend_text
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MAP = frontend_text("whiteboard-map.js")


def _function(name: str) -> str:
    start = MAP.index(f"function {name}(")
    end = MAP.index("\n}\n", start) + 3
    return MAP[start:end]


def test_ribbon_sides_are_drawn_through_the_spline():
    body = _function("wbMapRibbonD")
    assert "wbMapSmoothThrough(left, at)" in body
    assert "wbMapSmoothThrough(right, at)" in body
    # The old polyline join must not come back on either side.
    assert 'map((pt, i) => `${i ? "L" : "M"}' not in body
    assert "right.reverse().map((pt) => `L" not in body


def test_longer_branches_get_more_samples():
    body = _function("wbMapRibbonD")
    assert re.search(r"Math\.hypot\(p1\.x - p0\.x, p1\.y - p0\.y\) / 40", body)


def test_spline_shares_its_tangent_at_every_sample():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    src = _function("wbMapSmoothThrough")
    script = src + """
const pts = [];
for (let i = 0; i <= 30; i += 1) pts.push([i * 40, Math.sin(i / 5) * 200]);
const at = ([x, y]) => `${x} ${y}`;
const d = wbMapSmoothThrough(pts, at);
const segs = d.split("C").filter(Boolean).map((s) => s.trim().split(/\\s+/).map(Number));
let worst = 0;
for (let i = 0; i + 1 < segs.length; i += 1) {
  const [, , c2x, c2y, ex, ey] = segs[i];
  const [n1x, n1y] = segs[i + 1];
  const a = Math.atan2(ey - c2y, ex - c2x);
  const b = Math.atan2(n1y - ey, n1x - ex);
  worst = Math.max(worst, Math.abs(a - b));
}
console.log(JSON.stringify({ spans: segs.length, worst }));
"""
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True, timeout=30)
    got = json.loads(out.stdout)
    assert got["spans"] == 30
    assert got["worst"] < 1e-9, "a corner where two spans meet"
