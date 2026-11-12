"""animrecalc-1108 (INBOX 1696 jj, lagjj-1108 targets 3 and 4): where the idle dashboard's style recalcs come from.

Probe (scratchpad of the session, 4x CPU, Atlas companion on, dashboard idle, 8 s trace): every loop
the list names is composited (`getAnimations()` shows transform, rotate, scale and opacity only, on
HTML spans; the only compositor refusals are the eyes' and lids' blink on svg groups, 1 to 3 in 8 s, and
they are short). What costs is the frame count: each main frame restyles every running animation's
element (75 of them, 13 to 20 ms a recalc at 4x, 4 to 5 ms with the loops paused), and the wake sources at
rest are the pacer's coil beat, the tail's calm beat and the rig. So the fix pinned here is the diagnosis
the lag log lacked: a long animation frame names the callback that ran, not the wrapper around it.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from tests._js_scope import unwrapped, unwrapped_copy

ROOT = Path(__file__).resolve().parents[1]
LAG = unwrapped((ROOT / "frontend" / "js" / "lag-watch.js").read_text(encoding="utf-8"))

HARNESS = r"""
const vm = require("vm");
const fs = require("fs");
let now = 0;
const ctx = vm.createContext({ console, navigator: {}, document: { hidden: false, getElementsByTagName: () => [], addEventListener() {} }, window: {}, Error, Map, WeakMap, performance: { now: () => now }, setTimeout: () => 1 });
vm.runInContext("var LAZY_MODULES = {}; var prefs = { get: (k, d) => d, set() {} }; var recordBrowserLog = () => {}; var api = () => Promise.resolve();", ctx);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), ctx);
const input = JSON.parse(fs.readFileSync(0, "utf8"));
console.log(JSON.stringify(vm.runInContext(input.expr, ctx)));
"""


def _run(expr: str):
    result = subprocess.run(
        ["node", "-e", HARNESS, str(ROOT / "frontend" / "js" / "diag-report.js"), str(unwrapped_copy(ROOT / "frontend" / "js" / "lag-watch.js"))],
        input=json.dumps({"expr": expr}),
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return json.loads(result.stdout)


def test_a_wrapper_row_names_the_callback_that_ran_in_its_window() -> None:
    out = _run(
        """(() => {
        LAG_RAF.note("atlas-motion.js atlasRigFrame", 1000, 104);
        LAG_RAF.note("avatars.js tick", 1010, 9);
        LAG_RAF.note("whiteboard.js step", 5000, 60);
        const row = (start, dur) => lagScriptCause([{ duration: dur, sourceURL: "http://h/js/lag-watch.js?v=1", sourceFunctionName: "", invokerType: "user-callback", startTime: start }], { startTime: start, duration: dur });
        return [row(990, 130), row(4990, 70), row(9000, 50)];
        })()"""
    )
    assert out[0].startswith("atlas-motion.js atlasRigFrame 104ms"), out[0]
    assert "whiteboard.js step 60ms" in out[1], "the window picks its own frame's callback, not the last second's top"
    assert out[2].startswith("animation loops (top: "), "no slow callback in the window: the old wording stands"
    assert "lag-watch.js" not in out[0] + out[1]


def test_the_ring_of_slow_callbacks_is_bounded_and_the_wrapper_adds_one_compare() -> None:
    out = _run("""(() => { for (let i = 0; i < 100; i++) LAG_RAF.note("a.js f", i, 5 + i); return LAG_RAF.slow.length; })()""")
    assert out <= 16
    wrap = LAG.split("function lagRafInstall() {", 1)[1].split("\n}\n", 1)[0]
    assert "if (ms >= LAG_RAF.slowMs) LAG_RAF.note(owner, t0, ms);" in wrap
    assert wrap.count("performance.now()") == 2, "no extra clock read in the wrapper"
    assert re.search(r"slowMs: \d+", LAG), "the threshold lives on LAG_RAF: no new global names (test_global_scope_ratchet)"
