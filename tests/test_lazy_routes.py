"""The lazy router host (L-world-class-230): a route module is included at its first request.

`create_app` names its routers in `ROUTER_ROWS` instead of importing them, and
`_LazyRouters` includes a row's router the first time a request's path starts
with one of the row's segments. These tests hold the four promises that makes:
a first request to a lazy prefix is served, the unlock still guards it before
and after its router is included, `/openapi.json` lists every route, and a
path no route serves is still a 404. Each builds a lazy app explicitly, since
`create_app()` under pytest is eager.
"""

from __future__ import annotations

import logging
import random
import re

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.routing import Mount, Route, WebSocketRoute

from tessellate.api import app as app_module

SKIP_METHODS = {"HEAD", "OPTIONS"}


def _walk(routes, prefix="", segments=None):
    """(method, path) of every route, included routers walked through (see
    tests/test_every_route_is_locked.py for why a flat filter is not enough).
    With `segments` (a row's), a route that is not an APIRoute (websocket, mount,
    add_route) must start with one of them: the walk cannot list it as a method and
    path, so the row's promise about it would otherwise go unchecked."""
    for route in routes:
        inner = getattr(route, "original_router", None)
        if inner is not None:
            context = getattr(route, "include_context", None)
            yield from _walk(inner.routes, prefix + getattr(context, "prefix", ""), segments)
            continue
        if isinstance(route, APIRoute):
            for method in sorted(set(route.methods or []) - SKIP_METHODS):
                yield method, prefix + route.path
        elif segments is not None:
            first = app_module._first_segment(prefix + getattr(route, "path", ""))
            assert first in segments.split(), (type(route).__name__, prefix + getattr(route, "path", ""))


def _row_index(module):
    return next(i for i, row in enumerate(app_module.ROUTER_ROWS) if row.module == module)


def _setup(client):
    token = client.post("/auth/setup", json={"password": "first-pass"}).json()["token"]
    return {"X-Auth-Token": token}


def test_each_row_names_exactly_the_segments_its_routes_start_with():
    """The host's correctness rests on this: a row not yet included must not
    serve a path outside its segments, or a request could miss its route."""
    wrong = {}
    for row in app_module.ROUTER_ROWS:
        router = row.router()
        served = {
            app_module._first_segment(path) for _method, path in _walk(router.routes, router.prefix, row.segments)
        }
        if served != set(row.segments.split()):
            wrong[f"{row.module}.{row.attr}"] = sorted(served)
    assert not wrong, wrong


def test_a_lazy_app_includes_nothing_until_asked(app_state):  # noqa: ARG001
    app = app_module.create_app(lazy_routes=True)
    assert not any(app.state.lazy_routes.loaded)


def test_the_first_request_to_a_lazy_prefix_is_served(app_state):  # noqa: ARG001
    app = app_module.create_app(lazy_routes=True)
    client = TestClient(app)
    headers = _setup(client)
    host = app.state.lazy_routes
    assert not host.loaded[_row_index("routes_tags")]
    response = client.get("/tags", headers=headers)
    assert response.status_code == 200, response.text
    assert host.loaded[_row_index("routes_tags")]
    # Only the rows that could serve `/tags` (and `/auth`, for the setup) came in.
    assert not host.loaded[_row_index("routes_chat")]


def test_the_unlock_guards_a_lazy_route_before_and_after_it_is_included(app_state):  # noqa: ARG001
    app = app_module.create_app(lazy_routes=True)
    client = TestClient(app)
    headers = _setup(client)
    host = app.state.lazy_routes
    index = _row_index("routes_tags")
    assert not host.loaded[index]
    # The request that includes the router is itself refused: the gate is on the
    # router from the moment it is included, not from the next request.
    assert client.get("/tags").status_code == 401
    assert host.loaded[index]
    assert client.get("/tags").status_code == 401
    assert client.get("/tags", headers=headers).status_code == 200


def test_middleware_applies_to_a_lazy_route_as_to_an_eager_one(app_state):  # noqa: ARG001
    lazy = TestClient(app_module.create_app(lazy_routes=True))
    eager = TestClient(app_module.create_app(lazy_routes=False))
    headers = _setup(lazy)
    a = lazy.get("/tags", headers=headers)
    b = eager.get("/tags", headers=headers)
    assert a.status_code == b.status_code == 200
    assert "content-security-policy" in a.headers
    assert set(a.headers) == set(b.headers)


def test_openapi_lists_every_route_of_a_lazy_app(app_state):  # noqa: ARG001
    lazy = TestClient(app_module.create_app(lazy_routes=True))
    eager = TestClient(app_module.create_app(lazy_routes=False))
    headers = _setup(lazy)
    lazy_paths = lazy.get("/openapi.json", headers=headers).json()["paths"]
    eager_paths = eager.get("/openapi.json", headers=headers).json()["paths"]
    assert len(lazy_paths) > 200
    assert lazy_paths == eager_paths


def test_a_fully_loaded_lazy_app_has_the_eager_routes_in_the_eager_order(app_state):  # noqa: ARG001
    lazy = app_module.create_app(lazy_routes=True)
    # Included out of table order on purpose: the host still places each in its row's slot.
    TestClient(lazy).get("/whiteboard")
    TestClient(lazy).get("/entries")
    app_module.load_all_routes(lazy)
    eager = app_module.create_app(lazy_routes=False)
    assert list(_walk(lazy.routes)) == list(_walk(eager.routes))


def test_a_path_no_route_serves_is_still_a_404(app_state):  # noqa: ARG001
    lazy = TestClient(app_module.create_app(lazy_routes=True))
    eager = TestClient(app_module.create_app(lazy_routes=False))
    headers = _setup(lazy)
    for path in ("/no-such-route", "/tags/no/such/route/here", "/entries/1/no-such-child"):
        a = lazy.get(path, headers=headers)
        b = eager.get(path, headers=headers)
        assert a.status_code == b.status_code, path
    assert lazy.get("/no-such-route", headers=headers).status_code == 404


def test_the_routers_table_still_reads_as_router_gate_pairs():
    """`ROUTERS` is built on reading (module `__getattr__`) for the tests that
    hold the table to the routers; it must keep the old shape."""
    pairs = app_module.ROUTERS
    assert len(pairs) == len(app_module.ROUTER_ROWS)
    assert all(hasattr(router, "routes") and gate in {"open", "locked", "media"} for router, gate in pairs)


def test_importing_the_app_imports_only_the_route_modules_it_calls():
    """The point of the host: app import pays for three route modules, not a hundred.
    `routes_auth` (the unlock and the vault layer), `routes_diag` (the build hash) and
    `routes_update` (the launcher choice at start) are called by app.py itself.
    Measured 2026-11-22: app import 2,639 to 874 ms median wall, five runs."""
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    probe = (
        "import sys, tessellate.api.app\n"
        "print(' '.join(sorted(m for m in sys.modules if m.startswith('tessellate.api.routes_')"
        " or m == 'tessellate.api.run_sandbox')))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", probe], cwd=root, capture_output=True, text=True, check=True,
        env={"PYTHONPATH": str(root / "src"), "PATH": ""},
    )
    assert out.stdout.split() == [
        "tessellate.api.routes_auth", "tessellate.api.routes_diag", "tessellate.api.routes_update",
    ]


def test_the_segment_walk_catches_a_route_that_is_not_an_api_route():
    from fastapi import APIRouter

    router = APIRouter()
    router.routes.append(WebSocketRoute("/stray/ws", lambda ws: None))
    router.routes.append(Mount("/other", routes=[Route("/x", lambda r: None)]))
    with pytest.raises(AssertionError):
        list(_walk(router.routes, "", "/entries"))
    assert list(_walk(router.routes[:1], "", "/stray")) == []


def test_no_row_router_has_lifespan_handlers():
    """A lazily included router's startup, shutdown or lifespan handlers would never run
    (`include_router` does not copy them), so none may have one."""
    bad = {}
    for row in app_module.ROUTER_ROWS:
        router = row.router()
        found = [
            name
            for name in ("on_startup", "on_shutdown")
            if getattr(router, name, None)
        ]
        if getattr(router, "lifespan_context", None) is not None and not _is_default_lifespan(router):
            found.append("lifespan")
        if found:
            bad[f"{row.module}.{row.attr}"] = found
    assert not bad, bad


def _is_default_lifespan(router) -> bool:
    """The default, or the wrapper `include_router` makes when a router includes others
    (its nested routers are rows or modules of their own, held to the same rule)."""
    context = router.lifespan_context
    return type(context).__name__ == "_DefaultLifespan" or context.__qualname__.startswith("_merge_lifespan_context")


def test_a_router_that_fails_to_import_is_logged_and_the_rest_still_load(app_state, monkeypatch, caplog):  # noqa: ARG001
    rows = list(app_module.ROUTER_ROWS)
    index = _row_index("routes_entries_relations")
    rows[index] = rows[index]._replace(module="no_such_route_module_for_test")
    monkeypatch.setattr(app_module, "ROUTER_ROWS", tuple(rows))
    app = app_module.create_app(lazy_routes=True)
    client = TestClient(app, raise_server_exceptions=False)
    headers = _setup(client)
    with caplog.at_level(logging.ERROR):
        client.get("/entries", headers=headers)
        client.get("/entries", headers=headers)
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR and "no_such_route_module_for_test" in r.getMessage()]
    assert len(errors) == 1, "one error naming the module, not one per request"
    host = app.state.lazy_routes
    sharing = [i for i in host.by_segment["/entries"] if i != index]
    assert sharing and all(host.loaded[i] for i in sharing)
    assert not host.loaded[index]


def _concrete(path):
    path = re.sub(r"\{[^}]*:path\}", "a/b", path)
    return re.sub(r"\{[^}]*\}", "1", path)


def test_a_lazy_app_answers_every_route_unauthenticated_as_the_eager_app_does(app_state):  # noqa: ARG001
    """The gate parity of the whole table: after a password is set, every (method, path)
    of the eager app is sent with no token to both apps, in a fixed shuffled order, and
    the status codes must match."""
    eager_app = app_module.create_app(lazy_routes=False)
    pairs = sorted(set(_walk(eager_app.routes)))
    random.Random(1).shuffle(pairs)
    eager = TestClient(eager_app, raise_server_exceptions=False)
    lazy = TestClient(app_module.create_app(lazy_routes=True), raise_server_exceptions=False)
    # A third client sets the password: the one that does keeps its media cookie.
    _setup(TestClient(app_module.create_app(lazy_routes=False)))
    # Acting routes that are open by design (a shutdown, a sync, a handoff) are sent as GET only.
    skip = ("/auth", "/shutdown", "/sync", "/mcp", "/origin-handoff", "/reminders/act")
    diffs = []
    for method, path in pairs:
        url = _concrete(path)
        if method != "GET" and url.startswith(skip):
            continue
        a, b = lazy.request(method, url).status_code, eager.request(method, url).status_code
        if a != b:
            diffs.append((method, url, a, b))
    assert not diffs, diffs[:20]


def _unused_routes_module():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "unused_routes.py"
    spec = importlib.util.spec_from_file_location("unused_routes", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_unused_routes_report_sees_a_lazy_only_route(app_state):  # noqa: ARG001
    """scripts/unused_routes.py walked the top level of `app.routes`, where an
    included router is one node, so it listed 0 routes; it must reach a route
    that only a lazy row serves, on an app where no request has loaded it."""
    module = _unused_routes_module()
    index = _row_index("routes_hello")
    row = app_module.ROUTER_ROWS[index]
    lazy_path = next(path for _m, path in _walk(row.router().routes))
    app = app_module.create_app(lazy_routes=True)
    assert not app.state.lazy_routes.loaded[index]
    listed = {path for path, _methods, _name in module.unreferenced(app, corpus="")}
    assert lazy_path in listed
    assert "/health" in listed
    again = module.unreferenced(app_module.create_app(lazy_routes=True), corpus=lazy_path)
    assert lazy_path not in {path for path, _m, _n in again}


def test_every_route_on_the_unused_routes_allow_list_is_still_a_route(app_state):  # noqa: ARG001
    """An allow-list entry names a caller the text search cannot see; once its
    route is gone the entry would hide nothing and must go with it."""
    module = _unused_routes_module()
    paths = {path for path, _route in module.flat_routes(app_module.create_app(lazy_routes=True))}
    assert sorted(set(module.ALLOWED) - paths) == []
    assert all(reason.strip() for reason in module.ALLOWED.values())
