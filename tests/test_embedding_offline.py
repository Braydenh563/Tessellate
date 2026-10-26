"""The embedding model goes online only for its first download (INBOX 439).

The owner's privacy panel showed huggingface.co contacted by the embedding
model with the model already on the machine: a failed cache load fell
through to an online load, logged at debug. A stand-in for the library here
records every load and whether it was allowed online.
"""

from __future__ import annotations

import sys
import types

import pytest

from tessellate.ai import embeddings
from tessellate.core import embedmodels


class _FakeST:
    calls: list[bool] = []
    local_works = True
    online_works = True

    def __init__(self, name, local_files_only=False):  # noqa: ANN001
        type(self).calls.append(bool(local_files_only))
        if local_files_only and not type(self).local_works:
            raise OSError("cache incomplete")
        if not local_files_only and not type(self).online_works:
            raise OSError("no network")


@pytest.fixture(autouse=True)
def _own_cache(tmp_path, monkeypatch):
    """Never the real hub cache: a repair clears an incomplete folder."""
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))


@pytest.fixture
def fake_st(monkeypatch):
    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = _FakeST
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    _FakeST.calls = []
    _FakeST.local_works = True
    _FakeST.online_works = True
    return _FakeST


def _service():
    return embeddings.EmbeddingService.__new__(embeddings.EmbeddingService)


def test_a_cached_model_loads_without_going_online(fake_st):
    _service()._load_st_model()
    assert fake_st.calls == [True]


def test_a_model_on_disk_that_will_not_load_is_fetched_again_once(fake_st, monkeypatch):
    """The owner, 2026-10-07: "things should be auto fixed for the user"."""
    fake_st.local_works = False
    monkeypatch.setattr(embedmodels, "is_downloaded", lambda repo: True)
    service = _service()
    service._load_st_model()
    assert fake_st.calls == [True, False]  # one repair fetch


def test_the_fix_is_a_visible_task_and_the_person_is_asked_only_after_two_failed_fixes(fake_st, monkeypatch):
    """INBOX 1289: "Fixing search by meaning", keyword search meanwhile, and no
    "Reinstall" until two fixes have failed."""
    from tessellate.core import jobruns

    fake_st.local_works = False
    fake_st.online_works = False
    monkeypatch.setattr(embedmodels, "is_downloaded", lambda repo: True)
    seen = []
    real = jobruns.job_run

    def spy(kind, *args, **kwargs):
        seen.append((kind, kwargs.get("title")))
        return real(kind, *args, **kwargs)

    monkeypatch.setattr(jobruns, "job_run", spy)
    service = _service()
    with pytest.raises(embeddings.EmbeddingCacheBroken) as first:
        service._load_st_model()
    assert "Reinstall" not in str(first.value) and "keywords" in str(first.value)
    with pytest.raises(embeddings.EmbeddingCacheBroken, match="Reinstall it from Settings"):
        service._load_st_model()
    assert seen == [("embedding-fix", "Fixing search by meaning")] * 2
    calls = len(fake_st.calls)
    with pytest.raises(embeddings.EmbeddingCacheBroken, match="Reinstall it from Settings"):
        service._load_st_model()
    assert len(fake_st.calls) == calls + 1, "a third load tries the cache only; nothing goes online again"


def test_a_model_never_downloaded_downloads_as_a_visible_task(fake_st, monkeypatch):
    from tessellate.core import jobruns

    fake_st.local_works = False
    monkeypatch.setattr(embedmodels, "is_downloaded", lambda repo: False)
    seen = []
    real = jobruns.job_run
    monkeypatch.setattr(jobruns, "job_run", lambda kind, *a, **k: seen.append((kind, k.get("title"))) or real(kind, *a, **k))
    _service()._load_st_model()
    assert seen == [("embedding-fix", "Downloading the search model")]


def test_with_automatic_installs_off_a_broken_model_stays_offline(fake_st, monkeypatch):
    fake_st.local_works = False
    monkeypatch.setattr(embedmodels, "is_downloaded", lambda repo: True)
    service = _service()
    service._models = types.SimpleNamespace(_config=types.SimpleNamespace(get_preference=lambda key, default=None: False))
    with pytest.raises(embeddings.EmbeddingCacheBroken, match="Reinstall it from Settings"):
        service._load_st_model()
    assert fake_st.calls == [True]  # no online attempt


def test_a_model_never_downloaded_downloads_once(fake_st, monkeypatch):
    fake_st.local_works = False
    monkeypatch.setattr(embedmodels, "is_downloaded", lambda repo: False)
    _service()._load_st_model()
    assert fake_st.calls == [True, False]


def test_downloaded_means_weights_in_a_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    repo_dir = tmp_path / "models--BAAI--bge-small-en-v1.5"
    (repo_dir / "snapshots" / "abc").mkdir(parents=True)
    assert not embedmodels.is_downloaded("BAAI/bge-small-en-v1.5")
    (repo_dir / "snapshots" / "abc" / "model.safetensors").write_bytes(b"x")
    #: Weights alone are not a model (INBOX 1288, "weights and config"): a
    #: snapshot cut off before its config reads as present and fails offline.
    assert not embedmodels.is_downloaded("BAAI/bge-small-en-v1.5")
    (repo_dir / "snapshots" / "abc" / "config.json").write_text("{}", encoding="utf-8")
    assert embedmodels.is_downloaded("BAAI/bge-small-en-v1.5")


def test_the_state_of_a_cache_is_ready_partial_or_absent(tmp_path, monkeypatch):
    """INBOX 1290: each embedding row shows its real state."""
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    repo = "BAAI/bge-small-en-v1.5"
    assert embedmodels.snapshot_state(repo) == "absent"
    snapshot = tmp_path / "models--BAAI--bge-small-en-v1.5" / "snapshots" / "abc"
    snapshot.mkdir(parents=True)
    assert embedmodels.snapshot_state(repo) == "partial", "the folder an interrupted first request leaves"
    (snapshot / "model.safetensors").write_bytes(b"x")
    assert embedmodels.snapshot_state(repo) == "partial", "weights without config"
    (snapshot / "config.json").write_text("{}", encoding="utf-8")
    assert embedmodels.snapshot_state(repo) == "ready"


def test_the_catalogue_carries_each_rows_state(client, tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    snapshot = tmp_path / "models--BAAI--bge-small-en-v1.5" / "snapshots" / "abc"
    snapshot.mkdir(parents=True)
    rows = {row["model"]: row for row in client.get("/embedding-models/choices").json()["choices"] if row["backend"] == "sentence-transformers"}
    bge = rows["BAAI/bge-small-en-v1.5"]
    assert bge["state"] == "partial" and bge["downloaded"] is False
    #: `downloaded` is the whole-cache check (101c): modules.json, a
    #: tokenizer and weights of a believable size, not only weights and config.
    with (snapshot / "model.safetensors").open("wb") as weights:
        weights.truncate(120 * 1024 * 1024)  # sparse on disk
    for name in ("config.json", "tokenizer.json", "modules.json"):
        (snapshot / name).write_text("[]" if name == "modules.json" else "{}", encoding="utf-8")
    bge = {row["model"]: row for row in client.get("/embedding-models/choices").json()["choices"]}["BAAI/bge-small-en-v1.5"]
    assert bge["state"] == "ready" and bge["downloaded"] is True and bge["on_disk"]
    other = next(row for model, row in rows.items() if model != "BAAI/bge-small-en-v1.5")
    assert other["state"] == "absent" and other["on_disk"] == ""


def test_the_off_switch_stops_the_first_download(fake_st, monkeypatch):
    """docs/PRIVACY.md: `TESSELLATE_NO_AUTO_INSTALL` stops the search model's
    one-off fetch. An uncached model stays uncached and search uses keywords."""
    monkeypatch.setenv("TESSELLATE_NO_AUTO_INSTALL", "1")
    fake_st.local_works = False
    with pytest.raises(embeddings.EmbeddingCacheBroken):
        _service()._load_st_model()
    assert fake_st.calls == [True]
