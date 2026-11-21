"""Listing: which notes a list, a change poll or a query answers (decision 55, L-world-class-632).

The route parses the page, the cursor and the filters, calls one function
here, shapes the rows (`api/entry_out.py`) and writes the headers. Nothing
here imports the API layer. `tests/test_entries_changes.py`,
`tests/test_query_rollups_kg7.py` and `tests/test_list_limits.py` hold it.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.core import deps
from tessellate.core.database import Entry, utcnow
from tessellate.entry import manager, manager_text
from tessellate.entry import properties as note_properties
from tessellate.search import search_manager

#: How many concept matches `?semantic=true` returns. A search result is a
#: shortlist to read, not a second copy of the notebook.
SEMANTIC_LIST_LIMIT = 25

#: KG7: the table view's columns, and its rows, at most.
QUERY_COLUMNS_MAX = 8
QUERY_ROWS_MAX = 500

#: The most ids one `/entries/changes` answer carries; past it, `more` says
#: re-read the list (a bulk retag or an import touched more than a patch is
#: worth).
CHANGES_IDS_MAX = 60
#: How far behind the newest change the next stamp starts (see `changes`).
CHANGES_OVERLAP_SECONDS = 2.0


class SemanticNotReady(RuntimeError):
    """No embedding backend is ready: the caller can fall back to its own keyword filter."""


@dataclasses.dataclass
class NotesPage:
    entries: list
    total: int
    #: The sort key of the page's last note when a later page exists (the route makes it a cursor).
    next_key: tuple | None


def semantic(session: Session, q: str, *, deleted: bool, archived: bool, boards: str) -> list:
    """The notes a concept search ranks, best first, inside the view's scope.

    The scope is the *complete* id set, deliberately not paginated: it decides
    which semantic hits are even in view (bin, archive, or live), and paging
    that fetch would silently drop matches past the first page. Ids only, no
    row bodies, cheap at real notebook scale.

    Ranked, and returned ranked: rebuilding the result as `[e for e in entries
    if e.id in found_ids]` gave the notebook's order, so the best match could
    land anywhere and the feature looked like it picked notes at random."""
    scope_ids = manager.entry_id_scope(session, deleted=deleted, archived=archived, boards=boards)
    results = search_manager.semantic_search(session, q, deps.get_embeddings(), limit=SEMANTIC_LIST_LIMIT)
    if results is None:
        # Saying so beats silently handing back the entire notebook as though it were the search result.
        raise SemanticNotReady("Semantic search isn't ready yet: the embedding model is still loading.")
    # `semantic_search` already drops anything under MIN_SIMILARITY; a
    # second threshold here was a different number for the same job.
    return [e for e, _score in results if e.id in scope_ids]


def by_ids(session: Session, wanted: list[int], *, boards: str) -> tuple[list, int]:
    """Just these notes of the notes list, and the whole list's size."""
    entries = manager.list_entries(session, boards=boards, ids=wanted)
    return entries, manager.count_notes(session, include_archived=False, boards=boards, include_drafts=True)


def bin_page(session: Session, *, deleted: bool, limit: int, offset: int) -> tuple[list, int]:
    """One page of the bin (`deleted`) or the archive, and its size.

    Both page by position: both are short, both sort on a column that can be
    NULL on rows from before it existed (a keyset over NULLs needs a second
    ordering rule), and neither is written to while somebody scrolls it."""
    lister = manager.list_deleted_entries if deleted else manager.list_archived_entries
    entries = lister(session, limit=limit, offset=offset)
    total = manager.count_deleted_entries(session) if deleted else manager.count_archived_entries(session)
    return entries, total


def notes_page(session: Session, *, limit: int, offset: int, boards: str, after: tuple | None) -> NotesPage:
    """One page of the notes list by keyset (B7): a note saved while page one
    is on screen cannot push a row of page one onto page two as well."""
    entries = manager.list_entries(
        session, limit=limit + 1, offset=0 if after else offset, boards=boards, after=after
    )
    more = len(entries) > limit
    entries = entries[:limit]
    next_key = manager.list_sort_key(entries[-1]) if more and entries else None
    total = manager.count_notes(session, include_archived=False, boards=boards, include_drafts=True)
    return NotesPage(entries, total, next_key)


def changes(session: Session, since: str) -> dict:
    """**Which notes changed since `since`** (INBOX 881, the owner: "what if I
    make a change on my phone?? does it live update??"). The notes list on
    another device asks every few seconds and patches those ids in with
    `refreshEntries`. With no `since` it is only a stamp to ask from next.

    By `updated_at`, which every write moves (an edit, a filing, a bin, an
    archive, an open too: a refresh of an unchanged row costs one small read
    and is the price of not missing a change made by a path that forgot
    `edited_at`). Boards are left out, as the list leaves them out. The stamp
    sent back is two seconds behind now, so a write whose
    transaction committed a moment after this read is asked about again
    rather than missed (and never further back than the newest change, so a
    change is not sent for ever); the client drops ids it has already seen at
    the same `updated_at`, which `stamps` carries. A `since` this app did not
    write is a ValueError."""
    now = utcnow()
    overlap = timedelta(seconds=CHANGES_OVERLAP_SECONDS)
    if not since:
        return {"since": (now - overlap).isoformat(), "ids": [], "stamps": {}, "more": False}
    try:
        after = datetime.fromisoformat(since)
    except ValueError as exc:
        raise ValueError("That time is not one this app wrote.") from exc
    if after.tzinfo is None:
        after = after.replace(tzinfo=now.tzinfo)
    rows = session.execute(
        select(Entry.id, Entry.updated_at)
        .where(Entry.updated_at > after, Entry.is_board.is_(False))
        .order_by(Entry.updated_at.desc())
        .limit(CHANGES_IDS_MAX + 1)
    ).all()
    more = len(rows) > CHANGES_IDS_MAX
    rows = rows[:CHANGES_IDS_MAX]
    newest = max((r.updated_at for r in rows), default=None)
    stamp = max(after, min(newest, now - overlap) if newest is not None else now - overlap)
    return {
        "since": stamp.isoformat(),
        "ids": [r.id for r in rows],
        "stamps": {str(r.id): r.updated_at.isoformat() for r in rows},
        "more": more,
    }


def query(session: Session, q: str) -> dict:
    """The notes a live query matches (GRAPH_PLAN KG7, `entry/query.py`),
    newest first, with the table view's columns (the properties they carry,
    most common first, `type` leading) and rows. The Notes list, the table
    and the graph all take these ids, so one query is one answer."""
    from tessellate.entry import query as live_query

    terms = live_query.parse(q)
    if not terms:
        return {"ids": [], "columns": [], "rows": [], "structural": False, "rollups": {}}
    ids = live_query.run(session, q)
    rows = []
    counts: dict[str, int] = {}
    shown = ids[:QUERY_ROWS_MAX]
    entries = {e.id: e for e in session.scalars(select(Entry).where(Entry.id.in_(shown)))} if shown else {}
    for entry_id in shown:
        entry = entries[entry_id]
        content = manager_text.readable_content(entry)
        found = {} if entry.is_private else note_properties.split(content)[0]
        for key in found:
            counts[key] = counts.get(key, 0) + 1
        rows.append({
            "id": entry_id,
            "title": manager_text.extract_title(content) or manager_text.plain_label(content, 60) or "Untitled note",
            "properties": found,
        })
    columns = sorted(counts, key=lambda k: (k != "type", -counts[k], k))[:QUERY_COLUMNS_MAX]
    return {
        "ids": ids,
        "columns": columns,
        "rows": rows,
        "structural": live_query.is_structural(terms),
        #: The footer's count, sum, min, max, earliest and latest, over every
        #: match (not only the rows drawn), per column.
        "rollups": live_query.rollups(session, ids, columns),
    }
