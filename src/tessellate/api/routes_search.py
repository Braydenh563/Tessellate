"""One search endpoint over the whole notebook (WORLD_CLASS_PLAN B3).

Every surface that searches had its own half of this: the Notes list filters
client-side by keyword, `/entries?semantic=true` ranks by cosine and returns
notes only, the Library filters its own arrays, and nothing at all looked
inside a document, a file's extracted text, a bookmark or a reminder. This is
the one call that answers "where did I write that", whatever it was written
in, and says why each answer is an answer.

Deliberately thin: the engine (`search/engine.py`) does the work and this
module turns a query string into its arguments and its `Hit`s into JSON. The
operators come off `search/query.py`, so `tag:`, `kind:`, `in:`, `before:`,
`after:`, `has:`, `is:`, `"quoted phrases"` and `-excluded` work here without
this file knowing any of them exist.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.core.deps import get_session
from tessellate.search import engine
from tessellate.search import index as search_index
from tessellate.search import query as search_query

router = APIRouter(prefix="/search", tags=["search"])


class WarmBody(BaseModel):
    q: str = Field(default="", max_length=2000)


@router.post("/warm")
def warm(body: WarmBody, session: Session = Depends(get_session)) -> dict:
    """Speculative retrieval (WORLD_CLASS_PLAN H9): the Ask and chat boxes send
    their words on a typing pause, and the question's vector is made now, so
    Enter does not wait for the embedding model. `search_manager.warm`."""
    from tessellate.core import deps
    from tessellate.search import search_manager

    try:
        warmed = search_manager.warm(session, body.q.strip(), deps.get_embeddings())
    except Exception:  # noqa: BLE001  # a warm-up that fails costs the real search nothing
        warmed = False
    return {"warmed": warmed}

#: The most hits one call will return. A search box shows a page, not a
#: notebook; a caller that wants more is asking for a list, which
#: `/entries` already serves with its own paging.
MAX_LIMIT = 50

#: The deepest page one call will serve. The engine ranks a candidate pool of
#: `engine.CANDIDATE_DEPTH` rows, so a page past it could only ever be empty.
MAX_PAGE = 20


def _scope_of(entry_id: int | None, space: str) -> dict:
    ctx = {}
    if entry_id:
        ctx["entry_id"] = entry_id
    if space:
        ctx["space"] = space
    return ctx


def _with_typo_fix(session: Session, q: str, hits: list, ctx: dict, want: int, hybrid: bool, kinds: list[str]) -> tuple[list, str]:
    """The hits and the corrected query they are for ("" when `q` stands).

    **A typo gets the word it meant** (audit 2026-10-05, UX-04). Ask's
    `keyword_search` corrected "dentst" to "dentist" and these two boxes
    did not, so the same notebook answered a typo differently depending on
    where it was typed. Only when the query found nothing, and only to a
    word the notes actually hold, so a word that exists is never "fixed".
    The engine corrects a typo itself now (ARCH-07), so the hits can already
    be the corrected query's; the line still says so. `_corrected_query`
    only changes a word the notes do not hold, so a real word never shows
    as "corrected".
    """
    retry = _corrected_query(session, q) if q.strip() else ""
    if not retry or retry == q:
        return hits, ""
    if not hits:
        hits = engine.search(session, retry, ctx=ctx or None, limit=want, hybrid=hybrid, kinds=kinds or None)
    return hits, (retry if hits else "")


def _notices_for(q: str, hits: list) -> list[str]:
    asked = search_query.understand(q)
    notices = list(asked.notices)
    if asked.filters["title"] and not hits:
        notices.append("No title says " + " or ".join(f"\u201c{value}\u201d" for value in asked.filters["title"]) + ".")
    return notices


@router.get("")
def search(
    q: str = Query(default="", description="The query, operators included"),
    kind: str = Query(default="", description="Comma-separated kinds to search"),
    entry_id: int | None = Query(default=None, description="The note the person has open"),
    space: str = Query(default="", description="Limit to one space"),
    hybrid: bool = Query(default=True, description="False for keyword only"),
    limit: int = Query(default=20, ge=1, le=MAX_LIMIT),
    page: int = Query(default=1, ge=1, le=MAX_PAGE, description="1-based page of `limit` hits"),
    session: Session = Depends(get_session),
) -> dict:
    """Hits with their three scores and their explanation, best first.

    `{"hits": [...], "counts": {...}, "query": "..."}`. The counts are what
    the index holds per kind, so an empty result can say *why* it is empty:
    "nothing matched" and "nothing of that kind is indexed yet" are different
    answers and a bare empty list renders them identically, the same
    reasoning `/entries/tensions` states for its own status field.
    """
    kinds = [part.strip() for part in kind.split(",") if part.strip() in search_index.KINDS]
    ctx = _scope_of(entry_id, space)
    #: Paged by ranking deeper and slicing: one more than the page asks for,
    #: so `more` is known without a count of the whole notebook.
    want = page * limit + 1
    hits = engine.search(session, q, ctx=ctx or None, limit=want, hybrid=hybrid, kinds=kinds or None)
    hits, corrected = _with_typo_fix(session, q, hits, ctx, want, hybrid, kinds)
    notices = _notices_for(q, hits)
    return {
        "query": q,
        #: Said beside the results: a filter nothing answers, and a `title:`
        #: nothing is called (audit 1029 N4, N16).
        "notices": notices,
        #: The query the hits are for when it is not `query`: the view says
        #: "Showing results for ..." rather than letting a typo look matched.
        "corrected": corrected,
        "hits": _with_categories(session, hits[(page - 1) * limit : page * limit]),
        "page": page,
        "limit": limit,
        "more": len(hits) > page * limit,
        "counts": engine.index_counts(session),
    }


def _with_categories(session: Session, hits: list) -> list[dict]:
    """The page's hits as JSON, each with the name of the category its note is
    filed under (`null` for anything that is not a note), one query for the
    page: a Group by category in Find anything needs it (INBOX 1332)."""
    from sqlalchemy import select

    from tessellate.core.database import Category, Entry

    ids = [hit.ref_id for hit in hits if hit.kind == "note"]
    names: dict[int, str] = {}
    if ids:
        rows = session.execute(
            select(Entry.id, Category.name).join(Category, Category.id == Entry.category_id).where(Entry.id.in_(ids))
        )
        names = {entry_id: name for entry_id, name in rows}
    return [{**hit.as_dict(), "category": names.get(hit.ref_id) if hit.kind == "note" else None} for hit in hits]


_PLAIN_WORD = re.compile(r"[^\W\d_][\w'-]*")


def _corrected_query(session: Session, q: str) -> str:
    """`q` with each plain word swapped for the nearest word in the notes.

    Operators (`tag:x`, `-word`, quoted phrases) are left as typed: a filter
    is a statement, not a guess, and correcting one would change what it
    says. The correction itself is `search_manager._corrected_terms`, the
    one Ask uses, so the three boxes agree on what a typo finds.
    """
    from tessellate.search import search_manager

    if '"' in q:
        return q
    tokens = q.split()
    words = [token.lower() for token in tokens if _PLAIN_WORD.fullmatch(token)]
    if not words:
        return q
    fixed = dict(zip(words, search_manager._corrected_terms(session, words), strict=True))  # noqa: SLF001
    return " ".join(
        fixed.get(token.lower(), token) if _PLAIN_WORD.fullmatch(token) else token for token in tokens
    )


@router.get("/stats")
def stats(session: Session = Depends(get_session)) -> dict:
    """What the engine has to work with: index rows per kind, vectors held,
    and the weights the ranking used. The Settings page and a session report
    both want this, and neither should have to guess at it."""
    return engine.stats(session)
