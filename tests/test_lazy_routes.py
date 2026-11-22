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

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from tessellate.api import app as app_module

SKIP_METHODS = {"HEAD", "OPTIONS"}


def _walk(routes, prefix=""):
    """(method, path) of every route, included routers walked through (see
    tests/test_every_route_is_locked.py for why a flat filter is not enough)."""
    for route in routes:
        inner = getattr(route, "original_router", None)
        if inner is not None:
            context = getattr(route, "include_context", None)
            yield from _walk(inner.routes, prefix + getattr(context, "prefix", ""))
            continue
        if isinstance(route, APIRoute):
            for method in sorted(set(route.methods or []) - SKIP_METHODS):
                yield method, prefix + route.path


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
            app_module._first_segment(path) for _method, path in _walk(router.routes, router.prefix)
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
