"""The lazy router host (L-world-class-230, `api/lazy_routes.py`).

A route module outside `BOOT_MODULES` is imported at the first request that
matches one of its paths. What must not change: the response, the gate, which
of two overlapping paths wins, and what the schema lists.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Match

from tessellate.api import app as app_module
from tessellate.api import lazy_routes, routes_auth
from tessellate.api.route_table import PATHS

ROOT = Path(__file__).resolve().parents[1]


def _fresh():
    return app_module.create_app()


def _eager(monkeypatch):
    """The app as it was before the lazy host: every row included at create_app."""
    with monkeypatch.context() as patch:
        patch.setattr(lazy_routes, "is_lazy", lambda _spec: False)
        app = app_module.create_app()
    assert not lazy_routes.lazy_rows(app)
    return app


def _row(app, spec):
    return next(row for row in lazy_routes.lazy_rows(app) if row.spec == spec)


def test_the_path_table_is_fresh():
    built = lazy_routes.render_table(lazy_routes.build_table(app_module.ROUTER_ROWS))
    on_disk = (ROOT / "src" / "tessellate" / "api" / "route_table.py").read_text(encoding="utf-8")
    assert built == on_disk, "run: PYTHONPATH=src python scripts/route_table.py"


def test_every_row_outside_the_boot_set_is_lazy_and_keeps_its_place(app_state):  # noqa: ARG001
    app = _fresh()
    rows = [spec for spec, _gate in app_module.ROUTER_ROWS if lazy_routes.is_lazy(spec)]
    assert set(PATHS) == set(rows)
    assert [row.spec for row in lazy_routes.lazy_rows(app)] == rows
    assert not any(row.loaded for row in lazy_routes.lazy_rows(app))
    # Each row keeps the gate its row names: the outer include carries it.
    gates = {"open": 0, "locked": 2, "media": 1}
    for route in app.router.routes:
        row = getattr(route, "original_router", None)
        if isinstance(row, lazy_routes.LazyRouter):
            gate = dict(app_module.ROUTER_ROWS)[row.spec]
            assert len(route.include_context.dependencies) == gates[gate], row.spec


def test_routers_still_resolves_every_row_in_order():
    resolved = app_module.ROUTERS
    assert [gate for _r, gate in resolved] == [gate for _s, gate in app_module.ROUTER_ROWS]
    assert all(router.routes for router, _gate in resolved)


def test_the_app_import_leaves_the_lazy_modules_unimported(tmp_path):
    probe = (
        "import sys, os; os.environ['TESSELLATE_DATA_DIR'] = sys.argv[1]\n"
        "from tessellate.api import app, lazy_routes\n"
        "app.create_app()\n"
        "rows = {spec.split('.')[0] for spec, _ in app.ROUTER_ROWS}\n"
        "print(sorted(m.split('.')[-1] for m in sys.modules if m.split('.')[-1] in rows))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", probe, str(tmp_path / "data")],
        capture_output=True, text=True, timeout=60, env={"PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin"},
    )
    assert out.returncode == 0, out.stderr[-2000:]
    loaded = eval(out.stdout.strip().splitlines()[-1])  # noqa: S307  (our own probe's list)
    assert set(loaded) == set(lazy_routes.BOOT_MODULES)


def test_a_lazy_rows_first_request_answers_as_the_eager_app(client, monkeypatch):
    client.post("/entries", json={"content": "A note about the garden.", "tags": ["tomatoes", "basil"]})
    first = client.get("/tags")
    assert _row(client.app, "routes_tags.router").loaded
    eager = TestClient(_eager(monkeypatch)).get("/tags")
    assert first.status_code == eager.status_code == 200
    assert first.json() == eager.json()
    assert set(first.json()) >= {"tomatoes", "basil"}


def test_the_gate_refuses_a_lazy_locked_route_without_a_session(app_state):  # noqa: ARG001
    client = TestClient(_fresh())
    made = client.post("/auth/setup", json={"password": "correct horse battery"})
    token = made.json()["token"]
    routes_auth._active_tokens.clear()
    assert client.get("/tags").status_code == 401
    assert _row(client.app, "routes_tags.router").loaded
    unlocked = client.post("/auth/unlock", json={"password": "correct horse battery"}).json()["token"]
    assert token and client.get("/tags", headers={"X-Auth-Token": unlocked}).status_code == 200


def test_an_open_lazy_row_stays_open(app_state):  # noqa: ARG001
    client = TestClient(_fresh())
    client.post("/auth/setup", json={"password": "correct horse battery"})
    routes_auth._active_tokens.clear()
    # The sandbox page is open by design (its row says why); locked it would be 401.
    page = client.get("/documents/run-sandbox")
    assert page.status_code == 200, page.status_code
    assert _row(client.app, "run_sandbox.router").loaded


def _concrete(template: str) -> str:
    return re.sub(r"\{[^}:]+(:(int|float))?\}", "1", re.sub(r"\{[^}:]+:path\}", "a/b", template))


def _target(app, method: str, path: str):
    """The endpoint the router picks for (method, path), and whether the match was full."""
    scope = {"type": "http", "method": method, "path": path, "root_path": "", "headers": [], "query_string": b""}
    partial = None
    for route in app.router.routes:
        match, _child = route.matches(scope)
        if match is Match.FULL:
            return _leaf(route, scope), "full"
        if match is Match.PARTIAL and partial is None:
            partial = route
    return (_leaf(partial, scope), "partial") if partial is not None else (None, "none")


def _leaf(route, scope):
    while hasattr(route, "_match"):  # FastAPI's included-router node
        _m, _child, inner, _ctx = route._match(scope)
        if inner is None:
            return None
        route = inner
    endpoint = getattr(route, "endpoint", None)
    return getattr(endpoint, "__qualname__", None) or f"{type(route).__name__} {getattr(route, 'path', '')}"


def _all_templates():
    for spec, _gate in app_module.ROUTER_ROWS:
        for template in lazy_routes.router_paths(lazy_routes.resolve(spec)):
            yield spec, template


def test_overlapping_paths_go_where_they_went_when_everything_was_eager(app_state, monkeypatch):  # noqa: ARG001
    templates = list(_all_templates())
    compiled = {spec: lazy_routes._pattern(tuple(t for s, t in templates if s == spec)) for spec, _ in templates}
    overlaps = sorted(
        {_concrete(t) for _spec, t in templates if sum(bool(p.match(_concrete(t))) for p in compiled.values()) > 1}
    )
    assert len(overlaps) > 10, overlaps  # the case this test exists for is common here
    eager = _eager(monkeypatch)
    wrong = []
    for path in overlaps:
        for method in ("GET", "POST", "DELETE"):
            want = _target(eager, method, path)
            got = _target(_fresh(), method, path)  # a fresh app: nothing loaded before this path
            if got != want:
                wrong.append(f"{method} {path}: {got} != {want}")
    assert not wrong, wrong


def test_a_trailing_slash_redirect_reaches_a_lazy_row(app_state, monkeypatch):  # noqa: ARG001
    lazy = TestClient(_fresh()).get("/tags/", follow_redirects=False)
    eager = TestClient(_eager(monkeypatch)).get("/tags/", follow_redirects=False)
    assert (lazy.status_code, lazy.headers.get("location")) == (eager.status_code, eager.headers.get("location"))


def test_the_schema_lists_every_route_before_any_was_requested(app_state, monkeypatch):  # noqa: ARG001
    app = _fresh()
    listed = app.openapi()
    assert all(row.loaded for row in lazy_routes.lazy_rows(app))
    eager = _eager(monkeypatch).openapi()
    assert len(listed["paths"]) > 400
    assert listed == eager


@pytest.mark.parametrize("spec", ["routes_files_ocr.router"])
def test_a_row_that_needs_another_module_loads_it_first(spec):
    probe = (
        "from tessellate.api import lazy_routes\n"
        f"lazy_routes.resolve({spec!r})\n"
        "from tessellate.api import routes_files_ocr\n"
        "assert routes_files_ocr.rf is not None\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, timeout=60,
        env={"PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin"},
    )
    assert out.returncode == 0, out.stderr[-2000:]


def test_the_unused_routes_report_sees_a_lazy_only_route():
    """scripts/unused_routes.py walked the top level of `app.routes`, where an
    included router is one node, so it listed 0 routes; it must reach a route
    that only a lazy row serves, on an app where no request has loaded it."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("unused_routes", ROOT / "scripts" / "unused_routes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    lazy_path = PATHS["routes_hello.router"][0]
    app = _fresh()
    assert not _row(app, "routes_hello.router").loaded
    listed = {path for path, _methods, _name in module.unreferenced(app, corpus="")}
    assert lazy_path in listed
    assert "/health" in listed
    assert not {path for path, _m, _n in module.unreferenced(_fresh(), corpus=lazy_path)} & {lazy_path}


def test_every_route_on_the_unused_routes_allow_list_is_still_a_route():
    """An allow-list entry names a caller the text search cannot see; once its
    route is gone the entry would hide nothing and must go with it."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("unused_routes_allow", ROOT / "scripts" / "unused_routes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    paths = {path for path, _route in lazy_routes.flat_routes(_fresh())}
    assert sorted(set(module.ALLOWED) - paths) == []
    assert all(reason.strip() for reason in module.ALLOWED.values())
