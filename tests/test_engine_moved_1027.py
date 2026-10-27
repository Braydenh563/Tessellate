"""Someone who upgrades from the PyTorch engine is told the engine moved
(the owner, 2026-10-27: keep the ask, since nothing downloads without a yes).

Their cache holds `models--BAAI--bge-small-en-v1.5` (safetensors) and not the
ONNX build the new engine reads (`models--Qdrant--...`), so search by meaning
needs one download. The notice and the welcome card then say what is going on
instead of the first-time wording: the download replaces the old engine, the
notes' search data is kept or read again, and keywords work meanwhile. Every
cache here is a fake folder in a temp dir; nothing reaches a network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tessellate.core import deps, embedmodels

ROOT = Path(__file__).resolve().parents[1]

BGE = "BAAI/bge-small-en-v1.5"


@pytest.fixture
def hf_cache(tmp_path, monkeypatch):
    """An empty Hugging Face cache the app reads instead of the real one."""
    cache = tmp_path / "hub"
    cache.mkdir()
    monkeypatch.setenv("HF_HUB_CACHE", str(cache))
    return cache


def _old_copy(cache: Path, repo: str, files=("model.safetensors",)) -> Path:
    """What the sentence-transformers engine left: a snapshot of PyTorch weights."""
    snapshot = cache / ("models--" + repo.replace("/", "--")) / "snapshots" / "abc123"
    snapshot.mkdir(parents=True)
    for name in files:
        (snapshot / name).write_bytes(b"w" * 2048)
    (snapshot / "config.json").write_text("{}", encoding="utf-8")
    return snapshot


def _new_build(cache: Path, repo: str) -> None:
    """A whole ONNX build for `repo`, the state after the download."""
    build = embedmodels.build_for(repo)
    snapshot = cache / ("models--" + build.source.replace("/", "--")) / "snapshots" / "def456"
    (snapshot / Path(build.model_file).parent).mkdir(parents=True, exist_ok=True)
    (snapshot / build.model_file).write_bytes(b"o" * 4096)
    (snapshot / "config.json").write_text("{}", encoding="utf-8")


def test_the_old_copy_alone_reads_as_a_moved_engine(hf_cache):
    _old_copy(hf_cache, BGE)
    assert embedmodels.is_downloaded(BGE) is False
    moved = embedmodels.engine_moved(BGE)
    assert moved == {"vectors": "kept", "download": "about 130 MB"}


def test_a_model_whose_notes_are_embedded_again_says_so(hf_cache):
    """MiniLM was never compared across the engines, so its notes are read again."""
    _old_copy(hf_cache, "sentence-transformers/all-MiniLM-L6-v2")
    moved = embedmodels.engine_moved("sentence-transformers/all-MiniLM-L6-v2")
    assert moved is not None and moved["vectors"] == "again"


def test_nothing_is_said_without_an_old_copy_or_once_the_new_build_is_here(hf_cache):
    assert embedmodels.engine_moved(BGE) is None
    _old_copy(hf_cache, BGE)
    _new_build(hf_cache, BGE)
    assert embedmodels.is_downloaded(BGE) is True
    assert embedmodels.engine_moved(BGE) is None


def test_a_model_outside_the_catalogue_is_left_alone(hf_cache):
    _old_copy(hf_cache, "someone/typed-model")
    assert embedmodels.engine_moved("someone/typed-model") is None


def test_the_status_and_the_preferences_carry_it_while_the_question_is_open(client, hf_cache):
    _old_copy(hf_cache, BGE)
    deps.get_embeddings().awaiting_consent = True
    status = client.get("/models/status").json()
    assert status["semantic_offer"] is True
    assert status["semantic_engine_moved"] == {"vectors": "kept", "download": "about 130 MB"}
    prefs = client.get("/preferences").json()
    assert prefs["semantic_engine_moved"] == {"vectors": "kept", "download": "about 130 MB"}


def test_a_first_time_user_gets_the_plain_question(client, hf_cache):
    deps.get_embeddings().awaiting_consent = True
    assert client.get("/models/status").json()["semantic_engine_moved"] is None
    assert client.get("/preferences").json()["semantic_engine_moved"] is None


def test_an_answered_question_asks_nothing_more(client, hf_cache):
    _old_copy(hf_cache, BGE)
    answered = client.put("/preferences", json={"semantic_auto_install": False})
    assert answered.status_code == 200
    assert client.get("/preferences").json()["semantic_engine_moved"] is None


def test_the_notice_and_the_welcome_card_use_the_server_s_words():
    js = (ROOT / "frontend" / "js" / "semantic-notice.js").read_text(encoding="utf-8")
    assert "function semanticQuestionText(moved)" in js
    assert "The search engine moved." in js
    assert "nothing is embedded again" in js
    assert "prefs.semantic_engine_moved" in js
    assert chr(0x2014) not in js
