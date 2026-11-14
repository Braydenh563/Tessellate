"""The chat plan holds no open work of its own (the hub, 2026-11-14: "every
unbuilt item is now a row"). The recount of CHAT_PLAN.md from its text filed
each partly or unbuilt item as a LEDGER row, so the LEDGER counts table says 0
for the plan file, and any line that still reads as open names its row.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import open_scan  # noqa: E402

LEDGER = (ROOT / "docs" / "roadmap" / "LEDGER.md").read_text(encoding="utf-8")
ROW_ID = re.compile(r"\bL(?:-chat-)?\d+\b")


def test_chat_plan_file_open_cell_is_zero():
    row = re.search(r"^\| chat \| (\d+) \|", LEDGER, re.M)
    assert row and row.group(1) == "0", "CHAT_PLAN open work belongs in LEDGER rows; recount before changing the cell"


def test_every_open_reading_plan_line_names_its_ledger_row():
    lines = (ROOT / "docs" / "roadmap" / "CHAT_PLAN.md").read_text(encoding="utf-8").splitlines()
    hits = [lines[i - 1] for _, i, _ in open_scan.hits(["docs/roadmap/CHAT_PLAN.md"])]
    unnamed = [line[:80] for line in hits if not ROW_ID.search(line)]
    assert not unnamed, unnamed
    ids = {m for line in hits for m in ROW_ID.findall(line)}
    missing = [i for i in ids if f"**{i}**" not in LEDGER]
    assert not missing, f"named rows not in LEDGER: {missing}"
