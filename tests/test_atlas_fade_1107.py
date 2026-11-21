"""The companion's CSS loops are not created under its entrance fade (atlasfade-1107).

On the reload path `#nm-buddy` is `nmb-away` (opacity 0, hidden) and then
faded up from opacity 0 while its figure is built. Chromium refuses to
composite an animation whose box is empty at the moment it is created
(compositeFailed bit 17) and never retries, so every CSS loop of the figure
created then (22 on the boot trace: the orbit arms and planets, the stream,
hair, tail and dress drifts, the shimmer) ran on the main thread, and every
restyle restyled them. The figure now carries `atl-lit` once its companion
shows (`atlasWhenShown` in atlas.js, which also holds back the ring, pose and
tail animations the lazy life module makes), and until then a rule in the boot
sheet keeps every animation name off its boxes.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
ATLAS = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    match = re.search(rf"^function {name}\(.*?^\}}", ATLAS, re.S | re.M)
    assert match, f"{name} is gone from atlas.js"
    return match.group(0)


def test_an_unlit_figure_holds_every_animation_name_in_the_boot_sheet() -> None:
    rule = re.search(
        r"\.atl-figure-box:not\(\.atl-lit\), \.atl-figure-box:not\(\.atl-lit\) \*,\s*:where\(:root\[data-motion=\"reduced\"\][^{]*\{ animation: none !important; \}",
        CSS,
    )
    assert rule, "one rule: the box and everything in it, animation none, until atl-lit (the reduced-motion orbit rule rides it, as test_atlas_shape reads it)"
    # Boot CSS, not the lazy faces: the orbit and drift loops are written here and
    # are created the moment the figure is drawn, before atlas-lazy.css arrives.
    assert ".atl-figure-box:not(.atl-lit)" not in (ROOT / "frontend" / "css" / "atlas-lazy.css").read_text(encoding="utf-8")


def test_the_gate_shares_the_one_animation_none_important_rule() -> None:
    # Pausing is not enough: a paused animation is still created, and refused,
    # under the fade. And the !important ratchet (test_style_scale) does not
    # grow: the gate rides the rule that already stops the orbits.
    rule = re.search(r"\.atl-figure-box:not\(\.atl-lit\)[^{]*\{([^}]*)\}", CSS)
    assert rule and rule.group(1).strip() == "animation: none !important;"
    assert "atlas-lazy" not in rule.group(0)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_figure_waits_for_its_companion_to_show_and_a_loose_one_does_not() -> None:
    script = (
        _fn("atlasWhenShown")
        + """
let opacity = "0";
globalThis.getComputedStyle = () => ({ opacity });
const frames = [];
globalThis.requestAnimationFrame = (f) => frames.push(f);
// the rig's own frame scheduler (atlas-motion.js)
const atlasRigWake = { after: (cb, n) => requestAnimationFrame((t) => (n > 1 ? atlasRigWake.after(cb, n - 1) : cb(t))) };
const flush = () => { const f = frames.splice(0); f.forEach((g) => g(0)); };
const set = new Set();
const make = (inBuddy, away, connected = true) => {
  const buddy = { classList: { contains: (c) => c === "nmb-away" && away } };
  const box = { isConnected: connected, classList: { contains: (c) => set.has(c) }, closest: (s) => (inBuddy && s === "#nm-buddy" ? buddy : null) };
  const log = [];
  atlasWhenShown(box, () => log.push("go"));
  return { box, log };
};
const loose = make(false, false);
const away = make(true, true);
const early = [loose.log.length, away.log.length, frames.length, typeof away.box.atlasShow];
// a wake (the away class comes off) looks again: still opacity 0, so it waits three frames at a time
const fading = make(true, false);
const queued = frames.length;
flush(); flush();
const mid = fading.log.length;
flush();
const stillWaiting = [fading.log.length, frames.length];
// the fade's first frame passes
opacity = "0.03";
flush(); flush(); flush();
const late = [fading.log.length, frames.length, fading.box.atlasShow];
// a wake after it went does nothing more
set.add("atl-lit");
fading.box.atlasShow && fading.box.atlasShow();
// a figure dropped from the page before its companion showed gives up (it would look
// every three frames for good), but waits while it is only not yet attached
set.delete("atl-lit");
opacity = "0";
frames.length = 0;
const lost = make(true, false, false);
let looks = 0;
while (frames.length && looks < 400) { flush(); looks++; }
const dropped = [lost.log.length, frames.length, lost.box.atlasShow, looks < 400];
const attaching = make(true, false, false);
for (let i = 0; i < 30; i++) flush();
const youngWaits = [attaching.log.length, frames.length > 0, typeof attaching.box.atlasShow];
process.stdout.write(JSON.stringify({ early, queued, mid, stillWaiting, late, after: fading.log.length, dropped, youngWaits }));
"""
    )
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert out["early"] == [1, 0, 0, "function"], "a figure outside the companion goes at once; away, it waits for the rig's wake and queues no frame"
    assert out["queued"] == 1 and out["mid"] == 0, "fading in at opacity 0: one look every three frames"
    assert out["stillWaiting"][0] == 0, "still opacity 0 on the fade's first frame: it goes on waiting"
    assert out["late"][0] == 1 and out["late"][1] == 0 and out["late"][2] is None, "goes once, on the first frame the companion shows, and asks for no more frames"
    assert out["after"] == 1, "never twice"
    assert out["dropped"] == [0, 0, None, True], "removed before the companion showed: it stops looking, and never lights"
    assert out["youngWaits"] == [0, True, "function"], "not yet attached is not removed: the settle wait gives it time"


def test_the_rig_wake_looks_again_for_a_figure_that_waits() -> None:
    motion = (ROOT / "frontend" / "js" / "atlas-motion.js").read_text(encoding="utf-8")
    wake = re.search(r"^function atlasRigWake\(.*?^\}", motion, re.S | re.M)
    assert wake and "if (box?.atlasShow) atlasRigWake.after(box.atlasShow, 3);" in wake.group(0)
    # and no new observer or frame loop of atlas.js's own for it (test_frontend_wake_sources)
    assert "MutationObserver" not in _fn("atlasWhenShown") and "requestAnimationFrame" not in _fn("atlasWhenShown")


def test_everything_the_life_module_makes_waits_for_the_companion_and_the_loops_are_lit_with_it() -> None:
    figure = _fn("atlasFigure")
    body = re.search(r'ensureModule\("atlasLife"\)\.then\(\(ok\) => atlasWhenShown\(figure, \(\) => \{(.*?)\n  \}\)\);', figure, re.S)
    assert body, "the life module's attach rides atlasWhenShown"
    steps = body.group(1)
    assert steps.index('figure.classList.add("atl-lit")') < steps.index("if (!ok) return;") < steps.index("atlasRigLowerAttach(figure)")
    for made in ("atlasRingLoops(figure)", "atlasPropLoops(figure)", "atlasTailAttach(figure)"):
        assert made in steps, f"{made} is made after the companion shows"
