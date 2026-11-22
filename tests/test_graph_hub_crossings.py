"""INBOX 1306 and W34 "Hub crossings": the owner's default 40-note graph had a hub
whose lines crossed everything. The check the plan names: 36-note seeds with
two hubs, counted with the shipped worker under node (no browser), crossings
on the hubs' lines down by at least a third with no two notes overlapping.

Before this change, ten seeds of each shape measured 90 hub crossings
(links mostly inside a category) and 256 (links ignoring categories); after,
44 and 150 (a counter clock, `clockStep`, so a loaded machine buys the same
work; edges sorted, so the hash seed cannot reorder them). Two parts did it: the least crossed layout of the passes is the
one cleaned (`untangleKeepBest`, a relax gave back most of a pass), and a
hub's neighbours are dealt into their spots in the order their other lines
lead (`untangleOrderSteps`)."""

from __future__ import annotations

import json
import math
import random
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tests" / "_graph_worker_harness.js"
WORKER = ROOT / "frontend" / "js" / "graph-worker.js"
HUBS = ("n0", "n1")
CATS = ["Work", "Reading", "Ideas", "Personal", "Research"]


def _seed(k: int, mixed: bool) -> dict:
    r = random.Random(k)
    nodes = [{"id": f"n{i}", "group": CATS[i % 5], "r": 7} for i in range(36)]
    edges = set()
    for h, hub in enumerate(HUBS):
        same = [j for j in range(2, 36) if j % 5 == h]
        other = [j for j in range(2, 36) if j % 5 != h]
        for j in r.sample(same, 5) + r.sample(other, 7 if mixed else 3):
            edges.add((hub, f"n{j}"))
    for _ in range(26):
        a = r.choice(range(2, 36))
        b = r.choice([j for j in range(2, 36) if j != a and (mixed or j % 5 == a % 5 or r.random() < 0.2)])
        edges.add((f"n{a}", f"n{b}"))
    edges.add(HUBS)
    return {"nodes": nodes, "edges": [{"source": a, "target": b, "kind": "link"} for a, b in sorted(edges)], "ticks": 600, "clockStep": 0.001}


def _crosses(p, q, s, t) -> bool:
    def o(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    return o(p, q, s) * o(p, q, t) < 0 and o(s, t, p) * o(s, t, q) < 0


def _measure(mixed: bool) -> tuple[int, int]:
    hub = overlaps = 0
    for k in range(10):
        scenario = _seed(k, mixed)
        out = subprocess.run(
            ["node", str(HARNESS)], input=json.dumps(scenario), capture_output=True, text=True, check=True, timeout=60
        ).stdout
        at = json.loads(out)["positions"]
        lines = [(e["source"], e["target"]) for e in scenario["edges"]]
        for i, (a, b) in enumerate(lines):
            for c, d in lines[i + 1 :]:
                if len({a, b, c, d}) == 4 and set(HUBS) & {a, b, c, d} and _crosses(at[a], at[b], at[c], at[d]):
                    hub += 1
        ids = list(at)
        overlaps += sum(1 for i, a in enumerate(ids) for b in ids[i + 1 :] if math.dist(at[a], at[b]) < 14)
    return hub, overlaps


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
@pytest.mark.parametrize(("mixed", "before"), [(False, 90), (True, 256)])
def test_hub_crossings_fall_by_a_third_with_no_overlaps(mixed: bool, before: int) -> None:
    hub, overlaps = _measure(mixed)
    assert hub <= before * 2 / 3, (hub, before)
    assert overlaps == 0


def test_the_passes_keep_their_least_crossed_layout_and_order_the_fans() -> None:
    worker = WORKER.read_text(encoding="utf-8")
    assert "function untangleKeepBest()" in worker and "function untangleTakeBest()" in worker
    assert "gained += yield* untangleOrderSteps(i, still, until);" in worker
