"""WORLD_CLASS_PLAN holds no open work (owner, 2026-11-14).

Every item became a LEDGER row, a dated decision, or a block moved to HISTORY
(recount 2026-11-14). The plan cell of the counts table stays 0, and
open_scan finds nothing in the plan file.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_counts_table_has_no_plan_file_items() -> None:
    text = (ROOT / "docs" / "roadmap" / "LEDGER.md").read_text(encoding="utf-8")
    row = re.search(r"^\| world-class \| (\d+) \|", text, re.M)
    assert row and row.group(1) == "0"


def test_open_scan_finds_nothing_in_the_plan() -> None:
    out = subprocess.run(
        [sys.executable, "scripts/open_scan.py", "--plan", "world-class"],
        cwd=ROOT, capture_output=True, text=True, timeout=120, check=False,
    ).stdout
    hits = [line for line in out.splitlines() if "WORLD_CLASS_PLAN.md:" in line]
    assert not hits, hits
