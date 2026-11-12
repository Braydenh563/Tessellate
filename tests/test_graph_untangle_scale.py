"""W34 "Incremental crossing count per turned category": at 2,000 notes the
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
past 16 lines (`crossingsGridded`, tests/test_graph_crossings_grid.py)."""

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
