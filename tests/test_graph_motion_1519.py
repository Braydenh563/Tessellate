"""INBOX 1519: the graph draws and settles only for motion the eye can see.

The owner's log: `raf 125ms on graph: gcRequestDraw 60 calls/s, 2.1ms each`,
draws for about 3 s after open at 36 notes. Three class rules: a frame whose
notes moved under half a pixel is not drawn, a camera glide's sub-pixel steps
are not drawn, and a layout ends when its motion stops rather than at an alpha
floor. The numbers before and after are in the CHANGELOG line.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from tests._app_js import JS_DIR, frontend_text

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(source: str, name: str) -> str:
    return re.search(rf"^function {name}\(.*?^\}}\n", source, re.S | re.M).group(0)


def _node(script: str) -> dict:
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(done.stdout)


@needs_node
def test_a_hot_layout_that_moved_nothing_visible_is_not_drawn_and_a_hand_always_is():
    source = (JS_DIR / "graph-canvas.js").read_text(encoding="utf-8")
    consts = "".join(re.findall(r"^const GC_COOL_\w+ = [\d.]+;\n", source, re.M))
    funcs = "".join(_fn(source, n) for n in ("gcDrawTick", "gcCoolGap", "gcTickDraw", "gcDrawHeld"))
    out = _node(
        "const draws = []; const gcRequestDraw = () => draws.push(1); const performance = { now: () => 0 };\n"
        + consts
        + funcs
        + "const gcCooling = (s) => s.alpha < GC_COOL_ALPHA && !s.dragNode;\n"
        + """
const out = {};
const hot = { alpha: 0.3, transform: { k: 1 } };
for (let i = 0; i < 4; i++) gcTickDraw(hot, i * 16, 0.1);   // 0.4 px in all
out.still = draws.length;
gcTickDraw(hot, 80, 0.1);                                    // 0.5 held: drawn
out.added = draws.length;
gcTickDraw(hot, 96, 3);                                      // a visible step
out.moving = draws.length;
const held = { alpha: 0.3, transform: { k: 1 }, dragNode: { id: 1 } };
gcTickDraw(held, 0, 0);
out.hand = draws.length;
console.log(JSON.stringify(out));
"""
    )
    assert out == {"still": 0, "added": 1, "moving": 2, "hand": 3}


@needs_node
def test_a_camera_within_half_a_pixel_of_the_last_frame_is_still():
    source = (JS_DIR / "graph-canvas.js").read_text(encoding="utf-8")
    consts = "".join(re.findall(r"^const GC_COOL_MOVE_PX = [\d.]+;\n", source, re.M))
    out = _node(
        consts
        + _fn(source, "gcCameraStill")
        + """
const s = { dims: { w: 1000, h: 600 }, drawnCamera: { x: 10, y: 20, k: 1 } };
const at = (x, y, k) => { s.transform = { x, y, k }; return gcCameraStill(s); };
console.log(JSON.stringify({ same: at(10, 20, 1), pan: at(10.4, 20, 1), far: at(11, 20, 1), zoom: at(10, 20, 1.001), zoomed: at(10, 20, 1.0004), none: gcCameraStill({ dims: {}, transform: { x: 0, y: 0, k: 1 } }) }));
"""
    )
    assert out == {"same": True, "pan": True, "far": False, "zoom": False, "zoomed": True, "none": False}


def test_a_programmatic_camera_glide_skips_sub_pixel_frames_and_the_end_draws_the_rest():
    js = frontend_text("graph-canvas.js")
    zoom = js[js.index('.on("zoom", (event) => {') : js.index('.on("end", () => {', js.index('.on("zoom", (event) => {'))]
    assert "if (!event.sourceEvent && gcCameraStill(s)) {" in zoom
    # A person's own pan or zoom is never skipped (the gate is the programmatic glide).
    assert zoom.index("gcCameraStill(s)") < zoom.index("gcRequestMinimapFrame(s);")
    end = js[js.index('.on("end", () => {') :]
    assert "gcRequestDraw(s, true);" in end.split("});")[0]
    draw = js[js.index("function gcDraw(s = gcTab) {") :]
    assert draw.index("s.drawnCamera =") < draw.index("gcLightFrame(s)")


@needs_node
def test_the_worker_calls_a_layout_calm_after_three_quiet_passes_and_not_before():
    worker = (JS_DIR / "graph-worker.js").read_text(encoding="utf-8")
    start = worker.index("const STILL_STEP")
    block = worker[start : worker.index("//: Every message that moves the layout", start)]
    out = _node(
        block
        + """
const nodes = Array.from({ length: 100 }, (_, i) => ({ x: i * 10, y: 0 }));
const out = {};
const step = (d, every = 1) => { nodes.forEach((n, i) => { if (i % every === 0) n.x += d; }); };
out.first = calmPass(nodes, 0.004, false);                   // records only
const quiet = []; for (let i = 0; i < 3; i++) { step(0.1); quiet.push(calmPass(nodes, 0.004, false)); }
out.quiet = quiet;
step(5); out.moved = calmPass(nodes, 0.004, false);          // every note moved 5: count restarts
const few = []; for (let i = 0; i < 3; i++) { step(5, 20); few.push(calmPass(nodes, 0.004, false)); }  // 5 of 100 moving: still calm
out.few = few;
const hot = []; for (let i = 0; i < 4; i++) { step(0.1); hot.push(calmPass(nodes, 0.2, false)); }     // heat still high
out.hot = hot;
const ramp = []; for (let i = 0; i < 4; i++) { step(0.1); ramp.push(calmPass(nodes, 0.004, true)); }   // heat climbing
out.ramp = ramp;
console.log(JSON.stringify(out));
"""
    )
    assert out["first"] is False and out["quiet"] == [False, False, True]
    assert out["moved"] is False and out["few"] == [False, False, True]
    assert not any(out["hot"]) and not any(out["ramp"])


def test_the_worker_asks_the_calm_pass_before_settling_and_a_drag_or_run_restarts_it():
    worker = frontend_text("graph-worker.js")
    loop = worker[worker.index("function loop()") :]
    loop = loop[: loop.index("\n}\n")]
    assert "calmPass(nodes, simulation.alpha(), ramp.n > 0 || shuffle.left > 0)" in loop
    assert re.search(r"settled = !dragging && \(.*overBudget\) \|\| calmed;", loop)
    run = worker[worker.index("function run()") :]
    assert "calm.n = 0;" in run[: run.index("\n}\n")]
