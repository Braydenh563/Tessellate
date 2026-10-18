"""The retrieval engine: one search, three signals, every hit explained.

WORLD_CLASS_PLAN B3, SESSION_BRIEFS Brief 11, spec in
`tests/test_search_engine_spec.py`.

One `search()` over every kind, answering with `Hit`s that carry all three of
their scores rather than one blended number. That is the part worth stating
plainly: **"why this result" is a rendering here, not a guess.** The list can
say "matched the title, similar meaning, linked to the note you have open"
because those three numbers came back with the row, and a person who disagrees
with the ranking can see which signal did it.

The three signals, and where each comes from:

- **bm25**, from `search_index` (`search/index.py`), which covers notes,
  documents, boards, files' extracted text, bookmarks and reminders. SQLite's
  own IDF-weighted relevance, no dependency, and the only signal that works
  with the model switched off, which is why it carries the most weight.
- **cosine**, from the vectors already stored in `embeddings`, through the
  process-level matrix below. The matrix is the change: `semantic_search`
  selects every `EmbeddingRecord` row on **every request** and stacks them
  into a fresh array each time (ANALYSIS §34 measured the older, worse version
  of that at ~7s on 50k notes). Here the array is built once and kept up to
  date by the writes themselves.
- **graph proximity** to what the person is looking at: 1 / (1 + hops) over
  the link tables, at most two hops, computed only for the candidates that
  already matched. A note linked to the note you have open is a better answer
  to a question you asked while reading it, and no amount of text similarity
  knows that.

What this does **not** replace: `search_manager.retrieve()` is what /chat
uses, and it stays. It fuses keyword and semantic results by rank, expands the
graph for context and reads a question's time phrases, all of which is tuned
against its own tests. This engine is the *search surface*: one query, every
kind, explained, fast. The two share `search/query.py` (one parser) and this
module reuses `search_manager`'s stopword list and term splitter rather than
writing a second one.
"""
from __future__ import annotations

import importlib
import itertools
import logging
import math
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import event, or_, select, text
from sqlalchemy.orm import Session

from tessellate.ai import variants
from tessellate.core.database import Attachment, EmbeddingRecord, Entry, EntryLink, Reminder
from tessellate.entry.highlights import has_highlight
from tessellate.entry.properties import strip as strip_properties
from tessellate.search import chunks as search_chunks
from tessellate.search import index as search_index
from tessellate.search import query as query_understanding
from tessellate.search import search_manager
from tessellate.search.snippet import clip_words, window_words

if TYPE_CHECKING:
    # Annotation-only: see ai/embeddings.py's own TYPE_CHECKING import for
    # why. The matrix (`_Matrix`, this module's whole reason to exist) is
    # built once, on the warm-up thread, by `_load_all_vectors`; every
    # function below that touches `np.*` for real carries its own import so
    # merely importing this module (which `routes_search.py` does at app
    # start, to register the router) never does.
    import numpy as np

logger = logging.getLogger("tessellate.search.engine")

#: How the three signals are weighted into one order. Keyword relevance leads
#: because it is the signal that is always there: a notebook with no embedding
#: backend still has to rank well, and an app whose search quality depends on a
#: model being warm is not an offline app. Cosine is the second because it is
#: what finds the note you cannot remember the words of. Graph proximity is
#: deliberately the smallest: it is context, not evidence, the same judgement
#: `search_manager.graph_expansion` already makes by appending rather than
#: interleaving its neighbours.
WEIGHTS = {"bm25": 0.5, "cosine": 0.35, "graph": 0.15}

#: How many FTS candidates go on to the expensive signals. Cosine over 200
#: rows is one small matrix slice and the graph walk is two queries; over the
#: whole notebook both are a scan. Anything ranked past 200 by words alone was
#: not going to reach a twenty-row answer on a 0.35 weight.
CANDIDATE_DEPTH = 200

#: Graph proximity stops here. A third hop reaches most of a well-linked
#: notebook, at which point the signal says nothing about any one note.
MAX_HOPS = 2

#: Below this blended score a hit is noise and is dropped rather than shown at
#: the bottom of the list. Deliberately low: the keyword index only returns
#: rows that matched at all, so this is a floor against near-zero graph-only
#: dust, not a relevance opinion.
MIN_SCORE = 0.01


@dataclass
class Hit:
    """One result, with the whole of why it is here."""

    kind: str
    ref_id: int
    source: str
    title: str
    snippet: str
    #: `{"bm25": .., "cosine": .., "graph": ..}`, each 0 to 1. Always all
    #: three keys, even when a signal was unavailable: a missing key and a
    #: zero score render identically to a person and mean opposite things to
    #: a maintainer, so the zero is explicit and `available` says which.
    scores: dict[str, float]
    #: The blended score the list is ordered by.
    score: float
    #: Why this matched, in words, ready to render.
    explain: list[str] = field(default_factory=list)
    space: str = "default"
    written: str = ""
    flags: str = ""

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "id": self.ref_id,
            "source": self.source,
            "title": self.title,
            "snippet": self.snippet,
            "scores": {name: round(value, 4) for name, value in self.scores.items()},
            "score": round(self.score, 4),
            "explain": self.explain,
            "space": self.space,
            "written": self.written,
            "flags": self.flags.split() if self.flags else [],
        }


# --- the vector matrix --------------------------------------------------------
#
# One float32 matrix per process, rows already unit-normalised so a top-k is a
# single matmul and nothing divides at query time. Rebuilt when the notebook or
# the embedding backend changes underneath it (a test opens a new database per
# test; a person can switch embedding models in Settings), and otherwise kept
# in step by the flush hook below rather than by a reload.


@dataclass
class _Matrix:
    key: str
    ids: list[int]
    rows: np.ndarray
    position: dict[int, int]
    #: Rows forgotten in place (zeroed, id -1) and not yet compacted away.
    dead: int = 0
    #: The embedding backend these vectors came from ("" for a hand-built
    #: matrix in a test): a vector the hook sees from any other is not
    #: comparable and never joins.
    backend: str = ""
    #: `{entry_id: embeddings.id}` for every row of the table this matrix has
    #: *considered*, including the ones it holds no vector for (another
    #: backend, another width). What `current_matrix` diffs the table against
    #: to find the writes the flush hook never saw, without reading a blob.
    seen: dict[int, int] = field(default_factory=dict)
    #: The table's `(count, max(id), total(entry_id))` when `seen` last
    #: matched it; None when the hook has changed the matrix since, which
    #: forces the next `current_matrix` to diff once (a rollback after a flush
    #: would otherwise leave a vector the table never kept).
    fingerprint: tuple | None = None
    #: Entries of this backend at another width: a model swapped inside one
    #: backend. Counted so the matrix moves to the new width once the reindex
    #: has put most rows there.
    off_width: set[int] = field(default_factory=set)
    #: Bumped on every change to `rows`, unique across rebuilds (a global
    #: counter), so a cache over "the vector set" (`similar_pairs` for link
    #: suggestions and tensions) can key on `(key, version)` and nothing else.
    version: int = 0
    #: Which rows are real vectors (not dead, not zero), cached until a change.
    _live: np.ndarray | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.version:
            self.version = next(_versions)

    def changed(self) -> None:
        self.version = next(_versions)
        self._live = None

    def live(self) -> np.ndarray:
        if self._live is None or self._live.shape[0] != self.rows.shape[0]:
            import numpy as np

            self._live = np.any(self.rows != 0, axis=1) if self.rows.size else np.zeros(0, dtype=bool)
        return self._live

    def top_k(self, vector: np.ndarray, k: int, exclude: int | None = None) -> list[tuple[int, float]]:
        if not self.ids:
            return []
        import numpy as np

        norm = float(np.linalg.norm(vector))
        if norm == 0:
            return []
        scores = self.rows @ (vector.astype("float32") / norm)
        # `argpartition` rather than a full sort: at 50k vectors the sort is
        # most of the cost of the whole call, and only the top k is wanted.
        take = min(k + (1 if exclude is not None else 0), len(self.ids))
        # Widened by the dead rows, and the dead rows dropped: a zeroed row
        # scores 0, which outranks every negative cosine, so with few live
        # vectors pointing away from the query `top_k` used to hand back the
        # id -1 as an answer.
        take = min(take + self.dead, len(self.ids))
        best = np.argpartition(-scores, take - 1)[:take]
        ordered = best[np.argsort(-scores[best])]
        out = [
            (self.ids[i], float(scores[i]))
            for i in ordered
            if self.ids[i] != exclude and self.ids[i] >= 0
        ]
        return out[:k]

    def scores_for(self, vector: np.ndarray, wanted: list[int]) -> dict[int, float]:
        """Cosine for a named handful of ids, no scan: this is the search
        path, where the candidates are already chosen by the keyword index."""
        rows = [(entry_id, self.position[entry_id]) for entry_id in wanted if entry_id in self.position]
        if not rows:
            return {}
        import numpy as np

        norm = float(np.linalg.norm(vector))
        if norm == 0:
            return {}
        slice_ = self.rows[[position for _id, position in rows]]
        scores = slice_ @ (vector.astype("float32") / norm)
        return {entry_id: float(score) for (entry_id, _p), score in zip(rows, scores)}


_versions = itertools.count(1)
_matrix: _Matrix | None = None
#: Guards the matrix's arrays while they change and while a reader copies its
#: view of them. Never held across a database read: the hook that takes it
#: runs inside another session's flush, and a lock held while waiting on
#: SQLite is the shape a deadlock is made of.
_matrix_lock = threading.RLock()


def _matrix_key(session: Session, backend_id: str) -> str:
    bind = session.get_bind()
    return f"{getattr(bind, 'url', '')}|{backend_id}"


def _table_fingerprint(session: Session) -> tuple:
    """`(count, max(id), total(entry_id))` of the embeddings table.

    Answered from the `entry_id` index and the rowid alone, so it never
    touches a vector: 0.1 ms at 5,000 rows against the 20-odd ms of reading
    and parsing them. It changes on every insert (a new id) and every delete
    (the count), which is all a vector write can be here: `store_for_entry`
    deletes and inserts, nothing updates a row in place.
    """
    row = session.execute(
        text("SELECT count(*), max(id), total(entry_id) FROM embeddings")
    ).one()
    return (int(row[0]), row[1], float(row[2] or 0))


def _row_ids(session: Session) -> dict[int, int]:
    """`{entry_id: embeddings.id}` for the whole table, never a vector.

    From the `entry_id` index alone, through the driver's own rows rather
    than an ORM select: at 5,000 rows SQLAlchemy's row processing was ten of
    the seventeen milliseconds the first query after a write paid.
    """
    rows = session.connection().exec_driver_sql("SELECT entry_id, id FROM embeddings").fetchall()
    return {int(entry_id): int(row_id) for entry_id, row_id in rows}

def _load_all_vectors(session: Session, backend_id: str) -> _Matrix:
    """The one full scan of `embeddings`, run once per process.

    Named, private and called from exactly one place on purpose: the spec
    (`test_similarity_does_not_scan_every_vector`) patches this function and
    asserts a request never reaches it. If a future change makes a per-request
    path call it again, that test fails, which is the whole point of it having
    a name rather than being inline.
    """
    import numpy as np

    # Before the rows, so a write that lands between the two reads leaves the
    # fingerprint behind the table and the next `current_matrix` diffs it in.
    fingerprint = _table_fingerprint(session)
    seen = _row_ids(session)
    records = session.execute(
        select(EmbeddingRecord.entry_id, EmbeddingRecord.embedding).where(
            # Vectors from another backend live in a different space; mixing
            # them gives nonsense (plan §6.5), the same filter
            # `semantic_search`'s table scan applies.
            EmbeddingRecord.model_version == backend_id
        )
    ).all()
    ids: list[int] = []
    vectors: list[np.ndarray] = []
    widths: dict[int, int] = {}
    for entry_id, blob in records:
        vector = _unit(np.frombuffer(blob, dtype="float32"))
        widths[vector.shape[0]] = widths.get(vector.shape[0], 0) + 1
        ids.append(int(entry_id))
        vectors.append(vector)
    off_width: set[int] = set()
    if widths and len(widths) > 1:
        # A model swapped inside one backend leaves rows at the old width, and
        # stacking a ragged list raises and takes every search down with it
        # (`semantic_search`'s own comment records that outage). The widest
        # family wins; the rest come back when the reindex refills them.
        keep = max(widths, key=lambda width: widths[width])
        logger.info(
            "vectors at %d widths in one backend; indexing the %d at width %d, reindex for the rest",
            len(widths),
            widths[keep],
            keep,
        )
        off_width = {entry_id for entry_id, vector in zip(ids, vectors) if vector.shape[0] != keep}
        pairs = [(entry_id, vector) for entry_id, vector in zip(ids, vectors) if vector.shape[0] == keep]
        ids = [entry_id for entry_id, _v in pairs]
        vectors = [vector for _id, vector in pairs]
    rows = np.stack(vectors) if vectors else np.zeros((0, 1), dtype="float32")
    return _Matrix(
        key=_matrix_key(session, backend_id),
        ids=ids,
        rows=rows,
        position={entry_id: i for i, entry_id in enumerate(ids)},
        backend=backend_id,
        seen=seen,
        fingerprint=fingerprint,
        off_width=off_width,
    )


def _unit(vector: np.ndarray) -> np.ndarray:
    import numpy as np

    norm = float(np.linalg.norm(vector))
    return (vector / norm).astype("float32") if norm else vector.astype("float32")


def warm_vectors(session: Session, backend_id: str | None = None) -> int:
    """Build the matrix. Called at startup, and by nothing per request.

    Returns how many vectors it holds, so a caller can log it. Cheap to call
    again: a matrix already built for this notebook and backend is kept.
    """
    global _matrix
    backend = backend_id or _backend_id()
    if backend is None:
        return 0
    key = _matrix_key(session, backend)
    if _matrix is not None and _matrix.key == key:
        return len(_matrix.ids)
    _matrix = _load_all_vectors(session, backend)
    return len(_matrix.ids)


#: Past this many changed rows, one full rebuild is cheaper than fetching
#: them by id (and a reindex is exactly the case that gets here).
RECONCILE_MAX_ROWS = 500


def current_matrix(session: Session, backend_id: str) -> _Matrix | None:
    """The matrix for this notebook and backend, brought up to date with the table.

    What `semantic_search` scores against (WORLD_CLASS_PLAN row 1, F3). The
    flush hook below keeps the matrix in step with every ORM write; what it
    cannot see is a bulk `delete()` statement (the purge, a category
    re-embed, a re-embed that then failed) or a flush that was rolled back.
    So this asks the table one cheap question first, its fingerprint, and
    only when that has moved does it diff the table's `(entry_id, id)` pairs
    against what the matrix has seen and fetch the handful of rows that
    differ. A request that finds the table as the matrix left it reads no
    vector at all.

    Builds a cold matrix, once: the table scan this replaces cost the same,
    per request.
    """
    global _matrix
    key = _matrix_key(session, backend_id)
    fingerprint = _table_fingerprint(session)
    matrix = _matrix
    if matrix is None or matrix.key != key:
        built = _load_all_vectors(session, backend_id)
        with _matrix_lock:
            _matrix = built
        return built
    if matrix.fingerprint == fingerprint:
        return matrix
    if not _reconcile(session, matrix, backend_id, fingerprint):
        built = _load_all_vectors(session, backend_id)
        with _matrix_lock:
            _matrix = built
        return built
    return matrix


def rows_for(matrix: _Matrix, ids: list[int]) -> tuple[list[int], np.ndarray] | None:
    """`(positions in ids, rows)` for the ids the matrix holds, copied under
    its lock: a caller's own read of the vectors it needs, without the scan
    of the table this matrix exists to replace (the janitor's filing by
    meaning, ARCH-02). None when it holds none of them."""
    import numpy as np

    wanted = np.fromiter(ids, dtype=np.int64, count=len(ids))
    with _matrix_lock:
        if not matrix.ids or not len(wanted):
            return None
        held = np.asarray(matrix.ids, dtype=np.int64)
        # Sorted lookup in C: the dict walk this replaces was 200 ms of a
        # save at 5,000 notes. A dead row holds id -1, which no caller asks for.
        order = np.argsort(held, kind="stable")
        at = np.searchsorted(held[order], wanted)
        at[at >= len(held)] = 0
        hit = held[order][at] == wanted
        if not hit.any():
            return None
        positions = order[at[hit]]
        # Fancy indexing copies, so the caller holds its own rows.
        rows = matrix.rows[positions]
    return np.flatnonzero(hit).tolist(), rows


def _reconcile(session: Session, matrix: _Matrix, backend_id: str, fingerprint: tuple) -> bool:
    """Apply the writes the hook missed. False means "rebuild instead"."""
    import numpy as np

    table = _row_ids(session)
    seen = dict(matrix.seen)
    gone = [entry_id for entry_id in seen if entry_id not in table]
    changed = {entry_id: row_id for entry_id, row_id in table.items() if seen.get(entry_id) != row_id}
    if len(changed) > RECONCILE_MAX_ROWS:
        return False
    fetched: dict[int, tuple[str, bytes]] = {}
    wanted = list(changed.values())
    for start in range(0, len(wanted), 400):  # under SQLite's variable limit
        for entry_id, model_version, blob in session.execute(
            select(EmbeddingRecord.entry_id, EmbeddingRecord.model_version, EmbeddingRecord.embedding).where(
                EmbeddingRecord.id.in_(wanted[start : start + 400])
            )
        ).all():
            fetched[int(entry_id)] = (model_version, blob)
    with _matrix_lock:
        for entry_id in gone:
            _forget_from(matrix, entry_id)
            matrix.seen.pop(entry_id, None)
            matrix.off_width.discard(entry_id)
        for entry_id, row_id in changed.items():
            if entry_id not in fetched:
                # Deleted between the two reads: gone, and the fingerprint
                # left as it was so the next request looks again.
                _forget_from(matrix, entry_id)
                matrix.seen.pop(entry_id, None)
                continue
            model_version, blob = fetched[entry_id]
            matrix.seen[entry_id] = row_id
            if model_version != backend_id:
                _forget_from(matrix, entry_id)
                matrix.off_width.discard(entry_id)
                continue
            _put(matrix, entry_id, _unit(np.frombuffer(blob, dtype="float32")))
        if len(fetched) == len(changed):
            matrix.fingerprint = fingerprint
    live = len(matrix.ids) - matrix.dead
    # Most of this backend's rows are now at a width the matrix is not: the
    # reindex after a model swap has passed half way, so the new width wins.
    return len(matrix.off_width) <= live


def vector_view(session: Session, backend_id: str) -> tuple[list[int], np.ndarray, np.ndarray] | None:
    """`(ids, unit rows, live mask)` for `semantic_search`, or None.

    A copy of the id list and references to the arrays, taken under the lock
    so a write in another thread cannot hand back ids and rows of different
    lengths. None when the matrix cannot be had, which sends the caller back
    to its table scan rather than failing a search.
    """
    matrix = current_matrix(session, backend_id)
    if matrix is None:
        return None
    with _matrix_lock:
        rows = matrix.rows
        ids = list(matrix.ids)
        live = matrix.live()
    if len(ids) != rows.shape[0]:
        return None
    return ids, rows, live


def _backend_id() -> str | None:
    """The embedding backend's id, or None when there is no embedding at all.

    Reached through the dependency container rather than passed in, because
    every caller of `search()` would otherwise have to know about embeddings
    to ask a keyword question.
    """
    try:
        # `importlib`, not an `import` statement, and the difference is the
        # whole point: this is a leaf naming the dependency container that
        # *builds* the things it reads, which closes
        # `ai.embeddings -> search.engine -> core.deps -> ai.embeddings`.
        # `tests/test_no_import_cycles.py` counts the statement wherever it
        # sits, because CodeQL does, so moving it into this function body
        # would hide the cycle from a naive reader and leave the alert open.
        deps = importlib.import_module("tessellate.core.deps")

        embeddings = deps.get_embeddings()
        return embeddings.backend_id() if embeddings.is_ready() else None
    except Exception:  # noqa: BLE001  # a bare-session script with no app state
        return None


def _live_matrix(session: Session) -> _Matrix | None:
    """The matrix if it is built for this notebook, else None. Never builds.

    This is what keeps `related()` off the scan path: a cold matrix means "no
    similarity yet", not "go and read fifty thousand rows while someone waits".
    Startup warms it (`api/app.py`), so cold only ever means the first moments
    of a process.
    """
    backend = _backend_id()
    if backend is None or _matrix is None:
        return None
    return _matrix if _matrix.key == _matrix_key(session, backend) else None


@event.listens_for(Session, "after_flush")
def _keep_matrix_in_step(session: Session, flush_context) -> None:  # noqa: ANN001
    """A stored vector joins the matrix without a reload; a deleted one leaves.

    The same reasoning as the index's own hook (`search/index.py`): every
    writer participates by construction. A bulk `DELETE FROM embeddings`
    through `session.execute` is the one shape this cannot see, and
    `current_matrix` catches it from the table's fingerprint. Of the three
    that exist, two (`routes_entries.py`, re-embedding after an edit) store a
    fresh vector immediately afterwards, so the row is replaced rather than
    left stale; the third (`manager.set_private`) stores nothing, because a
    private note is never embedded, and calls `forget_vector` instead.
    """
    if _matrix is None:
        return
    for obj in session.new:
        if isinstance(obj, EmbeddingRecord):
            _remember(obj)
    for obj in session.deleted:
        if isinstance(obj, EmbeddingRecord):
            _forget(int(obj.entry_id))


def _remember(record: EmbeddingRecord) -> None:
    matrix = _matrix
    if matrix is None:
        return
    import numpy as np

    entry_id = int(record.entry_id)
    with _matrix_lock:
        # Unseen until the next `current_matrix` confirms it against the
        # table: this runs at flush, and a flush can still be rolled back.
        matrix.fingerprint = None
        if record.id is not None:
            matrix.seen[entry_id] = int(record.id)
        if matrix.backend and record.model_version != matrix.backend:
            _forget_from(matrix, entry_id)
            return
        _put(matrix, entry_id, _unit(np.frombuffer(record.embedding, dtype="float32")))


def _put(matrix: _Matrix, entry_id: int, vector: np.ndarray) -> None:
    """Set one entry's row, or record it as another width. Caller holds the lock."""
    import numpy as np

    live = len(matrix.ids) - matrix.dead
    if live > 0 and vector.shape[0] != matrix.rows.shape[1]:
        # A different width: a model swapped inside one backend. The row it
        # replaces is stale either way, so it goes; the matrix moves to the
        # new width once the reindex has put most rows there (`_reconcile`).
        _forget_from(matrix, entry_id)
        matrix.off_width.add(entry_id)
        return
    matrix.off_width.discard(entry_id)
    if vector.shape[0] != matrix.rows.shape[1]:
        # Nothing live at the old width (a fresh notebook's empty matrix is
        # `(0, 1)`): start again at this one.
        matrix.rows = np.zeros((0, vector.shape[0]), dtype="float32")
        matrix.ids = []
        matrix.position = {}
        matrix.dead = 0
    existing = matrix.position.get(entry_id)
    if existing is not None:
        matrix.rows[existing] = vector
        matrix.changed()
        return
    rows = np.vstack([matrix.rows, vector]) if matrix.rows.size else vector.reshape(1, -1)
    matrix.ids.append(entry_id)
    matrix.position[entry_id] = len(matrix.ids) - 1
    matrix.rows = rows
    matrix.changed()


def forget_vector(entry_id: int) -> None:
    """Drop one note's vector from the matrix, now.

    For the writes the ORM hook cannot see. There is exactly one that matters
    and it is a privacy one: `manager.set_private` deletes a note's
    `EmbeddingRecord` with a bulk `delete()` statement and stores nothing in
    its place, because a private note is never embedded. Without this the
    matrix would go on holding a vector *derived from the text the
    encryption exists to hide*, and every similarity query would keep
    answering questions about it until the next `current_matrix` noticed.
    """
    _forget(int(entry_id))


def _forget(entry_id: int) -> None:
    matrix = _matrix
    if matrix is None:
        return
    with _matrix_lock:
        matrix.fingerprint = None
        _forget_from(matrix, entry_id)


def _forget_from(matrix: _Matrix, entry_id: int) -> None:
    """Zero one row out of `matrix`. Caller holds the lock (or owns `matrix`)."""
    matrix.off_width.discard(entry_id)
    position = matrix.position.pop(entry_id, None)
    if position is None:
        return
    # The row is zeroed rather than removed: deleting from the middle of the
    # array would renumber every position after it. A zero row scores zero
    # against every query, and `top_k` skips it by its id.
    matrix.rows[position] = 0.0
    matrix.ids[position] = -1
    matrix.dead += 1
    matrix.changed()
    # **Compacted once the dead rows are a quarter of the array** (the
    # `search-matrix-compaction` row: "counted rather than guessed"). Before,
    # a dead row stayed for the life of the process, so a long session of
    # deleting and privatising carried all of it in memory and in every
    # `top_k` scan. A quarter because the rebuild is one copy of the live
    # rows, O(n), so paying it after n/4 forgets costs at most four row
    # copies per forget, amortised; the floor keeps a small notebook from
    # rebuilding on every second delete.
    if matrix.dead >= max(COMPACT_MIN_DEAD, len(matrix.ids) // 4):
        _compact(matrix)


#: The fewest dead rows worth a rebuild, whatever the fraction says.
COMPACT_MIN_DEAD = 8


def _compact(matrix: _Matrix) -> None:
    """Rebuild the matrix without its dead rows, in place."""
    keep = [position for position, entry_id in enumerate(matrix.ids) if entry_id >= 0]
    matrix.rows = matrix.rows[keep] if keep else matrix.rows[:0]
    matrix.ids = [matrix.ids[position] for position in keep]
    matrix.position = {entry_id: n for n, entry_id in enumerate(matrix.ids)}
    matrix.dead = 0
    matrix.changed()


# --- the search ---------------------------------------------------------------


def index_counts(session: Session) -> dict[str, int]:
    """How many rows the index holds per kind. See `index.counts`."""
    return search_index.counts(session)


def _term_groups(terms: list[str], mode: str) -> list[str]:
    """Each term as an FTS5 group of its spellings ("centre" and "center",
    INBOX 895), with a prefix star in "prefix" mode. The shared threshold,
    not a second 4 written out here: the two stages are meant to agree, and
    a duplicated constant is how they stop agreeing."""
    if mode == "prefix":
        return [variants.fts_group(f"{term}*" if len(term) >= search_manager.PREFIX_MIN_LEN else term) for term in terms]
    return [variants.fts_group(term) for term in terms]


def _match_expression(terms: list[str], phrases: list[str], excluded: list[str], mode: str) -> str:
    """An FTS5 MATCH expression from what the person typed.

    `terms` are already `\\W`-stripped by `query.search_terms`, so
    none of them can carry FTS5 syntax; a phrase is quoted, which is FTS5's own
    phrase operator, and the quotes inside one are stripped for the same
    reason. `mode` is "all", "prefix" or "any", the same three stages
    `keyword_search` walks and for the same reason: an empty page for one
    transposed letter is the worst answer a search box gives.
    """
    parts = _term_groups(terms, mode)
    joiner = " OR " if mode == "any" else " AND "
    # Parenthesised before anything is appended. FTS5 binds AND tighter than
    # OR and reads NOT as a binary operator, so `a OR b AND "phrase"` means
    # `a OR (b AND "phrase")`: the phrase the person quoted would be optional
    # for half the results, and `a OR b NOT c` would exclude `c` from only
    # half. One pair of brackets is the whole fix.
    expression = f"({joiner.join(parts)})" if parts else ""
    for phrase in phrases:
        cleaned = phrase.replace('"', " ").strip()
        if cleaned:
            expression = f'{expression} AND "{cleaned}"' if expression else f'"{cleaned}"'
    for word in excluded:
        safe = "".join(ch for ch in word if ch.isalnum() or ch in "_-")
        if safe and expression:
            expression = f"({expression}) NOT {safe}"
    return expression


def _space_clause(space, params: dict) -> list[str]:  # noqa: ANN001
    """The space part of a raw index query.

    `space` is a space id (that space only), a tuple of ids (every space but
    those: "All spaces" leaving out the ones marked hidden from it), or
    empty (no narrowing). Raw SQL never meets the ORM's space hook, which is
    why `search` resolves this from the session itself (ARCH-03).
    """
    if isinstance(space, tuple):
        if not space:
            return []
        names = {f"hidden{i}": value for i, value in enumerate(space)}
        params.update(names)
        return ["AND space NOT IN (" + ", ".join(f":{name}" for name in names) + ")"]
    if space:
        params["space"] = space
        return ["AND space = :space"]
    return []


def _session_space(session: Session):  # noqa: ANN202
    """The space this session reads, as `_space_clause` takes it.

    **The search index is raw SQL, so the space hook never sees it.** Measured
    (audit 2026-10-05, ARCH-03): a note written in "work" came back from
    `/search` asked in "personal", while `/entries/query`, the graph, the
    timeline and chat retrieval all returned nothing. The finder and the
    palette call `/search` with no `space`, so they crossed spaces, titles
    and snippets included, and spaces hidden from "All spaces" too.
    """
    workspace = session.info.get("workspace_id")
    if workspace and workspace != "all":
        return workspace
    if workspace == "all":
        return tuple(session.info.get("hidden_workspaces") or ())
    return None


def _candidates(
    session: Session,
    expression: str,
    kinds: list[str],
    space: str | tuple[str, ...] | None,
    since,
    until,
    depth: int,
) -> list[dict]:
    """The keyword pass: one query, every kind, filters applied in SQL.

    Filtering here rather than in Python is the difference between "read the
    top 200 rows" and "read the notebook": `kind`, `space` and the date bounds
    are stored on the index row precisely so they can narrow a MATCH instead of
    trimming its results.
    """
    sql = [
        f"SELECT rowid, kind, ref_id, source, title, body, tags, space, flags, written, "
        f"bm25(search_index, {', '.join(str(w) for w in search_index.BM25_WEIGHTS)}) AS score "
        "FROM search_index WHERE search_index MATCH :expr"
    ]
    params: dict = {"expr": expression, "depth": depth}
    if kinds:
        names = {f"kind{i}": kind for i, kind in enumerate(kinds)}
        sql.append("AND kind IN (" + ", ".join(f":{name}" for name in names) + ")")
        params.update(names)
    sql.extend(_space_clause(space, params))
    # ISO dates sort as text, which is the whole reason the column holds them
    # that way; a row with no date is kept, the same choice `search_manager`
    # makes, since dropping it would be filtering on an absence.
    if since is not None:
        sql.append("AND (written = '' OR written >= :since)")
        params["since"] = since.isoformat()
    if until is not None:
        sql.append("AND (written = '' OR written <= :until)")
        params["until"] = until.isoformat()
    sql.append("ORDER BY score LIMIT :depth")
    rows = session.execute(text(" ".join(sql)), params).mappings().all()
    return [dict(row) for row in rows]


def _filter_only(
    session: Session,
    kinds: list[str],
    space: str | tuple[str, ...] | None,
    since,
    until,
    depth: int,
    tags: list[str] | tuple[str, ...] = (),
) -> list[dict]:
    """The rows a query with no words at all asks for.

    `kind:document`, `is:pinned`, `after:2026-01-01`: a filter is a question
    too, and an FTS5 MATCH needs something to match. Newest first, because
    with nothing to rank by, recency is the only honest order. `score` is
    zeroed so the caller's normalisation leaves every bm25 at zero rather
    than inventing a relevance nobody computed.
    """
    sql = [
        "SELECT rowid, kind, ref_id, source, title, body, tags, space, flags, written, "
        "0.0 AS score FROM search_index WHERE 1 = 1"
    ]
    params: dict = {"depth": depth}
    if kinds:
        names = {f"kind{i}": kind for i, kind in enumerate(kinds)}
        sql.append("AND kind IN (" + ", ".join(f":{name}" for name in names) + ")")
        params.update(names)
    sql.extend(_space_clause(space, params))
    if since is not None:
        sql.append("AND (written = '' OR written >= :since)")
        params["since"] = since.isoformat()
    if until is not None:
        sql.append("AND (written = '' OR written <= :until)")
        params["until"] = until.isoformat()
    #: `tag:` in the query, not after it (Brief 47's bench): filtered over the
    #: newest `depth` rows instead, `tag:tag3` alone found 5 of the ~110 notes
    #: a 5,000-note notebook tags with it. The same substring test the
    #: caller applies to the rows it gets back.
    for index, tag in enumerate(tags):
        sql.append(f"AND instr(lower(tags), :tag{index}) > 0")
        params[f"tag{index}"] = tag.lower()
    sql.append("ORDER BY written DESC, rowid DESC LIMIT :depth")
    rows = session.execute(text(" ".join(sql)), params).mappings().all()
    return [dict(row) for row in rows]


def _mentions(row: dict, words: list[str]) -> bool:
    """Does this row use any of these words, anywhere a query can see?"""
    haystack = " ".join(
        str(row.get(column) or "") for column in ("title", "body", "tags")
    ).lower()
    return any(word.lower() in haystack for word in words)


def _keyword_pass(
    session: Session,
    terms: list[str],
    asked,
    kinds: list[str],
    space: str | tuple[str, ...] | None,
    depth: int,
) -> list[dict]:
    for mode in ("all", "prefix", "any"):
        expression = _match_expression(terms, asked.phrases, asked.excluded, mode)
        if not expression:
            return []
        try:
            rows = _candidates(session, expression, kinds, space, asked.since, asked.until, depth)
        except Exception:  # noqa: BLE001  # a malformed MATCH is a typed query, not a bug
            # The expression is built from what somebody typed, so it stays
            # out of the log line (CodeQL, log injection): a newline in a
            # search box must not be able to forge a log entry. The stage and
            # the term count say as much as the text would for debugging.
            logger.debug("FTS match failed at the %s stage over %d term(s)", mode, len(terms))
            return []
        if rows:
            return rows
    return []


def _hops_from(session: Session, root_id: int, wanted: set[int]) -> dict[int, int]:
    """How many links away each wanted note is from the open one, up to two.

    Breadth-first over `entry_links` and reply threads, one query per hop, and
    only ever asked about the candidates: this is the same walk
    `search_manager._linked_neighbours` does for chat context, kept separate
    because that one collects *neighbours to add* and this one answers *how
    far is this hit*, which wants no truncation and no strength ordering.
    """
    hops: dict[int, int] = {}
    frontier = {root_id}
    seen = {root_id}
    for distance in range(1, MAX_HOPS + 1):
        if not frontier:
            break
        neighbours: set[int] = set()
        links = session.scalars(
            select(EntryLink).where(
                or_(
                    EntryLink.source_entry_id.in_(frontier),
                    EntryLink.target_entry_id.in_(frontier),
                )
            )
        )
        for link in links:
            neighbours.add(link.source_entry_id)
            neighbours.add(link.target_entry_id)
        for parent_id, child_id in session.execute(
            select(Entry.parent_id, Entry.id).where(
                or_(Entry.parent_id.in_(frontier), Entry.id.in_(frontier)),
                Entry.parent_id.is_not(None),
            )
        ).all():
            neighbours.add(parent_id)
            neighbours.add(child_id)
        neighbours -= seen
        for entry_id in neighbours:
            if entry_id in wanted:
                hops[entry_id] = distance
        seen |= neighbours
        frontier = neighbours
    return hops


def _normalised_bm25(raw: float, best: float) -> float:
    """FTS5's bm25 as a 0-to-1 score, best in this result set being 1.

    bm25() is negative and lower-is-better, which is neither comparable with a
    cosine nor renderable. Dividing by the best score in the same result set
    keeps the *order* exactly as FTS5 ranked it while putting it on the scale
    the other two signals live on. Deliberately relative: an absolute mapping
    would need a constant that depends on notebook size and document length,
    which is precisely the tuning-per-notebook that RRF exists to avoid
    elsewhere in this app.
    """
    if best == 0:
        return 0.0
    return max(0.0, min(1.0, raw / best))


def _explain(scores: dict[str, float], row: dict, terms: list[str], hop: int | None) -> list[str]:
    """Why this hit is here, in the words the Notes list renders.

    Ordered by which signal actually carried it, so the first phrase is the
    true reason rather than a fixed sentence with numbers in it.
    """
    said: list[tuple[float, str]] = []
    title = (row.get("title") or "").lower()
    body = " ".join((row.get("body") or "").split()).lower()
    # A note's "title" is its own first line, so on a one-line note the title
    # and the body are the same words and "matched the title" would be a
    # distinction the person cannot see. Only say it when there is a title to
    # match that the body does not repeat.
    has_real_title = bool(title) and body != title
    if scores["bm25"] > 0:
        if has_real_title and any(term in title for term in terms):
            said.append((scores["bm25"] * WEIGHTS["bm25"] + 0.01, "matched the title"))
        elif (row.get("tags") or "") and any(term in (row.get("tags") or "").lower() for term in terms):
            said.append((scores["bm25"] * WEIGHTS["bm25"], "matched a tag"))
        else:
            said.append((scores["bm25"] * WEIGHTS["bm25"], "matched your words"))
    if scores["cosine"] > 0:
        said.append((scores["cosine"] * WEIGHTS["cosine"], "similar meaning"))
    if scores["graph"] > 0:
        said.append(
            (
                scores["graph"] * WEIGHTS["graph"],
                "linked to the open note" if hop == 1 else "two links from the open note",
            )
        )
    said.sort(key=lambda pair: -pair[0])
    words = [phrase for _weight, phrase in said]
    if not words:
        # Reachable when a filter alone selected the row (`kind:document`
        # with no words). Saying so beats an empty line that reads like a bug.
        words = ["matched your filters"]
    return words


def _snippet(body: str, terms: list[str], width: int = 160) -> str:
    """A line of the body around the first matching word, or its opening."""
    # The properties block is matched by the index (a search for `type:` finds
    # it) but is never what a result quotes: it is data about the note.
    stripped = strip_properties(body or "")
    flat = " ".join(stripped.split())
    if not flat:
        return ""
    lowered = flat.lower()
    at = -1
    for term in terms:
        at = lowered.find(term)
        if at >= 0:
            break
    if at < 0:
        return clip_words(flat, width)
    return window_words(flat, max(0, at - width // 3), width)


def _flag_filters(asked) -> tuple[list[str], list[str]]:
    """`is:` and `has:` as the flag words the index row carries."""
    wanted_is = [value.lower() for value in asked.filters.get("is", [])]
    wanted_has = [value.lower() for value in asked.filters.get("has", [])]
    return wanted_is, wanted_has


def _has_attachment_ids(session: Session, entry_ids: list[int]) -> set[int]:
    """Which of these notes have a file attached. One query, candidates only.

    `has:file` is the one filter a row cannot answer about itself (see
    `index.Row.flags`), so it is answered here, over the handful of rows that
    already matched, instead of by a join on every save.
    """
    if not entry_ids:
        return set()
    return set(
        session.scalars(select(Attachment.entry_id).where(Attachment.entry_id.in_(entry_ids)))
    )


#: What each `has:` word is answered from (the decision the retrieval brief
#: left open: "decide each one's source ... and answer them over the
#: candidates, never with a join on every save"). `file` and `image` read the
#: attachment table, `link` a connection either way round, `reminder` a
#: reminder pointing at the note, and `highlight` the text itself (the marks
#: are `==words==`, there is no table). A word not in this table matches nothing,
#: which is what an unknown `is:` does too: a filter nobody can satisfy must
#: not silently become no filter.
HAS_WORDS = ("file", "image", "link", "reminder", "highlight")


#: Extensions a `/media/...` upload or an attachment name is a picture by,
#: for a row whose mime was never recorded.
_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".heic", ".avif")


def _has_ids(session: Session, want: str, entry_ids: list[int]) -> set[int]:
    """Which of these notes carry `want`. One query per word, candidates only."""
    if not entry_ids:
        return set()
    if want == "file":
        return _has_attachment_ids(session, entry_ids)
    if want == "image":
        rows = session.execute(
            select(Attachment.entry_id, Attachment.mime, Attachment.filename).where(
                Attachment.entry_id.in_(entry_ids)
            )
        )
        return {
            entry_id
            for entry_id, mime, name in rows
            if str(mime or "").startswith("image/")
            or str(name or "").lower().endswith(_IMAGE_SUFFIXES)
        }
    if want == "link":
        rows = session.execute(
            select(EntryLink.source_entry_id, EntryLink.target_entry_id).where(
                or_(
                    EntryLink.source_entry_id.in_(entry_ids),
                    EntryLink.target_entry_id.in_(entry_ids),
                )
            )
        )
        wanted = set(entry_ids)
        return {end for pair in rows for end in pair if end in wanted}
    if want == "reminder":
        return set(
            session.scalars(select(Reminder.entry_id).where(Reminder.entry_id.in_(entry_ids)))
        )
    return set()


def _row_has(row, want: str, carriers: dict[str, set[int]]) -> bool:  # noqa: ANN001
    """Does one index row satisfy one `has:` word."""
    kind = row["kind"]
    if want == "file":
        return kind == "file" or row["ref_id"] in carriers["file"]
    if want == "image":
        # A picture written into the text counts wherever the text is: a
        # note, a board or a document. `![` is the markdown for one.
        if "![" in (row["body"] or ""):
            return True
        if kind == "file":
            return str(row["title"] or "").lower().endswith(_IMAGE_SUFFIXES)
        return row["ref_id"] in carriers["image"]
    if want == "reminder":
        return kind == "reminder" or row["ref_id"] in carriers["reminder"]
    if want == "highlight":
        # The marks live in the text, so the row's own body answers it
        # (`entry/highlights.py`, shared with the Library's Highlights chip).
        return has_highlight(row["body"])
    if want in carriers:
        return row["ref_id"] in carriers[want]
    return want in (row["flags"] or "").split()


def _plan_terms(q: str, asked) -> tuple:  # noqa: ANN001
    """The query's subject and the words to match on."""
    # The raw query is the fallback only when the reader found nothing *and*
    # there were no operators to find: with operators, falling back would feed
    # `kind:document` to the index as the two words "kind" and "document",
    # which match nothing and turn a filter into an empty page.
    subject = asked.subject or ("" if (asked.has_operators or asked.has_range) else q)
    terms = query_understanding.search_terms(subject)
    for phrase in asked.phrases:
        terms.extend(
            word for word in query_understanding.search_terms(phrase) if word not in terms
        )
    return subject, terms


def _search_space(session: Session, context: dict, asked) -> str | None:  # noqa: ANN001
    space = context.get("space") or (asked.filters["space"][0] if asked.filters["space"] else None)
    return space or _session_space(session)


def _candidate_rows(session: Session, q: str, subject: str, terms: list, asked, wanted_kinds: list, space, hybrid: bool, limit: int, depth: int) -> tuple:  # noqa: ANN001
    """The rows the words (or, with none, the filters) select, and the terms
    after any typo fix."""
    if not (terms or asked.phrases):
        # Nothing to match on, but something to filter by: `kind:document`,
        # `is:pinned`, `after:2026-01-01`. Answering those with an empty page
        # would be the app refusing to do the one thing §5.1 promises works
        # with no model running.
        rows = _filter_only(
            session, wanted_kinds, space, asked.since, asked.until, depth, tags=asked.filters["tag"]
        )
        if asked.excluded:
            # There is no MATCH to hang a `NOT` on here, so the exclusion is
            # applied to the rows the filters selected. Over a page of
            # candidates rather than the notebook, the same place `has:file`
            # is answered.
            rows = [row for row in rows if not _mentions(row, asked.excluded)]
        return rows, terms
    rows = _keyword_pass(session, terms, asked, wanted_kinds, space, depth)
    if not rows and terms:
        # **A typo is still a question** (ARCH-07). The vocabulary fix the
        # older path had (`search_manager._corrected_terms`: a word the
        # notes never use, replaced by the closest one they do) was never
        # reached from here, so "gardn" found nothing in the finder.
        fixed = search_manager._corrected_terms(session, terms)
        if fixed != terms:
            rows = _keyword_pass(session, fixed, asked, wanted_kinds, space, depth)
            terms = fixed
    if hybrid and terms:
        rows = _with_meaning(session, subject or q, rows, wanted_kinds, space, asked, limit)
    return rows, terms


def _having(session: Session, rows: list, wanted_has: list) -> list:
    """The rows that carry everything `has:` asked for."""
    note_ids = [row["ref_id"] for row in rows if row["kind"] in search_index.ENTRY_KINDS]
    carriers = {want: _has_ids(session, want, note_ids) for want in HAS_WORDS if want in wanted_has}
    return [row for row in rows if all(_row_has(row, want, carriers) for want in wanted_has)]


def _filter_rows(session: Session, rows: list, asked) -> list:  # noqa: ANN001
    """The rows that also carry the `is:`, `has:` and `tag:` the query named."""
    wanted_is, wanted_has = _flag_filters(asked)
    if wanted_is:
        rows = [row for row in rows if all(flag in (row["flags"] or "").split() for flag in wanted_is)]
    if wanted_has:
        rows = _having(session, rows, wanted_has)
    wanted_tags = [tag.lower() for tag in asked.filters["tag"]]
    if wanted_tags:
        # Substring rather than word equality: the tags column is a space-
        # joined list, and `tag:garden` should find a note tagged "gardening"
        # for the same reason the keyword stage tries prefixes.
        rows = [
            row for row in rows if all(tag in (row["tags"] or "").lower() for tag in wanted_tags)
        ]
    return rows


def _hit_for(row, best_raw: float, filters_only: bool, cosines: dict, hops: dict, terms: list) -> Hit | None:  # noqa: ANN001
    """One row as a ranked, explained hit, or None when it scores too low."""
    is_entry = row["kind"] in search_index.ENTRY_KINDS
    hop = hops.get(row["ref_id"]) if is_entry else None
    scores = {
        "bm25": _normalised_bm25(row["score"], best_raw),
        "cosine": max(0.0, cosines.get(row["ref_id"], 0.0)) if is_entry else 0.0,
        "graph": (1.0 / (1 + hop)) if hop else 0.0,
    }
    blended = sum(WEIGHTS[name] * value for name, value in scores.items())
    if filters_only:
        # A filter matched, nothing was ranked: every row is equally an
        # answer, and MIN_SCORE would throw the whole list away.
        blended = max(blended, MIN_SCORE)
    # Three floats from three subsystems: a NaN here would sort
    # unpredictably and do its damage nowhere near its cause, which is a
    # shape this project has already paid an afternoon for once.
    if not math.isfinite(blended) or blended < MIN_SCORE:
        return None
    return Hit(
        kind=row["kind"],
        ref_id=row["ref_id"],
        source=row["source"],
        title=row["title"] or _snippet(row["body"], terms, 60),
        snippet=_snippet(row["body"], terms),
        scores=scores,
        score=blended,
        explain=_explain(scores, row, terms, hop),
        space=row["space"],
        written=row["written"],
        flags=row["flags"],
    )


def _rank_rows(session: Session, rows: list, subject: str, q: str, terms: list, context: dict, hybrid: bool) -> list[Hit]:
    best_raw = min(row["score"] for row in rows)  # bm25: more negative is better
    filters_only = best_raw == 0 and not any(row.get("by_meaning") for row in rows)
    cosines: dict[int, float] = _cosine_scores(session, subject or q, rows) if hybrid else {}
    # Settings' "last search" line reads one record for both search paths.
    search_manager.note_search_mode("hybrid" if cosines else "keyword")
    hops: dict[int, int] = {}
    open_entry = context.get("entry_id")
    if open_entry:
        note_ids = {row["ref_id"] for row in rows if row["kind"] in search_index.ENTRY_KINDS}
        if note_ids:
            hops = _hops_from(session, int(open_entry), note_ids)
    hits = [hit for hit in (_hit_for(row, best_raw, filters_only, cosines, hops, terms) for row in rows) if hit is not None]
    hits.sort(key=lambda hit: (-hit.score, hit.kind, -hit.ref_id))
    return hits


def search(
    session: Session,
    q: str,
    ctx: dict | None = None,
    *,
    limit: int = 20,
    hybrid: bool = True,
    kinds: list[str] | None = None,
    depth: int = CANDIDATE_DEPTH,
) -> list[Hit]:
    """Search everything, and say why each answer is an answer.

    `ctx` is what the person is looking at: `{"entry_id": 12, "space": "work"}`.
    Both parts are optional; without an `entry_id` the graph signal is zero for
    every hit, which is honest rather than absent, and the other two still
    rank.

    `hybrid=False` is the keyword-only path: the perf gate the spec sets (an
    FTS-only answer in under 50ms on 5,000 notes) and the mode a notebook with
    no embedding backend is permanently in.
    """
    asked = query_understanding.understand(q)
    subject, terms = _plan_terms(q, asked)
    context = ctx or {}
    space = _search_space(session, context, asked)
    wanted_kinds = [kind for kind in (kinds or asked.filters["kind"]) if kind in search_index.KINDS]

    # Something has to be *asked for*. An empty box, or a query that is only
    # `-rice`, names nothing to find: listing the whole notebook for it would
    # be the search box answering a question nobody put. The Notes list is
    # already showing every note when the box is empty; a search that also
    # returns every note is not an answer, it is noise with a scrollbar.
    if not (terms or asked.phrases or any(asked.filters.values()) or asked.has_range):
        return []
    rows, terms = _candidate_rows(session, q, subject, terms, asked, wanted_kinds, space, hybrid, limit, depth)
    rows = _filter_rows(session, rows, asked) if rows else rows
    if not rows:
        return []
    return _rank_rows(session, rows, subject, q, terms, context, hybrid)[:limit]


#: Notes meaning alone may add to a search: a handful at the end of the
#: words' answers, not a second list.
MEANING_EXTRA = 5
#: How far above this query's mean score (in standard deviations) a note
#: only meaning found must be, and the notebook size that spread needs.
MEANING_Z = 2.0
MEANING_MIN_NOTES = 20
#: The cosine a note must reach in a notebook too small for a spread.
MEANING_SMALL_NOTEBOOK = 0.65


def _with_meaning(
    session: Session, subject: str, rows: list[dict], kinds: list[str], space, asked, limit: int  # noqa: ANN001
) -> list[dict]:
    """The keyword candidates, and the notes nearest the query in meaning.

    **Cosine used to only re-rank keyword hits** (audit 2026-10-05, ARCH-07):
    candidates came from the FTS pass alone, so "horticulture" or "vegetable
    patch" found nothing in a notebook of garden notes, and "one index, three
    signals" was one signal deciding and two re-ordering. The matrix's top-k
    for the query vector joins the candidates here (index rows, so every
    filter below still applies); a row only meaning brought has a bm25 of
    zero and is ranked by its cosine. Nothing changes with no embedding
    backend: no vector, no extra rows.
    """
    if kinds and not set(kinds) & set(search_index.ENTRY_KINDS):
        return rows
    matrix = _live_matrix(session)
    if matrix is None:
        backend = _backend_id()
        if backend is None:
            return rows
        warm_vectors(session, backend)
        matrix = _live_matrix(session)
        if matrix is None:
            return rows
    try:
        deps = importlib.import_module("tessellate.core.deps")
        vector = deps.get_embeddings().embed_text(subject)
        floor, _margin = search_manager.configured_thresholds()
    except Exception:  # noqa: BLE001  # an embedding failure must not fail a search
        return rows
    if vector is None:
        return rows
    import numpy as np

    query = np.asarray(vector, dtype="float32")
    norm = float(np.linalg.norm(query))
    if norm == 0:
        return rows
    with _matrix_lock:
        if not matrix.ids:
            return rows
        scores = matrix.rows @ (query / norm)
        ids = np.asarray(matrix.ids)
        live = matrix.live() & (ids >= 0)
    # **A source of candidates has to be surer than a re-ranker.** BGE-family
    # vectors sit in a narrow cone, so an unrelated note scores 0.4 to 0.6
    # (`search_manager.semantic_search` says the same at length): measured in
    # the finder here, "gardn" brought three notes about a meeting with Sam
    # at the absolute floor alone. A note only meaning found must stand
    # `MEANING_Z` deviations above this query's own scores over the notebook,
    # or past `MEANING_SMALL_NOTEBOOK` when there are too few notes for a
    # spread to mean anything.
    valid = scores[live]
    if valid.size >= MEANING_MIN_NOTES:
        relative = float(np.mean(valid) + MEANING_Z * np.std(valid))
    else:
        relative = MEANING_SMALL_NOTEBOOK
    floor = max(floor, relative)
    have = {row["ref_id"] for row in rows if row["kind"] in search_index.ENTRY_KINDS}
    order = np.argsort(-np.where(live, scores, -np.inf))[: MEANING_EXTRA + len(have)]
    nearest = [
        int(ids[i]) for i in order if live[i] and float(scores[i]) >= floor and int(ids[i]) not in have
    ][:MEANING_EXTRA]
    if not nearest:
        return rows
    wanted = [kind for kind in (kinds or search_index.ENTRY_KINDS) if kind in search_index.ENTRY_KINDS]
    params: dict = {}
    names = {f"id{i}": entry_id for i, entry_id in enumerate(nearest)}
    params.update(names)
    kind_names = {f"kind{i}": kind for i, kind in enumerate(wanted)}
    params.update(kind_names)
    sql = [
        "SELECT rowid, kind, ref_id, source, title, body, tags, space, flags, written, "
        "0.0 AS score FROM search_index WHERE kind IN ("
        + ", ".join(f":{name}" for name in kind_names)
        + ") AND ref_id IN ("
        + ", ".join(f":{name}" for name in names)
        + ")"
    ]
    sql.extend(_space_clause(space, params))
    if asked.since is not None:
        sql.append("AND (written = '' OR written >= :since)")
        params["since"] = asked.since.isoformat()
    if asked.until is not None:
        sql.append("AND (written = '' OR written <= :until)")
        params["until"] = asked.until.isoformat()
    extra = [dict(row) | {"by_meaning": True} for row in session.execute(text(" ".join(sql)), params).mappings().all()]
    if asked.excluded:
        extra = [row for row in extra if not _mentions(row, asked.excluded)]
    return rows + extra


def _cosine_scores(session: Session, subject: str, rows: list[dict]) -> dict[int, float]:
    """Cosine for the candidates, from the matrix, without loading anything.

    Returns `{}` when there is no embedding backend or the matrix is cold,
    which leaves the cosine column at zero and the other two signals ranking:
    the app has to be excellent with the model off (WORLD_CLASS_PLAN §5).
    """
    matrix = _live_matrix(session)
    if matrix is None:
        # Cold, but this is the search path rather than the "see also" panel,
        # and a person who just typed a query is waiting for the best answer
        # this notebook can give. One build, once per process; `related()`
        # deliberately does not do this (see its own docstring).
        backend = _backend_id()
        if backend is None:
            return {}
        warm_vectors(session, backend)
        matrix = _live_matrix(session)
        if matrix is None:
            return {}
    try:
        # The same wrong-direction edge as `_backend_id`, broken the same way.
        deps = importlib.import_module("tessellate.core.deps")

        vector = deps.get_embeddings().embed_text(subject)
    except Exception:  # noqa: BLE001  # an embedding failure must not fail a search
        return {}
    if vector is None:
        return {}
    import numpy as np

    wanted = [row["ref_id"] for row in rows if row["kind"] in search_index.ENTRY_KINDS]
    query = np.asarray(vector, dtype="float32")
    scores = matrix.scores_for(query, wanted)
    if scores and search_chunks.ENABLED:
        # The note's best paragraph where it beats the note (row 6).
        for entry_id, best in search_chunks.best_paragraphs(
            session, query, matrix.backend or (_backend_id() or ""), matrix, only=set(scores)
        ).items():
            if best.score > scores.get(entry_id, 0.0):
                scores[entry_id] = best.score
    return scores


def related(session: Session, entry_id: int, k: int = 10) -> list[tuple[int, float]]:
    """Notes that mean something similar to this one, best first.

    `[(entry_id, cosine), …]`, and **no scan**: it reads the matrix that the
    writes keep current and nothing else. That is the behaviour the spec pins
    (`test_similarity_does_not_scan_every_vector`), and the reason is measured
    rather than theoretical: the path this replaces re-read every stored
    vector, stacked a fresh array and rebuilt an ORM entity per candidate, on
    every open of a note.

    A cold matrix returns nothing rather than building one. This is a "see
    also" panel; startup warms the matrix (`api/app.py`), so the empty case is
    the first seconds of a process, and the alternative is every note-open in
    a cold process paying for a full scan.
    """
    matrix = _live_matrix(session)
    if matrix is None:
        return []
    position = matrix.position.get(int(entry_id))
    if position is None:
        return []
    return matrix.top_k(matrix.rows[position], k, exclude=int(entry_id))


def vectors_by_id(session: Session, only: set[int] | None = None) -> dict[int, "np.ndarray"]:
    """Every vector the matrix holds, as `{entry_id: unit vector}`.

    For the three whole-notebook features that genuinely do need all of them
    at once (link suggestions, tensions, the graph's similarity edges): they
    compare every pair, so there is no top-k to take. What they no longer do
    is *re-read and re-parse* the blobs: each was selecting every
    `EmbeddingRecord` row and calling `bytes_to_vector` on it, per request,
    for data this process already has in one array.

    Rows are unit-normalised, which is what `embeddings.similar_pairs` does to
    them first thing anyway.
    """
    backend = _backend_id()
    if backend is None:
        return {}
    # `current_matrix`, not `_live_matrix`: these compare every pair and the
    # two in `routes_entries` are cached on the matrix's version, so a vector
    # a bulk delete took out of the table has to leave here too, or the cache
    # would go on suggesting a link from a note's old text.
    matrix = current_matrix(session, backend)
    if matrix is None:
        return {}
    return {
        entry_id: matrix.rows[position]
        for entry_id, position in matrix.position.items()
        if only is None or entry_id in only
    }


#: `{threshold: ((matrix key, matrix version), pairs)}`. One slot per
#: threshold, not an LRU, for the reason `routes_graph._cached` gives: only the
#: current vector set is ever asked for. Two thresholds are in use (link
#: suggestions at 0.55, tensions at 0.45), so this holds two lists.
_pairs_cache: dict[float, tuple[tuple[str, int], list[tuple[int, int, float]]]] = {}
_pairs_lock = threading.Lock()


#: Each note's best partners kept, at most (a pair stays if it is in either
#: end's). Uncapped, the pair list was every pair over the threshold: on the
#: audit's 5,000-note notebook 90% of pairs passed 0.55 and
#: `/entries/link-suggestions` did not finish in minutes (audit 2026-10-05,
#: ARCH-11). Link suggestions and tensions read the best few per note anyway.
PAIRS_PER_NOTE = 12


def cached_similar_pairs(
    session: Session, threshold: float, only: set[int] | None = None
) -> list[tuple[int, int, float]]:
    """`embeddings.similar_pairs` over the matrix, computed once per vector set.

    WORLD_CLASS_PLAN row 9 (§16). The all-pairs comparison is O(n²) and link
    suggestions and tensions ran it on every request; the graph had cached its
    own since 2026-09-08. The key is the matrix's `(key, version)`: the
    version moves on every change to a row, whether the flush hook made it or
    `current_matrix` caught up with a bulk delete, so there is no fingerprint
    here to forget to widen.

    Computed over every vector the matrix holds, and `only` applied to the
    result: a pair among a subset is exactly a pair of the whole whose two
    ends are both in the subset (the matrix is one width, so `similar_pairs`'
    majority-width rule picks the same rows either way). That is what lets
    the two callers, which want different notes (tensions leave boards out),
    share one comparison per threshold. Best first, as `similar_pairs` is.
    """
    backend = _backend_id()
    if backend is None:
        return []
    matrix = current_matrix(session, backend)
    if matrix is None:
        return []
    with _matrix_lock:
        version = (matrix.key, matrix.version)
        with _pairs_lock:
            hit = _pairs_cache.get(float(threshold))
        pairs = hit[1] if hit is not None and hit[0] == version else None
        if pairs is None:
            vectors = {
                entry_id: matrix.rows[position].copy() for entry_id, position in matrix.position.items()
            }
    if pairs is None:
        # Looked up on the module at call time, not imported by name, so a
        # test counting the comparisons sees this call.
        embeddings_module = importlib.import_module("tessellate.ai.embeddings")
        pairs = embeddings_module.similar_pairs(vectors, threshold, per_node=PAIRS_PER_NOTE)
        with _pairs_lock:
            _pairs_cache[float(threshold)] = (version, pairs)
    if only is None:
        return list(pairs)
    return [pair for pair in pairs if pair[0] in only and pair[1] in only]


def stats(session: Session) -> dict:
    """What the engine has to work with, for `/search/stats` and for a report."""
    matrix = _live_matrix(session)
    return {
        "index": index_counts(session),
        "vectors": (len(matrix.ids) - matrix.dead) if matrix else 0,
        "vectors_warm": matrix is not None,
        "weights": dict(WEIGHTS),
        #: `{at, rows}` from the last full rebuild in this process, or None.
        #: Beside `index` so a drift is readable: rows now against rows then.
        "last_rebuild": search_index.last_rebuild(),
    }
