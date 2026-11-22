"""L107: the ask-chat Guide topic says Agent mode needs a model, inside the 1,900 character reply budget."""

from __future__ import annotations

from tessellate.ai import help_chat


def _body() -> str:
    return next(t["body"] for t in help_chat.HELP_TOPICS if t["id"] == "ask-chat")


def test_ask_chat_says_agent_mode_needs_a_model():
    assert "Agent mode (a toggle in Chat) needs a model, and lets" in _body()


def test_ask_chat_stays_inside_the_reply_budget():
    assert len(_body()) < 1900, len(_body())
