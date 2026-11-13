"""Source text: part of this reads the shipped CSS, markup or script, whose effect needs a browser this suite does not run; what was measured in the app is below.

L-graph-10: a new note's cell in the Tessellation view settles like the logo's third cell.

The emblem's `emblem-arrive` keyframes (css/03-dashboard-widgets.css): from
translate(7%, -7%) rotate(-10deg) at 0, through (-0.8%, 0.8%) 1.5deg at 72%,
to rest at 100%, over 1.4 s. `tessArrivePose` is those keyframes in a cell's
width; `tessArrivals` decides which cells arrive. Both run under node here.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parent.parent
TESS = unwrapped((ROOT / "frontend" / "js" / "graph-tessellate.js").read_text(encoding="utf-8"))
CSS = (ROOT / "frontend" / "css" / "03-dashboard-widgets.css").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    m = re.search(rf"^function {name}\(.*?^\}}", TESS, re.S | re.M)
    assert m, name
    return m.group(0)


SCRIPT = "\n".join(
    [
        "let still = false, frames = 0;",
        "const gcStill = () => still; const gcRequestDraw = () => frames++; gcRequestDraw.selfCap = 300;",
        "const TESS_ARRIVE_MS = 1400;",
        _fn("tessArrivals"),
        _fn("tessArrivePose"),
        """
const cells = (ids) => ({ cells: ids.map((id) => ({ id })) });
const s = {};
const first = tessArrivals(s, cells([1, 2, 3]), 0);
const snap = (m) => m && [...m];
const added = snap(tessArrivals(s, cells([1, 2, 3, 4]), 100));
const mid = snap(tessArrivals(s, cells([1, 2, 3, 4]), 800));
const done = snap(tessArrivals(s, cells([1, 2, 3, 4]), 1600));
// A category shown again brings back old ids: not an arrival.
const s2 = {};
tessArrivals(s2, cells([5, 9]), 0);
const shownAgain = tessArrivals(s2, cells([2, 5, 9]), 10);
still = true;
const s3 = {};
tessArrivals(s3, cells([1]), 0);
const reduced = tessArrivals(s3, cells([1, 2]), 10);
const pose = (t) => tessArrivePose(t);
console.log(JSON.stringify({
  first, added, mid: mid && mid.map(([id]) => id), done,
  shownAgain, reduced, frames,
  p0: pose(0), p72: pose(0.72), p1: pose(1), p10: pose(0.1),
}));
""",
    ]
)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_only_a_newer_note_arrives_and_its_pose_follows_the_emblem() -> None:
    run = subprocess.run(["node", "-e", SCRIPT], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr[-2000:]
    out = json.loads(run.stdout.strip().splitlines()[-1])
    assert out["first"] is None, "the first draw is not an arrival"
    assert out["added"] == [[4, 100]] and out["mid"] == [4] and out["done"] is None, out
    assert out["frames"] >= 2, "a frame is asked for while a cell is arriving"
    assert out["shownAgain"] is None and out["reduced"] is None, out
    deg = math.pi / 180
    p0, p72, p10 = out["p0"], out["p72"], out["p10"]
    assert (p0["dx"], p0["dy"], p0["alpha"]) == (0.07, -0.07, 0) and math.isclose(p0["turn"], -10 * deg)
    assert math.isclose(p72["dx"], -0.008) and math.isclose(p72["dy"], 0.008) and math.isclose(p72["turn"], 1.5 * deg)
    assert out["p1"] is None
    assert 0 < p10["alpha"] < 1


def test_the_pose_is_the_emblem_keyframes() -> None:
    frames = CSS[CSS.index("@keyframes emblem-arrive") :]
    frames = frames[: frames.index("\n}\n")]
    assert "translate(7%, -7%) rotate(-10deg)" in frames and "72% {" in frames
    assert "translate(-0.8%, 0.8%) rotate(1.5deg)" in frames
    assert "emblem-arrive 1.4s" in CSS and "const TESS_ARRIVE_MS = 1400;" in TESS
    draw = _fn("gcDrawTessellation")
    assert "const arriving = tessArrivals(s, tess, now);" in draw
    assert "ctx.globalAlpha = fade * (" in draw
