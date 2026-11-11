"""E3 (INBOX 1719 b), the in-app side: the ears follow through (they lag a start, swing past a stop and settle a beat after the body
has stopped), driven by the same spring chain as the tail (`atlasTailFollow`, atlas-life.js). Node, a fixed clock; nothing uses real time."""

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
const a = src.indexOf("function atlasTailFollow("), b = src.indexOf("//: The tail's centreline bent");
const ctx = { Math, Number, Object, Array, Number };
vm.createContext(ctx);
vm.runInContext(src.slice(a, b), ctx);
const mode = process.argv[2];
const ears = [{ style: {} }, { style: {} }];
const writes = [];
for (const el of ears) { let v = ""; Object.defineProperty(el.style, "rotate", { get: () => v, set: (x) => { v = x; writes.push(x); } }); }
const box = { atlasRig: { lower: { boxes: [], wisps: [] } }, querySelectorAll: (q) => (q === ".atl-ear" ? ears : []) };
const tail = {}; const rows = [];
let x = 100, t = 0, y = 0;
const dt = 0.016;
for (let i = 0; i < 220; i += 1) {
  t = i * dt;
  // moves at 300 px/s from 0.2 s to 1.2 s (a start, a glide, a stop), then is still; "still" never moves at all
  const v = mode === "walk" && t >= 0.2 && t < 1.2 ? 300 : 0;
  x += v * dt;
  ctx.atlasTailFollow(tail, dt, x, y);
  ctx.atlasTailFollow.strands(box, tail);
  rows.push([t, v, parseFloat(ears[0].style.rotate || "0"), parseFloat(ears[1].style.rotate || "0")]);
}
console.log(JSON.stringify({ rows, writes: writes.length, last: [ears[0].style.rotate, ears[1].style.rotate] }));
"""


def _run(mode: str) -> dict:
    out = subprocess.run(["node", "-e", HARNESS, str(JS / "atlas-life.js"), mode], capture_output=True, text=True, timeout=60, check=True).stdout
    return json.loads(out)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_ears_lag_a_start_swing_past_a_stop_and_settle_after_the_body_has_stopped() -> None:
    r = _run("walk")
    rows = r["rows"]
    start = [row[2] for row in rows if 0.2 < row[0] <= 0.5]
    stop = [row for row in rows if 1.2 <= row[0] <= 1.6]
    later = [row[2] for row in rows if 1.6 < row[0] <= 2.6]
    assert min(start) < -0.6  # thrown back, opposite to the way it sets off (the ear streams behind)
    assert max(row[2] for row in stop) > 0.6  # and forward on the stop: the ear keeps going after the body has
    assert all(row[1] == 0 for row in stop)  # the body is already still
    assert min(later) < -0.15  # it swings back through the other way at least once
    assert abs(rows[-1][2]) < 0.1 and r["last"] == ["", ""]  # settled and the style cleared: nothing is left on the ears
    assert max(abs(row[2]) for row in rows) <= 9.1  # the most an ear turns is a few degrees
    assert all(row[2] == row[3] for row in rows)  # both ears turn together


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_still_figure_writes_nothing_to_its_ears_and_a_walk_writes_only_changes() -> None:
    still = _run("still")
    assert still["writes"] == 0 and still["last"] == ["", ""]
    walk = _run("walk")
    assert walk["writes"] <= 2 * len(walk["rows"]) // 2  # a write per ear per change of a tenth of a degree, never one per frame of rest
    steady = [row for row in walk["rows"] if 3.0 < row[0]]
    assert all(row[2] == 0 for row in steady)


def test_the_ear_follow_is_wired_into_the_tail_loop_and_costs_no_layout() -> None:
    src = (JS / "atlas-life.js").read_text(encoding="utf-8")
    body = src[src.index("atlasTailFollow.strands = "):src.index("//: The tail's centreline bent")]
    assert 'querySelectorAll(".atl-ear")' in body and "atlasEars" in body  # found once, kept on the box
    assert "getBoundingClientRect" not in body and "getComputedStyle" not in body and "offsetWidth" not in body  # no forced layout in a frame
