"""The board's hover hit test runs after the frame, not in it (owner-asks-audit-1108.md:20, 1667 f).

`portHover` asks `wbLinkCandidateAt`, which reads the box of every item on the
board. Run inside the animation frame it was the first reader after whatever
else wrote that frame: on a 400-card board at 4x the probe
(a throwaway board-lag sweep) logged 92 to 108 long frames with up to
139 ms of forced layout; after the frame, 2 to 12 and 33 ms at most. Measured in
docs/roadmap/agent-remaining/w34-def1-1111.md.
"""

from __future__ import annotations

from tests._app_js import frontend_text
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WB = frontend_text("whiteboard.js")


def _gate() -> str:
    match = re.search(r"^function wbOnFrame\(.*?^\}", WB, re.S | re.M)
    assert match, "wbOnFrame is gone from whiteboard.js"
    return match.group(0)


def test_only_the_select_hover_waits_for_the_frame_to_draw() -> None:
    assert re.search(r'containerEl\.addEventListener\("pointermove", wbOnFrame\(\(e\) => \{\s*\n\s*if \(wbLinkDragActive\) return;.*?\}, true\), \{ passive: true \}\);', WB, re.S)
    # The port-drag hint keeps the in-frame gate: it follows a held pointer.
    assert re.search(r"const portHints = wbOnFrame\(\(\{ drag, x, y \}\) => \{.*?\n  \}\);", WB, re.S)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_after_runs_in_a_timer_once_with_the_newest_event_and_the_default_runs_in_the_frame() -> None:
    script = f"""
const frames = [], timers = [];
const requestAnimationFrame = (f) => frames.push(f);
const setTimeout = (f) => timers.push(f);
{_gate()}
const late = [], early = [];
const a = wbOnFrame((e) => late.push(e.x), true);
const b = wbOnFrame((e) => early.push(e.x));
a({{ x: 1 }}); a({{ x: 2 }}); b({{ x: 7 }}); b({{ x: 8 }});
frames.splice(0).forEach((f) => f());
const midLate = late.length, midEarly = early.slice();
timers.splice(0).forEach((f) => f());
a({{ x: 3 }});
frames.splice(0).forEach((f) => f());
timers.splice(0).forEach((f) => f());
console.log(JSON.stringify({{ midLate, midEarly, late }}));
"""
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    assert json.loads(run.stdout) == {"midLate": 0, "midEarly": [8], "late": [2, 3]}, run.stdout
