"""INBOX 1719 (b): the in-app eyes take small steps during a held gaze (`atlasBlink.saccade`, atlas-motion.js).
Node, a fixed clock and a seeded generator; nothing here uses real time."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"

HARNESS = r"""
const vm = require("vm"); const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8");
const grab = (re) => { const m = src.match(re); if (!m) throw new Error(String(re)); return m[0]; };
let clock = 0, queue = [], seed = Number(process.argv[2]);
const rnd = () => ((seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296);
const writes = [];
const iris = { style: { setProperty: (k, v) => writes.push([clock, k, v]) } };
let attend = true;
const buddy = { classList: { contains: (c) => c === "nmb-attend" && attend }, querySelector: () => ({}), querySelectorAll: () => [iris] };
const ctx = {
  Math: Object.assign(Object.create(Math), { random: rnd }), Number,
  nmb: { ex: 0.4, ey: -0.2 }, document: { hidden: false, getElementById: () => buddy },
  atlasMotionOK: () => true, atlasBlink: () => {},
  setTimeout: (fn, ms) => { queue.push([clock + ms, fn]); return queue.length; },
};
vm.createContext(ctx);
vm.runInContext(grab(/^atlasBlink\.saccade = [\s\S]*?\n};\n/m) + grab(/^atlasBlink\.saccade\.step = [\s\S]*?\n};$/m), ctx);
ctx.atlasBlink.saccade();
ctx.atlasBlink.saccade();  // armed twice: still one timer
while (queue.length) { queue.sort((a, b) => a[0] - b[0]); const [t, fn] = queue.shift(); clock = t; if (clock > 60000) attend = false; fn(); }
const ts = [...new Set(writes.map((w) => w[0]))];
const gaps = ts.slice(1).map((t, i) => t - ts[i]);
const exs = writes.filter((w) => w[1] === "--nmb-ex").map((w) => Number(w[2]));
console.log(JSON.stringify({ n: ts.length, first: ts[0], maxGap: Math.max(...gaps), minGap: Math.min(...gaps), lo: Math.min(...exs), hi: Math.max(...exs), left: queue.length, last: clock }));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
@pytest.mark.parametrize("seed", [1, 7, 42])
def test_a_held_gaze_has_a_step_of_the_eyes_every_point_six_to_one_point_eight_seconds(seed: int) -> None:
    out = subprocess.run(["node", "-e", HARNESS, str(JS / "atlas-motion.js"), str(seed)], capture_output=True, text=True, timeout=60, check=True).stdout
    r = json.loads(out)
    # 60 s held: a step about every 1.2 s (33 to 100), none more than 1.8 s apart, so no eye is still over 2 s
    assert 33 <= r["n"] <= 100 and r["maxGap"] <= 1800 and r["minGap"] >= 600 and r["first"] <= 1800
    assert 0.4 - 0.26 <= r["lo"] and r["hi"] <= 0.4 + 0.26 and r["hi"] - r["lo"] > 0.3  # small, and never the same place twice
    assert r["left"] == 0 and r["last"] < 62000  # released at 60 s: the loop stops, nothing is left running


def test_the_aim_arms_the_saccade_and_nothing_runs_without_a_look() -> None:
    avatars = (JS / "avatars.js").read_text(encoding="utf-8")
    i = avatars.index('buddy.classList.add("nmb-attend");')
    assert "atlasBlink.saccade?.()" in avatars[i : i + 200]
    motion = (JS / "atlas-motion.js").read_text(encoding="utf-8")
    assert "if (!buddy?.classList.contains(\"nmb-attend\")) return false;" in motion  # released: the loop ends
