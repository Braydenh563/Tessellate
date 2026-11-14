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


def test_a_new_row_never_reuses_an_id_already_moved_to_history():
    """`add` once reissued L-whiteboard-17 after the closed row had moved to HISTORY
    (2026-11-12): two items shared one id. Ids closed into HISTORY stay taken."""
    taken = ledger.taken_ids("whiteboard", "", "- [x] **L-whiteboard-17** `whiteboard` open, S: done.\n")
    assert 17 in taken
    assert ledger.next_id("whiteboard", "- [ ] **L-whiteboard-3** x\n", "- [x] **L-whiteboard-17** x\n") == "L-whiteboard-18"


def test_add_numbers_past_the_ids_in_history(tmp_path, monkeypatch):
    """`ledger.py add` numbered from the LEDGER alone, so once every timeline row was done and
    moved to HISTORY it handed out L-timeline-1 again (2026-11-13), an id code comments cite."""
    import argparse
    import importlib.util

    spec = importlib.util.spec_from_file_location("ledger_cli", ROOT / "scripts" / "ledger.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    ledger, history = tmp_path / "LEDGER.md", tmp_path / "HISTORY.md"
    ledger.write_text("## timeline\n\n", encoding="utf-8")
    history.write_text("## Moved from the LEDGER\n- [x] **L-timeline-4** `timeline` open, S: old.\n", encoding="utf-8")
    monkeypatch.setattr(cli, "LEDGER", ledger)
    monkeypatch.setattr(cli, "HISTORY", history)
    args = argparse.Namespace(plan="timeline", status="open", size="S", src="a test", evidence=None, title="New row")
    assert cli.add(args) == "L-timeline-5"


def test_the_counts_table_has_one_row_per_plan():
    """A union merge once left 38 `| all |` rows, which flooded orient.sh past its 40 lines."""
    names = [m.group(1) for m in ledger.COUNT.finditer(TEXT)]
    assert len(names) == len(set(names)), sorted({n for n in names if names.count(n) > 1})


def test_a_plan_with_nothing_open_counts_zero_in_its_plan_file():
    """The "Plan file open" column is carried by hand; graph kept 15 after its plan closed.

    A plan with no LEDGER rows and no open-work line in its plan file has
    nothing open there, so its count must be 0.
    """
    import open_scan

    counts = ledger.table(TEXT)
    stale = {}
    for plan, owned in open_scan.OWNERS.items():
        plan_file = owned[0]
        if any(p == plan for _, p, _ in ledger.rows(TEXT)) or open_scan.hits([plan_file]):
            continue
        if counts[plan][0]:
            stale[plan] = counts[plan][0]
    assert not stale, stale
