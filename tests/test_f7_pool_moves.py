"""F7 (WORLD_CLASS_PLAN section 10): the threads moved onto `core/jobs.py`'s pool.

Two of the ratchet's sites moved on 2026-10-05 (`tests/test_flaw_class_lints.py`
lowered to match): the whole-notebook re-index, onto a `batch` lane of its own
so it never holds the model lane's captions and filing behind it, and the
model capability probe, a short HTTP call, onto the `cpu` lane. Neither shows
in the activity panel twice: the re-index has its own row, the probe is noise.
"""

from __future__ import annotations

from tessellate.ai import model_manager
from tessellate.core import deps, jobs


def test_the_reindex_runs_on_the_batch_lane_and_finishes(app_state, monkeypatch):
    seen = []
    real = jobs.enqueue

    def spy(kind, func, *args, **kwargs):
        seen.append(kind)
        return real(kind, func, *args, **kwargs)

    monkeypatch.setattr(jobs, "enqueue", spy)
    from tests.fakes import FakeEmbeddingService

    assert model_manager.start_reindex(deps.get_db(), FakeEmbeddingService(available=True))
    assert seen == ["reindex"]
    assert jobs.pool().lane_for("reindex") == "batch" != jobs.pool().lane_for("caption")
    import time

    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and model_manager.reindex_status()["status"] == "running":
        time.sleep(0.05)
    assert model_manager.reindex_status()["status"] == "success"
    jobs.shutdown(deadline=2.0)


def test_the_capability_probe_is_a_pool_job(monkeypatch):
    from tessellate.api import routes_models

    seen = []
    monkeypatch.setattr(jobs, "enqueue", lambda kind, func, *a, **k: seen.append(kind) or 1)

    class Client:
        def show(self, model):
            return {}

    routes_models._warm_capabilities(Client(), "tiny-model")
    assert seen == ["model-info"]
    assert "model-info" in jobs.QUIET_KINDS and "reindex" in jobs.QUIET_KINDS


def test_the_loaded_models_poll_leaves_no_history_row():
    #: INBOX 1620: it ran every thirty seconds and each run was a "Model info: loaded models" row.
    assert "model-poll" in jobs.QUIET_KINDS and "model-poll" in jobs.OWN_RUN_KINDS
