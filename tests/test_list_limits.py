"""Every list endpoint takes a limit, or says in writing why it does not.

WORLD_CLASS_PLAN section 10, F2: "25 list endpoints, 3 accept `limit`. Every
list is O(notebook)." The count in that row was taken with `grep`, which
counts function definitions rather than routes and cannot tell a list of
chat modes (a fixed seven) from a list of every attachment in the notebook.
This walks the app the way `test_every_route_is_locked.py` does, so a route
added tomorrow is checked too, and it separates the two cases with an
allowlist that carries a reason per line rather than a count.

The rule is deliberately "takes a limit", not "paginates with a cursor". A
cursor is better for a list somebody scrolls and worse for a list somebody
counts, and half of these are read once into a dialog. What matters, and what
this asserts, is that no route's response size is decided by how long the
person has been using the app.
"""

from __future__ import annotations

import inspect

from fastapi.routing import APIRoute

from tessellate.api.app import create_app

#: A list route is allowed to return everything only when "everything" is a
#: number the app itself fixes. One line per route, with the bound.
BOUNDED = {
    # What is running now: one row per live job, bounded by the workers.
    "/activity",
    # The chat modes and the tool catalogue are code, not data: both are
    # literals in the source and change only when somebody edits them.
    "/chat/modes",
    "/chat/tools",
    # The slash commands (ai/slash.py): a registry in code, like the modes.
    "/chat/commands",
    "/skills",
    "/extras",
    # The document file types the importer accepts: also a literal.
    "/documents/file-types",
    # Installed embedding models: bounded by what is on the disk, and the
    # person put every one of them there on purpose.
    "/embedding-models",
    # Backups are pruned by their own retention rule, which is the bound.
    "/backups",
    # Only *running* work is listed (ARCHITECTURE section 6), so this is
    # bounded by how many jobs the app can run at once, which is small.
    "/tasks",
    # One page of the update feed, bounded by the remote API's own page size.
    "/update/releases",
    # Per document rather than per notebook, and a document's AI edit history
    # is bounded by its own revision retention.
    "/documents/{document_id}/ai-edit-log",
}


def _routes(app):
    """Every (method, path, endpoint) the app serves.

    Included routers are lazy entries holding the real router, so a plain
    `isinstance(route, APIRoute)` filter sees three routes out of two hundred.
    `test_every_route_is_locked.py` records that trap at length.
    """

    def walk(routes, prefix=""):
        for route in routes:
            inner = getattr(route, "original_router", None)
            if inner is not None:
                context = getattr(route, "include_context", None)
                yield from walk(inner.routes, prefix + getattr(context, "prefix", ""))
                continue
            if isinstance(route, APIRoute):
                yield route, prefix + route.path

    yield from walk(app.routes)


def test_every_list_route_takes_a_limit_or_is_bounded_by_the_app(app_state):
    app = create_app()
    unbounded = []
    for route, path in _routes(app):
        if "GET" not in (route.methods or set()):
            continue
        if not route.endpoint.__name__.startswith("list_"):
            continue
        if path in BOUNDED:
            continue
        params = inspect.signature(route.endpoint).parameters
        if not {"limit", "cursor", "page"} & set(params):
            unbounded.append(f"{path} ({route.endpoint.__name__})")
    assert not unbounded, (
        "these list routes return as many rows as the notebook has; give each a "
        "limit, or add it to BOUNDED with the reason its size is fixed: "
        + ", ".join(sorted(unbounded))
    )


def test_the_allowlist_names_routes_that_exist(app_state):
    """An allowlist entry for a route that is gone is an exemption nobody
    granted, waiting for a new route to be given the same path."""
    app = create_app()
    served = {path for _route, path in _routes(app)}
    assert not (BOUNDED - served), f"BOUNDED names routes the app does not serve: {sorted(BOUNDED - served)}"
