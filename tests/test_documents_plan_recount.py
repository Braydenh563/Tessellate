"""The documents plan holds no open work of its own (the hub, 2026-11-14:
"turn each of those 20 into a row ... so the plan cell is 0 and pinned by a
test"). The 20 from scratchpad/docs-audit-1114.md section 1 are rows
(L-documents-6, 11, 46 to 62, 79), so the LEDGER counts table says 0 for the
plan file, and the scanner finds nothing open in the plan or its code.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import open_scan  # noqa: E402

LEDGER = (ROOT / "docs" / "roadmap" / "LEDGER.md").read_text(encoding="utf-8")


def test_documents_plan_file_open_cell_is_zero():
    row = re.search(r"^\| documents \| (\d+) \|", LEDGER, re.M)
    assert row and row.group(1) == "0", "DOCUMENTS_PLAN open work belongs in LEDGER rows; recount before changing the cell"


def test_nothing_in_the_documents_scope_reads_as_open():
    paths = [f for f in open_scan.files() if f.startswith(open_scan.OWNERS["documents"])]
    assert open_scan.hits(paths) == []


def test_every_row_the_plan_names_is_in_the_ledger_or_history():
    plan = (ROOT / "docs" / "roadmap" / "DOCUMENTS_PLAN.md").read_text(encoding="utf-8")
    history = (ROOT / "docs" / "roadmap" / "HISTORY.md").read_text(encoding="utf-8")
    named = set(re.findall(r"\bL-documents-\d+\b", plan))
    missing = [i for i in named if f"**{i}**" not in LEDGER and f"**{i}**" not in history]
    assert not missing, missing
