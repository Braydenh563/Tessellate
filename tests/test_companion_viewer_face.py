"""The enlarged face reacts (B62, the owner, 2026-10-17: "The profile
avatar in the enlarged popup from double clicking the profile picture
doesn't have any life to it").

The view's face kept the one mood drawn from its name; under reduced motion
it only blinked. `nameMarkViewerFace` (companion-menu.js) swaps in another
face of it and back, as the companion's own does: brighter as the view
opens, more each poke in a row, a neighbouring look with each line it says.
Measured in Chromium (`scratchpad/ui-sweeps/profileviewer.js`).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MENU = (ROOT / "frontend" / "js" / "companion-menu.js").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

VIEWER = MENU[MENU.index("const NM_VIEWER_POKED") : MENU.index("//: **Under reduced motion, a blink now and then**")]


@needs_node
def test_b62_the_enlarged_face_reacts_and_comes_back() -> None:
    script = r"""
const vm = require("vm");
const timers = [];
const mk = (expr) => ({ dataset: expr === undefined ? {} : { expr }, classList: { add(c) { this.c = c; } }, style: { v: {}, setProperty(k, v) { this.v[k] = v; }, getPropertyValue(k) { return this.v[k] || ""; } }, after(n) { kids.push(n); }, remove() { kids.splice(kids.indexOf(this), 1); }, animate: () => ({ finished: Promise.resolve() }) });
const kids = [mk()];
const figure = { isConnected: true, querySelector: () => kids.find((k) => k.classList.c !== "nmv-leaving") };
const root = { dataset: {} };
const ctx = {
  Math, document: { documentElement: root }, nameMood: () => ({ mood: "calm" }), NMB_EXPR_NEAR: { calm: ["happy", "sly", "cute"], "": ["happy"] },
  isAtlasSeed: (s) => s === "Atlas", characterRendererFor: () => null, nameCharacterFigure: () => mk(),
  setTimeout: (f, ms) => { timers.push([f, ms]); return timers.length; }, clearTimeout() {},
};
vm.createContext(ctx);
vm.runInContext(process.argv[1] + "\n;globalThis.face = nameMarkViewerFace; globalThis.near = nameMarkViewerNear; globalThis.POKED = NM_VIEWER_POKED;", ctx);
(async () => {
  const r = {};
  ctx.face(figure, "Sam", "laughing", 2400);
  await null; await null;
  r.now = figure.querySelector().dataset.expr;
  r.kids = kids.length;
  r.back = timers[timers.length - 1][1];
  timers.pop()[0]();
  await null; await null;
  r.after = figure.querySelector().dataset.expr;
  ctx.face(figure, "Atlas", "happy", 2400);
  r.atlas = figure.querySelector().dataset.expr;
  root.dataset.avatarMotion = "off";
  ctx.face(figure, "Sam", "happy", 2400);
  r.off = figure.querySelector().dataset.expr;
  r.near = [...Array(30)].map(() => ctx.near("Sam"));
  r.poked = [...ctx.POKED];
  process.stdout.write(JSON.stringify(r));
})();
"""
    run = subprocess.run(["node", "-e", script, VIEWER], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:]
    out = json.loads(run.stdout)
    assert out["now"] == "laughing" and out["kids"] == 1, "the new face replaces the old once faded in"
    assert out["back"] == 2400 and out["after"] == "", "and its own face comes back"
    assert out["atlas"] == "" and out["off"] == "", "not Atlas, not with Avatar animation off"
    assert set(out["near"]) <= {"happy", "sly", "cute"}
    assert out["poked"][:3] == ["happy", "excited", "laughing"], "more each poke in a row"
    for wired in ("nameMarkViewerFace(figure, seed, NM_VIEWER_POKED[", "nameMarkViewerFace(figure, seed, nameMarkViewerNear(seed), 2600)", "nameMarkViewerNear(seed, true)"):
        assert wired in MENU, wired
