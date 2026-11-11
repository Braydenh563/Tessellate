"""The lower body and the nebula follow the pose (E6, companion-asks B1 and B3, owner: "the lower body ... not a fixed
shape"): sit, hang, lean, lounge and the acts on them (a dangle over an edge, a kick, a swing, a sloth's hang) each take
a row of their own, in the app (Atlas's lower body, hair and stream) and on the desk (the strand flow). Run in node's vm
over the real files and over `behaviour.Flow` itself; fixed times, no clock."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.core.overlay import behaviour as bh
from tests.test_poses_1681 import MOTION, _fn

ROOT = Path(__file__).resolve().parent.parent
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")
NEW = ("lean", "dangle", "kick", "swing", "sloth")

LIFE_SCRIPT = r"""
const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync("frontend/js/atlas-life.js", "utf8");
const ctx = { atlasFix: (v) => Math.round(v * 100) / 100, console, Math, Map, Set, Object, Array, Number, performance, document: {}, window: {}, setTimeout, clearTimeout };
vm.createContext(ctx);
vm.runInContext(src + "\n;this.__x = { L: ATLAS_LOWER_STATES, H: ATLAS_HAIR_STATES, N: ATLAS_NEB_STATES, of: atlasRigLower.blend.of, byState: atlasRigLower.flowByState };", ctx);
const x = ctx.__x, out = {};
for (const s of %s) {
  const lower = x.of(x.L[s].v);
  out[s] = {
    authored: x.L[s].v.length, blended: lower.length, distinct: new Set(lower.map((r) => r.join())).size,
    turn: Math.max(...lower.map((r) => Math.abs(r[0]))),
    hair: x.of(x.H[s]).length, neb: x.of(x.N[s]).length, flow: x.byState[s],
    others: Object.keys(x.L).filter((k) => k !== s && JSON.stringify(x.L[k].v) === JSON.stringify(x.L[s].v)),
  };
}
console.log(JSON.stringify(out));
"""


@needs_node
def test_each_new_pose_has_three_authored_rows_six_or_more_arrangements_and_holds_the_join() -> None:
    script = LIFE_SCRIPT % json.dumps(list(NEW))
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True, cwd=ROOT)
    got = json.loads(done.stdout)
    assert set(got) == set(NEW)
    for state, row in got.items():
        assert row["authored"] >= 3 and row["blended"] >= 6 and row["distinct"] == row["blended"], (state, row)
        assert row["hair"] == row["neb"] == row["blended"], (state, "hair, stream and lower body agree")
        assert row["turn"] <= 4, (state, "the join with the torso allows 4 degrees")
        assert len(row["flow"]) == 2 and not row["others"], (state, row)


@needs_node
def test_the_lower_state_follows_the_lean_the_dangle_the_kick_the_swing_and_the_sloth() -> None:
    src = _fn("atlasLowerState", MOTION) + re.search(r"^atlasLowerState\.acts = .*;$", MOTION, re.M).group(0)
    script = (
        src
        + """
const make = (classes, pose = "") => ({ classList: { contains: (c) => classes.includes(c) }, dataset: { pose, travel: "" } });
const box = { dataset: {} };
console.log(JSON.stringify([
  atlasLowerState(make([], "lean"), box),
  atlasLowerState(make(["nmb-act-dangle"], "sit"), box),
  atlasLowerState(make(["nmb-act-kick"], "sit"), box),
  atlasLowerState(make(["nmb-act-swing"], "hang"), box),
  atlasLowerState(make(["nmb-act-sloth"], "hang"), box),
  atlasLowerState(make([], "hang"), box),
  atlasLowerState(make([], "sit"), box),
  atlasLowerState(make(["nmb-act-lounge"], "sit"), box),
  atlasLowerState(make(["nmb-sleep"], "lean"), box),
  atlasLowerState(make([], "stand"), box),
]));
"""
    )
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    assert json.loads(done.stdout) == ["lean", "dangle", "kick", "swing", "sloth", "hang", "sit", "lounge", "lie", "idle"]


def views(frame: str, seconds: float = 20.0, step: float = 0.5) -> list[tuple[int, ...]]:
    flow = bh.Flow(7)
    return [flow.view(i * step, frame=frame) for i in range(int(seconds / step))]


@pytest.mark.parametrize("frame", ["dangle", "kick0", "kick1", "meditate", "sit", "hang", "hang_one"])
def test_the_desk_lower_body_takes_three_or_more_arrangements_in_twenty_seconds_on_each_pose(frame: str) -> None:
    seen = views(frame)
    assert len({v for v in seen}) >= 3
    # and it never jumps: two ticks apart differ by a few pixels at most (join within the same 4 degrees)
    steps = [max(abs(a - b) for a, b in zip(p, q, strict=True)) for p, q in zip(seen, seen[1:], strict=False)]
    assert max(steps) <= bh.FLOW_MAX * 16, max(steps)


def test_a_dangle_a_kick_and_a_meditation_have_a_row_of_their_own_not_the_default() -> None:
    rows = {key: (reach, speed) for key, reach, speed in bh.FLOW_POSE}
    for frame in ("dangle", "kick", "meditate"):
        assert frame in rows and rows[frame] != (1.0, 1.0), frame
    assert rows["kick"][1] > rows["dangle"][1] > rows["meditate"][1], "a kick is quick, a dangle slow, a meditation slower"
    assert rows["meditate"][0] < rows["dangle"][0] <= rows["kick"][0], "and the reach follows"


@pytest.mark.parametrize("frame", ["dangle", "kick0", "meditate"])
def test_the_desk_pose_eases_in_and_is_never_a_step(frame: str) -> None:
    flow = bh.Flow(7)
    flow.view(0.0, frame="idle")
    before = (flow.k_reach, flow.k_speed)
    flow.view(0.04, frame=frame)
    assert abs(flow.k_reach - before[0]) < 0.05 and abs(flow.k_speed - before[1]) < 0.05
    for i in range(1, 400):
        flow.view(0.04 * i, frame=frame)
    want = next((r, s) for key, r, s in bh.FLOW_POSE if frame.startswith(key))
    assert (flow.k_reach, flow.k_speed) == pytest.approx(want, abs=0.02)
