"""The guards of `agent._dispatch_call` that no test reached.

Characterisation tests written before the function was split into one guard
each (cc-1101). They drive the stage directly with a hand-built plan and state,
so each guard is seen alone: what the model is told (the tool message), what
the person sees (the events) and what the turn remembers (the ledgers).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from tessellate.ai import agent
from tessellate.ai.agent_turn import _TurnState


def _plan(permitted=None, barred=()):
    return SimpleNamespace(permitted=permitted, barred=set(barred), budget=SimpleNamespace(tool_result_chars=100_000))


def _dispatch(session, plan, state, call):
    """The events, the turn-over flag, and the tool message the model was given."""
    events: list[dict] = []
    gen = agent._dispatch_call(session, plan, state, call, None)
    while True:
        try:
            events.append(next(gen))
        except StopIteration as stop:
            over = stop.value
            break
    return events, over


def _told(state):
    return json.loads(state.messages[-1]["content"])


def test_a_barred_tool_is_refused_with_the_reason_and_counted(session):
    state = _TurnState(messages=[], offered=[])
    events, over = _dispatch(session, _plan(barred={"run_skill"}), state, {"name": "run_skill", "arguments": {"name": "x"}})
    assert over is False
    assert events == [
        {
            "type": "tool",
            "label": "ph:warning run skill isn't available here",
            "ok": False,
            "error": "run_skill cannot be used inside a run",
        }
    ]
    assert _told(state)["error"] == "run_skill cannot be used inside a run"
    assert _told(state)["what_to_do"] == agent._RECOVERY_HINTS["already_running"]
    assert state.tool_failures == {"run_skill": 1} and len(state.failed_calls) == 1
    assert state.messages[-1]["tool_name"] == "run_skill"


def test_a_tool_outside_the_skills_allowlist_is_refused_and_a_repeat_is_told_to_stop(session):
    plan = _plan(permitted={"count_notes"})
    state = _TurnState(messages=[], offered=[])
    call = {"name": "tag_note", "arguments": {"id": 1, "tags": ["a"]}}
    events, over = _dispatch(session, plan, state, call)
    assert over is False
    assert events == [
        {"type": "tool", "label": "ph:warning tag_note isn't part of this skill", "ok": False,
         "error": "tag_note is not part of this skill's tools"}
    ]
    first = _told(state)
    assert first["error"] == "tag_note is not part of this skill's tools"
    assert first["what_to_do"] == agent._RECOVERY_HINTS["not_in_skill"]
    assert state.tool_failures == {"tag_note": 1}
    _dispatch(session, plan, state, call)
    assert _told(state)["what_to_do"] == agent.REPEATED_CALL_NOTE
    assert state.tool_failures == {"tag_note": 2}


def test_arguments_that_were_not_json_say_so_with_an_example(session):
    state = _TurnState(messages=[], offered=[])
    call = {"name": "count_notes", "arguments": {}, "invalid_arguments": "{oops"}
    events, over = _dispatch(session, _plan(), state, call)
    assert over is False
    assert events == [
        {
            "type": "tool",
            "tool": "count_notes",
            "label": "ph:warning count notes, arguments unreadable",
            "ok": False,
            "error": "count_notes: the arguments were not valid JSON, so nothing ran",
            "arguments": {"unreadable": "{oops"},
        }
    ]
    assert _told(state)["what_to_do"] == "Call count_notes again with its arguments as one JSON object, for example {}."
    assert state.tool_failures == {"count_notes": 1} and len(state.failed_calls) == 1


def test_a_destructive_tool_already_waiting_at_the_limit_queues_no_more(session):
    limit = agent.MAX_PARKED_CONFIRMS
    state = _TurnState(messages=[], offered=[], parked={"delete_document": limit})
    events, over = _dispatch(session, _plan(), state, {"name": "delete_document", "arguments": {"id": 1}})
    assert over is False
    assert [e["label"] for e in events] == ["ph:prohibit delete document, too many waiting for approval"]
    told = _told(state)
    assert told["error"] == (
        f"delete_document is already waiting for the user's approval {limit} times in this turn. "
        "Nothing more can be queued for them."
    )
    assert told["what_to_do"].startswith("Stop. The user has to approve what is already waiting")
    assert state.parked == {"delete_document": limit} and state.tool_failures == {"delete_document": 1}
    assert state.did_write is False


def test_a_destructive_tool_under_the_limit_is_parked_with_a_card(session):
    state = _TurnState(messages=[], offered=[], parked={"delete_document": 1})
    events, over = _dispatch(session, _plan(), state, {"name": "delete_document", "arguments": {"id": 1}})
    assert over is False and [e["type"] for e in events] == ["confirm"]
    assert state.parked == {"delete_document": 2} and state.did_write and state.ran_writes == {"delete_document"}
    assert _told(state) == agent.AWAITING_CONFIRMATION


def test_a_tool_that_failed_three_times_is_spent_whatever_the_arguments(session):
    state = _TurnState(messages=[], offered=[], tool_failures={"count_notes": 3})
    events, _ = _dispatch(session, _plan(), state, {"name": "count_notes", "arguments": {"tag": "new"}})
    assert [e["label"] for e in events] == ["ph:prohibit count notes, stopped after repeated failures"]
    assert _told(state)["error"] == "count_notes has failed 3 times in this turn and is no longer available for it"
    assert _told(state)["what_to_do"] == agent.TOOL_EXHAUSTED_NOTE


def test_a_call_that_already_failed_is_intercepted_and_counted(session):
    state = _TurnState(messages=[], offered=[])
    sig = ("count_notes", json.dumps({"tag": "new"}, sort_keys=True))
    state.failed_calls.add(sig)
    events, _ = _dispatch(session, _plan(), state, {"name": "count_notes", "arguments": {"tag": "new"}})
    assert events == [
        {"type": "tool", "label": "ph:warning count notes, repeated failure", "ok": False,
         "error": "Repeated failure intercepted"}
    ]
    assert _told(state)["what_to_do"] == agent.REPEATED_CALL_NOTE
    assert state.tool_failures == {"count_notes": 1}


def test_a_read_whose_result_is_already_held_is_answered_with_a_pointer(session):
    state = _TurnState(messages=[], offered=[])
    state.fresh_reads.add(("count_notes", "{}"))
    events, _ = _dispatch(session, _plan(), state, {"name": "count_notes", "arguments": {}})
    assert events == [{"type": "tool", "label": "↩︎ count notes, already read", "ok": True}]
    assert _told(state)["already_done"] is True
    assert state.tool_failures == {}
