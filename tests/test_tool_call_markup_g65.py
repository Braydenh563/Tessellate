"""L-general-65: a `<tool_call>` block whose body does not parse is markup, never shown as the answer."""

from tessellate.ai.provider import drop_tool_call_blocks, extract_text_tool_calls

TOOLS = {"create_note"}


def test_a_tool_call_that_does_not_parse_is_not_shown():
    text = 'Saving it now. <tool_call>{"name": "create_note", "arguments": {"title": </tool_call> Done.'
    calls, shown = extract_text_tool_calls(text, TOOLS)
    assert calls == []
    assert "<tool_call>" not in shown and "arguments" not in shown
    assert shown.startswith("Saving it now.") and shown.endswith("Done.")


def test_an_opener_cut_off_by_the_stream_is_dropped_to_the_end():
    calls, shown = extract_text_tool_calls('Here you go. <tool_call>{"name": "create_no', TOOLS)
    assert calls == [] and shown == "Here you go."


def test_a_call_that_parses_is_still_run_and_prose_is_untouched():
    calls, shown = extract_text_tool_calls('<tool_call>{"name": "create_note", "arguments": {"title": "A"}}</tool_call>', TOOLS)
    assert calls == [{"name": "create_note", "arguments": {"title": "A"}}] and shown == ""
    assert drop_tool_call_blocks("No markup here, just {braces}.") == "No markup here, just {braces}."


def test_the_scan_is_linear_on_many_openers():
    text = "<tool_call>" * 20000
    assert drop_tool_call_blocks(text) == ""
