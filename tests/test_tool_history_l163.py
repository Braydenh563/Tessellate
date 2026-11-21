"""O10 (L163, INBOX 1842): the agent's recent tool calls and what came back,
readable from the chat with `/tools`. Recorded at the one door every call
comes through (`tool_run.execute_tool`), refusals and failures included."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tessellate.ai import slash, tool_history, tools

NOW = datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _clean():
    tool_history.clear()
    yield
    tool_history.clear()


def test_a_call_is_kept_with_its_arguments_and_what_came_back():
    tool_history.record("search_notes", {"query": "dentist"}, {"results": [1, 2]}, now=NOW)
    (row,) = tool_history.recent(5)
    assert row["tool"] == "search_notes" and row["ok"] is True
    assert row["arguments"] == 'query="dentist"' and "results" in row["result"]
    assert row["at"] == NOW.isoformat()


def test_an_error_is_kept_as_a_failure_with_its_words():
    tool_history.record("delete_note", {"note_id": 9}, {"error": "delete_note: no such note"}, now=NOW)
    (row,) = tool_history.recent(5)
    assert row["ok"] is False and row["result"] == "delete_note: no such note"


def test_it_keeps_the_newest_fifty_newest_first():
    for n in range(60):
        tool_history.record("t", {"n": n}, {"ok": True}, now=NOW + timedelta(minutes=n))
    rows = tool_history.recent(100)
    assert len(rows) == 50 and rows[0]["arguments"] == "n=59" and rows[-1]["arguments"] == "n=10"


def test_a_long_argument_or_result_is_cut():
    tool_history.record("create_note", {"content": "x" * 500}, {"message": "y" * 500}, now=NOW)
    (row,) = tool_history.recent(1)
    assert len(row["arguments"]) <= 90 and len(row["result"]) <= 160


def test_the_real_door_records_every_call_even_a_refused_one(session):
    tools.execute_tool(session, "no_such_tool", {})
    tools.execute_tool(session, "search_notes", {"query": "anything"})
    kept = {row["tool"]: row for row in tool_history.recent(5)}
    assert kept["no_such_tool"]["ok"] is False and "Unknown tool" in kept["no_such_tool"]["result"]
    assert kept["search_notes"]["ok"] is True


def test_the_slash_command_lists_them_in_the_chat(client):
    assert "no tool calls yet" in _say(client, "/tools").lower()
    tool_history.record("search_notes", {"query": "dentist"}, {"results": []}, now=NOW)
    tool_history.record("delete_note", {"note_id": 9}, {"error": "no such note"}, now=NOW + timedelta(minutes=1))
    said = _say(client, "/tools")
    assert said.index("delete_note") < said.index("search_notes")
    assert "failed: no such note" in said and "!" not in said and chr(0x2014) not in said
    assert "/tools" in slash.COMMANDS["tools"].usage
    assert _say(client, "/tools 1").count("- ") == 1


def _say(client, text: str) -> str:
    import json

    with client.stream("POST", "/chat/stream", json={"question": text, "use_tools": False}) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    return "".join(e.get("delta", "") for e in events if e["type"] == "answer")
