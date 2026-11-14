"""No silent swallow (WORLD_CLASS_PLAN 26.2, decision 57): a ratchet.

A broad `except` (bare, `Exception` or `BaseException`) that neither logs nor
re-raises and then ends in `pass`, `continue` or `return None` turns a fault
into silence, the shape behind "a feature that never ran once". Ruff's BLE001
already makes every broad handler carry a reason; this finds the ones that
say nothing at all.

The seed is the 21 handlers found on 2026-10-10, plus the 39 that return a
fallback (`return ""`, `[]`, `False`) seeded 2026-11-12 (L797), keyed by file, enclosing
function and position in that function so an edit elsewhere in the file does
not move the key. A handler not in the seed fails the test; a seeded handler
that now logs, narrows or is gone fails it too, so the list only shrinks.
Fix one by logging with the reason and the way out, or by catching the
named exception, then delete its line below.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests._repo_files import repo_files

SRC = Path(__file__).resolve().parents[1] / "src" / "tessellate"

#: Calls that count as "says something": the logging methods, the project's
#: own `_log*` helpers and the audit log.
_LOG_NAMES = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log", "log_action"}

SEED = frozenset(
    """
src/tessellate/__main__.py::_bootloader_splash::1
src/tessellate/__main__.py::_password_exists::1
src/tessellate/__main__.py::_window_class_name::1
src/tessellate/ai/agent_turn.py::_names_an_existing_category::1
src/tessellate/ai/commands.py::_voice::1
src/tessellate/ai/composer_web.py::can_start_here::1
src/tessellate/ai/embeddings.py::_backfill_missing::1
src/tessellate/ai/embeddings.py::_notebook_has_notes::1
src/tessellate/ai/facts.py::runner_enabled::1
src/tessellate/ai/margin.py::_date_card::1
src/tessellate/ai/model_manager.py::_is_app_client::1
src/tessellate/ai/model_manager.py::_is_app_pair::1
src/tessellate/ai/needle_provider.py::_Engine._error::1
src/tessellate/ai/needle_provider.py::voice_now::1
src/tessellate/ai/provider.py::Provider.sampling_overrides::1
src/tessellate/ai/skills.py::small_class::1
src/tessellate/ai/tagging.py::_offered_again::1
src/tessellate/ai/tools/tool_schema.py::with_relation_types::1
src/tessellate/ai/tools/tool_web.py::prefetch_web.one::1
src/tessellate/ai/utilities.py::_zone_cities::1
src/tessellate/ai/utilities.py::web_on::1
src/tessellate/ai/vision_ocr.py::pdf_reader_or_none::1
src/tessellate/ai/vision_ocr.py::pdf_vision_ocr_and_store::1
src/tessellate/api/app.py::_has_password::1
src/tessellate/api/app.py::out_of_space_body::1
src/tessellate/api/chat_attach.py::_attachment_readings::1
src/tessellate/api/chat_said.py::_in_notes.holds::1
src/tessellate/api/chat_turn.py::_insight_level::1
src/tessellate/api/chat_turn.py::_meaning_loading::1
src/tessellate/api/chat_web.py::_search_service::1
src/tessellate/api/chat_web.py::_web_allowed::1
src/tessellate/api/chat_web.py::_web_pref_on::1
src/tessellate/api/routes_chat.py::_answer_voice::1
src/tessellate/api/routes_chat.py::_composer_embed::1
src/tessellate/api/routes_chat.py::_meaning_off::1
src/tessellate/api/routes_models.py::_tools_engine::1
src/tessellate/api/routes_vision.py::_meaning_alike::1
src/tessellate/core/activity.py::Job.request_stop::1
src/tessellate/core/desk_companion.py::_screen_area::1
src/tessellate/core/docview.py::_docx_part::1
src/tessellate/core/egress.py::_hook::1
src/tessellate/core/embedfind.py::_ollama_rows::1
src/tessellate/core/embedmodels.py::_in_use::1
src/tessellate/core/instance_lock.py::focus::1
src/tessellate/core/instance_lock.py::pid_alive::1
src/tessellate/core/lanlive.py::supervise.look::1
src/tessellate/core/logbuffer.py::NoiseFilter.filter::1
src/tessellate/core/ocr.py::extract_and_store::1
src/tessellate/core/ocr.py::saved_language::1
src/tessellate/core/overlay/win32.py::_cloaked::1
src/tessellate/core/security.py::_notebook_has_password::1
src/tessellate/core/webclip.py::_read::1
src/tessellate/entry/app_import.py::read_evernote::1
src/tessellate/entry/link_facts.py::reason_for::1
src/tessellate/search/chunks.py::current::1
src/tessellate/search/chunks.py::meaning_scorer::1
src/tessellate/search/engine.py::_backend_id::1
src/tessellate/search/engine.py::_cosine_scores::1
src/tessellate/search/search_manager.py::_named_category::1
""".split()
)


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
