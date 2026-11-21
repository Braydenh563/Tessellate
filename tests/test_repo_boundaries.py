"""The routers are not the data layer (audit 1031 AR1, INBOX 1499).

A resource moved behind its repository (`src/tessellate/repo/<resource>.py`)
is queried nowhere else under `api/`: no router imports its models. And the
ORM calls still left in the routers are counted, a ratchet that only goes
down as each resource moves (seeded 2026-11-01 at 884 after bookmarks moved,
876 after relation types; 910 before, counting `session.`/`db.` query, get, execute, scalar(s), add,
delete, merge, and `select(`/`sa_delete(`/`sa_update(`).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

API = Path(__file__).resolve().parents[1] / "src" / "tessellate" / "api"

#: Each moved resource and the models only its repository may name.
MOVED = {
    "bookmarks": {"Bookmark", "EntryBookmark", "DocumentBookmark"},
    "relation_types": {"RelationType"},
    "reminders": {"Reminder"},
    "properties": {"EntryProperty"},
    "relations": {"EntryLink"},
    "documents": {"Document", "DocumentLink", "DocumentRevision", "DocumentAiEdit"},
}

#: A route that deletes every row of a space walks every model at once; the
#: spaces repository will own it when spaces move (row 3a, step order).
CROSS_RESOURCE = {"routes_spaces.py"}

#: 876 at arch1518; the voice reads (the dashboard line, the companion's remarks)
#: moved to repo/voice.py: 872; the board bin guard to repo/content.py: 870;
#: reminders to repo/reminders.py (its router, the timeline, meetings, debug
#: and two chat readers): 843; documents' history and AI-edit log and the
#: document list, contents and write verbs to repo/documents.py: 811; the
#: other routers' reads of Document and DocumentLink (chat, graph, notes,
#: library, timeline, bench, mentions) to repo/documents.py: 767; the chat's
#: tag read (notes sharing a rare tag) to repo/tags.py: 765. Tags are a JSON
#: list in `Entry.tags`, not a table, so they have no model in `MOVED`; the
#: properties index reads (the graph's note types, the timeline's meeting dates
#: and their join) to repo/properties.py: 757; the links' reads (the graph's counts,
#: columns and pairs, the entries routes' suggestions, tensions and link-by-id
#: lookups, the inbox's untyped scan, the map's and the chat's neighbours, the
#: backlinks' wiki sources, the diagnostics and export counts) to
#: repo/relations.py: 717; the categories' name and count reads (the category
#: routes' lookup, Insights and chat suggestion counts, the search hit's
#: category, the graph fingerprint, exports and counts, the map's and the
#: board's category names) to repo/categories.py: 694; the spaces' id, list, find
#: and count reads to repo/spaces.py: 688; the chat attach paths' Library upload
#: reads to repo/uploads.py: 687; the affinity sort's sticky read to
#: repo/whiteboard.py: 686; the journal and Connections reads to entry/service.py
#: (decision 55, L-world-class-123): 658; the filing stop and the extraction's
#: reads there too: 655; L625's first moves (the category routes' note lists,
#: the recordings' page, find, add and sealed probe, the board history's item
#: and event-log reads, the bench's busiest board, the embedding coverage) to
#: repo/categories.py, repo/recordings.py, repo/whiteboard.py and
#: repo/graph_layers.py, with other sessions' moves since: 616.
ORM_CALLS_CAP = 616

#: L625 (ARCHITECTURE.md section 2, principle 8): the plain query verbs in the
#: route modules alone, the count the repository layer's progress is read by.
#: 230 on 2026-11-21 before L625's first moves (categories, recordings, models,
#: bench, board history), 215 after; it only falls.
ROUTE_QUERIES_CAP = 215

_ROUTE_QUERY = re.compile(r"\bsession\.query\(|\bselect\(|\bsession\.execute\(")

_ORM = re.compile(
    r"\b(?:session|db)\.(?:query|get|execute|scalar|scalars|add|add_all|delete|merge)\("
    r"|\bselect\(|\bsa_delete\(|\bsa_update\("
)


def _imported_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module == "tessellate.core.database":
            names.update(alias.name for alias in node.names)
    return names


def test_a_moved_resource_is_queried_only_by_its_repository():
    leaks = []
    for path in sorted(API.glob("*.py")):
        if path.name in CROSS_RESOURCE:
            continue
        names = _imported_names(path)
        for resource, models in MOVED.items():
            for model in sorted(names & models):
                leaks.append(f"{path.name} imports {model} (use repo.{resource})")
    assert not leaks, "; ".join(leaks)


def test_orm_calls_in_the_routers_only_go_down():
    count = sum(len(_ORM.findall(p.read_text(encoding="utf-8"))) for p in API.glob("*.py"))
    assert count <= ORM_CALLS_CAP, (
        f"{count} ORM calls under api/ (cap {ORM_CALLS_CAP}): a new query belongs in "
        "the resource's repository under src/tessellate/repo/, not in a router"
    )


def test_queries_in_the_route_modules_only_go_down():
    count = sum(len(_ROUTE_QUERY.findall(p.read_text(encoding="utf-8"))) for p in API.glob("routes_*.py"))
    assert count <= ROUTE_QUERIES_CAP, (
        f"{count} session.query / select( / session.execute calls in api/routes_*.py "
        f"(cap {ROUTE_QUERIES_CAP}): move the query into src/tessellate/repo/"
    )


def test_a_repository_never_commits():
    """The route owns the transaction, so two verbs in one request commit once."""
    repo = API.parent / "repo"
    committing = [p.name for p in sorted(repo.glob("*.py")) if ".commit(" in p.read_text(encoding="utf-8")]
    assert not committing, f"repositories that commit: {committing}"
