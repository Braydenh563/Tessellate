"""The ONE active embedding backend (plan §2, resolution 1).

Default: sentence-transformers `BAAI/bge-small-en-v1.5`, no Ollama needed.
Optional: an Ollama embedding model (user's choice).

Both hide behind `embed_text()`, which returns None whenever embeddings
are unavailable. Callers must treat None as "skip semantic features",
never as an error, capture and keyword search keep working (plan §4).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from typing import TYPE_CHECKING

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.ai.model_manager import ModelManager
from tessellate.ai.ollama_client import OllamaClient, OllamaError
from tessellate.core import background
from tessellate.core.database import Attachment, Category, ChunkVector, EmbeddingRecord, Entry
from tessellate.core.logbuffer import safe_value

if TYPE_CHECKING:
    # Only for the annotations below, which `from __future__ import
    # annotations` (above) already turns into strings: this import never
    # runs. The real `import numpy as np` lives inside every function and
    # method that actually calls `np.*`, so importing this module (which
    # `core/deps.py` always does, to wire up the `EmbeddingService` class)
    # never pulls numpy into a process that has not embedded anything yet.
    # Same shape as `_load_st_model`'s own deferred `sentence_transformers`
    # import just below, one step further out.
    import numpy as np

# The built-in embedding model. It was all-MiniLM-L6-v2 and is not any more,
# which is exactly why nothing user-facing may hard-code a name: the Models
# screen went on saying "Built-in (all-MiniLM)" long after this changed, and
# the only way to find out what was really running was to watch it download
# from Hugging Face in the log. Anything that shows the name asks
# `EmbeddingService.active_model()`.
DEFAULT_ST_MODEL = "BAAI/bge-small-en-v1.5"


class EmbeddingCacheBroken(RuntimeError):
    """The model is on disk but will not load; the app stays offline rather
    than fetching it again unasked (`_load_st_model`)."""

logger = logging.getLogger("tessellate.embeddings")

# Warm-up bookkeeping so the UI can tell "still loading" from "failed"
# (a silently failed load used to look like eternal "warming up…").
_warmup = {"running": False, "started": False, "error": False}


#: How long the warm-up waits before touching the model. Two seconds is longer
#: than a page load and a status probe take together on a slow machine, and
#: shorter than anyone takes to write a first note. Tests set it to zero.
WARMUP_DELAY_SECONDS = 2.0

#: **The warm-up also waits for the app to go quiet** (the owner, 2026-09-14:
#: the dashboard's counts "took a while for their stats to load, like the
#: length it took the embedding model to warm up"). The fixed pause above
#: let the first page through, but a person who logs in a few seconds after
#: launch lands on the dashboard exactly as the torch import begins, and
#: that import holds the GIL for seconds: a count query that takes
#: milliseconds waits behind it. So after the pause the thread waits until
#: no request has arrived for `WARMUP_IDLE_SECONDS` (the dashboard's burst
#: is over), and at most `WARMUP_MAX_WAIT_SECONDS` in total, so a window
#: that is never opened still warms. `note_request` is called by the ASGI
#: layer on every request; before the first one the app is idle by
#: definition and the warm-up goes straight on.
WARMUP_IDLE_SECONDS = 2.5
WARMUP_MAX_WAIT_SECONDS = 60.0
_pulse = {"at": 0.0}
_idle_wait = threading.Event()


def note_request() -> None:
    """Called for every HTTP request; the warm-up reads it to stay out of the
    way while a page is loading."""
    _pulse["at"] = time.monotonic()


def _wait_for_idle() -> None:
    deadline = time.monotonic() + WARMUP_MAX_WAIT_SECONDS
    while time.monotonic() < deadline:
        if _pulse["at"] == 0.0:
            return
        quiet = time.monotonic() - _pulse["at"]
        if quiet >= WARMUP_IDLE_SECONDS:
            return
        _idle_wait.wait(min(0.5, max(0.01, WARMUP_IDLE_SECONDS - quiet)))


def _notebook_has_notes(session_factory) -> bool:  # noqa: ANN001
    """Whether there is anything a warm model could be for.

    Raw SQL rather than the `Entry` model: this module is a leaf under the
    dependency container, and importing `core.database` from it is the cycle
    `tests/test_no_import_cycles.py` exists to refuse. An unreadable database
    answers True, because the cost of a wrong True is one model load and the
    cost of a wrong False is a cold first search."""
    try:
        from sqlalchemy import text

        session = session_factory()
        try:
            return session.execute(text("SELECT 1 FROM entries LIMIT 1")).first() is not None
        finally:
            session.close()
    except Exception:  # noqa: BLE001  # see the docstring
        return True


def start_warmup(service: "EmbeddingService", session_factory=None) -> None:  # noqa: ANN001
    """Load the embedding model in a background thread at startup, so the
    user's first save doesn't stall. Idempotent per process.

    The session factory is passed in rather than looked up. This module is
    imported by the dependency container, so reaching back into it would make
    the import cycle real instead of merely deferred.
    """
    if _warmup["started"]:
        return
    _warmup["started"] = True

    def run() -> None:
        #: **The first page load goes first.** Importing torch is seconds of
        #: C-extension initialisation that holds the GIL, and this thread used
        #: to start it the instant `create_app` returned: on a two-core CI
        #: runner the event loop stalled long enough that the shell's
        #: `/auth/status` probe (8s) timed out and the lock screen never
        #: appeared, which is exactly what the E2E smoke suite failed on
        #: (run 34734999382: "locator resolved to hidden" for 15 seconds after
        #: "Application startup complete"). It did not reproduce anywhere
        #: sentence-transformers was not installed, which is every sandbox
        #: that reproduced it, so the fix is stated here rather than measured
        #: here. A short pause lets the index and the status probe through
        #: before the heavy import begins; the model is still warm long before
        #: anyone has typed a note.
        time.sleep(WARMUP_DELAY_SECONDS)
        _wait_for_idle()
        #: **And an empty notebook warms nothing.** A first run has no note to
        #: search and no note to file, so loading a model for it costs the
        #: slowest part of startup for nothing; the first save loads it, which
        #: is the moment it is first needed. This is also what keeps a fresh
        #: CI data dir from paying the torch import at all.
        if session_factory is not None and not _notebook_has_notes(session_factory):
            logging.getLogger("tessellate.embeddings").info(
                "embedding warm-up skipped: the notebook is empty"
            )
            return
        _warmup["running"] = True
        _warmup["error"] = False
        started = time.monotonic()
        try:
            service.embed_text("warm up")
        except Exception:
            # The flag drives the "search is keyword-only" notice; the reason
            # is what somebody reading the log needs, and it was dropped.
            logger.warning("embedding warm-up failed", exc_info=True)
            _warmup["error"] = True
        finally:
            _warmup["running"] = False
            if _warmup["error"]:
                from tessellate.core import taskhistory
                taskhistory.record(
                    "embeddings",
                    "Loading embedding model",
                    "failed",
                    "Failed to load",
                    duration_ms=(time.monotonic() - started) * 1000,
                )
        # Now that the model is up, catch any notes that missed out.
        if session_factory is not None and not _warmup["error"]:
            backfill_missing(service, session_factory)
            # ...and build the retrieval engine's vector matrix once, here,
            # on the thread that already waited for the model rather than on
            # whichever request happens to be first (Brief 11). Before the
            # model is ready there is no backend id to build against, which
            # is why this is at the end of the warm-up and not in
            # `create_app`. A failure is logged and dropped: a cold matrix
            # means "no similarity yet", never a failed startup.
            try:
                # `importlib`, not an `import` statement: this module is a
                # leaf that `search/engine.py` sits on top of (through
                # `search_manager`), so naming the engine here closes
                # `ai.embeddings -> search.engine -> search.search_manager ->
                # ai.embeddings`. `tests/test_no_import_cycles.py` counts the
                # statement wherever it sits, because CodeQL does.
                import importlib

                search_engine = importlib.import_module("tessellate.search.engine")

                session = session_factory()
                try:
                    held = search_engine.warm_vectors(session)
                finally:
                    session.close()
                logging.getLogger("tessellate.embeddings").info(
                    "retrieval matrix warm with %d vector(s)", held
                )
            except Exception:  # noqa: BLE001  # see above
                logging.getLogger("tessellate.embeddings").warning(
                    "could not warm the retrieval matrix", exc_info=True
                )

    # **Not on `core/jobs.py`'s pool, deliberately** (WORLD_CLASS_PLAN A3).
    # The pool bounds the jobs that *multiply*: one per upload, three per
    # picture, so a folder of 200 is 600 threads. This is one thread per
    # process, it runs once at startup, and putting it on the shared queue
    # would make the first search of a session wait behind whatever OCR a
    # bulk import had already queued. One is not a concurrency problem.
    background.start("embedding-warmup", run)


# How many gaps to close per startup. Bounded so a huge notebook doesn't spend
# minutes embedding on every launch; the next start picks up where this stopped.
BACKFILL_LIMIT = 200

#: How many notes one batched encode takes when a whole notebook is being
#: embedded (the startup backfill and the Settings re-index). `embed_many`
#: hands the list to sentence-transformers as one `encode` call, which is
#: markedly cheaper per note than the same notes one at a time; the ceiling
#: keeps a long note's tokens from making one batch spike memory and keeps the
#: re-index's cancel check responsive (it looks between batches).
EMBED_BATCH = 16

# Enough to cover the repeated embeds within a single save, with headroom.
_EMBED_CACHE_MAX = 32

#: **One torch thread for a note-sized encode** (INBOX 434: background filing
#: took 1.2 to 4 seconds, nearly all of it this one call). `encode()` of one
#: short note is a few tiny matrix products, and torch's default intra-op pool
#: (one thread per core) pays barrier waits that dwarf the arithmetic the
#: moment any other process wants a core. Measured here, 70-character note,
#: median per encode: 4 threads idle 39 ms; 4 threads on a busy machine
#: 2,192 ms; 1 thread busy 79 ms; 2 threads busy 119 ms. A desktop app always
#: shares its machine (the window, the browser, an indexer), so the pool's
#: best case saves tens of milliseconds and its worst costs seconds.
#: `TESSELLATE_EMBED_THREADS` raises it for a machine that is known to be idle.
EMBED_THREADS = 1


def embed_threads() -> int:
    """The thread count one encode runs at: `EMBED_THREADS`, or the
    environment's whole number when it names one."""
    raw = os.environ.get("TESSELLATE_EMBED_THREADS", "").strip()
    try:
        return max(1, int(raw)) if raw else EMBED_THREADS
    except ValueError:
        return EMBED_THREADS


def _limit_torch_threads() -> None:
    """Put the calling thread's torch pool at `embed_threads()` before an
    encode. Set in the encoding thread itself, because an OpenMP build keeps
    the count per thread and a new pool thread starts at the default; a call
    that finds the count already right does nothing, so this costs one
    getter per note. Never an error: no torch, or one without the setter,
    only means the default pool."""
    try:
        import torch

        wanted = embed_threads()
        if torch.get_num_threads() != wanted:
            torch.set_num_threads(wanted)
    except Exception:  # noqa: BLE001  # a thread limit is an optimisation
        logger.debug("couldn't limit torch's threads for an encode", exc_info=True)


def backfill_missing(
    service: "EmbeddingService",
    session_factory,  # noqa: ANN001  # a callable returning a Session
    limit: int = BACKFILL_LIMIT,
) -> int:
    """Embed notes that have no vector, and report how many were fixed.

    Notes saved while the model was still warming up got no embedding, and
    nothing ever went back for them, so they stayed invisible to semantic
    search permanently, while looking perfectly normal in the list. The gap
    closes itself on the next start instead.

    Private notes are skipped, deliberately: store_for_entry refuses them, and
    a vector would leak what the note is about.
    """
    if not service.is_ready():
        return 0
    from tessellate.core import jobruns

    with jobruns.job_run("embeddings-backfill") as run:
        fixed = _backfill_missing(service, session_factory, limit, run)
    return fixed


def _backfill_missing(service, session_factory, limit: int, run) -> int:  # noqa: ANN001
    from sqlalchemy import select

    from tessellate.core import jobruns
    from tessellate.core.database import EmbeddingRecord, Entry

    fixed = 0
    try:
        session = session_factory()
    except Exception:  # noqa: BLE001  # startup helper, never fatal
        run.fail("Could not open the database.")
        return 0
    try:
        missing = session.scalars(
            select(Entry)
            .outerjoin(EmbeddingRecord, EmbeddingRecord.entry_id == Entry.id)
            .where(
                Entry.is_deleted == False,  # noqa: E712
                Entry.is_private == False,  # noqa: E712
                EmbeddingRecord.id.is_(None),
            )
            .limit(limit)
        ).all()
        run.say(
            f"{len(missing)} note{'' if len(missing) == 1 else 's'} without a vector."
            if missing
            else "Every note already has a vector."
        )
        stopped = False
        for start in range(0, len(missing), EMBED_BATCH):
            #: Stop (Settings, Background jobs) is honoured between batches, so
            #: a long backfill is no longer one call with nothing to stop at.
            if "embeddings-backfill" in jobruns.stop_asked:
                stopped = True
                break
            fixed += service.store_for_entries(session, missing[start : start + EMBED_BATCH])
            run.step(min(start + EMBED_BATCH, len(missing)), len(missing), "Embedding notes")
            run.say(f"Embedded {min(start + EMBED_BATCH, len(missing))} of {len(missing)} notes.")
        chunked = 0
        if not stopped:
            run.say("Checking long notes for paragraph vectors.")
            chunked = _backfill_chunks(service, session, limit, run)
        if fixed:
            session.commit()
            logging.getLogger("tessellate.embeddings").info(
                "backfilled %d note(s) that had no embedding", fixed
            )
        if stopped:
            run.cancel(f"stopped after {fixed} of {len(missing)} notes; the rest are done at the next start")
            return fixed
        run.result = (
            f"embedded {fixed} note{'' if fixed == 1 else 's'} that had no vector"
            if fixed
            else "every note already had a vector"
        )
        if chunked:
            run.result += f"; {chunked} long note{'' if chunked == 1 else 's'} got paragraph vectors"
    except Exception:  # noqa: BLE001  # a failed backfill must not stop startup
        session.rollback()
        #: A sentence, not `str(exc)` (ledger 1547); the traceback goes to the log.
        logger.warning("embedding backfill failed", exc_info=True)
        run.fail("Couldn't finish adding the missing search vectors. The log has the reason.")
    finally:
        session.close()
        jobruns.stop_asked.discard("embeddings-backfill")
    return fixed


#: A note shorter than this is one paragraph however it is laid out, so the
#: paragraph backfill does not look at it.
CHUNK_BACKFILL_MIN_CHARS = 400


def _backfill_chunks(service, session: Session, limit: int, run=None) -> int:  # noqa: ANN001
    """Paragraph vectors for long notes embedded before row 6 existed.

    A note vector of this backend and no paragraph rows, content long enough
    and with a blank line in it: the note vector is kept and only its
    paragraphs are embedded. A note that turns out to be one paragraph after
    all stores nothing and is looked at again next launch, which costs a
    split of its text and no embed.
    """
    backend = service.backend_id()
    candidates = session.execute(
        select(Entry, EmbeddingRecord)
        .join(EmbeddingRecord, EmbeddingRecord.entry_id == Entry.id)
        .outerjoin(ChunkVector, ChunkVector.entry_id == Entry.id)
        .where(
            Entry.is_deleted == False,  # noqa: E712
            Entry.is_private == False,  # noqa: E712
            EmbeddingRecord.model_version == backend,
            ChunkVector.id.is_(None),
            func.length(Entry.content) >= CHUNK_BACKFILL_MIN_CHARS,
            Entry.content.contains("\n\n"),
        )
        .limit(limit)
    ).all()
    done = 0
    for index, (entry, record) in enumerate(candidates, 1):
        if service._store_chunks(session, entry, record):
            done += 1
        if run is not None:
            run.step(index, len(candidates), "Paragraph vectors")
    if done:
        session.commit()
    return done


def warmup_running() -> bool:
    return _warmup["running"]


def warmup_failed() -> bool:
    return _warmup["error"]


def clean_orphaned_vectors(session_factory) -> int:  # noqa: ANN001
    """Delete vectors whose note is gone, and say how many went.

    Nothing prunes the embeddings table when an entry is hard-deleted, the
    recycle bin's purge removes the row and leaves the vector behind, so it
    grows forever and every semantic search scans rows that can never match.

    This function is called by the background pass, and for a while it was
    *only* called: it did not exist, and the call sat inside a `try/except`
    broad enough to swallow the `AttributeError`, so the orphan cleanup was
    reported as running and silently never ran. Hence the return value and the
    log line: a maintenance job that cannot say what it did is a maintenance
    job nobody can tell is broken.

    `session_factory` is required rather than defaulted from `deps`. Defaulting
    it meant this module importing `core.deps`, which imports `EmbeddingService`
    from this module: a cycle CodeQL flagged, and a layering inversion besides:
    `ai/` sits below the dependency container, not above it. Every caller
    already holds a factory, so the parameter costs them nothing.
    """
    with session_factory() as session:
        orphans = list(
            session.scalars(
                select(EmbeddingRecord).where(
                    EmbeddingRecord.entry_id.notin_(select(Entry.id))
                )
            )
        )
        for row in orphans:
            session.delete(row)
        # Paragraph vectors cut beside a note vector that no longer exists
        # (the note was purged, made private, or re-embedded by a bulk
        # statement): inert already, since a chunk only counts beside its own
        # note vector, and deleted here so the table does not keep them.
        stale_chunks = session.execute(
            sa_delete(ChunkVector).where(ChunkVector.embedding_id.notin_(select(EmbeddingRecord.id)))
        ).rowcount or 0
        if orphans or stale_chunks:
            session.commit()

    if orphans:
        logger.info("removed %d embedding(s) whose note no longer exists", len(orphans))
    return len(orphans)


def embedding_text(session: Session, entry: Entry) -> str:
    """What actually gets embedded for a note: its own words, plus what the
    pictures in it say.

    Asked for directly: "allow captions if they accompany images of sketches
    to be read by the ai if they appear in semantic searches." A note that is
    a drawing and one line of caption used to embed as that one line, the
    vision model's description of the drawing was on the `MediaUpload` row and
    the vector knew nothing about it, so "the diagram of the pond" matched
    nothing at all.

    The note is never modified: this is derived on the way past, which also
    means a picture captioned later improves search on the next re-index
    rather than needing the note rewritten. Falls back to the note's own text
    whenever there is nothing to add, so the vector for a plain note is
    exactly what it was before this existed.
    """
    import importlib

    media_process = importlib.import_module("tessellate.core.media_process")

    parts: list[str] = [entry.content]

    # **How the note is filed is part of what it is about.** Reported
    # directly: "I have a whole category called hobbies but basically none
    # came up in the semantic search." Nothing was broken: the word
    # "hobbies" appears in the *category*, and a category has never been part
    # of what gets embedded, so a note about the gym filed under Hobbies had
    # no more relation to the query "hobbies" than to any other word the note
    # does not contain. Naming the category and the tags in the embedded text
    # is what makes "what do I have under hobbies" a question the vectors can
    # actually answer, and it costs one short line per note.
    # Queried by id rather than read off a relationship: this app's models
    # declare foreign keys but no ORM `relationship()` anywhere, so
    # `entry.category` is not an attribute that exists, a `getattr` version
    # of this would have returned None forever and quietly indexed nothing.
    try:
        labels: list[str] = []
        if entry.category_id is not None:
            name = session.scalar(
                select(Category.name).where(Category.id == entry.category_id)
            )
            if name and str(name).lower() not in {"uncategorised", "uncategorized"}:
                labels.append(str(name))
        raw_tags = json.loads(entry.tags or "[]")
        labels += [str(tag) for tag in raw_tags if str(tag).strip()][:12]
        if labels:
            parts.append("Filed under: " + ", ".join(labels))
    except Exception:  # noqa: BLE001  # enrichment must never block an embedding
        logger.debug("no category or tags for entry %s", entry.id, exc_info=True)

    # What this note's own attached files say. The same reasoning as the
    # media captions below, for the half of the app that stores files as
    # `Attachment` rows: a scanned lecture PDF attached to a two-word note
    # was, to the vectors, a two-word note. Now the caption a vision model
    # wrote and the text either extractor read are searchable with it.
    try:
        attachments = session.scalars(
            select(Attachment).where(Attachment.entry_id == entry.id)
        ).all()
        for attachment in attachments:
            found = [
                getattr(attachment, "caption", None),
                getattr(attachment, "ocr_text", None) or getattr(attachment, "vision_ocr_text", None),
            ]
            text = " ".join(str(item).strip() for item in found if item)
            if text:
                parts.append(f"{attachment.filename}: {text[:2000]}")
    except Exception:  # noqa: BLE001  # an attachment must never block an embedding
        logger.debug("no attachment text for entry %s", entry.id, exc_info=True)

    try:
        extra = media_process.media_text_for(session, entry.content)
        if extra:
            parts.append(extra)
    except Exception:  # noqa: BLE001  # enrichment must never block an embedding
        logger.debug("no media text for entry %s", entry.id, exc_info=True)
    return "\n".join(parts)


# --- paragraph chunks (WORLD_CLASS_PLAN §14 item 3, row 6): `ai/chunks.py` ---

from tessellate.ai.chunks import paragraph_chunks  # noqa: E402  # one split for vectors and citations


def chunk_text(content: str, start: int, end: int) -> str:
    """What one paragraph embeds as: the note's first line, then the paragraph.

    A paragraph halfway down a note called "Boiler" may never say "boiler";
    the title is what it is about. The first chunk already starts with it.
    """
    body = content[start:end]
    first_line = content.lstrip().split("\n", 1)[0].strip().lstrip("#").strip()
    if start == 0 or not first_line or body.startswith(first_line):
        return body
    return f"{first_line[:120]}\n{body}"


def _digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8"), usedforsecurity=False).hexdigest()[:32]


def vector_to_bytes(vector: np.ndarray) -> bytes:
    """Raw float32 bytes: never pickle (plan §4)."""
    import numpy as np

    return np.asarray(vector, dtype="float32").tobytes()


def bytes_to_vector(blob: bytes) -> np.ndarray:
    import numpy as np

    return np.frombuffer(blob, dtype="float32")


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """1.0 = same direction, 0.0 = unrelated. Zero vectors score 0."""
    import numpy as np

    norms = float(np.linalg.norm(a)) * float(np.linalg.norm(b))
    if norms == 0.0:
        return 0.0
    return float(np.dot(a, b) / norms)


#: How many notes' vectors to compare against the rest at a time.
#:
#: "All pairs at once" is the obvious way to write this and the reason it is
#: not written that way: `vectors @ vectors.T` allocates an N×N float matrix,
#: and `np.triu` of it allocates a second. At 5,000 notes that is 400 MB for a
#: graph refresh, at 10,000 it is 1.6 GB, and the notebook this app is built
#: for is explicitly allowed to get that big (ANALYSIS.md §34 scale-tests it).
#: A row block at a time is the same arithmetic with a ceiling on the memory.
SIMILARITY_BLOCK = 512


def similar_pairs(
    vectors: dict[int, np.ndarray], threshold: float, per_node: int | None = None
) -> list[tuple[int, int, float]]:
    """Every pair of ids scoring at or above `threshold`, best first.

    `per_node` keeps only each id's `per_node` best partners (a pair stays if
    it is in either end's), found block by block, so the result is at most
    n * per_node pairs rather than up to n^2 / 2 (GRAPH_PLAN 518 (4)).

    Vectors of a width other than the majority's are dropped rather than
    stacked: a notebook part-way through an embedding-model change holds both
    widths at once, and `np.stack` on a ragged list raises, which took out the
    graph and the link suggestions entirely rather than degrading them.
    """
    if not vectors:
        return []

    import numpy as np

    by_width: dict[int, list[int]] = {}
    for node_id, vector in vectors.items():
        by_width.setdefault(vector.shape[0], []).append(node_id)
    # The width most of the notebook is on. Everything else is mid-reindex.
    widest = max(by_width, key=lambda w: len(by_width[w]))
    ids = sorted(by_width[widest])
    if len(ids) < 2:
        return []

    matrix = np.stack([vectors[node_id] for node_id in ids]).astype("float32")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    matrix /= np.where(norms == 0, 1.0, norms)

    found: list[tuple[int, int, float]] = []
    if per_node:
        keep = min(per_node, len(ids) - 1)
        best: dict[tuple[int, int], float] = {}
        for start in range(0, len(ids), SIMILARITY_BLOCK):
            scores = matrix[start : start + SIMILARITY_BLOCK] @ matrix.T
            rows = np.arange(scores.shape[0])
            scores[rows, rows + start] = -np.inf
            top = np.argpartition(-scores, keep - 1, axis=1)[:, :keep]
            for row, cols in enumerate(top):
                for col in cols:
                    score = float(scores[row, col])
                    if score >= threshold:
                        left, right = sorted((start + row, int(col)))
                        best[(left, right)] = score
        found = [(ids[a], ids[b], score) for (a, b), score in best.items()]
        found.sort(key=lambda pair: pair[2], reverse=True)
        return found
    for start in range(0, len(ids), SIMILARITY_BLOCK):
        block = matrix[start : start + SIMILARITY_BLOCK]
        scores = block @ matrix.T
        # Keep each pair once: only look to the right of the diagonal.
        rows, cols = np.where(scores >= threshold)
        for row, col in zip(rows, cols):
            left = start + int(row)
            right = int(col)
            if right <= left:
                continue
            found.append((ids[left], ids[right], float(scores[row, col])))

    found.sort(key=lambda pair: pair[2], reverse=True)
    return found


#: How many times a model whose files would not load is fetched again before
#: the person is asked to reinstall it themselves.
REPAIR_ATTEMPTS = 2


def _fetch_model_as_a_task(loader, repo: str, title: str):  # noqa: ANN001, ANN202
    """`loader(repo)` online, as a run the Activity list shows by `title`, so a
    download or a fix is something a person can see happening (INBOX 1289)."""
    from tessellate.core import jobruns

    with jobruns.job_run("embedding-fix", title=title) as run:
        run.say(f"{title}: fetching {repo}.")
        return loader(repo)


class EmbeddingService:
    # After a failed model load, wait this long before trying again, 
    # each attempt can hit the network and stall a save otherwise.
    RETRY_AFTER_SECONDS = 300
    #: How many times a process fixes an incomplete model cache by itself.
    REPAIR_ATTEMPTS = 2

    def __init__(self, model_manager: ModelManager, ollama_client: OllamaClient) -> None:
        self._models = model_manager
        self._ollama = ollama_client
        self._st_model = None  # loaded lazily; dropped after an idle hour (`unload_if_idle`)
        #: When the model last encoded something, and whether it ever loaded:
        #: an unloaded model is still "ready" (a reload from the disk cache,
        #: seconds, not a first-time download), so the status pill and the
        #: keyword-only notice do not flip on an idle hour.
        self._last_used = 0.0
        self._was_loaded = False
        self._load_failed_at: float | None = None
        # Why the last embed failed, for the Models screen, None = fine.
        self.last_error: str | None = None
        # Guards _maybe_auto_install_missing_package: try the self-heal at
        # most once per process, not once per failed embed.
        self._auto_install_attempted = False
        # text -> vector, bounded and FIFO. See embed_text for why.
        self._embed_cache: dict[str, np.ndarray] = {}
        # Written from request threads and the re-index thread at once. A
        # dict survives concurrent get/set, but the eviction iterates it
        # (`next(iter(...))`) while another thread may insert, which raises
        # "dictionary changed size during iteration" inside a save, at
        # random, under load. One lock, held for microseconds; the embedding
        # call itself runs outside it.
        self._cache_lock = threading.Lock()

    def use_client(self, ollama_client: OllamaClient) -> None:
        """Talk to a new chat client (Settings switched backend), keeping a
        loaded sentence-transformers model. Embeddings served by the chat
        backend are forgotten and retried at once: the same text may now map
        to a different server's vector, and a failure seen on the old one
        says nothing about the new."""
        self._ollama = ollama_client
        if self._models is not None and self._models.embedding_backend() == "ollama":
            self.clear_embed_cache()
            self.reset_failure_state()

    def clear_embed_cache(self) -> None:
        """Drop cached vectors: used when the embedding backend changes,
        since the same text then maps to a different vector."""
        with self._cache_lock:
            self._embed_cache.clear()

    def reset_failure_state(self) -> None:
        """Forget a cached load/embed failure so the very next attempt
        retries immediately, and clear the stale error the Models screen
        shows. Called when the user switches search engine, they've
        usually just fixed whatever was wrong (e.g. a broken torch), and
        shouldn't have to wait out the 5-minute retry cooldown or stare at
        an out-of-date banner."""
        self.last_error = None
        self._load_failed_at = None

    def active_model(self) -> str:
        """The model actually doing the work right now, whichever backend."""
        if self._models.embedding_backend() == "ollama":
            return self._models.embedding_model()
        return self.st_repo()

    def st_repo(self) -> str:
        """The built-in backend's model (INBOX 700: a choice now, from the
        allowlist in `core/embedmodels.py`; the default until one is made)."""
        chosen = getattr(getattr(self, "_models", None), "embedding_st_model", None)
        return chosen() if chosen is not None else DEFAULT_ST_MODEL

    def pinned(self, backend: str, model: str) -> "EmbeddingService":
        """A service bound to `backend` and `model` whatever the settings say:
        the one a model switch embeds the new set with while this one, on the
        saved settings, keeps answering searches (`core/embedswitch.py`)."""
        return EmbeddingService(_PinnedModels(backend, model), self._ollama)

    def adopt(self, other: "EmbeddingService") -> None:
        """Take over `other`'s loaded model once the switch has made its
        settings the saved ones: the new model is already in memory, and
        loading it again would cost the first search after the switch."""
        if other._st_model is not None:
            self._st_model = other._st_model
        self.clear_embed_cache()
        self.reset_failure_state()

    def backend_id(self) -> str:
        """Stored as model_version next to every vector, so a backend
        switch is detectable: vectors from different models live in
        different spaces and must never be compared (plan §6.5)."""
        if self._models.embedding_backend() == "ollama":
            return f"ollama:{self._models.embedding_model()}"
        return f"sentence-transformers:{self.st_repo()}"

    def loads_cold(self) -> bool:
        """Whether the next embed would first load the local model: torch's
        import and the weights, measured 21.75 s cold here (INBOX, the
        owner's trace: 27.06 s before the first step). A search does not
        wait for that; it reads by words while the model loads behind it."""
        models = getattr(self, "_models", None)
        return (
            models is not None
            and type(self).embed_text is EmbeddingService.embed_text
            and models.embedding_backend() != "ollama"
            and getattr(self, "_st_model", None) is None
            and getattr(self, "_load_failed_at", None) is None
        )

    def is_ready(self) -> bool:
        """Can we embed right now without a long first-time load?
        Drives the UI's status pill."""
        if self._models.embedding_backend() == "ollama":
            return self._ollama.is_running()
        return self._st_model is not None or self._was_loaded

    #: Idle time after which the model is dropped, in seconds (decision 62; the
    #: `embedder_idle_unload_minutes` preference, 0 turns it off). Torch holds
    #: about 430 MB resident once loaded (WORLD_CLASS_PLAN 19.1).
    IDLE_UNLOAD_SECONDS = 3600
    _idle_watch_started = False

    def unload_if_idle(self, now: float | None = None) -> bool:
        """Drop the sentence-transformers model when nothing has used it for the
        idle window. True when it was dropped. The next embed loads it again."""
        if self._st_model is None:
            return False
        try:
            minutes = float(self._models._config.get_preference("embedder_idle_unload_minutes", 60))
        except (TypeError, ValueError, AttributeError):
            minutes = 60.0
        if minutes <= 0:
            return False
        moment = time.monotonic() if now is None else now
        if moment - self._last_used < minutes * 60:
            return False
        self._st_model = None
        import gc

        gc.collect()
        logger.info("embedding model unloaded after %.0f minutes idle", minutes)
        return True

    def _watch_idle(self) -> None:
        """One registered thread per loaded model: checks every five minutes and
        ends when it has unloaded (the next load starts a new one)."""
        from tessellate.core import background

        if self._idle_watch_started:
            return
        self._idle_watch_started = True
        stop = threading.Event()

        def run() -> None:
            try:
                while not stop.wait(300):
                    if self.unload_if_idle() or self._st_model is None:
                        return
            finally:
                self._idle_watch_started = False

        background.start("embedder-idle-watch", run, stop=stop.set)

    def embed_text(self, text: str) -> np.ndarray | None:
        """Vector for one text, or None if the backend is unavailable.

        Recent results are cached by exact text. Saving a note embeds it twice
        within milliseconds: once to store the vector, once by the
        near-duplicate check that runs straight afterwards, and embedding is
        the slowest part of a save. Keying on the exact string means a cached
        vector can never be stale: different text is simply a different key.
        """
        with self._cache_lock:
            cached = self._embed_cache.get(text)
        if cached is not None:
            return cached
        vector = self._embed_uncached(text)
        if vector is not None:
            # Small and FIFO: this exists to collapse duplicate work inside one
            # request, not to be a general-purpose store.
            with self._cache_lock:
                if len(self._embed_cache) >= _EMBED_CACHE_MAX:
                    self._embed_cache.pop(next(iter(self._embed_cache)))
                self._embed_cache[text] = vector
        return vector

    def _embed_uncached(self, text: str) -> np.ndarray | None:
        if self._models.embedding_backend() == "ollama":
            import numpy as np

            try:
                vector = self._ollama.embed(self._models.embedding_model(), text)
                self.last_error = None
                return np.asarray(vector, dtype="float32")
            except OllamaError as exc:
                self.last_error = str(exc)
                return None
        return self._embed_with_sentence_transformers(text)

    def _load_st_model(self):  # noqa: ANN202
        """Load the sentence-transformers model, preferring what's already
        on disk over a live hub round-trip.

        This used to try online first, always, but `SentenceTransformer()`
        with no `local_files_only` still asks the hub whether a cached
        model is current before using it, and that's a real HTTP call this
        offline-first app has no business making on every note save. On a
        network that's merely slow or rate-limited (not simply down), that
        call doesn't fail fast: `huggingface_hub` retries with backoff for
        the better part of a minute before this code ever got a chance to
        fall back to the cache. Trying the cache first sidesteps the
        problem entirely for the common case (already downloaded once);
        the online attempt below is now purely for the genuine first-ever
        download."""
        #: **Online only for a first download** (INBOX 439, the owner's
        #: privacy panel: "huggingface.co, Embedding model, connected 1 time"
        #: with the model already on the machine). A cache lookup that failed
        #: used to fall straight through to an online load, logged at debug,
        #: so a model on disk whose files would not load (a newer library
        #: wanting a file the old download lacks, an interrupted download)
        #: went to the internet on every launch with nothing saying why. Now:
        #: never downloaded, it downloads, said in the log; on disk and not
        #: loading, it stays offline, says why, and Settings' Reinstall is the
        #: one way back online, a choice the person makes.
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        from sentence_transformers import SentenceTransformer

        repo = self.st_repo()
        try:
            model = SentenceTransformer(repo, local_files_only=True)
            logger.info("embedding model loaded from local cache")
            return model
        except Exception as exc:  # noqa: BLE001  # not cached, stale or corrupt
            #: **The off-switch for the one-off download** (docs/PRIVACY.md:
            #: `TESSELLATE_NO_AUTO_INSTALL` stops the search model's first
            #: fetch). Set, a note's first save on a machine without the model
            #: made the Hub call anyway, so a suite run on a machine with no
            #: cache (CI) reached huggingface.co from the first note any test
            #: saved. Search uses keywords until the model is installed.
            if os.environ.get("TESSELLATE_NO_AUTO_INSTALL"):
                raise EmbeddingCacheBroken(
                    "Search by meaning is not installed here and automatic downloads are switched off; search uses keywords."
                ) from exc
            from tessellate.core import embedmodels

            health = embedmodels.cache_health(repo)
            if health["state"] == "incomplete":
                self._mend_incomplete_cache(repo, health, exc)
            if embedmodels.is_downloaded(repo):
                #: **Repaired, not handed over** (the owner, 2026-10-07: "things
                #: should be auto fixed for the user"; a fresh install had a
                #: folder with no files). An online fetch fills what is
                #: missing, as a visible task ("Fixing search by meaning"),
                #: up to twice a process, unless the person switched
                #: automatic installs off (`semantic_auto_install`); search
                #: runs on keywords meanwhile, and the person is told to
                #: reinstall only once two fixes have failed (INBOX 1289).
                models = getattr(self, "_models", None)
                allowed = models is None or models._config.get_preference("semantic_auto_install", True)
                tried = getattr(self, "_repair_attempts", 0)
                if allowed and tried < REPAIR_ATTEMPTS:
                    self._repair_attempts = tried + 1
                    logger.warning("%s is on this computer but would not load (%s); fetching its files again", repo, safe_value(str(exc), 200))
                    try:
                        return _fetch_model_as_a_task(SentenceTransformer, repo, "Fixing search by meaning")
                    except Exception as again:  # noqa: BLE001  # offline, or the Hub refused
                        logger.warning("%s could not be fetched again (%s)", repo, safe_value(str(again), 200))
                    if self._repair_attempts < REPAIR_ATTEMPTS:
                        raise EmbeddingCacheBroken(
                            "Search by meaning is fixing its files; search uses keywords until it has."
                        ) from exc
                else:
                    logger.warning("%s is on this computer but would not load (%s); staying offline", repo, safe_value(str(exc), 200))
                raise EmbeddingCacheBroken(
                    "The search-by-meaning model's files on this computer would not load. "
                    "Reinstall it from Settings, Models."
                ) from exc
        logger.info("%s is not on this computer yet: downloading it once", repo)
        return _fetch_model_as_a_task(SentenceTransformer, repo, "Downloading the search model")

    def _mend_incomplete_cache(self, repo: str, health: dict, cause: Exception) -> None:
        """The folder is there but its files are not all (an empty folder, an
        interrupted download): mend it as a visible task and say so. Always
        raises `EmbeddingCacheBroken` (Brief 101c, the owner 2026-10-07).

        **Visible, not inline.** The hidden fetch that used to run here showed
        nowhere and, offline, ended as a bare "would not load". The repair is
        a Background task with Quit (`embedmodels.repair`), at most twice a process,
        unless automatic installs are off; when it lands, `_after_repair` lets
        the model load without waiting out the retry interval."""
        from tessellate.core import embedmodels

        models = getattr(self, "_models", None)
        allowed = models is None or models._config.get_preference("semantic_auto_install", True)
        running = embedmodels.current()
        mending = bool(running.running and running.repair)
        #: Two fixes a process (the owner: "ask the person only after two
        #: failed fixes"); each waits for the retry interval after the last.
        attempts = getattr(self, "_repair_attempts", 0)
        if not mending and allowed and attempts < self.REPAIR_ATTEMPTS:
            self._repair_attempts = attempts + 1
            mending, _ = embedmodels.repair(repo)
        logger.warning(
            "%s is on this computer but its files are incomplete (%s); %s",
            repo,
            safe_value(", ".join(health["missing"]), 200),
            "repairing it" if mending else "staying offline",
        )
        if mending:
            embedmodels.on_download_finished(self._after_repair)
            raise EmbeddingCacheBroken(
                "The search-by-meaning model's files were incomplete. They are being repaired "
                "(Background tasks); search uses keywords until that finishes."
            ) from cause
        raise EmbeddingCacheBroken(
            "The search-by-meaning model's files on this computer are incomplete. "
            "Reinstall it from Settings, Models."
        ) from cause

    def _after_repair(self, repo: str) -> None:
        """A repair landed: forget the failure and load the model now, so
        search by meaning returns without a restart."""
        if repo != self.st_repo():
            return
        self._load_failed_at = None
        self.last_error = None
        self._embed_with_sentence_transformers("warm up")

    def _prefixed(self, text: str) -> str:
        """`text` with the prefix its model was trained with (E5, nomic)."""
        from tessellate.core import embedmodels

        return embedmodels.prefix_for(self.st_repo()) + text

    def _embed_with_sentence_transformers(self, text: str) -> np.ndarray | None:
        if self._st_model is None and self._load_failed_at is not None:
            if time.monotonic() - self._load_failed_at < self.RETRY_AFTER_SECONDS:
                return None  # don't re-stall every save while it's broken
        try:
            if self._st_model is None:
                # Heavy import (pulls in torch): deferred so the app
                # starts fast and still runs if the package is missing.
                self._st_model = self._load_st_model()
                self._was_loaded = True
                self._load_failed_at = None
            import numpy as np

            _limit_torch_threads()
            # No progress bar: a tqdm "Batches" bar on stderr for every one
            # note is log noise in a packaged app and a little work besides.
            result = np.asarray(
                self._st_model.encode(self._prefixed(text), show_progress_bar=False), dtype="float32"
            )
            self.last_error = None
            self._last_used = time.monotonic()
            self._watch_idle()
            return result
        except Exception as exc:
            # No semantic features right now; the rest of the app must
            # keep working: but record and LOG why, or a broken install
            # looks like it's "warming up" forever (user-reported bug).
            self._load_failed_at = time.monotonic()
            self._maybe_auto_install_missing_package(exc)
            if isinstance(exc, ModuleNotFoundError) and "sentence_transformers" in str(exc):
                #: **Not installed is a state, not a crash** (owner's packaged-app
                #: log: a full traceback for `No module named
                #: 'sentence_transformers'`). The package is optional and the
                #: line above has already started installing it, so the log
                #: gets one sentence and Settings gets a reason a person can act
                #: on, rather than a Python exception name.
                from tessellate.core import extras

                installing = extras.current().running
                self.last_error = (
                    "Search by meaning is being installed; search uses keywords until it finishes"
                    if installing
                    else "Search by meaning is not installed; search uses keywords"
                )
                logger.warning("sentence-transformers is not installed (%s)", self.last_error)
                return None
            #: Our own sentence as it is; another library's error keeps its
            #: class name, which the Settings diagnosis reads (DLL, CUDA).
            self.last_error = str(exc) if isinstance(exc, EmbeddingCacheBroken) else f"{type(exc).__name__}: {exc}"
            logger.exception("embedding backend failed")
            return None

    def _maybe_auto_install_missing_package(self, exc: Exception) -> None:
        """Self-heal a missing `sentence-transformers` install, once per
        process, instead of leaving it to the user to find Settings ->
        Packages themselves.

        Search-by-meaning is the *default* engine, it already silently
        downloads its own ~130MB model from Hugging Face on first use with
        no separate opt-in, so installing the one PyPI package that makes
        it importable at all is the same "works without being asked" shape,
        not a new consent-requiring action the way turning on web search or
        checking GitHub for updates would be.

        Deliberately narrow: only a genuine "the package flat-out isn't
        there" `ModuleNotFoundError` triggers this. A different failure: 
        a corrupted install, an incompatible wheel, an out-of-memory crash
        - retrying the exact same `pip install` would do nothing but burn
        bandwidth and hide a real problem behind "installing…" forever;
        `is_installed`'s own docstring already notes that import-success
        isn't "it's sound", which is a different, harder problem than this
        (`reinstall`, the manual escape hatch in Settings, exists for that
        one). Reuses `core.extras.start`, the same machinery the Settings ->
        Packages button calls: including this session's `find_system_python`
        fix, so this now actually works on a packaged (frozen) build, not
        just a source checkout.
        """
        if self._auto_install_attempted:
            return
        # A developer's checkout and every UI sweep run with this set
        # (scratchpad/ui-sweeps/serve.sh): CLAUDE.md section 7 forbids torch
        # in the sandbox, and the first note a sweep saved used to start a
        # multi-gigabyte pip install behind it.
        if os.environ.get("TESSELLATE_NO_AUTO_INSTALL"):
            return
        if not isinstance(exc, ModuleNotFoundError) or "sentence_transformers" not in str(exc):
            return
        # The owner's refusal ("the user should be able to cancel or refuse
        # the auto install"): Settings, Search and index. Checked before the
        # once-per-process flag is spent, so switching it back on lets the
        # next failed embed install without a restart.
        #: Through the model manager's own config, not `core.deps`, which
        #: imports this module (tests/test_no_import_cycles.py).
        if not self._models._config.get_preference("semantic_auto_install", True):
            logger.info("sentence-transformers is missing and the auto-install is switched off")
            return
        #: Never started for another device (core/origin.py, secscan-1011's
        #: decision): a note saved from a phone waits for this computer.
        from tessellate.core import origin

        if origin.from_another_device():
            origin.defer("semantic-install", lambda: self._maybe_auto_install_missing_package(exc))
            return
        self._auto_install_attempted = True
        from tessellate.core import extras

        started, message = extras.start("semantic", auto=True)
        if not started:
            # Already installed (so this was a *different* failure, sound
            # but broken, `reinstall`'s job, not this one's), already
            # running (someone beat this to it), or genuinely unavailable
            # on this platform. Nothing safe to do automatically either way.
            logger.info("sentence-transformers auto-install not started: %s", message)
            return
        logger.info("sentence-transformers missing: installing it automatically")

        def _retry_once_installed() -> None:
            while extras.current().running:
                time.sleep(1)
            if extras.current().outcome == "completed":
                logger.info(
                    "sentence-transformers auto-install finished: retrying the load"
                )
                # CPython's path-based import finders cache directory
                # listings for speed, so a package that didn't exist the
                # first time this process looked can still come up
                # "missing" on a naive retry even though pip just put it
                # there: invalidate_caches() is the documented fix
                # (importlib docs, "Caching and invalidation"), and is what
                # makes this an actual same-process fix rather than a
                # "restart Tessellate" instruction in different words.
                import importlib

                importlib.invalidate_caches()
                self.reset_failure_state()

        # Also not on the pool, and this one would be an outright bug there:
        # it waits on someone else's pip process, which is minutes. A bounded
        # pool worker held that long with captions queued behind it is the
        # pool starving itself, the exact failure a queue is supposed to
        # prevent. One per process, at most once ever (`_auto_install_attempted`).
        threading.Thread(
            target=_retry_once_installed, name="embedding-auto-install-watch", daemon=True
        ).start()

    def store_for_entry(self, session: Session, entry: Entry) -> bool:
        """Save an entry's vector. Returns False on failure, which only
        means no semantic search for this entry; it never blocks the
        entry save itself.

        Private notes are never embedded. A vector derived from the text
        encodes what the note is about, so storing one beside the ciphertext
        would leak exactly what the encryption is there to hide."""
        if getattr(entry, "is_private", False):
            return False
        vector = self.embed_text(embedding_text(session, entry))
        if vector is None:
            return False
        self._write_vector(session, entry, vector)
        session.commit()
        return True

    def store_for_entries(self, session: Session, entries: list[Entry]) -> int:
        """Embed several entries in one batched encode and store each vector.

        The same rules as `store_for_entry`, for the loops that embed a whole
        notebook: private notes are skipped, an entry the backend could not
        embed is skipped and the rest of the batch still lands, and the number
        stored is returned. One commit for the batch rather than one per note,
        which is where the rest of the saving is. `embed_many` falls back to
        one call each on a backend with no batched encode (Ollama), so this is
        never slower than the loop it replaced.
        """
        eligible = [entry for entry in entries if not getattr(entry, "is_private", False)]
        if not eligible:
            return 0
        vectors = self.embed_many([embedding_text(session, entry) for entry in eligible])
        stored = 0
        for entry, vector in zip(eligible, vectors):
            if vector is None:
                continue
            self._write_vector(session, entry, vector)
            stored += 1
        session.commit()
        return stored

    def _write_vector(self, session: Session, entry: Entry, vector: np.ndarray) -> None:
        # **Storing is storing, not inserting.** `entry_id` is unique, so a
        # second call for the same note raised `UNIQUE constraint failed:
        # embeddings.entry_id` and took whatever was saving with it. Every
        # caller today already deletes the old row first, or selects only
        # notes that have none, so nothing was broken; the duplication of
        # that guard across four call sites was the bug waiting to happen,
        # because the next caller has to know to write it and the name says
        # it does not have to. Their deletes stay, harmlessly, as no-ops.
        session.execute(sa_delete(EmbeddingRecord).where(EmbeddingRecord.entry_id == entry.id))
        record = EmbeddingRecord(
            entry_id=entry.id,
            embedding=vector_to_bytes(vector),
            dim=int(vector.shape[0]),
            model_version=self.backend_id(),
        )
        session.add(record)
        session.flush()
        try:
            self._store_chunks(session, entry, record)
        except Exception:  # noqa: BLE001  # chunks refine a search; the note vector is the save
            logger.warning("couldn't store paragraph vectors for entry %s", entry.id, exc_info=True)

    def embed_many(self, texts: list[str]) -> list[np.ndarray | None]:
        """Vectors for several texts: one batched encode where the backend
        has one (sentence-transformers), one call each otherwise."""
        if (
            texts
            and self._models is not None
            and self._models.embedding_backend() != "ollama"
            and self._st_model is not None
        ):
            try:
                import numpy as np

                _limit_torch_threads()
                batch = self._st_model.encode([self._prefixed(text) for text in texts], show_progress_bar=False)
                return [np.asarray(row, dtype="float32") for row in batch]
            except Exception:  # noqa: BLE001  # fall back to one at a time
                logger.debug("batched encode failed; embedding one at a time", exc_info=True)
        return [self.embed_text(text) for text in texts]

    def _store_chunks(self, session: Session, entry: Entry, record: EmbeddingRecord) -> int:
        """Store a vector per paragraph beside the note's own (row 6).

        Paragraphs whose text is unchanged since the last save keep their
        vector (matched by digest, same backend), so an edit to one paragraph
        of a long note embeds that paragraph only. All or nothing: a paragraph
        the backend could not embed leaves the note with no chunks rather than
        some, since a note scored on half its paragraphs ranks below one scored
        on none.
        """
        content = entry.content or ""
        spans = paragraph_chunks(content)
        backend = self.backend_id()
        previous = {
            digest: (blob, dim)
            for digest, blob, dim in session.execute(
                select(ChunkVector.digest, ChunkVector.embedding, ChunkVector.dim).where(
                    ChunkVector.entry_id == entry.id, ChunkVector.model_version == backend
                )
            ).all()
        }
        session.execute(sa_delete(ChunkVector).where(ChunkVector.entry_id == entry.id))
        if len(spans) < 2:
            return 0
        texts = [chunk_text(content, start, end) for start, end in spans]
        digests = [_digest(text) for text in texts]
        missing = [i for i, digest in enumerate(digests) if digest not in previous]
        fresh = dict(zip(missing, self.embed_many([texts[i] for i in missing])))
        rows: list[ChunkVector] = []
        for ordinal, ((start, end), digest) in enumerate(zip(spans, digests)):
            if ordinal in fresh:
                vector = fresh[ordinal]
                if vector is None:
                    return 0
                blob, dim = vector_to_bytes(vector), int(vector.shape[0])
            else:
                blob, dim = previous[digest]
            if dim != record.dim:
                return 0
            rows.append(
                ChunkVector(
                    entry_id=entry.id,
                    embedding_id=record.id,
                    ordinal=ordinal,
                    start=start,
                    end=end,
                    digest=digest,
                    embedding=blob,
                    dim=dim,
                    model_version=backend,
                )
            )
        session.add_all(rows)
        return len(rows)


class _PinnedModels:
    """The three answers an `EmbeddingService` asks its model manager for,
    fixed: the settings a model switch is moving to, not the saved ones."""

    def __init__(self, backend: str, model: str) -> None:
        self._backend = backend
        self._model = model

    def embedding_backend(self) -> str:
        return self._backend

    def embedding_model(self) -> str:
        return self._model if self._backend == "ollama" else ""

    def embedding_st_model(self) -> str:
        return self._model if self._backend != "ollama" else DEFAULT_ST_MODEL


# `store_quietly` used to live here and is now `core.deps.store_quietly`, it
# needs the shared EmbeddingService, and reaching for that from inside this
# module means importing the container that imports this module. See the
# docstring there.
