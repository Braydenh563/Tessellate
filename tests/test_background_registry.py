"""Every background thread or task is registered (WORLD_CLASS_PLAN 26.2, decision 58): a ratchet.

A thread nobody can list or stop is the bug behind "the app would not quit"
and "a second embedding pass started under the first". Decision 58 puts the
registry in `core/background.py`, with `core/jobs.py` and `core/jobruns.py`
as the only modules allowed to start work themselves. That module is
built (`start`, `running`, `stop_all`; the embedding warm-up is its first
entry), and this test holds the line for the rest:
the sites below are the 26 found on 2026-10-10, each keyed by file, enclosing
function, kind and position. A new `Thread(`, `Timer(`, executor,
`create_task`, `ensure_future`, `run_in_executor` or `add_task` outside the
owning modules fails; a seeded site that is gone or moved into the registry
fails too, so the list only shrinks.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests._repo_files import repo_files

SRC = Path(__file__).resolve().parents[1] / "src" / "tessellate"

#: The modules whose job is to start work.
OWNERS = {"core/jobs.py", "core/jobruns.py", "core/background.py"}

_KINDS = {
    "Thread": "thread",
    "Timer": "timer",
    "ThreadPoolExecutor": "executor",
    "ProcessPoolExecutor": "executor",
    "create_task": "task",
    "ensure_future": "task",
    "run_in_executor": "executor",
    "add_task": "request-task",
}

SEED = frozenset(
    """
__main__.py::_boot_and_swap::thread::1
__main__.py::_serve_with_lan.serve_both::task::1
__main__.py::_serve_with_lan.serve_both::task::2
__main__.py::_start_tray::thread::1
ai/autonomous.py::start::thread::1
ai/embeddings.py::EmbeddingService._maybe_auto_install_missing_package::thread::1
ai/janitor.py::_chat_within_deadline::thread::1
ai/tools/__init__.py::prefetch_web::executor::1
api/app.py::_start_searxng_if_asked::thread::1
api/routes_backups.py::export_bundle::request-task::1
api/routes_import.py::export_notebook_folder::request-task::1
api/routes_settings.py::export_backup::request-task::1
api/routes_settings.py::restart_app::request-task::1
api/routes_settings.py::set_console_mode::request-task::1
api/routes_tasks.py::shutdown::timer::1
api/routes_update.py::apply_update::thread::1
api/routes_update.py::apply_update::thread::2
core/embedmodels.py::_spawn_download::thread::1
core/jobstore.py::_schedule::timer::1
core/security.py::_backend_addresses::thread::1
search/searxng_install.py::install_source::thread::1
search/searxng_manager.py::_run_streaming::thread::1
""".strip().splitlines()
) | frozenset(
    #: Registered 2026-10-11 with the work that started them, each one named in
    #: its module: the LAN listener's accept loop, its one first-byte watcher
    #: and its peek executor (core/lanserve.py, core/lanlive.py: infrastructure
    #: that must outlive any one request), and a recording's transcription,
    #: which is also listed in the activity panel (api/routes_recordings.py).
    """
core/lanlive.py::Listener.start::executor::1
core/lanlive.py::Listener.start::task::1
core/lanlive.py::supervise::executor::1
core/lanserve.py::<module>::executor::1
core/lanserve.py::_FirstByteWatcher.wait::thread::1
core/lanserve.py::_route::executor::1
core/lanserve.py::serve::executor::1
core/lanserve.py::serve::task::1
core/lanserve.py::serve::task::2
""".strip().splitlines()
)


def sites() -> set[str]:
    found: set[str] = set()
    for path in repo_files(SRC, suffixes=(".py",), exclude_dirs=("vendor",)):
        rel_src = path.relative_to(SRC).as_posix()
        if rel_src in OWNERS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))

        def visit(node: ast.AST, scope: str, counts: dict[str, int]) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    visit(child, f"{scope}.{child.name}" if scope else child.name, counts)
                    continue
                if isinstance(child, ast.Call):
                    fn = child.func
                    name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                    kind = _KINDS.get(name)
                    if kind:
                        key = f"{rel_src}::{scope or '<module>'}::{kind}"
                        counts[key] = counts.get(key, 0) + 1
                        found.add(f"{key}::{counts[key]}")
                visit(child, scope, counts)

        visit(tree, "", {})
    return found


def test_no_unregistered_background_site() -> None:
    new = sites() - SEED
    assert not new, (
        "a thread, timer, executor or task started outside core/jobs.py, core/jobruns.py "
        "and core/background.py; route it through the pool or register it:\n  " + "\n  ".join(sorted(new))
    )


def test_the_seed_only_shrinks() -> None:
    stale = SEED - sites()
    assert not stale, "gone or registered, so delete it from SEED:\n  " + "\n  ".join(sorted(stale))
