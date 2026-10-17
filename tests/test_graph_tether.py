"""B70 (INBOX 904): a note whose lines go to another category stays within
reach of its own.

The owner: "Why does this node wanna be all the way down there?? The graph
force structuring is still a bit messy." The real worker is run in node on a
fixed notebook (`tests/_graph_worker_harness.js`): three categories of six
densely linked notes, and one Work note whose only lines go to the Travel hub.
Without the leash it came to rest next to Travel; with it, within reach of
Work. The browser half is `scratchpad/ui-sweeps/graph1017-b70.js`.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKER = (ROOT / "frontend" / "js" / "graph-worker.js").read_text(encoding="utf-8")


def _scenario() -> dict:
    nodes = []
    edges = []
    for group in ("Work", "Travel", "Home"):
        ids = [f"{group}-{i}" for i in range(6)]
        nodes += [{"id": i, "r": 7, "group": group} for i in ids]
        edges += [{"source": ids[0], "target": i, "kind": "link"} for i in ids[1:]]
        edges += [{"source": ids[1], "target": ids[2], "kind": "link"}, {"source": ids[3], "target": ids[4], "kind": "link"}]
    nodes.append({"id": "Work-stray", "r": 7, "group": "Work"})
    edges += [{"source": "Work-stray", "target": "Travel-0", "kind": "link"}, {"source": "Work-stray", "target": "Travel-1", "kind": "link"}]
    edges.append({"source": "Work-0", "target": "Home-0", "kind": "link"})
    return {"nodes": nodes, "edges": edges, "ticks": 700}


def _stray_gap(tmp_path: Path) -> tuple[float, float]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    file = tmp_path / "scenario.json"
    scenario = _scenario()
    file.write_text(json.dumps(scenario), encoding="utf-8")
    out = subprocess.run([node, str(ROOT / "tests" / "_graph_worker_harness.js"), str(file)], capture_output=True, text=True, check=True)
    pos = json.loads(out.stdout)["positions"]
    work = [n["id"] for n in scenario["nodes"] if n["group"] == "Work" and n["id"] != "Work-stray"]
    xs = sorted(pos[i][0] for i in work)
    ys = sorted(pos[i][1] for i in work)
    cx, cy = xs[len(xs) // 2], ys[len(ys) // 2]
    reach = max(math.hypot(pos[i][0] - cx, pos[i][1] - cy) for i in work)
    return math.hypot(pos["Work-stray"][0] - cx, pos["Work-stray"][1] - cy), reach


def test_a_bridge_note_stays_within_reach_of_its_own_category(tmp_path: Path) -> None:
    gap, reach = _stray_gap(tmp_path)
    # Measured: 276px against the rest of Work reaching 162 (1.70x) with no
    # leash; 195px (1.20x) with it.
    assert gap <= 1.35 * reach, f"the Work note whose lines all go to Travel stood {gap:.0f}px from Work, whose other notes reach {reach:.0f}"


def test_the_leash_is_a_force_of_the_layout() -> None:
    assert 'force("tether", tetherForce)' in WORKER
    start = WORKER.index("function tetherForce(")
    body = WORKER[start : WORKER.index("tetherForce.initialize", start)]
    assert "node.fx != null" in body, "a pinned note is never moved"
    assert "!node.degree" in body, "a loose note keeps its orbit seat"
