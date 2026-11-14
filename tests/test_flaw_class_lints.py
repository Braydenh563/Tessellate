"""The flaw-class lints of WORLD_CLASS_PLAN section 10, F4 and F7.

F4: a broad `except Exception` that says nothing turns a fault into silence.
The rule is ruff's BLE001, enabled in `pyproject.toml` on 2026-09-26 once the
33 findings were triaged (twelve were silent and now log with `exc_info`, the
rest carry a `# noqa: BLE001  # <reason>`). This file holds the switch on, so
removing it from `select` is a failing test rather than a quiet regression.

F7: threads in many modules share SQLAlchemy sessions created per call, and
nothing enforces that a thread opens its own. The plan's end state is
`Thread(` in `core/jobs.py` only (B2's job runtime); until the rest move onto
the pool, this is a ratchet: the modules that start threads today are listed
with their count, a new module fails, and a count may only go down. A thread
also runs without the request's context, so it never holds a vault grant
(`core/vault.py`), which is one more reason each one is written down.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

from tests._repo_files import repo_files

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "tessellate"

#: Module -> `threading.Thread(` calls, 2026-09-26. Lower a number when a
#: thread moves onto `core/jobs.py`; never raise one, never add a module.
THREAD_SITES = {
    #: The captions helper is its own child process, standard library only (it
    #: never imports the app), so core/jobs.py's pool does not exist there: its
    #: one thread watches stdin so it exits when the app does (INBOX 1777).
    "ai/captions_helper.py": 1,
    #: 3 since INBOX 1502: the pool, the durable leases' heartbeat, and `jobs.thread`,
    #: the one place this is the design. Every other module starts its thread there (L567).
    "core/jobs.py": 3,
}


def _thread_calls(tree: ast.AST) -> int:
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "Thread":
                count += 1
            elif isinstance(func, ast.Name) and func.id == "Thread":
                count += 1
    return count


def test_ble001_stays_enabled() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert "BLE001" in config["tool"]["ruff"]["lint"]["select"]


def test_no_module_starts_more_threads_than_it_did() -> None:
    found = {}
    for path in repo_files(SRC, suffixes=(".py",)):
        calls = _thread_calls(ast.parse(path.read_text()))
        if calls:
            found[str(path.relative_to(SRC))] = calls
    new = {name: n for name, n in found.items() if name not in THREAD_SITES}
    grown = {name: (THREAD_SITES[name], n) for name, n in found.items() if n > THREAD_SITES.get(name, n)}
    assert not new, f"start work on core/jobs.py's pool instead of a new thread: {new}"
    assert not grown, f"these modules start more threads than recorded (was, now): {grown}"
    shrunk = {name: (n, found.get(name, 0)) for name, n in THREAD_SITES.items() if found.get(name, 0) < n}
    assert not shrunk, f"a thread moved: lower THREAD_SITES to match (was, now): {shrunk}"
