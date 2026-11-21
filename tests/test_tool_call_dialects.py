"""One test per dialect a local model actually writes a tool call in.

A model that emits the right call in the wrong syntax looks exactly like a
model that ignored the tool: nothing happens and the app says it did
something. These are the syntaxes the families in the README's model list
emit, taken from their own chat templates, plus the thinking-tag spellings
that ship with them. `tests/test_providers.py` covers the structured
`tool_calls` field; this file covers the text fallback only.
"""

import pytest

from tessellate.ai.provider import (
    _ThinkTagSplitter,
    extract_text_tool_calls,
    split_thinking,
)

TOOLS = {"create_note", "search_notes", "get_weather"}


def _one(text):
    calls, cleaned = extract_text_tool_calls(text, TOOLS)
    assert len(calls) == 1, (text, calls)
    return calls[0], cleaned


@pytest.mark.parametrize(
    ("family", "text"),
    [
        # Qwen, Hermes: the shape this was written for.
        ("qwen", '<tool_call>{"name": "create_note", "arguments": {"title": "a"}}</tool_call>'),
        # Granite and Phi write the same object behind a pipe spelling.
        ("granite", '<|tool_call|>{"name": "create_note", "arguments": {"title": "a"}}'),
        # Llama 3: a python_tag prefix, and `parameters` rather than `arguments`.
        ("llama-python-tag", '<|python_tag|>{"name": "create_note", "parameters": {"title": "a"}}'),
        # Llama 3 again: the name in the tag, the arguments alone in the object.
        ("llama-function-tag", '<function=create_note>{"title": "a"}</function>'),
        # DeepSeek: full-width pipe tokens, name outside, object in a fence.
        (
            "deepseek",
            "<｜tool▁calls▁begin｜>function<｜tool▁sep｜>create_note\n"
            '```json\n{"title": "a"}\n```',
        ),
        # Mistral.
        ("mistral", '[TOOL_CALLS] [{"name": "create_note", "arguments": {"title": "a"}}]'),
        # Gemma: a fenced object, no special tokens at all.
        ("gemma-json", 'Sure.\n```json\n{"name": "create_note", "arguments": {"title": "a"}}\n```'),
        # Gemma's own documented recipe: a python call inside a tool_code fence.
        ("gemma-tool-code", '```tool_code\nprint(create_note(title="a"))\n```'),
        # LFM2: a python call list between its own markers.
        ("lfm2", '<|tool_call_start|>[create_note(title="a")]<|tool_call_end|>'),
    ],
)
def test_every_family_s_call_is_recovered(family, text):
    call, _cleaned = _one(text)
    assert call == {"name": "create_note", "arguments": {"title": "a"}}, family


@pytest.mark.parametrize(
    ("family", "text"),
    [
        ("llama-function-tag", '<function=create_note>{"title": "a"}</function>'),
        ("lfm2", '<|tool_call_start|>[create_note(title="a")]<|tool_call_end|>'),
        ("gemma-tool-code", 'One moment.\n```tool_code\nprint(create_note(title="a"))\n```'),
        ("llama-python-tag", '<|python_tag|>{"name": "create_note", "parameters": {"title": "a"}}'),
    ],
)
def test_no_special_token_survives_into_the_answer(family, text):
    """The markers are special tokens, never prose: left in, a user reads
    them as the app being broken."""
    _call, cleaned = _one(text)
    for debris in ("<|", "|>", "</function>", "```", "print(", "[]"):
        assert debris not in cleaned, (family, cleaned)


def test_a_call_written_about_is_not_a_call_made():
    """The python-call pass is gated on a marker for exactly this reason: a
    model explaining itself must not file a note."""
    calls, cleaned = extract_text_tool_calls(
        'You would write create_note(title="x") to do that.', TOOLS
    )
    assert calls == []
    assert "create_note" in cleaned


def test_a_read_written_with_its_json_arguments_is_a_call():
    """Qwen2.5-3B in the loose-ends eval, 2026-10-05: "I've listed the notes:
    list_notes({"category": "General", "since": "this week"})", then "I cannot
    execute the tool call as I am a text-based AI". A JSON object as the one
    argument is the schema's own shape, a call rather than a description; it
    is taken ungated only for a read, which costs a round if it was not
    meant, never a change to the notebook."""
    import tessellate.ai.tools  # noqa: F401  registers the write list; alone, nothing is a read

    calls, cleaned = extract_text_tool_calls(
        'I\'ve listed the notes: search_notes({"query": "loose ends"}) and more.', TOOLS
    )
    assert calls == [{"name": "search_notes", "arguments": {"query": "loose ends"}}]
    assert "search_notes(" not in cleaned


def test_a_write_written_with_json_arguments_still_needs_a_marker():
    calls, cleaned = extract_text_tool_calls('You could call create_note({"content": "x"}) for that.', TOOLS)
    assert calls == []
    assert "create_note" in cleaned


def test_two_calls_in_one_lfm2_block():
    calls, _cleaned = extract_text_tool_calls(
        '<|tool_call_start|>[create_note(title="a"), search_notes(query="b")]<|tool_call_end|>',
        TOOLS,
    )
    assert [call["name"] for call in calls] == ["create_note", "search_notes"]


def test_a_name_with_no_object_near_it_adopts_nothing():
    calls, _cleaned = extract_text_tool_calls(
        "<function=create_note>" + ("x" * 5000) + '{"title": "a"}', TOOLS
    )
    assert calls == []


@pytest.mark.parametrize("word", ["think", "thinking", "thought", "reason", "reasoning"])
def test_every_thinking_spelling_is_separated(word):
    clean, thinking = split_thinking(f"<{word}>weighing it up</{word}>The answer")
    assert clean == "The answer"
    assert thinking == "weighing it up"


def test_a_close_with_no_open_is_deepseek_s_prefilled_tag():
    """DeepSeek's template ends the prompt with the opening tag, so the reply
    begins inside the thought and only the close is ever written. Requiring
    both tags handed the whole chain of reasoning to the user as the answer."""
    clean, thinking = split_thinking("First I check the notes.</think>You have three.")
    assert clean == "You have three."
    assert thinking == "First I check the notes."


def test_an_open_with_no_close_is_a_reply_cut_short():
    clean, thinking = split_thinking("<think>I was still going when")
    assert clean == ""
    assert thinking == "I was still going when"


def test_two_thoughts_are_both_kept_out_of_the_answer():
    clean, thinking = split_thinking("<think>one</think>A<think>two</think>B")
    assert clean == "AB"
    assert thinking == "one\n\ntwo"


def test_plain_text_is_untouched():
    assert split_thinking("just an answer") == ("just an answer", None)


def _stream(chunks):
    splitter = _ThinkTagSplitter()
    pieces = []
    for chunk in chunks:
        pieces.extend(splitter.feed(chunk))
    pieces.extend(splitter.flush())
    thinking = "".join(p["thinking_delta"] for p in pieces if "thinking_delta" in p)
    content = "".join(p["content_delta"] for p in pieces if "content_delta" in p)
    return content, thinking


def test_a_streamed_reasoning_tag_of_any_spelling_is_routed():
    content, thinking = _stream(["<reason", "ing>mulling", "</reasoning>", "Done"])
    assert content == "Done"
    assert thinking == "mulling"


def test_a_stray_close_tag_never_reaches_the_stream():
    """The prefilled-tag case cannot be split live without holding the whole
    reply back, so the text stays in the answer, but the raw tag must not."""
    content, thinking = _stream(["I check the notes.", "</think>", "You have three."])
    assert "</think>" not in content
    assert thinking == ""


def test_a_close_tag_split_across_chunks_is_still_caught():
    content, _thinking = _stream(["<think>a</th", "ink>b"])
    assert content == "b"


def test_qwen_small_doubled_opening_brace_is_still_the_call():
    """L-world-class-630, measured: Qwen2.5-1.5B on its own chat template in
    llama-cpp-python wrote this for "Open https://bread.example/", one `{`
    more than it closed. It read as no call, and the raw tag was the answer."""
    text = '<tool_call>\n{{"name": "search_notes", "arguments": {"query": "bread"}}\n</tool_call>'
    call, cleaned = _one(text)
    assert call["name"] == "search_notes" and call["arguments"] == {"query": "bread"}
    assert "<tool_call>" not in cleaned

