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


def test_past_the_cap_notes_are_sampled_evenly_not_the_oldest_first():
    """Review 5883476033 (3): a capped map shows the whole notebook's spread."""
    ids = list(range(1, 101))
    picked = proj.sample(ids, 10)
    assert len(picked) == 10 and picked[0] == 1 and picked[-1] == 100
    gaps = {b - a for a, b in zip(picked, picked[1:])}
    assert max(gaps) - min(gaps) <= 1
    assert proj.sample(ids, 200) == ids and proj.sample(ids, 1) == [1]
    vectors = {i: np.eye(4)[i % 4] for i in ids}
    assert set(proj.project(vectors, cap=10)) == set(picked)


def test_the_projection_of_a_large_notebook_is_quick():
    """Review 5883476033 (3): float32 and the d x d covariance, not an SVD of
    the whole matrix. 5,000 notes of 384 floats, the cap and the default
    model's width; it took 0.03 s here, so 3 s is room for a loaded runner."""
    import time

    rng = np.random.default_rng(3)
    vectors = {i: row for i, row in enumerate(rng.normal(size=(proj.MAX_PROJECTED, 384)).astype("float32"))}
    started = time.perf_counter()
    pts = proj.project(vectors)
    took = time.perf_counter() - started
    assert len(pts) == proj.MAX_PROJECTED
    assert took < 3.0, took


def test_the_projection_cache_follows_a_new_vector_with_no_note_edit(ai_client, session):
    """Review 5883476033 (5): a re-embed writes a new row and moves no
    `updated_at`, so the key must read the vectors themselves."""
    from tessellate.api import routes_graph
    from tessellate.core.database import EmbeddingRecord

    ids = [ai_client.post("/entries", json={"content": t}).json()["id"] for t in ("a funny joke", "buy milk", "a pun")]
    routes_graph.reset_graph_cache()
    before = {r["id"] for r in ai_client.get("/graph/projection").json()["points"]}
    assert before == set(ids)
    # Drop one note's vector behind the notes' backs: nothing a note edit would show.
    session.query(EmbeddingRecord).filter(EmbeddingRecord.entry_id == ids[2]).delete()
    session.commit()
    after = {r["id"] for r in ai_client.get("/graph/projection").json()["points"]}
    assert after == set(ids[:2])
    # The similarity and layer-similarity slots share this key.
    backend = routes_graph.deps.get_embeddings().backend_id()
    key = routes_graph._vector_fingerprint(session, backend)
    ai_client.post("/entries", json={"content": "a riddle"})
    assert routes_graph._vector_fingerprint(session, backend) != key


def test_vectors_of_another_width_are_logged_when_left_out(caplog):
    """Review 5883476033 (4): a model switch mid-re-embed leaves two widths;
    the minority is dropped from the lines, and the log says so."""
    import logging

    from tessellate.ai import embeddings

    notes = {1: np.ones(4), 2: np.ones(4), 3: np.ones(8)}
    derived = {"document:1": np.ones(4), "entity:1": np.ones(8)}
    with caplog.at_level(logging.INFO, logger="tessellate.embeddings"):
        ids, keys = embeddings._same_width(derived, notes)
    assert ids == [1, 2] and keys == ["document:1"]
    assert "left out 2 vectors not 4 wide" in caplog.text
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="tessellate.embeddings"):
        embeddings._same_width({}, {1: np.ones(4)})
    assert "left out" not in caplog.text
