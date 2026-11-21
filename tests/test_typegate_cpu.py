"""The typing gate (L342, L-documents-26) as a load-robust CPU measure.

Wall-clock event durations on a shared box move with other work, so the owner
ruled the gate is read from main-thread CPU, and the hub ruled which number:
CDP Performance.getMetrics ThreadTime deltas per keystroke, and long tasks by
thread CPU (a trace's `tdur`). Not TaskDuration: it counts the waits inside a
task as well as the work, and in a headless browser those are compositor idle
waits (a cold open read ThreadTime 365 ms against TaskDuration 968), so it
moves with the box's load the way wall time does. TaskDuration and
ScriptDuration are printed beside it. The budgets are p95 under 50 ms a key
and no long task over 50 ms, on a 20,000 word document at 4x CPU throttle, in
the Live and Source views. This pins the sweep and its numbers so a later edit
cannot quietly relax them; the live run needs a browser and a served app
(TESSELLATE_TYPEGATE_BASE).
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SWEEP = ROOT / "scratchpad" / "ui-sweeps" / "typegate.js"


def _src() -> str:
    return SWEEP.read_text(encoding="utf-8")


def _const(name: str) -> int:
    m = re.search(rf"^const {name} = (\d+);", _src(), re.M)
    assert m, f"{name} missing from typegate.js"
    return int(m.group(1))


def test_budgets_are_as_ruled():
    assert _const("P95_BUDGET_MS") == 50
    assert _const("LONG_TASK_BUDGET_MS") == 50
    assert _const("THROTTLE") == 4
    assert _const("WORDS") == 20000


def test_reads_cpu_not_wall_clock():
    src = _src()
    for needle in ("Performance.enable", "Performance.getMetrics", '"ThreadTime"', '"TaskDuration"',
                   '"ScriptDuration"', "Tracing.start", "Emulation.setCPUThrottlingRate",
                   "e.tdur ?? e.dur"):
        assert needle in src, needle
    # Both views are gated by default.
    assert re.search(r'VIEWS \|\| "live,source"', src)


def test_fails_the_run_when_the_gate_is_missed():
    src = _src()
    assert "process.exitCode = 1" in src
    # The verdict uses the budgets, not literals that could drift from them.
    assert "cpu.thread.p95 < P95_BUDGET_MS" in src and "cpu(e) > LONG_TASK_BUDGET_MS" in src


def test_node_parses_the_sweep():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    subprocess.run([node, "--check", str(SWEEP)], check=True)


@pytest.mark.skipif(not os.environ.get("TESSELLATE_TYPEGATE_BASE"),
                    reason="live run: set TESSELLATE_TYPEGATE_BASE to a served app")
def test_live_gate_holds():
    env = dict(os.environ, BASE=os.environ["TESSELLATE_TYPEGATE_BASE"],
               PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers"))
    r = subprocess.run(["node", str(SWEEP)], env=env, cwd=ROOT, capture_output=True,
                       text=True, timeout=900)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
