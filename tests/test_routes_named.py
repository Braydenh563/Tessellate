"""Every route has a test naming its path (WORLD_CLASS_PLAN 26.2, decision 59): a ratchet.

The route table is read from the real app (so `include_router` prefixes are
counted, which a regex over the route files misses). A route is named when
some string literal in `tests/` has the same segments: a `{param}` segment in
the route matches anything, and a hole (`{eid}`, `%s`) in the test's literal
matches only a route's own `{param}` segment, so `/entries/{eid}` does not
name `/entries/export`. A literal ending in `/` is a prefix with one
segment to come (`"/documents/" + id`). Methods are not compared: the rule
is the path, which is what the decision says.

The seed began as the 49 routes found on 2026-10-10 and is now empty: every
route is named. A route no test names fails; add a test that calls the path,
or delete the route.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._repo_files import repo_files

TESTS = Path(__file__).resolve().parent

#: Empty since the last 49 were named (ledger 1573). A route that no test names
#: fails `test_no_new_unnamed_route`; do not add a line here, add a test.
SEED: frozenset[str] = frozenset()

_LITERAL = re.compile(r"""["'`](/[A-Za-z0-9_\-./{}$%:+]*)""")


def route_table(app) -> set[tuple[str, str]]:  # noqa: ANN001
    """(method, path) for every route; FastAPI keeps included routers as nodes."""
    out: set[tuple[str, str]] = set()

    def walk(routes, prefix: str) -> None:  # noqa: ANN001
        for r in routes:
            if hasattr(r, "original_router"):
                walk(r.original_router.routes, prefix + (r.include_context.prefix or ""))
            elif hasattr(r, "methods") and hasattr(r, "endpoint"):
                for m in r.methods - {"HEAD", "OPTIONS"}:
                    out.add((m, prefix + r.path))
            elif hasattr(r, "routes") and hasattr(r, "app"):
                walk(r.routes, prefix + r.path)

    walk(app.routes, "")
    return out


def _test_literals() -> list[tuple[list[str], bool]]:
    text = ""
    for p in repo_files(TESTS, suffixes=(".py",)):
        if p.name != Path(__file__).name:  # this file's seed would name every route in it
            text += p.read_text(encoding="utf-8", errors="ignore") + "\n"
    lits = []
    for lit in set(_LITERAL.findall(text)):
        path = lit.split("?")[0]
        lits.append(([s for s in path.split("/") if s], path.endswith("/")))
    return lits


def untested_routes(app) -> set[str]:  # noqa: ANN001
    lits = _test_literals()
    missing = set()
    for method, path in route_table(app):
        segs = [s for s in path.split("/") if s]
        named = False
        for parts, prefix in lits:
            if not parts and not segs:
                named = True
            elif prefix and len(segs) == len(parts) + 1:
                named = all(a == b or b.startswith("{") for a, b in zip(parts, segs))
            elif not prefix and len(segs) == len(parts):
                named = all(a == b or b.startswith("{") for a, b in zip(parts, segs))
            if named:
                break
        if not named:
            missing.add(f"{method} {path}")
    return missing


def _app(tmp_path, monkeypatch):  # noqa: ANN001
    monkeypatch.setenv("TESSELLATE_DATA_DIR", str(tmp_path / "data"))
    from tessellate.api.app import create_app

    return create_app()


def test_no_new_unnamed_route(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    new = untested_routes(_app(tmp_path, monkeypatch)) - SEED
    assert not new, "a route no test names; add a test that calls its path, or remove it:\n  " + "\n  ".join(sorted(new))


def test_the_seed_only_shrinks(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    stale = SEED - untested_routes(_app(tmp_path, monkeypatch))
    assert not stale, "now named by a test, so delete it from SEED:\n  " + "\n  ".join(sorted(stale))
