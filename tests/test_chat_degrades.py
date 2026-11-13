"""The model path degrades to the deterministic one (CHAT_PLAN "The degrade tests", L-chat-21).

Six failures of the model, on the fake transport (CLAUDE.md section 4: real
inference is not covered): the connection is refused; the first token never
arrives (a timeout); the stream dies after the first token; the stream dies at
the last token; the model returns empty text; the model returns text with no
sentence the notes support. Each leaves the bubble with at least what the
composer would have shown: the composed text, a line saying the model stopped,
never an error-only bubble, and `composition.fallback` true on the stats.
"""

from __future__ import annotations

import pytest

from tessellate.ai.ollama_client import OllamaError
from tessellate.api.chat_said import MODEL_STOPPED_NOTE
from tests.test_composer_route_688 import _ask
from tests.test_engine_identity import _seed

COMPOSED = "Ship Harbor to the public on the 14th of next month."
QUESTIONS = ("What is the Harbor launch plan?", "when does Harbor ship?", "tell me about the harbor launch")


def _refused(_messages):
    raise OllamaError("connection refused")
    yield  # pragma: no cover


def _timeout(_messages):
    raise OllamaError("timed out waiting for the first token")
    yield  # pragma: no cover


def _dies_after_first(_messages):
    yield {"content_delta": "Harbor "}
    raise OllamaError("connection reset")


def _dies_at_last(_messages):
    for word in ("Harbor ", "ships ", "to ", "the ", "public "):
        yield {"content_delta": word}
    raise OllamaError("connection reset")


def _empty(_messages):
    yield {"content_delta": ""}
    yield {"done": True, "stats": {"eval_count": 0}}


def _unsupported(_messages):
    yield {"content_delta": "Harbor was cancelled in 2019 by the board. The team moved to Lisbon."}
    yield {"done": True, "stats": {"eval_count": 14}}


FAILURES = {
    "refused": _refused,
    "timeout": _timeout,
    "dies_after_first": _dies_after_first,
    "dies_at_last": _dies_at_last,
    "empty": _empty,
    "unsupported": _unsupported,
}


class _Failing:
    def __init__(self, fake, stream):
        self.fake, self.stream = fake, stream

    def __getattr__(self, name):
        return getattr(self.fake, name)

    def chat_stream(self, model, messages, mode=None):  # noqa: ANN001, ARG002
        return self.stream(messages)


def _final(out: dict) -> str:
    return out["answer_final"][-1]["text"] if out.get("answer_final") else out["text"]


@pytest.mark.parametrize("question", QUESTIONS)
@pytest.mark.parametrize("failure", list(FAILURES))
def test_the_bubble_keeps_the_composed_answer(ai_client, fake_ollama, session, monkeypatch, failure, question):
    _seed(session)
    from tessellate.core import deps

    monkeypatch.setattr(deps, "get_ollama", lambda: _Failing(fake_ollama, FAILURES[failure]))
    out = _ask(ai_client, question, notes_only=True, use_tools=False, answer_from="ai")
    final = _final(out)
    assert COMPOSED in final, (failure, final)
    assert MODEL_STOPPED_NOTE in final, (failure, final)
    assert "cancelled in 2019" not in final
    stats = out.get("stats") or [{}]
    assert stats[-1].get("composition", {}).get("fallback") is True, (failure, stats)
