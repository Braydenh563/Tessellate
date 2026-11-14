"""Keep docs/roadmap/LEDGER.md in shape: add a row, close a row, recount.

    python scripts/ledger.py add --plan graph --status open --size S \
        --src "INBOX 1790" --evidence "graph-canvas.js:120 draws every label" "Gate labels by zoom"
    python scripts/ledger.py done L12 "built in abc1234, tests/test_x.py"
    python scripts/ledger.py counts

New rows get `L-<plan>-<n>` ids so parallel plan sessions never pick the same
number (INBOX 1784). `done` moves the row to HISTORY.md, "Moved from the
LEDGER", with its evidence, and recounts; `tests/test_ledger.py` checks the
counts table against the rows.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "docs" / "roadmap" / "LEDGER.md"
HISTORY = ROOT / "docs" / "roadmap" / "HISTORY.md"
PLANS = ("graph", "chat", "whiteboard", "documents", "mindmap", "ui-modernisation", "timeline", "world-class", "general")
STATUSES = ("open", "partly", "owner-call", "blocked-hardware")
ROW = re.compile(r"^- \[ \] \*\*(L[\w-]+)\*\* `([a-z-]+)` ([a-z-]+), ([SML]): ", re.M)
COUNT = re.compile(r"^\| ([a-z-]+) \| (\d+) \| \d+ \| \d+ \| \d+ \| \d+ \| \d+ \|$", re.M)
HISTORY_HEAD = "## Moved from the LEDGER"


def rows(text: str) -> list[tuple[str, str, str]]:
    return [(m.group(1), m.group(2), m.group(3)) for m in ROW.finditer(text)]


def table(text: str) -> dict[str, tuple[int, ...]]:
    """Per plan: plan-file open, LEDGER open, partly, owner calls, hardware, total."""
    plan_open = {m.group(1): int(m.group(2)) for m in COUNT.finditer(text)}
    out = {}
    for p in PLANS:
        mine = [s for _, plan, s in rows(text) if plan == p]
        o, pa = mine.count("open"), mine.count("partly")
        po = plan_open.get(p, 0)
        out[p] = (po, o, pa, mine.count("owner-call"), mine.count("blocked-hardware"), po + o + pa)
    out["all"] = tuple(sum(v[i] for v in out.values()) for i in range(6))
    return out


def recount(text: str) -> str:
    #: One row per plan: a union merge of two branches' tables once stacked 38 `| all |` rows.
    seen: set[str] = set()
    kept = []
    for line in text.split("\n"):
        m = COUNT.match(line)
        if m and m.group(1) in seen:
            continue
        if m:
            seen.add(m.group(1))
        kept.append(line)
    text = "\n".join(kept)
    for p, v in table(text).items():
        text = re.sub(rf"^\| {re.escape(p)} \|( \d+ \|){{6}}$", f"| {p} | " + " | ".join(map(str, v)) + " |", text, flags=re.M)
    return text


def taken_ids(plan: str, *texts: str) -> set[int]:
    """Every number used for this plan's rows, open (LEDGER) or closed (HISTORY): a closed id is never reissued."""
    pat = re.compile(rf"\*\*L-{re.escape(plan)}-(\d+)\*\*")
    return {int(m.group(1)) for text in texts for m in pat.finditer(text)}


def next_id(plan: str, ledger_text: str, history_text: str) -> str:
    return f"L-{plan}-{max(taken_ids(plan, ledger_text, history_text), default=0) + 1}"


def add(a: argparse.Namespace) -> str:
    text = LEDGER.read_text(encoding="utf-8")
    rid = next_id(a.plan, text, HISTORY.read_text(encoding="utf-8") if HISTORY.exists() else "")
    title = a.title.strip().rstrip(".")
    line = f"- [ ] **{rid}** `{a.plan}` {a.status}, {a.size}: {title}. From {a.src}." + (f" Evidence: {a.evidence}" if a.evidence else "")
    head = {"owner-call": "## Owner calls", "blocked-hardware": "## Needs hardware"}.get(a.status, f"## {a.plan}")
    i = text.index(head + "\n")
    j = text.find("\n## ", i + 1)
    j = len(text) if j < 0 else j
    block = text[i:j].rstrip("\n") + "\n" + line + "\n"
    LEDGER.write_text(recount(text[:i] + block + text[j:]), encoding="utf-8")
    return rid


def done(rid: str, evidence: str) -> None:
    text = LEDGER.read_text(encoding="utf-8")
    m = re.search(rf"^- \[ \] \*\*{re.escape(rid)}\*\* .*\n", text, re.M)
    if not m:
        sys.exit(f"{rid} is not an open LEDGER row")
    LEDGER.write_text(recount(text[: m.start()] + text[m.end():]), encoding="utf-8")
    hist = HISTORY.read_text(encoding="utf-8")
    if HISTORY_HEAD not in hist:
        hist = hist.rstrip("\n") + f"\n\n{HISTORY_HEAD}\n"
    i = hist.index(HISTORY_HEAD) + len(HISTORY_HEAD) + 1
    moved = m.group(0).replace("- [ ]", "- [x]", 1).rstrip("\n") + f" Built: {evidence}\n"
    HISTORY.write_text(hist[:i] + moved + hist[i:], encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--plan", choices=PLANS, required=True)
    a.add_argument("--status", choices=STATUSES, default="open")
    a.add_argument("--size", choices=("S", "M", "L"), default="M")
    a.add_argument("--src", required=True)
    a.add_argument("--evidence", default="")
    a.add_argument("title")
    d = sub.add_parser("done")
    d.add_argument("id")
    d.add_argument("evidence")
    sub.add_parser("counts")
    args = ap.parse_args()
    if args.cmd == "add":
        print(add(args))
    elif args.cmd == "done":
        done(args.id, args.evidence)
    else:
        LEDGER.write_text(recount(LEDGER.read_text(encoding="utf-8")), encoding="utf-8")
        for p, v in table(LEDGER.read_text(encoding="utf-8")).items():
            print(p, *v)


if __name__ == "__main__":
    main()
