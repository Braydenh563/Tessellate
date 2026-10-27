"""Notes that missed their embedding get one on the next start.

The bug: a note saved while the embedding model was still warming up got no
vector, and nothing ever went back for it, so it stayed invisible to semantic
search forever while looking completely normal in the notes list.
"""

from __future__ import annotations

from sqlalchemy import select

from tessellate.ai import embeddings
from tessellate.core import vault
from tessellate.core.database import EmbeddingRecord


def _factory(session):
    """Hand the backfill the test's own session, so assertions see its writes."""
    return lambda: session


def _embedded_ids(session):
    return {row.entry_id for row in session.scalars(select(EmbeddingRecord))}


def test_backfill_embeds_notes_that_have_none(client, session, fake_embeddings):
    a = client.post("/entries", json={"content": "first note"}).json()
    b = client.post("/entries", json={"content": "second note"}).json()
    # Simulate the warm-up gap: throw away the vectors that were stored.
    session.query(EmbeddingRecord).delete()
    session.commit()
    assert _embedded_ids(session) == set()

    fixed = embeddings.backfill_missing(fake_embeddings, _factory(session))

    assert fixed == 2
    assert _embedded_ids(session) == {a["id"], b["id"]}


def test_backfill_leaves_existing_embeddings_alone(client, session, fake_embeddings):
    client.post("/entries", json={"content": "already embedded"}).json()
    before = _embedded_ids(session)
    assert before  # the normal save path embedded it

    assert embeddings.backfill_missing(fake_embeddings, _factory(session)) == 0
    assert _embedded_ids(session) == before


def test_backfill_skips_private_notes(client, session, fake_embeddings):
    """A vector encodes what a note is about, backfilling one would leak it."""
    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()

    entry = client.post("/entries", json={"content": "a private thing"}).json()
    client.post(f"/entries/{entry['id']}/privacy", json={"private": True})
    session.query(EmbeddingRecord).delete()
    session.commit()

    assert embeddings.backfill_missing(fake_embeddings, _factory(session)) == 0
    assert _embedded_ids(session) == set()
    vault.close()


def test_backfill_skips_binned_notes(client, session, fake_embeddings):
    entry = client.post("/entries", json={"content": "to be binned"}).json()
    client.delete(f"/entries/{entry['id']}")
    session.query(EmbeddingRecord).delete()
    session.commit()

    assert embeddings.backfill_missing(fake_embeddings, _factory(session)) == 0


def test_backfill_is_bounded(client, session, fake_embeddings):
    """A huge notebook must not spend minutes embedding on every launch."""
    for i in range(5):
        client.post("/entries", json={"content": f"note {i}"})
    session.query(EmbeddingRecord).delete()
    session.commit()

    assert embeddings.backfill_missing(fake_embeddings, _factory(session), limit=2) == 2


def test_backfill_does_nothing_without_a_ready_model(client, session, fake_embeddings):
    client.post("/entries", json={"content": "a note"})
    session.query(EmbeddingRecord).delete()
    session.commit()

    fake_embeddings.available = False  # is_ready() reads this
    assert embeddings.backfill_missing(fake_embeddings, _factory(session)) == 0


def test_wal_and_busy_timeout_are_set(app_state):
    """WAL lets reads continue during a write; the timeout stops a moment of
    contention surfacing as a broken save."""
    from tessellate.core import deps

    with deps.get_db().engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_repeated_embeds_of_the_same_text_are_cached():
    """Saving a note embeds the same text twice in quick succession, once to
    store the vector, once by the near-duplicate check right afterwards.

    Uses the real service: FakeEmbeddingService overrides embed_text wholesale,
    so it would never touch the cache being tested.
    """
    import numpy as np

    from tessellate.ai.embeddings import EmbeddingService

    service = EmbeddingService(model_manager=None, ollama_client=None)
    calls = []

    def fake_backend(text):
        calls.append(text)
        return np.array([len(text)], dtype="float32")

    service._embed_uncached = fake_backend

    first = service.embed_text("a note about bread")
    second = service.embed_text("a note about bread")

    assert calls == ["a note about bread"]  # the backend ran once, not twice
    assert (first == second).all()


def test_different_text_is_not_served_from_the_cache():
    import numpy as np

    from tessellate.ai.embeddings import EmbeddingService

    service = EmbeddingService(model_manager=None, ollama_client=None)
    calls = []

    def fake_backend(text):
        calls.append(text)
        return np.array([float(len(text))], dtype="float32")

    service._embed_uncached = fake_backend

    service.embed_text("bread")
    service.embed_text("kayaking")
    assert calls == ["bread", "kayaking"]


def test_the_cache_is_bounded():
    """It exists to collapse duplicate work in one request, not to grow."""
    import numpy as np

    from tessellate.ai import embeddings as emb
    from tessellate.ai.embeddings import EmbeddingService

    service = EmbeddingService(model_manager=None, ollama_client=None)
    service._embed_uncached = lambda text: np.array([1.0], dtype="float32")
    for i in range(emb._EMBED_CACHE_MAX + 20):
        service.embed_text(f"note {i}")
    assert len(service._embed_cache) <= emb._EMBED_CACHE_MAX


def test_stop_ends_the_backfill_between_batches_and_keeps_what_was_embedded(client, session, fake_embeddings, monkeypatch):
    """INBOX 1294: the backfill was one call with no step to stop at."""
    from tessellate.core import passes

    for i in range(3):
        client.post("/entries", json={"content": f"note {i}"})
    session.query(EmbeddingRecord).delete()
    session.commit()
    monkeypatch.setattr(embeddings, "EMBED_BATCH", 1)
    real = fake_embeddings.store_for_entries

    def store_then_stop(session_, batch):
        done = real(session_, batch)
        passes._stop.add("embeddings-backfill")  # Stop pressed during the first batch
        return done

    monkeypatch.setattr(fake_embeddings, "store_for_entries", store_then_stop)
    fixed = embeddings.backfill_missing(fake_embeddings, _factory(session))

    assert fixed == 1
    assert len(_embedded_ids(session)) == 1, "the batch done before Stop is kept"
    assert not passes.stop_requested("embeddings-backfill"), "a stale Stop must not end the next run"
    assert "embeddings-backfill" in passes.STOPPABLE


def _label(session, entry_id, model_version):
    """Mark a note's vector as made by another model, the state a model
    switch or an engine change leaves behind."""
    row = session.scalars(select(EmbeddingRecord).where(EmbeddingRecord.entry_id == entry_id)).one()
    row.model_version = model_version
    session.commit()


def _versions(session):
    session.expire_all()
    return {row.entry_id: row.model_version for row in session.scalars(select(EmbeddingRecord))}


def test_backfill_replaces_a_vector_from_another_model(client, session, fake_embeddings):
    """Search drops a vector whose model_version is not the current one
    (`search/engine.py`), so a note holding one is as unfindable by meaning
    as a note with none, and the backfill fills it the same way."""
    kept = client.post("/entries", json={"content": "made by this model"}).json()
    stale = client.post("/entries", json={"content": "made by the old one"}).json()
    _label(session, stale["id"], "fastembed:intfloat/multilingual-e5-small")

    assert embeddings.backfill_missing(fake_embeddings, _factory(session)) == 1
    current = fake_embeddings.backend_id()
    assert _versions(session) == {kept["id"]: current, stale["id"]: current}


def test_the_periodic_pass_replaces_a_vector_from_another_model(client, session, fake_embeddings):
    from tessellate.core import passes

    stale = client.post("/entries", json={"content": "made by the old engine"}).json()
    _label(session, stale["id"], "sentence-transformers:BAAI/bge-base-en-v1.5")

    passes._backfill()

    assert _versions(session) == {stale["id"]: fake_embeddings.backend_id()}
