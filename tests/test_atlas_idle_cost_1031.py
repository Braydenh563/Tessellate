"""The companion at rest costs what it shows (audit 2026-10-31, AI1 and HR1).

With the companion on, the Chat tab at rest ran about 65 to 130 animations:
at 4x CPU 5 long tasks and 540 ms blocked per 5 s, and the same animations
kept running while the companion was faded out on every other tab. Three
rules, each a fixed clock and fakes:

- an away companion (`nmb-away`) is not "may move" (`atlasMotionOK`), so
  every loop that asks rests;
- a slow frame budget (`atlasFrameBudget`) sets `data-atlas-lite` once the
  frames it timed run long, and never when they run well;
- the arm probe's animation state comes from its events, not a
  `getAnimations()` scan per arm per frame.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
MOTION = (JS / "atlas-motion.js").read_text(encoding="utf-8")
LIFE = (JS / "atlas-life.js").read_text(encoding="utf-8")
LAZY = (ROOT / "frontend" / "css" / "atlas-lazy.css").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(src: str, name: str) -> str:
    match = re.search(rf"^function {name}\(.*?^\}}", src, re.S | re.M)
    assert match, name
    return match.group(0)


def _node(script: str):
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout)


@needs_node
def test_an_away_companion_may_not_move() -> None:
    out = _node(
        r"""
const root = { dataset: {}, attrs: new Set(), hasAttribute(k) { return this.attrs.has(k); } };
globalThis.document = { documentElement: root };
globalThis.matchMedia = () => ({ matches: false });
const ATLAS_REDUCE_QUERY = null;
"""
        + _fn(MOTION, "atlasMotionOK")
        + r"""
const buddy = (away) => ({ classList: { contains: (c) => c === "nmb-away" && away } });
const box = (b) => ({ closest: () => b });
process.stdout.write(JSON.stringify({ here: atlasMotionOK(box(buddy(false))), away: atlasMotionOK(box(buddy(true))), figure: atlasMotionOK(box(null)) }));
"""
    )
    assert out == {"here": True, "away": False, "figure": True}


def _budget(frame_ms: float, hidden: bool = False) -> dict:
    return _node(
        r"""
const attrs = new Set();
const root = { setAttribute(k) { attrs.add(k); }, hasAttribute(k) { return attrs.has(k); } };
let t = 1000;
let queue = [];
globalThis.document = { documentElement: root, hidden: %s, querySelector: () => null };
globalThis.setTimeout = (fn) => fn();
globalThis.requestAnimationFrame = (fn) => queue.push(fn);
"""
        % json.dumps(hidden)
        + re.search(r"^const atlasBudget = .*;$", LIFE, re.M).group(0)
        + _fn(LIFE, "atlasFrameBudget")
        + r"""
atlasFrameBudget(t);
for (let i = 0; i < 400 && queue.length; i += 1) { t += %s; queue.shift()(t); }
process.stdout.write(JSON.stringify({ lite: attrs.has("data-atlas-lite") }));
"""
        % frame_ms
    )


@needs_node
def test_slow_frames_set_the_lite_flag_and_good_ones_do_not() -> None:
    assert _budget(16.7) == {"lite": False}
    assert _budget(28) == {"lite": True}
    assert _budget(40) == {"lite": True}


@needs_node
def test_a_hidden_tab_is_not_timed() -> None:
    assert _budget(60, hidden=True) == {"lite": False}


def test_the_lite_and_away_sets_pause_by_one_rule() -> None:
    rule = re.search(r"(:root\[data-atlas-lite\] \.atl-figure-box :is\([^)]*\),\s*#nm-buddy\.nmb-away :is\([^)]*\),\s*#nm-buddy\.nm-buddy-dragging :is\([^)]*\)) \{ animation-play-state: paused !important; \}", LAZY)
    assert rule, "lite, away and dragging share one `!important` (the ratchet)"
    for kept in ("atl-idle-sway", "atl-lw-body", "atl-lw-breathe"):
        assert kept not in rule.group(1).split("#nm-buddy.nmb-away")[0], f"{kept} keeps running in the lite set"
    assert ":root[data-atlas-lite] .atl-orbiter :is(.atl-orbiter-glow, .atl-orbiter-swirl) { display: none; }" in LAZY


def test_the_ring_loops_rest_in_the_lite_set() -> None:
    frame = _fn(LIFE, "atlasTailFrame")
    assert 'hasAttribute("data-atlas-lite")' in frame
    assert "atlasFrameBudget(now)" in frame


def test_the_arm_probe_is_read_from_events_not_scanned_each_frame() -> None:
    frame = _fn(MOTION, "atlasRigFrame")
    assert "getAnimations" not in frame
    assert "arm.running.size > 0" in frame
    watch = _fn(MOTION, "atlasProbeWatch")
    for event in ("animationstart", "animationend", "animationcancel"):
        assert event in watch
