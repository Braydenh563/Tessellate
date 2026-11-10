"""A module-level constant is assigned once, or extended from itself.

W2 (2026-11-10) added a second `_NAMED` to `ai/commands.py` for its own list
of act keys; it silently replaced the ("called ", "titled ", "named ") tuple
the note-name parser read, and "create a note called Shopping with milk"
wrote "Called Shopping with milk" (the full suite caught it, ruff did not).
A later assignment that reads the name (`X = X + (...)`, `X = (*extra, *X)`)
is an extension and allowed.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _constant(name: str) -> bool:
    bare = name.lstrip("_")
    return bool(bare) and bare.replace("_", "").isalnum() and bare.upper() == bare and any(c.isalpha() for c in bare)


def _reads(node: ast.AST, name: str) -> bool:
    return any(isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load) for n in ast.walk(node))


def _shadowed(path: Path) -> list[str]:
    seen: set[str] = set()
    found = []
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        for target in targets:
            if not (isinstance(target, ast.Name) and _constant(target.id)):
                continue
            if target.id in seen and not _reads(value, target.id):
                found.append(f"{path.relative_to(ROOT)}:{node.lineno} {target.id}")
            seen.add(target.id)
    return found


def test_no_module_constant_is_replaced_by_a_second_assignment():
    found = [hit for path in sorted((ROOT / "src" / "tessellate").rglob("*.py")) for hit in _shadowed(path)]
    assert not found, "a constant assigned twice (rename the second):\n  " + "\n  ".join(found)
