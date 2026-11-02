"""Running a skill checked against the registry, and the turn's hand-offs.

Moved whole from `__init__.py` (audit AR3, gods-2): the code is unchanged, and
`__init__` re-exports every name here that anything reads. Imports run one way,
down the layer list in `__init__.py`'s docstring, never back to `__init__`.
"""

from __future__ import annotations

import json

from typing import Callable
from tessellate.ai.tools._common import ToolError, _clip
from tessellate.core import deps
from tessellate.ai import skills
from tessellate.ai.tools.tool_turn import MAX_NAME_ECHO, MAX_SKILL_NAMES, _match_skill, validate_ask, validate_compress_chat, validate_make_plan, validate_propose_act
from tessellate.ai.tools.tool_table import TOOLS
from tessellate.ai.tools.tool_sets import WRITE_TOOLS

def validate_run_skill(arguments: dict) -> dict:
    """The skill a run should start on and the values to run it with.

    Resolved against the catalog here rather than trusted, because every way a
    model can get this wrong is recoverable *if it is told which way*: a name
    that matches nothing (hand back the names), a required input left blank
    (name it), an input the skill never declared (drop it silently: an
    invented key is noise, not an error worth a round).

    The alternative is a run that starts on a guess, and unlike a question, a
    run changes notes.
    """
    catalog = skills.catalog(deps.get_config(), set(TOOLS))
    wanted = str(arguments.get("name") or "").strip()
    if not wanted:
        raise ToolError("run_skill needs the name of a skill to run.")
    skill = _match_skill(catalog, wanted)
    if skill is None:
        known = ", ".join(f"“{item['name']}”" for item in catalog[:MAX_SKILL_NAMES])
        raise ToolError(
            f"There is no skill called “{_clip(wanted, MAX_NAME_ECHO)}”. "
            + (f"The ones that exist are: {known}." if known else "There are none saved.")
            + " Call list_skills to see them, or don't run one."
        )
    held = skills.held_back_reason(deps.get_config(), skill["name"])
    if held:
        raise ToolError(
            f"“{skill['name']}” needs a larger model than the one in use: {held} "
            "Do the job step by step with your tools instead, or say so."
        )

    raw = arguments.get("inputs")
    if isinstance(raw, str):
        # A model that sent the whole object as a JSON string. Free to
        # recover, and the alternative is a run refused for a quoting mistake.
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = None
    declared = {item["name"] for item in skill.get("inputs") or []}
    values = {
        str(key): str(value or "").strip()[: skills.MAX_INPUT_VALUE]
        for key, value in (raw or {}).items()
        if str(key) in declared
    } if isinstance(raw, dict) else {}

    missing = skills.missing_inputs(skill, values)
    if missing:
        # Named, not guessed. A skill run with a blank {{topic}} searches the
        # whole notebook for nothing and reads to the user as being ignored, 
        # the same reason `_resolve_skill` returns 422 rather than running.
        labels = {item["name"]: item.get("label") or item["name"] for item in skill["inputs"]}
        raise ToolError(
            f"“{skill['name']}” needs "
            + ", ".join(f"{name} ({labels[name]})" for name in missing)
            + ". Pass them in `inputs`, or ask the user with ask_user first."
        )

    return {
        "type": "run_skill",
        "skill": skill["name"],
        "inputs": values,
        # What the user is about to watch start, in the words the chip UI
        # would have used. The run itself announces its plan; this is the line
        # that says *the model chose it*, which the plan cannot say.
        "label": f"ph:lightning Running “{skill['name']}”"
        + (f", {', '.join(v for v in values.values() if v)}" if any(values.values()) else ""),
        "changes_notes": bool(set(skill.get("tools") or []) & WRITE_TOOLS),
    }


#: The tools whose whole effect is to end the turn and hand over, mapped to the
#: validator that turns the model's arguments into the event the UI receives.
#: A dispatch table rather than a chain of name checks in the agent loop: the
#: loop's job is "this tool ends the turn", not "which one". Every validator
#: takes `(arguments, history)` even though only `compress_chat` reads the
#: second one: one call shape in `handoff_event` below, rather than a
#: special case for the one handoff that needs the conversation itself.
HANDOFFS: dict[str, Callable[[dict, list[dict] | None], dict]] = {
    "ask_user": lambda arguments, history: dict(
        zip(("question", "options"), validate_ask(arguments)), type="ask"
    ),
    "run_skill": lambda arguments, history: validate_run_skill(arguments),
    "make_plan": lambda arguments, history: validate_make_plan(arguments),
    "compress_chat": validate_compress_chat,
    "propose_act": validate_propose_act,
}

#: The handovers that start a *run*. A run must not start another run: each one
#: brings its own fresh rounds, so the budget that bounds a turn would never
#: bind, and the plan the user is watching would stop describing what is
#: happening. `skills.NEVER_IN_A_SKILL` refuses these in a saved allowlist; this
#: is the same rule for a run that declared no allowlist at all.
RUN_STARTERS = frozenset({"run_skill", "make_plan"})


def handoff_event(name: str, arguments: dict, history: list[dict] | None = None) -> dict:
    """The event a turn-ending tool hands to the UI, or a ToolError explaining
    why it can't: which the agent loop feeds back so the model can retry.

    `history` is the conversation `run_agent` already has in scope; only
    `compress_chat` reads it, but every handoff is called the same way.
    """
    build = HANDOFFS.get(name)
    if build is None:  # a spec marked ends_turn with nothing to hand over
        raise ToolError(f"{name} cannot end the turn, it has no handover.")
    return build(arguments, history)
