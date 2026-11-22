#!/usr/bin/env python3
"""Count the tests that read source text instead of running behaviour
(L-general-9).

A source-text test is a test function whose body, or a module-level name it
uses, reads a file's text (`read_text(`, `app_js_text(`, `css_text(`). Some
are the only check there is (a CSS rule, a Dockerfile line); others stand in
for a behaviour test that was never written. A new one says which in its
docstring: scripts/gate.sh prints the counts and refuses a bare one added
since its base (`--new`), leaving the old ones as they are.

    python scripts/source_text_tests.py              # the counts
    python scripts/source_text_tests.py --new BASE   # exit 1 on a bare one added since BASE
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
READS = re.compile(r"\b(?:read_text|app_js_text|css_text|html_text)\(")


def _tests(tree: ast.Module):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            yield node
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            yield from (n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test"))


def scan_file(name: str, text: str) -> tuple[int, int, list[str]]:
    """One test file's (tests, source-text tests, bare ones as file::name)."""
    if not READS.search(text):
        return sum(1 for _ in _tests(ast.parse(text))), 0, []
    lines = text.splitlines()
    tree = ast.parse(text)

    def source(node: ast.AST) -> str:
        return "\n".join(lines[node.lineno - 1:node.end_lineno])

    readers = {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign) and READS.search(source(node))
        for target in node.targets
        if isinstance(target, ast.Name)
    } | {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("test") and READS.search(source(node))
    }
    total, reading, bare = 0, 0, []
    for test in _tests(tree):
        total += 1
        names = {n.id for n in ast.walk(test) if isinstance(n, ast.Name)}
        if READS.search(source(test)) or names & readers:
            reading += 1
            if not ast.get_docstring(test):
                bare.append(f"{name}::{test.name}")
    return total, reading, bare


def scan(root: Path = ROOT) -> tuple[int, int, list[str]]:
    """(tests, source-text tests, source-text tests without a docstring as file::name)."""
    total, reading, bare = 0, 0, []
    for path in sorted((root / "tests").glob("test_*.py")):
        t, r, b = scan_file(path.name, path.read_text(encoding="utf-8"))
        total, reading, bare = total + t, reading + r, bare + b
    return total, reading, bare


def new_bare(base: str, root: Path = ROOT) -> list[str]:
    """Bare source-text tests that are not in `base` (a git ref): the ones a
    change adds, which gate.sh refuses. Old ones are left as they are."""
    import subprocess

    def at_base(path: Path) -> str:
        done = subprocess.run(["git", "show", f"{base}:tests/{path.name}"], cwd=root, capture_output=True, text=True)
        return done.stdout if done.returncode == 0 else ""

    changed = subprocess.run(
        ["git", "diff", "--name-only", base, "--", "tests/"], cwd=root, capture_output=True, text=True,
    ).stdout.split()
    found = []
    for rel in changed:
        path = root / rel
        if not (path.name.startswith("test_") and path.suffix == ".py" and path.exists()):
            continue
        before = set(scan_file(path.name, at_base(path))[2]) if at_base(path) else set()
        found += [t for t in scan_file(path.name, path.read_text(encoding="utf-8"))[2] if t not in before]
    return found


def main(argv: list[str]) -> int:
    total, reading, bare = scan()
    print(f"source-text tests: {reading} of {total}, {len(bare)} without a docstring")
    if argv[:1] == ["--new"] and len(argv) == 2:
        added = new_bare(argv[1])
        for test in added:
            print(f"  new source-text test without a docstring saying why it cannot assert behaviour: {test}")
        return 1 if added else 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
