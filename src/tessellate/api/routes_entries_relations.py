"""Link suggestions, tensions, related notes and bookmarks of an entry.

Split out of routes_entries.py (K24); mounted in app.py beside that module's router.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from tessellate.ai import backend_hint, learning, librarian, links, relations
from tessellate.ai import tensions as tensions_module
from tessellate.api.routes_entries import _existing_entry, _preview, _to_out
from tessellate.api.schemas import (
    EntryOut,
)
from tessellate.core import deps, jobruns
from tessellate.core.database import (
    AuditLog,
    DerivedTension,
    Entity,
    EntityMention,
    Entry,
)
from tessellate.core.deps import get_session
from tessellate.entry import duplicates, link_facts, manager
from tessellate.entry import manager_links
from tessellate.entry import manager_text
from tessellate.repo import bookmarks as bookmark_repo
from tessellate.repo import relations as relations_repo
from tessellate.repo.content import NOTES
from tessellate.search import engine as search_engine

logger = logging.getLogger("tessellate.api.entries")

router = APIRouter(tags=["entries"], prefix="/entries")


# Notes this similar are almost certainly worth connecting.
LINK_SUGGESTION_THRESHOLD = 0.55

#: How many of the twelve suggestions any one note may anchor. See
#: `link_suggestions` for the measurement that put this here: without a cap,
#: one note paired with six copies of itself filled half the list.
MAX_SUGGESTIONS_PER_NOTE = 2


class _LazyNoteFacts:
    """`relations.NoteFacts` whose label is read only when asked for.

    `recognise` names a note only when it is a hub of shared neighbours, yet
    every note's label was cleaned up front: at 5,000 notes 0.66 s of a
    1.08 s warm `/entries/link-suggestions` (audit 2026-10-05, ARCH-11).
    """

    __slots__ = ("_content", "_label", "tags", "created_at")

    def __init__(self, content: str, tags: frozenset[str], created_at) -> None:  # noqa: ANN001
        self._content = content
        self._label: str | None = None
        self.tags = tags
        self.created_at = created_at

    @property
    def label(self) -> str:
        if self._label is None:
            self._label = manager_text.plain_label(self._content, 40) or "Untitled note"
        return self._label


#: **The suggestions are kept until the notebook changes** (audit 1028 K30:
#: every request read every note, link and mention, and the Inbox asks on
#: every open, from every tab). Any session write moves `_writes`: a flush,
#: or a bulk statement run through `session.execute`. A write past both (a
#: raw connection) is caught by the age bound.
_writes = [0]
_LINK_CACHE_SECONDS = 300.0
_link_cache: dict = {"key": None, "at": 0.0, "value": None}


@event.listens_for(Session, "after_flush")
def _count_flush(_session: Session, _context) -> None:  # noqa: ANN001
    _writes[0] += 1


@event.listens_for(Session, "do_orm_execute")
def _count_statement(state) -> None:  # noqa: ANN001
    if not state.is_select:
        _writes[0] += 1


@router.get("/link-suggestions")
def link_suggestions(session: Session = Depends(get_session)) -> list[dict]:
    """The pairs `_link_suggestions` finds, kept until something is written."""
    key = (id(deps.get_db()), _writes[0], deps.get_embeddings().is_ready())
    now = time.monotonic()
    if _link_cache["key"] == key and now - _link_cache["at"] < _LINK_CACHE_SECONDS:
        return _link_cache["value"]
    value = _link_suggestions(session)
    _link_cache.update(key=key, at=now, value=value)
    return value


def _already_linked(session: Session, entries: list) -> set[frozenset[int]]:
    """Pairs with nothing left to suggest: linked, parent and child, or dismissed."""
    already_linked: set[frozenset[int]] = set()
    for source_id, target_id in relations_repo.pairs(session):
        already_linked.add(frozenset((source_id, target_id)))
    # Threads are already a connection, don't re-suggest parent/child.
    for entry in entries:
        if entry.parent_id is not None:
            already_linked.add(frozenset((entry.parent_id, entry.id)))
    # A pair the person has already said no to (WORLD_CLASS_PLAN I7). The same
    # set as the two above, because "you dismissed this" and "these are
    # already linked" are the same answer to this endpoint's only question:
    # is there anything left to suggest about these two. A suggestion that
    # comes back after being dismissed is the single most annoying thing a
    # suggester can do, and it is what this feature did until now: the
    # dismissal lived in the browser and died with the tab.
    for pair in learning.boosts(session, kind="links"):
        already_linked.add(frozenset(pair))
    return already_linked


def _recognised_pairs(session: Session, entries: list, candidates: dict, already_linked: set) -> list:
    """`relations.recognise` over the notebook's meaning, links, entities, tags and time."""
    # **Structure as well as wording** (GRAPH_PLAN KG2): shared entities,
    # shared link neighbours, shared rare tags and time join the cosine pairs
    # in `ai/relations.recognise`, each with its own reason and confidence, so
    # the list explains itself and is not empty with the embedding backend
    # off. The cosine pairs come from the engine's matrix (Brief 11), cached
    # per version of it (WORLD_CLASS_PLAN row 9); the filters below are per
    # request because what is linked or dismissed moves without any vector
    # changing.
    similar: list[tuple[int, int, float]] = []
    if deps.get_embeddings().is_ready():
        similar = search_engine.cached_similar_pairs(
            session, LINK_SUGGESTION_THRESHOLD, only=set(candidates)
        )
    edges = relations_repo.pairs(session)
    edges += [(e.parent_id, e.id) for e in entries if e.parent_id is not None]
    mentions = [
        (name, entry_id)
        for name, entry_id in session.execute(
            select(Entity.name, EntityMention.entry_id).join(Entity, Entity.id == EntityMention.entity_id)
        )
    ]
    notes = {
        i: _LazyNoteFacts(e.content, frozenset(t.lower() for t in manager.entry_tags(e)), e.created_at)
        for i, e in candidates.items()
    }
    return relations.recognise(
        notes, edges, mentions, similar, already_linked, weights=learning.signal_weights(session)
    )


def _suggestion_row(session: Session, candidate, candidates: dict) -> dict:  # noqa: ANN001
    a, b = candidate.a, candidate.b
    signals = candidate.signals()
    reason = "; ".join(s["reason"] for s in signals if s["signal"] != "time")
    #: Meaning alone previews what linking would write, and linking now
    #: names what the two notes share when they share something (INBOX
    #: 691, `entry/link_wording.py`), so the preview does too.
    if [s["signal"] for s in signals if s["signal"] != "time"] == ["similarity"]:
        reason = link_facts.reason_for(session, a, b) or reason
    return {
        "source_id": a,
        "target_id": b,
        "source_preview": _preview(candidates[a].content),
        "target_preview": _preview(candidates[b].content),
        "similarity": round(candidate.similarity, 2) if candidate.similarity is not None else None,
        "confidence": round(candidate.confidence, 2),
        "signals": signals,
        # Similarity alone previews what `create_link` deduces at the same
        # bar (`manager.AUTO_REASON_THRESHOLD`): the specific reason, else
        # "similar in meaning". Otherwise every signal, strongest first,
        # less the time, which supports a pair but is no reason to link.
        "reason": reason,
    }


def _link_suggestions(session: Session) -> list[dict]:
    """Pairs of notes that mean similar things but aren't linked yet: 
    the auto-linker. Suggestion-only: it never links anything on
    its own, it hands the pairs to the UI to approve. Empty when the
    embedding backend is unavailable (semantic search off).

    Used to call `semantic_search` once *per entry*: a full embedding scan,
    for every entry, so O(entries) database round-trips each doing O(entries)
    work, and each one **re-embedding that entry's own content from scratch**
    on top of the scan. At any real notebook size that's the O(n^2) trap this
    file was checked for after §38.1's scale-test found two others: found by
    the same kind of sweep, not by profiling this one specifically, since a
    75k-note notebook running this by hand was not something worth actually
    waiting out. Rewritten to match `routes_graph._similarity_edges`'s
    already-correct shape: fetch every stored vector once, compare all
    pairs in memory: which turns O(n) queries plus O(n) re-embeddings into
    one query and zero re-embedding calls."""
    entries = manager.list_entries(session)
    candidates = {e.id: e for e in entries if not e.is_private and not e.is_board}
    already_linked = _already_linked(session, entries)
    found = _recognised_pairs(session, entries, candidates, already_linked)

    # **Two filters stand between "best-first" and "useful"**, both added
    # after measuring a real 116-note notebook whose twelve suggestions were
    # all a note paired with copies of itself (tests/test_link_suggestion_quality.py):
    #  1. A near-identical pair is a *duplicate* (`entry/duplicates.py`, same
    #     word-overlap score), not a connection.
    #  2. One note anchors at most `MAX_SUGGESTIONS_PER_NOTE` of the twelve, so
    #     the list is a survey of the notebook and not of its best-linked note.
    suggestions = []
    appearances: dict[int, int] = {}
    for candidate in found:
        a, b = candidate.a, candidate.b
        if (
            appearances.get(a, 0) >= MAX_SUGGESTIONS_PER_NOTE
            or appearances.get(b, 0) >= MAX_SUGGESTIONS_PER_NOTE
        ):
            continue
        if (
            duplicates.similarity(candidates[a].content, candidates[b].content)
            >= duplicates.DEFAULT_THRESHOLD
        ):
            continue
        appearances[a] = appearances.get(a, 0) + 1
        appearances[b] = appearances.get(b, 0) + 1
        suggestions.append(_suggestion_row(session, candidate, candidates))
        if len(suggestions) == 12:
            break
    return suggestions


#: Where dismissed tensions are remembered. A preference key rather than a new
#: table: this is a small list of pair keys, it belongs to the person rather
#: than to either note, and adding a migration for "I looked at this and it
#: was not a contradiction" would be a heavy answer to a light question.
TENSION_DISMISSED_KEY = "tensions_dismissed"

#: Tensions look at pairs the notebook already believes are about the same
#: thing (see `ai/tensions.py`, contradiction is only possible between notes
#: sharing a subject). A lower bar than `LINK_SUGGESTION_THRESHOLD` on
#: purpose: two notes that *disagree* often share less vocabulary than two
#: that agree, because the disagreement is exactly where their words differ.
TENSION_CANDIDATE_THRESHOLD = 0.45


def _tension_key(a: int, b: int) -> str:
    """A stable id for a pair, order-independent."""
    low, high = sorted((a, b))
    return f"{low}:{high}"


def _dismissed_tensions() -> set[str]:
    stored = deps.get_config().get_preference(TENSION_DISMISSED_KEY, []) or []
    return {str(key) for key in stored}


def _known_tension_keys(session: Session) -> set[str]:
    """Pairs that are never re-proposed."""
    # A pair already marked as contradicting is a finding the person has
    # already accepted, not one to re-propose. Every other link type is left
    # alone deliberately: notes can be linked as "related" *and* disagree,
    # and that is one of the more interesting cases.
    known: set[str] = set(_dismissed_tensions())
    for link in relations_repo.with_type(session, "contradicts"):
        known.add(_tension_key(link.source_entry_id, link.target_entry_id))
    # WORLD_CLASS_PLAN B4: a pair already in the tensions table (found by an
    # earlier scan or the night shift, whatever became of it) is never asked
    # about again; the widget and `GET /entries/tensions/known` list it.
    tensions_module.refresh(session)
    known.update(session.scalars(select(DerivedTension.pair)))
    return known


def _tension_row(tension, score: float) -> dict:  # noqa: ANN001
    return {
        "key": _tension_key(tension.earlier_id, tension.later_id),
        "earlier_id": tension.earlier_id,
        "later_id": tension.later_id,
        "explanation": tension.explanation,
        "earlier_excerpt": tension.earlier_excerpt,
        "later_excerpt": tension.later_excerpt,
        "earlier_at": tension.earlier_at,
        "later_at": tension.later_at,
        "gap_days": tension.gap_days,
        "similarity": round(score, 2),
    }


def _tension_scan_blocker(ollama, embeddings) -> str | None:  # noqa: ANN001
    """Why a scan cannot run at all, or None."""
    if not backend_hint.running(ollama):
        return "no_model"
    if not embeddings.is_ready():
        return "no_embeddings"
    return None


@router.get("/tensions")
def find_tensions(
    limit: int = Query(default=8, ge=1, le=20),
    session: Session = Depends(get_session),
) -> dict:
    """Places the notebook appears to disagree with itself.

    The feature `core/database.py`'s `LINK_TYPES` comment says the typed-link
    vocabulary was built for and that nothing ever produced, see
    `ai/tensions.py` for the full reasoning. Read-only and suggestion-only:
    finding a tension writes nothing, and `POST /entries/tensions/accept` is
    the only thing that creates the `contradicts` link.

    Returns `{"tensions": [...], "status": "..."}` rather than a bare list so
    an empty result can say *why* it is empty, "no model running" and "your
    notebook does not contradict itself" are completely different answers and
    a bare `[]` renders them identically, which is how a feature that never
    ran gets reported as a feature that found nothing.
    """

    ollama = deps.get_ollama()
    blocked = _tension_scan_blocker(ollama, deps.get_embeddings())
    if blocked:
        return {"tensions": [], "status": blocked}

    entries = manager.list_entries(session)
    by_id = {e.id: e for e in entries if not e.is_private and not e.is_board}
    if len(by_id) < 2:
        return {"tensions": [], "status": "too_few_notes"}

    # Cached per version of the matrix, as link suggestions are (row 9).
    pairs = search_engine.cached_similar_pairs(
        session, TENSION_CANDIDATE_THRESHOLD, only=set(by_id)
    )

    known = _known_tension_keys(session)

    models = deps.get_model_manager()
    found: list[dict] = []
    checked = 0
    for a_id, b_id, score in pairs:
        if checked >= tensions_module.MAX_PAIRS_PER_PASS or len(found) >= limit:
            break
        if _tension_key(a_id, b_id) in known:
            continue
        ordered = tensions_module.order_by_time(by_id[a_id], by_id[b_id])
        if ordered is None:
            continue  # same few days, or undated, see MIN_GAP_DAYS
        checked += 1
        tension = tensions_module.compare_pair(ordered[0], ordered[1], models, ollama)
        if tension is None:
            continue
        #: Kept as an event, so the finding outlives this response and the
        #: table can be rebuilt from it (B4).
        tensions_module.record_event(
            session,
            tensions_module.FOUND,
            tension.earlier_id,
            tension.later_id,
            reason=tension.explanation,
            model=str(models.utility_model() or "local"),
            confidence=0.7,
        )
        found.append(_tension_row(tension, score))
    status = "ok" if found else ("none_found" if checked else "no_candidates")
    session.commit()
    return {"tensions": found, "status": status, "pairs_checked": checked}


@router.get("/tensions/known")
def known_tensions(
    status: str = Query(default="open", pattern="^(open|accepted|dismissed|all)$"),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict:
    """The tensions the notebook already knows (WORLD_CLASS_PLAN B4): the
    derived table, rebuilt from its sources when one moved, in the shape the
    scan returns plus who decided each and when. Reads nothing with a model,
    so the Tensions widget can show it on every Dashboard draw."""
    rows, counts = tensions_module.listing(session, status=None if status == "all" else status, limit=limit)
    session.commit()
    notes = {
        e.id: e
        for e in session.scalars(
            select(Entry).where(Entry.id.in_({r.earlier_id for r in rows} | {r.later_id for r in rows}))
        )
    }
    out = []
    for row in rows:
        earlier, later = notes.get(row.earlier_id), notes.get(row.later_id)
        if earlier is None or later is None:
            continue
        out.append(
            {
                "key": row.pair,
                "earlier_id": row.earlier_id,
                "later_id": row.later_id,
                "explanation": row.reason,
                "earlier_excerpt": tensions_module._excerpt(manager_text.readable_content(earlier))[:280],
                "later_excerpt": tensions_module._excerpt(manager_text.readable_content(later))[:280],
                "earlier_title": manager_text.extract_title(manager_text.readable_content(earlier))
                or manager_text.plain_label(manager_text.readable_content(earlier), 60),
                "later_title": manager_text.extract_title(manager_text.readable_content(later))
                or manager_text.plain_label(manager_text.readable_content(later), 60),
                "earlier_at": tensions_module._stamp(earlier.created_at),
                "later_at": tensions_module._stamp(later.created_at),
                "gap_days": abs((later.created_at - earlier.created_at).days)
                if earlier.created_at and later.created_at
                else 0,
                "status": row.status,
                "model": row.model,
                "confidence": row.confidence,
                "computed_at": row.computed_at.isoformat() if row.computed_at else None,
                "source": row.source,
                "event_id": row.event_id,
            }
        )
    return {"tensions": out, "counts": counts}


class TensionPair(BaseModel):
    earlier_id: int
    later_id: int


@router.post("/tensions/accept")
def accept_tension(body: TensionPair, session: Session = Depends(get_session)) -> dict:
    """Record a tension as a real `contradicts` link between the two notes.

    Uses `manager.create_link` rather than inserting a row, so the link gets
    the same audit entry, the same self-link and duplicate guards, and the
    same graph/traversal treatment as one made by hand.
    """
    earlier = NOTES.writable(session, body.earlier_id)
    later = NOTES.writable(session, body.later_id)
    link = manager_links.create_link(
        session,
        earlier,
        later,
        reason="these disagree with each other",
        link_type="contradicts",
    )
    #: KG9: the inbox's decisions are corrections like every other kind.
    learning.record(session, kind="accept_tension", subject={"a": earlier.id, "b": later.id})
    tensions_module.record_event(session, tensions_module.ACCEPTED, earlier.id, later.id)
    session.commit()
    return {"created": link is not None}


@router.post("/tensions/dismiss")
def dismiss_tension(body: TensionPair, session: Session = Depends(get_session)) -> dict:
    """Stop offering this pair. Remembered across restarts.

    Capped, and oldest-first: without a cap this preference would grow
    without bound on a notebook where most candidates are rejected, and it
    is written to disk on every change (see `Config.set_preference`).
    """
    config = deps.get_config()
    stored = list(config.get_preference(TENSION_DISMISSED_KEY, []) or [])
    key = _tension_key(body.earlier_id, body.later_id)
    if key not in stored:
        stored.append(key)
    del stored[:-500]
    config.set_preference(TENSION_DISMISSED_KEY, stored)
    learning.record(session, kind="dismiss_tension", subject={"a": body.earlier_id, "b": body.later_id})
    tensions_module.record_event(session, tensions_module.DISMISSED, body.earlier_id, body.later_id)
    session.commit()
    return {"dismissed": key}


class TensionReopen(TensionPair):
    #: The accept made the `contradicts` link (it was not there before), so
    #: Undo takes it away; a link the person already had is left alone.
    remove_link: bool = False


@router.post("/tensions/reopen")
def reopen_tension(body: TensionReopen, session: Session = Depends(get_session)) -> dict:
    """Undo of accepting or dismissing a tension: the pair is offered again (INBOX 898).

    The event log is a history, so this writes a `tension_reopened` event
    rather than editing the earlier one, and drops the correction the
    decision taught the learning loop (it was a slip, not a lesson).
    """
    pair = {body.earlier_id, body.later_id}
    config = deps.get_config()
    stored = [k for k in (config.get_preference(TENSION_DISMISSED_KEY, []) or []) if k != _tension_key(body.earlier_id, body.later_id)]
    config.set_preference(TENSION_DISMISSED_KEY, stored)
    removed_link = False
    if body.remove_link:
        for link in relations_repo.with_type(session, "contradicts"):
            if {link.source_entry_id, link.target_entry_id} == pair:
                manager_links.delete_link(session, link)
                removed_link = True
    for kind in ("accept_tension", "dismiss_tension"):
        for item in reversed(learning.corrections(session, kind=kind)):
            if {item.subject.get("a"), item.subject.get("b")} == pair:
                row = session.get(AuditLog, item.id)
                if row is not None:
                    session.delete(row)
                break
    tensions_module.record_event(session, tensions_module.REOPENED, body.earlier_id, body.later_id)
    session.commit()
    return {"reopened": _tension_key(body.earlier_id, body.later_id), "removed_link": removed_link}


class LinkSuggestionReasonPair(BaseModel):
    source_id: int
    target_id: int


class LinkSuggestionReasonsBody(BaseModel):
    pairs: list[LinkSuggestionReasonPair]


@router.post("/link-suggestions/reasons")
def link_suggestion_reasons(
    body: LinkSuggestionReasonsBody, session: Session = Depends(get_session)
) -> dict:
    """Reasons for *pending* suggestions, not yet real links, the gap
    `/links/backfill-reasons` (below) deliberately doesn't cover, since that
    one only ever touches links that already exist. Asked for directly: the
    suggestions panel's own "Why?" boxes had no way to get an AI guess
    without linking first, editing, and re-linking. Best-effort per pair: 
    one bad or private pair doesn't sink the rest, and the whole call
    degrades to an empty list rather than an error the moment the model is
    down, so the caller can tell "nothing generated" from "everything
    genuinely had one already" without a special-cased response shape."""
    reasons = []
    ai_unavailable = False
    for pair in body.pairs[:12]:  # same cap link_suggestions() itself uses
        source = session.get(Entry, pair.source_id)
        target = session.get(Entry, pair.target_id)
        if not source or not target or source.is_private or target.is_private:
            continue
        try:
            reason = librarian.generate_link_reason(
                manager_text.readable_content(source),
                manager_text.readable_content(target),
                deps.get_model_manager(),
                deps.get_ollama(),
            )
        except Exception as exc:  # noqa: BLE001  # model offline is the expected case, once per pair; the message is logged
            logger.info("link suggestion reason skipped: %s", exc)
            ai_unavailable = True
            continue
        reasons.append(
            {"source_id": pair.source_id, "target_id": pair.target_id, "reason": reason}
        )
    result = {"reasons": reasons}
    if ai_unavailable:
        result["ai_unavailable"] = True
    return result


class BackfillReasonsBody(BaseModel):
    """`ai=False` runs only the cheap embedding pass, useful when the model
    is known to be down and you just want the links marked."""

    ai: bool = True
    limit: int = Field(default=100, ge=1, le=500)


@router.post("/links/backfill-reasons")
def backfill_link_reasons(
    body: BackfillReasonsBody | None = None, session: Session = Depends(get_session)
) -> dict:
    """"None of my notes have a linked reason yet, is there an easy way to
    give them all a reason?" There wasn't: `_deduce_reason` only ever ran at
    the moment a link was *made*, so every link from before that shipped, or
    made while the embedding backend was off, stays mute forever with
    nothing to revisit it. One pass over every reason-less link, same rule
    as a fresh one, a link that still can't be deduced is left alone rather
    than given a manufactured answer.

    **Two passes, not one, and the second is the one the user actually
    wanted.** The first (embeddings) can only ever write the literal string
    "similar in meaning", it compares two vectors and has no words for what
    it found. So a notebook that ran this ended up with every link reading
    *"similar in meaning"*, which is what was reported: the button appeared to
    work and the reasons it produced said nothing.

    The second pass hands those to the model and asks it to name the actual
    connection. It is best-effort: if the model is down, the embedding pass
    has still marked the links and the audit can be re-run later, which is
    why a failure here is reported in the result rather than raised.
    """
    options = body or BackfillReasonsBody()
    with jobruns.job_run("link-reasons", origin="you") as run:
        result = _backfill_reasons(session, options)
        run.result = (
            f"checked {result.get('checked', 0)} links, "
            f"added {result.get('updated', 0)} reasons, "
            f"reworded {result['rewritten']}"
        )
        if result.get("ai_unavailable"):
            run.result += " (the model was not available)"
    return result


def _backfill_reasons(session: Session, options: "BackfillReasonsBody") -> dict:
    result = manager_links.backfill_link_reasons(session)

    result["rewritten"] = 0
    if not options.ai:
        return result
    try:
        result["rewritten"] = links.audit_vague_links(
            session, deps.get_model_manager(), deps.get_ollama(), limit=options.limit
        )
    except Exception as exc:  # noqa: BLE001  # model offline is the expected case; the message is logged
        # Not an error the caller should see as a failure: the cheap pass
        # succeeded and its work is committed.
        logger.info("link reason audit skipped: %s", exc)
        result["ai_unavailable"] = True
    return result


#: How alike two notes have to be before one is offered as "see also".
#: Unchanged from the number this route already used inline; named now that
#: the scoring moved into the engine, so the threshold and the engine's own
#: `MIN_SIMILARITY` are visibly two different decisions rather than one
#: number copied twice.
RELATED_MIN_SIMILARITY = 0.3


@router.get("/{entry_id}/related", response_model=list[EntryOut])
def related_entries(entry_id: int, session: Session = Depends(get_session)) -> list[EntryOut]:
    """Semantic neighbours of one entry ("see also")."""
    entry = _existing_entry(session, entry_id)
    # The engine's matrix rather than a scan of every stored vector per note
    # opened (Brief 11). `warm_vectors` is idempotent: it builds once per
    # process and per notebook, and returns immediately after that, so this
    # is not per-request work. `related()` itself never builds, which is what
    # the spec pins.
    try:
        search_engine.warm_vectors(session)
        neighbours = search_engine.related(session, entry.id, k=8)
    except Exception:  # noqa: BLE001  # a "see also" panel never fails a note
        neighbours = []
    wanted = [other_id for other_id, score in neighbours if score >= RELATED_MIN_SIMILARITY]
    if not wanted:
        return []
    #: Each row is a press that links the two notes, so a note already linked
    #: (either way round) is left out, and so is a draft against a committed
    #: note (`manager.create_link` refuses both with a 400).
    linked = {
        other_id
        for link in relations_repo.touching(session, entry.id)
        for other_id in (link.source_entry_id, link.target_entry_id)
    }
    found = {
        other.id: other
        for other in session.scalars(
            select(Entry).where(Entry.id.in_(wanted), Entry.is_deleted == False)  # noqa: E712
        )
        if not other.is_private and other.id not in linked and bool(other.is_draft) == bool(entry.is_draft)
    }
    ordered = [found[other_id] for other_id in wanted if other_id in found]
    return _with_reasons(session, entry.id, [_to_out(session, e) for e in ordered[:3]])


def _with_reasons(session: Session, entry_id: int, rows: list[EntryOut]) -> list[EntryOut]:
    """Each offered note says what it shares with this one, else "similar in meaning"."""
    for row in rows:
        row.link_reason = link_facts.reason_for(session, entry_id, row.id) or manager_links.AUTO_REASON_TEXT
    return rows


class AttachBookmarkBody(BaseModel):
    bookmark_id: int
    #: Undo's door (undo-1005): a detached reference re-attached where it was,
    #: since References list in attach order. The DELETE answers with it.
    created_at: datetime | None = None


@router.get("/{entry_id}/bookmarks")
def entry_bookmarks(entry_id: int, session: Session = Depends(get_session)) -> list[dict]:
    """Bookmarks attached to this note, its References, alongside the
    [[wiki links]] `links` already carries. Its own endpoint rather than a
    field on EntryOut, matching `/related` right above: only the editor
    needs this, and `_to_out_bulk`'s per-list-page bulk fetch shouldn't grow
    a query for something most renders of a note never show."""
    _existing_entry(session, entry_id)
    rows = bookmark_repo.attached_to_entry(session, entry_id)
    return [
        {"id": b.id, "url": b.url, "title": b.title, "group_name": b.group_name}
        for b in rows
    ]


@router.post("/{entry_id}/bookmarks", status_code=201)
def attach_bookmark(
    entry_id: int, body: AttachBookmarkBody, session: Session = Depends(get_session)
) -> dict:
    NOTES.writable(session, entry_id)
    if bookmark_repo.attach_to_entry(session, entry_id, body.bookmark_id, created_at=body.created_at):
        session.commit()
    return {"attached": True}


@router.delete("/{entry_id}/bookmarks/{bookmark_id}")
def detach_bookmark(
    entry_id: int, bookmark_id: int, session: Session = Depends(get_session)
) -> dict:
    NOTES.writable(session, entry_id)
    # When it was attached, so Undo puts it back in its place in the list.
    attached = bookmark_repo.detach_from_entry(session, entry_id, bookmark_id)
    session.commit()
    return {"detached": True, "created_at": attached.isoformat() if attached else None}
