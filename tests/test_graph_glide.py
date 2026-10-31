"""The graph's notes move at an even speed between worker ticks (INBOX 586).

The owner, verbatim: "the graph is a little jittery when nodes move around or
adjust position". The layout worker steps on its own timer (about 16 ms, or
as long as a tick took on a big map) and the canvas paints on the display's
60 Hz: the two beat, so a note that moves the same distance every tick moved
two steps in one frame, none in the next, one in the one after. The canvas now
draws the point between the last two ticks that the frame's time says
(`gcGlideStep`, graph-canvas.js).

Measured here, not in a browser: the sandbox's headless frames are as slow and
as irregular as its load (12 to 27 fps at load 19), which hides the beat. The
two functions run under node against a worker ticking every 16 ms with up to
4 ms of timer jitter (and, the big-map case, every 70 ms) and frames every
16.7 ms, a note moving a constant distance per tick: how uneven the per-frame
steps are with the tick handler's old "jump to the tick" and with the glide.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CANVAS = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = CANVAS.index(f"\nfunction {name}(") + 1
    return CANVAS[start : CANVAS.index("\n}\n", start) + 2]


def _tick_body() -> str:
    start = CANVAS.index("        const now = performance.now();\n        const gap = s.lastTickAt")
    end = CANVAS.index("        s.gliding = true;", start) + len("        s.gliding = true;")
    return CANVAS[start:end]


SCRIPT = "\n".join(
    [
        "let clock = 0; const performance = { now: () => clock };",
        re.search(r"^const GC_GLIDE_MIN_MS = \d+;", CANVAS, re.M).group(0),
        re.search(r"^const GC_GLIDE_MAX_MS = \d+;", CANVAS, re.M).group(0),
        _function("gcGlideStep"),
        _function("gcGlideFinish"),
        _function("gcAimNodes"),  # the tick body points the notes through it (perf3-1031)
        "function onTick(s, positions) {\n  const count = s.nodes.length;\n" + _tick_body() + "\n}",
        """
function run(glide, tickMs, jitter) {
  let seed = 3;
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const s = { nodes: [{ x: 0, y: 0 }], dragNode: null };
  let worker = 0, x = 0, nextTick = tickMs;
  const shown = [];
  for (let frame = 1; frame <= 240; frame++) {
    const at = frame * (1000 / 60);
    while (nextTick <= at) {
      clock = nextTick;
      worker += 1;
      x = worker * 2;
      if (glide) onTick(s, [x, 0]);
      else s.nodes[0].x = x;
      nextTick += tickMs + (rnd() * 2 - 1) * jitter;
    }
    clock = at;
    if (glide) gcGlideStep(s);
    shown.push(s.nodes[0].x);
  }
  const steps = shown.slice(60).map((v, i, a) => (i ? v - a[i - 1] : null)).slice(1);
  const mean = steps.reduce((a, b) => a + b, 0) / steps.length;
  const sd = Math.sqrt(steps.reduce((a, b) => a + (b - mean) ** 2, 0) / steps.length);
  return { cv: Math.round((sd / mean) * 100) / 100, still: steps.filter((v) => v < 0.05).length, frames: steps.length };
}
console.log(JSON.stringify({
  jump: run(false, 16, 4), glide: run(true, 16, 4),
  jumpBig: run(false, 70, 10), glideBig: run(true, 70, 10),
}));
""",
    ]
)


@pytest.fixture(scope="module")
def motion():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    run = subprocess.run([node, "-e", SCRIPT], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def test_the_glide_evens_out_a_worker_beating_against_the_display(motion):
    # Jumping to each tick: frames with no step at all, and steps of 0, 2, 4.
    assert motion["jump"]["still"] > 0 and motion["jump"]["cv"] > 0.3
    # Drawn between ticks: every frame moves, and by a near-even step.
    assert motion["glide"]["still"] == 0
    assert motion["glide"]["cv"] < motion["jump"]["cv"] / 2


def test_a_big_map_moves_every_frame_rather_than_once_every_four(motion):
    assert motion["jumpBig"]["still"] > motion["jumpBig"]["frames"] / 2
    assert motion["glideBig"]["still"] == 0
    assert motion["glideBig"]["cv"] < motion["jumpBig"]["cv"] / 4
