"""The composer controls needle (CHAT_PLAN 1353): it decides a turn is a tool
act, needle only extracts the slots, the composer validates them (dates
through ai/recognise.py) and writes every word of prose, with a fake needle
transport as in test_needle_provider.py."""

from __future__ import annotations

import json
from datetime import datetime

from tessellate.ai import composer_compose as compose
from tessellate.ai import needle_control
from tests.test_needle_provider import fake_engine  # noqa: F401  # the fixture

NOW = datetime(2026, 10, 26, 9, 0)
MOOD = compose.mood_of("remind me", voice="natural", seed="t")


def _tool(name, props, required=()):
    return {"type": "function", "function": {"name": name, "description": name,
                                             "parameters": {"type": "object", "properties": {p: {"type": "string"} for p in props}, "required": list(required)}}}


TOOLS = [_tool("set_reminder", ["text", "when"], ["text"]), _tool("create_note", ["content"], ["content"]), _tool("search_notes", ["query"], ["query"])]
OFFERED = {"set_reminder", "create_note", "search_notes"}


def test_the_composer_decides_which_turns_are_acts():
    assert needle_control.decide("remind me to call mum tomorrow at 9", OFFERED) == "set_reminder"
    assert needle_control.decide("set a reminder for Friday 3pm: dentist", OFFERED) == "set_reminder"
    assert needle_control.decide("make a new note about the harbor launch", OFFERED) == "create_note"
    assert needle_control.decide("what did I write about tides", OFFERED) is None
    assert needle_control.decide("how many notes do I have", OFFERED) is None
    assert needle_control.decide("remind me to call mum", {"search_notes"}) is None


def test_needle_is_shown_only_the_decided_tool(fake_engine):  # noqa: F811
    from tessellate.ai import needle_provider

    provider = needle_provider.NeedleProvider()
    provider._engine()  # noqa: SLF001
    fake_engine[0].answers = [{"function_calls": [{"name": "set_reminder", "arguments": {"text": "call mum", "when": "tomorrow at 9am"}}]}]
    reply = provider.chat_tools("any", [{"role": "user", "content": "remind me to call mum tomorrow at 9am"}], TOOLS)
    _system, shown = fake_engine[0].inits[0]
    assert [t["name"] for t in json.loads(shown)] == ["set_reminder"]
    assert reply["tool_calls"] == [{"name": "set_reminder", "arguments": {"text": "call mum", "when": "tomorrow at 9am"}}]
    assert reply["content"] == ""  # needle wrote nothing and the composer had nothing to ask


def test_slots_needle_left_empty_are_read_from_the_request():
    verdict = needle_control.validate("set_reminder", [{"function": {"name": "set_reminder", "arguments": {}}}], "remind me to call mum tomorrow at 9am", NOW, MOOD)
    assert verdict.call == {"text": "Call mum", "due_at": "2026-10-27T09:00:00"}, verdict
    note = needle_control.validate("create_note", [], "make a new note: buy flour", NOW, MOOD)
    assert note.call == {"content": "buy flour"}


def test_a_date_that_does_not_read_is_asked_about_not_called():
    bad = [{"function": {"name": "set_reminder", "arguments": {"text": "call mum", "when": "whenever the moon is full"}}}]
    verdict = needle_control.validate("set_reminder", bad, "remind me to call mum whenever the moon is full", NOW, MOOD)
    assert verdict.call is None and "whenever the moon is full" in verdict.say and "!" not in verdict.say


def test_a_missing_time_or_subject_is_asked_for():
    no_when = needle_control.validate("set_reminder", [], "remind me to call mum", NOW, MOOD)
    assert no_when.call is None and "when" in no_when.say
    no_what = needle_control.validate("set_reminder", [{"function": {"name": "set_reminder", "arguments": {"when": "tomorrow at 9am"}}}], "remind me tomorrow at 9am", NOW, MOOD)
    assert no_what.call is None and "for" in no_what.say


def test_the_provider_asks_instead_of_calling_with_a_bad_date(fake_engine):  # noqa: F811
    from tessellate.ai import needle_provider

    provider = needle_provider.NeedleProvider()
    provider._engine()  # noqa: SLF001
    fake_engine[0].answers = [{"function_calls": [{"name": "set_reminder", "arguments": {"text": "call mum", "when": "blorp o'clock"}}]}]
    reply = provider.chat_tools("any", [{"role": "user", "content": "remind me to call mum blorp o'clock"}], TOOLS)
    assert reply["tool_calls"] == [] and "blorp o'clock" in reply["content"]


def test_the_confirmation_is_the_composers_prose_in_every_voice():
    result = {"id": 4, "text": "Call mum", "due_at": "2026-10-27T09:00:00"}
    seen = set()
    for voice in ("natural", "plain", "playful", "professional"):
        for n in range(30):
            text = needle_control.confirm("set_reminder", result, {}, compose.mood_of("", voice=voice, seed=str(n)))
            assert "call mum" in text and "27 October at 09:00" in text and "!" not in text and "{" not in text
            seen.add(text)
    assert len(seen) >= 20, len(seen)
    assert needle_control.confirm("search_notes", {}, {}, MOOD) is None


def test_after_the_tool_ran_the_reply_is_composed(fake_engine):  # noqa: F811
    from tessellate.ai import needle_provider

    messages = [
        {"role": "user", "content": "remind me to call mum tomorrow at 9am"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "set_reminder", "arguments": {"text": "call mum", "when": "tomorrow at 9am"}}}]},
        {"role": "tool", "tool_name": "set_reminder", "content": json.dumps({"id": 1, "text": "call mum", "due_at": "2026-10-27T09:00:00"})},
    ]
    reply = needle_provider.NeedleProvider().chat_tools("any", messages, TOOLS)
    assert "call mum" in reply["content"] and "27 October at 09:00" in reply["content"]


def test_a_request_no_tool_fits_gets_the_composers_line(fake_engine):  # noqa: F811
    from tessellate.ai import needle_provider

    reply = needle_provider.NeedleProvider().chat_tools("any", [{"role": "user", "content": "tell me a joke"}], TOOLS)
    assert reply["tool_calls"] == [] and "model" in reply["content"] and "reminders" in reply["content"]
