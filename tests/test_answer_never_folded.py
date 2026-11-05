"""CHAT_PLAN B1 (the owner, 2026-11-05).

B1: "also the whole response from my ai model just got placed in a dropdown
collapsed box". Two classes did it: a model that writes its reasoning as an
untagged "Thinking Process:" preamble (the `<think>` open tag is in the
prompt, so the only tag it writes is the close, which the stream drops) had
all of it streamed as the answer, and the long-block fold (`replyFoldLong`)
then shut a model's own answer paragraph into a "145 words" card. The answer
is never in a fold; the reasoning always is.
"""

from __future__ import annotations

from pathlib import Path

from fakes_http import FakeResponse, sse

from tessellate.ai.ollama_client import _ThinkTagSplitter, split_thinking

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"

#: The owner's shape: a "Thinking Process:" header, numbered steps, the stray
#: close tag a template that opened the thought leaves, then the answer.
STEPS = (
    "1. **Analyze the request:** the person asks what their notes say about beans.\n"
    "2. **Search the context:** note 3 mentions soaking beans overnight.\n"
    "3. **Draft the answer:** say it plainly and cite note 3.\n"
)
ANSWER = "Your notes say to soak the beans overnight before cooking them [3]."
REPLY = f"Thinking Process:\n\n{STEPS}</think>\n\n{ANSWER}"


def _split(chunks):
    splitter = _ThinkTagSplitter()
    pieces = []
    for chunk in chunks:
        pieces += splitter.feed(chunk)
    pieces += splitter.flush()
    thinking = "".join(p["thinking_delta"] for p in pieces if "thinking_delta" in p)
    answer = "".join(p["content_delta"] for p in pieces if "content_delta" in p)
    return thinking, answer


def _chunked(text, size):
    return [text[i : i + size] for i in range(0, len(text), size)]


def test_an_untagged_thinking_process_preamble_streams_as_reasoning():
    for size in (1, 3, 7, 40, len(REPLY)):
        thinking, answer = _split(_chunked(REPLY, size))
        assert answer.strip() == ANSWER, size
        assert "Analyze the request" in thinking and "Draft the answer" in thinking, size
        assert "Thinking Process" not in answer and "</think>" not in answer, size


def test_the_header_spellings_a_model_writes_are_all_reasoning():
    for header in ("Thinking Process:", "**Thinking Process:**", "## Thinking process:", "Thought process:", "Reasoning:"):
        thinking, answer = _split(_chunked(f"{header}\n{STEPS}</think>\n{ANSWER}", 5))
        assert answer.strip() == ANSWER, header
        assert "Search the context" in thinking, header


def test_a_preamble_that_never_closes_keeps_its_words_as_the_answer():
    """No close tag at all: nothing says where the answer starts, so the text
    is never lost to the fold."""
    text = f"Thinking Process:\n\n{STEPS}\n{ANSWER}"
    thinking, answer = _split(_chunked(text, 9))
    assert ANSWER in answer


def test_an_answer_that_merely_starts_with_the_word_is_an_answer():
    for text in ("Thinking about beans: soak them overnight.", "Reasoning aside, soak them.", "Thinking"):
        thinking, answer = _split(_chunked(text, 4))
        assert answer == text and not thinking, text


def test_a_saved_reply_of_that_shape_splits_the_same_way():
    clean, thinking = split_thinking(REPLY)
    assert clean == ANSWER
    assert thinking and thinking.startswith("1. **Analyze") and "Thinking Process" not in thinking


def test_the_openai_stream_routes_the_preamble_to_reasoning(openai_client, capture_post):
    deltas = [{"choices": [{"delta": {"content": part}}]} for part in _chunked(REPLY, 6)]
    capture_post.queue.append(FakeResponse(lines=sse(*deltas)))
    pieces = list(openai_client.chat_stream("m", [{"role": "user", "content": "beans?"}]))
    answer = "".join(p.get("content_delta", "") for p in pieces)
    thinking = "".join(p.get("thinking_delta", "") for p in pieces)
    assert answer.strip() == ANSWER and "Analyze the request" in thinking


def test_the_agent_stream_routes_the_preamble_to_reasoning(openai_client, capture_post):
    deltas = [{"choices": [{"delta": {"content": part}}]} for part in _chunked(REPLY, 6)]
    capture_post.queue.append(FakeResponse(lines=sse(*deltas)))
    pieces = list(openai_client.chat_tools_stream("m", [{"role": "user", "content": "beans?"}], []))
    answer = "".join(p.get("content_delta", "") for p in pieces)
    final = next(p["final"] for p in pieces if "final" in p)
    assert answer.strip() == ANSWER and final["content"] == ANSWER
    assert "Analyze the request" in (final["thinking"] or "")


def test_a_model_written_answer_is_never_folded():
    """`replyFoldLong` (INBOX 1300 C08) was asked for text the composer
    writes ("abrieviated/summarised by the composer"), and it shut a model's
    own long paragraph into a collapsed card. It runs on a composed reply
    only; every surface passes `composed` (Chat, Ask, the popup agent, the
    Guide)."""
    kit = (JS / "reply-kit.js").read_text(encoding="utf-8")
    assert "if (opts.composed) for (const answer of list) replyFoldLong(answer);" in kit
    for name in ("ask-compose.js", "chat-turn.js", "palette.js", "help-chat.js"):
        source = (JS / name).read_text(encoding="utf-8")
        assert "finishReply(" in source and "composed:" in source, name
