"""INBOX 1709: the lower body's, the wisps' and the nebula's drawings change shape (`atlasRigLower.morph`), not only
their boxes. Run in node's vm over the real file: a parsed path moves with the clock, loops, keeps its commands, and a
ribbon is still at its root. Browser numbers (distinct `d` per path over 5 s, 0 of 64 before, 62 of 64 after) are in the
CHANGELOG line."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped, unwrapped_copy

ROOT = Path(__file__).resolve().parent.parent
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")
LIFE = unwrapped((ROOT / "frontend" / "js" / "atlas-life.js").read_text(encoding="utf-8"))

SCRIPT = r"""
const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync(process.argv[1], "utf8");
const ctx = { atlasFix: (v) => Math.round(v * 100) / 100, console, Math, Map, Set, Object, Array, Number, Float32Array, document: {}, window: {}, setTimeout, clearTimeout, performance: { now: () => 0 } };
vm.createContext(ctx);
vm.runInContext(src + "\n;this.__m = atlasRigLower.morph;", ctx);
const M = ctx.__m;
const d = "M10 20C10 30 12 40 14 50A1 1 0 0 0 16 50C14 40 12 30 12 20Z";
const p = M.parse(d);
const mk = (kind) => {
  const el = { v: d, setAttribute(k, v) { this.v = v; }, getAttribute() { return d; } };
  const t = M.target(el, kind, kind === "hem" ? { y0: 20, y1: 50, cx: 13 } : { rx: 10, ry: 20, far: 30 }, 0.5);
  M.prep(t);
  return { t, el };
};
const ang = [[0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]];
const frame = (o, clock, gain = 1) => { M.draw(o.t, clock, gain, ang); return o.el.v; };
const out = { parsed: !!p, points: p.pts.length / 2, arc: p.pre.some(Boolean), rejectsRelative: M.parse("m1 2c3 4 5 6 7 8") === null, rejectsH: M.parse("M1 2H5") === null };
for (const kind of ["ribbon", "field", "hem"]) {
  const o = mk(kind);
  const seen = new Set();
  for (let i = 0; i < 40; i += 1) seen.add(frame(o, i * 0.7));
  const period = M.periods[0] * M.periods[1] * M.periods[2];
  out[kind] = { distinct: seen.size, letters: frame(o, 3.3).replace(/[-\d. ]/g, ""), still: frame(o, 3.3, 0) === frame(mk(kind), 3.3, 0), sane: /NaN|undefined/.test(frame(o, 5.1)) };
}
const r = mk("ribbon");
out.ribbonRoot = frame(r, 4.4).startsWith("M10 20");
const h = mk("hem");
out.hemWaist = frame(h, 4.4).startsWith("M10 20");
console.log(JSON.stringify(out));
"""


def _run() -> dict:
    res = subprocess.run(["node", "-e", SCRIPT, str(unwrapped_copy(ROOT / "frontend" / "js" / "atlas-life.js"))], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout.strip().splitlines()[-1])


@needs_node
def test_a_path_moves_keeps_its_commands_and_rests_at_zero_gain() -> None:
    out = _run()
    assert out["parsed"] and out["arc"] and out["points"] == 8
    assert out["rejectsRelative"] and out["rejectsH"]
    for kind in ("ribbon", "field", "hem"):
        assert out[kind]["distinct"] >= 30, kind
        assert out[kind]["letters"] == "MCACZ", out[kind]["letters"]
        assert out[kind]["still"], f"{kind} moved at zero gain"
        assert not out[kind]["sane"], f"{kind} wrote NaN or undefined"


@needs_node
def test_the_root_of_a_ribbon_and_the_waist_of_a_hem_hold() -> None:
    out = _run()
    assert out["ribbonRoot"] and out["hemWaist"]


def test_motion_is_off_when_the_figure_is_not_live() -> None:
    run = LIFE[LIFE.index("atlasRigLower.morph.run = ") :]
    run = run[: run.index("\n};")]
    for guard in ("atlasMotionOK(box)", "atl-off", "document.hidden", "data-atlas-lite", "nm-buddy-dragging"):
        assert guard in run, guard
    assert "M.rest(low)" in run, "a figure that stops moving must put its drawn shapes back"


def test_no_path_animation_which_would_take_the_figure_off_the_compositor() -> None:
    block = LIFE[LIFE.index("atlasRigLower.morph = {") : LIFE.index("**When the lower body spells")]
    assert ".animate(" not in block and "requestAnimationFrame" not in block
