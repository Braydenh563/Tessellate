"""Routes are thin (decision 55, LEDGER L-world-class-123).

A converted route parses the request, calls its service, and shapes the
answer. This holds the line for the routes moved so far: their bodies run
no ORM query of their own, the helpers that moved are not defined under
`api/` again, and a service never reaches back into `api/` or HTTP.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "tessellate"
API = SRC / "api"

#: The services, and what each may not import (the layers above it).
SERVICES = (
    SRC / "entry" / "service.py",
    SRC / "entry" / "capture.py",
    SRC / "entry" / "listing.py",
    SRC / "entry" / "assist.py",
    SRC / "entry" / "editing.py",
)
_UPWARD = ("tessellate.api", "fastapi", "starlette")

#: Route module -> the route functions already moved behind a service.
CONVERTED = {
    "routes_entries.py": {
        "create_entry",
        "list_entries",
        "entry_changes",
        "query_entries",
        "daily_journal",
        "daily_note",
        "open_daily_note",
        "stop_filing_one",
        "decide_filing",
        "filing_status",
        "extract_commit",
        "make_all_private",
        "set_entry_privacy",
        "generate_entry_title",
        "remove_entry_title",
        "suggest_tags_for_draft",
        "answer_suggested_tags",
        "add_context",
        "improve_writing",
        "update_entry",
    },
    "routes_entries_links.py": {"entry_connections"},
}

#: Helpers that moved to a service: no module under `api/` defines them again.
MOVED_OUT = {
    "_connection_cue",
    "_stored_connections",
    "_add_referenced",
    "_add_wiki_outgoing",
    "_boards_of",
    "_wiki_link_targets_of",
    "_connected_files",
    "_daily_notes",
    "_daily_note",
    "stop_filing",
    "stop_all_filing",
    "_filing_similar",
    "_choices_filled",
    "_offered_categories",
    "_filing_why",
    "_filed_by",
    "_mark_new_entry",
    "_decide_filing",
    "_new_note_text",
    "_finish_new_entry",
    "_starts_sealed",
    "_cheer_note_count",
    "_find_near_duplicate",
    "_discard_tags",
    "_content_change",
    "_after_content_edit",
    "_wiki_rename",
    "_apply_flags",
    "_stored_form",
    "_readable",
}

#: The ORM verbs and statement builders a route body may not call itself.
_ORM = re.compile(
    r"\b(?:session|db)\.(?:query|get|execute|scalar|scalars|add|add_all|delete|merge|flush)\("
    r"|\bselect\(|\bsa_delete\(|\bsa_update\("
)


def _functions(path: Path) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def test_a_converted_route_runs_no_query_of_its_own():
    heavy = []
    for module, names in CONVERTED.items():
        path = API / module
        source = path.read_text(encoding="utf-8").splitlines()
        defined = _functions(path)
        missing = sorted(names - set(defined))
        assert not missing, f"{module} no longer defines {missing}: update CONVERTED"
        for name in sorted(names):
            node = defined[name]
            body = "\n".join(source[node.lineno - 1 : node.end_lineno])
            if _ORM.search(body):
                heavy.append(f"{module}::{name}")
    assert not heavy, f"these routes query the database themselves; call their service: {heavy}"


def test_a_moved_helper_is_not_defined_under_api_again():
    back = []
    for path in sorted(API.glob("*.py")):
        for name in sorted(MOVED_OUT & set(_functions(path))):
            back.append(f"{path.name}::{name}")
    assert not back, f"moved to a service, defined under api/ again: {back}"


def test_a_service_never_imports_the_routes_or_http():
    upward = []
    for path in SERVICES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            upward += [f"{path.parent.name}/{path.name}: {n}" for n in names if n.startswith(_UPWARD)]
    assert not upward, upward


def test_the_lint_sees_a_query_in_a_route_body():
    """A ratchet that parses nothing passes forever: pin that the pattern bites."""
    assert _ORM.search("    rows = session.scalars(select(Entry)).all()")
    assert not _ORM.search("    return entry_service.journal(session, last, days)")
