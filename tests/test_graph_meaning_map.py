"""The Map of meaning reads as a map (owner, 2026-11-22: "scattered dots,
almost no labels, no links"): it places notes by their meaning, or by their
words when no embedding model has made a vector, draws nearest-meaning ties
and names its clusters, and the layout control says what distance means."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np

from tessellate.api import meaning_map, routes_graph_projection as proj

ROOT = Path(__file__).resolve().parents[1]
NOTES = json.loads((ROOT / "scratchpad" / "ui-sweeps" / "_meaning_notes.json").read_text())


def _fixture():
    texts, topic = {}, {}
    for name, notes in NOTES.items():
        for text in notes:
            texts[len(texts) + 1] = text
            topic[len(topic) + 1] = name
    return texts, topic


def _ratio(points, topic):
    same, other = [], []
    for a, b in itertools.combinations(points, 2):
        d = float(np.hypot(points[a][0] - points[b][0], points[a][1] - points[b][1]))
        (same if topic[a] == topic[b] else other).append(d)
    return float(np.mean(same) / np.mean(other))


def test_words_place_same_topic_notes_closer_than_other_topics():
    texts, topic = _fixture()
    assert len(set(topic.values())) >= 3 and len(texts) >= 24
    points = proj.project(meaning_map.word_vectors(texts))
    assert set(points) == set(texts)
    assert _ratio(points, topic) < 0.55


def test_pulling_toward_near_notes_beats_the_bare_plane(monkeypatch):
    texts, topic = _fixture()
    vectors = meaning_map.word_vectors(texts)
    pulled = _ratio(proj.project(vectors), topic)
    monkeypatch.setattr(meaning_map, "PULL_ROUNDS", 0)
    assert pulled < _ratio(proj.project(vectors), topic)


def test_clusters_are_named_by_what_their_notes_share():
    texts, topic = _fixture()
    vectors = meaning_map.word_vectors(texts)
    ids, plane, idx, sim = proj.lay_out(vectors)
    found = meaning_map.clusters(ids, plane, texts)
    assert len(found) >= 3
    assert all(g["label"] and len(g["ids"]) >= meaning_map.MIN_CLUSTER for g in found)
    said = {w for g in found for w in g["label"].split(", ")}
    assert said & {"sauce", "garlic", "butter", "oven", "dough"}
    assert said & {"bike", "ride", "gear", "saddle", "tube"}
    assert said & {"tax", "return", "accountant", "income", "expense"}
    tied = meaning_map.ties(ids, idx, sim, "words")
    assert tied and all(a < b and 0 < s <= 1 for a, b, s in tied)
    assert sum(topic[a] == topic[b] for a, b, _ in tied) / len(tied) > 0.7


def test_the_endpoint_with_no_model_places_notes_by_words(client):
    """`client` has no embedding model: before, every note waited in a row."""
    texts, _ = _fixture()
    for text in texts.values():
        client.post("/entries", json={"content": text})
    data = client.get("/graph/projection").json()
    assert data["source"] == "words"
    assert len(data["points"]) == len(texts)
    assert data["ties"] and data["clusters"]
    assert all(g["id"] and g["label"] and g["ids"] for g in data["clusters"])


def test_the_endpoint_with_a_model_says_so(ai_client):
    for text in ("a funny joke", "buy milk", "a pun"):
        ai_client.post("/entries", json={"content": text})
    assert ai_client.get("/graph/projection").json()["source"] == "model"


def test_frontend_draws_ties_names_and_the_fallback_line():
    graph = (ROOT / "frontend" / "js" / "graph.js").read_text()
    canvas = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text()
    assert "graphLate.mapLinks" in graph and "projection?.ties" in graph
    assert "gcDrawMeaningNames" in canvas and "s.tree.map" in canvas
    assert "tree.source" in canvas and "words, not meaning" in canvas


def test_the_layout_control_says_what_distance_means_and_the_guide_agrees():
    html = (ROOT / "frontend" / "index.html").read_text()
    row = html[html.index('id="graph-layout-label"') :][:900]
    assert 'data-help-for="graph-layout-help"' in row
    help_box = html[html.index('id="graph-layout-help"') :][:700]
    assert "closer" in help_box and "meaning" in help_box and "words" in help_box
    from tests._help_text import help_chat_text

    assert "shared words" in help_chat_text()
