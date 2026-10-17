"""Skills as jobs rather than saved sentences (roadmap §21).

Reported: "the way skills are used currently … are closer to just presaved
mini prompts. I keep on trying to get the AI to make me some skills in the
chat but it doesn't recognise that it needs to use tools." A skill was
`{name, prompt}`, so `save_skill` had nowhere to put steps and no way to say
which tools a job needs. These tests pin the new shape, and the two things it
buys: a small model that is *told* which tools to use, and a run that carries
four tool schemas instead of twenty-six (§11a).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tessellate.ai import agent, skill_runner, skills, tools
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]


def _known() -> set[str]:
    return set(tools.TOOLS)


def _stream_events(client, question, **body):
    with client.stream(
        "POST", "/chat/stream", json={"question": question, **body}
    ) as response:
        assert response.status_code == 200
        return [json.loads(line) for line in response.iter_lines() if line]


#: A five-step skill whose steps are **plain strings**, for the tests that are
#: about the runner rather than about a particular built-in.
#:
#: A string step is unchecked, it has no contract (see `skills.STEP_EXPECTS`)
#: and advances on whatever the model says, which is what every skill written
#: by hand in the settings box does. That is exactly the right scaffolding for
#: "does a step get its own turn", "does the manual pause land in the right
#: place", "does step 3 see what step 2 touched": those are properties of the
#: runner, and they should not change the day a shipped skill changes what it
#: expects of its own steps.
#:
#: These tests used to borrow the "Auto-tag my notes" built-in for this, and
#: every one of them broke when that built-in started declaring a contract per
#: step: a coupling worth removing rather than working around, since the fake
#: model narrates and never calls a tool, so a `tool_called` contract can only
#: ever end those runs in `stalled`.
BENCH_SKILL = {
    "name": "Test bench",
    "prompt": "Tag the notes in my notebook that have no tags yet.",
    "steps": [
        "List the tags I already use.",
        "Find my notes with no tags.",
        "Read each of those notes.",
        "Call tag_note on each one with 2-3 tags.",
        "Tell me which notes you tagged.",
    ],
    "tools": ["list_notes", "get_note", "list_tags", "tag_note"],
}


def _bench(client) -> str:
    """Save the bench skill and return its name, for `skill=` on a run."""
    response = client.put("/preferences", json={"skills": [BENCH_SKILL]})
    assert response.status_code < 400
    return BENCH_SKILL["name"]


# --- what a skill is now -----------------------------------------------------


def test_a_prompt_only_skill_still_works():
    """Nothing is lost: the old shape is a one-step skill."""
    skill = skills.normalise({"name": "Weekly", "prompt": "Summarise my week."})
    assert skill["steps"] == [] and skill["tools"] == [] and skill["inputs"] == []
    assert skills.is_action(skill) is False
    assert "Summarise my week." in skills.run_instruction(skill)


def test_a_skill_carries_steps_tools_and_inputs():
    skill = skills.normalise(
        {
            "name": "File my inbox",
            "prompt": "File everything tagged {{tag}}.",
            "steps": ["Find every note tagged {{tag}}", "Give each one a category"],
            "tools": ["search_notes", "edit_note"],
            "inputs": [{"name": "tag", "label": "Which tag?"}],
        },
        _known(),
    )
    assert skill["steps"][0] == "Find every note tagged {{tag}}"
    assert skill["tools"] == ["search_notes", "edit_note"]
    assert skills.is_action(skill) is True

    instruction = skills.run_instruction(skill, {"tag": "inbox"})
    assert "{{tag}}" not in instruction
    assert "Find every note tagged inbox" in instruction
    assert "1." in instruction and "2." in instruction
    # Named in the text as well as narrowed on the wire: a small model that is
    # told "use edit_note" reaches for it, which is the reported failure.
    assert "search_notes, edit_note" in instruction


def test_a_placeholder_with_no_input_behind_it_is_refused():
    """Otherwise the model is handed a literal {{tag}} and invents a value."""
    with pytest.raises(skills.SkillError, match="doesn't declare"):
        skills.normalise({"name": "Broken", "prompt": "File everything in {{tag}}"})


def test_a_tool_that_does_not_exist_is_refused_by_name():
    with pytest.raises(skills.SkillError, match="tag_everything"):
        skills.normalise(
            {"name": "Nope", "prompt": "Do a thing", "tools": ["tag_everything"]},
            _known(),
        )


def test_a_required_input_with_nothing_behind_it_is_reported():
    skill = skills.normalise(
        {
            "name": "Catch up",
            "prompt": "Everything about {{topic}}",
            "inputs": [{"name": "topic", "required": True}],
        }
    )
    assert skills.missing_inputs(skill, {}) == ["topic"]
    assert skills.missing_inputs(skill, {"topic": "sailing"}) == []
    # A default counts as an answer.
    with_default = skills.normalise(
        {
            "name": "Catch up",
            "prompt": "Everything about {{topic}}",
            "inputs": [{"name": "topic", "default": "work"}],
        }
    )
    assert skills.missing_inputs(with_default, {}) == []
    assert "work" in skills.run_instruction(with_default, {})


def test_the_built_in_skills_are_valid_and_name_real_tools():
    """They moved out of app.js, where nothing could check them."""
    for skill in skills.builtins(_known()):
        assert skill["builtin"] is True
        for name in skill["tools"]:
            assert name in tools.TOOLS


def test_every_built_in_is_a_job_rather_than_a_sentence():
    """The point of the rebuild. A built-in with no steps and no tools is a
    saved prompt wearing a skill's clothes."""
    for skill in skills.builtins(_known()):
        assert skill["steps"], f"{skill['name']} has no steps"
        assert skill["tools"], f"{skill['name']} names no tools"
        assert skill["description"], f"{skill['name']} says nothing about itself"


def test_every_built_in_step_declares_what_it_expects():
    """Phase A of the skills reform, as a lint. A shipped step with no contract
    is a step that can be ticked green having done nothing, which is the
    reported failure, and it is not something a behaviour test can catch,
    because the fake model happily narrates any step you give it."""
    for skill in skills.builtins(_known()):
        for spec in skill["step_specs"]:
            assert spec["expects"] in skills.STEP_EXPECTS, (
                f"{skill['name']}: “{spec['text'][:40]}” declares no contract"
            )


def test_no_built_in_step_names_more_than_one_tool():
    """Phase B's measured target: *"no built-in step names more than one tool"*.

    It is the acceptance test for the atomic rewrite, a step that needs two
    tools is two steps, and the "and" in the middle of it was the model's
    licence to do the first half and narrate the second. It is also what makes
    small-model mode meaningful: that mode offers a step only the tools its
    contract names, so a step naming three would offer three."""
    for skill in skills.builtins(_known()):
        for spec in skill["step_specs"]:
            assert len(spec["tools"]) <= 1, (
                f"{skill['name']}: “{spec['text'][:40]}” names {spec['tools']}"
            )
            for name in spec["tools"]:
                # A contract naming a tool the run will not be offered can
                # never be met: the allowlist refuses the call, the step is
                # nudged twice, and every run of it stalls.
                assert name in skill["tools"], f"{skill['name']}: {name} is not in its tools"


def test_a_built_in_that_needs_a_value_asks_for_it_instead_of_guessing():
    """"Ask me who it's to" inside a prompt is a round trip the user pays for
    every run; a declared input is a box before it starts."""
    email = next(
        s for s in skills.builtins(_known()) if "Draft an email" in s["name"]
    )
    assert [item["name"] for item in email["inputs"]] == ["to", "about"]
    assert skills.missing_inputs(email, {}) == ["to", "about"]
    filled = skills.run_instruction(email, {"to": "Sam", "about": "the lease"})
    assert "to Sam about the lease" in filled
    assert "{{" not in filled


def test_a_stored_skill_that_no_longer_validates_is_kept_as_a_prompt(app_state):
    """Losing someone's skill because a field went stale is worse than running
    it with fewer powers than it asked for."""
    app_state.set_preference(
        "skills", [{"name": "Old", "prompt": "Do the thing", "tools": ["gone_tool"]}]
    )
    catalog = skills.catalog(app_state, _known())
    mine = [s for s in catalog if not s["builtin"]]
    assert [s["name"] for s in mine] == ["Old"]
    assert mine[0]["tools"] == []


# --- the model writing one ---------------------------------------------------


def test_the_model_can_save_a_skill_with_steps_and_tools(client, session, app_state):
    """The reported failure, from the other end: there was nowhere to put the
    steps, so "make me a skill that files my inbox" saved another sentence."""
    result = tools.execute_tool(
        session,
        "save_skill",
        {
            "name": "File my inbox",
            "prompt": "File the notes I tagged inbox.",
            "steps": ["Find notes tagged inbox", "Give each one a category"],
            "tools": ["search_notes", "edit_note"],
        },
    )
    assert result["steps"] == 2
    assert result["tools"] == ["search_notes", "edit_note"]

    saved = app_state.get_preference("skills")[0]
    assert saved["steps"] == ["Find notes tagged inbox", "Give each one a category"]
    assert saved["useTools"] is True


def test_the_model_is_told_when_it_names_a_tool_that_is_not_there(session, app_state):
    result = tools.execute_tool(
        session,
        "save_skill",
        {"name": "Nope", "prompt": "Do a thing", "tools": ["make_coffee"]},
    )
    assert "make_coffee" in result["error"]


def test_the_model_cannot_shadow_a_built_in_skill(session, app_state):
    name = skills.BUILTIN_SKILLS[0]["name"]
    result = tools.execute_tool(
        session, "save_skill", {"name": name, "prompt": "Something else"}
    )
    assert "built-in" in result["error"]


# --- the settings path uses the same rules -----------------------------------


def test_the_skills_endpoint_serves_built_ins_and_your_own(client, app_state):
    client.put(
        "/preferences",
        json={"skills": [{"name": "Mine", "prompt": "Do my thing"}]},
    )
    body = client.get("/skills").json()
    names = [skill["name"] for skill in body["skills"]]
    assert "Mine" in names
    assert len(names) == len(skills.BUILTIN_SKILLS) + 1
    assert body["limits"]["steps"] == skills.MAX_STEPS


def test_only_the_skills_that_write_are_marked_as_changing_your_notes(client, app_state):
    """A marker on all ten says nothing. Nearly every skill uses tools; the
    question the user is asking is which ones act."""
    listed = {skill["name"]: skill for skill in client.get("/skills").json()["skills"]}
    assert listed["Auto-tag my notes"]["changes"] is True  # tag_note
    assert listed["Find loose ends"]["changes"] is False  # reads only
    assert listed["Tidy suggestions"]["changes"] is False  # proposes, never applies


def test_saving_a_skill_naming_an_unknown_tool_is_refused(client, app_state):
    response = client.put(
        "/preferences",
        json={"skills": [{"name": "Bad", "prompt": "x", "tools": ["nope_tool"]}]},
    )
    assert response.status_code == 422
    assert "nope_tool" in response.json()["detail"]


def test_steps_and_inputs_round_trip_through_preferences(client, app_state):
    body = {
        "skills": [
            {
                "name": "Catch up",
                "prompt": "Everything about {{topic}}",
                "steps": ["Search for {{topic}}", "Summarise what you find"],
                "tools": ["search_notes"],
                "inputs": [{"name": "topic", "label": "Which topic?"}],
            }
        ]
    }
    saved = client.put("/preferences", json=body).json()["skills"][0]
    assert saved["steps"] == body["skills"][0]["steps"]
    assert saved["inputs"][0]["label"] == "Which topic?"
    assert saved["useTools"] is True


# --- running one -------------------------------------------------------------


def test_a_skill_run_offers_only_the_tools_it_declared(app_state):
    """Roadmap §11a, measured: 28 schemas go up on every round of every turn
    whether the question needs them or not."""
    everything = tools.ollama_tools()
    narrowed = tools.ollama_tools(["search_notes", "tag_note"])
    assert {t["function"]["name"] for t in narrowed} == {"search_notes", "tag_note"}
    assert len(json.dumps(narrowed)) < len(json.dumps(everything)) / 3


def test_a_disabled_tool_stays_disabled_inside_a_skill(app_state):
    """A skill declaring a tool must not re-enable one the user turned off."""
    app_state.set_preference("disabled_tools", ["tag_note"])
    offered = tools.ollama_tools(["search_notes", "tag_note"])
    assert {t["function"]["name"] for t in offered} == {"search_notes"}


def test_the_agent_refuses_a_tool_the_skill_did_not_declare(
    ai_client, session, fake_ollama, app_state
):
    """The allowlist is a safety property, not only a prompt, a model that
    calls something it was never offered doesn't get to run it."""
    from tessellate.core import deps

    fake_ollama.tool_script = [
        [{"name": "create_note", "arguments": {"content": "sneaky"}}]
    ]
    events = list(
        agent.run_agent(
            session,
            "run the skill",
            [],
            deps.get_model_manager(),
            fake_ollama,
            allowed_tools=["search_notes"],
        )
    )
    refused = [e for e in events if e["type"] == "tool"]
    assert refused and refused[0]["ok"] is False
    assert "isn't part of this skill" in refused[0]["label"]
    assert ai_client.get("/entries").json() == []


def test_running_a_skill_sends_its_instruction_not_its_name(ai_client, fake_ollama):
    name = _bench(ai_client)
    events = _stream_events(ai_client, name, skill=name)
    plan = [e for e in events if e["type"] == "plan"][0]
    assert plan["steps"]

    sent = fake_ollama.tool_rounds[-1][-1]["content"]
    assert f"step {len(plan['steps'])} of {len(plan['steps'])}" in sent
    assert "tag_note" in sent


def test_a_skill_with_no_steps_is_still_one_instruction(ai_client, fake_ollama):
    """Nothing was taken away: a skill saved before the rebuild, a name and a
    prompt: still runs, as a single turn."""
    ai_client.put(
        "/preferences",
        json={"skills": [{"name": "Old style", "prompt": "Summarise my week."}]},
    )
    _stream_events(ai_client, "Old style", skill="Old style")
    sent = fake_ollama.tool_rounds[-1][-1]["content"]
    assert "Run my saved skill" in sent
    assert "step 1 of" not in sent


def test_running_a_skill_narrows_the_tools_on_the_wire(ai_client, fake_ollama, session):
    """The point of the allowlist, end to end.

    `count_notes` is in this set because the skill verifies with it (a skill
    may only verify with a tool it declares, the same rule its steps' own
    contracts follow), and it is a read-only count. That is the whole of the
    widening, and it is written here rather than left to be rediscovered: the
    wire grew by one tool so that "no note is left untagged" became a claim
    the app reads back out of the notebook.
    """
    captured = {}
    original = fake_ollama.chat_tools

    def spy(model, messages, offered):
        captured["names"] = {t["function"]["name"] for t in offered}
        return original(model, messages, offered)

    fake_ollama.chat_tools = spy
    _stream_events(ai_client, "Auto-tag my notes", skill="Auto-tag my notes")
    assert captured["names"] == {
        "list_notes",
        "get_note",
        "list_tags",
        "tag_note",
        "count_notes",
    }


def test_a_skill_with_a_missing_input_is_refused_rather_than_run_blank(ai_client):
    response = ai_client.post(
        "/chat/stream", json={"question": "x", "skill": "Catch up on a topic"}
    )
    assert response.status_code == 422
    assert "topic" in response.json()["detail"]


def test_a_skill_input_reaches_the_model(ai_client, fake_ollama):
    _stream_events(
        ai_client,
        "Catch up on a topic",
        skill="Catch up on a topic",
        skill_inputs={"topic": "sailing"},
    )
    sent = fake_ollama.tool_rounds[-1][-1]["content"]
    assert "sailing" in sent


def test_running_a_skill_that_does_not_exist_says_so(ai_client):
    response = ai_client.post(
        "/chat/stream", json={"question": "x", "skill": "Not a skill"}
    )
    assert response.status_code == 404


# --- running one step at a time ----------------------------------------------


def _saved(client, content, **extra):
    response = client.post("/entries", json={"content": content, **extra})
    assert response.status_code == 201
    return response.json()


def test_a_network_failure_mid_step_stops_the_run_instead_of_repeating(
    ai_client, fake_ollama, monkeypatch
):
    """Tier 1 §3: Ollama going offline mid-round used to look, to
    skill_runner, exactly like the model answering with a sentence of prose
    (agent.run_agent's own OllamaError handling is a real "answer" event): 
    so the step was ticked done and the run moved on to repeat the identical
    failure on every later step. It must stop and name the real reason
    instead, the same way running out of rounds already does."""
    from tessellate.ai import agent

    def offline(session, question, notes, *args, **kwargs):
        yield {"type": "answer", "delta": "Ollama doesn't seem to be running.", "offline": True}

    monkeypatch.setattr(agent, "run_agent", offline)
    events = _stream_events(ai_client, "run", skill="Auto-tag my notes")
    steps = [e for e in events if e["type"] == "step"]
    result = [e for e in events if e["type"] == "result"][0]

    failed = [e for e in steps if e["state"] == "failed"]
    assert failed and failed[0]["index"] == 0
    assert "ollama" in failed[0]["reason"].lower()
    assert not any(s["state"] == "done" for s in steps)
    # It stops rather than ploughing on through the remaining steps, hitting
    # the same offline error on each one.
    assert not [e for e in steps if e["index"] == 1]
    assert result["stopped_at"] == 0


def test_each_step_is_its_own_turn_and_is_ticked_off(ai_client, fake_ollama):
    """Handing a 3B model four instructions at once gets the first one done
    and the rest narrated. One step per turn is what makes "step 2 happened"
    something the app knows rather than hopes."""
    events = _stream_events(ai_client, "run", skill=_bench(ai_client))
    plan = [e for e in events if e["type"] == "plan"][0]
    steps = [e for e in events if e["type"] == "step"]

    assert [s["state"] for s in steps if s["state"] == "running"] == ["running"] * len(
        plan["steps"]
    )
    assert [s["index"] for s in steps if s["state"] == "done"] == list(
        range(len(plan["steps"]))
    )
    # One model turn per step, not one turn carrying a numbered list.
    assert len(fake_ollama.tool_rounds) >= len(plan["steps"])


def test_a_step_that_produces_nothing_is_not_ticked_done(ai_client, fake_ollama):
    """Reported as "the AI fails to respond while still saying it is writing
    - and the skill step counted as done": a turn that ends with no answer
    text and no tool call (an empty reply, no `tool_script` queued) used to
    fall through to the generic "done" branch, so the run's own progress
    list claimed success for a step that never actually did anything. It
    must stop and report the step as failed instead, so Resume, not the
    next step: picks it back up."""
    fake_ollama.librarian_reply = ""  # the model says and does nothing
    events = _stream_events(ai_client, "run", skill="Auto-tag my notes")
    steps = [e for e in events if e["type"] == "step"]
    result = [e for e in events if e["type"] == "result"][0]

    assert steps[-1]["state"] == "failed"
    assert "state" not in steps[-1] or steps[-1]["state"] != "done"
    assert not any(s["state"] == "done" for s in steps)
    assert result["stopped_at"] == 0


def test_a_step_only_sees_what_the_earlier_steps_said(ai_client, fake_ollama):
    _stream_events(ai_client, "run", skill=_bench(ai_client))
    last_turn = fake_ollama.tool_rounds[-1]
    # The history the last step was given carries the earlier steps as turns.
    earlier = [m for m in last_turn if m.get("role") == "user"]
    assert len(earlier) > 1, "the last step was given no earlier context"


def test_a_later_step_sees_which_notes_an_earlier_step_actually_touched(
    ai_client, fake_ollama
):
    """Robustness pass, reported as the run "losing the plot" partway
    through: a step's own narration ("tagged the relevant notes") is a
    summary the model wrote about itself, not a record of what happened, and
    it used to be *all* the next step saw. A later step that needed "those
    notes" had only that sentence to work from, too vague to act on. The
    actual note id (from the same `change` event that already backs the
    chat UI's View/Undo buttons) now travels with it."""
    name = _bench(ai_client)
    note = _saved(ai_client, "a note that wants tagging")
    fake_ollama.tool_script = [
        [{"name": "tag_note", "arguments": {"note_id": note["id"], "add": ["filed"]}}]
    ]
    _stream_events(ai_client, "run", skill=name)
    last_turn = fake_ollama.tool_rounds[-1]
    history_text = " ".join(
        str(m.get("content", "")) for m in last_turn if m.get("role") == "assistant"
    )
    assert f"#{note['id']}" in history_text


def test_step_answer_with_nothing_touched_is_just_the_prose():
    assert skill_runner._step_answer("Looked, found nothing.", []) == "Looked, found nothing."


def test_step_answer_with_no_prose_says_so():
    assert skill_runner._step_answer("", []) == "(nothing said)"


def test_step_answer_names_the_notes_touched():
    changes = [{"note_id": 12}, {"note_id": 5}]
    result = skill_runner._step_answer("Tagged them.", changes)
    assert result == "Tagged them. [Notes touched this step: #5, #12]"


def test_step_answer_ignores_changes_with_no_id_of_either_kind():
    changes = [{"note_id": None}, {}]
    assert skill_runner._step_answer("Nothing to show.", changes) == "Nothing to show."


def test_step_answer_names_documents_too():
    """The same "loses the plot" fix as notes, for a step that wrote a
    document: a later step told to "attach that document" needs its id,
    not a re-told sentence about writing it."""
    changes = [{"document_id": 41}]
    result = skill_runner._step_answer("Wrote it up.", changes)
    assert result == "Wrote it up. [Documents touched this step: #41]"


def test_step_answer_names_both_kinds_together():
    changes = [{"note_id": 5}, {"document_id": 41}]
    result = skill_runner._step_answer("Done.", changes)
    assert result == (
        "Done. [Notes touched this step: #5] [Documents touched this step: #41]"
    )


def test_step_answer_deduplicates_and_sorts_ids():
    changes = [{"note_id": 9}, {"note_id": 3}, {"note_id": 9}]
    result = skill_runner._step_answer("Done.", changes)
    assert result == "Done. [Notes touched this step: #3, #9]"


def test_step_answer_caps_how_many_ids_it_names():
    changes = [{"note_id": n} for n in range(20)]
    result = skill_runner._step_answer("Tagged a lot.", changes)
    assert result.endswith(", and 5 more]")
    assert result.count("#") == skill_runner.MAX_TOUCHED_IDS_NAMED


def test_step_answer_truncates_prose_before_dropping_ids():
    """The ids are the fact the next step needs; the model's own words are
    what it can afford to lose if the two don't both fit."""
    long_answer = "x" * 1000
    result = skill_runner._step_answer(long_answer, [{"note_id": 1}])
    assert len(result) <= skill_runner.STEP_ANSWER_CHARS
    assert "[Notes touched this step: #1]" in result


def test_what_changed_comes_back_as_a_list_with_a_way_to_undo_it(
    ai_client, session, fake_ollama
):
    """§21: "a result: what changed, as a list the user can undo, rather than
    prose claiming something happened"."""
    note = _saved(ai_client, "a note that wants tagging")
    fake_ollama.tool_script = [
        [{"name": "tag_note", "arguments": {"note_id": note["id"], "add": ["filed"]}}]
    ]
    events = _stream_events(ai_client, "run", skill="Auto-tag my notes")

    result = [e for e in events if e["type"] == "result"][-1]
    assert len(result["changes"]) == 1
    change = result["changes"][0]
    assert change["note_id"] == note["id"]
    assert change["undo"]["tool"] == "edit_note"
    # And the undo actually undoes it, through the endpoint the UI uses.
    ai_client.post(
        "/chat/tools/execute",
        json={"name": change["undo"]["tool"], "arguments": change["undo"]["arguments"]},
    )
    assert ai_client.get(f"/entries/{note['id']}").json()["tags"] == []


# --- manual (step-through) mode ----------------------------------------------
#
# "a manual mode", asked for directly, and named in ROADMAP.md as "the
# single most-requested unbuilt thing on the list": a pause after every
# completed step with a Continue button, so a person can add what the agent
# missed or answer a question it raised before the next step starts, rather
# than the run barrelling straight through five steps unattended.


def test_manual_mode_pauses_after_the_first_step_instead_of_continuing(
    ai_client, fake_ollama
):
    events = _stream_events(
        ai_client, "run", skill=_bench(ai_client), skill_manual=True
    )
    steps = [e for e in events if e["type"] == "step"]
    result = [e for e in events if e["type"] == "result"][0]

    assert [s["state"] for s in steps] == ["running", "done"]
    assert result["stopped_at"] == 1
    assert result["paused"] is True


def test_manual_mode_off_runs_straight_through_as_before(ai_client, fake_ollama):
    events = _stream_events(ai_client, "run", skill=_bench(ai_client))
    result = [e for e in events if e["type"] == "result"][0]
    assert result["stopped_at"] is None
    assert result["paused"] is False


def test_manual_mode_does_not_pause_after_the_last_step(ai_client, fake_ollama):
    """Nothing to pause for once the run is actually finished."""
    events = _stream_events(
        ai_client,
        "run",
        skill=_bench(ai_client),
        skill_manual=True,
        skill_from_step=4,  # the last of the five steps
    )
    result = [e for e in events if e["type"] == "result"][0]
    assert result["stopped_at"] is None
    assert result["paused"] is False


def test_a_paused_run_is_never_reported_as_failed_or_stalled(ai_client, fake_ollama):
    events = _stream_events(
        ai_client, "run", skill=_bench(ai_client), skill_manual=True
    )
    steps = [e for e in events if e["type"] == "step"]
    assert not any(s["state"] in ("failed", "stalled") for s in steps)


def test_manual_note_is_folded_into_the_next_steps_own_instruction(
    ai_client, fake_ollama
):
    """What the user typed at the pause is read as part of what the next
    step is being asked to do, not buried in history the model may or may
    not weigh against everything else in the window."""
    _stream_events(
        ai_client,
        "run",
        skill=_bench(ai_client),
        skill_manual=True,
        skill_from_step=1,
        skill_manual_note="focus on the work notes only",
    )
    sent = fake_ollama.tool_rounds[-1][-1]["content"]
    assert "focus on the work notes only" in sent


def test_manual_note_only_reaches_the_step_it_was_added_before(ai_client, fake_ollama):
    """Not repeated into every later step's instruction: it was about *this*
    step, and a note that keeps reappearing three steps later would read as
    a standing instruction nobody actually gave."""
    name = _bench(ai_client)
    events = _stream_events(
        ai_client,
        "run",
        skill=name,
        skill_manual=True,
        skill_from_step=1,
        skill_manual_note="focus on the work notes only",
    )
    # Paused again after step 1 (index 1), one turn only having seen the note.
    result = [e for e in events if e["type"] == "result"][0]
    assert result["stopped_at"] == 2
    later = _stream_events(
        ai_client,
        "run",
        skill=name,
        skill_manual=True,
        skill_from_step=2,
    )
    sent = fake_ollama.tool_rounds[-1][-1]["content"]
    assert "focus on the work notes only" not in sent
    assert later  # the resumed run itself produced events


def test_the_undo_never_reaches_the_model(ai_client, session, fake_ollama):
    """Every field left in a tool result is resent on every later round."""
    note = _saved(ai_client, "a note")
    fake_ollama.tool_script = [
        [{"name": "pin_note", "arguments": {"note_id": note["id"]}}]
    ]
    _stream_events(ai_client, "run", skill="Auto-tag my notes")
    tool_messages = [
        m
        for turn in fake_ollama.tool_rounds
        for m in turn
        if m.get("role") == "tool"
    ]
    assert tool_messages
    assert not any("undo" in m["content"] for m in tool_messages)


def test_a_step_that_produces_nothing_is_reported_as_the_failure(
    ai_client, fake_ollama, monkeypatch
):
    """"A skill that fails halfway should say which step it stopped at."""
    from tessellate.ai import agent

    def only_failures(session, question, notes, *args, **kwargs):
        yield {"type": "tool", "label": "nope", "ok": False, "error": "it broke"}

    monkeypatch.setattr(agent, "run_agent", only_failures)
    events = _stream_events(ai_client, "run", skill="Auto-tag my notes")

    failed = [e for e in events if e["type"] == "step" and e["state"] == "failed"]
    assert failed and failed[0]["index"] == 0
    assert "it broke" in failed[0]["reason"]
    # It stops rather than ploughing on through the remaining steps.
    assert not [e for e in events if e["type"] == "step" and e["index"] == 1]


def test_a_model_that_cannot_use_tools_still_falls_back_to_a_plain_answer(
    ai_client, fake_ollama
):
    """The runner's first event has to mean what the agent's did, or the
    fallback that keeps this app usable without tool support breaks."""
    fake_ollama.supports_tools = False
    events = _stream_events(ai_client, "run", skill="Auto-tag my notes")

    assert not [e for e in events if e["type"] == "plan"]
    assert any(e["type"] == "answer" for e in events)


def test_an_action_skill_acts_even_with_agent_mode_off(ai_client, fake_ollama):
    """The frontend used to tick the agent-mode box on the user's behalf and
    leave it ticked. A skill that acts brings its own permission."""
    events = _stream_events(
        ai_client,
        "Auto-tag my notes",
        skill="Auto-tag my notes",
        use_tools=False,
    )
    assert any(e["type"] == "plan" for e in events)
    assert fake_ollama.tool_rounds, "the agent never ran"


# --- findable by the model, not only by the person who wrote it (§33) --------


def test_a_skill_can_say_when_it_applies():
    """The description says what a skill *is*; this says when to reach for it.
    Without it a model reading the skill list can see that a skill exists and
    has no basis at all for choosing it."""
    from tessellate.ai import skills, tools

    skill = skills.normalise(
        {
            "name": "Inbox tidy",
            "prompt": "file the loose notes",
            "when_to_use": "when Uncategorised is getting full",
        },
        set(tools.TOOLS),
    )
    assert skill["when_to_use"] == "when Uncategorised is getting full"


def test_when_to_use_is_optional_so_old_skills_still_load():
    from tessellate.ai import skills, tools

    assert skills.normalise({"name": "n", "prompt": "p"}, set(tools.TOOLS))["when_to_use"] == ""


def test_the_skill_list_tells_the_model_what_running_one_commits_to(app_state, session):
    """A skill that changes notes is a different proposition from one that only
    reads them, and the name alone does not say which."""
    from tessellate.ai import tools

    app_state.set_preference(
        "skills",
        [
            {
                "name": "Retagger",
                "prompt": "retag things",
                "when_to_use": "when tags have drifted",
                "steps": ["find untagged notes", "tag them"],
                "tools": ["search_notes", "tag_note"],
            }
        ],
    )
    listed = tools.TOOLS["list_skills"].handler(session, {})
    mine = next(s for s in listed["skills"] if s["name"] == "Retagger")
    assert mine["when_to_use"] == "when tags have drifted"
    assert mine["step_count"] == 2
    assert mine["changes_notes"] is True


def test_a_read_only_skill_says_it_changes_nothing(app_state, session):
    from tessellate.ai import tools

    app_state.set_preference(
        "skills",
        [{"name": "Recap", "prompt": "summarise", "tools": ["search_notes", "get_note"]}],
    )
    listed = tools.TOOLS["list_skills"].handler(session, {})
    assert next(s for s in listed["skills"] if s["name"] == "Recap")["changes_notes"] is False


def test_the_model_is_told_how_to_start_a_skill(app_state, session):
    """This used to assert the note said the model *cannot* start a skill,
    which was true and worth saying then, a model that believes it can run
    one will narrate having done so. §33's plan is built now, so the note has
    to say the opposite: leaving the old sentence in beside a working
    `run_skill` would be worse than either state on its own."""
    from tessellate.ai import tools

    note = tools.TOOLS["list_skills"].handler(session, {})["note_to_model"]
    assert "cannot start" not in note.lower()
    assert "run_skill" in note


def test_the_agent_can_save_a_when_to_use(app_state, session):
    from tessellate.ai import tools

    tools.TOOLS["save_skill"].handler(
        session,
        {
            "name": "Weekly recap",
            "prompt": "summarise the week",
            "when_to_use": "on a Sunday evening",
        },
    )
    saved = app_state.get_preference("skills")
    assert saved[0]["when_to_use"] == "on a Sunday evening"


# --- the notebook audit set --------------------------------------------------
#
# Asked for directly: a skill that audits and cleans up the whole notebook, 
# links, tags, categories, moving notes, combining duplicates. Built as five
# skills rather than one, and these tests are mostly about *why*.


AUDIT_SKILLS = [
    "Notebook health check",
    "Clean up my tags",
    "Reorganise my categories",
    "Fix my links",
    "Find notes worth combining",
]


def _builtin(name):
    from tessellate.ai import skills, tools

    return next(s for s in skills.builtins(set(tools.TOOLS)) if s["name"] == name)


@pytest.mark.parametrize("name", AUDIT_SKILLS)
def test_each_audit_skill_is_valid_and_says_when_to_use_it(name):
    skill = _builtin(name)
    assert skill["steps"] and skill["tools"]
    assert skill["when_to_use"], "an audit skill nobody can find is not much use"


@pytest.mark.parametrize("name", AUDIT_SKILLS)
def test_every_tool_an_audit_skill_names_actually_exists(name):
    """A skill naming a tool that isn't in the registry loses it silently at
    run time: the run then fails on the step that needed it."""
    from tessellate.ai import tools

    assert set(_builtin(name)["tools"]) <= set(tools.TOOLS)


@pytest.mark.parametrize("name", AUDIT_SKILLS)
def test_no_audit_skill_exceeds_the_limits(name):
    """One step per turn, so a skill longer than the cap cannot finish."""
    from tessellate.ai import skills

    skill = _builtin(name)
    assert len(skill["steps"]) <= skills.MAX_STEPS
    assert len(skill["tools"]) <= skills.MAX_TOOLS


def test_the_health_check_cannot_change_anything():
    """"Audit" and "clean up" are two requests. The audit is safe by
    construction rather than by instruction: it is offered no tool that could
    write, so a model that ignores "do not change anything" still can't."""
    from tessellate.ai import tools

    skill = _builtin("Notebook health check")
    assert not (set(skill["tools"]) & tools.WRITE_TOOLS)


def test_the_health_check_points_at_the_skills_that_do_the_work():
    """A report that names problems and not their fix leaves the person to
    guess which skill to reach for."""
    steps = " ".join(_builtin("Notebook health check")["steps"]).lower()
    assert "skill" in steps


def test_no_audit_skill_can_delete_a_note():
    """Combining and reorganising both involve deciding what to lose, and that
    is not a judgement to hand a model across a whole notebook."""
    for name in AUDIT_SKILLS:
        assert "delete_note" not in _builtin(name)["tools"], name


def test_combining_notes_proposes_rather_than_merges():
    """It reports the combined note it would write and links the group, so the
    person accepts the merge. Nothing is destroyed on its say-so."""
    skill = _builtin("Find notes worth combining")
    assert "delete_note" not in skill["tools"]
    assert "link_notes" in skill["tools"]


def test_reorganising_categories_merges_rather_than_deletes():
    """`delete_category` is destructive, so it would stop a bulk run for a
    confirm card: and merging is what was wanted anyway, since it keeps the
    notes together instead of scattering them into Uncategorised."""
    skill = _builtin("Reorganise my categories")
    assert "merge_categories" in skill["tools"]
    assert "delete_category" not in skill["tools"]


def test_fixing_links_can_both_add_and_remove():
    """The whole point: before `unlink_notes` existed, an audit could add a
    connection and never correct one."""
    tools_used = _builtin("Fix my links")["tools"]
    assert {"link_notes", "unlink_notes", "related_notes"} <= set(tools_used)


def test_the_audit_skills_are_offered_alongside_the_others(app_state, session):
    from tessellate.ai import tools

    listed = tools.TOOLS["list_skills"].handler(session, {})
    names = {s["name"] for s in listed["skills"]}
    assert set(AUDIT_SKILLS) <= names


def test_a_skill_description_is_not_clipped_to_one_line():
    """Reported twice. The row reused `.persona-preview`, which is nowrap with
    an ellipsis: so the only field saying what a skill *does* got whatever
    width was left after five chips."""

    from tests._css_paths import css_text

    app_js = app_js_text()
    css = css_text()
    assert 'note.className = "muted skill-blurb"' in app_js
    blurb = css[css.index(".skill-blurb {") :][: css[css.index(".skill-blurb {") :].index("}")]
    assert "white-space: normal" in blurb


# --- recovery: re-running one step, reworded (AGENT_SKILLS_REFORM.md Phase D) --
#
# The other two thirds of Phase D were already built and are checked elsewhere:
# `skill_from_step` resumes a stalled run (above, and `test_long_runs.py`), and
# `_unmet_reason` puts the contract that was not met on the stalled step event
# in one sentence (`test_contracts.py`, and the plan card renders it). This is
# the third: a run that stalled on step 4 because the step was written for a
# bigger model is fixed by rewriting step 4, and without this the only way to
# find out whether the rewrite works is to run the whole skill again, every
# earlier step of which writes to the notebook.


def test_only_step_runs_that_step_and_nothing_after_it(ai_client, fake_ollama):
    events = _stream_events(ai_client, "run", skill=_bench(ai_client), skill_only_step=2)
    steps = [e for e in events if e["type"] == "step"]
    earlier = [s["index"] for s in steps if s["state"] == "earlier"]
    ran = [s["index"] for s in steps if s["state"] in ("running", "done")]

    #: Steps before it are marked as done in an earlier run rather than re-run,
    #: which is what `start_at` already does; the difference is that the run
    #: stops after the one step instead of carrying on to the end.
    assert earlier == [0, 1]
    assert set(ran) == {2}


def test_a_single_step_run_reads_as_waiting_rather_than_broken(ai_client, fake_ollama):
    """It is a pause, not a failure: the person asked for this step and got it,
    and the rest of the skill is still there to carry on with."""
    events = _stream_events(ai_client, "run", skill=_bench(ai_client), skill_only_step=1)
    result = [e for e in events if e["type"] == "result"][0]
    assert result["paused"] is True
    assert result["stopped_at"] == 2
    assert not any(
        e["state"] in ("failed", "stalled") for e in events if e["type"] == "step"
    )


def test_re_running_the_last_step_ends_the_run(ai_client, fake_ollama):
    events = _stream_events(ai_client, "run", skill=_bench(ai_client), skill_only_step=4)
    result = [e for e in events if e["type"] == "result"][0]
    assert result["stopped_at"] is None and result["paused"] is False


def test_a_reworded_step_is_what_actually_runs(ai_client, fake_ollama):
    events = _stream_events(
        ai_client,
        "run",
        skill=_bench(ai_client),
        skill_only_step=1,
        skill_step_text="Tag the note about beans with `garden`",
    )
    sent = fake_ollama.tool_rounds[-1][-1]["content"]
    assert "Tag the note about beans with `garden`" in sent

    #: And the plan card carries the step that is about to run, not the one
    #: that failed: a card showing the old wording beside a step running the
    #: new one is exactly the drift this reform exists to stop.
    plan = [e for e in events if e["type"] == "plan"][0]
    assert plan["steps"][1] == "Tag the note about beans with `garden`"
    assert plan["start_at"] == 1


def test_rewording_a_step_does_not_drop_its_contract(ai_client, fake_ollama):
    """The one thing a step edit must not be able to do. An instruction is
    words; a contract is what has to be true when the step is finished, and a
    reworded step that quietly stopped being checked would put the reform's
    whole mechanism one text box away from being switched off."""
    events = _stream_events(
        ai_client,
        "run",
        skill=_bench(ai_client),
        skill_only_step=1,
        skill_step_text="Do the tagging",
    )
    plan = [e for e in events if e["type"] == "plan"][0]
    before = skills.normalise(BENCH_SKILL)["step_specs"][1]
    after = plan["step_specs"][1]
    assert after["expects"] == before["expects"]
    assert after["tools"] == before["tools"]
    assert after["text"] == "Do the tagging"


def test_a_step_index_past_the_end_runs_the_last_step_rather_than_nothing(
    ai_client, fake_ollama
):
    """A stale card in an open tab naming step 9 of a skill that now has five
    is not a reason to run nothing and say nothing."""
    events = _stream_events(ai_client, "run", skill=_bench(ai_client), skill_only_step=9)
    ran = [e["index"] for e in events if e["type"] == "step" and e["state"] == "running"]
    assert ran == [4]


def test_the_chat_offers_to_edit_the_step_a_run_stopped_on():
    """The DOM-blind half: the runner's `only_step` is reachable from the place
    a stopped run is actually looked at, beside the Resume it belongs with."""
    app = app_js_text()
    start = app.index("const editStepAction = (index) => ({")
    body = app[start : app.index("\n  };\n", start)]
    assert "skillOnlyStep: index" in body
    assert "skillStepText: text.trim()" in body
    #: The box opens on the instruction that actually ran, which for a
    #: re-planned step is not the one in the catalogue.
    #: `spec.timeline`, since the controls moved into `appendRunResumeControls`
    #: so a reopened conversation can draw them too: the timeline is passed in
    #: rather than closed over.
    assert "spec.timeline?.stepText?.(index)" in body

    #: On both of the stopped-run controls, not only one: a run you stopped and
    #: a run that stalled are the same question ("now what") with the same two
    #: answers.
    assert app.count("also: editStepAction(stoppedAtStep)") == 2
    #: And it reaches the wire. `!= null` rather than truthiness, or step 0
    #: would be dropped as falsy.
    assert "if (skillOnlyStep != null) body.skill_only_step = skillOnlyStep;" in app


def test_no_shipped_step_names_a_tool_it_does_not_check_for():
    """The owner, reading a run's own reasoning: "check that the other skills
    arent poorly worded or designed, and make sure the system still catches
    them not being carried out".

    Nine shipped steps named a tool and declared `answer_only`, so a model
    that wrote "I used unlink_notes to remove the link between #12 and #45"
    without calling anything ticked the step green over an untouched notebook.
    They are `tool_optional` now: words still satisfy them, because "they all
    hold up" is a real answer, but a step that changed nothing says so.

    The one exception is the step that *forbids* the call, where requiring it
    would be the opposite of what the step is for.
    """
    from tessellate.ai import skills as skills_mod

    tools = {t for sk in skills_mod.BUILTIN_SKILLS for t in (sk.get("tools") or [])}
    offenders = []
    for skill in skills_mod.BUILTIN_SKILLS:
        for index, spec in enumerate(
            skills_mod._step_specs(skill, None, skill.get("tools", [])), 1
        ):
            named = {t for t in tools if re.search(rf"\b{re.escape(t)}\b", spec["text"])}
            if named and spec["expects"] == "answer_only":
                offenders.append(f"{skill['name']} step {index}: {sorted(named)}")
    assert offenders == ["Find where I disagreed with myself step 3: ['link_notes']"], offenders


def test_a_step_may_not_ask_for_a_note_before_anything_has_listed_one():
    """The owner: "How can related notes be called if the model doesnt even
    know what notes there are to pick from". The first step of a skill whose
    first tool takes a note id has to be the listing, not the id."""
    from tessellate.ai import skills as skills_mod

    needs_an_id = {"get_note", "related_notes", "link_notes", "unlink_notes", "tag_note"}
    for skill in skills_mod.BUILTIN_SKILLS:
        specs = skills_mod._step_specs(skill, None, skill.get("tools", []))
        if not specs:
            continue
        first = specs[0]
        assert not (set(first["tools"]) & needs_an_id), (
            f"{skill['name']} opens by asking for a note it has not seen: {first['text']}"
        )


def test_a_skill_saved_from_settings_keeps_its_check(client, app_state):
    """Measured in the browser while the editor's own control was built: the
    block was sent, the save reported success, and the stored skill had no
    check at all, because `SkillItem` did not declare the field and pydantic
    drops what a model does not name. The save path and the tool path are
    supposed to be one set of rules (`_validated_skills`), and this is the
    seam where they were not."""
    response = client.put(
        "/preferences",
        json={
            "skills": [
                {
                    "name": "Tag the bare ones",
                    "prompt": "Tag every note that has no tags.",
                    "tools": ["list_notes", "tag_note", "count_notes"],
                    "verify": {
                        "tool": "count_notes",
                        "args": {"untagged": True},
                        "field": "count",
                        "expect": {"max": 0},
                    },
                }
            ]
        },
    )
    assert response.status_code == 200
    stored = client.get("/preferences").json()["skills"][0]
    assert stored["verify"] == {
        "tool": "count_notes",
        "args": {"untagged": True},
        "field": "count",
        "expect": {"max": 0},
    }


def test_a_check_the_skill_cannot_run_is_refused_by_the_settings_path_too(client, app_state):
    """One validator for both ways in: the message is the same sentence
    `save_skill` would have given the model."""
    response = client.put(
        "/preferences",
        json={
            "skills": [
                {
                    "name": "Checks with a tool it lacks",
                    "prompt": "Tag every note that has no tags.",
                    "tools": ["tag_note"],
                    "verify": {"tool": "count_notes", "expect": {"unchanged": True}},
                }
            ]
        },
    )
    assert response.status_code == 422
    assert "count_notes" in response.json()["detail"]


def test_no_built_in_step_asks_the_model_for_the_time_to_set_a_reminder():
    """AGENT_SKILLS_REFORM, "The harness does the work the model is worst
    at", consequence 3: a skill's steps get the same audit as the tools.
    `set_reminder` reads the user's own words (`ai/when.py`), so a step that
    fetched the clock "so any reminder lands on the right date" asked the
    model to do arithmetic the app does, and spent a round on it."""
    daily = next(s for s in skills.BUILTIN_SKILLS if s["name"] == "Daily review")
    texts = [step["text"] if isinstance(step, dict) else str(step) for step in daily["steps"]]
    assert not any("get_current_time" in text for text in texts), texts
    assert "get_current_time" not in daily["tools"]
    remind = next(text for text in texts if "set_reminder" in text)
    assert "own words" in remind


def _agent_intent_words() -> set[str]:
    source = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "skills.js").read_text(encoding="utf-8")
    block = source.split("const AGENT_INTENT_RE = new RegExp(", 1)[1].split('"i"', 1)[0]
    joined = "".join(re.findall(r'^\s*"([^"]*)"', block, re.M))
    return set(joined.replace("\\\\b(?:", "").replace(")\\\\b", "").split("|"))


def test_agent_nudge_verbs_ask_for_an_action_not_a_question() -> None:
    """The owner's 2026-10-10 triage: "how do I format a date" is a question,
    so "format", "fix", "plan" and the like do not offer Agent mode; "draft",
    "outline" and "generate" ask for something written and do."""
    words = _agent_intent_words()
    assert {"draft", "outline", "generate"} <= words
    assert not words & {"fix", "repair", "modify", "adjust", "plan", "build", "format", "translate"}


def test_the_skill_nudge_waits_for_a_model_and_tools() -> None:
    """The owner: "The ai model isnt running, skills are disabled, and it
    still suggests skills". The offer is gated on both, and the skills button
    carries the model gate every other AI control uses."""
    app = app_js_text()
    nudge = app.split("function renderChatNudge(", 1)[1].split("\nfunction ", 1)[0]
    skill_offer = nudge.split('chatNudgeDismissed.has("skill")', 1)
    assert len(skill_offer) == 2, "the skill offer moved; this test must follow it"
    gate = skill_offer[1].split("{", 1)[0]
    assert "aiIsOff()" in gate and '$("tools-toggle")?.checked' in gate
    # O7 (B69): the intent moved. The Skills button is no longer gated whole,
    # because the composer runs nine skills with no model; the menu disables
    # only the ones it cannot (`skill.composer`), each marked "(needs a model)".
    assert "needsModel" not in app.split("async function loadChatSkills(", 1)[1].split("\nfunction ", 1)[0]
    fill = app.split("function fillSkillSelect(", 1)[1].split("\nfunction ", 1)[0]
    assert "aiIsOff() && !skill.composer" in fill and "(needs a model)" in fill
