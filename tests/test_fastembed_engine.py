"""The built-in engine is fastembed (ONNX Runtime), not sentence-transformers
and PyTorch (the owner, 2026-10-27), with the same models.

What has to hold across the move: a settings file that says
"sentence-transformers" keeps working and is not read as a different engine
(which would re-embed every note), models fastembed does not know by name are
taught to it with the pooling they were trained with, and the catalogue's
ONNX builds are the ones fastembed itself would fetch. No test downloads.
"""

from __future__ import annotations

import pytest

from tessellate.ai import embeddings
from tessellate.core import deps, embedmodels
from tests import _fake_fastembed as fake


def test_a_saved_old_engine_name_reads_as_the_new_engine(app_state):
    deps.get_config().set_preference("embedding_backend", "sentence-transformers")
    manager = deps.get_model_manager()
    assert manager.embedding_backend() == "fastembed"
    assert deps.get_embeddings().backend_id() == "fastembed:BAAI/bge-small-en-v1.5"


def test_asking_for_the_old_engine_is_not_a_switch(ai_client):
    """A page that has not reloaded still sends "sentence-transformers": the
    engine in use, so nothing is embedded again."""
    deps.get_config().set_preference("embedding_backend", "sentence-transformers")
    reply = ai_client.post("/models/embedding-backend", json={"backend": "sentence-transformers", "model": None})
    assert reply.status_code == 200
    assert reply.json()["reindex_started"] is False and "already" in reply.json()["message"]


def test_the_status_names_the_new_engine(client):
    deps.get_config().set_preference("embedding_backend", "sentence-transformers")
    assert client.get("/models/status").json()["embedding_backend"] == "fastembed"


def test_a_model_fastembed_knows_is_not_registered_again(monkeypatch, tmp_path):
    engine = fake.install(monkeypatch)
    root = fake.snapshot(tmp_path / "hub")
    embeddings._register(engine, fake.BGE, root / "snapshots" / "abc123")
    assert engine.custom == []


def test_a_catalogue_model_with_its_own_pooling_is_taught_once(monkeypatch, tmp_path):
    """multilingual-e5-small is not in fastembed's list; it is mean-pooled
    and normalised, 384 floats, from the repo's own ONNX export."""
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    engine = fake.install(monkeypatch)
    repo = "intfloat/multilingual-e5-small"
    root = fake.snapshot(tmp_path / "hub", repo)
    snap = root / "snapshots" / "abc123"
    embeddings._register(engine, repo, snap)
    embeddings._register(engine, repo, snap)
    assert len(engine.custom) == 1
    taught = engine.custom[0]
    assert taught["model"] == repo and taught["pooling"] == fake.PoolingType.MEAN
    assert taught["normalization"] is True and taught["dim"] == 384
    assert taught["model_file"] == "onnx/model.onnx" and taught["sources"].hf == repo


def test_a_found_model_is_pooled_the_way_its_config_says(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    engine = fake.install(monkeypatch)
    repo = "someone/cls-model"
    snap = fake.snapshot(tmp_path / "hub", repo) / "snapshots" / "abc123"
    (snap / "1_Pooling").mkdir()
    (snap / "1_Pooling" / "config.json").write_text('{"pooling_mode_cls_token": true, "word_embedding_dimension": 512}')
    embeddings._register(engine, repo, snap)
    assert engine.custom[0]["pooling"] == fake.PoolingType.CLS and engine.custom[0]["dim"] == 512


def test_a_load_reads_the_snapshot_folder_offline(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    engine = fake.install(monkeypatch)
    fake.snapshot(tmp_path / "hub")
    embeddings._open_snapshot(engine, fake.BGE)
    load = engine.loads[0]
    assert load["local_files_only"] is True and load["model_name"] == fake.BGE
    assert load["path"] == str(tmp_path / "hub" / "models--Qdrant--bge-small-en-v1.5-onnx-Q" / "snapshots" / "abc123")


def test_nothing_on_disk_is_not_a_load(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    engine = fake.install(monkeypatch)
    with pytest.raises(FileNotFoundError):
        embeddings._open_snapshot(engine, fake.BGE)
    assert engine.loads == []


def test_the_catalogue_fetches_what_fastembed_itself_would():
    """Read from the installed fastembed (CI installs it): a catalogue model
    fastembed knows by name comes from the same repo, file and extra files,
    at the width it says."""
    fastembed = pytest.importorskip("fastembed")
    native = {row["model"]: row for row in fastembed.TextEmbedding.list_supported_models()}
    checked = 0
    for model in embedmodels.EMBED_MODELS:
        row = native.get(model.repo)
        if row is None or model.onnx is None or model.onnx.pooling:
            continue
        checked += 1
        assert row["sources"]["hf"] == model.onnx.source, model.repo
        assert row["model_file"] == model.onnx.model_file, model.repo
        assert list(row.get("additional_files") or []) == list(model.onnx.extra_files), model.repo
    assert checked >= 4
