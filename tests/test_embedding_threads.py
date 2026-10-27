"""One short note is embedded on one thread, never on a whole-machine pool
(INBOX 434, background filing took 1.2 to 4 seconds).

Measured on the 4-core sandbox with torch, one 70-character note, median:
4 intra-op threads idle 39 ms; 4 threads with the machine busy 2,192 ms;
1 thread busy 79 ms. A sentence this short is a handful of tiny matrix
products, so the pool's barrier waits cost far more than the arithmetic does
the moment another process wants a core. fastembed (ONNX Runtime) fixes the
count when its session is made, so these tests pin that the session is made
at the limit, that the environment can raise it, and that the model is
loaded once. They are timing free.
"""

from __future__ import annotations

import types

import pytest

from tessellate.ai import embeddings as emb
from tessellate.core import deps
from tests import _fake_fastembed as fake


@pytest.fixture
def engine(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    fake.snapshot(tmp_path / "hub")
    return fake.install(monkeypatch)


def _service(monkeypatch):  # noqa: ANN001
    service = deps.get_embeddings()
    monkeypatch.setattr(service, "_models", types.SimpleNamespace(embedding_backend=lambda: "fastembed"))
    service._st_model = None
    return service


def test_the_session_is_made_at_one_thread(app_state, engine, monkeypatch):
    monkeypatch.delenv("TESSELLATE_EMBED_THREADS", raising=False)
    model = emb._open_snapshot(engine, fake.BGE)
    assert model is not None
    assert [load["threads"] for load in engine.loads] == [emb.EMBED_THREADS] == [1]


def test_the_environment_can_raise_it(app_state, engine, monkeypatch):
    monkeypatch.setenv("TESSELLATE_EMBED_THREADS", "3")
    emb._open_snapshot(engine, fake.BGE)
    assert engine.loads[0]["threads"] == 3
    monkeypatch.setenv("TESSELLATE_EMBED_THREADS", "not a number")
    assert emb.embed_threads() == emb.EMBED_THREADS


def test_the_model_is_loaded_once_across_many_embeds(app_state, engine, monkeypatch):
    service = _service(monkeypatch)
    loads = []
    model = engine(model_name=fake.BGE)
    engine.loads.clear()
    monkeypatch.setattr(service, "_load_builtin_model", lambda: (loads.append(1), model)[1])

    for text in ("first note", "second note", "third note"):
        assert service.embed_text(text) is not None

    assert len(loads) == 1
    assert engine.embeds == [["first note"], ["second note"], ["third note"]]


def test_a_vector_is_the_models_own_unit_vector(app_state, engine, monkeypatch):
    """The engine already normalises (cosine), and its 384 floats arrive as
    float32, the stored format."""
    service = _service(monkeypatch)
    service._st_model = engine(model_name=fake.BGE)
    vector = service.embed_text("a note")
    assert vector.dtype.name == "float32" and vector.shape == (384,)
    assert abs(float((vector * vector).sum()) - 1.0) < 1e-5
