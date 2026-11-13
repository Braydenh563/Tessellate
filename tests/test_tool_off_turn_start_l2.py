"""A request whose tools are switched off is told so before any model call (L-chat-2)."""

from __future__ import annotations

from tessellate.ai.tools import tool_off


def test_every_needed_tool_off_gets_one_plain_sentence(ai_client):
    ai_client.put("/preferences", json={"disabled_tools": ["tag_note", "rename_tag", "delete_tag"]})
    line = tool_off.switched_off_line("tag the knife note with kitchen")
    assert line and line.startswith("The tools this needs are switched off in Settings, Tools")
    assert "tag note" in line and "propose act" not in line and "\u2014" not in line


def test_one_tool_of_a_group_off_still_lets_the_model_try(ai_client):
    ai_client.put("/preferences", json={"disabled_tools": ["delete_tag"]})
    assert tool_off.switched_off_line("tag the knife note with kitchen") is None


def test_nothing_off_or_no_group_asked_for(ai_client):
    assert tool_off.switched_off_line("tag the knife note with kitchen") is None
    ai_client.put("/preferences", json={"disabled_tools": ["tag_note", "rename_tag", "delete_tag"]})
    assert tool_off.switched_off_line("what did I write yesterday") is None


def test_a_tie_needs_every_top_group_off(ai_client):
    """"delete the tag kitchen" scores the tag and the bin groups the same; the bin group is still on."""
    ai_client.put("/preferences", json={"disabled_tools": ["tag_note", "rename_tag", "delete_tag"]})
    assert tool_off.switched_off_line("delete the tag kitchen") is None


def test_the_agent_stream_answers_with_it_and_no_model_call(ai_client, monkeypatch):
    from tessellate.ai import agent

    ai_client.put("/preferences", json={"disabled_tools": ["tag_note", "rename_tag", "delete_tag"]})
    monkeypatch.setattr(agent, "run_agent", lambda *a, **k: (_ for _ in ()).throw(AssertionError("model called")))
    from tessellate.api import chat_agent

    class Req:
        skill = None
        allowed_tools = None
        history = persona_prompt = None
        question = full_question = "tag the knife note with kitchen"

    events = list(chat_agent._agent_events(Req(), {"style": "", "profile": "", "notes": []}, None))
    assert events == [{"type": "answer", "delta": tool_off.switched_off_line(Req.question)}]
