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
import io
import re
import subprocess
import tokenize
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
#: Text in quotes in a code file is copy a user reads (a checkbox's "Not
#: done", a template's "## Still open", the `todo` callout), never a work
#: marker; a marker lives in a comment or a docstring (owner, INBOX 1810).
def _blank(lines: list[str], spans) -> list[str]:
    """`lines` with each ((row, col), (row, col)) span, 1-based rows, blanked."""
    rows = [list(line) for line in lines]
    for (r0, c0), (r1, c1) in spans:
        for r in range(r0, r1 + 1):
            row = rows[r - 1] if r - 1 < len(rows) else []
            for c in range(c0 if r == r0 else 0, c1 if r == r1 else len(row)):
                if c < len(row):
                    row[c] = " "
    return ["".join(row) for row in rows]


def _js_quoted(lines: list[str]) -> list[str]:
    """JS lines with '...', "..." and `...` literals blanked; comments kept."""
    out, mode = [], None  # mode: None, "/*", or the open quote mark
    for line in lines:
        chars, i = list(line), 0
        while i < len(chars):
            ch, nxt = chars[i], line[i + 1 : i + 2]
            if mode == "/*":
                mode, i = (None, i + 2) if ch == "*" and nxt == "/" else (mode, i + 1)
            elif mode:
                chars[i] = " "
                if ch == "\\":
                    if nxt:
                        chars[i + 1] = " "
                    i += 2
                    continue
                if ch == mode:
                    mode = None
                i += 1
            elif ch == "/" and nxt == "/":
                break
            elif ch == "/" and nxt == "*":
                mode, i = "/*", i + 2
            elif ch in "'\"`":
                mode, i = ch, i + 1
            else:
                i += 1
        if mode in ("'", '"'):
            mode = None  # a plain quote does not run past its line
        out.append("".join(chars))
    return out


def _py_quoted(text: str, lines: list[str]) -> list[str]:
    """Python lines with string literals blanked; docstrings kept."""
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return lines
    skip = {tokenize.NL, tokenize.COMMENT}
    spans = []
    for n, tok in enumerate(toks):
        if tok.type == getattr(tokenize, "FSTRING_MIDDLE", -1):
            spans.append((tok.start, tok.end))
        if tok.type != tokenize.STRING:
            continue
        before = next((x for x in reversed(toks[:n]) if x.type not in skip), None)
        after = next((x for x in toks[n + 1 :] if x.type not in skip), None)
        alone = before is None or before.type in (tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING)
        if not (alone and after is not None and after.type in (tokenize.NEWLINE, tokenize.ENDMARKER)):
            spans.append((tok.start, tok.end))
    return _blank(lines, spans)


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
            text = (ROOT / f).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        lines = text.splitlines()
        seen = _js_quoted(lines) if f.endswith((".js", ".css")) else _py_quoted(text, lines) if f.endswith(".py") else lines
        in_done_row = f == "docs/roadmap/LEDGER.md"
        for i, line in enumerate(lines, 1):
            if in_done_row and line.startswith("- [x]"):
                continue
            if SIGNAL.search(seen[i - 1]) and not COPY.search(line):
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
