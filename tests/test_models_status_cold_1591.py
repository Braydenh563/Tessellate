"""INBOX 1591, a31m: `/models/status` 3908ms cold.

The route itself answers in ~15ms on a cold process (its slow parts were already cached, made lazy or
budgeted: `_installed_state`, `INSTALLED_COLD_BUDGET`, `prewarm_installed`). The time was FastAPI's lazy
route state: the first dispatch of any request builds the effective routes for all ~240 paths under one
lock (~0.9s here, about four times that on the owner's machine), and the browser's boot burst of ~30
requests all queued behind it, `/models/status` among them. The class is "the first request of a launch
pays for the whole app's routes", so the launch pays it instead: a background job dispatches one
in-process `/health` after the server is up.
"""

from __future__ import annotations

from pathlib import Path

from tessellate.api import app as app_module

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "tessellate" / "api" / "app.py").read_text(encoding="utf-8")


def test_lifespan_warms_routes_off_the_event_loop_and_not_in_tests():
    life = APP.split("async def lifespan(", 1)[1].split("yield", 1)[0]
    assert "_warm_routes" in life
    warm = APP.split("def _warm_routes(", 1)[1].split("\ndef ", 1)[0]
    assert "PYTEST_CURRENT_TEST" in warm, "a test app must not pay a second of warm-up per app"
    assert "jobs.thread(" in warm, "not a new thread site (tests/test_flaw_class_lints.py)"
    assert "/health" in warm


def test_warm_dispatches_a_real_request_and_leaves_the_app_working(client, monkeypatch):
    seen = []

    def inline(name, target, stop=None):
        seen.append(name)
        target()

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(app_module.jobs, "thread", inline)
    app_module._warm_routes(client.app)
    assert seen == ["route warm"]
    assert client.get("/health").status_code == 200


def test_warm_is_skipped_under_pytest(monkeypatch):
    called = []
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "x")
    monkeypatch.setattr(app_module.jobs, "thread", lambda *a, **k: called.append(a))
    app_module._warm_routes(object())
    assert called == []
