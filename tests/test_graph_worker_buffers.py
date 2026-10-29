"""The layout worker never reads a buffer it did not size for this run (audit G1).

At 2,000 notes and more than `UNTANGLE_MAX_EDGES` links the untangle stage is
skipped; its cleanup used to run anyway and read `untangle.ea`, which was null,
so the worker threw and positions were never saved. The scenario settles with
a cap already passed (the slow-machine branch) at several sizes.
"""

import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "tests" / "_graph_worker_harness.js"

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _scenario(notes: int, links: int) -> dict:
    rng = random.Random(7)
    nodes = [{"id": f"n{i}", "group": f"g{i % 8}", "r": 6} for i in range(notes)]
    edges = []
    while len(edges) < links:
        a, b = rng.randrange(notes), rng.randrange(notes)
        if a != b:
            edges.append({"source": f"n{a}", "target": f"n{b}", "kind": "link"})
    return {"nodes": nodes, "edges": edges, "ticks": 3, "settleCap": True}


@needs_node
@pytest.mark.parametrize(("notes", "links"), [(40, 60), (200, 3900), (2000, 4300), (2000, 0)])
def test_settle_with_a_passed_cap_never_throws(notes, links):
    out = subprocess.run(
        ["node", str(HARNESS)],
        input=json.dumps(_scenario(notes, links)),
        capture_output=True,
        text=True,
        check=True,
        timeout=100,
    ).stdout
    settled = json.loads(out)["settled"]
    assert not settled.startswith("error"), settled
