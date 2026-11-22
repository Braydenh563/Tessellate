"""WHITEBOARD_PLAN.md holds no open work: `scripts/open_scan.py` lists nothing in it, and the LEDGER's counts cell for the
whiteboard plan ("Plan file open") says so (2026-11-14 re-ground; what is left is LEDGER rows and BACKLOG entries)."""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = "docs/roadmap/WHITEBOARD_PLAN.md"


def _plan_hits() -> list[str]:
    out = subprocess.run([sys.executable, "scripts/open_scan.py", "--plan", "whiteboard"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.startswith(PLAN + ":")]


def test_the_open_scan_lists_nothing_in_the_plan():
    assert _plan_hits() == []


def test_the_ledger_cell_is_that_count():
    ledger = (ROOT / "docs" / "roadmap" / "LEDGER.md").read_text(encoding="utf-8")
    cell = re.search(r"^\| whiteboard \| (\d+) \|", ledger, re.M)
    assert cell and int(cell.group(1)) == len(_plan_hits()) == 0
