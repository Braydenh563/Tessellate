"""The notes rail's spy reads after the frame that drew the change (perf1667-1107 left row).

`notesSpyPick` measures the list's cards. Run straight from its settle timer
it was the first reader after a layout-dirtying change and paid for the layout
itself: 3 to 8 ms (median 4.8) at 4x on the 36-note seed. It now waits for the
frame, so the reads find a clean page: 0.1 to 1.4 ms (median 0.6) in the same
probe (numbers in docs/roadmap/agent-remaining/w34-def1-1111.md). Run in node
with fake timers and frames.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPY = (ROOT / "frontend" / "js" / "notes-rail-spy.js").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def test_the_pick_waits_for_a_frame_after_the_settle_timer() -> None:
    fn = re.search(r"^function notesSpySchedule\(\).*?^\}", SPY, re.S | re.M)
    assert fn, "notesSpySchedule is gone from notes-rail-spy.js"
    script = f"""
const NOTES_SPY_SETTLE_MS = 150;
const notesSpy = {{ timer: 0 }};
const log = [];
const timers = [];
const frames = [];
globalThis.clearTimeout = () => {{}};
globalThis.setTimeout = (fn, ms) => {{ timers.push({{ fn, ms }}); return timers.length; }};
globalThis.afterFrames = (fn, n) => frames.push({{ fn, n }});
const notesSpyPick = () => log.push("pick");
{fn.group(0)}
notesSpySchedule();
log.push("timers " + timers.length + " settle " + timers[0].ms);
timers.shift().fn();
log.push("frames " + frames.length + " n " + frames[0].n);
log.push("after settle timer: " + (log.includes("pick") ? "picked" : "not yet"));
frames.shift().fn();
log.push("after frame: " + (log.includes("pick") ? "picked" : "not yet"));
timers.shift().fn();
process.stdout.write(JSON.stringify(log));
"""
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    assert out == (
        '["timers 1 settle 150","frames 1 n 1","after settle timer: not yet","after frame: not yet","pick"]'
    ), out
