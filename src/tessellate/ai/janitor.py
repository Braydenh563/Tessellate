"""The janitor: files a new thought into a category (LLM prompt #1).

Not a separate AI model, just a prompt to the active chat model, with
embedding-based filing behind it for when there is no model. Order of
attempts:

1. ONE call to the chat model, JSON answer. **This runs first**, which is
   the reverse of how it worked originally: the embedding shortcuts used to
   come first and were so rarely declined that in an established notebook
   the model was almost never asked, and notes were filed by resemblance
   rather than by meaning. Reported as notes landing in the wrong category
   and needing fixing by hand; see `categorise` for the full reasoning.
2. Embedding vs. category centroids: free, and what files notes when no
   chat model is running.
3. Nearest neighbours: the k most similar individual notes vote for their
   own category. Catches what a centroid can't: a category holding more
   than one kind of thing has an average resembling none of them.
4. No AI available and nothing similar → 'Uncategorised' with confidence 0.
   Saving an entry must never fail because the AI is down (plan §4).
"""

from __future__ import annotations

import contextvars
import inspect
import json
import logging
import threading
import time
import weakref
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.ai import filing_certainty, learning, lexical_filing, librarian
from tessellate.ai.embeddings import EmbeddingService, cosine_similarity
from tessellate.ai.model_manager import ModelManager
from tessellate.ai.ollama_client import OllamaClient, OllamaError

# **No `TYPE_CHECKING: import numpy as np` here.** CodeQL flagged it as
# unused and CodeQL was right, which is worth writing down because the import
# looked obviously necessary: the two annotations naming `np.ndarray` are
# *local variable* annotations inside `_best_centroid_match` and `_knn_match`,
# and both of those functions already import numpy for real at their top. The
# local name resolves the annotation for a type checker, so the module-level
# one paid a lint finding for nothing.
#
# The deferral it was part of stands: numpy is imported inside those two
# functions alone, because every other filing path here (the chat-model
# attempt, "no AI available") never touches a vector and must not pay to load
# one.
from tessellate.core import deps
from tessellate.core.database import Category, Entry
from tessellate.core.logbuffer import safe_value
from tessellate.entry.manager import AUTO_FILED, UNCATEGORISED, WORDS_FILED, record_filing

# Above this cosine similarity we trust the embedding match and skip
# the LLM entirely. Below it, the call is worth its cost.
CONFIDENT_MATCH = 0.60

# Nearest-neighbour filing, tried after the centroid and before the model.
# k is small because a personal notebook's categories are small: with twenty
# notes in a category, twenty neighbours is the whole category and the vote
# stops meaning anything.
KNN_NEIGHBOURS = 7
# A neighbour further away than this has no useful opinion about where a note
# belongs; below it, everything looks equally unrelated.
KNN_MIN_SIMILARITY = 0.42
# The winner needs a clear majority of the weighted vote. A split is exactly
# the case where asking the model earns its cost.
KNN_MIN_SHARE = 0.55
# **A short note needs a close relative before meaning may file it** (BACKLOG
# section 8, "ai is cool" filed under Sketches). A one-to-three word note's
# vector is mostly the model's baseline, and the baseline sits above both bars
# above: measured with BAAI/bge-small-en-v1.5 over a hundred-note, ten-category
# notebook (`scratchpad/filing_short_eval.py`), all 20 short notes that belong
# nowhere ("ai is cool", "hello", "remember this") were filed by meaning, and a
# centroid at 0.60 or a neighbour at 0.42 is cleared by anything. What does
# separate them is the nearest filed note: 0.68 to 0.93 (median 0.83) for short
# notes that have a home, 0.55 to 0.75 (median 0.64) for those that do not. At
# 0.72, 59 of the 60 short notes with a home are still filed and 3 of the 20
# without one are. Measured on one embedding model; another backend's scale
# differs, and there a short note falls through to the notebook's own words
# (`lexical_filing`), which is the safe side.
SHORT_NOTE_WORDS = 4
SHORT_NOTE_MIN_NEIGHBOUR = 0.72
#: A note ending in an image and under this many characters is a picture with a
#: caption: no words of its own to file by.
PICTURE_NOTE_CHARS = 160

SYSTEM_PROMPT = (
    "You are the filing assistant of a personal notebook. Given a note, "
    "choose the single best category for it. Prefer one of the existing "
    "categories; invent a short new category name (1-3 words) only if none "
    'fit. Reply with ONLY JSON like {"category": "...", "confidence": 0-100} '
    "where confidence is how sure you are."
)


@dataclass
class CentroidMatch:
    name: str
    similarity: float


@dataclass
class NeighbourMatch:
    name: str
    confidence: int


logger = logging.getLogger("tessellate.janitor")

#: The `method` values `categorise` returns when the *AI* made the choice, as
#: opposed to the user, a parent note, or nothing being available. A note filed
#: by one of these carries `manager.AUTO_FILED`, which is what makes a later
#: move by hand a correction rather than an ordinary edit (Brief 13). A tuple
#: here rather than a check at each call site so a fourth method added later
#: has one place to be listed.
AI_METHODS = ("semantic-match", "semantic-neighbours", "llm")


def is_ai_method(method: str) -> bool:
    return str(method or "") in AI_METHODS


def settled_state(method: str) -> str:
    """`filing_state` once a filing decision lands: `auto` when the AI chose,
    `words` when the notebook's own words did, `done` when nothing decided."""
    if is_ai_method(method):
        return AUTO_FILED
    if method == "words":
        return WORDS_FILED
    return "done"


def _unless_held(content: str, found: tuple[str, int, str] | None) -> tuple[str, int, str] | None:
    """A filer's answer, or None when decision 6 holds it: a sensitive note
    is suggested by the words path below, never filed, until Settings lets
    it (`lexical_filing.holds_sensitive`, INBOX 770)."""
    if found is None:
        return None
    topic = lexical_filing.holds_sensitive(content, found[0])
    if topic is None:
        return found
    logger.info("janitor: '%s' by %s held for the person (%s)", safe_value(found[0], 60), found[2], safe_value(topic, 40))
    return None


def categorise(
    session: Session,
    content: str,
    embeddings: EmbeddingService,
    model_manager: ModelManager,
    ollama: OllamaClient,
    exclude_entry_id: int | None = None,
    on_late_llm=None,  # noqa: ANN001 - has .arrived(category, confidence) and .waiting()
    model_deadline: float | None = None,
) -> tuple[str, int, str]:
    """Decide (category_name, confidence 0-100, method) for a new note.

    `method` tells the UI how the decision was made: 'semantic-match'
    (embedding centroid, no LLM), 'llm' (asked the chat model), or
    'none' (no AI available).

    When RE-categorising an existing note (add-context), pass
    `exclude_entry_id`, otherwise the note's own stored vector anchors
    it to its old category and it can never move.

    `on_late_llm.arrived(category, confidence)`, when given, is called on the model's
    thread if the model answers after `FILING_MODEL_DEADLINE_SECONDS`: what
    this returned was a stand-in, and the model's answer is applied when it
    lands (`_file_entry_in_background`). `model_deadline` is that wait; the
    default is `BLOCKING_MODEL_DEADLINE_SECONDS`, because every other caller
    (re-evaluate, adding context, the agent's own notes, extraction) keeps
    what it gets, and a short wait there would swap the model's answer for
    a weaker guess for good."""
    # **The model decides when there is a model.** This used to run the other
    # way round: a confident centroid match, then nearest neighbours, and the
    # chat model only if both declined, which meant that in an established
    # notebook the AI was almost never consulted at all: there is nearly
    # always *some* category whose vectors sit close to a new note. Reported
    # directly, and the complaint is the right one: "what's the point of
    # having an ai managed notebook if it is filed inaccurately and I need to
    # manually fix it". Vector similarity answers "what does this most
    # resemble", which is not the same question as "where does this belong", 
    # a note about a bug in a work project resembles every other code note
    # more than it resembles the rest of "Work", and gets filed accordingly.
    #
    # The semantic paths below are kept exactly as they were, because they are
    # still the right answer for the case they were really written for: no
    # chat model running, where the alternative is Uncategorised. `_ask_llm`
    # already reports that case as method 'none' (it returns early when
    # `ollama.is_running()` is false, and on any model error or unparseable
    # reply), so "the model had nothing useful to say" and "there is no model"
    # collapse into the same fallback here without a second availability
    # check.
    # The order is a preference, defaulting to the model. Asking the model
    # first buys accuracy and costs a round-trip on every single capture,
    # which on a slow local model is felt immediately, so anyone who would
    # rather have the instant save can have the old order back without giving
    # up the AI entirely (the model still decides everything the vectors
    # decline). Flagged as a real latency change when it shipped; this is the
    # honest fix for it, rather than reverting the accuracy for everyone.
    if not deps.get_config().get_preference("ai_first_filing", True):
        semantic = _unless_held(content, _semantic_category(
            session, content, embeddings, exclude_entry_id=exclude_entry_id
        ))
        if semantic is not None:
            return semantic

    category, confidence, method = _ask_llm(
        session, content, model_manager, ollama, on_late=on_late_llm, deadline=model_deadline,
        exclude_entry_id=exclude_entry_id,
    )
    if method == "timeout":
        # The model is still answering and its answer will be applied when
        # it lands. A stand-in by meaning is only worth it while the
        # embedding model is loaded: a cold load is minutes, which would put
        # "Filing…" back on screen for exactly as long as the wait saved.
        if not embeddings.is_ready():
            return UNCATEGORISED, 0, "none"
        method = "none"
    if method != "none" and _unless_held(content, (category, confidence, method)) is None:
        category, confidence, method = UNCATEGORISED, 0, "none"
    if method != "none":
        # The category can come straight from the chat model, so it is
        # untrusted text on the way to a log line like any other.
        logger.info(
            "janitor: filed by %s -> '%s' (%d%%)",
            method,
            safe_value(category, 60),
            confidence,
        )
        return category, confidence, method

    semantic = _unless_held(content, _semantic_category(
        session, content, embeddings, exclude_entry_id=exclude_entry_id
    ))
    if semantic is not None:
        return semantic

    #: **No model and nothing by meaning: the notebook's own words**
    #: (INBOX 434). Learned from the notes already filed, the moves made by
    #: hand and the categories' names, and abstaining when it is not sure.
    words = lexical_filing.lexical_category(session, content, exclude_entry_id=exclude_entry_id)
    if words is not None:
        logger.info(
            "janitor: filed by your notebook's words -> '%s' (%d%%)",
            safe_value(words.name, 60),
            words.confidence,
        )
        return words.name, words.confidence, "words"

    # Still "filed by <method>", even when the method is 'none'. Reversing the
    # order above briefly replaced this with a differently-worded line, which
    # broke the one thing every filing decision is supposed to leave behind:
    # `test_ai_decisions_are_logged` greps the log console for exactly this
    # prefix, and the Logs tab is where a user finds out *why* a note landed
    # where it did. A decision with no model and no vector match is still a
    # decision, and it is the one most worth being able to see.
    logger.info(
        "janitor: filed by %s -> '%s' (%d%%)",
        method,
        safe_value(category, 60),
        confidence,
    )
    return category, confidence, method


#: Notes this process has already given a second opinion and that the model
#: still could not decide, so the pass moves on to the next ones instead of
#: asking about the same twenty every tick. In memory on purpose: a restart is
#: a fresh chance, and a stuck note costs one prompt, not a loop.
_review_tried: set[int] = set()


def review_words_filed(
    session: Session,
    embeddings: EmbeddingService,
    model_manager: ModelManager,
    ollama: OllamaClient,
    limit: int = 20,
) -> dict[str, int]:
    """The second half of filing by the notebook's own words (BACKLOG 76).

    A note filed while no model was available carries `filing_state ==
    "words"` and is a best guess. Once a model is back, the background pass
    gives each such note a real second opinion: the same `categorise` a new
    note gets, which asks the model first. Where the model files it
    somewhere else the note moves (a `filed` event by `system:filing`, which
    "undo auto-filing" can put back); where it agrees, the note is marked as
    the AI's (`auto`), so a later move by hand reads as a correction, exactly
    as for any other AI filing. Where the model could not decide, the note
    stays `words` and is not asked again this run.

    A note the person filed themselves, a private note (no model reads one)
    and a binned note are never touched. Returns what happened, counted:
    `looked`, `moved`, `confirmed`.
    """
    result = {"looked": 0, "moved": 0, "confirmed": 0}
    if not ollama.is_running():
        return result
    query = (
        select(Entry)
        .where(
            Entry.filing_state == WORDS_FILED,
            Entry.is_deleted == False,  # noqa: E712
            Entry.is_private == False,  # noqa: E712
            Entry.user_filed == False,  # noqa: E712
        )
        .order_by(Entry.id)
    )
    for entry in session.scalars(query):
        if result["looked"] >= limit:
            break
        if entry.id in _review_tried:
            continue
        result["looked"] += 1
        try:
            category, confidence, method = categorise(
                session,
                entry.content,
                embeddings,
                model_manager,
                ollama,
                exclude_entry_id=entry.id,
            )
        except Exception:  # noqa: BLE001 - one note's failure never stops the pass
            logger.warning("janitor: second opinion failed for a words-filed note", exc_info=True)
            _review_tried.add(entry.id)
            continue
        if not is_ai_method(method):
            _review_tried.add(entry.id)
            continue
        moved = record_filing(
            session, entry, category,
            by=filed_by_label(method, confidence, model_manager, embeddings),
        )
        entry.ai_confidence = confidence
        entry.filing_state = settled_state(method)
        result["moved" if moved else "confirmed"] += 1
    session.commit()
    return result


def _semantic_category(
    session: Session,
    content: str,
    embeddings: EmbeddingService,
    exclude_entry_id: int | None = None,
) -> tuple[str, int, str] | None:
    """Filing by vectors alone, or None when neither path is confident.

    One implementation because it is now reached from two directions: as the
    fallback when there is no chat model, and as the *first* attempt when
    `ai_first_filing` is off. Two copies would be two chances for the
    orderings to drift apart.
    """
    # One read of the filed vectors for both passes below, and the categories
    # the person has corrected notes like this one out of (I7's consumer:
    # `learning.centroid_excluded` was claimed built with no caller, ARCH-08).
    labelled = _labelled_vectors(session, embeddings, exclude_entry_id)
    # **Nothing filed by meaning yet, nothing to compare against.** Both
    # matches below embedded the note before finding that out, and on a new
    # notebook (which skips the launch warm-up) that embed is the model's
    # cold load: the first note sat at "Filing…" for as long as it took,
    # over 20 s on a CI runner that downloads the model (E2E first-run,
    # 2026-10-06), to reach the Uncategorised it was always going to get.
    if labelled is None or not labelled.names:
        return None
    if _too_short_to_trust(content, embeddings, labelled):
        logger.info("janitor: too short and too far from any filed note to file by meaning")
        return None
    excluded = learning.excluded_categories(session, content)
    match = _best_centroid_match(
        session, content, embeddings, exclude_entry_id=exclude_entry_id,
        labelled=labelled, excluded=excluded,
    )
    if match is not None and match.similarity >= CONFIDENT_MATCH:
        confidence = min(filing_certainty.CAP, round(match.similarity * 100))
        logger.info(
            "janitor: filed by semantic match -> '%s' (%d%%)",
            safe_value(match.name, 60),
            confidence,
        )
        return match.name, confidence, "semantic-match"

    # A centroid is the average of a whole category, which is a poor
    # description of any category holding more than one kind of thing: "Work"
    # containing both meeting notes and code snippets has a centroid sitting
    # between them, resembling neither. Individual neighbours don't average
    # away like that.
    neighbours = _knn_match(
        session, content, embeddings, exclude_entry_id=exclude_entry_id,
        labelled=labelled, excluded=excluded,
    )
    if neighbours is not None:
        logger.info(
            "janitor: filed by nearest neighbours -> '%s' (%d%%)",
            safe_value(neighbours.name, 60),
            neighbours.confidence,
        )
        return neighbours.name, neighbours.confidence, "semantic-neighbours"
    return None


def _too_short_to_trust(content: str, embeddings: EmbeddingService, labelled: "_Labelled | None") -> bool:
    """True for a note under `SHORT_NOTE_WORDS` words whose nearest filed note
    (a private one never counts, as in `_knn_match`) is under
    `SHORT_NOTE_MIN_NEIGHBOUR` close. False when there is nothing to judge."""
    if labelled is None or not labelled.names or len((content or "").split()) >= SHORT_NOTE_WORDS:
        return False
    vector = embeddings.embed_text(content)
    if vector is None:
        return False
    import numpy as np

    rows = labelled.rows[~labelled.private]
    norm = float(np.linalg.norm(vector))
    if rows.shape[0] == 0 or norm == 0.0 or rows.shape[1] != vector.shape[0]:
        return False
    return float((rows @ (vector.astype("float32") / norm)).max()) < SHORT_NOTE_MIN_NEIGHBOUR


@dataclass
class _Labelled:
    """Every filed note's vector beside its category, for one filing call."""

    names: list[str]
    #: One unit-length row per name (numpy, imported lazily like the rest).
    rows: Any
    #: Which rows are private notes, as a boolean array.
    private: Any


def _labelled_vectors(
    session: Session, embeddings: EmbeddingService, exclude_entry_id: int | None = None
) -> _Labelled | None:
    """The filed notes' vectors, from the search engine's matrix.

    **Not from the table.** This used to select every stored vector as a blob
    and decode each one, on every save, twice (once for the centroids, once
    for the neighbours): 539 ms of a 1,415 ms save at 610 notes (audit
    2026-10-05, ARCH-02), beside a matrix in the search engine that already
    holds every one of them decoded, unit length and kept in step with every
    write. What is read here per save is one small query, each filed note's
    id and category, and the rows are a slice of that matrix.

    Only vectors of the current backend count (the matrix is per backend),
    never Uncategorised (filing must not gravitate into the junk drawer).
    """
    from tessellate.search import engine as search_engine

    import numpy as np

    query = (
        select(Entry.id, Category.name, Entry.is_private)
        .join(Category, Entry.category_id == Category.id)
        .where(
            Entry.is_deleted == False,  # noqa: E712
            Category.name != UNCATEGORISED,
            #: A short caption beside a drawing (the Sketches category) has
            #: no words to compare, yet its vector sat close enough to file
            #: unrelated text under it at 52% (dog3-1026 row 1).
            ~(Entry.content.like("%![%](%)") & (func.length(Entry.content) < PICTURE_NOTE_CHARS)),
        )
    )
    if exclude_entry_id is not None:
        query = query.where(Entry.id != exclude_entry_id)
    filed = session.execute(query).all()
    if not filed:
        return None
    matrix = search_engine.current_matrix(session, embeddings.backend_id())
    if matrix is None:
        return None
    ids = [entry_id for entry_id, _name, _private in filed]
    found = search_engine.rows_for(matrix, ids)
    if found is None:
        return None
    positions, rows = found
    names = [filed[i][1] for i in positions]
    private = np.array([bool(filed[i][2]) for i in positions], dtype=bool)
    return _Labelled(names=names, rows=rows, private=private)


def _best_centroid_match(
    session: Session,
    content: str,
    embeddings: EmbeddingService,
    exclude_entry_id: int | None = None,
    labelled: _Labelled | None = None,
    excluded: set[str] | None = None,
) -> CentroidMatch | None:
    """Compare the note's vector to the average vector (centroid) of each
    existing category. Only vectors from the current backend count.

    `excluded` are the categories the person has corrected notes like this
    one away from (`learning.excluded_categories`, WORLD_CLASS_PLAN I7):
    never the answer, however close."""
    if labelled is None:
        labelled = _labelled_vectors(session, embeddings, exclude_entry_id)
    if labelled is None or not labelled.names:
        return None
    note_vector = embeddings.embed_text(content)
    if note_vector is None:
        return None

    import numpy as np

    if labelled.rows.shape[1] != note_vector.shape[0]:
        return None
    order = sorted(set(labelled.names))
    index = {name: i for i, name in enumerate(order)}
    groups = np.array([index[name] for name in labelled.names])
    # A masked sum per category. Measured at 5,000 vectors: 3 to 12 ms, where
    # `np.add.at` (an unbuffered per-row loop) took 670 ms and a product with
    # a membership matrix 400 to 1,300 ms on a loaded machine (BLAS threads).
    centroids = np.stack(
        [labelled.rows[groups == i].mean(axis=0) for i in range(len(order))]
    )

    best: CentroidMatch | None = None
    for name, centroid in zip(order, centroids):
        if excluded and name in excluded:
            continue
        similarity = cosine_similarity(note_vector, centroid.astype("float32"))
        if best is None or similarity > best.similarity:
            best = CentroidMatch(name=name, similarity=similarity)
    return best


def _knn_match(
    session: Session,
    content: str,
    embeddings: EmbeddingService,
    exclude_entry_id: int | None = None,
    labelled: _Labelled | None = None,
    excluded: set[str] | None = None,
) -> NeighbourMatch | None:
    """Vote among the k most similar individual notes.

    Each neighbour votes for its own category, weighted by how similar it is,
    so one very close note outweighs three vague ones. Returns None unless the
    nearest note is genuinely close *and* the winner takes a clear majority, 
    a split vote is the case where asking the model is worth its cost.
    `excluded` categories have no vote (see `_best_centroid_match`).
    """
    if labelled is None:
        labelled = _labelled_vectors(session, embeddings, exclude_entry_id)
    if labelled is None or not labelled.names:
        return None
    note_vector = embeddings.embed_text(content)
    if note_vector is None:
        return None

    import numpy as np

    # Private notes are excluded from everything the AI touches, and filing
    # is no exception: a category chosen by a private note's neighbours would
    # leak what that note is about.
    keep = ~labelled.private
    if excluded:
        keep &= np.array([name not in excluded for name in labelled.names], dtype=bool)
    if not keep.any():
        return None
    if keep.all():
        # The usual case: nothing to leave out, so no copy of every row.
        names, matrix = labelled.names, labelled.rows
    else:
        names = [name for name, kept in zip(labelled.names, keep) if kept]
        matrix = labelled.rows[keep]
    if matrix.shape[1] != note_vector.shape[0]:
        return None
    # One query vector against N candidates is a single matrix-vector
    # product; the matrix's rows are already unit length.
    query_vec = note_vector.astype("float32")
    query_norm = float(np.linalg.norm(query_vec))
    if query_norm == 0.0:
        return None  # every pair would score 0, same as the old per-row path
    similarities = matrix @ (query_vec / query_norm)

    order = np.argsort(-similarities)[:KNN_NEIGHBOURS]
    scored = [(float(similarities[i]), names[i]) for i in order]

    if not scored or scored[0][0] < KNN_MIN_SIMILARITY:
        return None

    votes: dict[str, float] = {}
    for similarity, name in scored:
        if similarity < KNN_MIN_SIMILARITY:
            continue  # too far away to have an opinion
        votes[name] = votes.get(name, 0.0) + similarity
    if not votes:
        return None

    total = sum(votes.values())
    name, weight = max(votes.items(), key=lambda pair: pair[1])
    share = weight / total
    if share < KNN_MIN_SHARE:
        return None

    # Confidence reflects both how close the neighbours are and how much they
    # agree: a unanimous vote among distant notes shouldn't read as certain.
    confidence = round(min(1.0, scored[0][0]) * share * 100)
    return NeighbourMatch(name=name, confidence=max(1, min(filing_certainty.CAP, confidence)))


def _ask_llm(
    session: Session,
    content: str,
    model_manager: ModelManager,
    ollama: OllamaClient,
    on_late=None,  # noqa: ANN001
    deadline: float | None = None,
    exclude_entry_id: int | None = None,
) -> tuple[str, int, str]:
    if not ollama.is_running():
        return UNCATEGORISED, 0, "none"

    existing = [
        name
        for name in session.scalars(select(Category.name))
        if name != UNCATEGORISED
    ]
    # Built by the librarian, because it now carries more than this function
    # knows about: the corrections the user has already made for these
    # categories (Brief 13). Filing the same kind of note into the same wrong
    # place every week, with the user moving it every week, is the reported
    # failure this answers.
    user_prompt = librarian.filing_prompt(session, content, existing, exclude_entry_id=exclude_entry_id)
    try:
        reply = _chat_within_deadline(
            ollama,
            # Filing is a quick background job, use the utility model so a
            # big slow chat model isn't tied up on every save.
            model_manager.utility_model(),
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            deadline=deadline or BLOCKING_MODEL_DEADLINE_SECONDS,
            on_late=None if on_late is None else (lambda reply: _late_answer(reply, on_late.arrived)),
        )
        # Thinking models reason before answering; only the answer part
        # can contain the JSON we asked for.
        data = _extract_json(reply["content"])
        category = str(data["category"]).strip()
        if not category:
            raise ValueError("empty category")
        raw = _confidence_of(data)
        confidence = filing_certainty.calibrated(
            session, content, category, raw, "llm", exclude_entry_id=exclude_entry_id
        )
        # The model's own number is kept in the log only: it is how a small
        # model phrases itself, not a probability (`filing_certainty`).
        logger.info(
            "janitor: the model said %d%% for '%s'; shown as %d%%",
            raw, safe_value(category, 60), confidence,
        )
        return category, confidence, "llm"
    except ModelStalled:
        #: Not asked at all: nothing is coming, so this is "no model" for it.
        return UNCATEGORISED, 0, "none"
    except TimeoutError:
        # Logged where the deadline passed. "timeout" only when an answer is
        # still coming to someone (`on_late`); `categorise` turns it back
        # into "none" for everyone else.
        if on_late is not None:
            on_late.waiting()
            return UNCATEGORISED, 0, "timeout"
        return UNCATEGORISED, 0, "none"
    except (OllamaError, ValueError, KeyError, TypeError) as exc:
        # A confused model must never block a save, and must never be
        # silent either: this is the line in Settings, Logs that says why
        # a note was filed by meaning rather than by the model.
        logger.warning("janitor: the model couldn't file a note (%s); filing by meaning", safe_value(str(exc), 200))
        return UNCATEGORISED, 0, "none"


#: **Filing waits at most this long for the model** (owner, 0.3.31: a note
#: "needs to take a few seconds, like 5-10 at most", after watching one say
#: "Filing…" for minutes). A cold model load or a reasoning model thinking
#: through a one-word answer can take a minute or more on a laptop; past the
#: deadline the note is filed by meaning instead (`_semantic_category`), the
#: same fallback as no model at all. The call is left to finish on its
#: daemon thread rather than cut off, so the model it loaded is warm for the
#: next note.
FILING_MODEL_DEADLINE_SECONDS = 15.0
#: The owner's range for the Settings field (Settings, Automation: "Wait for
#: Atlas to file a note"): a slow computer can give the model longer, and a
#: late answer is applied anyway (`on_late_llm`), so the wait only decides
#: how long the card says "Filing…" before the stand-in shows.
FILING_WAIT_RANGE = (5, 60)
#: Callers that keep what they get wait this long, roughly the old behaviour
#: (the client's own timeout decided it before the deadline existed).
BLOCKING_MODEL_DEADLINE_SECONDS = 180.0

#: Background filing Settings can see (`/tasks`): the model answering past
#: the wait. Each late answer is a run in the process ledger (INBOX 805) that
#: ends on every way out: the answer lands, it fails, or the wait is given up.
#: The note itself is already filed by meaning by then, so the row says that
#: rather than "Filing a note" (B77: "still says the note is filing but it is
#: finished").
_late: dict[int, tuple[Any, float]] = {}
_late_ids = iter(range(1, 1 << 62))
_activity_lock = threading.Lock()
#: How long a late answer is waited for before its run ends: a runner that
#: never answers must not leave a row running for the rest of the session.
FILING_LATE_GIVE_UP_SECONDS = 600.0
LATE_TITLE = "Waiting for a late filing answer"


def activity_rows() -> list[dict]:
    _give_up_stale_late()
    rows = []
    with _activity_lock:
        late = len(_late)
    if late:
        rows.append(_row(
            "filing-late", LATE_TITLE,
            f"{late} note{'' if late == 1 else 's'} filed by meaning; Atlas's answer refines "
            f"{'it' if late == 1 else 'them'} when it lands",
        ))
    return rows


def late_count() -> int:
    with _activity_lock:
        return len(_late)


def _count_late(model: str, waited: float) -> int:
    from tessellate.core import jobruns

    run = jobruns.Run("filing-late", None, title=LATE_TITLE, origin="app")
    #: The janitor's own row shows it; the run lends that row its lines.
    run.listed = True
    run.start()
    run.say(f"{model or 'The model'} missed the {waited:.0f} s wait: the note is filed by meaning for now.")
    with _activity_lock:
        token = next(_late_ids)
        _late[token] = (run, time.monotonic())
    return token


def _uncount_late(token: int, said: str, outcome: str = "completed") -> None:
    with _activity_lock:
        item = _late.pop(token, None)
    if item is None:
        return
    run, started = item
    run.say(f"{said} ({time.monotonic() - started:.0f} s after the wait).")
    if outcome == "failed":
        run.fail(said)
    elif outcome == "cancelled":
        run.cancel(said)
    else:
        run.result = said
    run.finish()


def _give_up_stale_late(now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    with _activity_lock:
        stale = [token for token, (_, at) in _late.items() if now - at > FILING_LATE_GIVE_UP_SECONDS]
    for token in stale:
        _uncount_late(token, "Stopped waiting: the note stays filed by meaning", "cancelled")


def _row(kind: str, label: str, detail: str) -> dict:
    return {"kind": kind, "name": "", "label": label, "detail": detail,
            "progress": None, "log": [], "queued": False}


def filed_by_label(method: str, confidence: int, model_manager=None, embeddings=None) -> str:  # noqa: ANN001
    """Who decided, for the note's History: the model's name for the model,
    the embedding model's for a match by meaning."""
    try:
        if method == "llm" and model_manager is not None:
            return f"{model_manager.utility_model()}, {confidence}% sure"
        if method in ("semantic-match", "knn") and embeddings is not None:
            return f"meaning ({embeddings.active_model()}), {confidence}% sure"
    except Exception:  # noqa: BLE001 - a label never fails a filing
        logger.debug("janitor: couldn't name the filer", exc_info=True)
    if method == "words":
        return f"your notebook's own words, {confidence}% sure"
    return {"none": "nothing (no model)", "user": "you"}.get(method, method)


def filing_deadline() -> float:
    try:
        value = int(deps.get_config().get_preference("filing_wait_seconds") or 0)
    except (TypeError, ValueError):
        value = 0
    if not value:
        return FILING_MODEL_DEADLINE_SECONDS
    low, high = FILING_WAIT_RANGE
    return float(max(low, min(high, value)))


def _confidence_of(data: dict) -> int:
    return max(0, min(100, int(data.get("confidence", 50))))


def _late_answer(reply: dict, on_late) -> None:  # noqa: ANN001
    """The model's answer after the deadline, parsed as `_ask_llm` parses
    it and handed on; an unusable one is dropped and the stand-in stays."""
    try:
        data = _extract_json(reply["content"])
        category = str(data["category"]).strip()
        if category:
            on_late(category, _confidence_of(data))
    except Exception:  # noqa: BLE001 - a late answer is best effort
        logger.debug("janitor: the model's late filing answer was unusable", exc_info=True)


def warm_filing_model(model_manager: ModelManager, ollama: OllamaClient) -> None:
    """Load the filing model before the first note needs it. A cold load
    is most of a first filing's wait, and past the deadline the first notes
    of every launch would get the stand-in first. Never raises.

    **Only a model that is installed** (the owner, 2026-10-07, "llama3.2
    failed" on a fresh install with other models present): a name nobody
    chose and nothing installed is never sent to the server. A fresh install
    first chooses from what is there, as the launch step does."""
    try:
        if not ollama.is_running():
            return
        from tessellate.ai import model_manager as mm

        installed = ollama.list_models()
        mm.choose_chat_model_if_missing(deps.get_config(), installed)
        model = model_manager.utility_model()
        if not mm.is_installed_name(model, installed):
            logger.info("janitor: not warming the filing model, %s is not installed", safe_value(model, 80))
            return
        _chat_within_deadline(
            ollama,
            model,
            [{"role": "user", "content": "Reply with OK."}],
            deadline=BLOCKING_MODEL_DEADLINE_SECONDS,
        )
        logger.info("janitor: filing model warmed up")
    except Exception as exc:  # noqa: BLE001
        #: A model never pulled (a fresh install's default) is not a fault.
        level = logging.INFO if "not found" in str(exc).lower() else logging.WARNING
        logger.log(level, "janitor: couldn't warm the filing model (%s)", safe_value(str(exc), 200))


class ModelStalled(TimeoutError):
    """The filing model missed the last note's wait, so this one was not asked.

    A subclass of `TimeoutError` so every caller already handles it; the
    difference is that no answer is on its way to this note (nothing was sent),
    so it is filed by meaning for good rather than left waiting for a late one."""


#: How long filing leaves a model alone after it missed the wait. Without it a
#: burst of notes against a model that never answers queued on the model lane
#: and each waited its own deadline in turn (measured, 20 notes: about 300 s
#: for the last one; INBOX 1312). A late answer from the missed call ends it
#: early. Callers that chose to wait for the model (Tidy, the warm-up) are
#: never skipped.
FILING_STALL_COOLDOWN_SECONDS = 60.0
_stalled_until: "weakref.WeakKeyDictionary[object, float]" = weakref.WeakKeyDictionary()


#: How many notes may wait on the model at once when the caller holds a
#: database connection while it waits (an inline `POST /entries` from MCP, a
#: script, an importer or the agent). Twenty at once against a model that never
#: answered filled SQLAlchemy's pool (5 + 10) and `POST /auth/unlock` answered
#: 500 until the model's connection was cut (INBOX 1313). The rest are filed by
#: meaning at once; the page itself defers, so it never queues here.
FILING_MODEL_CONCURRENCY = 4
_model_slots = threading.BoundedSemaphore(FILING_MODEL_CONCURRENCY)


def _stalled(ollama: object) -> bool:
    try:
        return _stalled_until.get(ollama, 0.0) > time.monotonic()
    except TypeError:  # a client that cannot be weakly referenced is never skipped
        return False


def _stall_set(ollama: object, until: float | None) -> None:
    #: Keyed by the client itself, so a test's or a switched provider's fresh
    #: client starts with a clean slate and nothing leaks between them.
    try:
        if until is None:
            _stalled_until.pop(ollama, None)
        else:
            _stalled_until[ollama] = until
    except TypeError:  # a client that cannot be weakly referenced is never skipped
        logger.debug("janitor: no stall memory for %r", type(ollama))


def _chat_within_deadline(
    ollama: OllamaClient,
    model: str,
    messages: list[dict],
    deadline: float = FILING_MODEL_DEADLINE_SECONDS,
    on_late=None,  # noqa: ANN001 - Callable[[dict], None] | None
) -> dict:
    """`ollama.chat` in `quick` mode (thinking off, a short reply), or
    `TimeoutError` once `deadline` seconds pass. `quick` only where the
    provider takes a mode: a filing reply is one line of JSON, and a
    reasoning model left to think first is most of the minute."""
    waits_for_it = deadline >= BLOCKING_MODEL_DEADLINE_SECONDS
    if not waits_for_it and _stalled(ollama):
        raise ModelStalled("filing model stalled")
    slot = False
    if not waits_for_it:
        if not _model_slots.acquire(blocking=False):
            logger.info("janitor: %d notes are already waiting on the model; filing this one by meaning", FILING_MODEL_CONCURRENCY)
            raise ModelStalled("filing model busy")
        slot = True
    try:
        try:
            takes_mode = "mode" in inspect.signature(ollama.chat).parameters
        except (TypeError, ValueError):
            takes_mode = False
        outcome: dict = {}
        lock = threading.Lock()

        def settle(key: str, value: object) -> bool:
            """Record the result; True when the caller had already given up
            (and counted this call as a late answer in Settings)."""
            with lock:
                outcome[key] = value
                return bool(outcome.get("abandoned"))

        from tessellate.core import jobruns

        #: The filing job's run, so the call's lines land there, not in a run
        #: of their own on this thread.
        parent = jobruns.active()

        def run() -> None:
            try:
                with jobruns.bound(parent):
                    if takes_mode:
                        reply = ollama.chat(model, messages, mode="quick")
                    else:
                        reply = ollama.chat(model, messages)
            except Exception as exc:  # noqa: BLE001 - re-raised on the caller's thread
                if settle("error", exc):
                    logger.warning(
                        "janitor: the model's late filing answer failed (%s)", safe_value(str(exc), 200)
                    )
                    _uncount_late(outcome.get("late", 0), "The late answer failed; the note stays filed by meaning", "failed")
                return
            except BaseException:
                _uncount_late(outcome.get("late", 0), "The late answer stopped", "cancelled")
                raise
            if settle("reply", reply):
                _stall_set(ollama, None)  # it answered after all: ask it again
                try:
                    if on_late is not None:
                        on_late(reply)
                except Exception:  # noqa: BLE001
                    logger.warning("janitor: applying a late filing answer failed", exc_info=True)
                    _uncount_late(outcome.get("late", 0), "The late answer came but could not be applied", "failed")
                finally:
                    _uncount_late(outcome.get("late", 0), "The late answer came and was applied")

        #: The request's context too, so a call made for a request is named
        #: for it ("Create entry") rather than "AI request to <model>".
        worker = threading.Thread(target=contextvars.copy_context().run, args=(run,), name="mm-filing-chat", daemon=True)
        worker.start()
        worker.join(deadline)
        with lock:
            if "reply" not in outcome and "error" not in outcome:
                outcome["abandoned"] = True
                outcome["late"] = _count_late(model, deadline)
        if outcome.get("abandoned"):
            logger.info(
                "janitor: the model took over %.0fs to file a note, filing by meaning for now",
                deadline,
            )
            if not waits_for_it:
                _stall_set(ollama, time.monotonic() + FILING_STALL_COOLDOWN_SECONDS)
            raise TimeoutError("filing model deadline")
        _stall_set(ollama, None)
        if "error" in outcome:
            raise outcome["error"]
        return outcome["reply"]
    finally:
        if slot:
            _model_slots.release()


def _extract_json(text: str) -> dict:
    """Small models often wrap JSON in chatter, grab the {...} part."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"no JSON object in reply: {text!r}")
    try:
        parsed = json.loads(text[start : end + 1])
    except RecursionError as exc:
        raise ValueError("reply JSON is nested too deeply") from exc
    if not isinstance(parsed, dict):
        raise ValueError("reply JSON is not an object")
    return parsed
