"""Route modules imported at their first request, not at app import (L-world-class-230).

Every FastAPI route decorator builds pydantic TypeAdapters (1,732 ModelFields for
the whole API), which was about 825 ms of a 2.06 s app import. Logging in to the
first screen reaches 20 of the route modules, so `BOOT_MODULES` stay eager and the
rest are hosted by a `LazyRouter`: an empty `APIRouter` included at the module's
own row of `app.ROUTER_ROWS`, behind that row's gate. FastAPI keeps an included
router as one `_IncludedRouter` node that rebuilds its routes whenever the router's
routes version moves, so when a request's path matches one of the module's path
templates (`route_table.PATHS`, generated, `tests/test_lazy_routes.py` holds it
fresh), the module is imported and its router is included *inside* the placeholder.
Its position, and so which of two overlapping paths wins, and its gate
dependencies, which the outer include carries, are the eager app's.

Anything that lists routes (the schema, the route tests) calls `load_all_routes`
first.
"""

from __future__ import annotations

import importlib
import re
import threading
from typing import Callable

from fastapi import APIRouter
from starlette.routing import compile_path, get_route_path
from starlette.types import Scope

PACKAGE = "tessellate.api"

#: The route modules the first screen after login reaches (29 requests, measured
#: 2026-11-22), plus `routes_debug`, which those import anyway. Imported by
#: `create_app`, as before; `tests/test_lazy_routes.py` holds the rest unimported.
BOOT_MODULES = frozenset(
    {
        "routes_ask_history", "routes_auth", "routes_backups", "routes_categories",
        "routes_chat_meta", "routes_conversations", "routes_entries", "routes_help",
        "routes_insights", "routes_kept_words", "routes_models", "routes_privacy",
        "routes_read", "routes_recordings", "routes_reminders", "routes_settings",
        "routes_settings_logs", "routes_spaces", "routes_tasks", "routes_update",
        "routes_debug",
    }
)

#: A module that only works once another has loaded: `routes_files_ocr.rf` is bound
#: by `routes_files` at its foot (an import there would close a cycle).
LOAD_FIRST: dict[str, tuple[str, ...]] = {"routes_files_ocr": ("routes_files",)}


def is_lazy(spec: str) -> bool:
    return spec.split(".", 1)[0] not in BOOT_MODULES


def resolve(spec: str) -> APIRouter:
    """`routes_x.router` to the router object, importing its module."""
    module_name, attr = spec.split(".", 1)
    for first in LOAD_FIRST.get(module_name, ()):
        importlib.import_module(f"{PACKAGE}.{first}")
    return getattr(importlib.import_module(f"{PACKAGE}.{module_name}"), attr)


def _pattern(paths: tuple[str, ...]) -> re.Pattern[str]:
    # One regex for the row: starlette's own compiled templates with their named
    # groups made plain, since two templates may name the same parameter.
    parts = [re.sub(r"\(\?P<\w+>", "(?:", compile_path(path)[0].pattern) for path in paths]
    return re.compile("|".join(f"(?:{part})" for part in parts) or r"(?!)")


class LazyRouter(APIRouter):
    """The placeholder for one `ROUTER_ROWS` row; see the module docstring."""

    def __init__(self, spec: str, paths: tuple[str, ...], on_load: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.spec = spec
        self._paths = paths
        # Each template's literal head: a C-speed `startswith` turns away nearly every
        # request, so the row's regex is compiled only when a path first gets past it
        # (82 rows compiled at create_app cost more than the import they save).
        self._heads = tuple({path.split("{", 1)[0] for path in paths})
        self._pattern: re.Pattern[str] | None = None
        self._on_load = on_load
        self._lock = threading.Lock()
        self.loaded = False

    def wants(self, path: str) -> bool:
        if not path.startswith(self._heads):
            return False
        if self._pattern is None:
            self._pattern = _pattern(self._paths)
        return bool(self._pattern.match(path))

    def load(self) -> None:
        if self.loaded:
            return
        with self._lock:  # the route warm-up thread and the event loop can both arrive
            if self.loaded:
                return
            self.include_router(resolve(self.spec))
            if self._on_load is not None:
                self._on_load()
            self.loaded = True

    def matches(self, scope: Scope):  # noqa: ANN201  (starlette's own signature)
        # Reached for every request the routers above did not claim (and for the
        # trailing-slash retry), so an unloaded row costs one `startswith`.
        if not self.loaded and self.wants(get_route_path(scope)):
            self.load()
        return super().matches(scope)


def lazy_rows(app) -> list[LazyRouter]:  # noqa: ANN001
    return [
        route.original_router
        for route in app.router.routes
        if isinstance(getattr(route, "original_router", None), LazyRouter)
    ]


def load_all_routes(app) -> None:  # noqa: ANN001
    """Every lazy row loaded, for whatever lists the app's routes."""
    for row in lazy_rows(app):
        row.load()


def router_paths(router: APIRouter, prefix: str = "") -> list[str]:
    """Every path template a router serves, nested includes walked through."""
    out: list[str] = []
    if getattr(router, "_low_priority_routes", None):
        raise ValueError("a lazy row with low-priority routes would answer before it loads")
    for route in router.routes:
        inner = getattr(route, "original_router", None)
        if inner is not None:
            out += router_paths(inner, prefix + (route.include_context.prefix or ""))
        elif hasattr(route, "routes"):
            raise ValueError(f"a mount in a lazy row is not handled: {route!r}")
        else:
            out.append(prefix + route.path)
    return list(dict.fromkeys(out))


def build_table(rows) -> dict[str, tuple[str, ...]]:  # noqa: ANN001
    """The path templates of every lazy row, the source of `route_table.PATHS`."""
    return {spec: tuple(router_paths(resolve(spec))) for spec, _gate in rows if is_lazy(spec)}


def render_table(table: dict[str, tuple[str, ...]]) -> str:
    lines = [
        '"""Generated by scripts/route_table.py: the path templates of every lazy router row.',
        "",
        "`api/lazy_routes.py` imports a row's module when a request matches one of these.",
        '`tests/test_lazy_routes.py` fails when this is stale."""',
        "",
        "PATHS: dict[str, tuple[str, ...]] = {",
    ]
    for spec, paths in table.items():
        lines.append(f"    {spec!r}: (")
        lines += [f"        {path!r}," for path in paths]
        lines.append("    ),")
    lines.append("}")
    return "\n".join(lines) + "\n"
