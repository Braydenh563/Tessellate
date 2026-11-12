"""List every line outside BACKLOG that reads as open work (the owner, 2026-11-12:
"I want absolutely nothing left outside of the backlog file").

    python scripts/open_scan.py              # every hit, file:line: text
    python scripts/open_scan.py --counts     # hits per file
    python scripts/open_scan.py --plan chat  # only files the plan's session owns

A hit is a signal, not a verdict: a plan session clears the hits in its files by
doing the work, filing it as a LEDGER row, moving it to BACKLOG, or rewording a
line that only reads as open (history written as "built", not "still open").
The closing session runs it with no filter; the run is done when the only hits
left are LEDGER rows for real-device checks the owner has agreed to move to BACKLOG.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Files that hold no open work by definition, or are not ours to edit.
SKIP = re.compile(
    r"^(docs/roadmap/(BACKLOG|HISTORY)\.md|CHANGELOG\.md|docs/CHANGELOG\.md|docs/CODEMAP\.md"
    r"|frontend/vendor/|frontend/fonts/|.*\.min\.(js|css)$|.*\.lock$|.*package-lock\.json$"
    r"|\.claude/skills/ui-ux-pro-max/|scripts/open_scan\.py$|tests/fixtures/)"
)
TEXT = re.compile(r"\.(md|txt|py|js|css|html|json|ya?ml|toml|sh|cfg|ini)$")

SIGNAL = re.compile(
    r"^\s*[-*] \[ \]"
    r"|\b(TODO|FIXME|XXX|HACK)\b"
    r"|\bstill open\b|\bnot (yet )?built\b|\bunbuilt\b|\bnot done\b|\bleft open\b"
    r"|\bfollow[- ]?up\b|\bdeferred\b|\bnext session\b|\blater (PR|session|pass)\b"
    r"|\bowner[- ]call\b|\bneeds (the )?owner\b|\bopen question\b|\bneeds hardware\b|\bblocked-hardware\b"
    r"|\bstill to (do|build|fix)\b|\bremains? open\b|\bnot yet (built|done|fixed|wired)\b"
    r"|xfail\(.*strict\s*=\s*True|mark\.skip\(",
    re.I,
)

#: A reminder's default text ("Follow up: <note>") is app copy, not work.
COPY = re.compile(r"`Follow up: \$\{")
#: Which plan session owns a path (anything else goes to the closing session).
OWNERS = {
    "graph": ("docs/roadmap/GRAPH_PLAN.md", "frontend/js/graph"),
    "chat": ("docs/roadmap/CHAT_PLAN.md", "frontend/js/chat", "src/tessellate/ai/"),
    "whiteboard": ("docs/roadmap/WHITEBOARD_PLAN.md", "frontend/js/whiteboard"),
    "documents": ("docs/roadmap/DOCUMENTS_PLAN.md", "frontend/js/documents", "frontend/js/code"),
    "mindmap": ("docs/roadmap/MINDMAP_PLAN.md", "frontend/js/whiteboard-map"),
    "ui-modernisation": ("docs/roadmap/UI_MODERNISATION_PLAN.md", "docs/DESIGN.md", "frontend/css/"),
    "timeline": ("docs/roadmap/TIMELINE_PLAN.md", "frontend/js/timeline"),
    "world-class": ("docs/roadmap/WORLD_CLASS_PLAN.md",),
}


def files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [f for f in out.splitlines() if TEXT.search(f) and not SKIP.search(f)]


def hits(paths: list[str]) -> list[tuple[str, int, str]]:
    found = []
    for f in paths:
        try:
            lines = (ROOT / f).read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        in_done_row = f == "docs/roadmap/LEDGER.md"
        for i, line in enumerate(lines, 1):
            if in_done_row and line.startswith("- [x]"):
                continue
            if SIGNAL.search(line) and not COPY.search(line):
                found.append((f, i, line.strip()[:200]))
    return found


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--counts", action="store_true")
    a.add_argument("--plan", choices=sorted(OWNERS))
    args = a.parse_args()
    paths = files()
    if args.plan:
        paths = [f for f in paths if f.startswith(OWNERS[args.plan])]
    found = hits(paths)
    if args.counts:
        for f, n in Counter(f for f, _, _ in found).most_common():
            print(f"{n:6} {f}")
        print(f"{len(found):6} total")
        return
    for f, i, t in found:
        print(f"{f}:{i}: {t}")


if __name__ == "__main__":
    main()
