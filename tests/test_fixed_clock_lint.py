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


def _sources():
    for path in sorted(TESTS.glob("*.py")):
        if path.name not in {"_clock.py", Path(__file__).name}:
            yield path, path.read_text(encoding="utf-8")


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


def _patches_one_clock(text: str) -> bool:
    """A `setattr(module, "user_now", ...)` or `setattr("pkg.mod.utcnow", ...)`,
    read from the syntax tree: a regex over every test file's text cost CodeQL's
    Analyze its 20 minutes (bisect, #248 and #249)."""
    for node in ast.walk(ast.parse(text)):
        func = node.func if isinstance(node, ast.Call) else None
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
        if name != "setattr":
            continue
        for arg in node.args[:2]:
            value = arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else ""
            if value.rpartition(".")[2] in _APP_CLOCKS:
                return True
    return False


def _imported(text: str) -> set[str]:
    """Every module a file imports, a relative one with its leading dots."""
    names = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            # `from tests import _seed` imports `tests._seed` as surely as
            # `from tests._seed import x` does.
            base = "." * node.level + (node.module or "")
            names.add(base)
            names.update(f"{base}.{alias.name}" if node.module else base + alias.name for alias in node.names)
    return names


def _real_reads(text: str) -> list[int]:
    return [line for line, _node in _real_read_nodes(ast.parse(text))]


def test_the_clock_is_pinned_everywhere_or_not_at_all():
    """Patching `user_now` or `utcnow` on one module leaves every other holder on the real day."""
    offenders = [path.name for path, text in _sources() if _patches_one_clock(text)]
    assert not offenders, f"pin the clock with tests._clock.pin_clock(monkeypatch, NOW): {offenders}"


def test_no_test_reads_the_real_clock():
    """No exceptions: data built relative to "now" is built from `SUITE_NOW` and pinned."""
    offenders = [f"{path.name}:{line}" for path, text in _sources() for line in _real_reads(text)]
    assert not offenders, f"build from tests._clock.SUITE_NOW and pin it with pin_clock: {offenders}"


#: The app's own clocks, called by name or through their module.
_APP_CLOCKS = {"utcnow", "user_now"}


_PINS = ("pin_clock(", "freeze_reminder_clock(")


def _app_clock_calls(text: str) -> list[int]:
    lines = []
    for node in ast.walk(ast.parse(text)):
        func = node.func if isinstance(node, ast.Call) else None
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
        if name in _APP_CLOCKS:
            lines.append(node.lineno)
    return lines


def test_a_test_that_asks_the_app_clock_has_pinned_it():
    """`utcnow()` or `user_now()` in a test is the real clock unless the file
    pins it; a helper module is pinned through every test file importing it."""
    sources = dict((path.stem, text) for path, text in _sources())
    pinned = {stem for stem, text in sources.items() if any(pin in text for pin in _PINS)}
    imports = {stem: _imported(text) for stem, text in sources.items()}
    offenders = []
    for stem, text in sources.items():
        calls = _app_clock_calls(text)
        if not calls or stem in pinned:
            continue
        users = [s for s, names in imports.items() if {f"tests.{stem}", f".{stem}"} & names] if stem.startswith("_") else [stem]
        if not users or any(user not in pinned for user in users):
            offenders.append(f"{stem}.py:{calls[0]}")
    assert not offenders, f"pin the clock with tests._clock.pin_clock(monkeypatch, SUITE_NOW): {offenders}"


def test_the_lint_sees_a_one_module_patch_and_an_import():
    assert _patches_one_clock('monkeypatch.setattr(routes_chat, "user_now", f)\n')
    assert _patches_one_clock('monkeypatch.setattr("tessellate.core.database.utcnow", f)\n')
    assert not _patches_one_clock('monkeypatch.setattr(config, "user_name", f)\n"setattr(x, \'user_now\', f)"\n')
    assert _imported("from tests._clock import pin_clock\nfrom ._seed import x\nimport tests._frozen_clock\nfrom tests import _app_js\n") == {
        "tests._clock", "tests._clock.pin_clock", "._seed", "._seed.x", "tests._frozen_clock", "tests", "tests._app_js"}


def test_the_lint_sees_an_app_clock_call():
    assert _app_clock_calls("from tessellate.core.database import utcnow\nx = utcnow()\n") == [2]
    assert _app_clock_calls("from tessellate.core import config\nx = config.user_now(c)\n") == [2]
    assert _app_clock_calls('"""`utcnow()` is a mention."""\n') == []


def test_the_lint_sees_a_real_read_and_not_a_mention():
    assert _real_reads("import datetime as dt\nx = dt.datetime.now(dt.timezone.utc)\n") == [2]
    assert _real_reads("from datetime import date\nd = date.today()\n") == [2]
    assert _real_reads('"""`date.today()` read the wrong day."""\nP = r"datetime\\.now\\("\n') == []


