"""A plan holds open work only; what is built lives in HISTORY.md.

The owner, after the fourth time: "you, opus and sonnet have just marked
things as built in the roadmap and not actually moved them to history.md
... if they are fully built, they should not take up room where new
features, fixes and refinements should be." CLAUDE.md standing order 10.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._repo_files import repo_files

ROADMAP = Path(__file__).resolve().parent.parent / "docs" / "roadmap"
ROOT = Path(__file__).resolve().parent.parent

#: Directories the conflict-marker sweep below never walks: a checkout's own
#: plumbing, a virtual environment's vendored packages, and the browser
#: profiles the sweeps leave behind, none of which this project writes.
#: `worktrees` is here for the same reason `.git` is: `.claude/worktrees/`
#: holds other branches' checkouts, one per running agent, and a lint on this
#: branch has no business asserting about another branch's files. Left in, it
#: also fails for a reason that is not a fault: an agent part-way through a
#: merge legitimately has conflict markers in its own tree, so this test went
#: red the moment two agents were started and stayed red until they finished.
#: Added 2026-09-21, after it correctly caught a real marker on this branch
#: and then drowned it in eleven lines about other people's worktrees.
_SKIP_PARTS = {".git", ".venv", "node_modules", "__pycache__", ".gate", "shots", "worktrees"}


PLANS = sorted(ROADMAP.glob("*_PLAN.md"))


#: Line caps per planning file: today's count rounded up to the next 100, plus
#: 200 (2026-10-10). Orientation reads are the largest token cost, so these
#: only ratchet down. Keys are file names; ROADMAP.md lives in docs/, the rest
#: in docs/roadmap/.
PLAN_LINE_CAPS = {
    "CHAT_PLAN.md": 1900,
    "DOCUMENTS_PLAN.md": 1600,
    "GRAPH_PLAN.md": 800,
    "MINDMAP_PLAN.md": 2000,
    "TIMELINE_PLAN.md": 500,
    "UI_MODERNISATION_PLAN.md": 1600,
    "WHITEBOARD_PLAN.md": 1800,
    "WORLD_CLASS_PLAN.md": 4200,
    "ROADMAP.md": 600,
    "BACKLOG.md": 4500,
    "LEDGER.md": 1300,
}


def test_plan_files_stay_under_their_size_caps() -> None:
    over = []
    for name, cap in PLAN_LINE_CAPS.items():
        path = ROADMAP.parent / name if name == "ROADMAP.md" else ROADMAP / name
        lines = path.read_text(encoding="utf-8").count("\n")
        if lines > cap:
            over.append(f"{name}: {lines} lines (cap {cap})")
    assert over == [], (
        "move built blocks to HISTORY.md ('Moved from the plans') or condense; "
        "never raise the cap without moving something out: " + "; ".join(over)
    )


def test_no_plan_carries_a_built_block() -> None:
    offenders = []
    for plan in PLANS:
        for line in plan.read_text(encoding="utf-8").splitlines():
            if re.match(r"^#{2,3} (\d+\. )?Built\b", line):
                body = plan.read_text(encoding="utf-8")
                after = body.split(line, 1)[1][:300]
                if "Moved to HISTORY.md" not in after:
                    offenders.append(f"{plan.name}: {line}")
    assert offenders == [], (
        "move these blocks whole into HISTORY.md ('Moved from the plans') and leave "
        "the one-line pointer: " + "; ".join(offenders)
    )


def test_handover_is_the_current_state_only() -> None:
    lines = (ROADMAP / "HANDOVER.md").read_text(encoding="utf-8").count("\n")
    assert lines < 600, f"HANDOVER.md is {lines} lines; append the session record to HISTORY.md"


def test_inbox_holds_open_reports_only() -> None:
    """A resolved report (fixed, not reproduced, checked) moves to HISTORY.md's
    "INBOX resolved" with its number; INBOX holds only unresolved reports."""
    text = (ROADMAP / "INBOX.md").read_text(encoding="utf-8")
    resolved = [
        line for line in text.splitlines()
        if re.match(r"^\d+\. \*\*\(?(fixed|Fixed|Not reproduced|checked|Checked|Done|done)", line)
    ]
    assert resolved == [], "move these to HISTORY.md, INBOX resolved: " + "; ".join(r[:60] for r in resolved)


def test_inbox_is_a_tray_not_a_backlog() -> None:
    """Under twenty open items: anything older is placed in its plan."""
    text = (ROADMAP / "INBOX.md").read_text(encoding="utf-8")
    count = len(re.findall(r"(?m)^\d+\. \*\*", text))
    assert count < 20, f"INBOX has {count} items; place the rest in their plans (Placed from INBOX)"


def test_an_inbox_item_is_listed_once_and_not_also_in_history() -> None:
    """A merge that keeps both sides of INBOX.md left three copies of 1508 and
    put back 1506, 1509 and 1510 after they had moved to HISTORY (2026-11-01)."""
    numbers = re.findall(r"(?m)^(\d+)\. \*\*", (ROADMAP / "INBOX.md").read_text(encoding="utf-8"))
    twice = sorted({n for n in numbers if numbers.count(n) > 1})
    assert not twice, f"INBOX lists {twice} more than once; keep the newest entry"
    history = (ROADMAP / "HISTORY.md").read_text(encoding="utf-8")
    moved = [n for n in numbers if re.search(rf"(?m)^{n}\. \*\*", history)]
    assert not moved, f"INBOX still lists {moved}, already moved to HISTORY.md"


def test_no_conflict_marker_survives_a_merge():
    """A merge conflict must never reach the branch.

    It did, on 2026-09-09: three worktrees were merged in one shell loop with
    each merge piped to `tail`, so the pipeline's exit status was `tail`'s,
    `set -e` never saw the failure, the loop carried on, and the `git add -A`
    that follows the gate staged the conflicted files and committed them.
    Every lint in `scripts/gate.sh` passed, because none of them looked for a
    marker, and the result was pushed.

    Text files only, and the markers are built from parts so this file does
    not fail on its own source.
    """
    opener = "<" * 7 + " "
    divider = "=" * 7
    closer = ">" * 7 + " "
    offenders = []
    for path in repo_files(exclude_dirs=tuple(sorted(_SKIP_PARTS))):
        if path.suffix.lower() not in {".md", ".py", ".js", ".css", ".html", ".json", ".txt", ".yml", ".yaml"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if line.startswith(opener) or line.startswith(closer) or line.rstrip() == divider:
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert offenders == [], (
        "an unresolved merge conflict is committed; resolve it rather than "
        "committing the markers:\n" + "\n".join(offenders[:40])
    )


def test_no_entry_is_in_both_the_tray_and_the_history():
    """An entry moved to HISTORY must leave the tray.

    Found 2026-09-21, and it was a merge that caused it: resolving a conflict
    in INBOX.md by keeping both sides restores entries the other side had
    already moved out, so 313 and 314 sat in the tray and in HISTORY at once.
    Nothing else noticed, because each copy is well formed on its own and the
    "Fixed" rule above only reads the first words of an entry.

    The number is the identity, so the check is a set intersection.
    """
    tray = set(re.findall(r"^(\d{3})\. ", (ROADMAP / "INBOX.md").read_text(encoding="utf-8"), re.M))
    history = set(
        re.findall(r"^(\d{3})\. ", (ROADMAP / "HISTORY.md").read_text(encoding="utf-8"), re.M)
    )
    both = sorted(tray & history)
    assert not both, (
        "these entries are in INBOX.md and in HISTORY.md at once, which means "
        f"a move was undone (usually by a merge keeping both sides): {both}"
    )
