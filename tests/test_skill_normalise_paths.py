"""The refusals and the canonical form of `skills.normalise` that no test named.

Characterisation tests written before the function was split into tools,
inputs and placeholders (cc-1101): the sentence each refusal says, how a tool
list is cleaned, and how an input is read from a bare name or a full object.
"""

from __future__ import annotations

import pytest

from tessellate.ai import skills
from tessellate.ai.skills import SkillError, normalise

KNOWN = {"search_notes", "tag_note", "count_notes"}


def _refused(raw: dict, known: set[str] | None = None) -> str:
    with pytest.raises(SkillError) as caught:
        normalise(raw, known)
    return str(caught.value)


def test_a_skill_needs_a_name_a_prompt_or_steps():
    assert _refused({"name": "  ", "prompt": "Do it"}) == "A skill needs a name."
    assert _refused({"name": "Quiet"}) == "A skill needs a prompt saying what it should do, or steps."
    assert normalise({"name": "Stepped", "steps": ["Look"]})["prompt"] == ""


def test_the_tool_list_is_cleaned_in_order_and_capped():
    skill = normalise({"name": "T", "prompt": "p", "tools": [" tag_note ", "", None, "tag_note", "count_notes"]}, KNOWN)
    assert skill["tools"] == ["tag_note", "count_notes"] and skill["useTools"] is True
    assert normalise({"name": "T", "prompt": "p"}) ["tools"] == []
    many = [f"tool_{i}" for i in range(skills.MAX_TOOLS + 1)]
    assert _refused({"name": "T", "prompt": "p", "tools": many}) == f"A skill can name at most {skills.MAX_TOOLS} tools."


def test_a_tool_that_starts_a_run_or_does_not_exist_is_refused_with_its_name():
    assert _refused({"name": "T", "prompt": "p", "tools": ["run_skill"]}) == (
        "A skill can't use “run_skill”: a skill that starts another skill would never have to stop. "
        "Put the steps in this one."
    )
    assert _refused({"name": "T", "prompt": "p", "tools": ["nope"]}, KNOWN) == (
        "There is no tool called “nope”. Pick from the tools shown in Settings, Tools it can use."
    )
    assert normalise({"name": "T", "prompt": "p", "tools": ["nope"]})["tools"] == ["nope"]


def test_an_input_is_a_bare_name_or_an_object_and_is_read_with_its_defaults():
    skill = normalise(
        {
            "name": "I",
            "prompt": "Use {{tag}} and {{when}}",
            "inputs": ["tag", {"name": "when", "label": " When ", "required": False, "default": " today "}],
        }
    )
    assert skill["inputs"] == [
        {"name": "tag", "label": "tag?", "required": True, "default": ""},
        {"name": "when", "label": "When", "required": False, "default": "today"},
    ]


def test_a_bad_input_name_or_too_many_inputs_are_refused():
    message = "is not a usable input name. Use letters, digits and underscores, and start with a letter."
    assert _refused({"name": "I", "prompt": "p", "inputs": ["2bad"]}) == f"“2bad” {message}"
    assert _refused({"name": "I", "prompt": "p", "inputs": [{"label": "x"}]}) == f"“{{'label': 'x'}}” {message}"
    many = [f"in{i}" for i in range(skills.MAX_INPUTS + 1)]
    assert _refused({"name": "I", "prompt": "p", "inputs": many}) == f"A skill can declare at most {skills.MAX_INPUTS} inputs."


def test_an_undeclared_placeholder_in_the_prompt_or_a_step_is_refused():
    assert _refused({"name": "P", "prompt": "Use {{a}}"}) == "This skill uses {{a}} but doesn't declare it as an input."
    assert _refused({"name": "P", "prompt": "x", "steps": ["Do {{b}} and {{a}}"]}) == (
        "This skill uses {{a}}, {{b}} but doesn't declare them as an input."
    )
