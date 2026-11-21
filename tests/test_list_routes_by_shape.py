"""A GET that returns a list, or a dict holding one, takes a `limit` or says why not.

Audit 2026-10-05, ARCH-13: `tests/test_list_endpoints_page.py` keys on a
function named `list_*`, so it never saw `/graph`, `/entries/link-suggestions`,
`/documents/outline` or `/entries/query`. This lint keys on what a route
returns instead: a `list[...]` response (its annotation or `response_model`),
or a `return {...}` whose values include a list built in the route (a
comprehension, `list(...)`, `sorted(...)`, `.all()`, `_to_out_bulk`). Such a
route takes a `limit` query parameter, or is named below with the reason its
size does not grow with the notebook. A row marked **open** grows with the
notebook and has no page yet: the list of those may only shrink.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
import textwrap
import typing

from fastapi import APIRouter
from fastapi.routing import APIRoute

import tessellate.api as api

LISTY_CALLS = {"list", "sorted", "all", "_to_out_bulk", "scalars"}

#: Unpaged list routes, each with why its size is bounded (2026-10-05).
BOUNDED = {
    "/files/readings": "one file's readings: a caption, two OCR texts and its page reads, bounded by the file's page count",
    "/timeline/digest": "a span's notes, cut at SPAN_NOTES_MAX (200); `more` says how many were left out",
    "/running-copies": "one row per copy of the app running on this computer, a handful at most",
    "/insights/patterns": "one line per pattern rule, a fixed set in ai/insights.py",
    "/insights/remarks": "the best six things the companion could say, cut by the route",
    "/ask-history/{turn_id}": "one saved turn's raw results, capped when the turn was saved",
    "/backups": "one row per backup file, made on purpose and few",
    "/chat/modes": "the chat modes this app ships",
    "/chat/recent": "the last questions asked, capped by `_recent_questions`",
    "/chat/suggestions": "a handful of starter questions built from two categories",
    "/chat/tools": "the AI tools this app defines",
    "/suggestions/dismissed/items": "the suggestions said no to, newest first, cut at DISMISSED_LIST_MAX (200); `more` says how many were left out",
    "/documents/contents": "Replace in every document reads them whole, capped at CONTENTS_READ_MAX (1,000)",
    "/documents/outline": "capped at OUTLINE_DOCUMENTS documents",
    "/documents/{document_id}/ai-edit-log": "one document's AI edits",
    "/documents/{document_id}/bookmarks": "the bookmarks attached to one document",
    "/documents/{document_id}/revisions": "one document's revisions",
    "/embedding-models": "the embedding models this app offers, and its own install log",
    "/entries/changes": "ids changed since a stamp, capped at CHANGES_IDS_MAX (60); `more` says to re-read the list",
    "/entries/link-suggestions": "at most twelve suggestions",
    "/entries/most-accessed": "the top five",
    "/entries/{entry_id}/bookmarks": "the bookmarks attached to one note",
    "/entries/{entry_id}/history": "one note's history, paged by `before` (HISTORY_PAGE rows)",
    "/entries/{entry_id}/related": "the three closest notes",
    "/extras": "the optional installs this app knows about",
    "/graph/match": "ids only, capped at 5,000 matches",
    "/graph/path": "one path between two notes",
    "/insights/on-this-day": "the first five matches, read as five",
    "/insights/stats": "per category, and categories are few by design",
    "/insights/tag-cloud": "the top sixty tags",
    "/learned/export": "an export, read whole on purpose, capped at 10,000 facts",
    "/privacy/receipt": "this app's own switches",
    "/spaces": "the person's spaces, a handful",
    "/tidy/{key}": "capped at tidy.MAX_ROWS (300) rows; `count` still says how many the review found",
    "/websearch/providers": "the search providers this app knows",
}

#: Grows with the notebook and has no page yet. May only shrink.
OPEN: dict[str, str] = {}


def _routes():
    for info in pkgutil.iter_modules(api.__path__):
        module = importlib.import_module(f"tessellate.api.{info.name}")
        for value in vars(module).values():
            if isinstance(value, APIRouter):
                yield from (r for r in value.routes if isinstance(r, APIRoute))


def _returns_a_list(route: APIRoute) -> bool:
    if typing.get_origin(route.response_model) is list:
        return True
    try:
        hint = typing.get_type_hints(route.endpoint).get("return")
    except Exception:  # noqa: BLE001  # a forward reference the module never resolves
        hint = None
    if typing.get_origin(hint) is list:
        return True
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(route.endpoint)))
    except (OSError, TypeError, SyntaxError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            for value in node.value.values:
                if isinstance(value, ast.ListComp) or (isinstance(value, ast.List) and value.elts):
                    return True
                if isinstance(value, ast.Call):
                    func = value.func
                    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                    if name in LISTY_CALLS:
                        return True
    return False


def _unpaged() -> set[str]:
    found = set()
    for route in _routes():
        if "GET" not in route.methods or not _returns_a_list(route):
            continue
        if "limit" not in {p.name for p in route.dependant.query_params}:
            found.add(route.path)
    return found


def test_every_unpaged_list_route_says_why():
    unpaged = _unpaged()
    unexplained = sorted(unpaged - set(BOUNDED) - set(OPEN))
    assert not unexplained, (
        "these GET routes return a list without a `limit`: add the parameter, or name "
        f"each in BOUNDED with why its size does not grow with the notebook: {unexplained}"
    )


def test_no_row_outlives_its_route():
    unpaged = _unpaged()
    stale = sorted((set(BOUNDED) | set(OPEN)) - unpaged)
    assert not stale, f"these rows name routes that take a limit now, or are gone: {stale}"
