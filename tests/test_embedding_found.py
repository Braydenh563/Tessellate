"""INBOX 700, the owner's addendum: "should there also be a way to detect and
potentially use any other cached models the user may have?? like for
embedding models and such??"

Detected: the Hugging Face cache, the old sentence-transformers cache,
Ollama's model list when it is running, and LM Studio's models folder. Listed
as "Found on this computer", with Use only for a format the built-in engine
(fastembed: an ONNX export with its tokenizer) or Ollama can load; anything
else says why. Offline, read-only, nothing imported.
"""

from __future__ import annotations

import json
import sys
import time

import pytest

from tessellate.core import deps, embedfind, embedmodels, embedswitch
from tests.fakes import FakeEmbeddingService


@pytest.fixture(autouse=True)
def _clean():
    embedswitch.reset_for_tests()
    yield
    embedswitch.reset_for_tests()


def _snapshot(root, repo, files):
    snap = root / ("models--" + repo.replace("/", "--")) / "snapshots" / "abc123"
    snap.mkdir(parents=True)
    for name, text in files.items():
        (snap / name).parent.mkdir(parents=True, exist_ok=True)
        (snap / name).write_text(text)
    return snap


@pytest.fixture()
def disk(tmp_path, monkeypatch):
    home = tmp_path / "home"
    hub = tmp_path / "hub"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("HF_HUB_CACHE", str(hub))
    monkeypatch.delenv("SENTENCE_TRANSFORMERS_HOME", raising=False)
    monkeypatch.delenv("LMSTUDIO_HOME", raising=False)
    weights = {"model.safetensors": "x", "config.json": "{}"}
    onnx = {"onnx/model.onnx": "x", "tokenizer.json": "{}", "config.json": "{}"}
    # An embedding model with an ONNX export: the engine loads it as it is.
    _snapshot(hub, "thenlper/gte-small", {**weights, **onnx, "modules.json": "[]"})
    # One with PyTorch weights only: the engine runs ONNX, so it says why.
    _snapshot(hub, "sentence-transformers/all-mpnet-base-v2", {**weights, "tokenizer.json": "{}", "modules.json": "[]"})
    # One that needs its repository's own Python code.
    _snapshot(hub, "jinaai/jina-embeddings-v2-small-en", {
        "model.safetensors": "x", "modules.json": "[]",
        "config.json": json.dumps({"auto_map": {"AutoModel": "jinaai/x--modeling.Bert"}}),
    })
    # A chat model: not an embedding model, so not listed at all.
    _snapshot(hub, "Qwen/Qwen2.5-0.5B-Instruct", weights)
    # A catalogue model already downloaded (the old engine's folder, and the
    # ONNX build the new one fetches): it has its own row, not a found one.
    _snapshot(hub, "BAAI/bge-small-en-v1.5", {**weights, "modules.json": "[]"})
    _snapshot(hub, "Qdrant/bge-small-en-v1.5-onnx-Q", {"model_optimized.onnx": "x", "tokenizer.json": "{}", "config.json": "{}"})
    # The old sentence-transformers cache.
    legacy = home / ".cache" / "torch" / "sentence_transformers" / "sentence-transformers_paraphrase-MiniLM-L3-v2"
    legacy.mkdir(parents=True)
    (legacy / "modules.json").write_text("[]")
    # LM Studio's folder: a GGUF embedding model.
    gguf = home / ".lmstudio" / "models" / "nomic-ai" / "nomic-embed-text-v1.5-GGUF"
    gguf.mkdir(parents=True)
    (gguf / "nomic-embed-text-v1.5.Q8_0.gguf").write_bytes(b"GGUF")
    return tmp_path


def _found(ollama=None):
    return {row["id"]: row for row in embedfind.found(ollama)}


def test_an_onnx_embedding_model_in_the_cache_is_usable(disk):
    rows = _found()
    row = rows["found:thenlper/gte-small"]
    assert row["usable"] is True and row["backend"] == "fastembed"
    assert row["where"] == "Hugging Face cache"


def test_a_pytorch_only_model_is_listed_with_why(disk):
    row = _found()["found:sentence-transformers/all-mpnet-base-v2"]
    assert row["usable"] is False and "ONNX" in row["why_not"]


def test_a_model_needing_its_own_code_is_listed_with_why(disk):
    row = _found()["found:jinaai/jina-embeddings-v2-small-en"]
    assert row["usable"] is False and "code" in row["why_not"]


def test_chat_models_and_catalogue_models_are_not_found_rows(disk):
    rows = _found()
    assert "found:Qwen/Qwen2.5-0.5B-Instruct" not in rows
    assert "found:BAAI/bge-small-en-v1.5" not in rows
    assert "found:Qdrant/bge-small-en-v1.5-onnx-Q" not in rows


def test_the_old_sentence_transformers_cache_and_lm_studio_say_why(disk):
    rows = list(_found().values())
    legacy = next(row for row in rows if "paraphrase-MiniLM-L3-v2" in row["label"])
    assert legacy["usable"] is False and legacy["why_not"]
    gguf = next(row for row in rows if row["where"] == "LM Studio")
    assert gguf["usable"] is False and "GGUF" in gguf["why_not"]


def test_ollama_embedding_models_are_found_when_it_runs(disk):
    class _Ollama:
        def is_running(self):
            return True

        def list_models(self):
            return [
                {"name": "all-minilm:latest", "size": 45_000_000},
                {"name": "nomic-embed-text:latest", "size": 274_000_000},
                {"name": "llama3.2:latest", "size": 2_000_000_000},
            ]

    rows = _found(_Ollama())
    assert rows["found-ollama:all-minilm:latest"]["usable"] is True
    # In the catalogue already, so it is that row, not a found one.
    assert "found-ollama:nomic-embed-text:latest" not in rows
    assert not any("llama3.2" in key for key in rows)


def test_the_scan_never_imports_the_engine(disk):
    for name in ("fastembed", "onnxruntime"):
        sys.modules.pop(name, None)
    _found()
    assert "fastembed" not in sys.modules and "onnxruntime" not in sys.modules


def test_a_found_repo_is_a_valid_built_in_choice_only_while_it_is_on_disk(app_state, disk):
    manager = deps.get_model_manager()
    deps.get_config().set_preference("embedding_st_model", "thenlper/gte-small")
    assert manager.embedding_st_model() == "thenlper/gte-small"
    deps.get_config().set_preference("embedding_st_model", "jinaai/jina-embeddings-v2-small-en")
    assert manager.embedding_st_model() == embedmodels.DEFAULT_REPO


def test_use_on_a_found_model_switches_to_it(ai_client, fake_embeddings, disk, monkeypatch):
    monkeypatch.setattr(fake_embeddings, "pinned", lambda backend, model: FakeEmbeddingService())
    body = ai_client.get("/embedding-models/choices").json()
    assert any(row["id"] == "found:thenlper/gte-small" for row in body["found"])
    started = ai_client.post("/embedding-models/use", json={"id": "found:thenlper/gte-small"}).json()
    assert started["started"] is True, started
    deadline = time.monotonic() + 10
    while embedswitch.status()["running"] and time.monotonic() < deadline:
        time.sleep(0.02)
    assert deps.get_model_manager().embedding_st_model() == "thenlper/gte-small"


def test_use_on_an_unusable_found_model_is_refused(ai_client, disk):
    refused = ai_client.post("/embedding-models/use", json={"id": "found:jinaai/jina-embeddings-v2-small-en"})
    assert refused.status_code == 400
    missing = ai_client.post("/embedding-models/use", json={"id": "found:nobody/not-here"})
    assert missing.status_code == 400


def test_a_pytorch_only_model_chosen_earlier_is_re_embedded_with_the_default(client, session, disk):
    """Chosen from this computer when the engine ran PyTorch weights, it now
    reads as the default (no ONNX export), and the vectors it made are filled
    again by the backfill rather than left stranded."""
    from sqlalchemy import select

    from tessellate.ai import embeddings
    from tessellate.core.database import EmbeddingRecord

    deps.get_config().set_preference("embedding_st_model", "sentence-transformers/all-mpnet-base-v2")
    real = embeddings.EmbeddingService(model_manager=deps.get_model_manager(), ollama_client=None)
    assert real.backend_id() == f"fastembed:{embedmodels.DEFAULT_REPO}"

    class Default(FakeEmbeddingService):
        def backend_id(self) -> str:
            return real.backend_id()

    service = Default(available=True)
    deps.override_ai(embeddings=service)
    note = client.post("/entries", json={"content": "embedded by the old choice"}).json()
    row = session.scalars(select(EmbeddingRecord).where(EmbeddingRecord.entry_id == note["id"])).one()
    row.model_version = "fastembed:sentence-transformers/all-mpnet-base-v2"
    session.commit()

    assert embeddings.backfill_missing(service, lambda: session) == 1
    session.expire_all()
    assert session.scalars(select(EmbeddingRecord.model_version)).all() == [real.backend_id()]
