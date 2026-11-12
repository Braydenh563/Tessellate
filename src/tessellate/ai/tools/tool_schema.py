"""The schemas the model is shown: Ollama's shape, compacting, ranking and the window budget, and the catalog.

Moved whole from `__init__.py` (audit AR3, gods-2): the code is unchanged, and
`__init__` re-exports every name here that anything reads. Imports run one way,
down the layer list in `__init__.py`'s docstring, never back to `__init__`.
"""

from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session
from tessellate.repo import relation_types
from tessellate.ai import toolrank, toolwords
from tessellate.ai.tools.tool_sets import CHANGE_TOOLS, CORE_TOOLS, TOOL_GROUPS, WRITE_TOOLS, tool_enabled
from tessellate.ai.tools.tool_read import CHARS_PER_TOKEN
from tessellate.ai.tools.tool_table import TOOLS
from tessellate.ai.tools.tool_focus import focus_detail
from tessellate.ai.tools.tool_write import link_type_description

def ollama_tools(allowed: list[str] | None = None, session: Session | None = None) -> list[dict]:
    """The registry in the shape Ollama's /api/chat 'tools' field wants,
    minus any the user disabled, a model can't be tempted by a tool it
    never hears about.

    `allowed` narrows it further, to the tools a skill declared. That is
    roadmap §11a in one line: 28 schemas are ~77% of the fixed per-round
    overhead, and a skill that needs three of them should pay for three. The
    user's own switches still win, a skill cannot re-enable something turned
    off in Settings, Tools.
    """
    wanted = set(allowed) if allowed else None
    offered = [
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
            },
        }
        for spec in TOOLS.values()
        if tool_enabled(spec.name) and (wanted is None or spec.name in wanted)
    ]
    return with_relation_types(offered, session) if session is not None else offered


def with_relation_types(offered: list[dict], session: Session) -> list[dict]:
    """`link_notes` described with this notebook's own kinds of link (KG3):
    a copy of that one schema, so the registry stays what it was."""
    for index, spec in enumerate(offered):
        function = spec.get("function") or {}
        props = (function.get("parameters") or {}).get("properties") or {}
        if function.get("name") != "link_notes" or "link_type" not in props:
            continue
        try:
            kinds = relation_types.kinds(session)
        except Exception:  # noqa: BLE001
            # A session that cannot list kinds (a test double, a closed
            # session) keeps the registry's own description: the built-ins.
            continue
        text = link_type_description(kinds)
        parameters = {
            **function["parameters"],
            "properties": {**props, "link_type": {**props["link_type"], "description": text}},
        }
        offered = [*offered[:index], {**spec, "function": {**function, "parameters": parameters}}, *offered[index + 1 :]]
    return offered


# --- fitting the registry to the model that will read it -------------------------
#
# Asked directly, after four category tools took the all-tools overhead within
# ~180 characters of a 4096-token window: "if adding more tools is an issue, can
# we change or improve how tools are used so that doesn't become an issue?"
#
# The honest answer is that the ceiling was never a fact about the app, it was
# an assumption about the model. 4096 is what Ollama falls back to when a model
# declares nothing; a current 7B routinely declares 32k or 128k, and rationing
# against 4096 there withholds tools for no reason at all. Meanwhile a genuine
# 3B at 4096 needed rationing *harder* than a fixed constant could express,
# because the right number depends on the question too.
#
# So the fixed budget is replaced by a measured one: ask the model how much room
# it has (ollama_client.usable_context), spend a bounded share of it on schemas,
# and drop the least relevant tools when they do not fit. Adding a tool stops
# being a question of whether it fits inside a constant, and becomes a question
# of what gets sent first, which is a much easier question, and one the app can
# answer per turn instead of once at import time.

# The share of the window the tool schemas may occupy. The rest is the system
# prompt, the retrieved notes, the history and the answer, and tool RESULTS,
# which is what makes a generous share a false economy: schemas the model never
# calls cost the same as ones it does.
TOOL_SCHEMA_WINDOW_SHARE = 0.25

#: Below this much room for schemas, the model is a small one (roughly: a 3B
#: on a 4k window) and the tools below come off the list.
SMALL_WINDOW_CHARS = 6_000

#: Tools that ask the model to reason about *work* rather than about notes:
#: writing a plan, delegating to a saved skill, saving a new one. A small model
#: handed these tends to reach for them instead of answering, and then handles
#: the multi-step result badly, so on a small window they are the first thing
#: to go, ahead of the size-based trim below.
#:
#: `ask_user` is deliberately NOT in this set, though it was put here once. It
#: is the opposite of complex: one question, a few options, and it is the only
#: way the agent can say "I need to know which one you meant". Taking it away
#: from small models left them guessing, the exact failure it exists to stop , 
#: and it is one of the cheapest schemas in the registry.
ORCHESTRATION_TOOLS = frozenset({"make_plan", "run_skill", "save_skill"})


def schema_chars(specs: list[dict]) -> int:
    """What this list of tool schemas costs on the wire."""
    return len(json.dumps(specs))


#: How much of a tool description survives compaction. One sentence is what a
#: model needs to pick between tools; the rest is disambiguation it only needs
#: once it has already picked, by which point the arguments say more than the
#: prose does.
COMPACT_DESCRIPTION_CHARS = 150

#: Parameter descriptions get less again, the name and JSON type already carry
#: most of it ("limit", integer), so what is left is the unit or the range.
COMPACT_PARAM_CHARS = 60

#: A sentence end followed by whitespace. Cutting on this rather than on a
#: character count keeps the trimmed description a sentence rather than a
#: fragment that stops mid-clause.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s")


def _first_sentence(text: str, cap: int) -> str:
    """The leading sentence of ``text``, or a hard-trimmed prefix."""
    text = " ".join((text or "").split())
    if len(text) <= cap:
        return text
    match = _SENTENCE_END.search(text)
    if match and match.start() < cap:
        return text[: match.start() + 1]
    return text[:cap].rstrip()


def compact_schemas(offered: list[dict]) -> list[dict]:
    """The same tools, described in one sentence each.

    **Why this exists, and why it runs before anything is dropped.** Measured
    on a real turn with an 8k-window model, eight notes and no history, the
    prompt broke down as system 3,288 chars, notes-and-question 2,377, and tool
    schemas 4,827: the schemas cost nearly twice what the user's own notes
    did, and were the single largest thing in the prompt. That is the reported
    *"agent mode and chats are too heavy for small models"* in one number.

    The instinct is to send fewer tools, and `within_budget` did exactly that.
    But dropping a tool changes what the app can *do*, the model stops being
    able to set a reminder, and the only visible symptom is that it says it
    cannot, which reads as the app being broken rather than rationed. Trimming
    a description changes only how verbosely each tool is explained. So on a
    window too small for the full set, this is tried first and tools are only
    dropped if it is still not enough.

    Names, parameter names, types and required-ness are untouched: those are
    what the model actually calls the tool with, and shortening any of them
    would produce malformed calls rather than a smaller prompt.
    """
    out: list[dict] = []
    for spec in offered:
        function = spec.get("function") or {}
        parameters = function.get("parameters") or {}
        properties = parameters.get("properties") or {}
        slim_properties = {}
        for key, value in properties.items():
            if isinstance(value, dict) and "description" in value:
                value = {
                    **value,
                    "description": _first_sentence(
                        value["description"], COMPACT_PARAM_CHARS
                    ),
                }
            slim_properties[key] = value
        out.append(
            {
                **spec,
                "function": {
                    **function,
                    "description": _first_sentence(
                        function.get("description", ""), COMPACT_DESCRIPTION_CHARS
                    ),
                    "parameters": {**parameters, "properties": slim_properties}
                    if parameters
                    else parameters,
                },
            }
        )
    return out


#: Plan mode's own sentence (`PLAN_PREFIX`, frontend/js/wiring.js): the request
#: names the tool, so a small model must be handed it (owner, 2026-10-17).
_PLAN_MODE_CUE = re.compile(r"\bcall make_plan\b", re.IGNORECASE)


def asks_for_plan(question: str) -> bool:
    return bool(_PLAN_MODE_CUE.search(question or ""))


def keep_first_for(question: str) -> list[str] | None:
    """The tools a small window must not drop for this question: a turn that
    asks for the web outright keeps `web_search` and `read_url` at the head of
    the budget. They were appended last and so cut first, and the model, told
    about web search by the help text but not handed the tool, thought for 150
    seconds and answered that it had no way to look (owner, 2026-10-12)."""
    if toolwords.asks_web(question) and tool_enabled("web_search"):
        return ["web_search", "read_url", *CORE_TOOLS]
    if asks_for_plan(question):
        return ["make_plan", *CORE_TOOLS]
    return None


def rank_tools(question: str, recent: str = "", recent_tools: tuple[str, ...] = ()) -> list[tuple[str, float]]:
    """Every registered tool with the probability the question wants it,
    likeliest first (`ai/toolrank.py`). Not filtered by Settings: whether a
    tool is on is a separate fact, and a ranking that hid the off ones could
    not say what a turn held back."""
    focus = focus_detail(question, recent)
    specs = [{"function": {"name": s.name, "description": s.description, "parameters": s.parameters}} for s in TOOLS.values()]
    return toolrank.rank(
        question,
        specs,
        core=CORE_TOOLS,
        groups=TOOL_GROUPS,
        ranked_groups=focus.ranked,
        kept_first=keep_first_for(question),
        writes=WRITE_TOOLS,
        asking_about=focus.asking_about,
        recent_tools=recent_tools,
    )


def ranking_line(offered: list[str], held_back: list[str], chances: dict[str, float]) -> str:
    """The log line for a turn's ranking, see `toolrank.line`."""
    return toolrank.line(offered, held_back, chances)


def within_budget(
    offered: list[dict],
    budget_chars: int,
    keep_first: list[str] | None = None,
    exempt: frozenset[str] = frozenset(),
    ranking: dict[str, float] | None = None,
) -> tuple[list[dict], list[str]]:
    """(the tools that fit, the names dropped), most important kept.

    Order is the whole design. CORE_TOOLS go first because a model that cannot
    search or read a note cannot answer anything; whatever the question-focus
    picked comes next; the rest fill the remaining room. Dropping happens at
    the tail, so what is lost is always the least relevant thing left.

    At least one tool is always returned even if the budget cannot afford it:
    a model handed an empty tool list does not degrade gracefully, it simply
    answers from nothing and sounds confident about it.
    """
    if budget_chars <= 0 or not offered:
        return offered, []
    # Cheaper descriptions before fewer tools, see compact_schemas for the
    # measurement behind that order. Only when the full set genuinely does not
    # fit: a model with room for the long descriptions should get them, because
    # they are what stops it reaching for the wrong tool.
    if schema_chars(offered) > budget_chars:
        offered = compact_schemas(offered)
    priority = list(keep_first or CORE_TOOLS)
    rank = {name: index for index, name in enumerate(priority)}
    chances = ranking or {}
    # The priority list first, then the likeliest (`rank_tools`); equal chances
    # keep the order the focus gave them.
    ordered = sorted(offered, key=lambda t: (rank.get(t["function"]["name"], len(rank)), -chances.get(t["function"]["name"], 0.0)))

    kept: list[dict] = []
    dropped: list[str] = []
    small_window = budget_chars < SMALL_WINDOW_CHARS

    for spec in ordered:
        name = spec["function"]["name"]
        if small_window and name in ORCHESTRATION_TOOLS and name not in exempt:
            dropped.append(name)
            continue
        # Measured against the list as it will actually be serialised, rather
        # than by summing individual schemas, the brackets and commas are
        # small but they are also the difference between fitting and not.
        if not kept or schema_chars(kept + [spec]) <= budget_chars:
            kept.append(spec)
        else:
            dropped.append(name)
    return kept, dropped


def budget_for_window(context_tokens: int) -> int:
    """How many characters of tool schema a model with this window can hold."""
    return int(context_tokens * TOOL_SCHEMA_WINDOW_SHARE) * CHARS_PER_TOKEN


#: **The tools a skill's `verify` block can read a number from**, which is the
#: list the skill editor offers (`renderSkillVerifyPicker`, app.js). A block
#: may name any read-only tool and the runner will try it, so this is a
#: shortlist rather than a rule: these two answer a question about notes with
#: one integer in a field `skills.VERIFY_COUNT_FIELDS` looks for, and
#: `tests/test_harness_verifier.py` runs each of them to prove it rather than
#: trusting this comment. Offering thirty tools in a dropdown, most of which
#: come back with no number at all, would be offering a choice that mostly
#: fails at the end of a run.
COUNTING_TOOLS = ("count_notes", "list_notes")


def tool_catalog() -> list[dict]:
    """Metadata for the Settings, Tools toggles."""
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "destructive": spec.destructive or spec.name in CHANGE_TOOLS,
            "enabled": tool_enabled(spec.name),
            "online": spec.name in ("web_search", "read_url"),
            "counts": spec.name in COUNTING_TOOLS,
            #: The Settings list's group (CHAT_PLAN, INBOX 71): what a tool
            #: does to the notebook, the one question a person switching it
            #: off is asking.
            "group": (
                "online"
                if spec.name in ("web_search", "read_url")
                else "confirm"
                if spec.destructive or spec.name in CHANGE_TOOLS or spec.name in WRITE_TOOLS
                else "read"
            ),
        }
        for spec in TOOLS.values()
    ]
