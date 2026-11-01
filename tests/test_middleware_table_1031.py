"""The middleware stack and the router list are tables with reasons (audit 1031 AR9).

The order is load-bearing and used to live only in a call sequence: compression
innermost so it sees real lengths, the API version outermost so every check sees
the path without its prefix. A new layer or router is a row, and a row that
moves or loses its reason fails here.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from tessellate.api import app as app_module
from tessellate.api.app import MIDDLEWARE, ROUTERS, create_app

#: Innermost first. Changing this list is changing the order a request is checked in.
EXPECTED_ORDER = [
    "GZipMiddleware",
    "OriginCheckMiddleware",
    "VaultScope",
    "HostCheckMiddleware",
    "SpaceGuard",
    "RequestPulse",
    "BodyCapMiddleware",
    "SecurityHeadersMiddleware",
    "ApiVersionMiddleware",
]


def test_the_order_is_the_one_written_down():
    assert [layer.cls.__name__ for layer in MIDDLEWARE] == EXPECTED_ORDER


def test_every_layer_says_why_it_is_there():
    for layer in MIDDLEWARE:
        assert len(layer.reason) >= 30, layer.cls.__name__
        assert layer.reason[0].isupper() and layer.reason.rstrip().endswith((".", ")")), layer.reason


def test_the_built_app_runs_them_outermost_first(app_state):  # noqa: ARG001  (a data dir of its own)
    built = [m.cls.__name__ for m in create_app().user_middleware]
    assert built == list(reversed(EXPECTED_ORDER))


def test_every_router_module_is_in_the_table_once():
    seen = [id(router) for router, _gate in ROUTERS]
    assert len(seen) == len(set(seen))
    missing = []
    for info in pkgutil.iter_modules([str(Path(app_module.__file__).parent)]):
        if not info.name.startswith("routes_"):
            continue
        module = importlib.import_module(f"tessellate.api.{info.name}")
        for name in ("router", "open_router", "media_router", "jobs_router", "files_router", "capture_router"):
            router = getattr(module, name, None)
            if router is not None and id(router) not in seen and getattr(router, "routes", None):
                missing.append(f"{info.name}.{name}")
    assert not missing, missing


def test_the_gates_are_the_three_that_exist():
    assert {gate for _router, gate in ROUTERS} == {app_module.OPEN, app_module.LOCKED, app_module.MEDIA}
