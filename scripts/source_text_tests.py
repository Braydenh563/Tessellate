"""Count the tests that read a file's text, and how many say why (L-general-9).

A test that reads source text (`read_text`, `read_bytes`, `app_js_text`)
asserts what the code says, not what it does, so it passes for code that
never runs. Some cannot be anything else; those say why in a docstring.
`tests/test_source_text_docstrings.py` holds the undocumented count to a
ratchet so a new one carries its reason, and `scripts/gate.sh` prints both.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READERS = frozenset({"read_text", "read_bytes", "app_js_text"})


def _reads(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name in READERS:
                return True
    return False


def scan(root: Path = ROOT) -> tuple[int, list[str]]:
    """(tests that read file text, `file::test` of those with no docstring).

    A test counts when its body calls a reader or names a module constant
    assigned from one (`DOCKERFILE = (...).read_text()`)."""
    total, bare = 0, []
    for path in sorted((root / "tests").glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if not any(reader in text for reader in READERS):
            continue
        tree = ast.parse(text)
        constants = {
            target.id
            for node in tree.body
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and _reads(node)
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
            if isinstance(target, ast.Name)
        }
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test"):
                continue
            if _reads(node) or any(isinstance(n, ast.Name) and n.id in constants for n in ast.walk(node)):
                total += 1
                if not ast.get_docstring(node):
                    bare.append(f"{path.name}::{node.name}")
    return total, bare


if __name__ == "__main__":
    total, bare = scan()
    print(f"{total} ({len(bare)} without a docstring saying why)")
    sys.exit(0)
