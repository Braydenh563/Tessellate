"""A 2-D map of the notes from their stored vectors (L-graph-2): PCA through
numpy's SVD, so notes that mean alike sit near each other."""

from __future__ import annotations

import numpy as np

from tessellate.api import routes_graph_projection as proj


def test_pca_puts_alike_vectors_together_and_fits_the_unit_square():
    rng = np.random.default_rng(7)
    a = rng.normal(0, 0.05, (5, 8)) + np.eye(8)[0]
    b = rng.normal(0, 0.05, (5, 8)) + np.eye(8)[1]
    vectors = {i: v for i, v in enumerate(np.vstack([a, b]))}
    pts = proj.project(vectors)
    assert set(pts) == set(vectors)
    xs = [p[0] for p in pts.values()] + [p[1] for p in pts.values()]
    assert min(xs) >= 0 and max(xs) <= 1
    inner = np.linalg.norm(np.array(pts[0]) - np.array(pts[1]))
    across = np.linalg.norm(np.array(pts[0]) - np.array(pts[7]))
    assert across > 4 * inner


def test_pca_is_deterministic_and_handles_tiny_sets():
    assert proj.project({}) == {}
    assert proj.project({3: np.ones(4)}) == {3: (0.5, 0.5)}
    v = {1: np.array([1.0, 0, 0]), 2: np.array([0, 1.0, 0]), 3: np.array([0, 0, 1.0])}
    assert proj.project(v) == proj.project(dict(reversed(list(v.items()))))


def test_endpoint_returns_x_y_per_note_and_skips_private(ai_client, session):
    from tessellate.api import routes_graph
    from tessellate.core.database import Entry

    ids = [ai_client.post("/entries", json={"content": t}).json()["id"] for t in ("a funny joke", "buy milk", "a pun", "fix the sink")]
    # Private by the column the similarity sweep filters on, vector and all.
    session.get(Entry, ids[3]).is_private = True
    session.commit()
    routes_graph.reset_graph_cache()
    points = ai_client.get("/graph/projection").json()["points"]
    got = {r["id"] for r in points}
    assert got == set(ids[:3])
    assert all(0 <= r["x"] <= 1 and 0 <= r["y"] <= 1 for r in points)


def test_the_graph_offers_the_map_layout_and_places_notes_by_the_endpoint():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "frontend"
    graph = (root / "js" / "graph.js").read_text()
    assert '<option value="map">Map of meaning</option>' in (root / "index.html").read_text()
    assert '"arc", "map", "treemap"' in graph
    assert 'apiJson("/graph/projection")' in graph and "graphLate.layoutMap(" in graph
