"""L122: a model that dies after some tokens leaves the composed answer, not
a half sentence and an error (the before-first-word case is in
test_engine_identity.py)."""

from __future__ import annotations

from tessellate.ai.ollama_client import OllamaError
from tessellate.api import routes_chat
from tests.test_composer_route_688 import _ask
from tests.test_engine_identity import _seed


class _DiesAfterWords:
    """A provider whose stream says two words, then drops."""

    def __init__(self, fake):
        self.fake = fake

    def __getattr__(self, name):
        return getattr(self.fake, name)

    def chat_stream(self, model, messages, mode=None):  # noqa: ANN001, ARG002
        yield {"content_delta": "The Harbor plan "}
        yield {"content_delta": "is probably "}
        raise OllamaError("connection reset")


def test_a_model_that_dies_mid_answer_is_replaced_by_the_composed_answer(ai_client, fake_ollama, session, monkeypatch):
    _seed(session)
    from tessellate.core import deps

    monkeypatch.setattr(deps, "get_ollama", lambda: _DiesAfterWords(fake_ollama))
    out = _ask(ai_client, "What is the Harbor launch plan?", notes_only=True, use_tools=False, answer_from="ai")
    final = out["answer_final"][-1]["text"]
    assert "Ship Harbor to the public on the 14th of next month." in final
    assert final.endswith(routes_chat.MODEL_STOPPED_NOTE)
    assert "probably" not in final
