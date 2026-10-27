"""The embedding model is dropped after an idle hour and loads again on use (decision 62)."""

from __future__ import annotations

import types

from tessellate.ai.embeddings import EmbeddingService


def _service(minutes=60):
    service = object.__new__(EmbeddingService)
    service._st_model = object()
    service._was_loaded = True
    service._last_used = 1000.0
    service._models = types.SimpleNamespace(
        _config=types.SimpleNamespace(get_preference=lambda key, default=None: minutes if key == "embedder_idle_unload_minutes" else default)
    )
    return service


def test_the_model_is_kept_inside_the_idle_window_and_dropped_after_it():
    service = _service()
    assert service.unload_if_idle(now=1000.0 + 59 * 60) is False and service._st_model is not None
    assert service.unload_if_idle(now=1000.0 + 61 * 60) is True and service._st_model is None


def test_an_unloaded_model_still_counts_as_ready():
    service = _service()
    service.unload_if_idle(now=1000.0 + 3700)
    service._models.embedding_backend = lambda: "fastembed"
    assert service.is_ready() is True


def test_zero_minutes_turns_the_unload_off():
    service = _service(minutes=0)
    assert service.unload_if_idle(now=10**9) is False and service._st_model is not None
