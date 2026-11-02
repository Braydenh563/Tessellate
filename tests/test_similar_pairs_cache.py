"""`similar_pairs` for link suggestions and tensions, once per vector set.

WORLD_CLASS_PLAN row 9 (§16): the all-pairs comparison ran on every request
of `/entries/link-suggestions` and `/entries/tensions`; only the graph cached
its pairs. Both now read `engine.cached_similar_pairs`, keyed by the matrix's
version, which moves on every vector write the matrix sees and on every one
`current_matrix` catches up with, so a cache hit can never be a stale answer.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import delete

from tessellate.ai import embeddings as embeddings_module
from tessellate.core.database import EmbeddingRecord, Entry
from tessellate.search import engine


def _note(session, content, private=False):
    entry = Entry(content=content, tags=json.dumps([]), is_private=private)
    session.add(entry)
    session.commit()
    return entry


@pytest.fixture()
def pair_calls(monkeypatch):
    """Counts the all-pairs comparisons actually run."""
    calls: list[float] = []
    real = embeddings_module.similar_pairs

    def counting(vectors, threshold, per_node=None):
        calls.append(threshold)
        return real(vectors, threshold, per_node=per_node)

    monkeypatch.setattr(embeddings_module, "similar_pairs", counting)
    return calls


def _embedded(session, fake_embeddings, *contents):
    made = [_note(session, text) for text in contents]
    for entry in made:
        assert fake_embeddings.store_for_entry(session, entry)
    return made


def test_link_suggestions_compare_the_pairs_once_per_vector_set(ai_client, session, fake_embeddings, pair_calls):
    _embedded(session, fake_embeddings, "a joke about a pun", "a funny scarecrow joke, different words")
    first = ai_client.get("/entries/link-suggestions").json()
    second = ai_client.get("/entries/link-suggestions").json()
    assert first == second
    assert len(pair_calls) == 1, pair_calls


def test_a_new_vector_is_a_new_comparison(ai_client, session, fake_embeddings, pair_calls):
    a, _b = _embedded(session, fake_embeddings, "a joke about a pun", "shopping for milk and eggs")
    assert ai_client.get("/entries/link-suggestions").json() == []
    (c,) = _embedded(session, fake_embeddings, "a funny scarecrow told it")
    pairs = ai_client.get("/entries/link-suggestions").json()
    assert {(p["source_id"], p["target_id"]) for p in pairs} == {(a.id, c.id)}
    assert len(pair_calls) == 2


def test_a_vector_deleted_round_the_orm_is_not_suggested(ai_client, session, fake_embeddings, pair_calls):
    a, b = _embedded(session, fake_embeddings, "a joke about a pun", "a funny scarecrow told it")
    assert ai_client.get("/entries/link-suggestions").json()
    session.execute(delete(EmbeddingRecord).where(EmbeddingRecord.entry_id == b.id))
    session.commit()
    assert ai_client.get("/entries/link-suggestions").json() == []


def test_the_note_filter_is_applied_after_the_cache(session, fake_embeddings):
    """One cached comparison serves callers that want different notes: a
    pair is only handed back when both ends are in the caller's set."""
    a, b, c = _embedded(session, fake_embeddings, "a joke", "a pun", "a funny thing")
    all_pairs = engine.cached_similar_pairs(session, 0.5)
    assert {frozenset(p[:2]) for p in all_pairs} == {
        frozenset((a.id, b.id)), frozenset((a.id, c.id)), frozenset((b.id, c.id))
    }
    some = engine.cached_similar_pairs(session, 0.5, only={a.id, b.id})
    assert [p[:2] for p in some] == [tuple(sorted((a.id, b.id)))]


def test_tensions_compare_the_pairs_once_per_vector_set(ai_client, session, fake_embeddings, pair_calls):
    _embedded(session, fake_embeddings, "a joke about a pun", "a funny scarecrow joke")
    ai_client.get("/entries/tensions")
    ai_client.get("/entries/tensions")
    assert len(pair_calls) == 1, pair_calls


def test_no_embeddings_means_no_pairs(session, monkeypatch):
    monkeypatch.setattr(engine, "_backend_id", lambda: None)
    assert engine.cached_similar_pairs(session, 0.5) == []


def test_link_suggestions_are_kept_until_the_notebook_changes(client, session, monkeypatch):
    """Audit 1028 K30: every request read every note, link and mention and
    ran the recogniser. A second ask with nothing written is answered from
    the kept list; a flush or a bulk statement starts it again."""
    from sqlalchemy import update

    from tessellate.ai import relations

    runs = []
    real = relations.recognise
    monkeypatch.setattr(relations, "recognise", lambda *a, **k: runs.append(1) or real(*a, **k))
    first = _note(session, "Sam Lee came by the studio about the kiln")
    _note(session, "Sam Lee and the kiln firing schedule")
    asks = [client.get("/entries/link-suggestions") for _ in range(2)]
    assert [a.status_code for a in asks] == [200, 200]
    assert asks[0].json() == asks[1].json()
    assert len(runs) == 1, "nothing was written between the two asks"
    _note(session, "A third note")
    client.get("/entries/link-suggestions")
    assert len(runs) == 2, "a flush starts it again"
    session.execute(update(Entry).where(Entry.id == first.id).values(is_private=True))
    session.commit()
    client.get("/entries/link-suggestions")
    assert len(runs) == 3, "so does a bulk statement"
