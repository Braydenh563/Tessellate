"""Tests use a fixed clock, never the real one (CLAUDE.md section 8).

On 2026-11-21 five composer tests failed on py3.13: their fixture pinned
`user_now` on two or three modules, and the modules it missed (`from
tessellate.core.config import user_now` binds the name at import) read the real
day, so "21 November" was today and "the 16th" had passed. `tests/_clock.pin_clock`
pins every holder at once; these lints keep the suite on it."""

from __future__ import annotations

import ast
import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent
_ONE_MODULE = re.compile(r"""setattr\(\s*(?:[\w.]+\s*,\s*["'](?:user_now|utcnow)["']|["'][\w.]+\.(?:user_now|utcnow)["'])""")
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


def _real_reads(text: str) -> list[int]:
    return [line for line, _node in _real_read_nodes(ast.parse(text))]


def test_the_clock_is_pinned_everywhere_or_not_at_all():
    """Patching `user_now` or `utcnow` on one module leaves every other holder on the real day."""
    offenders = [path.name for path, text in _sources() if _ONE_MODULE.search(text)]
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
    offenders = []
    for stem, text in sources.items():
        calls = _app_clock_calls(text)
        if not calls or stem in pinned:
            continue
        users = [s for s, t in sources.items() if re.search(rf"\btests\.{stem}\b|\bfrom \.{stem}\b", t)] if stem.startswith("_") else [stem]
        if not users or any(user not in pinned for user in users):
            offenders.append(f"{stem}.py:{calls[0]}")
    assert not offenders, f"pin the clock with tests._clock.pin_clock(monkeypatch, SUITE_NOW): {offenders}"


def test_the_lint_sees_an_app_clock_call():
    assert _app_clock_calls("from tessellate.core.database import utcnow\nx = utcnow()\n") == [2]
    assert _app_clock_calls("from tessellate.core import config\nx = config.user_now(c)\n") == [2]
    assert _app_clock_calls('"""`utcnow()` is a mention."""\n') == []


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


def test_the_lint_sees_a_real_read_and_not_a_mention():
    assert _real_reads("import datetime as dt\nx = dt.datetime.now(dt.timezone.utc)\n") == [2]
    assert _real_reads("from datetime import date\nd = date.today()\n") == [2]
    assert _real_reads('"""`date.today()` read the wrong day."""\nP = r"datetime\\.now\\("\n') == []


def test_pin_clock_reaches_a_module_that_imported_user_now_by_name(monkeypatch):
    from datetime import datetime

    from tessellate.api import routes_chat
    from tessellate.core import config
    from tests._clock import pin_clock

    when = datetime(2026, 8, 1, 9, 0)
    pin_clock(monkeypatch, when)
    assert config.user_now() == when and routes_chat.user_now(None) == when


def test_a_row_made_under_a_pinned_clock_is_stamped_with_it(monkeypatch, session):
    """`created_at` defaults to `database.stamp`, which reads the pinned `utcnow`;
    before, a note made under a pinned 30 October was stamped with the real day."""
    from datetime import datetime, timezone

    from tessellate.core import clock
    from tessellate.entry import manager
    from tests._clock import pin_clock

    when = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
    pin_clock(monkeypatch, when)
    entry = manager.create_entry(session, "# Pinned\n\nWritten on the pinned day.")
    session.commit()
    assert entry.created_at.replace(tzinfo=timezone.utc) == when
    assert clock.today() == when.date()
