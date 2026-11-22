"""Paragraph vectors in memory (WORLD_CLASS_PLAN §14 item 3, row 6).

`ChunkVector` holds a vector per paragraph of every long note; this module
keeps them as one unit-row matrix, the way `engine._Matrix` keeps the note
vectors, and answers one question: for this query vector, what is each note's
best paragraph, and how close is it?

**A note's meaning score is the better of its own vector and its best
paragraph's.** One vector per note dilutes a long note: a page about the
house that mentions the boiler in one paragraph is, to a question about the
boiler, a twentieth relevant. Its best paragraph is not diluted at all. The
note vector stays in the maximum because a short question about what the
whole note is about ("my house notes") is better answered by the whole.

**Kept in step by asking, not by hooks.** The note matrix has an ORM hook
because a save must show in the next search at once and its table is read
by many paths. This one is read only here, so it compares the table's
`(count, max(id), total(id))` with what it last loaded (a tenth of a
millisecond) and, when that has moved, fetches the rows it has not seen and
zeroes the ones that left. A save of a long note is therefore one small
fetch on the next search, never a reload.

**A chunk counts only beside its own note vector.** Each row names the
`embeddings.id` it was cut beside; a row whose note vector has since been
deleted or replaced (purge, private, a re-embed by bulk statement) is
skipped, which is what lets ten delete sites stay ignorant of this table.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from tessellate.core.database import ChunkVector
from tessellate.search import matrix_hooks

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)

#: The switch the before-and-after measurement flips (and a way out, should
#: paragraph scores ever misrank on some backend): off, a note scores on its
#: own vector alone, as every note did before row 6.
ENABLED = True

#: Past this many unseen rows a full reload is cheaper than fetching by id.
RELOAD_AT = 2000
#: Dead rows are compacted away once they are a quarter of the matrix.
COMPACT_MIN_DEAD = 32


@dataclass
class _Chunks:
    key: str
    backend: str
    width: int = 0
    fingerprint: tuple | None = None
    row_ids: list[int] = field(default_factory=list)
    position: dict[int, int] = field(default_factory=dict)
    #: Parallel arrays, one entry per row of `rows`.
    meta: "np.ndarray | None" = None  # int64 columns: entry, embedding, ordinal, start, end
    rows: "np.ndarray | None" = None
    dead: int = 0
    version: int = 0
    _valid_key: tuple | None = None
    _valid: "np.ndarray | None" = None


_state: _Chunks | None = None
_lock = threading.RLock()


def _fingerprint(session: Session) -> tuple:
    row = session.execute(text("SELECT count(*), max(id), total(id) FROM chunk_vectors")).one()
    return (int(row[0]), row[1], float(row[2] or 0))


def _key(session: Session, backend_id: str) -> str:
    return f"{getattr(session.get_bind(), 'url', '')}|{backend_id}"


def _unit_rows(blobs: list[bytes], width: int) -> tuple["np.ndarray", list[bool]]:
    import numpy as np

    keep = [len(blob) == width * 4 for blob in blobs]
    if not any(keep):
        return np.zeros((0, width), dtype="float32"), keep
    rows = np.stack([np.frombuffer(blob, dtype="float32") for blob, ok in zip(blobs, keep) if ok])
    norms = np.linalg.norm(rows, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (rows / norms).astype("float32"), keep


def _append(state: _Chunks, fetched: list[tuple]) -> None:
    """Add `(id, entry, embedding, ordinal, start, end, blob)` rows."""
    import numpy as np

    if not fetched:
        return
    if not state.width:
        widths: dict[int, int] = {}
        for row in fetched:
            widths[len(row[6]) // 4] = widths.get(len(row[6]) // 4, 0) + 1
        state.width = max(widths, key=lambda width: widths[width])
        state.rows = np.zeros((0, state.width), dtype="float32")
        state.meta = np.zeros((0, 5), dtype="int64")
    rows, keep = _unit_rows([row[6] for row in fetched], state.width)
    kept = [row for row, ok in zip(fetched, keep) if ok]
    if not kept:
        return
    meta = np.asarray([row[1:6] for row in kept], dtype="int64")
    base = len(state.row_ids)
    for offset, row in enumerate(kept):
        state.row_ids.append(int(row[0]))
        state.position[int(row[0])] = base + offset
    state.rows = np.vstack([state.rows, rows])
    state.meta = np.vstack([state.meta, meta])


def _fetch(session: Session, backend_id: str, ids: list[int] | None) -> list[tuple]:
    columns = (
        ChunkVector.id,
        ChunkVector.entry_id,
        ChunkVector.embedding_id,
        ChunkVector.ordinal,
        ChunkVector.start,
        ChunkVector.end,
        ChunkVector.embedding,
    )
    if ids is None:
        return [
            tuple(row)
            for row in session.execute(
                select(*columns).where(ChunkVector.model_version == backend_id).order_by(ChunkVector.id)
            ).all()
        ]
    out: list[tuple] = []
    for start in range(0, len(ids), 400):  # under SQLite's variable limit
        out.extend(
            tuple(row)
            for row in session.execute(
                select(*columns).where(ChunkVector.id.in_(ids[start : start + 400]))
            ).all()
        )
    return out


def _forget(state: _Chunks, row_id: int) -> None:
    position = state.position.pop(row_id, None)
    if position is None:
        return
    state.row_ids[position] = -1
    state.rows[position] = 0.0
    state.meta[position, 0] = -1
    state.dead += 1


def _compact(state: _Chunks) -> None:
    keep = [i for i, row_id in enumerate(state.row_ids) if row_id >= 0]
    state.rows = state.rows[keep]
    state.meta = state.meta[keep]
    state.row_ids = [state.row_ids[i] for i in keep]
    state.position = {row_id: i for i, row_id in enumerate(state.row_ids)}
    state.dead = 0


def current(session: Session, backend_id: str) -> _Chunks | None:
    """The paragraph matrix for this notebook and backend, brought up to date."""
    global _state
    try:
        fingerprint = _fingerprint(session)
    except Exception:  # noqa: BLE001  # no table yet (an old database mid-upgrade)
        logger.debug("current: no table yet (an old database mid-upgrade)", exc_info=True)
        return None
    key = _key(session, backend_id)
    with _lock:
        state = _state
        if state is not None and state.key == key and state.fingerprint == fingerprint:
            return state
        if state is None or state.key != key:
            state = _Chunks(key=key, backend=backend_id)
            _append(state, _fetch(session, backend_id, None))
        else:
            table = {
                int(row_id)
                for (row_id,) in session.connection()
                .exec_driver_sql("SELECT id FROM chunk_vectors WHERE model_version = ?", (backend_id,))
                .fetchall()
            }
            gone = [row_id for row_id in state.position if row_id not in table]
            new = sorted(table.difference(state.position))
            if len(new) > RELOAD_AT:
                state = _Chunks(key=key, backend=backend_id)
                _append(state, _fetch(session, backend_id, None))
            else:
                for row_id in gone:
                    _forget(state, row_id)
                _append(state, _fetch(session, backend_id, new))
                if state.dead >= max(COMPACT_MIN_DEAD, len(state.row_ids) // 4):
                    _compact(state)
        state.fingerprint = fingerprint
        state.version += 1
        state._valid_key = None
        _state = state
        return state


def _valid_rows(state: _Chunks, note_matrix) -> tuple:  # noqa: ANN001
    """`(index, note_rows, grouped_index, starts, group_rows)`: the rows that
    count (alive, and cut beside the note's live vector), each one's row in
    the note matrix, and the same rows grouped by note. Cached until either
    matrix changes, so a query pays for none of it."""
    import numpy as np

    key = (state.version, note_matrix.version, note_matrix.fingerprint, id(note_matrix))
    if state._valid_key == key and state._valid is not None:
        return state._valid
    seen = note_matrix.seen
    position = note_matrix.position
    index: list[int] = []
    note_rows: list[int] = []
    for i, (entry, embedding_id) in enumerate(state.meta[:, :2].tolist()):
        row = position.get(entry)
        if entry >= 0 and row is not None and seen.get(entry) == embedding_id:
            index.append(i)
            note_rows.append(row)
    index_array = np.asarray(index, dtype="int64")
    rows_array = np.asarray(note_rows, dtype="int64")
    # Grouped by note row once here, so a query takes each note's best
    # paragraph with one `maximum.reduceat` rather than `maximum.at`, which
    # is unbuffered and the slowest thing in the lift at 15,000 rows.
    order = np.argsort(rows_array, kind="stable")
    grouped_index, grouped_rows = index_array[order], rows_array[order]
    starts = np.flatnonzero(np.r_[True, grouped_rows[1:] != grouped_rows[:-1]]) if grouped_rows.size else grouped_rows
    valid = (index_array, rows_array, grouped_index, starts, grouped_rows[starts] if grouped_rows.size else grouped_rows)
    state._valid_key, state._valid = key, valid
    return valid


def _scores(state: _Chunks, vector) -> "np.ndarray | None":  # noqa: ANN001
    """Cosine of every row against `vector`, or None when it cannot be scored."""
    import numpy as np

    query = np.asarray(vector, dtype="float32")
    if state.rows is None or query.shape[0] != state.width:
        return None
    norm = float(np.linalg.norm(query))
    if norm == 0:
        return None
    # `einsum`, not `@`, for the reason `search_manager._score_from_matrix`
    # measured: a product this size is memory-bound and BLAS's thread pool
    # wake-up is most of its cost on a busy machine (here, 57 ms to 1 ms).
    return np.einsum("ij,j->i", state.rows, query / np.float32(norm))


@dataclass(frozen=True)
class Best:
    """A note's best paragraph for one query."""

    score: float
    ordinal: int
    start: int
    end: int


def best_paragraphs(
    session: Session,
    vector,  # noqa: ANN001
    backend_id: str,
    note_matrix,  # noqa: ANN001  # engine._Matrix, for the live-vector rule
    only: set[int] | None = None,
) -> dict[int, Best]:
    """`{entry_id: Best}` for every note with paragraph vectors (or only these).

    Empty when there are none, the widths disagree, or anything goes wrong:
    a paragraph score refines a search and must never fail one.
    """
    if note_matrix is None:
        return {}
    try:
        import numpy as np

        with _lock:
            state = current(session, backend_id)
            if state is None or not state.row_ids:
                return {}
            all_scores = _scores(state, vector)
            if all_scores is None:
                return {}
            index = _valid_rows(state, note_matrix)[0]
            meta = state.meta[index]
        if only is not None:
            keep = np.isin(meta[:, 0], np.fromiter(only, dtype="int64", count=len(only)))
            index, meta = index[keep], meta[keep]
        if index.size == 0:
            return {}
        scores = all_scores[index]
        # Best row per note: sort by (entry, -score) and keep each entry's first.
        order = np.lexsort((-scores, meta[:, 0]))
        entries = meta[order, 0]
        first = np.ones(order.size, dtype=bool)
        first[1:] = entries[1:] != entries[:-1]
        out: dict[int, Best] = {}
        for i in order[first].tolist():
            entry, _embedding, ordinal, start, end = meta[i].tolist()
            out[int(entry)] = Best(float(scores[i]), int(ordinal), int(start), int(end))
        return out
    except Exception:  # noqa: BLE001  # see the docstring
        logger.debug("paragraph scores unavailable", exc_info=True)
        return {}


def lift(session: Session, backend_id: str, vector, ids: list[int], scores):  # noqa: ANN001
    """`scores` (one per id, the note vectors' cosines, in the note matrix's
    row order as `engine.vector_view` hands them out) raised to each note's
    best paragraph where that is higher. The same array when there is nothing
    to raise; never fails a search."""
    if not ENABLED or not ids:
        return scores
    try:

        import numpy as np

        # `matrix_hooks`: the engine imports `search_manager`, which calls this.
        engine = matrix_hooks.engine()
        note_matrix = engine.current_matrix(session, backend_id)
        if note_matrix is None or len(note_matrix.ids) != len(ids):
            return scores
        with _lock:
            state = current(session, backend_id)
            if state is None or not state.row_ids:
                return scores
            all_scores = _scores(state, vector)
            if all_scores is None:
                return scores
            _index, _rows, grouped, starts, group_rows = _valid_rows(state, note_matrix)
        if grouped.size == 0:
            return scores
        best = np.maximum.reduceat(all_scores[grouped].astype("float32"), starts)
        raised = np.array(scores, dtype="float32", copy=True)
        raised[group_rows] = np.maximum(raised[group_rows], best)
        return raised
    except Exception:  # noqa: BLE001  # a refinement, never a failure
        logger.debug("paragraph lift skipped", exc_info=True)
        return scores


def paragraphs_of(session: Session, entry_id: int, backend_id: str) -> list[tuple[int, int, int, "np.ndarray"]]:
    """`[(ordinal, start, end, unit vector)]` for one note, from the table.

    For grounding, which scores a handful of notes' paragraphs against an
    answer sentence and has no reason to touch the whole matrix.
    """
    import numpy as np

    rows = session.execute(
        select(ChunkVector.ordinal, ChunkVector.start, ChunkVector.end, ChunkVector.embedding)
        .where(ChunkVector.entry_id == entry_id, ChunkVector.model_version == backend_id)
        .order_by(ChunkVector.ordinal)
    ).all()
    out = []
    for ordinal, start, end, blob in rows:
        vector = np.frombuffer(blob, dtype="float32")
        norm = float(np.linalg.norm(vector))
        out.append((int(ordinal), int(start), int(end), vector / norm if norm else vector))
    return out


def reset() -> None:
    """Drop the in-memory matrix (tests, and a notebook switch)."""
    global _state
    with _lock:
        _state = None


def stats() -> dict:
    state = _state
    if state is None:
        return {"rows": 0, "dead": 0, "width": 0}
    return {"rows": len(state.row_ids) - state.dead, "dead": state.dead, "width": state.width}


def meaning_scorer(session: Session, embeddings):  # noqa: ANN001, ANN201
    """`score(sentence, note_id, start, end) -> cosine | None` for grounding.

    The evidence card's meaning signal (WORLD_CLASS_PLAN I6): an answer
    sentence against the paragraph its passage sits in, or against the note's
    own vector when the note is one paragraph. None when there is no backend
    ready, so a card never shows a meaning bar the app could not measure.
    Each note's vectors are read once per answer, not once per sentence.
    """
    try:
        if embeddings is None or not embeddings.is_ready():
            return None
        backend = embeddings.backend_id()
    except Exception:  # noqa: BLE001  # no backend is a state, not an error
        logger.debug("meaning_scorer: no backend is a state, not an error", exc_info=True)
        return None
    import numpy as np

    from tessellate.core.database import EmbeddingRecord

    cache: dict[int, tuple[list, "np.ndarray | None"]] = {}

    def vectors(note_id: int):  # noqa: ANN202
        if note_id not in cache:
            note = session.scalar(
                select(EmbeddingRecord.embedding).where(
                    EmbeddingRecord.entry_id == note_id, EmbeddingRecord.model_version == backend
                )
            )
            whole = None
            if note is not None:
                whole = np.frombuffer(note, dtype="float32")
                norm = float(np.linalg.norm(whole))
                whole = whole / norm if norm else None
            cache[note_id] = (paragraphs_of(session, note_id, backend) if whole is not None else [], whole)
        return cache[note_id]

    def score(sentence: str, note_id: int, start: int | None, end: int | None) -> float | None:
        paragraphs, whole = vectors(note_id)
        if whole is None:
            return None
        target = whole
        if start is not None and paragraphs:
            # The paragraph the passage overlaps most, as
            # `grounding.paragraph_ordinal` picks it.
            stop = end if end is not None and end > start else start + 1
            overlap, vector = max(
                ((min(stop, last) - max(start, first), vector) for _o, first, last, vector in paragraphs),
                key=lambda pair: pair[0],
            )
            if overlap > 0:
                target = vector
        query = embeddings.embed_text(sentence)
        if query is None:
            return None
        query = np.asarray(query, dtype="float32")
        norm = float(np.linalg.norm(query))
        if not norm or query.shape[0] != target.shape[0]:
            return None
        return float(np.dot(query / norm, target))

    return score
