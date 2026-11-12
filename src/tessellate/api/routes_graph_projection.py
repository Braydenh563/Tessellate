"""A 2-D "map of my notes" (L-graph-2): where each note sits when its stored
meaning vector is flattened to a plane.

PCA through numpy's SVD: centre the vectors, keep the two directions they
vary most along. Nothing is trained and nothing is sent anywhere, and the
same notes always give the same picture (each axis's sign is fixed). Notes
come from `routes_graph._note_vectors`, so the rules are the similarity
lines' own: live, not a draft or a board, never a private note (it has no
vector), only the current embedding backend's vectors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from tessellate.api import routes_graph
from tessellate.core import deps
from tessellate.core.deps import get_session

if TYPE_CHECKING:
    import numpy as np

router = APIRouter(tags=["graph"])


def project(vectors: dict[int, np.ndarray]) -> dict[int, tuple[float, float]]:
    """`{id: (x, y)}` in the unit square, one scale on both axes so the
    picture is not stretched."""
    # Imported here: numpy stays out of the app's start (test_lazy_heavy_imports).
    import numpy as np

    if not vectors:
        return {}
    ids = sorted(vectors)
    if len(ids) == 1:
        return {ids[0]: (0.5, 0.5)}
    matrix = np.array([np.asarray(vectors[i], dtype=float) for i in ids])
    centred = matrix - matrix.mean(axis=0)
    _, _, axes = np.linalg.svd(centred, full_matrices=False)
    plane = centred @ axes[:2].T
    if plane.shape[1] < 2:
        plane = np.hstack([plane, np.zeros((len(ids), 2 - plane.shape[1]))])
    for k in range(2):
        # An SVD axis is only defined up to its sign: pin it to the notes.
        if plane[np.argmax(np.abs(plane[:, k])), k] < 0:
            plane[:, k] = -plane[:, k]
    low = plane.min(axis=0)
    span = max(float((plane.max(axis=0) - low).max()), 1e-9)
    scaled = (plane - low) / span
    pad = (1.0 - scaled.max(axis=0)) / 2
    scaled = scaled + pad
    return {i: (round(float(x), 4), round(float(y), 4)) for i, (x, y) in zip(ids, scaled)}


@router.get("/graph/projection")
def graph_projection(
    session: Session = Depends(get_session),
    limit: int = Query(20000, ge=1, le=20000),
) -> dict:
    backend = deps.get_embeddings().backend_id()
    fingerprint = (*routes_graph._graph_fingerprint(session), backend)
    points = routes_graph._cached(
        "projection", fingerprint, lambda: project(routes_graph._note_vectors(session, backend))
    )
    return {"points": [{"id": i, "x": x, "y": y} for i, (x, y) in list(points.items())[:limit]]}
