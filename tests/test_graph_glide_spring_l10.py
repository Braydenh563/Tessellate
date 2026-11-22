"""A camera glide cut off by another continues at the speed it had (LEDGER L10).

Before, the second glide began from rest on d3's cubic ease, so the view
stalled at the join: a pan of 400 px over 220 ms interrupted at its peak
(about 2,700 px/s) restarted at 0 px/s. Now the new glide's ease is a critically
damped spring entered at the old speed (`graphGlideKit.spring`, `.entry`,
`graphGlide` in graph.js). The two functions run under node on a fixed clock.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GRAPH = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")
CANVAS = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _function(name: str) -> str:
    start = GRAPH.index(f"\nfunction {name}(") + 1
    return GRAPH[start : GRAPH.index("\n}\n", start) + 2]


def _kit() -> str:
    start = GRAPH.index("\nconst graphGlideKit = {") + 1
    return GRAPH[start : GRAPH.index("\n};\n", start) + 4]


SCRIPT = "\n".join(
    [
        "let clock = 0; const performance = { now: () => clock };",
        _kit(),
        "const graphGlideLast = graphGlideKit.last, graphGlideVec = graphGlideKit.vec, graphGlideSlope = graphGlideKit.slope;",
        "const graphGlideSpring = graphGlideKit.spring, graphGlideEntry = graphGlideKit.entry;",
        """
const cubic = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const MS = 220;
// Old glide: x from 0 to 400 on the cubic, sampled every 16.7 ms, cut at 110 ms (its peak).
const node = {};
let x = 0, prevT = 0, first = true;
const at = (t) => 400 * cubic(t / MS);
let last = null;
for (let t = 16.7; t <= 111; t += 16.7) {
  clock = t;
  // the ease is called with the view applied one tick earlier
  const view = { x: at(t - 16.7), y: 0, k: 1 };
  Object.assign(graphGlideLast, { node, tPrev: graphGlideLast.t, t: clock, view, live: true });
  last = t;
}
const cutAt = last;
const view = { x: at(cutAt), y: 0, k: 1 };
clock = cutAt + 8;
const vel = graphGlideEntry(node, view, clock);
// the last two frames give the mean speed over the last frame: the glide's speed half a frame back
const mid = cutAt - 16.7 / 2;
const exact = (400 * (cubic((mid + 0.5) / MS) - cubic((mid - 0.5) / MS))) * 1000;
const atCut = (400 * (cubic((cutAt + 0.5) / MS) - cubic((cutAt - 0.5) / MS))) * 1000;
const target = [900, 0, 400];
const slope = graphGlideSlope(vel, graphGlideVec(view), target);
const ease = graphGlideSpring(slope, MS);
const way = 900 - view.x;
const dt = 0.02;
const startSpeed = (way * (ease(dt / MS) - ease(0))) / (dt / 1000);
// the restart without the fix: cubic from rest
const restartSpeed = (way * (cubic(dt / MS) - cubic(0))) / (dt / 1000);
// monotone to the target and settled
let overshoot = 0, ended = ease(1);
for (let i = 0; i <= 1000; i++) overshoot = Math.max(overshoot, ease(i / 1000) - 1);
// stale: a long gap, a finished glide, another element
const stale = [];
clock = cutAt + 300; stale.push(graphGlideEntry(node, view, clock));
clock = cutAt + 8; graphGlideLast.live = false; stale.push(graphGlideEntry(node, view, clock));
graphGlideLast.live = true; stale.push(graphGlideEntry({}, view, clock));
console.log(JSON.stringify({ vel: vel[0], exact, atCut, startSpeed, restartSpeed, overshoot, ended, stale, slopeNegative: graphGlideSlope([-100, 0, 0], [0, 0, 0], [10, 0, 0]) < 0, zeroWay: graphGlideSlope([5, 5, 5], [1, 1, 1], [1, 1, 1]) }));
""",
    ]
)


@needs_node
def test_an_interrupted_glide_continues_at_the_speed_it_had() -> None:
    out = json.loads(
        subprocess.run(
            ["node", "-e", SCRIPT], capture_output=True, text=True, check=True, timeout=60
        ).stdout
    )
    # The speed read from the last two frames is the glide's own, half a frame back (0.4 of the
    # way up its peak, so within 20% of the speed at the cut itself).
    assert out["vel"] == pytest.approx(out["exact"], rel=0.02), out
    assert out["vel"] == pytest.approx(out["atCut"], rel=0.2), out
    assert out["exact"] > 2000, out
    # The new glide opens at that speed, where the restart opened at 0.
    assert out["startSpeed"] == pytest.approx(out["vel"], rel=0.03), out
    assert out["restartSpeed"] < 50, out
    # It settles on the target and (opening forward) does not overshoot it.
    assert out["ended"] == 1 and out["overshoot"] < 0.02, out
    # No glide to continue (too long ago, ended, another view): null, so the cubic stays.
    assert out["stale"] == [None, None, None], out
    assert out["slopeNegative"] is True and out["zeroWay"] == 0, out


def test_every_camera_move_goes_through_the_one_glide() -> None:
    # The helper takes its length from the motion token (graphGlideMs), so less motion still cuts.
    assert "const ms = graphGlideMs(base);" in _function("graphGlide")
    assert ".transition().duration(graphGlideMs(" not in GRAPH + CANVAS
    calls = re.findall(r"graphGlide\((?:s\.)?(?:svg|graphSvg|s\.svg)", GRAPH + CANVAS)
    assert len(calls) >= 9, calls
