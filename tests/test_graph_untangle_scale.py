"""Source text: part of this reads the shipped CSS, markup or script, whose effect needs a browser this suite does not run; what was measured in the app is below.

W34 "Incremental crossing count per turned category": at 2,000 notes the
crossing count was 96% of the untangle pass and the pass gained nothing.
Measured with the shipped worker under node (`scratchpad/hub/size.py`, gain as a
share of the crossings, 1.9 links a note, seven categories):

    notes        120   200   300   500   800   1,200   2,000
    before       8.6%  5.6%  13.7% 0%    0%    0%      0%
    after        19%   18.7% 15.3% 8.6%  3.2%  (1.2%)  (0.5%)

A category's turn past `UNTANGLE_TURN_LINES` lines never won and spent the
budget, so it is left to the per-note moves; past `UNTANGLE_PASS_NOTES` the
passes are skipped (the bracketed gains, for three 600 ms passes) and only the
cleanup runs. The 2,000-note settle went from 5.7 s to 3.4 s under node with
the count out of the profile's top ten; the count itself uses a grid of lines
past 16 lines (`crossingsGridded`, tests/test_graph_crossings_grid.py).

L-graph-18, the same 2,000 notes under node with the counter clock (three runs
each, wall time of the whole harness): the cleanup's "which notes meet" scan
(2M pairs) called `collideRadius` four million times and took a root per pair;
radii read once and the square test first took it from 8.9 s to 8.0 s median
(`collideRadius` 260 ms self time to nothing) with byte-identical positions.
Browser, 4x CPU throttle, worker start to end on the 2,000-note fixture: 5.3 s
median (5.6, 4.6, 5.3) before this commit; it was 11 to 14 s before the untangle
gates. Tried and left: `theta` 1.6 at 1,000+ notes saved 146 ms of charge self
time but added 2% crossings; skipping cells wholly past `distanceMax` saved
nothing (the theta test already ends those descents)."""

from __future__ import annotations

import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tests" / "_graph_worker_harness.js"
WORKER = (ROOT / "frontend" / "js" / "graph-worker.js").read_text(encoding="utf-8")
CATS = ["Work", "Reading", "Ideas", "Personal", "Research", "Health", "Travel"]


def _seed(n: int) -> dict:
    r = random.Random(n)
    edges = set()
    while len(edges) < int(n * 1.9):
        a = r.randrange(n)
        b = r.randrange(n) if r.random() < 0.25 else (a + 7 * r.randint(1, 4)) % n
        if a != b:
            edges.add((min(a, b), max(a, b)))
    return {
        "nodes": [{"id": f"n{i}", "group": CATS[i % 7], "r": 7} for i in range(n)],
        "edges": [{"source": f"n{a}", "target": f"n{b}", "kind": "link"} for a, b in sorted(edges)],
        "ticks": 3000,
        "clockStep": 0.05,
    }


def _untangled(n: int) -> dict:
    out = subprocess.run(["node", str(HARNESS)], input=json.dumps(_seed(n)), capture_output=True, text=True, check=True, timeout=120)
    return json.loads(out.stdout)["untangled"]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_500_note_map_gains_from_the_passes_and_a_1200_note_map_skips_them() -> None:
    mid = _untangled(500)
    assert mid["gain"] >= 0.05 * mid["total"], mid  # 0 before: the category turns spent the budget
    big = _untangled(1200)
    assert big.get("total") is None, big  # no pass ran
    assert big["passes"] > 0  # so the cleanup still runs


def test_the_turn_and_the_passes_are_gated_by_size() -> None:
    turns = WORKER[WORKER.index("function* untangleGroupsSteps(") :]
    assert "lines.length > UNTANGLE_TURN_LINES) continue;" in turns[: turns.index("\n}\n")]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_cleanup_scan_reads_each_radius_once_and_a_2000_note_map_keeps_its_dots_apart() -> None:
    scan = WORKER[WORKER.index("function* untangleCleanupSteps(") :]
    scan = scan[: scan.index("\n}\n")]
    assert "nodes.map(collideRadius)" in scan
    assert "spread(nodes[" not in scan  # a call per pair was 4 million at 2,000 notes
    seed = _seed(2000)
    out = subprocess.run(["node", str(HARNESS)], input=json.dumps(seed), capture_output=True, text=True, check=True, timeout=120)
    at = json.loads(out.stdout)["positions"]
    pts = list(at.values())
    cell: dict[tuple[int, int], list[list[float]]] = {}
    for p in pts:
        cell.setdefault((int(p[0] // 20), int(p[1] // 20)), []).append(p)
    close = 0
    for (cx, cy), here in cell.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for p in here:
                    for q in cell.get((cx + dx, cy + dy), []):
                        if p is not q and (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 < 14 * 14:
                            close += 1
    assert close // 2 <= 35, close  # 35 dots closer than 2r before and after this change
