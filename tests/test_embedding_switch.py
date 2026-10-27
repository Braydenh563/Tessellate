"""INBOX 700: more embedding models, and switching without losing search.

The owner: "can you also add more embedding model options as alternatives in
the models??" / "research the best ones available today". Decision taken: a
curated list with size, languages, context, licence and a one-line best-for;
a one-press switch only where the licence allows it; the switch re-embeds in a
durable background job and search keeps the old vectors until the new set is
complete. No real model anywhere here (CLAUDE.md section 7): the fakes stand in.
"""

from __future__ import annotations

import threading
import time

import pytest
from sqlalchemy import select

from tessellate.core import deps, embedmodels, embedswitch, jobstore
from tessellate.core.database import EmbeddingRecord, StagedEmbedding
from tests.fakes import FakeEmbeddingService


@pytest.fixture(autouse=True)
def _clean():
    embedswitch.reset_for_tests()
    yield
    embedswitch.reset_for_tests()


class _Target(FakeEmbeddingService):
    """The model being switched to: its own id, and a gate the test holds."""

    def __init__(self, gate: threading.Event | None = None) -> None:
        super().__init__(available=True)
        self.gate = gate

    def backend_id(self) -> str:
        return "fake:new-model"

    def embed_many(self, texts):
        if self.gate is not None:
            assert self.gate.wait(10)
        return [self.embed_text(text) for text in texts]


def _wait(check, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.02)
    raise AssertionError("timed out")


def _versions():
    session = deps.get_db().session()
    try:
        return {row.model_version for row in session.scalars(select(EmbeddingRecord))}
    finally:
        session.close()


def _staged_count():
    session = deps.get_db().session()
    try:
        return len(list(session.scalars(select(StagedEmbedding))))
    finally:
        session.close()


# --- the catalogue -------------------------------------------------------------


def test_the_list_holds_the_researched_models_with_their_facts():
    rows = {row["id"]: row for row in embedmodels.catalogue()}
    for wanted in ("minilm", "bge-small", "nomic-v1.5", "qwen3-0.6b", "bge-m3", "me5-small"):
        assert wanted in rows, wanted
    for name in (
        "nomic-embed-text", "mxbai-embed-large", "bge-m3", "snowflake-arctic-embed2",
        "granite-embedding", "qwen3-embedding:0.6b", "embeddinggemma",
    ):
        assert f"ollama:{name}" in rows, name
    for row in rows.values():
        for fact in ("size", "languages", "context", "licence", "best_for"):
            assert row[fact], (row["id"], fact)
    assert rows["bge-small"]["default"] is True
    assert sum(1 for row in rows.values() if row["default"]) == 1


def test_only_open_licences_are_one_press():
    rows = {row["id"]: row for row in embedmodels.catalogue()}
    for row in rows.values():
        if row["one_press"]:
            assert row["licence"] in ("Apache-2.0", "MIT"), row["id"]
        else:
            assert row["terms_url"].startswith("https://") and row["why_not"], row["id"]
    assert rows["ollama:embeddinggemma"]["one_press"] is False
    assert rows["embeddinggemma"]["one_press"] is False
    # Open licence, but the built-in load would run its repository's code.
    assert rows["nomic-v1.5"]["one_press"] is False


def test_a_choice_resolves_only_from_the_allowlist():
    assert embedmodels.resolve_choice("bge-m3") == ("fastembed", "BAAI/bge-m3")
    assert embedmodels.resolve_choice("ollama:bge-m3") == ("ollama", "bge-m3")
    assert embedmodels.resolve_choice("ollama:embeddinggemma") is None
    assert embedmodels.resolve_choice("BAAI/bge-m3") is None
    assert embedmodels.resolve_choice("ollama:anything-else") is None


def test_a_gated_model_cannot_be_downloaded_in_one_press():
    started, message = embedmodels.start("embeddinggemma")
    assert started is False and "Gemma" in message


def test_the_e5_family_gets_its_prefix():
    assert embedmodels.prefix_for("intfloat/multilingual-e5-small") == "query: "
    assert embedmodels.prefix_for("BAAI/bge-small-en-v1.5") == ""


def test_a_stored_repo_outside_the_allowlist_reads_as_the_default(app_state):
    manager = deps.get_model_manager()
    deps.get_config().set_preference("embedding_st_model", "../../etc/passwd")
    assert manager.embedding_st_model() == embedmodels.DEFAULT_REPO
    deps.get_config().set_preference("embedding_st_model", "google/embeddinggemma-300m")
    assert manager.embedding_st_model() == embedmodels.DEFAULT_REPO
    deps.get_config().set_preference("embedding_st_model", "BAAI/bge-m3")
    assert manager.embedding_st_model() == "BAAI/bge-m3"


def test_the_switch_is_a_durable_job():
    assert jobstore.durable_kind("embed-switch", embedswitch.run)


# --- the switch ----------------------------------------------------------------


def test_search_keeps_the_old_vectors_until_the_new_set_is_complete(ai_client, fake_embeddings, monkeypatch):
    for text in ("a funny scarecrow joke", "buy milk and eggs", "the match ended 2-1"):
        saved = ai_client.post("/entries", json={"content": text})
        assert saved.status_code == 201
    _wait(lambda: len(_versions()) == 1 and _staged_count() == 0)
    before = _versions()
    gate = threading.Event()
    monkeypatch.setattr(fake_embeddings, "pinned", lambda backend, model: _Target(gate))

    response = ai_client.post("/embedding-models/use", json={"id": "bge-m3"})
    assert response.json()["started"] is True
    _wait(lambda: embedswitch.status()["phase"] == "stage")

    # Mid-switch: the live vectors and the saved setting are the old ones.
    assert _versions() == before
    assert deps.get_model_manager().embedding_st_model() == embedmodels.DEFAULT_REPO
    row = next(t for t in ai_client.get("/tasks").json()["tasks"] if t["kind"] == "embed-switch")
    assert row["label"] == "Switching search to BGE M3 (multilingual)"
    assert row["cancellable"] is True

    gate.set()
    _wait(lambda: not embedswitch.status()["running"])
    assert embedswitch.status()["outcome"] == "completed", embedswitch.status()
    assert "fake:new-model" in _versions()
    assert deps.get_model_manager().embedding_st_model() == "BAAI/bge-m3"
    assert _staged_count() == 0
    body = ai_client.get("/embedding-models/choices").json()
    assert body["current"] == {"backend": "fastembed", "model": "BAAI/bge-m3"}


def test_stop_leaves_the_old_model_in_use(ai_client, fake_embeddings, monkeypatch):
    for text in ("a funny scarecrow joke", "buy milk and eggs"):
        ai_client.post("/entries", json={"content": text})
    _wait(lambda: len(_versions()) == 1)
    before = _versions()
    gate = threading.Event()
    monkeypatch.setattr(fake_embeddings, "pinned", lambda backend, model: _Target(gate))
    monkeypatch.setattr(embedswitch, "BATCH", 1)

    begun = ai_client.post("/embedding-models/use", json={"id": "minilm"}).json()
    assert begun["started"]
    _wait(lambda: embedswitch.status()["phase"] == "stage")
    stopped = ai_client.post("/tasks/cancel", json={"kind": "embed-switch", "name": ""}).json()
    assert stopped["stopped"] is True
    gate.set()
    _wait(lambda: not embedswitch.status()["running"])

    assert embedswitch.status()["outcome"] == "cancelled"
    assert _versions() == before
    assert deps.get_model_manager().embedding_st_model() == embedmodels.DEFAULT_REPO
    assert _staged_count() == 0


def test_a_model_that_will_not_load_fails_the_switch_and_keeps_search(ai_client, fake_embeddings, monkeypatch):
    ai_client.post("/entries", json={"content": "buy milk and eggs"})
    _wait(lambda: len(_versions()) == 1)
    before = _versions()
    broken = FakeEmbeddingService(available=False)
    monkeypatch.setattr(fake_embeddings, "pinned", lambda backend, model: broken)

    begun = ai_client.post("/embedding-models/use", json={"id": "qwen3-0.6b"}).json()
    assert begun["started"]
    _wait(lambda: not embedswitch.status()["running"])
    assert embedswitch.status()["outcome"] == "failed"
    assert _versions() == before
    assert deps.get_model_manager().embedding_st_model() == embedmodels.DEFAULT_REPO


def test_a_licence_gated_choice_is_refused_by_the_server(ai_client):
    for choice in ("ollama:embeddinggemma", "nomic-v1.5"):
        refused = ai_client.post("/embedding-models/use", json={"id": choice})
        assert refused.status_code == 400, choice


def test_switching_to_the_model_in_use_does_nothing(ai_client):
    body = ai_client.post("/embedding-models/use", json={"id": "bge-small"}).json()
    assert body["started"] is False and "already" in body["message"]
