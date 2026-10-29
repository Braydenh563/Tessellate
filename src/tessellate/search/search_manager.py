"""Find entries two ways.

- Keyword search: word-based and ranked: always works, even with zero AI.
- Semantic search: cosine similarity over stored vectors, needs an
  embedding backend.

`retrieve()` is what /chat uses: semantic when possible, keyword as the
fallback, so asking a question always returns *something* (plan §4).
"""

from __future__ import annotations

import difflib
import importlib
import logging
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, time, timezone

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from tessellate.ai import recognise, variants
from tessellate.ai.embeddings import (
    EmbeddingService,
    bytes_to_vector,
)
from tessellate.core.database import LIKE_ESCAPE, EmbeddingRecord, Entry, EntryDate, like_escape, link_strength
from tessellate.search import query as query_understanding

# **No `TYPE_CHECKING: import numpy as np` here**, for the reason janitor.py
# records at length: the one annotation naming `np.ndarray` is a local
# variable annotation inside `semantic_search`, which already imports numpy
# for real, so the module-level import was a CodeQL finding buying nothing.
# The deferral itself stands: `retrieve` and keyword search, which is what
# most `/chat` turns and every plain note save actually run, never touch
# numpy at all.

logger = logging.getLogger("tessellate.search")


def _user_today(session: Session):
    """The user's own date, not the server's.

    A question about "yesterday" asked at 00:30 in one timezone is about a
    different day in another, and getting this wrong makes the filter look
    broken in exactly the cases where it matters most.
    """
    try:
        from tessellate.core import deps
        from tessellate.core.config import user_now

        return user_now(deps.get_config()).date()
    except Exception:  # noqa: BLE001  # a script or a test with no app state
        return datetime.now().date()

# Below this cosine similarity a match is probably noise, hide it. An
# absolute floor, kept as a sanity check alongside the relative one below
# (RELATIVE_Z_MARGIN): see semantic_search's own comment on why an
# absolute number alone is not enough for an anisotropic embedding space.
MIN_SIMILARITY = 0.25

# How many standard deviations above this query's own mean score a
# candidate needs to clear the *relative* floor in semantic_search.
RELATIVE_Z_MARGIN = 0.5

# Below this many valid candidate scores, a mean/std is too noisy an
# estimate to reject anything by, semantic_search falls back to
# MIN_SIMILARITY alone.
RELATIVE_MIN_CANDIDATES = 5

# When nothing matches, hand the assistant this many recent entries so
# broad/overview questions ("what have I saved?") still get answered.
RECENT_FALLBACK_LIMIT = 10


def recent_entries(session: Session, limit: int = RECENT_FALLBACK_LIMIT) -> list[Entry]:
    """Most recent non-deleted, non-private notes, newest first.

    Every reader in this module returns *notes*: a board or mind map is an
    `Entry` too (`Entry.is_board`), but its entry text is the one line
    `# Title` and its words live on its objects, so listing it here put a map
    in Ask's results as an Uncategorised note card with a similarity score
    (reported 2026-10-10). Maps are found as maps by `search.engine`."""
    return list(
        session.scalars(
            select(Entry)
            .where(
                Entry.is_deleted == False,  # noqa: E712
                Entry.is_private == False,  # noqa: E712
                Entry.is_board == False,  # noqa: E712
            )
            .order_by(Entry.created_at.desc(), Entry.id.desc())
            .limit(limit)
        )
    )


def entries_between(session: Session, since, until, limit: int = 40, archived: bool = False) -> list[Entry]:
    """Non-deleted, non-private entries written from `since` to `until`
    (days, both kept), newest first: what "what did I do last week" is
    about (CHAT_PLAN decision 31, recall by time), every note of the window
    rather than the five a similarity search would rank. Archived notes are
    left out, as in every count, unless the question asks for them
    (`archived=True`: only those; composer plan, "Decisions made")."""
    from datetime import datetime, time, timedelta

    start = datetime.combine(since, time(0))
    end = datetime.combine(until + timedelta(days=1), time(0))
    return list(
        session.scalars(
            select(Entry)
            .where(
                Entry.is_deleted == False,  # noqa: E712
                Entry.is_private == False,  # noqa: E712
                Entry.created_at >= start,
                Entry.created_at < end,
                Entry.archived_at.is_not(None) if archived else Entry.archived_at.is_(None),
            )
            .order_by(Entry.created_at.desc(), Entry.id.desc())
            .limit(limit)
        )
    )


def keyword_search(session: Session, query: str, limit: int = 10) -> list[Entry]:
    """Find entries by words, best match first.

    This used to be one `LIKE %query%`, which meant the query had to appear as
    a contiguous substring: "proving bread" found nothing even when notes
    contained both words, because the order didn't match. Word order is not
    something anyone should have to guess.

    Now every word must appear somewhere (content or tags), in any order.
    Ranked by SQLite's own FTS5 `bm25()`, real IDF-weighted relevance
    (ROADMAP.md item 32: the previous hand-rolled integer score treated a
    rare, distinctive word the same as a common one), with tag matches
    weighted above a plain content mention, and an exact contiguous phrase
    (checked in Python against the small candidate set FTS already
    narrowed things to, not a second index) breaking ties in front of
    everything else, the same way the old +25 phrase bonus did. When no
    note has all the words, it falls back to notes with *some* of them, a
    partial answer beats an empty page.

    This matters most with no AI running: keyword search is then the whole of
    search, not a fallback.
    """
    terms = _meaningful_terms(query)
    if not terms:
        # Nothing to match on, a question made entirely of common words
        # ("what have I saved so far?") isn't a keyword search at all, and
        # saying so lets the caller fall through to recent notes instead.
        return []

    base = (
        Entry.is_deleted == False,  # noqa: E712
        Entry.is_private == False,  # noqa: E712
        Entry.is_board == False,  # noqa: E712
    )

    def matching(require_all: bool, words: list[str] | None = None) -> dict[int, float]:
        # `terms` are pre-filtered to \W-stripped words by `_meaningful_terms`,
        # so none of them can contain FTS5 query-syntax characters, safe to
        # join directly rather than needing to quote/escape each one. (A
        # trailing `*` from the prefix stage is FTS5's own prefix operator.)
        #: Each word in every spelling it has ("colour" asks for "color"
        #: too, INBOX 895): the index read both ways without a rebuild.
        match_expr = (" AND " if require_all else " OR ").join(variants.fts_group(w) for w in (words or terms))
        rows = session.execute(
            text(
                "SELECT rowid, bm25(entries_fts, 1.0, 4.0) AS score "
                "FROM entries_fts WHERE entries_fts MATCH :expr "
                # Over-fetch so ranking (below) has something to choose
                # between; the cut to `limit` happens after, not before.
                "ORDER BY score LIMIT :n"
            ),
            {"expr": match_expr, "n": max(limit * 5, 50)},
        ).all()
        # bm25() is *lower is better*, more negative means more relevant.
        return {row.rowid: row.score for row in rows}

    # Four stages, each only when the one before found nothing, each a
    # little looser: every word exactly → every word as a prefix ("agent"
    # finds "agents", "prov" finds "proving") → every word corrected to the
    # nearest word the notebook actually contains ("sourdogh" → "sourdough")
    # → any of the words. Asked for as "search tolerant of spelling
    # mistakes": a student typing fast should not get an empty page for one
    # transposed letter, and the FTS index already knows every word it has.
    phrase_terms = terms
    scores = matching(require_all=True)
    if not scores:
        prefixed = [f"{t}*" if len(t) >= PREFIX_MIN_LEN and not is_exact_term(t) else t for t in terms]
        if prefixed != terms:
            scores = matching(require_all=True, words=prefixed)
    if not scores:
        corrected = _corrected_terms(session, terms)
        if corrected != terms:
            scores = matching(require_all=True, words=corrected)
            if scores:
                phrase_terms = corrected
    if not scores:
        scores = matching(require_all=False)
    if not scores:
        return []

    entries = list(session.scalars(select(Entry).where(*base, Entry.id.in_(scores))))
    phrase = " ".join(phrase_terms)

    def sort_key(entry: Entry) -> tuple[int, float, int]:
        has_phrase = phrase in re.sub(r"\W+", " ", (entry.content or "").lower())
        return (0 if has_phrase else 1, scores.get(entry.id, 0.0), -entry.id)

    entries.sort(key=sort_key)
    return entries[:limit]


# A query word this long or longer is also tried as a prefix when nothing
# matched it whole.
#
# **It was 4, and the reason given for that cannot happen.** The comment here
# said three letters would turn "the" into "the*" and match "theory",
# "thermal" and "these". But "the" is a stopword, and `query.search_terms`
# drops stopwords before any of this runs: `search_terms("the")` returns an
# empty list, so "the" never reaches the prefix stage to be starred. The
# premise was already handled one layer down.
#
# What the threshold did instead was refuse the case people actually type.
# The owner, 2026-09-21: the universal finder matches only whole words, so a
# note called "test" appears for "test" and not for "tes". Three characters in
# a find-as-you-type box is intent, not noise, and this is the only thing
# standing between the two.
#
# Two is left alone deliberately. The FTS5 table is built without a `prefix=`
# option, so a prefix query walks the term list rather than an index for it,
# and a two-letter prefix on a large notebook is a different cost question
# that wants the index option and a measurement, not a smaller number here.
PREFIX_MIN_LEN = 3
# Only words this long are ever "corrected": a three-letter word is one
# edit from dozens of others, and difflib's ratio cannot tell them apart.
CORRECT_MIN_LEN = 4
# difflib ratio floor for treating a vocabulary word as the query word
# misspelt: 0.8 is roughly one wrong letter in five, two in ten.
CORRECT_CUTOFF = 0.8


def is_exact_term(term: str) -> bool:
    """A word with a digit in it is a number, a code or a date: "4471" is not
    a misspelling of "447" and does not begin "44710" (audit 1029 N5), so it
    is matched as typed, never prefix-expanded and never typo-corrected."""
    return any(char.isdigit() for char in term)


def _corrected_terms(session: Session, terms: list[str]) -> list[str]:
    """Each term replaced by the closest word the FTS index holds, when it
    holds no such word itself. Terms already in the vocabulary, and short
    terms, are returned unchanged.

    Reads `entries_fts_vocab` (database.py) one first-letter range at a time
    - a few hundred candidates at most, and lets `difflib` pick. Nothing
    here is cleverer than that on purpose: it can only ever propose a word
    that is actually in a note, so a wrong correction still lands on real
    text rather than inventing a match."""
    corrected: list[str] = []
    for term in terms:
        if len(term) < CORRECT_MIN_LEN or is_exact_term(term):
            corrected.append(term)
            continue
        first = term[0]
        try:
            rows = session.execute(
                text(
                    "SELECT term FROM entries_fts_vocab "
                    "WHERE term >= :lo AND term < :hi"
                ),
                {"lo": first, "hi": chr(ord(first) + 1)},
            ).all()
        except Exception:  # noqa: BLE001 - an older database without the vocab table
            return terms
        vocabulary = [row.term for row in rows]
        if term in vocabulary:
            corrected.append(term)
            continue
        close = _near_words(term, vocabulary)
        # The vocabulary holds porter stems ("lectur"), which no one wrote; the
        # correction offered, and searched, is a word a note really uses.
        real = _word_for_stem(session, close[0], term) if close else None
        corrected.append(real or term)
    return corrected


def _near_words(term: str, vocabulary: list[str]) -> list[str]:
    """The vocabulary word closest to a misspelt term, as a one-item list.

    The vocabulary holds porter stems, which are shorter than the word typed
    ("respir" for "respiraton"), so a stem is also compared with the typed
    word cut to just past the stem's length."""
    best, best_ratio = None, CORRECT_CUTOFF
    for word in vocabulary:
        if abs(len(word) - len(term)) > 2 and not (len(word) >= CORRECT_MIN_LEN and len(word) < len(term)):
            continue
        for typed in {term, term[: len(word) + 1]}:
            ratio = difflib.SequenceMatcher(None, typed, word).ratio()
            if ratio >= best_ratio:
                best, best_ratio = word, ratio
    return [best] if best else []


def _word_for_stem(session: Session, stem: str, typed: str) -> str | None:
    """A whole word from a note that starts with `stem`, the one
    nearest the typed word; None when no note holds one."""
    rows = session.execute(
        text("SELECT content FROM entries WHERE content LIKE :p LIMIT 40"),
        {"p": f"%{stem}%"},
    ).all()
    found = re.compile(rf"\b{re.escape(stem)}\w*", re.IGNORECASE)
    words = {m.lower() for row in rows for m in found.findall(row.content or "")}
    nearest = difflib.get_close_matches(typed, sorted(words), n=1, cutoff=0)
    return nearest[0] if nearest else None


#: The stopword list and the term splitter both moved to `search/query.py`,
#: which is the floor both searches share (see its own comment on the import
#: cycle that made the move necessary).
#:
#: A `_STOPWORDS = query_understanding.STOPWORDS` alias stood here for one
#: commit, kept "under the name eighty lines of this file and
#: `ai/grounding.py` already use". That was true before the move and false
#: after it: the same commit rewrote every one of those call sites to go
#: through `search_terms`, so the alias was read by nothing. CodeQL said so
#: (alert 402, unused global) and a grep agreed, which is the whole value of
#: that check: a name kept for compatibility is worth keeping only while
#: something is compatible with it.


def _meaningful_terms(query: str) -> list[str]:
    """Search words worth matching on, in order. See `query.search_terms`."""
    return query_understanding.search_terms(query)


def configured_thresholds() -> tuple[float, float]:
    """(min_similarity, relative_z_margin), from user preferences if set,
    the module defaults otherwise. One place for every real caller (the API
    routes, /chat's retrieve() below) to read these, so semantic_search
    itself stays a pure function of its arguments, no hidden global-state
    dependency for a bare-session test to trip over."""
    from tessellate.core import deps

    config = deps.get_config()
    return (
        config.get_preference("search_min_similarity", MIN_SIMILARITY),
        config.get_preference("search_relative_z_margin", RELATIVE_Z_MARGIN),
    )


#: **Speculative retrieval** (WORLD_CLASS_PLAN H9, row 27). The question's
#: vector, kept by its exact text for the backend that made it: the Ask box
#: and the chat box send the words on a typing pause (`POST /search/warm`), so
#: the embedding call, the slow part of a search with a model behind it, is
#: already done when Enter arrives and the first token comes that much
#: sooner. A miss costs nothing: the vector is made here as it always was.
#: Kept on the embedding service itself, so two services (a reindex to a new
#: width, a test's fake) can never be handed each other's vectors.
_QUERY_VECTOR_CACHE = 64
_query_lock = threading.Lock()


def query_vector(embeddings: EmbeddingService, query: str):  # noqa: ANN201
    """The vector for `query`, from the cache when it was warmed."""
    key = (embeddings.backend_id(), query)
    with _query_lock:
        cache = embeddings.__dict__.setdefault("_query_vectors", OrderedDict())
        if key in cache:
            cache.move_to_end(key)
            return cache[key]
    loads_cold = getattr(embeddings, "loads_cold", None)
    if callable(loads_cold) and loads_cold():
        #: **No question waits for the model to load** (the owner's trace,
        #: 2026-10-11: 27.06 s before the first step, 21.75 s of it this
        #: load). The model loads in the background; this search reads by
        #: words, and the next one by meaning too.
        _load_later(embeddings)
        return None
    vector = embeddings.embed_text(query)
    if vector is not None:
        with _query_lock:
            cache[key] = vector
            while len(cache) > _QUERY_VECTOR_CACHE:
                cache.popitem(last=False)
    return vector


def _load_later(embeddings: EmbeddingService) -> None:
    """Load the search model in the background, once at a time; not while
    the launch warm-up (`embeddings.start_warmup`) is already loading it."""
    from tessellate.ai import embeddings as embedding_service

    if getattr(embeddings, "_warm_loading", False) or embedding_service.warmup_running():
        return
    try:
        embeddings._warm_loading = True
    except AttributeError:
        return

    def load() -> None:
        try:
            embeddings.embed_text("warm up")
        except Exception:  # noqa: BLE001  # the real search reports a broken model
            logger.debug("warm: the embedding model did not load", exc_info=True)
        finally:
            embeddings._warm_loading = False

    from tessellate.core import jobs

    jobs.enqueue("warm", load, name="warm the search model", dedupe_key="search-warm")


def warm(session: Session, query: str, embeddings: EmbeddingService) -> bool:
    """Embed what `_retrieve` will embed for `query`, ahead of Enter.

    The same subject `_retrieve` searches for (the question's scaffolding and
    its time phrase taken off by `search/query.py`), so the vector warmed is
    the vector asked for. False when there is nothing to warm.

    **A model not yet loaded is loaded now, in the background.** Measured on a
    fresh install (`scratchpad/ui-sweeps/inv1005-firstrun.js`): an empty
    notebook skips the launch warm-up (`embeddings.start_warmup`), so the
    first question paid the embedding model's cold load, 15 of the 17 s to
    the first answer. The Ask box asks for this as soon as it is typed in, so
    the load overlaps the person's typing instead of following their Enter.
    """
    if not embeddings.is_ready():
        _load_later(embeddings)
        return False
    asked = query_understanding.understand(query, _user_today(session))
    subject = asked.subject or query
    if is_recency_ask(query) or asked.time_only or len(subject.strip()) < 3:
        return False
    return query_vector(embeddings, subject) is not None


def semantic_search(
    session: Session,
    query: str,
    embeddings: EmbeddingService,
    limit: int = 5,
    min_similarity: float = MIN_SIMILARITY,
    relative_z_margin: float = RELATIVE_Z_MARGIN,
) -> list[tuple[Entry, float]] | None:
    """Best-matching entries with scores, or None when embeddings are
    unavailable (caller should fall back to keyword search).

    The MVP compared against every stored vector *and joined in the full
    `Entry` for each one* in Python, this docstring used to say "revisit
    only if it ever feels slow", and ANALYSIS.md §34's scale-test found it
    does: materialising every entry as an ORM object just to score and throw
    most of them away was ~85% of one search's cost at 20k+ notes (~6.6s of
    a ~7.3s call at 50k). The vector scan itself is still brute-force, there
    is no index to avoid it, but scoring needs only `(entry_id, embedding)`
    tuples, not full mapped entities, so that part is now a plain column
    query and only the handful of notes that actually rank get a real
    `Entry` fetched."""
    import numpy as np

    query_vec = query_vector(embeddings, query)
    if query_vec is None:
        return None

    query_norm = float(np.linalg.norm(query_vec))
    if query_norm == 0:
        return []

    # **The engine's matrix first** (WORLD_CLASS_PLAN row 1, F3). This used to
    # select every stored vector and parse it on every Ask and chat turn:
    # 24.5 ms median at 5,000 notes, most of a search, for data the process
    # already held in one array for the "see also" panel. The matrix is kept
    # in step by the writes and checks the table's fingerprint before it
    # answers, so a note edited, deleted or reindexed a moment ago scores on
    # what is stored now. The table scan below stays as the fallback, for a
    # query at a width the matrix does not hold (the minority side of a
    # half-finished reindex) or a matrix that cannot be had at all.
    scored = _score_from_matrix(session, query_vec, query_norm, embeddings.backend_id())
    if scored is None:
        scored = _score_from_table(session, query_vec, query_norm, embeddings.backend_id())
    if scored is None:
        return []
    entry_ids, scores, valid = scored

    # MIN_SIMILARITY alone assumes "0.25" means the same thing regardless of
    # which embedding model produced the vectors, it does not. A BGE-family
    # model (the current DEFAULT_ST_MODEL, embeddings.py) is anisotropic:
    # its vectors cluster in a narrow cone, so two genuinely unrelated notes
    # routinely land at 0.4-0.6 cosine similarity, nowhere near the "0 is
    # unrelated" an absolute floor implicitly assumes. Reported live: an
    # unrelated note scored 57% for an unconnected query, comfortably above
    # this floor. MIN_SIMILARITY predates that model (the built-in default
    # was all-MiniLM before it, which does not have anisotropy to nearly the
    # same degree: see embeddings.py's own comment on the switch) and was
    # never recalibrated.
    #
    # Rather than guess a new fixed number for BGE specifically, unverified
    # in this sandbox, which ran no local embedding engine at all per
    # CLAUDE.md: this adds a second, *relative* floor from the query's own
    # score distribution: a candidate has to beat what an unrelated note
    # typically scores for THIS query, not just clear an absolute number
    # picked for a different model. Self-calibrating regardless of backend,
    # and it degrades to "floor only" (relative_floor = -inf) when there
    # are too few candidates for a mean/std to mean anything, a two-note
    # notebook has no "typical unrelated score" to measure against.
    valid_scores = scores[valid]
    if valid_scores.size >= RELATIVE_MIN_CANDIDATES:
        relative_floor = float(np.mean(valid_scores) + relative_z_margin * np.std(valid_scores))
    else:
        relative_floor = float("-inf")

    # Vectorised rather than a Python loop over every row: at 5,000 notes the
    # loop was a millisecond of its own once the read above stopped
    # dominating. A stable sort on the negated scores keeps equal scores in
    # row order, which is what the `list.sort(reverse=True)` here did.
    # `valid` is in the mask too: a forgotten row in the matrix is all zeros,
    # and a zero score clears a floor a person has set to 0.
    keep = np.nonzero(valid & (scores >= min_similarity) & (scores >= relative_floor))[0]
    if keep.size == 0:
        return []
    ranked = keep[np.argsort(-scores[keep], kind="stable")]

    # A generous pool before the is_deleted filter below: a deleted note's
    # embedding can still be sitting in the table (nothing prunes it), and
    # over-fetching candidates is cheap next to under-returning matches.
    candidates = [(entry_ids[i], float(scores[i])) for i in ranked[: max(limit * 4, 40)]]
    entries_by_id = {
        e.id: e
        for e in session.scalars(
            select(Entry).where(
                Entry.id.in_([eid for eid, _ in candidates]),
                Entry.is_deleted == False,  # noqa: E712
                Entry.is_board == False,  # noqa: E712
            )
        )
    }
    result = [
        (entries_by_id[eid], score) for eid, score in candidates if eid in entries_by_id
    ]
    return result[:limit]


def _score_from_matrix(session: Session, query_vector, query_norm: float, backend_id: str):
    """`(entry_ids, scores, valid)` from the engine's matrix, or None to scan.

    None when the matrix cannot be had (the engine raised: never a failed
    search) or holds another width than the query's: after a model swap
    inside one backend the matrix follows the majority, and the rows at the
    query's width are the table scan's to find.
    """
    import numpy as np

    try:
        # `importlib`, not an `import` statement: `search/engine.py` imports
        # this module, so naming it here is the cycle
        # `tests/test_no_import_cycles.py` counts wherever the statement sits.
        engine = importlib.import_module("tessellate.search.engine")
        view = engine.vector_view(session, backend_id)
    except Exception:  # noqa: BLE001  # the scan below answers instead
        logger.warning("the retrieval matrix is unavailable; scanning the table", exc_info=True)
        return None
    if view is None:
        return None
    ids, rows, live = view
    if not ids or rows.shape[1] != query_vector.shape[0]:
        return None
    # `einsum`, not `@`: a matrix-vector product this size is memory-bound,
    # and `@` hands it to the BLAS thread pool, whose wake-up dominated on a
    # busy machine (measured at 5,000 x 384: 12 ms median through `@` with
    # other work running, 0.45 ms through `einsum`, 0.3 ms either way on one
    # thread). One core at memory speed is all this needs.
    scores = np.einsum("ij,j->i", rows, np.asarray(query_vector, dtype="float32") / np.float32(query_norm))
    # **A long note scores on its best paragraph too** (row 6, §14 item 3):
    # its own vector averages every subject it covers, so one paragraph about
    # the question used to rank below a short note that only brushed it.
    scores = importlib.import_module("tessellate.search.chunks").lift(
        session, backend_id, query_vector, ids, scores
    )
    return ids, scores, live


def _score_from_table(session: Session, query_vector, query_norm: float, backend_id: str):
    """The table scan `semantic_search` did on every request until 2026-09-24.

    Kept as the fallback, with the width handling it grew: see the comment
    inside. Returns `(entry_ids, scores, valid)`, or None for "nothing to
    score".
    """
    import numpy as np

    records = session.execute(
        select(EmbeddingRecord.entry_id, EmbeddingRecord.embedding).where(
            # Vectors from other backends live in a different space,
            # comparing them would give nonsense (plan §6.5).
            EmbeddingRecord.model_version
            == backend_id
        )
    ).all()

    if not records:
        return None

    # One matrix multiply instead of a Python loop of dot products, the scan
    # is still brute-force, but NumPy does it at memory speed.
    #
    # Only over the rows whose vector is the same width as the query, though.
    # `model_version` narrows this to one backend, and a backend is not a
    # dimension: swapping the embedding *model* inside the same backend (which
    # Settings → Embedding models offers as a button) leaves the old rows in
    # place at their old width. Stacking those into one array raises on the
    # ragged list and took the whole search down with it, every query
    # returning nothing, until a reindex that the error gave no hint to run.
    # Mismatched rows are skipped instead; they get their real scores back as
    # the reindex refills them.
    by_width: dict[int, list[tuple[int, np.ndarray]]] = {}
    for entry_id, blob in records:
        vector = bytes_to_vector(blob)
        by_width.setdefault(vector.shape[0], []).append((entry_id, vector))

    usable = by_width.get(query_vector.shape[0], [])
    if not usable:
        logger.warning(
            "no stored vectors match the query's %d dimensions (widths present: %s) "
            ", reindex to score these notes again",
            query_vector.shape[0],
            sorted(by_width),
        )
        return None
    if len(usable) < len(records):
        logger.info(
            "%d of %d vectors are a different width and were skipped, reindex to include them",
            len(records) - len(usable),
            len(records),
        )

    entry_ids = [entry_id for entry_id, _ in usable]
    vectors = np.stack([vector for _, vector in usable])

    norms = np.linalg.norm(vectors, axis=1)
    valid = norms > 0

    scores = np.zeros(len(vectors), dtype="float32")
    if np.any(valid):
        scores[valid] = np.dot(vectors[valid], query_vector) / (norms[valid] * query_norm)
    return entry_ids, scores, valid


# --- fusing the two searches ---------------------------------------------------
#
# The old rule was either/or: semantic won outright, and keyword was only
# consulted when semantic came back empty. That loses in both directions, and
# each failure is one a person notices immediately.
#
# - A note containing the query **verbatim** loses to three notes that are
#   vaguely on topic, because 0.31 cosine beats 0.28 and the exact match was
#   never in the running. Searching for a phrase you know you wrote and not
#   getting it is the single most damaging thing a notebook search can do.
# - A misspelling, a synonym, or a question phrased differently from the note
#   ("how do I prove dough" vs "bread rising times") is exactly what semantic
#   search is *for*, and it was being discarded whenever the keyword branch
#   happened to fire first.
#
# Reciprocal rank fusion combines the two by **rank** rather than by score,
# which is what makes it robust here: a cosine similarity and a keyword tally
# are not on the same scale and never will be, so any weighted sum of the two
# needs a tuning constant per notebook. RRF needs none: it only asks "how near
# the top of each list did this note come?"
RRF_K = 10

# How deep each ranking is read before fusing. Deeper than the number returned,
# because the whole point is that a note ranked 8th by meaning and 3rd by words
# can beat one ranked 2nd by meaning and nowhere by words.
FUSION_DEPTH = 20


def _recency_pin_ranking(entries: list[Entry]) -> list[Entry]:
    """The same candidates, reordered by pinned-first then most-recently-
    touched: a third vote for `_fuse` rather than a new source of matches.

    BACKLOG.md §95 item B.6, asked for directly: "search ranks by relevance;
    it does not know that a note pinned last week matters more than a
    relevant one from 2023." Both columns already existed (`Entry.pinned`,
    `Entry.updated_at`); nothing read them at search time.

    Deliberately a *reorder of the candidates a real search already found*,
    never a fresh query, a pinned note that has nothing to do with the
    question is not a better answer to it, so this only ever influences
    ranking among notes that already matched by meaning or by word. Fed into
    `_fuse` exactly like the semantic and keyword rankings: by rank
    position, not a weighted score, for the same reason those two are (see
    RRF_K's own comment): "how recently pinned" and "how many days old"
    are not on a shared scale with cosine similarity or a BM25 tally, and a
    weighted sum of the three would need a tuning constant this notebook has
    no way to pick.
    """
    return sorted(
        entries,
        key=lambda entry: (not entry.pinned, -(entry.updated_at or entry.created_at).timestamp()),
    )


def _fuse(ranked_lists: list[list[Entry]], limit: int) -> list[Entry]:
    """Reciprocal rank fusion over several rankings of the same notes."""
    scores: dict[int, float] = {}
    seen: dict[int, Entry] = {}
    for ranking in ranked_lists:
        for position, entry in enumerate(ranking[:FUSION_DEPTH]):
            scores[entry.id] = scores.get(entry.id, 0.0) + 1.0 / (RRF_K + position + 1)
            seen.setdefault(entry.id, entry)
    order = sorted(scores, key=lambda note_id: (-scores[note_id], -note_id))
    return [seen[note_id] for note_id in order[:limit]]


# How many notes the graph is allowed to add to an answer's context, and how
# many of the top hits it walks out from.
#
# **This is what makes the app a memory *map* rather than a search box.** A
# question retrieves the notes that match it; the notes those *link to* are
# very often where the answer actually is, you wrote the question's subject in
# one note and the thing you need in the note you linked from it. That
# connection is the structure the whole app is built around, and until now no
# answer used it: only the agent could walk links, and only when it thought to.
#
# Deliberately small, and deliberately at the end of the list. These are
# context, not matches: they earned their place by being connected to
# something that matched, which is weaker evidence than matching. A large
# expansion would push real matches out of a budgeted prompt to make room for
# notes nobody searched for.
GRAPH_EXPANSION_SEEDS = 3
GRAPH_EXPANSION_LIMIT = 3
# ROADMAP.md item 33: a second hop, opt-in by being small and automatic
# rather than a user-visible "search deeper" action: the roadmap left that
# choice open; automatic is the one that needs no new UI and degrades to
# "just doesn't add much" rather than "a control nobody found". Smaller than
# the first hop on purpose: a neighbour-of-a-neighbour is weaker evidence
# again, verified the same way (still a real link, still carries its own
# reason if it has one) but two links removed from what was actually asked.
GRAPH_EXPANSION_HOP2_LIMIT = 2


def _linked_neighbours(
    session: Session, seeds: list[int], exclude: set[int]
) -> tuple[list[int], dict[int, str]]:
    """One hop of `graph_expansion`'s own walk: links plus reply threads,
    strongest first (ties in the order found). Factored out so a second hop
    can call it again starting from the first hop's own results, rather than
    duplicating the walk.

    Ordering matters here specifically because both `GRAPH_EXPANSION_LIMIT`
    and `GRAPH_EXPANSION_HOP2_LIMIT` truncate this list: §87.5's payoff for
    this side is which neighbours *survive* that truncation, not just how
    they're labelled.
    """
    from tessellate.core.database import EntryLink

    neighbours: list[int] = []
    reasons: dict[int, str] = {}
    # A reply/parent thread has no EntryLink to read a type or confidence
    # off, so it gets no entry here, the sort below falls back to 1.0 for
    # it, the same baseline `entry/paths.py`'s THREAD_WEIGHT == LINK_WEIGHT
    # already treats a reply and a bare link as equally strong.
    strengths: dict[int, float] = {}
    if not seeds:
        return neighbours, reasons

    links = session.scalars(
        select(EntryLink).where(
            or_(
                EntryLink.source_entry_id.in_(seeds),
                EntryLink.target_entry_id.in_(seeds),
            )
        )
    )
    for link in links:
        strength = link_strength(link.link_type, link.reason_confidence)
        for end in (link.source_entry_id, link.target_entry_id):
            if end in exclude:
                continue
            if end not in neighbours:
                neighbours.append(end)
                if link.reason:
                    reasons[end] = link.reason
            # A neighbour reachable by more than one link (from different
            # seeds, say) is scored by its strongest connection, not its
            # first-seen one.
            strengths[end] = max(strengths.get(end, 0.0), strength)
    # Replies, both directions: a thread is one train of thought, so the note
    # that answers the match is as relevant as the one it answers.
    for entry in session.scalars(
        select(Entry).where(Entry.parent_id.in_(seeds), Entry.is_deleted == False)  # noqa: E712
    ):
        if entry.id not in exclude and entry.id not in neighbours:
            neighbours.append(entry.id)
    # The seeds' own parents, in one query rather than one `session.get` each
    #, same reasoning as `semantic_search`'s own docstring on avoiding
    # per-row fetches.
    for parent_id in session.scalars(
        select(Entry.parent_id).where(Entry.id.in_(seeds), Entry.parent_id.is_not(None))
    ):
        if parent_id not in exclude and parent_id not in neighbours:
            neighbours.append(parent_id)
    neighbours.sort(key=lambda n: strengths.get(n, 1.0), reverse=True)
    return neighbours, reasons


def graph_expansion(
    session: Session, matches: list[Entry], limit: int = GRAPH_EXPANSION_LIMIT
) -> tuple[list[Entry], dict[int, str], dict[int, int]]:
    """Notes connected to the best matches, nearest first, plus *why*, a
    link's own reason, keyed by neighbour id, for the ones that have one, 
    and *how far*, keyed the same way (1 = directly linked to a match, 2 =
    linked to one of those). Only the one caller (`_retrieve`) reads either
    extra dict; the reason is what lets the "linked to a match" badge say
    what the link actually is instead of just that one exists (asked for
    directly: "does the reason in the links show in [connected results] as
    well?", it didn't, this is that gap closed), and the hop count is what
    lets a second-hop note render as a visibly weaker tier rather than
    merged in with the first hop's (ROADMAP.md item 33).

    Links and reply threads only, not shared tags. A tag is a filing label
    that can put fifty unrelated notes one hop apart, and the same reasoning
    that made `entry/paths.py` weight tag steps down applies with more force
    here: this list goes straight into a prompt, where a weak connection is
    indistinguishable from a strong one.
    """
    if not matches:
        return [], {}, {}

    have = {entry.id for entry in matches}
    seeds = [entry.id for entry in matches[:GRAPH_EXPANSION_SEEDS]]
    hop1, reasons = _linked_neighbours(session, seeds, have)

    hop2: list[int] = []
    if hop1 and GRAPH_EXPANSION_HOP2_LIMIT:
        hop2_all, hop2_reasons = _linked_neighbours(
            session, hop1[:GRAPH_EXPANSION_SEEDS], have | set(hop1)
        )
        hop2 = hop2_all[:GRAPH_EXPANSION_HOP2_LIMIT]
        for note_id in hop2:
            if note_id in hop2_reasons:
                reasons[note_id] = hop2_reasons[note_id]

    neighbours = hop1 + hop2
    if not neighbours:
        return [], {}, {}
    found = list(
        session.scalars(
            select(Entry).where(
                Entry.id.in_(neighbours),
                Entry.is_deleted == False,  # noqa: E712
                Entry.is_private == False,  # noqa: E712
                Entry.is_board == False,  # noqa: E712
            )
        )
    )
    # Back into the order the walk found them, so the nearest neighbour of the
    # best match comes first rather than whatever the database returned.
    by_id = {entry.id: entry for entry in found}
    hop_of = {note_id: 1 for note_id in hop1} | {note_id: 2 for note_id in hop2}
    ordered_hop1 = [by_id[note_id] for note_id in hop1 if note_id in by_id][:limit]
    ordered_hop2 = [
        by_id[note_id] for note_id in hop2 if note_id in by_id
    ][:GRAPH_EXPANSION_HOP2_LIMIT]
    ordered = ordered_hop1 + ordered_hop2
    return (
        ordered,
        {e.id: reasons[e.id] for e in ordered if e.id in reasons},
        {e.id: hop_of[e.id] for e in ordered},
    )


def in_range(
    session: Session, since, until, limit: int = 25
) -> list[Entry]:
    """Every note written in a date range, newest first.

    The answer to a question that is *only* about time, "what did I save last
    week?", where ranking by similarity would be ranking noise: there is no
    subject to be similar to.
    """
    clauses = [
        Entry.is_deleted == False,  # noqa: E712
        Entry.is_private == False,  # noqa: E712
        Entry.is_board == False,  # noqa: E712
    ]
    if since is not None:
        clauses.append(Entry.created_at >= datetime.combine(since, time.min))
    if until is not None:
        clauses.append(Entry.created_at <= datetime.combine(until, time.max))
    return list(
        session.scalars(
            select(Entry)
            .where(*clauses)
            .order_by(Entry.created_at.desc(), Entry.id.desc())
            .limit(limit)
        )
    )


def _written_at(entry: Entry):
    """When a note was written, for sorting. A note with no timestamp sorts
    oldest rather than crashing the comparison, the same choice `_within`
    makes when it keeps an undated note rather than filtering on an absence."""
    written = getattr(entry, "created_at", None)
    return written or datetime.min


_WEEKDAY = recognise.WEEKDAY_WORD


def day_mentions(session: Session, since, until, phrase: str = "") -> set[int]:  # noqa: ANN001
    """Ids of the notes that *mention* the one day asked about, whenever they
    were written (E6): "what do I have on 3 November" is the Dentist note that
    says "3 November at 2pm", written weeks before, and "how much did I lift on
    friday" is the log that says "Friday deadlift 100kg". A mention is a stored
    date landing on the day, or, for a weekday asked by name, the weekday's
    name in the text. Empty for a window of more than one day."""
    if since is None or until is None or since != until:
        return set()
    day = since
    #: Month and day only, whatever the year: "the 3rd of November" read
    #: without a year lands on last year's, and the note says this year's.
    found = {
        row[0]
        for row in session.execute(
            select(EntryDate.entry_id).where(func.strftime("%m-%d", EntryDate.at) == f"{day.month:02d}-{day.day:02d}")
        )
    }
    named = _WEEKDAY.search(phrase or "")
    if named:
        like = f"%{like_escape(named.group(1).lower())}%"
        found |= set(session.scalars(select(Entry.id).where(Entry.content.ilike(like, escape=LIKE_ESCAPE))))
    if not found:
        return found
    visible = select(Entry.id).where(
        Entry.id.in_(found), Entry.is_deleted == False, Entry.is_private == False, Entry.is_board == False  # noqa: E712
    )
    return set(session.scalars(visible))


def _within(entry: Entry, since, until, mentioned=()) -> bool:  # noqa: ANN001
    """Was this note written in the range? Notes with no timestamp are kept, 
    dropping a note because its date is missing would be filtering on an
    absence rather than on a fact."""
    written = getattr(entry, "created_at", None)
    if written is None or getattr(entry, "id", None) in mentioned:
        return True
    day = written.date() if hasattr(written, "date") else written
    if since is not None and day < since:
        return False
    if until is not None and day > until:
        return False
    return True


@dataclass
class Retrieval:
    """What a search found, and how, everything `retrieve` knows.

    A separate shape rather than a wider tuple because the *provenance* is the
    part that matters to the model: a note that arrived because it is linked to
    a match is context, and reporting it as a search hit is the same class of
    mistake as calling a shared tag a link. The two-value `retrieve()` below
    stays exactly as it was for everything that only wants the notes.
    """

    entries: list[Entry]
    mode: str
    #: Ids that came from the graph walk rather than from either search.
    connected_ids: set[int]
    #: The date range applied, and the phrase it came from, or None.
    since: object = None
    until: object = None
    when_phrase: str = ""
    #: The category the question named as where its notes are, or "".
    category: str = ""
    #: Why each entry is here, keyed by id, e.g. {"type": "semantic",
    #: "score": 0.81} or {"type": "keyword", "terms": ["gym"]}. Built from
    #: information `_rank`/`_fuse` would otherwise discard once they've
    #: collapsed two ranked lists into one ordered-by-relevance list of
    #: entries. Best-effort: an id with no entry here matched by whatever
    #: `mode` alone already says (`dated`, `recent`, `attached`, …).
    match_info: dict = None
    #: Ids that mention the one day asked about (`day_mentions`).
    mentioned: set = None

    def __post_init__(self) -> None:
        if self.match_info is None:
            self.match_info = {}
        if self.mentioned is None:
            self.mentioned = set()


def retrieve_detailed(
    session: Session,
    query: str,
    embeddings: EmbeddingService,
    limit: int = 5,
    expand_graph: bool = True,
    locale: str | None = None,
) -> Retrieval:
    """`retrieve`, with the provenance kept. See `Retrieval`.

    `locale` is the asker's (the browser's), so "3/4" reads as 4 March in
    en-US and 3 April elsewhere, the way the quick-add reading route does."""
    found: dict = {}
    entries, mode = _retrieve(
        session, query, embeddings, limit, expand_graph, found, locale
    )
    return Retrieval(
        entries=entries,
        mode=mode,
        connected_ids=found.get("connected", set()),
        since=found.get("since"),
        until=found.get("until"),
        when_phrase=found.get("when_phrase", ""),
        category=found.get("category", ""),
        match_info=found.get("match_info", {}),
        mentioned=found.get("mentioned", set()),
    )


def retrieve(
    session: Session,
    query: str,
    embeddings: EmbeddingService,
    limit: int = 5,
    expand_graph: bool = True,
) -> tuple[list[Entry], str]:
    """Entries for a question + how they were found, so the UI can be honest.

    Modes: `hybrid` (both searches agreed on a ranking), `semantic`, `keyword`,
    `recent` (a broad question matched nothing specific, so the notebook must
    not look empty), `dated` (the question was about *when*), or `none`.

    `expand_graph` adds notes *connected* to the matches, see
    `graph_expansion`. On by default because it is the app's whole premise;
    switched off by callers that want the matches alone, such as a duplicate
    check, where a linked note is not a candidate for anything.

    `retrieve_detailed` above is the same search with the provenance kept.
    """
    return _retrieve(session, query, embeddings, limit, expand_graph, {})


#: How the most recent search found its notes, for Settings' one-line answer
#: to "is search by meaning working" (INBOX 431 (3), the owner: "half the time
#: I can't tell if it is working or how well"). Process-wide and overwritten,
#: never a log: the question is only ever about the last one.
_last_search: dict = {}


def last_search() -> dict:
    """`{"mode": "hybrid"|"semantic"|"keyword", "at": ISO time}`, or {}."""
    return dict(_last_search)


def _rank(
    semantic: list[tuple[Entry, float]] | None, keyword: list[Entry], limit: int
) -> tuple[list[Entry], str]:
    ranked, mode = _rank_inner(semantic, keyword, limit)
    note_search_mode(mode)
    return ranked, mode


def note_search_mode(mode: str) -> None:
    """Record how a search found its notes (the box's engine calls this too)."""
    _last_search.update(mode=mode, at=datetime.now(timezone.utc).isoformat())


def _rank_inner(
    semantic: list[tuple[Entry, float]] | None, keyword: list[Entry], limit: int
) -> tuple[list[Entry], str]:
    """Combine a semantic and a keyword result list into one ranked answer,
    with an honest label for how it was found. Factored out so the
    date-range fallback in `_retrieve` (searching again with the same two
    lists, minus the range) can reuse it instead of repeating the branch."""
    if semantic is None:
        # No embedding backend at all: keyword search is the whole of search,
        # not a fallback, and saying "keyword" is the honest label.
        return keyword[:limit], "keyword"
    if semantic and keyword:
        sem_entries = [entry for entry, _s in semantic]
        # The pool both searches already agreed is relevant, recency/pin
        # only ever reorders within it, see _recency_pin_ranking's own
        # docstring on why that scope matters.
        candidates = {entry.id: entry for entry in [*sem_entries, *keyword]}.values()
        return (
            _fuse(
                [sem_entries, keyword, _recency_pin_ranking(list(candidates))],
                limit,
            ),
            "hybrid",
        )
    if semantic:
        return [entry for entry, _s in semantic][:limit], "semantic"
    return keyword[:limit], "keyword"


_RECENCY_ASK = re.compile(
    r"\b(?:last|latest|newest|most recent|recent)\s+(?:\w+\s+){0,2}?(?:note|notes|entry|entries|thing i (?:wrote|saved|added))\b"
    r"|\b(?:write|wrote|written|saved|added|captured)\b[^.?!]{0,20}\b(?:last|most recently)$"
    #: "What have I saved recently?" (INBOX 441): the whole question is the
    #: verb and the time word, nothing between them to search for. A topic
    #: in between ("written about golf recently") stays a search.
    r"|^what\s+(?:have|did|had)\s+i\s+(?:been\s+)?(?:write|wrote|written|writing|save|saved|saving|add|added|adding|capture|captured|capturing|note|noted)\s+(?:down\s+)?(?:recently|lately)$",
    re.IGNORECASE,
)


def is_recency_ask(query: str) -> bool:
    r"""Whether a question asks for the newest notes rather than a subject.

    The trailing whitespace and closing marks are stripped here, in code,
    so the pattern ends on a word and `$` with no quantifier before it:
    any `\s*` (or `[\s?.!]*`) ahead of `$` backtracks over a run of tabs
    on every start position `search` tries (CodeQL 443 and 445, the second
    after a 300-character slice the analysis cannot see). Read on the first
    300 characters: a recency question is short.
    """
    return bool(_RECENCY_ASK.search(query[:300].strip().rstrip("?.! \t\r\n")))


#: The words a question about a whole category is made of besides the
#: category's own name: "Summarise my notes in Health" is nothing but these,
#: so it asks for the category, not for notes about some subject in it.
_CATEGORY_ONLY_WORDS = frozenset(
    "summarise summarize summary sum up recap overview what whats say says said "
    "have has i ive my me all every the a an of in under from about do does did "
    "notes note entries entry saved written wrote tell give show list category".split()
)


def _category_named_whole(session: Session, subject: str):
    """The category whose name is all of `subject` ("courses & study",
    "Courses and Study"), or None."""
    from tessellate.core.database import Category

    said = re.sub(r"\s+", " ", re.sub(r"\band\b", "&", (subject or "").lower())).strip(" ?.!")
    if not said:
        return None
    for category in session.scalars(select(Category)):
        name = re.sub(r"\s+", " ", re.sub(r"\band\b", "&", (category.name or "").lower())).strip()
        if name and name == said:
            return category
    return None


def _named_category(session: Session, query: str):
    """The category a question names as where its notes are, or None.

    "notes in Health", "under Work", "my Travel notes", "the Cooking
    category": the app suggests "Summarise my notes in Health." itself, and
    retrieval answered it from whatever matched the words, other categories
    included (tests/test_ask_category_scope.py). A bare word is not enough:
    "how does the physio work" names no category, so the name has to be
    framed as a place ("in", "under", "from") or as a kind of note ("my Work
    notes"). Answers `(category, the question with that phrase taken out)`.
    """
    from tessellate.core.database import Category
    from tessellate.entry import manager

    try:
        categories = list(session.scalars(select(Category)))
    except Exception:  # noqa: BLE001
        return None
    for category in sorted(categories, key=lambda c: -len(c.name or "")):
        name = (category.name or "").strip()
        if not name or name == manager.UNCATEGORISED:
            continue
        named = re.escape(name)
        for pattern in (
            rf"\b(?:in|under|from|filed under)\s+(?:my\s+|the\s+)?{named}\b(?:\s+(?:category|notes?))?",
            rf"\b(?:my|the)\s+{named}\s+(?:notes?|category)\b",
        ):
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                rest = (query[: match.start()] + " " + query[match.end() :]).strip()
                return category, rest
    return None


def _category_only(rest: str) -> bool:
    """Whether what is left of the question asks for nothing narrower."""
    words = re.findall(r"[a-z']+", rest.lower().replace("'", ""))
    return all(word in _CATEGORY_ONLY_WORDS or len(word) < 3 for word in words)


def _category_notes(session: Session, category_id: int, limit: int) -> list[Entry]:
    """A category's notes, newest first."""
    return list(
        session.scalars(
            select(Entry)
            .where(
                Entry.is_deleted == False,  # noqa: E712
                Entry.is_private == False,  # noqa: E712
                Entry.is_board == False,  # noqa: E712
                Entry.category_id == category_id,
            )
            .order_by(Entry.created_at.desc(), Entry.id.desc())
            .limit(limit)
        )
    )


def _early_answer(session: Session, query: str, asked, limit: int, mentioned=()):  # noqa: ANN001
    """The two questions that are an order or a range, not a subject, or None."""
    #: **"My last note" is an order, not a subject** (the owner at release,
    #: wrapup-0927 10 n: "Show me my last entry" answered with an older
    #: note). Searched by meaning, "last entry" matches whatever note talks
    #: about entries; the question is about when. The newest notes, newest
    #: first, and the prompt now carries each note's dates, so the answer
    #: can say which is newest written and which was last edited.
    if is_recency_ask(query):
        return _without_private(recent_entries(session, limit=min(limit, RECENT_FALLBACK_LIMIT))), "recent"
    if asked.time_only:
        # Nothing but a date range: list it. Ranking by similarity here would
        # be ranking noise, and the honest answer to "what did I write last
        # week" is *the notes from last week*, in order. An empty week falls
        # through so the caller still gets recent notes.
        dated = in_range(session, asked.since, asked.until)
        if mentioned:
            seen = {e.id for e in dated}
            dated += [e for e in session.scalars(select(Entry).where(Entry.id.in_(set(mentioned) - seen)))]
        if dated:
            return _without_private(dated)[: max(limit, 10)], "dated"
    return None


def _candidates(session: Session, subject: str, embeddings: EmbeddingService, scope):  # noqa: ANN001
    """Both searches for the subject rather than the sentence, inside the
    named category when there is one."""
    _min_sim, _z_margin = configured_thresholds()
    semantic = semantic_search(
        session, subject, embeddings, limit=FUSION_DEPTH,
        min_similarity=_min_sim, relative_z_margin=_z_margin,
    )
    keyword = keyword_search(session, subject, limit=FUSION_DEPTH)
    if scope is not None:
        if semantic is not None:
            semantic = [(entry, score) for entry, score in semantic if entry.category_id == scope.id]
        keyword = [entry for entry in keyword if entry.category_id == scope.id]
    return semantic, keyword


def _narrow_to_range(semantic, keyword, asked, mentioned=()):  # noqa: ANN001
    """A range alongside a subject narrows the candidates before they are
    ranked, so "the allotment, last week" cannot be answered with a note from
    March that happens to be a better match.

    **Except when the range is soft.** "Recently" is a lean, not a boundary
    (`Understood.soft`), and filtering on it is what made "jokes I have saved
    recently" come back with a gym routine: the two notes tagged `jokes` were
    16 and 30 days old, the fortnight window dropped both. A soft range sorts
    (newest first) and labels; it does not exclude."""
    if asked.has_range and not asked.soft:
        if semantic is not None:
            semantic = [(entry, score) for entry, score in semantic if _within(entry, asked.since, asked.until, mentioned)]
        keyword = [e for e in keyword if _within(e, asked.since, asked.until, mentioned)]
    elif asked.soft:
        # Recency as a tiebreak rather than a gate: of the notes that match the
        # subject, the newer ones come first, which is the whole of what the
        # word was asking for.
        keyword = sorted(keyword, key=_written_at, reverse=True)
        if semantic is not None:
            semantic = sorted(semantic, key=lambda pair: _written_at(pair[0]), reverse=True)
    return semantic, keyword


def _outside_window(semantic_any_time, keyword_any_time, asked, limit: int):  # noqa: ANN001
    """A subject was named and nothing matched it *inside* the window (reported
    directly: a note about jokes, asked about as "two weeks ago", was written
    three weeks ago and came back empty). This drops the date and keeps the
    subject, so it can never return something unrelated to what was asked,
    only the same match outside the window the person's memory of *when* was
    wrong about.

    **Bounded, not unbounded**: widened by the window's own span rather than
    searched across the whole notebook, so "the allotment, last week" still
    answers nothing when the only allotment note is three months old."""
    span = asked.until - asked.since if asked.since and asked.until else None
    since_wide = asked.since - span if span is not None else asked.since
    until_wide = asked.until + span if span is not None else asked.until
    outside, _mode = _rank(
        [(e, s) for e, s in semantic_any_time if _within(e, since_wide, until_wide)] if semantic_any_time is not None else None,
        [e for e in keyword_any_time if _within(e, since_wide, until_wide)],
        limit,
    )
    return (_without_private(outside), "outside_range") if outside else ([], "dated")


def _nothing_matched(session: Session, asked, scope, semantic, any_time, limit: int, found: dict, subject: str):  # noqa: ANN001
    """What to answer when ranking found nothing, or None to carry on empty."""
    if scope is not None:
        return _without_private(_category_notes(session, scope.id, max(limit, 10))), "category"
    if semantic is None:
        #: **No meaning search yet** (the model still loading, or none): a
        #: subject that is a category's whole name ("what have I saved about
        #: courses & study?") is that category, not the newest notes. With
        #: the model up, meaning finds the same notes by what they say.
        named = _category_named_whole(session, subject)
        if named is not None:
            found["category"] = named.name
            return _without_private(_category_notes(session, named.id, max(limit, 10))), "category"
    # The "never look empty" fallback is recent notes, but **not when the
    # question named a date range**: "what did I write about the allotment last
    # week" with nothing that week would otherwise come back with unrelated
    # notes from any time, silently dropping the one constraint the person
    # stated. A dated question that finds nothing falls back *within its
    # range*, and if that is empty returns nothing, labelled `dated`.
    #
    # **Only when the question was about time alone.** With a subject, listing
    # the window drops the more specific constraint and is how "jokes I have
    # saved recently" was answered with a gym routine. Nothing, labelled
    # `dated`, is the honest reply for a subject.
    if asked.has_range and not asked.subject:
        return _without_private(in_range(session, asked.since, asked.until, limit=limit)), "dated"
    if asked.has_range:
        return _outside_window(any_time[0], any_time[1], asked, limit)
    recent = recent_entries(session, limit=RECENT_FALLBACK_LIMIT)
    return (_without_private(recent), "recent") if recent else None


def _match_info(entries: list[Entry], sem_scores: dict, kw_terms) -> dict:  # noqa: ANN001
    """Why each of these is here, built before graph expansion appends any
    connected notes, so "connected" always wins over an incidental keyword
    overlap for those (a neighbour that also shares a word with the question is
    still here *because it's linked*, not because it matched)."""
    info: dict = {}
    for entry in entries:
        content = (entry.content or "").lower()
        matched_terms = [t for t in kw_terms if t in content]
        if entry.id in sem_scores and matched_terms:
            info[entry.id] = {"type": "hybrid", "score": round(sem_scores[entry.id], 2), "terms": matched_terms}
        elif entry.id in sem_scores:
            info[entry.id] = {"type": "semantic", "score": round(sem_scores[entry.id], 2)}
        elif matched_terms:
            info[entry.id] = {"type": "keyword", "terms": matched_terms}
    return info


def _append_connected(session: Session, entries: list[Entry], match_info: dict, found: dict) -> None:
    # Appended, never interleaved: a connected note is context and a match is
    # an answer, and a prompt that has to drop something should drop the
    # context first. The order encodes that.
    neighbours, neighbour_reasons, neighbour_hops = graph_expansion(session, entries)
    for neighbour in neighbours:
        if all(neighbour.id != entry.id for entry in entries):
            entries.append(neighbour)
            found["connected"].add(neighbour.id)
            # A second-hop note (item 33) is real evidence but weaker, so it
            # gets its own badge type rather than looking like a neighbour.
            info = {"type": "connected_2hop" if neighbour_hops.get(neighbour.id) == 2 else "connected"}
            if neighbour.id in neighbour_reasons:
                info["reason"] = neighbour_reasons[neighbour.id]
            match_info[neighbour.id] = info


def _category_scope(session: Session, query: str, limit: int, found: dict):  # noqa: ANN202
    """The category the question names (or None) and, when it asks for the
    whole category, the listing that answers it (else None)."""
    scoped = _named_category(session, query)
    if scoped is None:
        return None, None
    scope, rest = scoped
    found["category"] = scope.name
    if _category_only(rest):
        return scope, (_without_private(_category_notes(session, scope.id, max(limit, 10))), "category")
    return scope, None


def _dated_candidates(session: Session, mentioned: set, limit: int) -> list[Entry]:
    """The notes that say the day the person gave, newest first."""
    #: The day is the anchor the person gave; their word for the thing
    #: ("lift" for "deadlift") may not be the note's. The notes that say
    #: the day are the candidates.
    return list(session.scalars(select(Entry).where(Entry.id.in_(mentioned)).order_by(Entry.created_at.desc(), Entry.id.desc()).limit(limit)))


def _latest_about(session: Session, query: str, embeddings: EmbeddingService, limit: int, found: dict, locale: str | None):  # noqa: ANN202
    """"The latest notes about running", "the last three notes": the subject
    filters first, then the newest of what it left (audit 1029 C31); the
    newest notes of the whole notebook were the answer to a subject never
    searched. None when the query is no such request."""
    from tessellate.ai import note_rank

    #: A find's topic keeps no noun ("latest", "last three"): short, it is read bare.
    bare = len(query.split()) <= 3
    rec = note_rank.recency(query, bare=bare)
    if rec is None:
        return None
    if not rec.subject:
        return (_without_private(recent_entries(session, limit=rec.count)), "recent") if rec.said_count or bare else None
    entries, mode = _retrieve(session, rec.subject, embeddings, max(limit, 20), False, found, locale)
    terms = _meaningful_terms(rec.subject)
    held = [e for e in entries if mode != "recent" and any(t in (e.content or "").lower() for t in terms)]
    held.sort(key=lambda e: (e.created_at, e.id), reverse=True)
    return _without_private(held[: rec.count]), mode if held else "keyword"


def _retrieve(
    session: Session,
    query: str,
    embeddings: EmbeddingService,
    limit: int,
    expand_graph: bool,
    found: dict,
    locale: str | None = None,
) -> tuple[list[Entry], str]:
    """The search itself. `found` is filled in with what happened, for
    `retrieve_detailed`; the plain caller passes a dict it throws away."""
    # What the question is actually asking. A time phrase becomes a filter
    # instead of search terms, and the question's scaffolding comes off before
    # anything is embedded: see `search/query.py` for why both matter.
    asked = query_understanding.understand(query, _user_today(session), locale)
    found["since"] = asked.since
    found["until"] = asked.until
    found["when_phrase"] = asked.when_phrase
    found["connected"] = set()
    mentioned = day_mentions(session, asked.since, asked.until, asked.when_phrase) if asked.has_range else set()
    found["mentioned"] = mentioned
    latest = _latest_about(session, query, embeddings, limit, found, locale)
    if latest is not None:
        return latest
    early = _early_answer(session, query, asked, limit, mentioned)
    if early is not None:
        return early

    #: **A named category is a scope** (`_named_category`). A question that
    #: asks for the whole category lists it; one with a subject searches
    #: inside it, and lists it when nothing inside matches.
    scope, listed = _category_scope(session, query, limit, found)
    if listed is not None:
        return listed

    # Falls back to the whole question when stripping left nothing to search for.
    subject = asked.subject or query
    semantic, keyword = _candidates(session, subject, embeddings, scope)
    # Kept before the range narrows them, so a subject match outside the
    # stated window stays reachable as a fallback without a second search.
    any_time = (semantic, keyword)
    # Captured before `_rank`/`_fuse` collapse both lists into one ordered list
    # and lose the per-entry detail: a cosine score means something, a fused
    # rank position doesn't. Range-filtering only removes candidates, never
    # changes their score, so looking these up by id later stays correct.
    sem_scores = {entry.id: score for entry, score in semantic} if semantic is not None else {}
    kw_terms = _meaningful_terms(subject)
    semantic, keyword = _narrow_to_range(semantic, keyword, asked, mentioned)

    entries, mode = _rank(semantic, keyword, limit)
    if not entries and mentioned:
        dated = _dated_candidates(session, mentioned, limit)
        if dated:
            return _without_private(dated), "dated"
    if not entries:
        miss = _nothing_matched(session, asked, scope, semantic, any_time, limit, found, subject)
        if miss is not None:
            return miss

    entries = _without_private(entries)
    match_info = _match_info(entries, sem_scores, kw_terms)
    #: Not across a scope: a neighbour from another category is exactly the
    #: stray a question about one category must not be answered with.
    if expand_graph and entries and scope is None:
        _append_connected(session, entries, match_info, found)
    found["match_info"] = match_info

    # One final filter covering every mode. Private notes are also excluded by
    # the individual queries and have no embeddings to match on, but retrieval
    # feeds the AI's context: a single missed path would hand a private note
    # to the model, so it's checked once more here where every route converges.
    return _learned_order(session, query, _without_private(entries)), mode


def _learned_order(session: Session, query: str, entries: list[Entry]) -> list[Entry]:
    """Move what the person opened last time a question like this was asked.

    WORLD_CLASS_PLAN I7. The ranking above has no memory: asked the same
    question next week it returns the same order, including the order that
    was wrong enough that the person scrolled past the first result to open
    the third. An `open_after_ask` correction records which one they opened,
    and this puts it back on top.

    Deliberately a *reorder of what was already found*, never an addition: a
    boost that could inject a note the search did not match would make one
    click permanently change what the notebook appears to contain, which is
    the failure mode of every recommender that learns too eagerly. If the
    note is not in this result, it stays out of it.

    "A question like this" is word overlap against the recorded question, so
    "sourdough notes" and "my sourdough notes" are the same question and
    "sourdough" and "tax return" are not. Half the recorded question's words,
    at least one, which is strict enough that two unrelated questions sharing
    "notes" do not match.
    """
    if not entries:
        return entries
    importlib = __import__("importlib")
    # Imported at the call site: `search` is imported by `ai`, so a module
    # level `from tessellate.ai import learning` here is a cycle, and
    # `tests/test_no_import_cycles.py` counts the statement wherever it sits.
    learning = importlib.import_module("tessellate.ai.learning")
    boosts = learning.boosts(session, kind="search")
    if not boosts:
        return entries
    asked = learning._words(query)
    if not asked:
        return entries
    by_id = {entry.id: entry for entry in entries}
    promoted: list[tuple[float, int]] = []
    for (question, entry_id), weight in boosts.items():
        if entry_id not in by_id:
            continue
        words = learning._words(question)
        if not words:
            continue
        shared = len(words & asked)
        if shared and shared * 2 >= len(words):
            promoted.append((weight, entry_id))
    if not promoted:
        return entries
    promoted.sort(reverse=True)
    order = [by_id[entry_id] for _weight, entry_id in promoted]
    seen = {entry.id for entry in order}
    order.extend(entry for entry in entries if entry.id not in seen)
    return order


def _without_private(entries: list[Entry]) -> list[Entry]:
    return [entry for entry in entries if not getattr(entry, "is_private", False)]
