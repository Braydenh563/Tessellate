"""A restored layout opens where it was left (audit 1029 G6).

GRAPH_PLAN decision 2026-10-27, the map opens settled: positions kept from the
last rest start the worker at alpha 0, and nothing may move them until a real
change (data, filter, physics) heats the layout. Measured before
(`graphlag.js drift`, 500 notes): after a reload every note moved, RMS 99 px,
max 339 px, because a fresh `init` owed the untangle passes and their relax
again, so the cleanup ran over a map that had already had it.
"""

import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tests" / "_graph_worker_harness.js"
WORKER = (ROOT / "frontend" / "js" / "graph-worker.js").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _run(scenario: dict) -> dict:
    out = subprocess.run(
        ["node", str(HARNESS)], input=json.dumps(scenario), capture_output=True, text=True, check=True, timeout=90
    ).stdout
    return json.loads(out)


def _map() -> tuple[list, list]:
    # Crossing links on purpose: a map the untangle would want to change.
    nodes = [{"id": i, "group": f"g{i % 4}", "r": 7} for i in range(40)]
    edges = [{"source": i, "target": (i * 7 + 3) % 40, "kind": "link"} for i in range(40)]
    return nodes, edges


@needs_node
def test_a_restored_layout_does_not_move():
    nodes, edges = _map()
    # Positions as a reload brings them back: rounded, so the restore is not
    # the exact float rest the worker ended on.
    rest = _run({"nodes": nodes, "edges": edges, "ticks": 600})["positions"]
    seeded = [{**n, "x": round(rest[str(n["id"])][0]), "y": round(rest[str(n["id"])][1])} for n in nodes]
    out = _run({"nodes": seeded, "edges": edges, "ticks": 600, "alpha": 0})
    worst = max(
        math.hypot(out["positions"][str(n["id"])][0] - n["x"], out["positions"][str(n["id"])][1] - n["y"])
        for n in seeded
    )
    assert worst < 0.5, f"a restored note moved {worst:.1f} px"
    # And it says it is at rest straight away, so the page saves and frames once.
    assert out["endedAt"] == 0
    assert out["firstAlpha"] == 0


def test_heating_after_a_restore_still_runs_the_layout():
    # The hold must not freeze the simulation: a drag, a reheat or a pin after
    # a restore steps it as before.
    for case, nxt in (('case "reheat":', 'case "reshuffle":'), ('case "pin": {', 'case "unpin": {')):
        block = WORKER[WORKER.index(case) : WORKER.index(nxt)]
        assert "run()" in block
