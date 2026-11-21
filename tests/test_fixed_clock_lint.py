"""Tests use a fixed clock, never the real one (CLAUDE.md section 8).

On 2026-11-21 five composer tests failed on py3.13: their fixture pinned
`user_now` on two or three modules, and the modules it missed (`from
tessellate.core.config import user_now` binds the name at import) read the real
day, so "21 November" was today and "the 16th" had passed. `tests/_clock.pin_clock`
pins every holder at once; these lints keep the suite on it."""

from __future__ import annotations

import ast

from pathlib import Path

TESTS = Path(__file__).resolve().parent


#: `datetime.now()`, `date.today()`, `dt.datetime.utcnow()` and the like, as calls:
#: a name in a docstring or a lint's pattern is not a read.
_CLOCK_CALLS = {"now", "today", "utcnow"}


_CLOCK_OWNERS = {"datetime", "date"}


def _real_read_nodes(tree: ast.AST) -> list[tuple[int, ast.Call]]:
    found = []
    for node in ast.walk(tree):
        func = node.func if isinstance(node, ast.Call) else None
        if isinstance(func, ast.Attribute) and func.attr in _CLOCK_CALLS:
            owner = func.value
            name = owner.attr if isinstance(owner, ast.Attribute) else getattr(owner, "id", "")
            if name in _CLOCK_OWNERS:
                found.append((node.lineno, node))
    return found


#: The three places the app reads the real clock: every other reader goes
#: through them (`clock.utc`, `clock.wall`, `clock.today`), so a pin reaches it.
_SEAMS = {("core/config.py", "user_now"), ("core/database.py", "utcnow"), ("core/clock.py", "today"), ("core/clock.py", "_now")}


def _reads_outside_seams(rel: str, text: str) -> list[int]:
    tree = ast.parse(text)
    inside = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and (rel, node.name) in _SEAMS:
            inside.update(id(n) for n in ast.walk(node))
    return [line for line, node in _real_read_nodes(tree) if id(node) not in inside]


def test_the_app_reads_the_real_clock_only_through_its_seams():
    """`datetime.now()` in a module is a clock no test can pin: on 2026-11-21
    the staleness cutoff and the chart's "this month" read the real day under
    a pinned one."""
    src = TESTS.parent / "src" / "tessellate"
    offenders = [
        f"{rel}:{line}"
        for path in sorted(src.rglob("*.py"))
        for rel in [path.relative_to(src).as_posix()]
        for line in _reads_outside_seams(rel, path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"read the clock through tessellate.core.clock (utc, wall, today): {offenders}"


def _module_level(nodes):
    """Statements run at import: a function's or class's own imports bind a local."""
    for node in nodes:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            yield node
            yield from _module_level(ast.iter_child_nodes(node))


def _clock_holders() -> set[tuple[str, str]]:
    root = TESTS.parent
    found = set()
    for path in [*(root / "src").rglob("*.py"), *TESTS.rglob("*.py")]:
        parts = path.relative_to(root / "src" if path.is_relative_to(root / "src") else root).with_suffix("").parts
        name = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        for node in _module_level(ast.parse(path.read_text(encoding="utf-8")).body):
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                found |= {(name, a.name) for a in node.names if a.name in {"user_now", "utcnow"} and a.asname is None}
    return found


def test_the_pin_lists_every_module_that_holds_a_clock_by_name():
    """`pin_clock` patches the fixed `HOLDERS` pairs, so a new `from ... import
    user_now` (or `utcnow`) at a module's top must be listed, and a listed one
    that no longer imports it must go."""
    from tests._clock import HOLDERS

    found = _clock_holders()
    assert len(HOLDERS) == len(set(HOLDERS))
    assert not found - set(HOLDERS), f"add to tests/_clock.HOLDERS: {sorted(found - set(HOLDERS))}"
    assert not set(HOLDERS) - found, f"drop from tests/_clock.HOLDERS: {sorted(set(HOLDERS) - found)}"


