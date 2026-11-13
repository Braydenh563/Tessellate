"""One place for open work (INBOX 1784, the owner 2026-11-12: "EVERYTHING OPEN
PUT INTO ONE SPOT ... NO MULTIPLE FILES, NO MISSED OPEN STUFF ... OTHER THAN
THE PLAN FILES AND THE BACKLOG").

Open items outside the plans and BACKLOG live only in docs/roadmap/LEDGER.md,
one row each with a plan tag; INBOX is intake, so an item triaged out of it
names where it went; and a "ready to merge" claim in HANDOVER holds only when
the plans it names have no open LEDGER rows left (owner calls and hardware
rows aside, since no session can close them).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROADMAP = ROOT / "docs" / "roadmap"
sys.path.insert(0, str(ROOT / "scripts"))
import ledger  # noqa: E402

TEXT = (ROADMAP / "LEDGER.md").read_text(encoding="utf-8")

#: The only files under docs/roadmap/. A new one is how open work scattered
#: across agent-remaining (about 980 files) and nine retired docs before.
ALLOWED = {"BACKLOG.md", "HANDOVER.md", "HISTORY.md", "INBOX.md", "LEDGER.md"}


def test_open_work_has_no_second_home():
    stray = sorted(
        p.relative_to(ROADMAP).as_posix()
        for p in ROADMAP.rglob("*")
        if p.is_file() and p.name not in ALLOWED and not p.name.endswith("_PLAN.md")
    )
    assert not stray, f"open work belongs in LEDGER.md, a plan or BACKLOG, not {stray}"


def test_every_row_is_well_formed_and_unique():
    rows = ledger.rows(TEXT)
    assert len(rows) > 0
    ids = [r[0] for r in rows]
    assert len(ids) == len(set(ids)), "two LEDGER rows share an id"
    for rid, plan, status in rows:
        assert plan in ledger.PLANS, f"{rid}: unknown plan tag {plan}"
        assert status in ledger.STATUSES, f"{rid}: unknown status {status}"
    # A row that starts like a row but misses the shape (plan tag, status, size).
    loose = [ln for ln in TEXT.splitlines() if ln.startswith("- [") and not ledger.ROW.match(ln + "\n")]
    assert not loose, f"malformed rows: {loose[:3]}"


def test_a_done_row_leaves_the_ledger():
    """A built row moves to HISTORY with its evidence (`ledger.py done`); a
    ticked or struck row left here is the plans' old failure again (order 10)."""
    assert not re.search(r"^- \[x\]|^- ~~", TEXT, re.M)


def test_the_counts_table_matches_the_rows():
    stated = {
        m.group(1): tuple(int(x) for x in m.groups()[1:])
        for m in re.finditer(r"^\| ([a-z-]+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|$", TEXT, re.M)
    }
    assert stated == ledger.table(TEXT), "run `python scripts/ledger.py counts`"


def test_every_triaged_inbox_item_names_its_home():
    inbox = (ROADMAP / "INBOX.md").read_text(encoding="utf-8")
    block = inbox.split("## Open items", 1)[1].split("\n## ", 1)[0]
    items = re.findall(r"(?ms)^(\d+)\. (.*?)(?=^\d+\. |\Z)", block)
    homeless = [n for n, body in items if "Placed" in body and not re.search(r"LEDGER L[\w-]+|_PLAN|BACKLOG|HISTORY", body)]
    assert not homeless, f"INBOX items placed with no LEDGER id or plan: {homeless}"


def test_ready_to_merge_only_with_no_open_rows():
    handover = (ROOT / "docs" / "roadmap" / "HANDOVER.md").read_text(encoding="utf-8")
    now = re.search(r"^\*\*Now \(.*$", handover, re.M)
    assert now, "HANDOVER has no Now line"
    line = now.group(0)
    if not re.search(r"ready (to|for) merge", line, re.I):
        return
    named = [p for p in ledger.PLANS if f"`{p}`" in line] or list(ledger.PLANS)
    left = [rid for rid, plan, status in ledger.rows(TEXT) if plan in named and status in ("open", "partly")]
    assert not left, f"Now says ready to merge, but LEDGER still has {len(left)} open rows ({left[:5]})"


def test_add_never_reuses_an_id_already_closed_into_history(tmp_path, monkeypatch):
    """`add` once reused L-documents-29, whose row had moved to HISTORY."""
    import argparse
    import ledger as tool

    led, hist = tmp_path / "LEDGER.md", tmp_path / "HISTORY.md"
    led.write_text("## documents\n- [ ] **L-documents-3** `documents` open, S: a. From x.\n", encoding="utf-8")
    hist.write_text("- [x] **L-documents-9** `documents` open, S: b. From x.\n", encoding="utf-8")
    monkeypatch.setattr(tool, "LEDGER", led)
    monkeypatch.setattr(tool, "HISTORY", hist)
    a = argparse.Namespace(plan="documents", status="open", size="S", src="y", evidence="", title="c")
    assert tool.add(a) == "L-documents-10"


def test_the_counts_table_has_one_row_per_plan():
    """A union merge once left 38 `| all |` rows, which flooded orient.sh past its 40 lines."""
    names = [m.group(1) for m in ledger.COUNT.finditer(TEXT)]
    assert len(names) == len(set(names)), sorted({n for n in names if names.count(n) > 1})
