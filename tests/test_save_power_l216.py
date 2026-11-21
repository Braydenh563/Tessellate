"""CHAT_PLAN decision 61 (L-chat-216): Save power. With the Battery-efficient
mode setting on, a chat turn is answered by the engine alone with a model
running and says so in one line; the follow-up suggestion wakes no model
either. Off, the same turn is the model's."""

from __future__ import annotations

from tessellate.api import chat_turn
from tessellate.core import deps
from tests.test_composer_route_688 import _ask
from tests.test_engine_identity import _seed


def test_save_power_answers_from_the_engine_and_says_so(ai_client, fake_ollama, session):
    _seed(session)
    deps.get_config().set_preference("battery_efficient_mode", True)
    asked = len(fake_ollama.chat_models) + len(fake_ollama.chat_calls)
    out = _ask(ai_client, "What is the Harbor launch plan?", use_tools=False)
    assert out["meta"][0]["answered_by"] is None and out["meta"][0]["composed"] is True
    assert "Ship Harbor to the public on" in out["text"]
    assert out["text"].endswith(chat_turn.SAVE_POWER_LINE)
    assert len(fake_ollama.chat_models) + len(fake_ollama.chat_calls) == asked, "no model was asked"
    followups = ai_client.post("/chat/followups", json={"question": "What is the Harbor launch plan?", "answer": out["text"]})
    assert followups.json() == []
    assert len(fake_ollama.chat_models) + len(fake_ollama.chat_calls) == asked


def test_with_save_power_off_the_line_is_not_said(ai_client, fake_ollama, session):
    _seed(session)
    out = _ask(ai_client, "What is the Harbor launch plan?", use_tools=False)
    assert chat_turn.SAVE_POWER_LINE not in out["text"]


def test_a_generation_shows_in_activity_before_the_model_says_a_word():
    """Decision 61: a model start shows in Activity at once. The stream's job is
    listed while its source is still blocked, so the row never waits on the model."""
    import threading

    from tessellate.core import activity

    release = threading.Event()
    seen_blocked = threading.Event()

    def slow_model():
        seen_blocked.set()
        release.wait(10)
        yield '{"type": "done"}\n'

    stream = activity.tracked_stream("generation", "Answering in Chat", slow_model())
    first = []
    worker = threading.Thread(target=lambda: first.append(next(stream)), daemon=True)
    worker.start()
    assert seen_blocked.wait(5)
    try:
        assert [r["kind"] for r in activity.snapshot()] == ["generation"]
    finally:
        release.set()
        worker.join(5)
        stream.close()
