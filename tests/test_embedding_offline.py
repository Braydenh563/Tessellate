"""The embedding model goes online only for its first download (INBOX 439).

The owner's privacy panel showed huggingface.co contacted by the embedding
model with the model already on the machine: a failed cache load fell
through to an online load, logged at debug. A stand-in for the engine here
records every load (always from a folder on disk, never by name) and every
fetch, the one way a model reaches the network.
"""

from __future__ import annotations

import types

import pytest

from tessellate.ai import embeddings
from tessellate.core import embedmodels
from tests import _fake_fastembed as fake

BGE = fake.BGE


@pytest.fixture(autouse=True)
def _own_cache(tmp_path, monkeypatch):
    """Never the real hub cache: a repair clears an incomplete folder."""
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))


@pytest.fixture
def engine(monkeypatch):
    return fake.install(monkeypatch)


@pytest.fixture
def fetched(monkeypatch, tmp_path):
    return fake.fake_fetch(monkeypatch, tmp_path / "hub")


def _service():
    return embeddings.EmbeddingService.__new__(embeddings.EmbeddingService)


def test_a_cached_model_loads_without_going_online(engine, fetched, tmp_path):
    fake.snapshot(tmp_path / "hub")
    _service()._load_builtin_model()
    assert fetched == []
    assert [load["local_files_only"] for load in engine.loads] == [True]
    #: Handed the snapshot folder itself, so the engine never asks the hub
    #: whether the model is current.
    assert engine.loads[0]["path"].endswith("snapshots/abc123")


def test_a_model_on_disk_that_will_not_load_is_fetched_again_once(engine, fetched, tmp_path):
    """The owner, 2026-10-07: "things should be auto fixed for the user"."""
    fake.snapshot(tmp_path / "hub")
    engine.local_works = False
    _service()._load_builtin_model()
    assert fetched == [BGE]  # one repair fetch
    assert len(engine.loads) == 2


def test_the_fix_is_a_visible_task_and_the_person_is_asked_only_after_two_failed_fixes(engine, monkeypatch, tmp_path):
    """INBOX 1289: "Fixing search by meaning", keyword search meanwhile, and no
    "Reinstall" until two fixes have failed."""
    from tessellate.core import jobruns

    fake.snapshot(tmp_path / "hub")
    engine.local_works = False
    fetched = fake.fake_fetch(monkeypatch, tmp_path / "hub", works=False)
    seen = []
    real = jobruns.job_run

    def spy(kind, *args, **kwargs):
        seen.append((kind, kwargs.get("title")))
        return real(kind, *args, **kwargs)

    monkeypatch.setattr(jobruns, "job_run", spy)
    service = _service()
    with pytest.raises(embeddings.EmbeddingCacheBroken) as first:
        service._load_builtin_model()
    assert "Reinstall" not in str(first.value) and "keywords" in str(first.value)
    with pytest.raises(embeddings.EmbeddingCacheBroken, match="Reinstall it from Settings"):
        service._load_builtin_model()
    assert seen == [("embedding-fix", "Fixing search by meaning")] * 2
    assert len(fetched) == 2
    loads = len(engine.loads)
    with pytest.raises(embeddings.EmbeddingCacheBroken, match="Reinstall it from Settings"):
        service._load_builtin_model()
    assert len(engine.loads) == loads + 1 and len(fetched) == 2, "a third load tries the disk only; nothing goes online again"


def test_a_model_never_downloaded_downloads_as_a_visible_task(engine, fetched, monkeypatch):
    from tessellate.core import jobruns

    seen = []
    real = jobruns.job_run
    monkeypatch.setattr(jobruns, "job_run", lambda kind, *a, **k: seen.append((kind, k.get("title"))) or real(kind, *a, **k))
    _service()._load_builtin_model()
    assert seen == [("embedding-fix", "Downloading the search model")]


def test_with_automatic_installs_off_a_broken_model_stays_offline(engine, fetched, tmp_path):
    fake.snapshot(tmp_path / "hub")
    engine.local_works = False
    service = _service()
    service._models = types.SimpleNamespace(_config=types.SimpleNamespace(get_preference=lambda key, default=None: False))
    with pytest.raises(embeddings.EmbeddingCacheBroken, match="Reinstall it from Settings"):
        service._load_builtin_model()
    assert fetched == [] and len(engine.loads) == 1  # no online attempt


def test_a_model_never_downloaded_downloads_once(engine, fetched):
    _service()._load_builtin_model()
    assert fetched == [BGE]
    assert [load["local_files_only"] for load in engine.loads] == [True]


def test_the_download_takes_only_the_onnx_build(monkeypatch, tmp_path):
    """Only the files the engine reads: bge's repo also holds PyTorch and
    safetensors weights, several times the ONNX build's size."""
    import huggingface_hub

    asked = {}
    monkeypatch.setattr(huggingface_hub, "snapshot_download", lambda **kwargs: asked.update(kwargs))
    embedmodels.fetch(BGE)
    assert asked["repo_id"] == "Qdrant/bge-small-en-v1.5-onnx-Q"
    assert "model_optimized.onnx" in asked["allow_patterns"]
    assert not any(pattern.endswith((".bin", ".safetensors")) for pattern in asked["allow_patterns"])


def test_downloaded_means_weights_in_a_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    repo_dir = tmp_path / "models--Qdrant--bge-small-en-v1.5-onnx-Q"
    (repo_dir / "snapshots" / "abc").mkdir(parents=True)
    assert not embedmodels.is_downloaded(BGE)
    (repo_dir / "snapshots" / "abc" / "model_optimized.onnx").write_bytes(b"x")
    #: Weights alone are not a model (INBOX 1288, "weights and config"): a
    #: snapshot cut off before its config reads as present and fails offline.
    assert not embedmodels.is_downloaded(BGE)
    (repo_dir / "snapshots" / "abc" / "config.json").write_text("{}", encoding="utf-8")
    assert embedmodels.is_downloaded(BGE)


def test_the_state_of_a_cache_is_ready_partial_or_absent(tmp_path, monkeypatch):
    """INBOX 1290: each embedding row shows its real state."""
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    assert embedmodels.snapshot_state(BGE) == "absent"
    snapshot = tmp_path / "models--Qdrant--bge-small-en-v1.5-onnx-Q" / "snapshots" / "abc"
    snapshot.mkdir(parents=True)
    assert embedmodels.snapshot_state(BGE) == "partial", "the folder an interrupted first request leaves"
    (snapshot / "model_optimized.onnx").write_bytes(b"x")
    assert embedmodels.snapshot_state(BGE) == "partial", "weights without config"
    (snapshot / "config.json").write_text("{}", encoding="utf-8")
    assert embedmodels.snapshot_state(BGE) == "ready"


def test_the_catalogue_carries_each_rows_state(client, tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    snapshot = tmp_path / "models--Qdrant--bge-small-en-v1.5-onnx-Q" / "snapshots" / "abc"
    snapshot.mkdir(parents=True)
    rows = {row["model"]: row for row in client.get("/embedding-models/choices").json()["choices"] if row["backend"] == "fastembed"}
    bge = rows[BGE]
    assert bge["state"] == "partial" and bge["downloaded"] is False
    #: `downloaded` is the whole-cache check (101c): a config, a tokenizer
    #: and weights of a believable size, not only weights and config.
    with (snapshot / "model_optimized.onnx").open("wb") as weights:
        weights.truncate(120 * 1024 * 1024)  # sparse on disk
    for name in ("config.json", "tokenizer.json"):
        (snapshot / name).write_text("{}", encoding="utf-8")
    bge = {row["model"]: row for row in client.get("/embedding-models/choices").json()["choices"]}[BGE]
    assert bge["state"] == "ready" and bge["downloaded"] is True and bge["on_disk"]
    other = next(row for model, row in rows.items() if model != BGE)
    assert other["state"] == "absent" and other["on_disk"] == ""


def test_the_off_switch_stops_the_first_download(engine, fetched, monkeypatch):
    """docs/PRIVACY.md: `TESSELLATE_NO_AUTO_INSTALL` stops the search model's
    one-off fetch. An uncached model stays uncached and search uses keywords."""
    monkeypatch.setenv("TESSELLATE_NO_AUTO_INSTALL", "1")
    with pytest.raises(embeddings.EmbeddingCacheBroken):
        _service()._load_builtin_model()
    assert fetched == []
