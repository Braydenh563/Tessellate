"""The previous engine's files can be removed from the app (the owner, 2026-10-27).

After the move to fastembed the Hugging Face cache still holds each model's
PyTorch copy (`models--BAAI--...`, `models--intfloat--...`) and a packaged app's
extras folder still holds torch and sentence-transformers. Once the new build
of the model in use is in place, Settings, Search and index lists them with
their sizes and Remove deletes one. Every cache here is a fake folder in a temp
dir; nothing reaches a network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tessellate.core import embedmodels, extras

ROOT = Path(__file__).resolve().parents[1]

BGE = "BAAI/bge-small-en-v1.5"
E5 = "intfloat/multilingual-e5-small"


@pytest.fixture
def hf_cache(tmp_path, monkeypatch):
    cache = tmp_path / "hub"
    cache.mkdir()
    monkeypatch.setenv("HF_HUB_CACHE", str(cache))
    return cache


def _snapshot(cache: Path, repo: str, name: str = "abc123") -> Path:
    path = cache / ("models--" + repo.replace("/", "--")) / "snapshots" / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _old_copy(cache: Path, repo: str, size: int = 2048) -> Path:
    snapshot = _snapshot(cache, repo)
    (snapshot / "model.safetensors").write_bytes(b"w" * size)
    (snapshot / "config.json").write_text("{}", encoding="utf-8")
    return snapshot


def _new_build(cache: Path, repo: str) -> Path:
    build = embedmodels.build_for(repo)
    snapshot = _snapshot(cache, build.source, "def456")
    (snapshot / build.model_file).parent.mkdir(parents=True, exist_ok=True)
    (snapshot / build.model_file).write_bytes(b"o" * 4096)
    (snapshot / "config.json").write_text("{}", encoding="utf-8")
    return snapshot


def test_the_old_folder_is_listed_with_its_size(hf_cache):
    _old_copy(hf_cache, BGE, size=3000)
    rows = embedmodels.legacy_files()
    assert [(row["id"], row["folder"], row["bytes"]) for row in rows] == [
        ("bge-small", "models--BAAI--bge-small-en-v1.5", 3000 + 2)
    ]
    assert rows[0]["size"] == "3 KB"


def test_removing_it_deletes_that_folder_and_nothing_else(hf_cache):
    _old_copy(hf_cache, BGE)
    new = _new_build(hf_cache, BGE)
    removed, message = embedmodels.remove_legacy("bge-small")
    assert removed is True, message
    assert not (hf_cache / "models--BAAI--bge-small-en-v1.5").exists()
    assert (new / "config.json").is_file()
    assert embedmodels.is_downloaded(BGE) is True
    assert embedmodels.legacy_files() == []


def test_a_model_whose_new_build_shares_the_folder_loses_only_the_pytorch_weights(hf_cache):
    """E5's ONNX build is its own repo, so the old and new files sit together."""
    snapshot = _old_copy(hf_cache, E5)
    new = _new_build(hf_cache, E5)
    assert new == snapshot or new.parent == snapshot.parent
    removed, message = embedmodels.remove_legacy("me5-small")
    assert removed is True, message
    shared = hf_cache / "models--intfloat--multilingual-e5-small" / "snapshots"
    assert not list(shared.glob("*/model.safetensors"))
    assert list(shared.glob("*/onnx/model.onnx"))
    assert embedmodels.is_downloaded(E5) is True


def _blob_store(cache: Path, repo: str, shared_with: str = "") -> Path:
    """E5's weights as the hub keeps them: a blob the snapshot links to, the
    same blob linked from a second revision, and optionally from another repo."""
    blob = cache / "blobs" / "ab"
    blob.mkdir(parents=True)
    weights = blob / "hash1"
    weights.write_bytes(b"w" * 2048)
    for revision in ("one", "two"):
        (_snapshot(cache, repo, revision) / "model.safetensors").symlink_to(weights)
    if shared_with:
        (_snapshot(cache, shared_with) / "pytorch_model.bin").symlink_to(weights)
    return weights


def test_a_blob_goes_with_its_last_link(hf_cache):
    """The hub keeps weights in a blob store the snapshots link to; both
    revisions' links go together, so the blob goes with them."""
    weights = _blob_store(hf_cache, E5)
    _new_build(hf_cache, E5)
    removed, _message = embedmodels.remove_legacy("me5-small")
    assert removed is True
    assert not weights.exists()


def test_a_blob_another_repo_still_links_to_stays(hf_cache):
    weights = _blob_store(hf_cache, E5, shared_with="someone/else")
    _new_build(hf_cache, E5)
    removed, _message = embedmodels.remove_legacy("me5-small")
    assert removed is True
    assert weights.is_file()


def test_a_name_outside_the_catalogue_removes_nothing(hf_cache):
    _old_copy(hf_cache, BGE)
    removed, message = embedmodels.remove_legacy("../../etc")
    assert removed is False and message == "No such embedding model."
    assert (hf_cache / "models--BAAI--bge-small-en-v1.5").is_dir()


def test_nothing_to_remove_says_so(hf_cache):
    removed, message = embedmodels.remove_legacy("bge-small")
    assert removed is False and "not on this computer" in message


def test_the_choices_list_them_only_once_the_new_build_is_here(client, hf_cache):
    _old_copy(hf_cache, BGE)
    legacy = client.get("/embedding-models/choices").json()["legacy"]
    assert legacy == {"files": [], "engine": None}
    _new_build(hf_cache, BGE)
    legacy = client.get("/embedding-models/choices").json()["legacy"]
    assert [row["id"] for row in legacy["files"]] == ["bge-small"]


def test_the_remove_route_is_refused_before_the_new_build_and_works_after(client, hf_cache):
    _old_copy(hf_cache, BGE)
    early = client.delete("/embedding-models/legacy/bge-small").json()
    assert early["removed"] is False and "Download the new search model first" in early["message"]
    assert (hf_cache / "models--BAAI--bge-small-en-v1.5").is_dir()
    _new_build(hf_cache, BGE)
    done = client.delete("/embedding-models/legacy/bge-small").json()
    assert done["removed"] is True
    assert not (hf_cache / "models--BAAI--bge-small-en-v1.5").exists()


# --- the packages in a packaged app's extras folder -------------------------


def _fake_dist(target: Path, name: str, files: dict[str, str]) -> None:
    dist_info = target / f"{name.replace('-', '_')}-1.0.dist-info"
    dist_info.mkdir(parents=True)
    (dist_info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\n")
    record = []
    for rel, text in files.items():
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        record.append(f"{rel},,{len(text)}")
    record.append(f"{dist_info.name}/METADATA,,")
    record.append(f"{dist_info.name}/RECORD,,")
    (dist_info / "RECORD").write_text("\n".join(record) + "\n")


@pytest.fixture
def packaged(app_state, tmp_path, monkeypatch):
    """A packaged build whose extras folder holds the old engine and an
    unrelated package."""
    target = tmp_path / "python-extras" / "cp313"
    target.mkdir(parents=True)
    monkeypatch.setattr(extras, "frozen_extras_dir", lambda: target)
    monkeypatch.setattr(extras, "_dispatch", lambda func, *args, name="": func(*args))
    extras._forget_footprints()
    _fake_dist(target, "torch", {"torch/__init__.py": "x" * 5000, "torch/lib.so": "y" * 5000})
    _fake_dist(target, "sentence-transformers", {"sentence_transformers/__init__.py": "z" * 1000})
    _fake_dist(target, "faster-whisper", {"faster_whisper/__init__.py": "keep"})
    return target


def test_the_old_engine_is_listed_with_the_size_of_its_two_packages(packaged):
    found = extras.legacy_engine()
    assert found is not None and found["id"] == "engine"
    assert found["bytes"] >= 11000


def test_removing_it_takes_those_two_packages_and_not_the_rest(packaged):
    started, message = extras.remove_legacy_engine()
    assert started is True, message
    assert not (packaged / "torch").exists()
    assert not (packaged / "sentence_transformers").exists()
    assert (packaged / "faster_whisper" / "__init__.py").is_file()
    assert extras.current().outcome == "completed"
    assert extras.legacy_engine() is None


def test_a_removal_leaves_the_installer_free_for_the_next_job(packaged):
    """A pip removal used to leave the installer marked running, so every
    install after it was refused as already running."""
    extras.remove_legacy_engine()
    assert extras.current().running is False
    assert extras._busy() is False


def test_outside_a_packaged_build_there_is_nothing_to_offer(monkeypatch):
    monkeypatch.setattr(extras, "frozen_extras_dir", lambda: None)
    assert extras.legacy_engine() is None
    started, message = extras.remove_legacy_engine()
    assert started is False and "not in this app" in message


def test_the_choices_carry_the_engine_in_a_packaged_build(client, hf_cache, packaged):
    _new_build(hf_cache, BGE)
    legacy = client.get("/embedding-models/choices").json()["legacy"]
    assert legacy["engine"]["id"] == "engine" and legacy["engine"]["size"]
    done = client.delete("/embedding-models/legacy/engine").json()
    assert done["removed"] is True
    assert client.get("/embedding-models/choices").json()["legacy"]["engine"] is None


# --- the page ---------------------------------------------------------------


def test_the_settings_list_is_drawn_by_the_lazy_file_with_the_row_recipe():
    js = (ROOT / "frontend" / "js" / "embed-choices.js").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="embed-legacy"' in html and 'id="embed-legacy-box"' in html
    assert "function renderEmbedLegacy(legacy)" in js
    assert 'rowActions([{ label: "ph:trash Remove"' in js
    assert "/embedding-models/legacy/" in js
    assert "Old search files" in html
    assert chr(0x2014) not in js


def test_the_guide_and_the_settings_help_name_the_list():
    topics = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")
    assert "Old search files" in topics and "search-engine-moved" in topics
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "Old search files lists what the old engine" in html
