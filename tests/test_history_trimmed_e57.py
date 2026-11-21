"""Audit 1028 E57: when a long chat no longer fits the model's window, say so.

`context.fit_history` drops the oldest exchanges silently, so a model that
"forgot" the start of a chat looked like a model that was wrong. The turn now
reports how many exchanges it left out (`composition.history_dropped`, only
when some were) and the chat shows one line under the reply. Model on and off
both behave (CHAT_PLAN decision 75): with no model nothing is sent to a window,
so there is nothing to drop and no notice.
"""

from __future__ import annotations

import json

import pytest

from tessellate.ai import context, librarian
from tests import _js_scope
from tests._app_js import frontend_text


def _history(pairs: int, size: int = 900) -> list[dict]:
    filler = "word " * (size // 5)
    return [{"question": f"question {i} {filler}", "answer": f"answer {i} {filler}"} for i in range(pairs)]


def _events(client, question, **body):
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as r:
        return [json.loads(line) for line in r.iter_lines() if line.strip()]


@pytest.mark.parametrize("pairs", [1, 2, 4, 6])
def test_history_dropped_counts_the_exchanges_the_budget_cut(pairs):
    history = _history(pairs)
    past = librarian.history_messages(history)
    kept = context.fit_history(past, 1500)
    sent = [{"role": "system", "content": "s"}, *kept, {"role": "user", "content": "q"}]
    expected = (len(past) - len(kept)) // 2
    assert librarian.history_dropped(history, sent) == expected
    assert librarian.history_dropped(history, [sent[0], *past, sent[-1]]) == 0


def test_nothing_dropped_for_no_history():
    assert librarian.history_dropped(None, [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}]) == 0


def test_a_small_window_reports_the_dropped_exchanges_with_a_model_in_ask_mode(ai_client, fake_ollama):
    ai_client.post("/entries", json={"content": "a note about kayaking"})
    fake_ollama.context_tokens = 4096
    fake_ollama.librarian_reply = "You wrote about kayaking."
    events = _events(ai_client, "what did I write about kayaking?", use_tools=False, history=_history(8))
    stats = next(e for e in events if e["type"] == "stats")
    assert stats["composition"]["history_dropped"] >= 1, stats["composition"]


def test_a_small_window_reports_the_dropped_exchanges_in_agent_mode(ai_client, fake_ollama):
    ai_client.post("/entries", json={"content": "a note about kayaking"})
    fake_ollama.context_tokens = 4096
    fake_ollama.librarian_reply = "Done."
    events = _events(ai_client, "use your tools to look over my notebook", history=_history(8))
    stats = [e for e in events if e["type"] == "stats"]
    assert stats and stats[0]["composition"]["history_dropped"] >= 1, stats[:1]


def test_a_roomy_window_reports_nothing(ai_client, fake_ollama):
    ai_client.post("/entries", json={"content": "a note about kayaking"})
    fake_ollama.context_tokens = 131_072
    fake_ollama.librarian_reply = "You wrote about kayaking."
    events = _events(ai_client, "what did I write about kayaking?", use_tools=False, history=_history(3, 200))
    stats = next(e for e in events if e["type"] == "stats")
    assert "history_dropped" not in stats["composition"]


def test_with_no_model_there_is_no_stats_and_no_notice(ai_client, fake_ollama):
    ai_client.post("/entries", json={"content": "a note about kayaking"})
    fake_ollama.running = False
    events = _events(ai_client, "what did I write about kayaking?", use_tools=False, history=_history(8))
    assert not [e for e in events if e["type"] == "stats"]


@pytest.mark.parametrize(
    "question",
    ["what is the context window", "why did the model forget the start of my chat", "what does the context pill do"],
)
def test_the_guide_explains_the_line_and_the_pill(question):
    from tessellate.ai import help_chat

    assert help_chat.topics_for(question)[0]["id"] == "chat-context"


def test_the_chat_draws_one_line_under_a_trimmed_reply():
    
    kit = _js_scope.unwrapped(frontend_text("reply-kit.js"))
    assert "function renderHistoryTrimmedNotice" in kit
    assert "renderHistoryTrimmedNotice(opts.bubble, opts.trimmed)" in kit
    assert "composition?.history_dropped" in frontend_text("chat-turn.js")
