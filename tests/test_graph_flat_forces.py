"""The worker's flat many-body and collide forces are d3-force's, to the last bit (audit 1031 row 19).

They replay d3-quadtree and the two forces on typed arrays so a 2,000-note
layout settles in about two thirds of the time; a different push anywhere would
move every note, so the check is exact equality with d3's own forces on the
same notes, including notes stacked on one spot.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "tests" / "_flat_forces_check.js"

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


@needs_node
def test_flat_forces_match_d3_exactly():
    out = subprocess.run(["node", str(CHECK)], capture_output=True, text=True, timeout=120, check=True)
    diffs = json.loads(out.stdout)
    assert len(diffs) == 10
    assert {k: v for k, v in diffs.items() if v != 0} == {}
