"""A 2-D "map of my notes" (L-graph-2): where each note sits when its stored
meaning vector is flattened to a plane.

PCA: centre the vectors, keep the two directions they vary most along, read
from the d x d covariance (`eigh`) in float32 rather than an SVD of the n x d
matrix in float64 (review 5883476033; 384 wide, measured here: 0.03 s against
0.23 s at 5,000 notes, 0.09 s against 0.61 s at 20,000). Nothing is trained
and nothing is sent anywhere, and the same notes always give the same picture (each axis's sign is fixed). Notes
come from `routes_graph._note_vectors`, so the rules are the similarity
lines' own: live, not a draft or a board, never a private note (it has no
vector), only the current embedding backend's vectors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from tessellate.api import meaning_map, routes_graph
from tessellate.core import deps
from tessellate.core.deps import get_session

if TYPE_CHECKING:
    import numpy as np

router = APIRouter(tags=["graph"])

#: The most notes one picture places. Past it the notes are sampled evenly
#: over their ids, so the map shows the whole notebook's spread rather than
#: its oldest corner; a note left out sits in the row under the map, as a
#: note with no vector does.
MAX_PROJECTED = 5000


def sample(ids: list[int], cap: int) -> list[int]:
    """At most `cap` of the sorted `ids`, evenly spaced, first and last kept."""
    if len(ids) <= cap:
        return ids
    if cap == 1:
        return ids[:1]
    step = (len(ids) - 1) / (cap - 1)
    return [ids[round(k * step)] for k in range(cap)]


def lay_out(vectors: dict[int, np.ndarray], cap: int = MAX_PROJECTED):
    """`(ids, plane, idx, sim)`: the notes in the unit square, one scale on
    both axes so the picture is not stretched, each drawn toward its nearest
    neighbours by meaning (`meaning_map.pull_together`), and those neighbours."""
    # Imported here: numpy stays out of the app's start (test_lazy_heavy_imports).
    import numpy as np

    ids = sample(sorted(vectors), cap)
    if len(ids) == 1:
        return ids, np.array([[0.5, 0.5]]), np.zeros((1, 0), dtype=np.int64), np.zeros((1, 0), dtype=np.float32)
    matrix = np.stack([np.asarray(vectors[i], dtype=np.float32) for i in ids])
    centred = matrix - matrix.mean(axis=0)
    # `eigh` answers in ascending order: the last two columns are the axes.
    _, eigvecs = np.linalg.eigh(centred.T @ centred)
    plane = centred @ eigvecs[:, ::-1][:, :2]
    if plane.shape[1] < 2:
        plane = np.hstack([plane, np.zeros((len(ids), 2 - plane.shape[1]), dtype=np.float32)])
    for k in range(2):
        # An axis is only defined up to its sign: pin it to the notes.
        if plane[np.argmax(np.abs(plane[:, k])), k] < 0:
            plane[:, k] = -plane[:, k]
    idx, sim = meaning_map.neighbours(matrix, meaning_map.PULL_K)
    plane = meaning_map.pull_together(plane, idx, sim)
    low = plane.min(axis=0)
    span = max(float((plane.max(axis=0) - low).max()), 1e-9)
    scaled = (plane - low) / span
    pad = (1.0 - scaled.max(axis=0)) / 2
    return ids, scaled + pad, idx, sim


def project(vectors: dict[int, np.ndarray], cap: int = MAX_PROJECTED) -> dict[int, tuple[float, float]]:
    """`{id: (x, y)}` in the unit square."""
    if not vectors:
        return {}
    ids, plane, _, _ = lay_out(vectors, cap)
    return {i: (round(float(x), 4), round(float(y), 4)) for i, (x, y) in zip(ids, plane)}


def build(session: Session, backend: str, limit: int) -> dict:
    """The picture: points, the faint ties between near notes, the named
    clusters, and what placed them (`model`, or the notes' `words` when no
    embedding model has made a vector yet)."""
    from sqlalchemy import select

    from tessellate.core.database import Entry
    from tessellate.repo import graph_layers

    vectors = routes_graph._note_vectors(session, backend)
    source = "model"
    wanted = graph_layers.vector_note_ids(session)
    texts = dict(session.execute(select(Entry.id, Entry.content).where(Entry.id.in_(wanted))).all()) if wanted else {}
    if not vectors:
        source = "words"
        vectors = meaning_map.word_vectors(dict(sorted(texts.items())[:MAX_PROJECTED * 2]))
    if not vectors:
        return {"points": [], "ties": [], "clusters": [], "source": source}
    ids, plane, idx, sim = lay_out(vectors, limit)
    return {
        "points": [
            {"id": i, "x": round(float(x), 4), "y": round(float(y), 4)} for i, (x, y) in zip(ids, plane)
        ],
        "ties": meaning_map.ties(ids, idx, sim, source),
        "clusters": meaning_map.clusters(ids, plane, texts),
        "source": source,
    }


@router.get("/graph/projection")
def graph_projection(
    session: Session = Depends(get_session),
    limit: int = Query(MAX_PROJECTED, ge=1, le=MAX_PROJECTED),
) -> dict:
    backend = deps.get_embeddings().backend_id()
    fingerprint = (*routes_graph._vector_fingerprint(session, backend), limit)
    return routes_graph._cached("projection", fingerprint, lambda: build(session, backend, limit))
