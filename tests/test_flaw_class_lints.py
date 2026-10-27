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
    "__main__.py": 2,  # the desktop window's server thread and the tray icon
    "ai/autonomous.py": 1,  # the scheduler loop; its passes and Run now moved onto the pool (Brief 9),
    "ai/embeddings.py": 1,
    "ai/janitor.py": 1,  # the filing deadline: runs *on* the model lane, so it cannot queue there
    # ai/model_manager.py: 0 since Brief 9, model downloads run on the pool's `download` lane
    "api/app.py": 1,
    "api/routes_update.py": 2,
    "core/embedmodels.py": 1,
    "core/background.py": 1,  # the registry: `start` is the one place a registered thread begins
    "core/lanserve.py": 1,  # lan-first-byte: one selector thread for every connection waiting on its first byte, started on the first wait
    # core/extras.py: 0 since INBOX 595, its installs run on the pool's `install` lane
    "core/jobs.py": 2,  # the pool itself and the durable leases' heartbeat: the one place this is the design
    "core/security.py": 1,
    "search/searxng_install.py": 1,
    "search/searxng_manager.py": 1,
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
