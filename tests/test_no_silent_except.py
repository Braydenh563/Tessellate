"""No silent swallow (WORLD_CLASS_PLAN 26.2, decision 57): a ratchet.

A broad `except` (bare, `Exception` or `BaseException`) that neither logs nor
re-raises and then ends in `pass`, `continue` or `return None` turns a fault
into silence, the shape behind "a feature that never ran once". Ruff's BLE001
already makes every broad handler carry a reason; this finds the ones that
say nothing at all.

The seed was 60 handlers (21 found 2026-10-10, 39 fallbacks seeded 2026-11-12)
and is now empty: every handler logs at debug with the reason and the way
out, or catches the named exceptions. Keys, when one ever returns, are file,
enclosing function and position in that function. Never add an exemption.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests._repo_files import repo_files

SRC = Path(__file__).resolve().parents[1] / "src" / "tessellate"

#: Calls that count as "says something": the logging methods, the project's
#: own `_log*` helpers and the audit log.
_LOG_NAMES = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log", "log_action"}

#: Zero since L-world-class-122 (decision 57): every broad handler logs, narrows or re-raises.
SEED: frozenset[str] = frozenset()


def _says_something(body: list[ast.stmt]) -> bool:
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Raise):
            return True
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name in _LOG_NAMES or name.startswith("_log") or name == "print":
                return True
    return False


def _ends_quiet(body: list[ast.stmt]) -> bool:
    last = body[-1]
    if isinstance(last, (ast.Pass, ast.Continue)):
        return True
    # A fallback returned in place of the fault (`return ""`, `return []`,
    # `return False`) is as silent as `return None` (L797, owner 2026-11-12:
    # decision 57 covers them, ratchet them all).
    return isinstance(last, ast.Return) and (last.value is None or _is_fallback(last.value))


def _is_fallback(value: ast.expr) -> bool:
    if isinstance(value, ast.Constant):
        return True
    if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
        return all(_is_fallback(e) for e in value.elts)
    if isinstance(value, ast.Dict):
        return not value.keys
    if isinstance(value, ast.UnaryOp):
        return isinstance(value.operand, ast.Constant)
    return False


def _is_broad(handler: ast.ExceptHandler) -> bool:
    t = handler.type
    return t is None or (isinstance(t, ast.Name) and t.id in {"Exception", "BaseException"})


def silent_handlers() -> set[str]:
    found: set[str] = set()
    for path in repo_files(SRC, suffixes=(".py",), exclude_dirs=("vendor",)):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel = path.relative_to(SRC.parent.parent).as_posix()

        def visit(node: ast.AST, scope: str, counts: dict[str, int]) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    visit(child, f"{scope}.{child.name}" if scope else child.name, counts)
                    continue
                if (
                    isinstance(child, ast.ExceptHandler)
                    and _is_broad(child)
                    and not _says_something(child.body)
                    and _ends_quiet(child.body)
                ):
                    n = counts[scope] = counts.get(scope, 0) + 1
                    found.add(f"{rel}::{scope or '<module>'}::{n}")
                visit(child, scope, counts)

        visit(tree, "", {})
    return found


def test_no_new_silent_swallow() -> None:
    new = silent_handlers() - SEED
    assert not new, (
        "a broad except that neither logs nor re-raises and ends quietly; log the reason "
        "and the way out, or catch the named exception:\n  " + "\n  ".join(sorted(new))
    )


def test_the_seed_only_shrinks() -> None:
    stale = SEED - silent_handlers()
    assert not stale, "fixed, so delete it from SEED (the ratchet only tightens):\n  " + "\n  ".join(sorted(stale))
