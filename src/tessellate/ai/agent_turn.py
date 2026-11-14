"""The agent loop, layer two: one turn's messages and plan (audit 1031 AI23).

`build_agent_messages`, the turn plan and focus, `_prepare_turn`, the turn state,
result fitting and the first round's toolbox, up to the tool events. A pure move
out of `agent.py`, text unchanged; it imports `agent_policy` and nothing above.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import cards, context, fence, librarian, memory, tools
from tessellate.ai.agent_policy import (
    _OUTBOUND_TOOLS,
    _WRITE_TOOLS,
    AGENT_GROUNDING,
    FOCUS_NOTE,
    SMALL_WINDOW_TOKENS,
    SizeTier,
    claims_a_write,
    _bare_host,
    _page_key,
    _result_summary,
    _seen_ids,
    _tool_sources,
    _touched_items,
    size_tier,
    unsupported_claims,
    tools_guide,
)
from tessellate.ai.model_manager import ModelManager
from tessellate.ai.ollama_client import OllamaClient


def _now_hint() -> str:
    """The date line of the agent system prompt: weekday, the week ahead, and the clock last."""
    # The model needs "now" to turn "in 10 minutes" into a real time.
    # The user's wall clock. This line is what "remind me in 10 minutes"
    # is computed from, so resolving it against the server's zone instead
    # puts every relative time out by the offset between them.
    from datetime import timedelta

    from tessellate.core import deps
    from tessellate.core.config import user_now

    local = user_now(deps.peek_config())
    # To the minute, not the microsecond. This string sits near the top of a
    # prompt that is resent on every round of every turn, and Ollama's prefix
    # cache keeps only the tokens *before* the first difference, so a clock
    # that ticked every microsecond invalidated the history and the notes
    # below it every single time, and each round re-read the whole prompt from
    # scratch. A tool loop runs its rounds seconds apart, so a minute-precision
    # clock is identical across all of them, and no answer this app gives
    # needs the seconds: "remind me in 10 minutes" is not resolved to one.
    #: **The weekday and the week ahead, because the model was computing them
    #: and getting them wrong.** The owner's transcript, 2026-09-21: he asked
    #: for a reminder two hours before midnight, and the model reasoned "the
    #: current date and time is 2026-09-21T15:55+10:00 ... midnight for today
    #: is 2026-09-22T00:00 ... two hours before midnight is 2026-09-22T22:00",
    #: which is a day out: two hours before that midnight is the 21st at
    #: 22:00. It also had a note saying the work was due "Friday" and no way
    #: to turn that into a date without counting days from an ISO string.
    #:
    #: An ISO timestamp does not say what day of the week it is, so a small
    #: model derives it, and deriving a weekday from a date is exactly the
    #: arithmetic these models are worst at. The days are cheap to state and
    #: they are facts, so they are stated: naming them costs about 120
    #: characters against `PROSE_BUDGET_CHARS` and removes a whole class of
    #: wrong answer.
    #:
    #: The "still today" sentence that followed is gone (INBOX 527): it taught
    #: reminder arithmetic, which `ai/when.py` now does. The week stays,
    #: because placing a note's "due Friday" is reading, not a tool argument.
    #: The day number by hand, not `%-d`: that flag is glibc's, and Windows'
    #: strftime raises "Invalid format string" on it, which took every agent
    #: turn down on the owner's machine before the first event.
    week = ", ".join(
        f"{day:%a} {day.day} {day:%b}" for day in (local + timedelta(days=n) for n in range(1, 8))
    )
    #: The order inside this line matters for the same reason the line's own
    #: position does. The weekday, the week ahead and the rule change once a
    #: day; the timestamp changes every minute. So the daily part goes first
    #: and the minute goes last, which keeps the prefix cache holding
    #: everything up to the minute that actually ticked.
    #: `tests/test_prompt_prefix_stability.py` asserts the clock is last, and
    #: it caught this being written the other way round.
    now_hint = (
        f" Today is {local.strftime('%A')}, and the next seven days are {week}."
        f" The current date and time is {local.replace(second=0, microsecond=0).isoformat()}"
        f" ({local.tzname() or 'local time'})."
    )
    return now_hint


def _notes_section(notes: list[dict], budget: "context.ContextBudget | None") -> str:
    """The `My notes:` block of the agent user message, trimmed to the budget and honest about what was cut."""
    dropped_notes = 0
    if budget is not None:
        notes, dropped_notes = context.fit_notes(
            notes, budget.notes_chars, librarian.note_for_prompt
        )

    numbered = "\n".join(
        # Same caveats the plain (no-tools) librarian prompt already gives,
        # attached-by-hand, linked-not-matched (with its reason, when the
        # link has one), similarity/keyword match info, reused rather than
        # left agent-mode-only silent about them. Nothing new to compute:
        # `prepared["notes"]` already carries this from routes_chat.py; the
        # agent path just never read it before.
        f"{i}. (note id {note.get('id', '?')}){librarian.category_hint(note)}"
        #: When it was written and what its time words meant (INBOX 441: the
        #: chat read a two-week-old "this Friday" as this week's).
        f"{librarian._written_hint(note)}{librarian._dates_hint(note)}"
        #: INBOX 527, the owner: "does the ai know that it can have images in
        #: its response??" Chat and Ask did (526); this prompt, the default
        #: with tools on, did not. N is the note's number here, which is its
        #: place in the turn's `raw_results`, where the bubble looks it up.
        f"{librarian._pictures_hint(note, i)}"
        f"{' (attached by me)' if note.get('attached') else ''}"
        f"{' (not a match: linked to one of the above)' if note.get('connected') else ''}"
        f"{librarian._match_info_hint(note.get('match_info'))} "
        f"{librarian.note_for_prompt(note)}"
        for i, note in enumerate(notes, start=1)
    )
    #: **No match is not an empty notebook** (INBOX 527, Qwen2.5-1.5B): with
    #: four notes saved, "How many notes do I have?" matched none of them by
    #: its words, the prompt said "My notebook looks empty", and the model
    #: answered "There are no notes in your notebook". Retrieval cannot see the
    #: notebook's size; count_notes can.
    body = (
        f"My notes:\n{numbered}\n\n"
        if notes
        else "(No notes matched these words. That says nothing about how many I have: count_notes and search_notes do.)\n\n"
    )
    if dropped_notes:
        # Said rather than silently done. A model that knows its notes were
        # cut short can search for the rest; one that doesn't will answer as
        # though it saw the whole notebook, which is the confident-and-wrong
        # failure this app exists to avoid.
        body = (
            f"{body[:-2]}\n({dropped_notes} more matching note"
            f"{'' if dropped_notes == 1 else 's'} did not fit: use search_notes "
            f"or get_note if you need them.)\n\n"
        )
    return body


def build_agent_messages(
    question: str,
    notes: list[dict],
    style: str = "friendly",
    profile: str = "",
    history: list[dict] | None = None,
    persona_prompt: str | None = None,
    budget: "context.ContextBudget | None" = None,
    mode: str | None = None,
    images: list[str] | None = None,
) -> list[dict]:
    """Like librarian.build_messages, but the system prompt allows
    acting, and each note shows its id so tools can target it.

    `budget` trims the notes and the history to what the model can actually
    hold. Optional so every existing caller keeps working untrimmed, the
    agent loop passes one, having measured the window first.
    """
    style_hint = librarian.STYLE_HINTS.get(style, librarian.STYLE_HINTS["friendly"])
    profile_hint = f" About the user: {profile.strip()}" if profile.strip() else ""
    persona = (persona_prompt or librarian.DEFAULT_PERSONA).strip()
    now_hint = _now_hint()
    # **The clock goes last, and that ordering is the whole point.** A
    # prefix cache (Ollama's, llama.cpp's, every backend that has one) keeps
    # the tokens *before the first difference* and re-reads everything after
    # it. Rounding to the minute above stops the clock changing between the
    # rounds of one turn; putting it at the end of the message stops the
    # minute it does change from invalidating anything ahead of it. Persona,
    # grounding and the tools guide, by far the largest part of this prompt,
    # and the part that is identical turn after turn, now sit in front of
    # every volatile byte, so they are re-read from cache instead of
    # re-processed. Asked for directly: "keep the system prompt + persona
    # byte-identical turn to turn so the cache is reused."
    #
    # Everything between them is stable *within* a conversation: the style
    # hint, the profile and the length hint only change when the user changes
    # a setting or the mode, which is a new prefix either way.
    messages = [
        {
            "role": "system",
            "content": f"{persona} {AGENT_GROUNDING} "
            f"{tools_guide(budget.window_tokens if budget else None)} "
            f"{style_hint}{profile_hint}{librarian.length_hint(mode)}{now_hint}",
        }
    ]
    past = librarian.history_messages(history)
    if budget is not None:
        past = context.fit_history(past, budget.history_chars)
    messages.extend(past)

    body = _notes_section(notes, budget)
    user_message = {
        "role": "user",
        "content": f"{librarian._app_help(question)}{body}My request: {question}",
    }
    if images:
        user_message["images"] = images
    messages.append(user_message)
    return messages


# Handed back when an `ask_user` call is malformed, so the model can recover
# in the same turn instead of the question silently failing.
# What a turn-ending tool is told when its handover was malformed. Per tool,
# because the useful advice differs: a bad question is worth re-asking, a
# skill that doesn't exist usually means there was no skill for this job.
_HANDOFF_RECOVERY = {
    "ask_user": (
        "Fix the question and call ask_user again with 2-6 short options, or, "
        "if you can work it out yourself, just answer without asking."
    ),
    "run_skill": (
        "Call list_skills to see the exact names and what each one needs, then "
        "run_skill again: or, if none of them fits, just do the job yourself "
        "with the ordinary tools."
    ),
    "compress_chat": (
        "There isn't enough conversation yet to compress, keep going, or "
        "just answer without calling this."
    ),
}


def recovery_for(name: str) -> str:
    """The advice for a malformed handover by `name`; a bad question's for any other."""
    return _HANDOFF_RECOVERY.get(name, _HANDOFF_RECOVERY["ask_user"])


# What the model is told when a destructive call is parked for approval.
AWAITING_CONFIRMATION = {
    "status": "awaiting_user_confirmation",
    "note": (
        "The app is showing the user a confirm button for this action. "
        "It has NOT run yet, tell the user it's waiting for their approval."
    ),
}


#: How much of the previous exchange a follow-through turn is read against.
#: Two turns' worth of text, capped, this is only ever used for keyword
#: matching, so the whole of a long answer adds nothing but false positives
#: from words the model happened to use in passing.
FOLLOW_THROUGH_CONTEXT_CHARS = 1_200


def _recent_text(history: list[dict] | None) -> str:
    """The last exchange, as plain text, for reading a follow-through against.

    Newest first and clipped, so what survives the cap is the turn the user is
    actually following through *on* rather than the start of the conversation.
    """
    if not history:
        return ""
    parts: list[str] = []
    for turn in reversed(history[-2:]):
        for key in ("question", "answer", "content"):
            value = turn.get(key)
            if isinstance(value, str) and value:
                parts.append(value)
    # Clipped once, at the end, rather than per piece: clipping each and then
    # joining put the separators outside the budget, so the cap was not a cap.
    return " ".join(parts)[:FOLLOW_THROUGH_CONTEXT_CHARS]


#: The board and map tools a picture question must not be sent to (below).
_CANVAS_TOOLS = frozenset(
    {
        "read_whiteboard",
        "search_whiteboard",
        "add_whiteboard_card",
        "add_whiteboard_link",
        "generate_diagram",
        "read_mindmap",
        "create_mindmap",
        "map_from_note",
        "add_map_node",
        "link_map_nodes",
    }
)
#: Words that ask for a board to be changed, which keep the board tools.
_CANVAS_WRITE = re.compile(r"\b(?:add|put|place|pin|draw|make|create|link|map|diagram)\b", re.I)
_PICTURE_WORDS = re.compile(
    r"\b(?:photo|photos|picture|pictures|pic|image|images|sketch|drawing|screenshot|scan)\b", re.I
)


_PREFERENCE_CUE = re.compile(
    r"\b(?:remember|prefer|preference|from now on|always|never|call me|my name|i like|i don'?t like|i hate|i love)\b",
    re.I,
)
_FENCE_TEXT = re.compile(r"<<<(?:end data|data[^<>\n]{0,40})>>>")


def _copies_what_was_read(arguments: dict, messages: list[dict], wrote: bool) -> bool:
    """**A `create_note` that is a copy of a note this turn already has.**

    Qwen2.5-3B, H4: "Pin my dentist note" pinned it and then made a new note
    of the same text with the prompt's fence markers in it; "Add 'bring a rain
    jacket' to my Snowdon note" edited it and then made a copy of the edited
    note. Prompt markers in a new note are always a copy; otherwise, after a
    write, a new note whose first line (20 characters or more) is already in
    a note or tool result this turn is the same note again.
    """
    content = str(arguments.get("content") or "")
    if _FENCE_TEXT.search(content):
        return True
    first = content.strip().split("\n", 1)[0].strip()
    if not wrote or len(first) < 20:
        return False
    return any(
        first in str(m.get("content") or "")
        for m in messages[1:]
        if m.get("role") in ("user", "tool")
    )


def _picture_in_hand(question: str, notes: list[dict]) -> bool:
    """**A picture question whose picture is already in the prompt.**

    Measured on Qwen2.5-1.5B (INBOX 527's eval): "Show me the whiteboard
    sketch from the planning meeting" cued the board tools by its words, and
    the model read a whiteboard instead of writing `[picture 1]` for the note
    that held the sketch, listed in its own prompt with "has 1 picture"; with
    the reads gone, Qwen2.5-3B placed the note on a board instead (H4). When
    a note with a picture shares a word with a question that does not ask for
    a board to change, the board and map tools are left off the first offer;
    the focus correction still widens to them if the model asks.
    """
    if not _PICTURE_WORDS.search(question or "") or _CANVAS_WRITE.search(question or ""):
        return False
    from tessellate.search.search_manager import _meaningful_terms

    asked = {t for t in _meaningful_terms(question) if not _PICTURE_WORDS.fullmatch(t)}
    for note in notes or []:
        if not note.get("pictures"):
            continue
        text = f"{note.get('title') or ''} {note.get('content') or ''}".lower()
        if any(re.search(rf"\b{re.escape(term.lower())}", text) for term in asked):
            return True
    return False


def _focus(question: str, history: list[dict] | None = None) -> list[str] | None:
    """Which tools this turn is offered, unless the user asked for all of them.

    Settings, Tools has the switch, because the honest failure mode of a
    keyword rule is a request phrased in words it doesn't know, and the fix
    for that has to be reachable without editing code.

    `history` is passed so a turn that means "now do what we just discussed"
    can be read against what was discussed, reported directly, and the cause
    of an agent that answered "implement those suggestions" with the same
    suggestions again. See `tools.focus_for`.
    """
    from tessellate.core import deps

    if str(deps.get_config().get_preference("tool_focus", "auto")) == "all":
        return None
    return tools.focus_for(question, _recent_text(history))


@dataclass(slots=True)
class _TurnPlan:
    """Everything decided before the first model call of a turn.

    A record rather than sixteen locals, because the decisions are what the
    stage below is *for*: which model, how big it is, what the window affords,
    which messages, which tools, how many rounds. Reading them off one object
    is how a reader tells what the turn was set up to do without stepping
    through 190 lines of setup first (WORLD_CLASS_PLAN A5).
    """

    agent_model: str
    #: The size tier this turn runs under (`SIZE_TIERS`).
    tier: SizeTier
    #: The model's usable context, or None when the provider does not say.
    #: Passed to each tool call so a tool can size its own result.
    window: int | None
    budget: object
    messages: list[dict]
    offered: list[dict]
    every_tool: list[dict]
    focused_only: bool
    permitted: set[str] | None
    barred: set[str]
    composition_tokens: dict[str, int]
    granted: int
    ceiling: int


def _narrow_keeps(name: str, question: str, keep_pref: bool) -> bool:
    """Whether a small model's stable toolbox keeps `name`: no orchestration
    tool unless the request itself says to call `make_plan` (Plan mode), and
    `save_user_preference` only when the request is about the user."""
    plan = name == "make_plan" and tools.asks_for_plan(question)
    return (name not in tools.ORCHESTRATION_TOOLS or plan) and (
        keep_pref or name != "save_user_preference"
    )


def _plan_exempt(question: str) -> frozenset[str]:
    """Orchestration tools a small window may not drop for this request."""
    return frozenset({"make_plan"}) if tools.asks_for_plan(question) else frozenset()


def _focus_names(
    question: str,
    history: list[dict] | None,
    notes: list[dict],
    allowed_tools: list[str] | None,
    tier,
) -> list[str] | None:  # noqa: ANN001
    # A skill's declared tools are the only ones offered for its run: fewer
    # schemas on the wire (roadmap §11a) and a narrower thing to go wrong.
    # An ordinary turn declares nothing, so the question is read for what it
    # plausibly needs: see tools.focus_for. Note the asymmetry: the skill's
    # list is also *enforced* below, while the focus is only an economy. A
    # tool left out because a cue didn't fire must still run if the model
    # somehow calls it.
    focus_names = allowed_tools if allowed_tools is not None else _focus(question, history)
    if tier.narrow_toolbox and allowed_tools is None:
        # **One stable toolbox for a small model, not a per-question guess.**
        # `_focus` is an economy: it reads the question's words and adds the
        # groups they hint at, so the same model sees a different set every
        # turn and the set is usually larger than the core. Both halves are
        # wrong here. A small model does better with a short list it sees
        # every time than with a longer one tuned to the question, and the
        # orchestration three (`make_plan`, `run_skill`, `save_skill`) are the
        # ones it reaches for instead of answering: `ORCHESTRATION_TOOLS`
        # already documents that, and `within_budget` already drops them on a
        # small *window*. This is the same judgement made on the model's size.
        #
        # A skill's declared list is exempt (`allowed_tools is not None`): it
        # asked for exactly those tools, and dropping one breaks the run
        # rather than simplifying it.
        #:
        #: **Plus the tools the request itself names** (INBOX 527, measured on
        #: Qwen2.5-1.5B): the core alone holds one write, `create_note`, so
        #: "Pin my dentist note" was offered no `pin_note` and the model wrote
        #: a duplicate note instead; 2 of 10 everyday requests chose a right
        #: tool. The cued groups are added after the core, which stays first
        #: and stable; a broad request (None) still gets the core alone.
        cued = _focus(question, history) or []
        #: `save_user_preference` only when the request is about the user
        #: (H4, Qwen2.5-3B under the forced first call: "Note down: ...",
        #: "Save this: ..." and "Put ... in my note" saved a preference, 3/20).
        keep_pref = bool(_PREFERENCE_CUE.search(question or ""))
        focus_names = [
            name
            for name in dict.fromkeys([*tools.CORE_TOOLS, *cued])
            if _narrow_keeps(name, question, keep_pref)
        ]
    if focus_names is not None and allowed_tools is None and _picture_in_hand(question, notes):
        focus_names = [name for name in focus_names if name not in _CANVAS_TOOLS]
    return focus_names


def _fit_toolboxes(
    session: Session,
    question: str,
    history: list[dict] | None,
    tier,
    budget,
    offered: list[dict],  # noqa: ANN001
    unoffered: set[str] | frozenset[str],
) -> tuple[list[dict], list[dict]]:
    """The tools this turn offers, and the wider set a miss widens to, each fitted to the window."""
    # What the turn widens to if the model reaches for something it was not
    # shown (the correction below). For a small model that is the ordinary
    # question-focused set, **not** the whole registry: the narrowing above
    # is a judgement about the model rather than a guess about the
    # question, so a miss is evidence the focus was wrong, not evidence
    # that a 3B can suddenly choose between twenty-two schemas.
    every_tool = tools.with_relation_types(
        tools.ollama_tools(_focus(question, history) if tier.narrow_toolbox else None),
        session,
    )
    if unoffered:
        every_tool = [t for t in every_tool if t["function"]["name"] not in unoffered]
    if budget is not None and budget.window_tokens <= SMALL_WINDOW_TOKENS:
        every_tool = tools.compact_schemas(every_tool)
    keep = tools.keep_first_for(question)
    exempt = _plan_exempt(question)
    chances = dict(tools.rank_tools(question, _recent_text(history)))
    every_tool, _ = tools.within_budget(every_tool, budget.tool_schema_chars, keep, exempt, chances)
    offered, dropped = tools.within_budget(offered, budget.tool_schema_chars, keep, exempt, chances)
    if dropped:
        # Visible in Settings, Logs, because "the AI didn't use the tool I
        # expected" is otherwise indistinguishable from the model choosing
        # not to. Each name carries the chance the question gave it.
        logging.getLogger("tessellate.agent").info(
            "%s (%d-token window)",
            tools.ranking_line([t["function"]["name"] for t in offered], dropped, chances),
            budget.window_tokens,
        )
    return offered, every_tool


def _composition_tokens(messages: list[dict], offered: list[dict]) -> dict[str, int]:
    # Roadmap §11a's prescribed first step: measure before cutting. One line
    # per turn saying what the prompt is made of, so "which half dominates a
    # real chat: the notes or the history?" is answered from the log rather
    # than argued about. Chars, not tokens: the ratio is what matters, and
    # the true token counts already arrive in each round's stats event.
    system_chars = len(messages[0]["content"])
    history_chars = sum(len(m["content"]) for m in messages[1:-1])
    notes_chars = len(messages[-1]["content"])
    tool_schema_chars = len(json.dumps(offered))
    logging.getLogger("tessellate.agent").info(
        "prompt composition: system=%d history=%d notes+question=%d "
        "tool_schemas=%d chars (%d tools offered)",
        system_chars,
        history_chars,
        notes_chars,
        tool_schema_chars,
        len(offered),
    )
    # §88.4 item 4's next step past the log line above: the same breakdown,
    # as a rough token estimate (chars/4: the same approximation
    # ai/context.py's own budgeting uses), attached to the first round's
    # stats event so the UI's metadata line can show it rather than it
    # being visible only in Settings -> Logs. Measured once, here, before
    # the loop below appends any tool-result rounds to `messages`, a
    # later round's true composition would need re-measuring inside the
    # loop, which this does not attempt; the first round is also the one
    # every turn actually has, tool calls or not.
    return {
        "system": system_chars // context.CHARS_PER_TOKEN,
        "history": history_chars // context.CHARS_PER_TOKEN,
        "notes": notes_chars // context.CHARS_PER_TOKEN,
        "tool_schemas": tool_schema_chars // context.CHARS_PER_TOKEN,
    }


def _round_limits(max_rounds: int, earned_rounds: int, tier) -> tuple[int, int]:  # noqa: ANN001
    # Rounds are granted, then earned (see EARNED_ROUNDS). `allowance` is what
    # this turn has so far; a round that does something new adds one to it, up
    # to `ceiling`. A turn that loops never adds anything and stops where the
    # flat cap always stopped it.
    granted = max(1, max_rounds)
    ceiling = granted + max(0, earned_rounds)
    if tier.max_rounds is not None:
        # The cap is on the ceiling as well as the grant, or the earned rounds
        # put the total straight back to twelve: see SMALL_MODEL_MAX_ROUNDS.
        granted = min(granted, tier.max_rounds)
        ceiling = min(ceiling, tier.max_rounds)
    return granted, ceiling


def _first_toolbox(
    session: Session, question: str, focus_names, tier, budget, barred: set[str]
) -> tuple[list[dict], set[str]]:  # noqa: ANN001
    offered = tools.with_relation_types(tools.ollama_tools(focus_names), session)
    # Tools this turn may not use whatever it was offered. The one caller is a
    # run refusing to start another run (`tools.RUN_STARTERS`): each run brings
    # its own fresh rounds, so nesting them means the bound on a turn stops
    # meaning anything, and the plan on screen stops describing what is
    # happening. Withdrawn from the wire *and* refused below, because a model
    # that calls a tool it was never offered must not get it either.
    #: The web tools a first-person question does not need are only left off
    #: the wire (audit 1030 A3); a call a model makes anyway is judged as before.
    unoffered = barred | tools.web_barred(question)
    if unoffered:
        offered = [t for t in offered if t["function"]["name"] not in unoffered]
    # On a small window, trim the descriptions even when the full set would
    # fit. `within_budget` compacts only once the schemas overflow their share,
    # which is the right rule for a large model, but on an 8k window the
    # focused set measured 4,827 chars against a 7,901-char allowance, so it
    # "fits" and is sent in full, spending 1,206 tokens where 996 does the same
    # job. Affordable is not the same as wise: what the allowance leaves unspent
    # is what the notes and the conversation get, and on a small model those are
    # exactly what runs out first.
    #
    # Safe for a skill's declared list too (hence above the `allowed_tools`
    # branch): compaction never removes a tool, so nothing a skill asked for
    # can go missing this way.
    if tier.compact_schemas or (budget is not None and budget.window_tokens <= SMALL_WINDOW_TOKENS):
        offered = tools.compact_schemas(offered)
    return offered, unoffered


def _prepare_turn(
    session: Session,
    question: str,
    notes: list[dict],
    model_manager: ModelManager,
    ollama: OllamaClient,
    *,
    style: str,
    profile: str,
    history: list[dict] | None,
    persona_prompt: str | None,
    allowed_tools: list[str] | None,
    blocked_tools: frozenset[str] | set[str] | None,
    max_rounds: int,
    earned_rounds: int,
    mode: str | None,
    use_utility_model: bool,
    images: list[str] | None,
    model_override: str | None,
    image_context: str | None,
) -> _TurnPlan:
    """Stage one: decide everything the round loop will run on.

    Lifted whole out of `run_agent`, which the audit measured at 875 lines
    (WORLD_CLASS_PLAN A5). No behaviour is changed here and none may be: the
    existing agent tests are the only gate this split has, and they check the
    loop, so a stage that quietly reorders a decision would pass them.
    """
    # Size the whole turn against the window before building any of it.
    #
    # Every part used to carry its own constant, each reasonable alone and
    # never added up: the worst case came to ~11,300 tokens against a 4,096
    # window, and the tool-result cap alone exceeded that window by half.
    # Overflow is dropped from the FRONT, so the failure is not an error, it
    # is the model quietly losing its system prompt and answering from nothing.
    report = getattr(ollama, "usable_context", None)
    agent_model = model_override or (
        model_manager.utility_model() if use_utility_model else model_manager.chat_model()
    )
    window = report(agent_model) if callable(report) else None
    #: **How big the model is, asked about the model this turn will actually
    #: call** (WORLD_CLASS_PLAN A4). The window above and this are two
    #: different facts and the app had been using the first as a proxy for the
    #: second: a 3B served with a 32k window got the full registry, twelve
    #: rounds and the long descriptions, because the *window* was roomy. What
    #: the schemas cost is a window question; whether the model can choose
    #: between twenty of them is not.
    #:
    #: Read from `SIZE_TIERS` (H3), the one table every size decision below
    #: comes from; a name that gives no size is the large tier.
    tier = size_tier(agent_model)
    persona = memory.persona_with_memory(session, persona_prompt)

    system_chars = context.weighted_len(
        f"{persona} {AGENT_GROUNDING} {tools_guide(window)}{librarian.length_hint(mode)}"
    )
    budget = context.plan(window or OllamaClient.DEFAULT_CONTEXT_TOKENS, system_chars)
    logging.getLogger("tessellate.agent").info(budget.as_log_line())

    # Same fallback as librarian.answer()/converse(): a vision model's own
    # caption of an attached image, for when agent_model above can't see the
    # image itself: folded into the question text here rather than mutating
    # `question` in place, since later rounds of this same loop reuse it.
    full_question = f"{question}\n\n{image_context}" if image_context else question
    messages = build_agent_messages(
        full_question,
        notes,
        style=style,
        profile=profile,
        history=history,
        persona_prompt=persona,
        budget=budget,
        mode=mode,
        images=images,
    )
    focus_names = _focus_names(question, history, notes, allowed_tools, tier)
    barred = set(blocked_tools or ())
    offered, unoffered = _first_toolbox(session, question, focus_names, tier, budget, barred)
    # Then fit what is left to the window the model actually has, rather than
    # to a constant. See tools.within_budget: 4096 is Ollama's fallback, not a
    # fact, and a model declaring 32k was being rationed as if it were a 3B.
    # A skill's declared list is exempt, it asked for exactly those tools, and
    # silently dropping one would break the run rather than trim it.
    # --- the focus is a guess, and the model gets to overrule it ---------------
    #
    # `focus_for` reads the words of the question to decide which tools are
    # worth the room. It is deterministic and testable, and it is still a guess:
    # a request can want a tool whose name shares no word with it. So the guess
    # is never allowed to be final.
    #
    # Two mechanisms, and they are different things. The escape hatch already
    # existed: `permitted` is None on an ordinary turn, so a tool the model
    # calls anyway still runs even if it was never offered. What is added here
    # is the correction: a call for something unoffered is *evidence the focus
    # was wrong*, so the next round of this same turn gets the full toolbox
    # rather than the same narrow guess that already failed the model once.
    #
    # This is why the focus can afford to be narrow. A wrong guess costs one
    # round, not the request.
    focused_only = allowed_tools is None
    every_tool = offered
    # Say so, once, in the system prompt, but only when the list really was
    # narrowed. On a broad request the model already has everything, and a note
    # explaining that the list is partial would simply be false.
    if focused_only and focus_names is not None and messages:
        messages[0]["content"] += FOCUS_NOTE
    if allowed_tools is None:
        offered, every_tool = _fit_toolboxes(
            session, question, history, tier, budget, offered, unoffered
        )
    composition_tokens = _composition_tokens(messages, offered)
    if dropped := librarian.history_dropped(history, messages):
        composition_tokens["history_dropped"] = dropped

    granted, ceiling = _round_limits(max_rounds, earned_rounds, tier)
    return _TurnPlan(
        agent_model=agent_model,
        tier=tier,
        window=window,
        budget=budget,
        messages=messages,
        offered=offered,
        every_tool=every_tool,
        focused_only=focused_only,
        permitted=set(allowed_tools) if allowed_tools else None,
        barred=barred,
        composition_tokens=composition_tokens,
        granted=granted,
        ceiling=ceiling,
    )


@dataclass(slots=True)
class _TurnState:
    """The ledgers one turn carries from round to round.

    `_TurnPlan` above is what was decided before the turn started and never
    changes; this is everything the turn *learns* while it runs, and it is a
    record for one reason: the per-call stage below has to be able to write to
    all of it. Sixteen locals in a closure could do that too, and did, but only
    as long as the whole loop stayed inside `run_agent` (WORLD_CLASS_PLAN A5).

    The three that look alike are not, and mixing them up is how a real bug
    gets in: `done_calls` is the earned-round ledger and is never cleared;
    `fresh_reads` is a freshness cache and is emptied by any write;
    `failed_calls` is the repeat-suppression and outlives a write on purpose
    (a call that failed on its own arguments fails again for the same reason).
    """

    #: The conversation as the model will next see it. Tool results are
    #: appended here; the round loop appends the assistant's own turns.
    messages: list[dict]
    #: The tool schemas offered on the next round. Emptied when the tool-result
    #: budget runs out, which is what forces the round after that to answer.
    offered: list[dict]
    did_write: bool = False
    #: The person started this run with its writes listed (plan or skill): a
    #: change to existing text runs, a removal still parks (`needs_confirm`).
    approved: bool = False
    #: Which write tools ran, so a claim can be checked against the action that
    #: would have made it true rather than against the turn as a whole.
    ran_writes: set[str] = field(default_factory=set)
    #: Acts a write did on the side, for the claim check only: a note made
    #: with `tags` was tagged (H4, Qwen2.5-3B was told it had not been).
    implied: set[str] = field(default_factory=set)
    #: Characters of tool output added to the conversation so far.
    spent: int = 0
    #: (tool, arguments) pairs that have already failed.
    failed_calls: set[tuple[str, str]] = field(default_factory=set)
    #: How many times each tool has failed this turn, whatever the arguments.
    tool_failures: dict[str, int] = field(default_factory=dict)
    #: Destructive calls parked for the user's approval this turn, per tool.
    parked: dict[str, int] = field(default_factory=dict)
    #: Has this turn read something from outside the notebook (a page, a
    #: search result, a file)? Then reaching out again needs a confirm.
    outside: bool = False
    #: `outside` as it stood when this round's calls were chosen: what parks
    #: an outbound call. A call in the same reply as the first web read was
    #: decided before anything outside was read, so no page can have asked
    #: for it (INBOX 527: "search for X and Y" parked the second search).
    tainted: bool = False
    #: Calls that already succeeded: a repeat of one is not progress either.
    done_calls: set[tuple[str, str]] = field(default_factory=set)
    #: Reads whose result is already in `messages` and still current.
    fresh_reads: set[tuple[str, str]] = field(default_factory=set)
    #: Did this round do something new? Reset at the top of each round.
    progressed: bool = False
    #: SEC-02: the sites the person named, and the exact addresses this
    #: turn's searches returned (`_cleared_page`).
    named_hosts: set[str] = field(default_factory=set)
    result_pages: set[str] = field(default_factory=set)
    #: E66: the question, and the registry's card for every note an "all"
    #: delete names (worked out at the first delete; {} when there is none).
    asked: str = ""
    whole_card: dict | None = None

    def count_failure(self, tool_name: str) -> int:
        self.tool_failures[tool_name] = self.tool_failures.get(tool_name, 0) + 1
        return self.tool_failures[tool_name]


#: Below this much room a shortened result is too thin to answer from.
MIN_FITTED_CHARS = 400

#: Said inside a result that was shortened to fit (see `_fit_result`).
SHORTENED_NOTE = (
    "Shortened to fit what is left of this conversation: {what}. Answer from "
    "this; get_note reads one note in full if you need it."
)


def _clip_strings(value, limit: int):
    """`value` with every string over `limit` characters cut to it."""
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "…"
    if isinstance(value, dict):
        return {k: _clip_strings(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [_clip_strings(v, limit) for v in value]
    return value


def _shortened(result: dict, lists: list[str], limit: int, keep: int | None) -> dict:
    """`result` with long text clipped to `limit` and each list in `lists` kept to its first `keep` items, and a note saying what was cut."""
    shorter = _clip_strings(result, limit)
    dropped = 0
    if keep is not None:
        for key in lists:
            dropped += max(0, len(shorter[key]) - keep)
            shorter[key] = shorter[key][:keep]
    what = f"long text clipped to {limit} characters"
    if dropped:
        what += f", {dropped} item{'s' if dropped != 1 else ''} left out"
    shorter["shortened"] = SHORTENED_NOTE.format(what=what)
    return shorter


def _fit_result(result: dict, name: str, room: int) -> str | None:
    """The result as the model will read it, shortened to `room` characters
    if it must be, or None when no honest shortening fits (INBOX 527).

    Before, a result over the turn's budget was dropped whole and the tools
    withdrawn: on a 4k-window model one `search_notes` page of long notes
    could end the turn's reading with nothing read. Now its long text is
    clipped (400, then 160, then 60 characters) and then its lists kept from
    the front (10, 5, 3, 1 items), whole objects every time, with a note
    saying what was cut; only when one item does not fit is it refused.
    """
    payload = json.dumps(fence.fence_result(result, name))
    if len(payload) <= room:
        return payload
    if room < MIN_FITTED_CHARS or not isinstance(result, dict):
        return None
    lists = [k for k, v in result.items() if isinstance(v, list) and len(v) > 1]
    for limit in (400, 160, 60):
        for keep in (None, 10, 5, 3, 1):
            if keep is not None and not lists:
                break
            payload = json.dumps(fence.fence_result(_shortened(result, lists, limit, keep), name))
            if len(payload) <= room:
                return payload
    return None


def _prefetch_outbound(calls: list[dict]) -> None:
    """Fetch a round's web reads side by side, before they run one by one.

    **Parallel independent tool calls** (INBOX 527). A model that asks for
    three pages in one reply waited for them in series: three network
    round trips, each seconds, where the tool calls themselves are
    milliseconds. The calls still run in order through `_dispatch_call`,
    every guard and the session untouched; this only warms the in-process
    caches `websearch` already keeps, from threads that touch no database.
    Only for a round chosen before anything outside was read (the caller
    checks), so no page can start a fetch, and only when web access is on.
    """
    wanted = [
        c for c in calls if c.get("name") in _OUTBOUND_TOOLS and not c.get("invalid_arguments")
    ]
    if len(wanted) < 2:
        return
    tools.prefetch_web([(c["name"], c.get("arguments") or {}) for c in wanted])


#: An instruction to change the notebook, said as one: "Make a note: ...",
#: "Remind me ...", "Pin my ...". A question ("can you pin it?") is not one.
_IMPERATIVE = re.compile(
    r"^\s*(?:please\s+)?(?:make\s+a\s+note|note\s+down|jot\s+down|create|save|"
    r"remind\s+me|set\s+a\s+reminder|tag|untag|pin|unpin|link|unlink|rename|"
    r"add|append|put|write\s+down|file|move|mark)\b",
    re.IGNORECASE,
)


def _requires_a_call(question: str, plan: "_TurnPlan") -> bool:
    """Whether the first round of a small model's turn must be a tool call.

    INBOX 527, measured on Qwen2.5-1.5B under llama.cpp: asked "Make a note:
    buy oat milk and eggs", "Remind me tomorrow at 9am...", "Tag my plumber
    note", it answered in prose on most turns, sometimes claiming the work.
    Asked with `tool_choice: "required"`, the same server answered "Make a
    note" with `create_note {"content": "buy oat milk and eggs"}`. Only for an
    imperative whose own tools are on offer, never a question, never a
    skill's turn, and only the first round: what follows is the model's call.
    """
    text = (question or "").strip()
    if plan.permitted is not None or not text or text.endswith("?"):
        return False
    if not _IMPERATIVE.match(text):
        return False
    offered = {t["function"]["name"] for t in plan.offered}
    return bool(offered & _WRITE_TOOLS)


#: The reads a forced first round keeps: the ones that find the thing the
#: instruction names ("my dentist note", "the reminder to pay rent"). Every
#: other read is something a small model reaches for instead of acting.
_LOCATING_TOOLS = frozenset({"search_notes", "get_note", "list_notes", "list_reminders"})

#: A request for information, said as one: a wh-word, or an auxiliary with
#: its subject ("do I have", "is there", "are my"). "Can you pin it?" is a
#: request said as a question and is not matched: it keeps its writes.
_INFORMATION_QUESTION = re.compile(
    r"^\s*(?:(?:what|which|who|whom|whose|when|where|why|how)\b|"
    r"(?:is|are|am|do|does|did|have|has|was|were)\s+"
    r"(?:i|you|we|there|my|it|this|that|these|those|the|any)\b)",
    re.IGNORECASE,
)


#: The writes that change the category tree rather than a note.
_CATEGORY_TREE_TOOLS = frozenset(
    {"create_category", "rename_category", "merge_categories", "delete_category"}
)

#: "File the dentist note under Health", "move the plumber note to Home".
_FILING_REQUEST = re.compile(
    r"\b(?:file|filed|move|moved|recategori[sz]e|categori[sz]e)\b", re.IGNORECASE
)


def _names_an_existing_category(session: Session, question: str) -> bool:
    """Whether a filing request names a category the notebook already has.

    Qwen2.5-3B, forced: "File the dentist note under Health" opened once with
    `create_category` although "Health" existed; the note then stayed where it
    was. A narrowing is a hint and never a reason to fail a turn, so any
    trouble reading the categories (a test's stub session, a locked database)
    answers no and leaves the round as it was.
    """
    if not _FILING_REQUEST.search(question or ""):
        return False
    try:
        from tessellate.core.database import Category

        names = list(session.scalars(select(Category.name)))
    except Exception:  # noqa: BLE001
        return False
    return any(
        name and re.search(r"\b" + re.escape(name) + r"\b", question, re.IGNORECASE)
        for name in names
    )


def _forced_round_keep(question: str, session: Session | None) -> set[str]:
    """The tool names a forced first round keeps: the writes and the finders, less what the request makes wrong."""
    keep = _WRITE_TOOLS | _LOCATING_TOOLS
    #: "Put 'buy stamps' in my shopping note" names a note that exists:
    #: forced, the 3B made a new one instead (2 of 2). The edit and the
    #: finders stay; a new note is not what was asked.
    if tools.adds_to_a_named_note(question):
        keep = keep - {"create_note"}
    #: Filing under a category that exists is an edit of the note: leave
    #: out every tool that reshapes the category tree. The 3B picked
    #: `create_category` once, and on 2026-10-05 `rename_category {"old":
    #: "note 2", "new": "Health"}` (scratchpad/harness_probe.py).
    if session is not None and _names_an_existing_category(session, question):
        keep = keep - _CATEGORY_TREE_TOOLS
    return keep


def _first_round_tools(
    question: str,
    plan: "_TurnPlan",
    offered: list[dict],
    required: bool,
    session: Session | None = None,
) -> list[dict]:
    """The tools a small model's first round is offered (H4, measured on
    Qwen2.5-3B through llama-server).

    Forced, the round must call something, and a small model given the whole
    toolbox sometimes calls the harmless read: "Add X to my note" opened with
    `get_current_time`, "File the dentist note under Health" with
    `count_notes`. Forced rounds keep the writes and the reads that locate a
    note or a reminder, nothing else.

    Unforced, a question for information is offered no write: "What tags and
    what categories am I using?" opened with `tag_note`, because the word
    "tags" cues the tag group. The writes come back on the next round, so a
    question that turns into a job ("which note is about boots? pin it") still
    gets them once it has read.

    Only a narrowed tier and only an ordinary turn: a skill declared its own
    list, and a large model was never measured choosing this badly.
    """
    if not plan.tier.narrow_toolbox or plan.permitted is not None:
        return offered
    if required:
        keep = _forced_round_keep(question, session)
        narrowed = [t for t in offered if t["function"]["name"] in keep]
    elif _INFORMATION_QUESTION.match(question or ""):
        narrowed = [t for t in offered if t["function"]["name"] not in _WRITE_TOOLS]
    else:
        return offered
    if len(narrowed) != len(offered):
        logging.getLogger("tessellate.agent").info(
            "first round: %s, %d of %d tools",
            "forced" if required else "question",
            len(narrowed),
            len(offered),
        )
    return narrowed or offered


def _round_stream(ollama, model, messages, offered, mode, required):
    """One round's stream, with `tool_choice="required"` when asked and the
    provider takes it (the OpenAI dialect); any other provider, or a test's
    fake, is called as it always was."""
    if required and offered:
        try:
            return ollama.chat_tools_stream(
                model, messages, offered, mode=mode, tool_choice="required"
            )
        except TypeError:
            pass  # a fake or provider without tool_choice: the plain call below
    return ollama.chat_tools_stream(model, messages, offered, mode=mode)


def _tool_event(name: str, arguments: dict, result: dict) -> dict:
    """The `tool` event for one finished call: what the chat's chip, the
    Sources panel, the live action line and `skill_runner` read. Lifted
    from `_run_and_record` (ARCH-22)."""
    return {
        "type": "tool",
        #: **The tool's own name.** The front end has always tried
        #: to read it (`SOURCE_TOOLS[event.tool || event.name]`,
        #: app.js) and it was never sent, so every web page and
        #: every file this app read was silently missing from the
        #: answer's Sources panel: a feature that could not have
        #: worked once.
        "tool": name,
        "label": result.get("label") or name,
        "ok": "error" not in result,
        #: A write that went through: the chat asks before Regenerate or
        #: Edit re-runs a turn that made a change (INBOX audit E2).
        "wrote": name in _WRITE_TOOLS and "error" not in result,
        "error": result.get("error"),
        #: Why it failed, when a front end acts on the cause (`searxng_down`).
        **({"reason": result["reason"]} if result.get("reason") else {}),
        "arguments": arguments,
        #: Titles, addresses and one line each of what was read,
        #: see `_tool_sources`. This is what the Sources panel
        #: draws its cards, previews and links from.
        "sources": _tool_sources(name, result),
        # UI display only: the version fed back to the model as
        # conversation context is `payload` below, with its own
        # separate, real token budget (`result_cap`). This is just
        # what the chat transcript's tool-call disclosure shows,
        # and that box already scrolls (.tool-chip-result, 12rem
        # max-height): 300 chars cut it down to a couple of
        # lines for no reason tied to cost. Reported live: "make
        # the tool call output view a scrollable text box rather
        # than it being truncated", the box already was one;
        # this is what was starving it. 4000 is generous enough
        # that raw JSON from a typical note/search/fetch result
        # reads in full, while still bounding a pathological
        # single result (a huge page fetch) from bloating the
        # SSE event.
        "result_summary": _result_summary(result),
        # What this call actually touched, for the chat's live
        # action line: see `_touched_items`.
        "touched": _touched_items(result),
        #: **The ids this read returned, and whether there are
        #: more pages of them** (Brief 13; CHAT_PLAN decision 10).
        #: A paging read already tells the *model* there is more
        #: (`note_to_model`, `next_offset`); nothing told the
        #: *app*, so `skill_runner` could only see that a tool had
        #: been called once and ticked the step off with four
        #: fifths of the notebook unread. Read off the result here
        #: rather than parsed back out of `result_summary` in the
        #: runner: the shape is this module's to know, and a
        #: regex over a truncated JSON blob is the version of this
        #: that breaks silently.
        "seen": _seen_ids(result),
        "more": bool(result.get("has_more")),
        "next_offset": result.get("next_offset"),
        #: **The same call, as things with actions** (PLAN.md §4
        #: A1). `touched` is notes and documents; this is all five
        #: kinds: a file, a board and a reminder are equally
        #: openable and had no representation at all. Kept beside
        #: `touched` rather than replacing it because a saved
        #: transcript from before this existed has only `touched`,
        #: and `skill_runner._absorb` reads it to carry ids across
        #: a run's steps.
        "cards": cards.result_cards(name, result),
    }


def _tool_events(event: dict, result: dict) -> Iterator[dict]:
    """The tool's chip, then the card it asks the chat to draw beside it."""
    if result.get("proposal"):
        # `save_user_preference` no longer saves anything: it asks.
        # The row exists but is inactive and flagged `proposed`, and
        # it stays out of every system prompt until somebody says
        # yes. Carrying the id and the text on the event is what
        # lets the chat draw the accept/decline card next to the
        # tool chip, so the answer is given where the suggestion was
        # made rather than three clicks away in Settings.
        event["proposal"] = result["proposal"]
    yield event
    if result.get("act_card"):
        #: A model's act (`propose_act`, decision 53): the registry's own card,
        #: drawn as a typed act's is, waiting for Confirm; nothing ran.
        yield result["act_card"]


def from_outside(notes: list[dict]) -> bool:
    """SEC-02: a note retrieved for the question that was clipped from the web,
    imported or pasted from mail is already in the prompt, so the turn starts tainted."""
    return any(isinstance(n, dict) and n.get("from_outside") for n in notes or ())


def _whole_card(session: Session, asked: str, now) -> dict:  # noqa: ANN001
    """The registry's card for an "all" delete ("delete all notes about
    gym"), when it names more than one note; {} otherwise."""
    from tessellate.ai import act_registry

    if not asked or act_registry.proposer is None:
        return {}
    parsed = act_registry.typed_reader(asked, now)
    if not parsed or parsed.get("intent") != "delete" or parsed.get("single") is not False or not parsed.get("about"):
        return {}
    card = (act_registry.propose(session, asked, now) or {}).get("card") or {}
    ids = {(s.get("arguments") or {}).get("note_id") for s in card.get("steps") or () if s.get("name") == "delete_note"} - {None}
    return {"card": card, "ids": ids, "sent": False} if len(ids) > 1 else {}


#: What replaces a reply that claimed an act no tool ran, above the act's own card.
CLAIMED_ACT_LINE = "That is not done yet. Confirm the card below and it will be."


def claimed_act_events(session: Session, state: _TurnState, called_any: bool, answer: str, now) -> list[dict]:  # noqa: ANN001
    """**A claimed act with no call is the act's own card** (L114, qwen2.5-1.5b: "Make a board
    called Launch" answered "I've created a new board", no tool call). When the sentence is an act
    the registry reads (the reader the no-model path uses) and the reply claims a write nothing
    ran, the card waits for Confirm in place of the claim: [answer_final, card]. [] otherwise."""
    from tessellate.ai import act_registry

    if called_any or state.did_write or not state.asked or act_registry.proposer is None:
        return []
    if not (unsupported_claims(answer, state.ran_writes | state.implied) or claims_a_write(answer)):
        return []
    card = (act_registry.propose(session, state.asked, now) or {}).get("card")
    return [{"type": "answer_final", "text": CLAIMED_ACT_LINE}, card] if card else []


def all_it_names(session: Session, state: _TurnState, name: str, arguments: dict, now) -> tuple[dict, list[dict]] | None:  # noqa: ANN001
    """**"Delete all" is every match, on one card** (audit 1028 E66). A model
    asked to delete all notes about a thing queued the one best match, and the
    rest were quietly left. A delete of a note the person's "all" names parks
    the registry's own card for every match instead (Confirm, then Undo); a
    second delete of one of them is already on it. `now` is the plan clock."""
    if name != "delete_note":
        return None
    if state.whole_card is None:
        state.whole_card = _whole_card(session, state.asked, now())
    whole = state.whole_card
    try:
        note_id = int(arguments.get("note_id"))
    except (TypeError, ValueError):
        return None
    if not whole or note_id not in whole["ids"]:
        return None
    if whole["sent"]:
        return AWAITING_CONFIRMATION, []
    whole["sent"] = True
    state.did_write = True
    state.ran_writes.add(name)
    state.parked[name] = state.parked.get(name, 0) + 1
    return AWAITING_CONFIRMATION, [whole["card"]]


def _cleared_page(state: _TurnState, name: str, arguments: dict) -> bool:
    """Whether a `read_url` in a tainted turn opens without a card."""
    if name != "read_url":
        return False
    page = _page_key(str(arguments.get("url") or ""))
    if page is None:
        return False
    if page in state.result_pages:
        return True
    host = _bare_host(urlsplit("https://" + page).hostname or "")
    return host in state.named_hosts
