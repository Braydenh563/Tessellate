"""An app with no password runs its launch work at once, even when an app
built earlier in the same process armed the hold (CI flake on
test_the_launch_switch_decides_whether_startup_warms_the_model)."""

from tessellate.core import afterunlock


def test_an_app_without_a_password_drops_an_earlier_hold(app_state, monkeypatch):
    from tessellate.ai import embeddings
    from tessellate.api.app import create_app

    calls = []
    monkeypatch.setattr(embeddings, "start_warmup", lambda *a, **k: calls.append(1))
    app_state.set_preference("warm_search_model_at_launch", True)
    afterunlock.arm()
    try:
        create_app()
        assert not afterunlock.armed()
        assert len(calls) == 1
    finally:
        afterunlock.disarm()
