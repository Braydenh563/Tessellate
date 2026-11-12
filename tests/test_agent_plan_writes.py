"""The plan before the run, Copilot's shape (AGENT_SKILLS_REFORM "Deepened
2026-10-10" row 3): the steps and the writes each will make, listed before
the first runs and approved once; each step's writes with its diff after.

Driven by the fake transport (CLAUDE.md section 4): this proves the events
carry what the panel draws; it says nothing about how a real small model
plans.
"""

from __future__ import annotations

import json

from tessellate.ai import plan_writes


def _events(client, question, **body):
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True, **body}) as r:
        return [json.loads(line) for line in r.iter_lines() if line.strip()]


def _notes(client):
    harbor = client.post("/entries", json={"content": "# Harbor survey\n\nThe harbor wall needs a survey."}).json()["id"]
    budget = client.post("/entries", json={"content": "# Budget review\n\nThe budget is 40 dollars."}).json()["id"]
    return harbor, budget


def _one_write_per_step(fake, calls):
    """Each step: one round that calls the next scripted tool, one of prose."""
    original = fake.chat_tools
    state = {"round": 0}

    def scripted(model, messages, tools, mode=None):
        state["round"] += 1
        if state["round"] % 2 == 1 and calls:
            fake.tool_script = [[calls.pop(0)]]
        return original(model, messages, tools, mode)

    fake.chat_tools = scripted


def test_the_proposal_lists_each_steps_writes(ai_client, fake_ollama, app_state):
    _notes(ai_client)
    steps = ["Tag every note about the harbor survey with harbor", "Pin the budget note", "List my tags"]
    fake_ollama.tool_script = [[{"name": "make_plan", "arguments": {"goal": "Tidy up", "steps": steps}}]]
    proposal = next(e for e in _events(ai_client, "tidy up") if e["type"] == "run_plan")
    assert len(proposal["writes"]) == 3
    assert proposal["writes"][0] and "harbor" in proposal["writes"][0][0].lower()
    assert proposal["writes"][1] and proposal["writes"][1][0].startswith("Add the note")
    assert proposal["writes"][2] == []


def test_a_plan_run_lists_its_writes_before_the_first_step(ai_client, fake_ollama, app_state):
    """The row's measure: the writes are on the plan event, which arrives
    before any step starts."""
    _notes(ai_client)
    steps = ["Pin the budget note", "Edit note one"]
    _one_write_per_step(fake_ollama, [])
    events = _events(ai_client, "Tidy up", plan={"goal": "Tidy up", "steps": steps})
    kinds = [e["type"] for e in events]
    plan = events[kinds.index("plan")]
    assert plan["writes"][0] and plan["writes"][0][0].startswith("Add the note")
    assert kinds.index("plan") < kinds.index("step")


def test_each_step_ticks_with_its_writes_and_an_edit_with_its_diff(ai_client, fake_ollama, app_state):
    harbor, budget = _notes(ai_client)
    _one_write_per_step(fake_ollama, [
        {"name": "pin_note", "arguments": {"note_id": budget, "pinned": True}},
        {"name": "edit_note", "arguments": {"note_id": harbor, "content": "# Harbor survey\n\nThe harbor wall was surveyed."}},
    ])
    events = _events(ai_client, "Tidy up", plan={"goal": "Tidy up", "steps": ["Pin the budget note", "Edit the harbor note"]})
    done = [e for e in events if e["type"] == "step" and e["state"] == "done"]
    assert [len(e["changes"]) for e in done] == [1, 1]
    assert done[0]["changes"][0]["undo"]
    diff = done[1]["changes"][0]["diff"]
    assert diff["removed"] == ["The harbor wall needs a survey."]
    assert diff["added"] == ["The harbor wall was surveyed."]


def test_step_ones_write_can_be_undone_when_the_run_stops_at_step_two(ai_client, fake_ollama, app_state):
    """Stop at step 2 leaves step 1's writes on the undo bar: the page pushes
    each change's `undo` as it arrives, so what step 1 did is undoable from
    its own event whatever happened after it."""
    harbor, _budget = _notes(ai_client)
    before = ai_client.get(f"/entries/{harbor}").json()["content"]
    _one_write_per_step(fake_ollama, [
        {"name": "edit_note", "arguments": {"note_id": harbor, "content": "# Harbor survey\n\nChanged."}},
    ])
    events = _events(ai_client, "Tidy up", plan={"goal": "Tidy up", "steps": ["Edit the harbor note", "Say what you did"]})
    first = next(e for e in events if e["type"] == "step" and e["state"] == "done")
    undo = first["changes"][0]["undo"]
    ai_client.post("/chat/tools/execute", json={"name": undo["tool"], "arguments": undo["arguments"], "sig": undo["sig"]})
    assert ai_client.get(f"/entries/{harbor}").json()["content"] == before


def test_the_diff_is_a_few_lines_of_each():
    diff = plan_writes.edit_diff("a\nb\nc", "a\nB\nc\nd")
    assert diff == {"removed": ["b"], "added": ["B", "d"], "more": 0}
