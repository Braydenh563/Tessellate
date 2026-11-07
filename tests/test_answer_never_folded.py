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


def _split_live(chunks):
    """(thinking before the end, answer before the end, thinking, answer)."""
    splitter = _ThinkTagSplitter()
    pieces = []
    for chunk in chunks:
        pieces += splitter.feed(chunk)
    live = list(pieces)
    pieces += splitter.flush()
    pick = lambda ps, key: "".join(p[key] for p in ps if key in p)  # noqa: E731
    return pick(live, "thinking_delta"), pick(live, "content_delta"), pick(pieces, "thinking_delta"), pick(pieces, "content_delta")


def test_a_preamble_that_never_closes_shows_each_word_once():
    """Review of B1: with no close tag the steps went to the fold and the whole
    text, steps and header included, to the answer as well. The steps stream
    into the fold as they come; the prose after the last step is held, and is
    the answer when the reply ends without a close."""
    text = f"Thinking Process:\n\n{STEPS}\n{ANSWER}"
    for size in (1, 3, 9, len(text)):
        live_thinking, live_answer, thinking, answer = _split_live(_chunked(text, size))
        assert answer.strip() == ANSWER, size
        assert "Analyze the request" in thinking and "Draft the answer" in thinking, size
        assert "Analyze the request" not in answer and "Thinking Process" not in answer + thinking, size
        assert ANSWER not in thinking, size
        assert not live_answer, size
    #: The steps are on screen while the reply is still coming.
    live_thinking, *_ = _split_live(_chunked(text, 9))
    assert "Search the context" in live_thinking
    #: The reviewer's probe.
    *_, thinking, answer = _split_live(_chunked("Thinking Process:\n1. a\n2. b\nThe answer.", 2))
    assert (thinking.strip(), answer.strip()) == ("1. a\n2. b", "The answer.")


def test_a_header_over_plain_prose_is_all_answer():
    """Nothing reads as a step: no word went to the fold, so the whole text,
    header and all, is the answer, once."""
    text = "Reasoning:\nBeans swell as they soak, so soak them overnight."
    *_, thinking, answer = _split_live(_chunked(text, 4))
    assert answer == text and not thinking


def test_a_header_that_ends_on_a_step_keeps_every_word_in_the_answer():
    """No prose after the steps: nothing marks an answer, so the answer is
    the whole text (never lost to the fold)."""
    *_, thinking, answer = _split_live(_chunked("Thinking:\n1. buy beans\n2. soak them", 3))
    assert "1. buy beans" in answer and "2. soak them" in answer


def test_a_saved_reply_that_never_closes_splits_as_the_stream_did():
    clean, thinking = split_thinking(f"Thinking Process:\n\n{STEPS}\n{ANSWER}")
    assert clean == ANSWER
    assert thinking == STEPS.strip()
    assert split_thinking("Reasoning:\nBeans swell, so soak them.") == ("Reasoning:\nBeans swell, so soak them.", None)


#: Review of PR 216: an answer that is itself a list. The steps end at the
#: first prose line that follows a blank line; the list under it is the answer.
LISTED = "Here's the answer:\n- soak the beans\n- boil them\nHope that helps"


def test_an_answer_that_is_a_list_is_not_pulled_into_the_fold():
    text = f"Thinking Process:\n1. **Analyze:** beans.\n2. **Draft:** a list.\n\n{LISTED}"
    for size in (1, 3, 9, len(text)):
        live_thinking, live_answer, thinking, answer = _split_live(_chunked(text, size))
        assert answer.strip() == LISTED, size
        assert thinking.strip() == "1. **Analyze:** beans.\n2. **Draft:** a list.", size
        # Never on screen as reasoning, even briefly.
        assert "soak the beans" not in live_thinking and "Here's the answer" not in live_thinking, size
    assert split_thinking(text) == (LISTED, "1. **Analyze:** beans.\n2. **Draft:** a list.")


def test_prose_in_the_middle_of_the_steps_without_a_blank_line_stays_in_the_fold():
    text = "Thinking Process:\n1. a\nso the person wants beans\n2. b\n\nThe answer."
    *_, thinking, answer = _split_live(_chunked(text, 2))
    assert "so the person wants beans" in thinking and "2. b" in thinking
    assert answer.strip() == "The answer."


def test_a_bare_reasoning_header_over_a_plain_list_is_still_the_answer():
    """Is "Reasoning:" alone on a first line ever a real answer? It can be: a
    list the person asked for under that heading. With no prose after the
    steps nothing marks an answer, so the whole text is the answer."""
    *_, thinking, answer = _split_live(_chunked("Reasoning:\n- cheap\n- fast\n", 3))
    assert "- cheap" in answer and "- fast" in answer
