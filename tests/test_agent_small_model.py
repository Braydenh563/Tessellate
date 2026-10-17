"""What the agent asks of a 1.5B, against what it asks of a 27B.

The finding (WORLD_CLASS_PLAN A4): `SMALL_MODEL_PARAMS_B` and small-model
mode existed for skills, and `run_agent` used neither. A 3B was handed the
same registry, the same six-plus-six rounds and the same long descriptions as
a 70B, and the failure that produces is the one the owner reported for
skills: the model narrates instead of calling, or calls `make_plan` and then
cannot carry out the plan it wrote.

Everything below is measured against a scripted transport, so the numbers are
what goes on the wire, not what the code reads like. The standing caveat in
CLAUDE.md section 4 applies: no real small model was asked whether it does
better with this, and this file cannot show that.
"""

from __future__ import annotations

import json

from tessellate.ai import agent, model_manager


class _Session:
    def rollback(self):
        return None

    def commit(self):
        return None


class _Recorder:
    """A model that records the schemas it was offered, round by round, and
    replies with whatever was scripted for that round."""

    #: A real 32k window, so nothing below is the *window* rationing tools
    #: (`within_budget` drops the orchestration three under 6,000 schema chars
    #: on its own). Both models in every comparison get the same window, and
    #: the only difference is the name, which is the whole point of A4.
    window = 32_768

    def __init__(self, rounds=None, content=""):
        self.rounds = list(rounds or [])
        self.content = content
        self.offered: list[list[dict]] = []

    def usable_context(self, model):
        return self.window

    def chat_tools_stream(self, model, messages, offered, mode=None):
        self.offered.append([dict(spec) for spec in offered])
        calls = self.rounds.pop(0) if self.rounds else []
        yield {
            "final": {
                "content": "" if calls else self.content,
                "thinking": None,
                "tool_calls": calls,
                "raw_tool_calls": calls,
            }
        }


class _Models:
    def __init__(self, name: str) -> None:
        self.name = name

    def chat_model(self) -> str:
        return self.name

    def utility_model(self) -> str:
        return self.name


def _run(monkeypatch, model_name, rounds=None, results=None, content=""):
    fake = _Recorder(rounds, content=content)
    executed: list[tuple[str, dict]] = []
    results = list(results or [])

    def execute(session, name, arguments, **kwargs):
        executed.append((name, arguments))
        return results.pop(0) if results else {"ok": True}

    monkeypatch.setattr(agent.tools, "execute_tool", execute)
    events = list(agent.run_agent(_Session(), "q", [], _Models(model_name), fake))
    return fake, executed, events


def _names(offered: list[dict]) -> list[str]:
    return [spec["function"]["name"] for spec in offered]


# --- the predicate ------------------------------------------------------------


def test_the_predicate_is_the_one_skills_use() -> None:
    """One rule, in one place. The skills path reads it through
    `chat_model_is_small`; the agent reads the same function with the model it
    is actually about to call, which may be the utility model or an override."""
    assert model_manager.is_small_model("qwen3.5:4b") is True
    assert model_manager.is_small_model("llama3.1:70b") is False
    # 8B is the threshold and is NOT small: `size < SMALL_MODEL_PARAMS_B`.
    assert model_manager.is_small_model("llama3.1:8b") is False
    # The three states are kept apart: a name that says nothing answers None,
    # and every caller treats None as "not small" rather than guessing.
    assert model_manager.is_small_model("llama3.2") is None
    assert model_manager.is_small_model("") is None


# --- the tool schema ----------------------------------------------------------


def test_a_small_model_is_sent_fewer_and_shorter_schemas(monkeypatch, app_state):
    """Both halves of A4's claim, in counts and in bytes."""
    small, _, _ = _run(monkeypatch, "qwen3.5:4b", content="done")
    large, _, _ = _run(monkeypatch, "llama3.1:70b", content="done")

    small_specs = small.offered[0]
    large_specs = large.offered[0]
    assert len(small_specs) < len(large_specs), (
        len(small_specs),
        len(large_specs),
    )
    assert len(json.dumps(small_specs)) < len(json.dumps(large_specs))


def test_a_small_model_gets_no_orchestration_tools(monkeypatch, app_state):
    """`make_plan`, `run_skill`, `save_skill`: the three that ask a model to
    reason about work rather than about notes. A small model handed these
    reaches for them instead of answering."""
    small, _, _ = _run(monkeypatch, "qwen3.5:4b", content="done")
    offered = set(_names(small.offered[0]))
    assert not (offered & set(agent.tools.ORCHESTRATION_TOOLS)), offered


def test_a_small_model_gets_the_core_set_and_nothing_else(monkeypatch, app_state):
    """`CORE_TOOLS` minus `ORCHESTRATION_TOOLS`, exactly. Not a trim of
    whatever the question's cue words happened to pull in: the point is that
    the set is the same every turn, so the model sees one stable toolbox.
    Less `save_user_preference` unless the request is about the user (H4,
    `test_harness_tiers.py`)."""
    small, _, _ = _run(monkeypatch, "qwen3.5:4b", content="done")
    expected = [
        name
        for name in agent.tools.CORE_TOOLS
        if name not in agent.tools.ORCHESTRATION_TOOLS
        and name != "save_user_preference"
        and agent.tools.tool_enabled(name)
    ]
    assert sorted(_names(small.offered[0])) == sorted(expected)


def test_a_small_model_is_offered_the_tool_its_request_names(monkeypatch, app_state):
    """INBOX 527, measured on Qwen2.5-1.5B: the core alone holds one write, so
    "Pin my dentist note" had no `pin_note` and the model wrote a duplicate
    note. The request's cued groups ride after the stable core; orchestration
    stays out."""
    for question, needed in (
        ("Pin my dentist note", "pin_note"),
        ("Remind me tomorrow at 9 to call the dentist", "set_reminder"),
        ("Tag my plumber note with urgent", "tag_note"),
    ):
        fake = _Recorder([], content="done")
        monkeypatch.setattr(agent.tools, "execute_tool", lambda *a, **k: {"ok": True})
        list(agent.run_agent(_Session(), question, [], _Models("qwen3.5:4b"), fake))
        offered = _names(fake.offered[0])
        assert needed in offered, (question, offered)
        assert offered[: len(offered) - len(set(offered) - set(agent.tools.CORE_TOOLS))] == [
            name for name in offered if name in agent.tools.CORE_TOOLS
        ], "the core comes first"
        assert not set(offered) & set(agent.tools.ORCHESTRATION_TOOLS)


def test_a_small_model_gets_the_short_descriptions(monkeypatch, app_state):
    """Compaction is unconditional for a small model, not "once it overflows":
    on an 8k window the focused set measured 4,827 chars inside a 7,901-char
    allowance, so it fits and was sent in full."""
    small, _, _ = _run(monkeypatch, "qwen3.5:4b", content="done")
    for spec in small.offered[0]:
        description = spec["function"].get("description", "")
        assert len(description) <= agent.tools.COMPACT_DESCRIPTION_CHARS, spec[
            "function"
        ]["name"]


def test_a_large_model_keeps_its_orchestration_tools(monkeypatch, app_state):
    """The guard in the other direction: none of this may narrow a model that
    was coping. A plain "q" pulls the core set, which includes `make_plan`."""
    large, _, _ = _run(monkeypatch, "llama3.1:70b", content="done")
    assert "make_plan" in _names(large.offered[0])


def test_an_unrecognised_name_is_treated_as_large(monkeypatch, app_state):
    """None means "the name doesn't say", and narrowing a capable model on a
    guess is the worse mistake of the two."""
    unknown, _, _ = _run(monkeypatch, "llama3.2", content="done")
    assert "make_plan" in _names(unknown.offered[0])


def test_a_skills_declared_tool_list_is_still_honoured(monkeypatch, app_state):
    """A skill asked for exactly these; the small-model trim must not take
    one away, or the run breaks rather than gets simpler."""
    fake = _Recorder([], content="done")
    monkeypatch.setattr(agent.tools, "execute_tool", lambda *a, **k: {"ok": True})
    list(
        agent.run_agent(
            _Session(),
            "q",
            [],
            _Models("qwen3.5:4b"),
            fake,
            allowed_tools=["make_plan"],
        )
    )
    assert _names(fake.offered[0]) == ["make_plan"]


# --- the rounds ---------------------------------------------------------------


def test_a_small_model_stops_at_four_rounds(monkeypatch, app_state):
    """Six granted plus six earned is twelve chances to go wrong. A small
    model that has not finished in four is not going to finish in twelve; it
    is looping, and every extra round is another full prompt."""
    call = [{"name": "search_notes", "arguments": {"query": "x"}}]
    rounds = [[{**call[0], "arguments": {"query": str(index)}}] for index in range(12)]
    small, executed, _ = _run(
        monkeypatch,
        "qwen3.5:4b",
        rounds=rounds,
        results=[{"notes": [{"id": index}]} for index in range(12)],
    )
    # Tool rounds: the one after them (INBOX 527) offers no tools and only
    # answers from what was found.
    tool_rounds = [offered for offered in small.offered if offered]
    assert len(tool_rounds) <= agent.SMALL_MODEL_MAX_ROUNDS, len(tool_rounds)
    assert small.offered[-1] == []
    assert len(executed) <= agent.SMALL_MODEL_MAX_ROUNDS


def test_a_large_model_keeps_its_earned_rounds(monkeypatch, app_state):
    """The same script against a large model goes past four, so the cap above
    is the small-model rule and not a change to everyone's allowance."""
    rounds = [
        [{"name": "search_notes", "arguments": {"query": str(index)}}]
        for index in range(12)
    ]
    large, executed, _ = _run(
        monkeypatch,
        "llama3.1:70b",
        rounds=rounds,
        results=[{"notes": [{"id": index}]} for index in range(12)],
    )
    assert len(large.offered) > agent.SMALL_MODEL_MAX_ROUNDS, len(large.offered)


# --- the text-embedded call ---------------------------------------------------


def test_a_tool_call_written_as_text_runs_without_a_re_prompt(monkeypatch, app_state):
    """The small-model failure this app has actually seen: the model writes
    the call as prose instead of using the structured field, so the note it
    "creates" never gets made.

    The parser that recovers those is tried by the provider before the reply
    is handed back, which is what "before any re-prompt" means here: one model
    call in, one tool run out. The count of model calls is the measurement.
    """
    from tessellate.ai.provider import extract_text_tool_calls

    text = '{"name": "search_notes", "arguments": {"query": "cats"}}'
    recovered, clean = extract_text_tool_calls(text, {"search_notes"})
    assert [call["name"] for call in recovered] == ["search_notes"]
    assert clean.strip() == ""

    class _TextCaller(_Recorder):
        """Round one answers with the call written as text, exactly as a
        provider that has already recovered it hands it back."""

        def chat_tools_stream(self, model, messages, offered, mode=None):
            self.offered.append([dict(spec) for spec in offered])
            if len(self.offered) == 1:
                found, _ = extract_text_tool_calls(text, set(_names(offered)))
                yield {
                    "final": {
                        "content": "",
                        "thinking": None,
                        "tool_calls": found,
                        "raw_tool_calls": found,
                    }
                }
                return
            yield {
                "final": {
                    "content": "Found one.",
                    "thinking": None,
                    "tool_calls": [],
                    "raw_tool_calls": [],
                }
            }

    fake = _TextCaller()
    executed: list[str] = []

    def execute(session, name, arguments, **kwargs):
        executed.append(name)
        return {"notes": []}

    monkeypatch.setattr(agent.tools, "execute_tool", execute)
    list(agent.run_agent(_Session(), "q", [], _Models("qwen3.5:4b"), fake))

    assert executed == ["search_notes"]
    # Two model calls: the one that wrote the call as text, and the one that
    # read the result. A re-prompt would make it three.
    assert len(fake.offered) == 2


def test_an_empty_round_is_asked_once_more(ai_client, fake_ollama):
    """granite4.1:3b in the popup agent: a round with no text and no tool call
    ended the turn with nothing to show. It is nudged once, then answers."""
    replies = iter(["", "The graph shows how your notes connect."])
    original = fake_ollama.chat_tools

    def scripted(model, messages, tools, mode=None):
        fake_ollama.librarian_reply = next(replies)
        return original(model, messages, tools, mode)

    fake_ollama.chat_tools = scripted
    body = ai_client.post(
        "/chat/stream", json={"question": "what can I use the graph for?", "use_tools": True}
    ).text
    answer = "".join(
        json.loads(line)["delta"]
        for line in body.splitlines()
        if line and json.loads(line).get("type") == "answer"
    )
    assert answer == "The graph shows how your notes connect."
    assert any(
        m.get("content") == agent.EMPTY_ROUND_NUDGE for m in fake_ollama.tool_rounds[-1]
    )


def test_an_announced_but_untaken_action_is_asked_once_more(ai_client, fake_ollama):
    """Qwen2.5-1.5B through llama.cpp, the popup agent, 2026-10-03 (INBOX 432):
    asked "How many notes are in Work?", the model replied "To count notes in
    the Work category, I will use the count_notes function" and called
    nothing; the turn ended there, so every prompt read as answered and none
    was. A reply that only announces an action is nudged once to take it."""
    replies = iter(["I'll count the notes in the Work category for you.", "There are 3 notes in Work."])
    original = fake_ollama.chat_tools

    def scripted(model, messages, tools, mode=None):
        fake_ollama.librarian_reply = next(replies)
        return original(model, messages, tools, mode)

    fake_ollama.chat_tools = scripted
    body = ai_client.post(
        "/chat/stream", json={"question": "how many notes are in Work?", "use_tools": True}
    ).text
    answer = "".join(
        json.loads(line)["delta"]
        for line in body.splitlines()
        if line and json.loads(line).get("type") == "answer"
    )
    assert answer.endswith("There are 3 notes in Work.")
    assert any(
        m.get("content") == agent.UNACTED_INTENT_NUDGE for m in fake_ollama.tool_rounds[-1]
    )


def test_what_counts_as_an_announced_action():
    offered = [{"function": {"name": "count_notes"}}, {"function": {"name": "create_note"}}]
    for text in (
        "I'll count the notes in the 'Work' category for you.",
        "To count notes in the Work category, I will use the count_notes function.",
        "Let me search your notes for that.",
        "I am going to create a note for this.",
        # INBOX 527, Qwen2.5-1.5B: the note written out as markdown, the act
        # announced in the middle, nothing called.
        "Understood. I'll create a new note for you. Here it is:\n\n**Content:** "
        + "buy oat milk and eggs. " * 20
        + "\n\nI will call the tool to save the note for you.",
    ):
        assert agent.announces_unacted_tool(text, offered), text
    for text in (
        "You have 3 notes in Work.",
        "Let me know if you want me to file it anywhere else.",
        "I'll keep that in mind.",
        "",
        # A long answer is an answer, even if it promises more at the end.
        "Sourdough needs a starter fed daily. " * 20 + "I'll search for more if you like.",
        "Sourdough needs a starter fed daily. " * 20 + "I'll list the steps below: feed, wait.",
    ):
        assert not agent.announces_unacted_tool(text, offered), text
    # Nothing to call, nothing to nudge toward.
    assert not agent.announces_unacted_tool("I'll count them.", [])


def test_plan_mode_leaves_a_small_model_the_tool_it_is_told_to_call(monkeypatch, app_state):
    """Owner, 2026-10-17 (INBOX 904): Plan mode appends "Call make_plan with the
    goal and the steps", and the small-model toolbox had dropped `make_plan`, so
    the model reasoned about a tool it did not have. The request names it, so
    it stays; the other two orchestration tools still do not."""
    question = (
        "Plan an app for stored snippets.\n\nPlan this before you do any of it. "
        "Call make_plan with the goal and the steps, then carry the plan out."
    )
    monkeypatch.setattr(agent.tools, "execute_tool", lambda *a, **k: {"ok": True})
    fake = _Recorder([], content="done")
    list(agent.run_agent(_Session(), question, [], _Models("qwen3.5:4b"), fake))
    offered = set(_names(fake.offered[0]))
    assert "make_plan" in offered, offered
    assert not offered & {"run_skill", "save_skill"}, offered


def test_plan_mode_survives_a_small_window(app_state):
    """The window-budget drop of orchestration tools must not undo it either."""
    question = "Do it.\n\nCall make_plan with the goal and the steps."
    every = agent.tools.ollama_tools(None)
    keep = agent.tools.keep_first_for(question)
    exempt = frozenset({"make_plan"}) if agent.tools.asks_for_plan(question) else frozenset()
    kept, dropped = agent.tools.within_budget(every, 3000, keep, exempt)
    assert "make_plan" in _names(kept), dropped
    kept, _ = agent.tools.within_budget(every, 3000, agent.tools.keep_first_for("hello"))
    assert "make_plan" not in _names(kept)
