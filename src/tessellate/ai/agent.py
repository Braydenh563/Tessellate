"""The agent loop: the chat model can act on the notebook.

Flow: offer the tool registry to Ollama → run whatever it calls → feed
the results back → repeat (bounded) → its final text is the answer.
Yields NDJSON-ready event dicts; the chat route just serialises them.

Safety lives here and in tools.py: destructive calls are never executed
in this loop: a "confirm" event goes to the UI instead, and the model
is told the action is waiting on the user.
"""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import urlsplit
from collections.abc import Iterator
from datetime import datetime
from dataclasses import dataclass, field
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import act_registry, budget as run_budget, cards, context, fence, librarian, memory, source_check, tools
from tessellate.ai.model_manager import SMALL_MODEL_PARAMS_B, ModelManager, parameter_count
from tessellate.ai.ollama_client import (
    OllamaClient,
    OllamaError,
    ToolsUnsupportedError,
)
from tessellate.ai.provider import tools_unsupported_message
from tessellate.search.snippet import clip_words

# A runaway model must not loop forever on a local machine.
MAX_ROUNDS = 6

#: The whole allowance, granted plus earned, for a model under
#: `model_manager.SMALL_MODEL_PARAMS_B` (WORLD_CLASS_PLAN A4).
#:
#: Six granted plus six earned is twelve chances to go wrong, and a 3B that
#: has not finished the job in four rounds is not finishing it in twelve: what
#: it is doing by then is re-reading what it already read, and each of those
#: rounds costs a whole prompt on a machine where a prompt is seconds. The
#: number is the same four the skills reform settled on for the same models
#: and the same reason. Nothing is capped for a model the name does not size:
#: see `is_small_model`, where None means off.
SMALL_MODEL_MAX_ROUNDS = 4

#: Below this many billion parameters a model is "tiny" (H3): the 1.5B the
#: harness was measured on, against the 3B to 8B the small rules were made for.
TINY_MODEL_PARAMS_B = 3.0


class SizeTier(NamedTuple):
    """What a turn asks of a model of one size (AGENT_SKILLS_REFORM H3)."""

    name: str
    #: The core tools plus the ones the request names, never the orchestration
    #: three, in place of the question-focused set.
    narrow_toolbox: bool
    #: The short schema descriptions whatever the window.
    compact_schemas: bool
    #: The whole allowance, granted plus earned; None leaves the caller's.
    max_rounds: int | None
    #: `tool_choice: "required"` on an instruction's first round.
    force_first_call: bool
    #: Characters of prose a round with tools offered may write before its
    #: stream is closed; None never cuts. Prose only: thinking is not counted.
    reply_chars: int | None


#: **The one place a size decision lives** (H3; before, one boolean under 8B).
#: Measured on Qwen2.5-1.5B through llama-server: "Make a note" wrote the note
#: out in prose for 948 s, to the 2,048-token reply cap, and made no call.
#: 2,400 characters is about 600 tokens, three Normal-mode answers; a round
#: that meant to call a tool has said what it will say long before that. The
#: 3B to 8B tier gets twice the room. A name that gives no size is treated as
#: large: narrowing a capable model on a guess is the worse mistake.
SIZE_TIERS = {
    "tiny": SizeTier("tiny", True, True, SMALL_MODEL_MAX_ROUNDS, True, 2_400),
    "small": SizeTier("small", True, True, SMALL_MODEL_MAX_ROUNDS, True, 4_800),
    "large": SizeTier("large", False, False, None, False, None),
    "unsized": SizeTier("unsized", False, False, None, False, None),
}


def size_tier(model: str) -> SizeTier:
    """The tier for the model a turn will actually call, read off its name."""
    size = parameter_count(model)
    if size is None:
        return SIZE_TIERS["unsized"]
    if size < TINY_MODEL_PARAMS_B:
        return SIZE_TIERS["tiny"]
    return SIZE_TIERS["small" if size < SMALL_MODEL_PARAMS_B else "large"]


#: Said after a tool round's prose was cut at its tier's `reply_chars`.
REPLY_CAP_NOTE = "…\n\n(I cut that reply short: it was running long.)"

# Rounds a turn can *earn* beyond MAX_ROUNDS, one per round that got somewhere.
#
# **Reported, repeatedly:** *"the agent struggles with long tasks like skills,
# then cuts out half way through and has to restart, or it hits a limit for
# tool calls which has happened quite a bit."* A flat six is the whole cause of
# the second half, and it binds on exactly the requests the app is for: "tag
# these eight notes" costs one search, a read and eight writes, and the model
# is cut off after six with the work half done and a note saying so.
#
# The flat cap was never really measuring "runaway", it was counting rounds,
# and a model doing steady useful work spends rounds for the same reason a
# looping one does. What separates them is whether anything *new* happened: a
# round in which at least one tool call succeeded and was not a repeat of one
# already made this turn is progress, and it buys one more round. A model
# calling `search_notes` with the same arguments for the fourth time earns
# nothing and still stops at MAX_ROUNDS.
#
# So the ceiling is `MAX_ROUNDS + EARNED_ROUNDS` and it is only reachable by a
# turn that did twelve distinct, successful things, which is a long job, not a
# loop. A loop still stops at six.
EARNED_ROUNDS = 6

# How much of a round's own reasoning is carried into the next one.
#
# Asked for directly, and the reasoning behind the number: a plan is worth a
# paragraph, not a page. Carrying the whole of a thinking model's output would
# double the prompt every round, the thing §11a exists to prevent, and the
# part that stops the model re-deriving its plan is the plan, which is short.
# What gets clipped is the end, because a reasoning trace states its
# conclusion last only when it is finished; here it was interrupted by a tool
# call, so the useful half is the beginning.
THINKING_CARRIED_CHARS = 700

#: Sent after a round that produced neither text nor a tool call (see the
#: loop's `nudged_empty`). Says both ways forward, since either may be right.
EMPTY_ROUND_NUDGE = (
    "Your last reply was empty. Answer my previous message now, in plain words, "
    "or call the one tool that does what I asked."
)

#: Sent after a forced first round (`tool_choice: "required"`) that still came
#: back as prose. Measured at 3B (H4): the server's grammar did not always
#: hold, and a reply that neither claimed nor announced an act was taken as
#: the turn's answer, so the request was never done.
FORCED_PROSE_NUDGE = (
    "That request needs a tool call, and your reply made none. Call the one "
    "tool that does what I asked now."
)

#: Sent, with the tools withdrawn, when a turn runs out of rounds (see the end
#: of `run_agent`): what it found is worth an answer even if the job is not done.
WRAP_UP_NUDGE = (
    "You have used all your tool calls for this turn. Answer my request now, "
    "from what your tool results above show. Say plainly what you did and "
    "what is still not done. Do not claim anything you did not do."
)

#: H1: the rows of the plan card a multi-step turn draws (see `_TurnCard`).
TURN_ROW_RUNNING = "Deciding the next step"
TURN_ROW_ANSWER = "Wrote the answer"
TURN_ROW_RECHECK = "Rechecked the reply"
TURN_ROW_WRAP_UP = "Answered from what was found"
_ROW_ICON = re.compile(r"^(?:ph:[\w-]+|\u21a9\ufe0e)\s+")
_ROW_CHARS = 120
_TITLE_CHARS = 60


class _TurnCard:
    """**A plan card for every multi-step turn** (AGENT_SKILLS_REFORM H1).

    The tracker used to draw only for `make_plan` and skills, and a small model
    is never offered `make_plan`, so a turn that searched, read and answered
    showed tool rows and no sense of where it was. The card is drawn from the
    harness's own ledger when the second round starts (no model call): one row
    per round, the calls it made, ticked as it ends. It emits the same `plan`
    and `step` events a skill run does, marked `kind: "turn"`, so the client
    reuses `startPlan` and saves and replays it like any other card.
    """

    def __init__(self, question: str, enabled: bool):
        self.enabled = enabled
        title = " ".join(question.split())
        self.title = title if len(title) <= _TITLE_CHARS else title[: _TITLE_CHARS - 1].rstrip() + "…"
        self.rows: list[str] = []
        self.drawn = False
        self.open: int | None = None

    def start_round(self, called_any: bool) -> list[dict]:
        if not self.enabled or not called_any:
            return []
        events = []
        if not self.drawn:
            self.drawn = True
            events.append(
                {
                    "type": "plan",
                    "kind": "turn",
                    "skill": self.title,
                    "steps": list(self.rows),
                    "states": {str(i): {"state": "done"} for i in range(len(self.rows))},
                }
            )
        self.open = len(self.rows)
        events.append(self._step("running", TURN_ROW_RUNNING))
        return events

    def end_round(self, text: str, state: str = "done", reason: str | None = None) -> list[dict]:
        """Close this round's row. Before the card is drawn, only remembered."""
        if not self.enabled:
            return []
        text = text if len(text) <= _ROW_CHARS else text[: _ROW_CHARS - 1].rstrip() + "…"
        if not self.drawn:
            self.rows.append(text)
            return []
        index = len(self.rows) if self.open is None else self.open
        self.rows[index:index + 1] = [text]
        self.open = None
        event = self._step(state, text, index)
        if reason:
            event["reason"] = reason
        return [event]

    def _step(self, state: str, text: str, index: int | None = None) -> dict:
        index = self.open if index is None else index
        return {"type": "step", "kind": "turn", "index": index, "state": state, "text": text}

    @staticmethod
    def row_for(labels: list[str]) -> str:
        names = [_ROW_ICON.sub("", label).strip() for label in labels if label]
        row = ", ".join(dict.fromkeys(n for n in names if n)) or "Used a tool"
        return row[:1].upper() + row[1:]


def _check_sources(answer: str, messages: list[dict], wanted: bool):
    """H2: flag a number or a name the answer states that nothing this turn
    read contains (`source_check`). Only after a tool ran, so the answer is
    meant to be from the notebook, and only on an ordinary chat turn: a
    skill step's prose is checked by the run's own verify block."""
    if not wanted or not answer.strip():
        return
    claims = source_check.unbacked_claims(answer, source_check.sources_from_messages(messages))
    if claims:
        yield {"type": "answer", "delta": source_check.heads_up(claims)}


def _labelled(gen, labels: list[str]):
    """Re-yield a `_dispatch_call` generator, noting each tool row's label."""
    try:
        event = next(gen)
        while True:
            if event.get("type") == "tool" and event.get("label"):
                labels.append(str(event["label"]))
            event = gen.send((yield event))
    except StopIteration as stop:
        return stop.value


#: Sent once after a reply that claims an act no tool performed (see
#: `unsupported_claims` and the end of a round in `run_agent`).
CLAIM_RETRY_NUDGE = (
    "You wrote that you {claims}, but no tool ran, so it has not happened. "
    "Do it now by calling {tools}, or say plainly that it was not done."
)

#: Sent after a round whose words only announce an action ("I'll count the
#: notes in Work", "I will use the count_notes function") and that called no
#: tool (see `announces_unacted_tool`). Measured with Qwen2.5-1.5B through
#: llama.cpp in the popup agent (INBOX 432): every one of four prompts ended
#: on such a sentence, so each read as answered and none was.
UNACTED_INTENT_NUDGE = (
    "You said what you would do but did not do it. Do it now: call the tool "
    "instead of describing it. If no tool fits, answer my question in plain words."
)

#: "I'll", "I will", "I am going to", "let me", followed by a verb a tool
#: does. Verbs, not every verb: "let me know", "I'll keep that in mind" are
#: answers.
_INTENT_PATTERN = re.compile(
    r"\b(?:I(?:'ll|\u2019ll| will| am going to|'m going to| shall)|let me)\s+"
    r"(?:now\s+|first\s+|just\s+|go ahead and\s+)?"
    r"(?:use|call|run|count|search|look|find|check|create|make|add|tag|move|file|"
    r"list|fetch|read|open|update|edit|delete|remove|save|write|rename|link|get)\b",
    re.IGNORECASE,
)

#: Past this length a reply is an answer that happens to offer more, not an
#: announcement standing in for one.
_INTENT_MAX_CHARS = 400

#: What makes an announced act an offer ("if you like", "would you") or the
#: answer itself ("I'll list them below").
_CONDITIONAL = re.compile(
    r"\b(?:if|would|could|want|wish|prefer|should|below|above|following)\b", re.IGNORECASE
)


def announces_unacted_tool(answer: str, offered: list[dict]) -> bool:
    """Whether a reply with no tool call only says it is about to act.

    True for a short reply that names one of the tools on offer, or that says
    "I'll" / "let me" and a verb a tool does. False with nothing on offer,
    since then there is nothing to nudge the model toward.
    """
    text = (answer or "").strip()
    if not text or not offered:
        return False
    if len(text) > _INTENT_MAX_CHARS:
        #: **A long reply counts when one of its sentences announces an act
        #: outright** (INBOX 527, Qwen2.5-1.5B): asked "Make a note: buy oat
        #: milk", it wrote the note out as markdown, said "I will call the
        #: tool to save the note for you", and called nothing. A promise with
        #: a condition ("I'll search for more if you like") is an offer, and a
        #: long answer making one is still an answer.
        return any(
            _INTENT_PATTERN.search(sentence) and not _CONDITIONAL.search(sentence)
            for sentence in re.split(r"[.!?\n]+", text)
        )
    names = {t.get("function", {}).get("name", "") for t in offered}
    if any(name and re.search(rf"\b{re.escape(name)}\b", text) for name in names):
        return True
    return bool(_INTENT_PATTERN.search(text))


# How much tool output one turn may add to the conversation, in characters.
# Local models run in small windows, and tool results accumulate: six rounds
# of paging through a large notebook will push the question itself out of
# context, and the model then answers something nobody asked. The per-call
# caps in tools.py bound one result; this bounds the whole turn.
#
# Characters, not tokens, on purpose, a real tokeniser would mean loading one
# per model just to count, and ~4 chars/token is close enough for a stop rule.
#
# **A ceiling now, not the budget.** As the only rule it was the single worst
# offender in the overflow this app was reported to hit: 24,000 characters is
# ~6,000 tokens, half again more than a 4,096-token window holds *on its own*,
# before the system prompt, the tools, the notes or the question. The real
# allowance is `context.plan(...).tool_result_chars`, a share of the window
# actually available; this caps that share from above, because a 128k model
# would otherwise be handed tens of thousands of tokens of tool output and pay
# to re-read all of it on every later round.
TOOL_RESULT_BUDGET_CHARS = 24_000

BUDGET_EXHAUSTED = {
    "error": "context_budget_reached",
    "note": (
        "You have read as much of the notebook as fits in this conversation. "
        "No more tool results will be added. Answer now using what you already "
        "have, and tell the user plainly that you looked at part of their "
        "notes rather than all of them."
    ),
}

# The system prompt is resent in full on every round of every turn, alongside
# the tool schemas: see PROSE_BUDGET_CHARS below for why that matters more
# than it looks. Everything here earned its place by fixing an observed
# failure, so it is not padding; but anything that is *also* said by a tool
# schema or by a tool result is padding, and has been cut.
TOOLS_GUIDE = (
    "You can use tools to act on the notebook, create, edit, tag, pin, "
    "link, or delete notes, and manage reminders. Only make changes the "
    "user actually asked for; when they just ask a question, answer it "
    "without tools. "
    "The notes quoted below are only what search found for this question, "
    "they are NOT the whole notebook. To see more: count_notes to answer "
    "'how many', list_categories / list_tags to see what exists, list_notes "
    "to walk through notes, get_note to read one in full. Never state a "
    "total from a page of results, count_notes is the only thing that knows "
    "the real number. "
    # Was two clauses saying the same thing ("not available to you at all" /
    # "say you can't see private notes"). One says it; the saving paid for the
    # traversal sentence below, which is a capability the model otherwise
    # never reaches for.
    "Private notes are invisible to you; say so if asked about one. "
    # §9, and the §21 finding that decided it: a small model reaches for a tool
    # when the instruction *names* it. Without this the structural tools sit
    # unused and "tidy my notebook" gets answered from category names, which
    # describe the filing and say nothing about how the notes relate.
    "For how two notes relate, path_between; for the notebook's shape: "
    "clusters, hubs, notes joined to nothing, notebook_structure. "
    "You can also reach the user's long-form documents (list_documents / "
    "get_document: never searched automatically, so go and look when a "
    "question is about something they wrote up, and create_document to write "
    "a new one: where an essay or report belongs, not in a note), their "
    "earlier conversations "
    "with you (search_chat_history, for when they refer to something 'we "
    "talked about' that isn't in this thread, say when you're relying on "
    "it), and their saved skills (list_skills, save_skill; run_skill starts "
    "one and takes over from you, so use it when a saved skill already "
    "describes the job). "
    # The arithmetic left the prompt (INBOX 527; AGENT_SKILLS_REFORM, decided
    # 2026-09-21): set_reminder takes the user's words in `when` and the app
    # resolves them (`ai/when.py`). This only says so.
    "For \"remind me… in 10 minutes / tomorrow at 9\", call set_reminder "
    "with when in the user's own words; the app works out the date. "
    # Both halves of this earned their place and both were briefly cut. Without
    # the first the model acts and then says nothing, so the user watches tool
    # chips scroll past and gets no answer; without the second it narrates work
    # it never did. They are opposite failures and the pair is the fix.
    "After acting, tell the user briefly what you did. NEVER say you created, "
    "saved, edited, deleted, tagged, linked or unlinked anything unless you "
    "called the tool: \"we linked…\" is claiming it just as much as \"I "
    "linked…\", and a list of work you did not do is the worst thing you can "
    "write. Planning is fine: say it in the future tense, then call the tools. "
    # Asked for directly: "I need agents to use tools more and better if they
    # are required." The loop already allows several rounds; nothing told the
    # model that using them was expected rather than a failure to answer
    # promptly, so it tended to answer from the first page of search results.
    "Taking several turns is normal and expected: look something up, read "
    "what you found, look up anything still missing, then answer. Do not "
    "rush to an answer while something you were asked about is still "
    "unchecked. "
    # §35K: "I will say fix my categories and it will only merge two categories
    # and leave it at that." Short because the schema carries the rest, this
    # is only here because the *trigger* is a property of the request, and the
    # model has to be told to look for it.
    "If a request covers many notes, make_plan first. "
    # It under-used read_url badly: a result snippet is a sentence, and the
    # model treated it as the page.
    "A web search result is a title and one clipped sentence, enough to "
    "choose a page, never enough to answer from. Call read_url on a result "
    "that matters before relying on it, and name the sites you actually read. "
    # It re-narrated the step timeline the user was already watching.
    "The user can already see which tools you ran, in order. Do not narrate "
    "your process back to them ('let me search…', 'I will now check…'), just "
    "do it, then give the answer. "
    # Reported: "I don't know what 'Note #12' is when the ai refers to it."
    # Ids are the app's handle, not the user's: nothing in the interface shows
    # one, so a bare id names a note the user has no way to identify.
    "Users never see note ids: name a note by a few of its own words (\"your "
    "gym routine note\"), not \"note 28\". "
    # Screenshotted: a bullet reading "Jokes $\rightarrow$ Social Skills".
    # The renderer translates the common escapes now, but not writing them is
    # cheaper than translating them.
    "Write symbols plainly (→ × ≤), never as LaTeX. "
    "If a tool fails, its result carries a 'what_to_do' field. Follow it. "
    "Never repeat a call that has just failed in exactly the same way."
)

#: The window below which a model gets `COMPACT_TOOLS_GUIDE` instead. Same
#: threshold `tools.SMALL_WINDOW_CHARS` uses for holding back orchestration
#: tools, expressed in tokens: below this, the fixed cost of the prompt is the
#: thing squeezing out the notes, and the guide is the largest fixed piece.
SMALL_WINDOW_TOKENS = 8_192

#: The load-bearing half of TOOLS_GUIDE, for a model that cannot afford the
#: whole thing.
#:
#: Measured on a real turn: TOOLS_GUIDE is 2,807 characters, about 700 tokens
#:, and it is re-sent on **every round** of an agent loop. On a 4k-window
#: model that is 17% of the entire context spent, per round, on static prose,
#: which is a large part of the reported *"agent mode and chats are too heavy
#: for small models and have a too small context window"*.
#:
#: What is kept is what a model gets *wrong* without being told, and what
#: cannot be recovered from: claiming work it never did, treating a page of
#: search results as the whole notebook, quoting note ids at the user, and
#: repeating a call that just failed. What is dropped is elaboration the tool
#: schemas already carry: which tool to reach for is in each tool's own
#: description, and a small window is exactly the case where saying it twice
#: is unaffordable.
#:
#: Deliberately not a truncation of the constant above: a guide cut at 1,100
#: characters would lose the honesty rule, which sits at the end and is the one
#: sentence in this file that most needs to survive.
COMPACT_TOOLS_GUIDE = (
    "You can use tools to act on the notebook. Only make changes the user "
    "actually asked for; answer plain questions without tools. "
    "The notes quoted below are only what search found, NOT the whole "
    "notebook. Use count_notes for totals, list_notes to walk through, "
    "get_note to read one in full. Never state a total from a page of "
    "results. Private notes are invisible to you; say so if asked. "
    "For reminders, pass when in the user's own words. "
    "NEVER say you created, saved, edited, deleted, tagged or linked "
    "anything unless you actually called the tool, claiming work you did "
    "not do is the worst thing you can write. Planning ahead is fine: say "
    "it in the future tense, then call the tools. "
    "Taking several turns is normal: look something up, read it, then "
    "answer. Do not narrate ('let me search…'), just do it, then answer. "
    "Name a note by its own words, never 'note 28'. Write symbols plainly "
    "(→ × ≤), never as LaTeX. If a tool fails, follow its 'what_to_do' "
    "field, and never repeat a call that just failed the same way."
)


#: Appended when the tool list was narrowed by reading the question's words.
#:
#: The narrowing is a guess made from wording, and a guess the model is
#: entitled to disagree with, asked for directly: *"if the program detects
#: words and suggests that specific tools or skills might need to be used, and
#: the AI thinks that's wrong then it doesn't have to use them"*.
#:
#: It already may. `permitted` is None on an ordinary turn, so a tool the model
#: names runs whether or not it was in the list, and reaching past the list
#: widens it for the rest of the turn (see the focus-correction block in the
#: round loop). What was missing was the model being *told* that, without it,
#: a well-behaved model treats the list as exhaustive, which is exactly the
#: behaviour that makes a narrow guess expensive.
#:
#: One sentence, because it is on every round of every focused turn, and it
#: is appended to the system message, joining the clock in its volatile tail
#: (see build_agent_messages): narrowed-or-not is decided per turn, so this
#: can never be part of the prefix-cached head wherever it is put.
FOCUS_NOTE = (
    " The tools listed were picked from the wording of the request and are a "
    "suggestion, not a limit: if the right one is not there, call it by name "
    "anyway, and ignore any that do not fit."
)


def tools_guide(window_tokens: int | None) -> str:
    """The tool guide sized to the window, see COMPACT_TOOLS_GUIDE.

    ``None`` means the window is not known yet, which is the safe case for the
    long guide: an unknown window is usually a provider that did not report
    one, not a tiny one.
    """
    # `<=`, so an 8k model is included rather than sitting just outside. At 8k
    # the fixed prompt measured 32% of the window before a single turn of
    # history; at 16k the same prompt is 16%, which is a budget rather than a
    # squeeze. 8k is the last size that needs the help.
    if window_tokens is not None and window_tokens <= SMALL_WINDOW_TOKENS:
        return COMPACT_TOOLS_GUIDE
    return TOOLS_GUIDE


# What the model is handed before a single word of the question, the notes or
# the history, the system prompt plus every tool schema, resent on each of
# up to MAX_ROUNDS rounds.
#
# This is the number that decides whether the agent is usable on the 3B-class
# models people actually run here (granite4.1:3b, llama3.2:3b, qwen3.5:2b).
# Ollama defaults to a 4096-token window unless a model says otherwise, so at
# ~4 chars per token this overhead alone can be most of it, and everything
# past the limit is silently dropped from the *front*, which is the system
# prompt, so a model that overflows stops knowing it has tools at all.
#
# It is asserted rather than noted because it drifts upward invisibly: every
# tool added and every sentence added to the guide costs the same budget, and
# nothing else in the codebase would notice. When this needs raising, raise it
# deliberately and say why here.
#
# 13,000 → 13,800, for the four category tools (§14). The guard did its job:
# adding them took the all-tools overhead straight past the old figure, and
# the first version of those schemas, with a per-parameter description on
# each, matching the older tools, went past the *window* too. They were
# rewritten terse (no "old: the current name" when the field is called `old`)
# and now cost 1,112 characters between them.
#
# **This is now a backstop, not the mechanism.** It was briefly the binding
# constraint on §14's tool list, "room for about one more tool, then none" , 
# which was the wrong shape of answer, because the ceiling it described was
# never a fact about the app. 4096 is what Ollama falls back to when a model
# declares nothing; most current models declare 8k, 32k or far more.
#
# `tools.within_budget` now fits the schemas to the window the model actually
# reports (`ollama_client.usable_context`), dropping the least relevant tools
# when they do not fit and logging what it held back. So a 32k model gets the
# whole registry, a genuine 3B at 4096 gets a prioritised subset, and adding a
# tool is no longer a question of whether it fits inside a constant.
#
# What this number still does is catch the *prose* growing, the system prompt
# and TOOLS_GUIDE are sent whatever the window, and no per-turn trimming
# applies to them. If it trips, look at what was added to the guide before
# reaching for the number.
#
# 13,800 → 14,400, for `ask_user` (§33). The guard did its job again, and the
# useful part was *how* it tripped: the registry was sitting at 13,743 of
# 13,800, so it would have fired on whoever added the next tool, whatever it
# was. The first version of the schema was 784 characters of prose explaining
# when to ask; it was cut to 507 by keeping only the two rules that stop it
# being misused (stop after asking, don't ask what you could look up) and
# deleting the rest. `ask_user` is in CORE_TOOLS, so unlike most tools it is
# paid for on every single turn, which is exactly why it had to be terse.
#
# 14,400 → 15,000, for `related_notes` (§9). Second raise in one session, and
# that pattern is worth naming rather than repeating silently: **this number
# was measuring the wrong thing.** It weighed the *whole* registry, and no turn
# has sent the whole registry since `within_budget` started fitting the schemas
# to the model's real window: a 4k model receives about 1,450 tokens of it, a
# 32k model receives all of it and has ample room. So what tripped was not "the
# prompt is too heavy for a small model" but "the registry grew again", which
# is a thing that is *supposed* to happen.
#
# **Retired at that point, exactly as the note above it said to.** It asked for
# retirement if it ever needed raising a third time for a *tool* rather than
# for prose: and the third time came in the same session, for one added
# argument on `save_skill`. A guard that has to be raised every time the app
# grows is not a guard; it is a chore that teaches people to edit the number.
#
# What replaces it is two assertions that each measure something real:
#
#   - `PROSE_BUDGET_CHARS` below: the persona and TOOLS_GUIDE, which are sent
#     whatever the window and are *never* trimmed. This is the half the old
#     constant measured honestly, and the half that can still quietly bloat.
#   - `test_prompt_budget.test_the_overhead_leaves_room_for_an_actual_
#     conversation`, what actually reaches a 4,096-token model *after* the
#     trim. That is the number that decides whether a 3B model works.
#
# The tool registry is deliberately no longer capped by a constant. It is
# capped by the model's real window, per turn, by code that is tested.

# The un-trimmable half. Every character here is resent on every round of every
# turn, before the question, the notes or the history, and unlike the tool
# schemas, nothing fits it to the window. If this trips, something was added to
# TOOLS_GUIDE or the persona; look there rather than at the number.
#: 3,000 until 2026-09-23, raised by the default persona's growth alone
#: (librarian.DEFAULT_PERSONA, the owner's ask for a character): nothing else
#: may spend it.
PROSE_BUDGET_CHARS = 3_200

#: Re-exported so the constant keeps resolving from `agent` for anything that
#: already reads it there. It lives in `ai/memory.py` now, next to the code
#: that enforces it.
MEMORY_STREAM_BUDGET_CHARS = memory.MEMORY_STREAM_BUDGET_CHARS

# What to do about a failed tool call.
#
# A failure used to be handed to the model as a bare `{"error": "..."}` and
# nothing else. Small models do one of two things with that: give up and
# apologise, or call the identical thing again, and again, until MAX_ROUNDS
# runs out and the user gets "I stopped after using several tools in a row"
# having been told nothing. Neither is a reasonable response to, say, a
# mistyped note id.
#
# The error now travels with a recovery instruction. The wording is
# deliberately concrete about the *next call to make*, because "try something
# else" is exactly the advice a small model cannot act on.
_RECOVERY_HINTS = {
    "unknown_tool": (
        "That tool does not exist. Do not call it again. Use one of the tools "
        "you were given, or answer without tools."
    ),
    "disabled": (
        "The user has turned this tool off in Settings. Do not call it again. "
        "Tell them it is off and what turning it on would let you do."
    ),
    "not_found": (
        "Nothing exists with that id. Do not guess another id. Call "
        "search_notes (or list_notes) to find the real one, then retry with "
        "the id that search returned."
    ),
    "arguments": (
        "The arguments were wrong. Read the tool's schema again and retry "
        "once with corrected arguments. If you cannot work out what it wants, "
        "stop calling it and tell the user what you were trying to do."
    ),
    "web_off": (
        "Web access is off in Settings. Do not retry. Answer from the "
        "notebook, and say that a web lookup would need turning on."
    ),
    "web_down": (
        "The web could not be reached from here. Do not retry or rephrase the "
        "search. Answer from the notes you already have, or tell the user the "
        "web is unreachable and what to check in Settings, Web search."
    ),
    "generic": (
        "That call failed. Do not repeat it unchanged. Either retry once with "
        "different arguments, try a different tool, or tell the user plainly "
        "what failed and answer with what you already have."
    ),
    "not_in_skill": (
        "This skill does not include that tool. Use only the tools listed for "
        "the run, or finish and tell the user what the skill could not do."
    ),
    "already_running": (
        "You are already inside a run that is working through steps, you "
        "cannot start another one from in here. Do this step with the tools "
        "you have, and the next step will get its own turn."
    ),
    "empty_result": (
        "That search or list returned nothing. Do not repeat the same call. "
        "Try a different, broader search term, or tell the user you couldn't find it."
    ),
    "timeout": (
        "That tool call took too long and was aborted. Do not retry it right now. "
        "Tell the user the operation timed out and they may need to try again later."
    ),
    "rate_limited": (
        "The model or service is currently rate limited. Stop making tool calls "
        "and tell the user they are being rate limited."
    ),
}


#: Failure phrases and the advice each earns, first match wins; the tables
#: sit either side of the checks in `_recovery_hint`.
_HINTS_FIRST = ((("not part of this skill",), "not_in_skill"),)
_HINTS_MID = (
    (("turned off in settings",), "disabled"),
    (("web search is disabled",), "web_off"),
    (("rate limit", "too many requests", "429"), "rate_limited"),
)
_HINTS_AFTER = (
    (("timeout", "timed out"), "timeout"),
    #: "nothing found" and "returned nothing" are about the *search*; "empty" on
    #: its own is not, and matching it here sent "the note body is empty", an
    #: argument mistake the model can fix, down the "it isn't there, stop
    #: looking" path. Match the phrases that mean an empty result, not the word.
    (("nothing found", "returned nothing", "no results"), "empty_result"),
    (("not found", "no note", "no such"), "not_found"),
)


def _hint_in(table: tuple, lowered: str) -> str | None:
    return next((_RECOVERY_HINTS[key] for phrases, key in table if any(p in lowered for p in phrases)), None)


def _recovery_hint(name: str, message: str) -> str:
    """Pick the advice that fits this failure."""
    lowered = message.lower()
    found = _hint_in(_HINTS_FIRST, lowered)
    if found:
        return found
    if lowered.startswith("unknown tool"):
        return _RECOVERY_HINTS["unknown_tool"]
    found = _hint_in(_HINTS_MID, lowered)
    if found:
        return found
    #: A search or page service that failed is not an argument fault: the
    #: tool's own "no URL was given" is (audit 1030 A5).
    if name in ("web_search", "read_url") and not any(m in lowered for m in ("was given", "is required", "required", "must be")):
        return _RECOVERY_HINTS["web_down"]
    found = _hint_in(_HINTS_AFTER, lowered)
    if found:
        return found
    # ValueError/KeyError/TypeError from a handler are argument problems, and
    # execute_tool prefixes those with the tool's own name.
    if lowered.startswith(f"{name}:"):
        return _RECOVERY_HINTS["arguments"]
    return _RECOVERY_HINTS["generic"]


REPEATED_CALL_NOTE = (
    "You have already made this exact call and it failed the same way. "
    "Calling it a third time will not help. Change the arguments, use a "
    "different tool, or stop and tell the user what you could not do."
)

# How many times one tool may fail in a turn, with *any* arguments, before
# it is taken away for the rest of that turn. See `tool_failures` in
# `run_agent` for the logged loop this exists for. Three is deliberate: two
# failures is a model correcting itself, which is the behaviour the recovery
# hints are there to produce and worth allowing; a third means it is not
# converging and every further round is spent, not invested.
#: What the chat transcript's tool disclosure shows when a tool did not write
#: its own `summary`.
#:
#: Reported with a screenshot: "tools render fine in the chat initially but
#: then I come back to them after reloading the app later and they look like
#: this", rows reading `Listed your categories{'categories': [{'name':
#: 'Games', 'notes': 3}], 'total_notes': 27, 'label': 'ph:folders Listed your
#: categories'}`. That is Python's `repr` of the result dict, which is what
#: the fallback here used to be: single quotes, `True`/`False`, no line
#: breaks, and the app's own display `label` repeated inside the body of the
#: row whose heading already is that label.
#:
#: JSON instead, indented, for three reasons: it is the format the arguments
#: block directly above it in the same disclosure already uses
#: (`JSON.stringify(args, null, 2)`), so the two halves stop looking like they
#: came from different programs; it is what the tool actually returned over
#: the wire; and it wraps at field boundaries instead of running as one line.
#: `label` is dropped because it is presentation the row has already shown,
#: and `default=str` keeps a stray datetime from turning the whole disclosure
#: into an error.
#:
#: 4000 is unchanged and deliberate, see the note at the call site: the box
#: it lands in already scrolls (`.tool-chip-result`, 12rem), so this only
#: bounds a pathological single result from bloating the SSE event.
RESULT_SUMMARY_CHARS = 4000


def _result_summary(result: dict) -> str:
    """A tool's result as the transcript shows it."""
    summary = result.get("summary")
    if summary:
        return str(summary)
    body = {k: v for k, v in result.items() if k != "label"}
    try:
        text = json.dumps(body, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        # A result that will not serialise is still worth showing.
        text = str(body)
    if len(text) > RESULT_SUMMARY_CHARS:
        return text[:RESULT_SUMMARY_CHARS] + "…"
    return text


#: **What a tool call actually touched, as things the reader can open.**
#:
#: Asked for: "is it also possible to have live action lines show on the chat
#: ui, to show and visually show as the ai accesses specific notes, files and
#: stuff??"
#:
#: The transcript already said *that* a tool ran and, in a disclosure, what it
#: returned as JSON. What it could not say is *which note*, and a note id in a
#: blob of JSON is not something a person can act on, the same complaint that
#: produced the palette's note links.
#:
#: Read from the tool's own result rather than from the arguments it was called
#: with. Arguments are what the model *asked for*, which may be wrong, may be a
#: search string rather than an id, and may name a note the call then refused.
#: The result is what happened. A tool that touched nothing contributes
#: nothing, which is why this returns a list and the UI omits the row when it
#: is empty.
#:
#: Capped, because a `list_notes` over a big notebook would otherwise put fifty
#: chips under one row and bury the answer beneath its own evidence.
TOUCHED_LIMIT = 6


def _touched_kind(candidate: dict) -> str | None:
    """Which kind of thing a result row is, or None if it is not one.

    **The order matters and is the whole correctness of this function.** A
    document result carries `id`, `title` *and* `content` (see
    ai/tools/documents.py), so a check for `content` alone calls a document a
    note: and the UI would then open the *note* with that id, which is a
    different object entirely, or nothing at all. `title` is what only a
    document has; `content` is what a note has and a document also has. So
    document is tested first, and note is the fallback.
    """
    if "title" in candidate:
        return "document"
    if "content" in candidate:
        return "note"
    return None


def _touched_items(result: dict) -> list[dict]:
    """What a tool result names, as {kind, id, label} for the transcript."""
    if not isinstance(result, dict):
        return []
    rows: list[dict] = []
    seen: set[tuple[str, int]] = set()

    def _take(candidate: object) -> None:
        if len(rows) >= TOUCHED_LIMIT or not isinstance(candidate, dict):
            return
        item_id = candidate.get("id")
        if not isinstance(item_id, int):
            return
        kind = _touched_kind(candidate)
        if kind is None or (kind, item_id) in seen:
            return
        seen.add((kind, item_id))
        # A document is known by its title; a note has none, so its opening
        # words stand in for one, the same thing `noteLabel` shows in a list.
        source = candidate.get("title") if kind == "document" else candidate.get("content")
        label = " ".join(str(source or "").split())[:60]
        rows.append({"kind": kind, "id": item_id, "label": label or f"{kind} #{item_id}"})

    # The single-item shape (`get_note`, `edit_note`, `read_document`) is the
    # result itself; the many-item shapes nest under a handful of stable keys.
    _take(result)
    for key in ("notes", "documents", "results", "matches", "linked", "created"):
        value = result.get(key)
        if isinstance(value, list):
            for item in value:
                _take(item)

    #: **A mind map, which is named by `board_id` and not by `id`.**
    #: MINDMAP_PLAN.md §5 item 12 asks for a map chip in the chat transcript,
    #: and without this the four map tools contributed *nothing* to it:
    #: `read_mindmap`, `create_mindmap`, `add_map_node` and `link_map_nodes`
    #: all return `board_id` (plus `board_title` or `title`), so `_take`'s
    #: `candidate.get("id")` found no id and the row was dropped, a turn that
    #: read a whole map showed a bare tool name and no way to open it.
    #:
    #: Read here rather than by teaching `_take` about a second id field: `id`
    #: means "a note or a document" everywhere else in this function, and a
    #: board id in that space would be opened as a note by the front end,
    #: which is the exact confusion `_touched_kind`'s own comment is about.
    board_id = result.get("board_id")
    if isinstance(board_id, int) and len(rows) < TOUCHED_LIMIT:
        title = result.get("board_title") or result.get("title") or ""
        label = " ".join(str(title).split())[:60] or f"map #{board_id}"
        if ("map", board_id) not in seen:
            seen.add(("map", board_id))
            rows.append({"kind": "map", "id": board_id, "label": label})
    return rows


#: How many ids one read may contribute to a run's `seen_ids` (Brief 13).
#: Generous where `TOUCHED_LIMIT` is deliberately mean: `touched` draws chips
#: in the transcript, where six is already a crowd, while this is the run's
#: own ledger of what it has actually looked at, and the whole point of paging
#: a notebook is that the number is larger than one page. Ints only, so the
#: cost of carrying the full page is a few dozen bytes on the event.
SEEN_LIMIT = 500


def _seen_ids(result: dict) -> list[int]:
    """Every note id one read returned, in order, without the chip cap.

    **Why this is not `touched`.** `_touched_items` is the transcript's list
    and stops at six, which is right for a row of chips and wrong for the one
    question a paging step has to answer: *have I now seen all of them?* A
    step told to look at every note used to have no way to know, because the
    only record of what a page contained was capped at a quarter of a page.
    """
    if not isinstance(result, dict):
        return []
    ids: list[int] = []
    seen: set[int] = set()

    def _take(candidate: object) -> None:
        if len(ids) >= SEEN_LIMIT or not isinstance(candidate, dict):
            return
        item_id = candidate.get("id")
        # Notes only: an id here is read back as a note id by the state line
        # and by every id-targeting tool, and a document id in that space
        # names a different object entirely (see `_touched_kind`).
        if not isinstance(item_id, int) or item_id in seen or "title" in candidate:
            return
        if "content" not in candidate:
            return
        seen.add(item_id)
        ids.append(item_id)

    _take(result)
    for key in ("notes", "results", "matches", "linked", "created"):
        value = result.get(key)
        if isinstance(value, list):
            for item in value:
                _take(item)
    return ids


#: How many web/file sources one tool call may contribute to the answer's
#: Sources panel. Five is what `web_search` itself asks the engine for.
SOURCE_LIMIT = 8

#: How much of a result's own text stands in as a preview. Long enough to tell
#: whether the source is the one you want, short enough that eight of them do
#: not become a second answer under the answer.
SOURCE_SNIPPET_CHARS = 220


def _tool_sources(name: str, result: dict) -> list[dict]:
    """The pages and files one read-only call actually consulted, as
    ``{title, url, snippet}`` rows for the chat's Sources panel.

    Reported: *"improve the ui of the sources… what is shown about the
    sources, dropdown previews, hyperlinks etc."* The panel could not show any
    of that, because none of it was ever sent: a tool event carried a prose
    label and a bounded `result_summary` blob, so the front end had a sentence
    where it needed a title, an address and a line of the page.

    Read-only tools only. A write tool's result is a change, and changes are
    already carried by `change`/`touched`, a source is something the answer
    *drew on*.
    """
    if not isinstance(result, dict) or "error" in result:
        return []
    rows: list[dict] = []

    def _clip_text(value: object) -> str:
        return clip_words(value, SOURCE_SNIPPET_CHARS)

    if name == "web_search":
        for hit in (result.get("results") or [])[:SOURCE_LIMIT]:
            if not isinstance(hit, dict):
                continue
            rows.append(
                {
                    "title": _clip_text(hit.get("title")) or str(hit.get("url") or ""),
                    "url": str(hit.get("url") or ""),
                    "snippet": _clip_text(hit.get("snippet")),
                }
            )
    elif name == "read_url":
        rows.append(
            {
                "title": _clip_text(result.get("title")) or str(result.get("url") or ""),
                "url": str(result.get("url") or ""),
                "snippet": _clip_text(result.get("text")),
            }
        )
    elif name in {"read_file", "search_files"}:
        matches = result.get("matches") or result.get("results") or []
        if isinstance(matches, list) and matches:
            for hit in matches[:SOURCE_LIMIT]:
                if not isinstance(hit, dict):
                    continue
                rows.append(
                    {
                        "title": _clip_text(hit.get("path") or hit.get("name")),
                        "url": "",
                        "snippet": _clip_text(hit.get("snippet") or hit.get("text")),
                    }
                )
        elif result.get("path") or result.get("name"):
            rows.append(
                {
                    "title": _clip_text(result.get("path") or result.get("name")),
                    "url": "",
                    "snippet": _clip_text(result.get("text") or result.get("content")),
                }
            )
    #: A row with nothing to say is not a source. Dropping it here keeps the
    #: "is there anything to show" test in the front end a length check.
    return [row for row in rows if row["title"] or row["url"]]


MAX_TOOL_FAILURES = 3

# How many confirm cards one destructive tool may put in front of the user in
# a single turn. See the `parked` check in `run_agent`.
MAX_PARKED_CONFIRMS = 2

TOOL_EXHAUSTED_NOTE = (
    "This tool has now failed several times in this turn with different "
    "arguments, so it has been switched off for the rest of this turn. Do "
    "not call it again, you will get this same message. Either do the job "
    "with a different tool, or stop now and tell the user plainly what you "
    "were trying to do and what went wrong."
)


# Write tools whose absence makes a "I saved it" claim a lie (safety net).
# Defined in the registry, so the settings screen and the skill list can mark
# "this one changes things" from the same list rather than a second copy.
_WRITE_TOOLS = tools.WRITE_TOOLS

# Which key each note-touching write tool's own result carries the note's id
# under. Not "id" for all of them (`link_notes` says `linked`, `delete_note`
# says `deleted`) and not present at all for tools that touch something else
# entirely (`create_document`'s "id" is a *document* id).
#
# **Reported as "the agent does things that don't make sense":** a change
# event used to read `result.get("id")` unconditionally and call it
# `note_id`, so creating a document during a skill run produced a change
# whose "note_id" was really that document's id: the change list's own View
# button (§21/§22) would then take you to whatever note happened to share
# that id, or nowhere. `_change_note_id` only fills the field in for tools
# that actually touched a note, and reads it from the field that tool really
# uses.
_NOTE_ID_FIELD = {
    "create_note": "id",
    "edit_note": "id",
    "tag_note": "tagged",
    "pin_note": "id",
    "restore_note": "id",
    "link_notes": "linked",  # [source_id, target_id]: the note the call was made on
    "unlink_notes": "unlinked",
    "delete_note": "deleted",
}


def _change_note_id(name: str, result: dict) -> int | None:
    """The note this write actually touched, or None for a write that
    touched something else (a document, a reminder, a tag, a skill)."""
    field = _NOTE_ID_FIELD.get(name)
    if field is None:
        return None
    value = result.get(field)
    if isinstance(value, list):
        value = value[0] if value else None
    return value if isinstance(value, int) else None


# The document equivalent of `_NOTE_ID_FIELD` above: only `create_document`
# needs one: `delete_document` is destructive, so it never reaches this code
# path at all (it is parked for a confirm, not executed here).
_DOCUMENT_ID_FIELD = {"create_document": "id"}


def _change_document_id(name: str, result: dict) -> int | None:
    """The document this write actually created, or None otherwise. A
    sibling of `_change_note_id` for the same reason: a later skill step
    that needs to reference "the document I just wrote" is working from
    `step_history`, not from this turn's own tool results, so the id has to
    survive into the next step's context under a field that names what it
    actually is."""
    field = _DOCUMENT_ID_FIELD.get(name)
    if field is None:
        return None
    value = result.get(field)
    return value if isinstance(value, int) else None


# ROADMAP.md Tier 2 §13: reminders and categories had no `_change_*_id`
# resolver at all, so `changeRow`'s View button: built for notes and
# documents: had nothing to extend to. Both tools' own results already
# carry what's needed; this just names the field the same way the two
# resolvers above do.
_REMINDER_ID_FIELD = {"set_reminder": "id", "complete_reminder": "id"}


def _change_reminder_id(name: str, result: dict) -> int | None:
    """The reminder this write actually touched, or None otherwise."""
    field = _REMINDER_ID_FIELD.get(name)
    if field is None:
        return None
    value = result.get(field)
    return value if isinstance(value, int) else None


# Categories are identified by name, not id, every category tool's own
# arguments and results already work in names, so this names the field that
# carries the category a note ended up in rather than inventing an id
# nothing else uses. `delete_category` is destructive (like
# `delete_document`) and never reaches this code path, it's parked for a
# confirm card, not executed here.
_CATEGORY_NAME_FIELD = {
    "create_category": "name",
    "rename_category": "name",
    "merge_categories": "into",
}


def _change_category_name(name: str, result: dict) -> str | None:
    """The category this write actually created or landed notes in, or None
    otherwise."""
    field = _CATEGORY_NAME_FIELD.get(name)
    if field is None:
        return None
    value = result.get(field)
    return value if isinstance(value, str) and value else None

# --- claiming work that never happened -------------------------------------------
#
# The failure this catches is the one that costs the most trust, because the
# user has no way to see it: the model writes a confident list of what it did
# and calls no tool at all. A reported turn (§35B) narrated linking note 12 to
# three others and unlinking a fourth, having called `related_notes` once.
#
# That turn got past the original net twice over, and both gaps are worth
# naming because they are the shape of the next one:
#
# 1. The pattern only knew the first person singular, "I linked". The model
#    wrote "**Linked Notes:** We connected your main Social Skills Guide to…"
#    and "we" matched nothing.
# 2. It asked one question of the whole turn, "did *any* write run?", so a
#    turn that legitimately linked one pair and then claimed four more passed
#    on the strength of the one that was real.
#
# So claims are matched *per action* and checked against the tools that
# actually ran. That is §33's "completion verifier" in its cheap form: no
# second model round, just what was said against what was called.

#: Who the model says did it. Past and perfect only, "we could link these" is
#: a suggestion and must not be reported as a false claim.
_CLAIMANT = r"(?:i|we)(?:'ve)?\s+(?:have\s+|just\s+|now\s+|also\s+|then\s+|successfully\s+)*"

#: What was claimed, how it reads, and the tools that would make it true.
#: The label is written to be shown to the user, because a warning that says
#: *which* claim was unsupported is actionable where "something" is not.
_CLAIMED_ACTIONS: tuple[tuple[str, str, frozenset[str]], ...] = (
    (
        # `create_document` counts here too: "I wrote that up for you" is a
        # true claim when the document tool ran, and warning about it would be
        # the net crying wolf on work that really happened.
        "saved a note",
        r"(?:created|added|saved|made|wrote)",
        frozenset({"create_note", "create_document"}),
    ),
    ("edited a note", r"(?:edited|updated|rewrote|amended|revised)", frozenset({"edit_note"})),
    ("deleted a note", r"(?:deleted|removed|binned|trashed)", frozenset({"delete_note"})),
    (
        "tagged a note",
        r"(?:tagged|re-?tagged|labelled|labeled)",
        frozenset({"tag_note", "rename_tag"}),
    ),
    ("pinned a note", r"(?:pinned|unpinned)", frozenset({"pin_note"})),
    # Checked before "linked": \b keeps "linked" from matching inside
    # "unlinked", but the ordering makes that guarantee visible rather than
    # something a reader has to work out from the regex.
    (
        "unlinked notes",
        r"(?:unlinked|disconnected|detached)",
        frozenset({"unlink_notes"}),
    ),
    ("linked notes", r"(?:linked|connected)", frozenset({"link_notes"})),
    (
        "set a reminder",
        r"(?:set|scheduled|added)\s+(?:a|the|your)?\s*remind",
        frozenset({"set_reminder"}),
    ),
)

#: A verb carried on from an earlier subject: "I linked 12 to 13 **and
#: tagged** them both". Models write this constantly, and requiring an
#: explicit "I"/"we" in front of every verb missed the whole second half of
#: such a sentence. Only trusted once the answer has claimed something
#: outright somewhere: otherwise "the notes you tagged in March" would read
#: as a claim.
_CARRIED_ON = r"(?:and|then|,)\s+(?:also\s+|successfully\s+|later\s+)*"

_CLAIM_MATCHERS = tuple(
    (
        label,
        re.compile(rf"\b{_CLAIMANT}{verb}\b", re.IGNORECASE),
        re.compile(rf"\b{_CARRIED_ON}{verb}\b", re.IGNORECASE),
        needs,
    )
    for label, verb, needs in _CLAIMED_ACTIONS
)

#: **The passive voice** (INBOX 527, Qwen2.5-1.5B): asked to pin a note, it
#: created a duplicate instead and wrote "Your dentist appointment note has
#: been created and pinned". No "I", so nothing matched. Read only on a turn
#: that ran or parked some write, because "has been tagged" also describes a
#: note as it already is, and a heads-up on a plain answer would be the net
#: crying wolf; on a turn that changed something it is a report of that turn.
_PASSIVE = r"(?:has|have|is now|are now)\s+(?:now\s+|just\s+|also\s+)?(?:been\s+)?(?:successfully\s+)?"
_PASSIVE_MATCHERS = tuple(
    re.compile(
        r"\bremind\w*\s+(?:has|have|is|are)\s+(?:now\s+)?(?:been\s+)?(?:set|scheduled|added|created)\b"
        if label == "set a reminder"
        else rf"\b{_PASSIVE}{verb}\b",
        re.IGNORECASE,
    )
    for label, verb, _needs in _CLAIMED_ACTIONS
)

# Kept because it is the cheapest check for the commonest case, a model that
# describes a note it never saved, and it catches phrasings with no claimant
# at all. Widened from the original to cover "we" as well as "I".
_CLAIM_PATTERN = re.compile(
    rf"\b({_CLAIMANT}(?:created|added|saved|made|updated|edited|deleted|tagged|"
    r"pinned|linked)|new note titled|created a? ?note)\b",
    re.IGNORECASE,
)


#: **"Added" says which act by what it was added to** (Qwen2.5-3B,
#: 2026-10-05, `scratchpad/harness_probe.py`): "Pin my dentist note" ran
#: `pin_note` and answered "has been added to Favourites"; "added" read as a
#: saved note, the heads-up and a retry followed, and the turn ended
#: contradicting itself. Rewritten to the verb of the act before matching,
#: so the claim is still checked, against the tool that does it.
_ADDED_TO = (
    (re.compile(r"\b(?:added|moved)\b(?=[^.!?\n]{0,40}\bto\s+(?:your\s+|the\s+)?favou?rites\b)", re.I), "pinned"),
    (re.compile(r"\bremoved\b(?=[^.!?\n]{0,40}\bfrom\s+(?:your\s+|the\s+)?favou?rites\b)", re.I), "unpinned"),
    (re.compile(r"\b(?:added|removed|applied)\b(?=[^.!?\n]{0,30}\btags?\b)", re.I), "tagged"),
    (re.compile(r"\b(?:added|appended)\b(?=[^.!?\n]{0,60}\bto\s+(?:your|the|that)\s+[^.!?\n]{0,40}\bnote\b)", re.I), "updated"),
)


def unsupported_claims(answer: str, ran: set[str]) -> list[str]:
    """Actions the answer says happened that no tool call performed.

    `ran` is the write tools that actually executed this turn (or were parked
    for the user's approval, which is its own visible signal). A claim whose
    tool is in there is taken at face value, this is a net for fabrication,
    not an auditor of whether the right note was edited.
    """
    for pattern, verb in _ADDED_TO:
        answer = pattern.sub(verb, answer)
    # Whether this answer speaks in the claiming voice at all. A carried-on
    # verb is only a claim inside a sentence that already made one, so this is
    # checked first and gates the looser half of every matcher below.
    passive = [m.search(answer) if ran else None for m in _PASSIVE_MATCHERS]
    claiming = any(passive) or any(direct.search(answer) for _, direct, _, _ in _CLAIM_MATCHERS)
    said = []
    for (label, direct, carried, needs), by_passive in zip(_CLAIM_MATCHERS, passive):
        hit = direct.search(answer) or by_passive or (claiming and carried.search(answer))
        if hit and not (needs & ran):
            said.append(label)
    return said

# Agent-mode grounding: tool results are a legitimate second source.
AGENT_GROUNDING = (
    "Answer the user in plain English using ONLY the notes provided and "
    "your tool results. If neither answers the question, say so honestly. "
    + fence.FENCE_RULE
)

#: **Read from outside, then reaching out, asks first** (INBOX 430: "a web
#: page or file can't trigger destructive or outbound tools without the
#: person's confirm"). Destructive tools always park for a confirm. These
#: are the tools that bring in text nobody in the notebook wrote, and the
#: tools that send something out of this computer; once a turn has run one
#: of the first, every call to the second parks for a confirm too, so a
#: page that says "now search for my password" cannot make a request by
#: itself.
_OUTSIDE_TOOLS = frozenset({"read_url", "web_search", "read_file", "search_files"})
_OUTBOUND_TOOLS = frozenset({"read_url", "web_search"})
#: **What parks once the turn is tainted** (SEC-02, audit 2026-10-05): every
#: tool that reaches out *and* every tool that writes. Outbound alone left
#: the slower attack open: a page that cannot send the notebook anywhere
#: this turn could still plant a note or rewrite a saved skill (`save_skill`
#: replaces a skill's tool list in place) so that a later, clean turn does
#: the sending. Taint also comes from the notebook itself now: a note
#: clipped from the web or brought in by an import, and an imported
#: document, are text from outside however they reach the model (a tool
#: result's `from_outside`, or a retrieved note's, see `run_agent`).
_PARK_WHEN_TAINTED = _OUTBOUND_TOOLS | frozenset(_WRITE_TOOLS)

#: **Which pages a tainted turn may still open without a card** (SEC-02's last
#: step). Parking every `read_url` once outside text is in the turn stopped a
#: page sending the notebook anywhere, and made every research turn a stack of
#: cards. Two addresses carry nothing the model could have put there:
#: one the person named (its site, by their own choice), and the exact
#: address a search result gave this turn. Anything else, a query string
#: added, a longer path, a name that only ends like the site, still parks:
#: that is where a page smuggles data out.
#: The lookbehind is what keeps it linear: without it a match restarted at
#: every label of a dotted run (`a.a.a.` 16,000 long took 3.8 s, CodeQL's
#: `py/polynomial-redos`), and a host never starts inside another host.
_ADDRESS = re.compile(
    r"(?<![a-z0-9.\-])(?:https?://)?((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63})(?::\d+)?(/[^\s<>()\"']*)?",
    re.IGNORECASE,
)


def _page_key(url: str) -> str | None:
    """An address as compared: no scheme, no fragment, no trailing slash,
    the host lowercased. None when it names no host."""
    text = (url or "").strip()
    if not text:
        return None
    if "://" not in text:
        text = "https://" + text
    parsed = urlsplit(text)
    host = (parsed.hostname or "").lower()
    if not host:
        return None
    path = parsed.path.rstrip("/")
    return host + path + (f"?{parsed.query}" if parsed.query else "")


def _bare_host(host: str) -> str:
    host = host.lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def _hosts_named(question: str) -> set[str]:
    """The sites the person named in their own words."""
    return {_bare_host(m.group(1)) for m in _ADDRESS.finditer(question or "")}


def _result_urls(result) -> set[str]:  # noqa: ANN001
    """Every address a search result handed back, as page keys."""
    found: set[str] = set()

    def walk(value) -> None:  # noqa: ANN001
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("url", "link", "href") and isinstance(item, str):
                    page = _page_key(item)
                    if page:
                        found.add(page)
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(result)
    return found


def _cleared_page(state: "_TurnState", name: str, arguments: dict) -> bool:
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
    # The model needs "now" to turn "in 10 minutes" into a real time.
    from tessellate.core import deps
    from tessellate.core.config import user_now

    # The user's wall clock. This line is what "remind me in 10 minutes"
    # is computed from, so resolving it against the server's zone instead
    # puts every relative time out by the offset between them.
    from datetime import timedelta

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
        f"{day:%a} {day.day} {day:%b}"
        for day in (local + timedelta(days=n) for n in range(1, 8))
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
_ASK_RECOVERY = _HANDOFF_RECOVERY["ask_user"]  # kept: named in tests and §33

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
        "read_whiteboard", "search_whiteboard", "add_whiteboard_card", "add_whiteboard_link",
        "generate_diagram", "read_mindmap", "create_mindmap", "map_from_note", "add_map_node", "link_map_nodes",
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
        first in str(m.get("content") or "") for m in messages[1:] if m.get("role") in ("user", "tool")
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
    return (name not in tools.ORCHESTRATION_TOOLS or plan) and (keep_pref or name != "save_user_preference")


def _plan_exempt(question: str) -> frozenset[str]:
    """Orchestration tools a small window may not drop for this request."""
    return frozenset({"make_plan"}) if tools.asks_for_plan(question) else frozenset()


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
        f"{persona} "
        f"{AGENT_GROUNDING} {tools_guide(window)}{librarian.length_hint(mode)}"
    )
    budget = context.plan(
        window or OllamaClient.DEFAULT_CONTEXT_TOKENS, system_chars
    )
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
    # A skill's declared tools are the only ones offered for its run: fewer
    # schemas on the wire (roadmap §11a) and a narrower thing to go wrong.
    # An ordinary turn declares nothing, so the question is read for what it
    # plausibly needs: see tools.focus_for. Note the asymmetry: the skill's
    # list is also *enforced* below, while the focus is only an economy. A
    # tool left out because a cue didn't fire must still run if the model
    # somehow calls it.
    focus_names = (
        allowed_tools if allowed_tools is not None else _focus(question, history)
    )
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
    offered = tools.with_relation_types(tools.ollama_tools(focus_names), session)
    # Tools this turn may not use whatever it was offered. The one caller is a
    # run refusing to start another run (`tools.RUN_STARTERS`): each run brings
    # its own fresh rounds, so nesting them means the bound on a turn stops
    # meaning anything, and the plan on screen stops describing what is
    # happening. Withdrawn from the wire *and* refused below, because a model
    # that calls a tool it was never offered must not get it either.
    barred = set(blocked_tools or ())
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
            every_tool = [
                t for t in every_tool if t["function"]["name"] not in unoffered
            ]
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
                "%s (%d-token window)", tools.ranking_line([t["function"]["name"] for t in offered], dropped, chances), budget.window_tokens
            )
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
    composition_tokens = {
        "system": system_chars // context.CHARS_PER_TOKEN,
        "history": history_chars // context.CHARS_PER_TOKEN,
        "notes": notes_chars // context.CHARS_PER_TOKEN,
        "tool_schemas": tool_schema_chars // context.CHARS_PER_TOKEN,
    }

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
            payload = json.dumps(fence.fence_result(shorter, name))
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
    wanted = [c for c in calls if c.get("name") in _OUTBOUND_TOOLS and not c.get("invalid_arguments")]
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
_CATEGORY_TREE_TOOLS = frozenset({"create_category", "rename_category", "merge_categories", "delete_category"})

#: "File the dentist note under Health", "move the plumber note to Home".
_FILING_REQUEST = re.compile(r"\b(?:file|filed|move|moved|recategori[sz]e|categori[sz]e)\b", re.IGNORECASE)


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
        name and re.search(r"\b" + re.escape(name) + r"\b", question, re.IGNORECASE) for name in names
    )


def _first_round_tools(
    question: str, plan: "_TurnPlan", offered: list[dict], required: bool, session: Session | None = None
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
        narrowed = [t for t in offered if t["function"]["name"] in keep]
    elif _INFORMATION_QUESTION.match(question or ""):
        narrowed = [t for t in offered if t["function"]["name"] not in _WRITE_TOOLS]
    else:
        return offered
    if len(narrowed) != len(offered):
        logging.getLogger("tessellate.agent").info(
            "first round: %s, %d of %d tools", "forced" if required else "question", len(narrowed), len(offered)
        )
    return narrowed or offered


def _round_stream(ollama, model, messages, offered, mode, required):
    """One round's stream, with `tool_choice="required"` when asked and the
    provider takes it (the OpenAI dialect); any other provider, or a test's
    fake, is called as it always was."""
    if required and offered:
        try:
            return ollama.chat_tools_stream(model, messages, offered, mode=mode, tool_choice="required")
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


def _finish_handover(
    session: Session, plan: _TurnPlan, state: _TurnState, name: str, arguments: dict, handover: dict
) -> Iterator[dict]:
    """Hand the turn over; True when it ends.

    `propose_act` is the one handover whose card needs the session, so the
    handler runs here and the turn stops only when a card was drawn. A sentence
    the app does not read as an act goes back to the model as an ordinary error.
    """
    if handover.get("type") == "act_proposal":
        result = yield from _run_and_record(session, plan, state, name, arguments)
        return "error" not in result
    if handover.get("type") == "run_plan":
        #: The writes each step will make, on the card the person approves
        #: once (AGENT_SKILLS_REFORM "Deepened 2026-10-10" row 3).
        handover = {**handover, "writes": _plan_writes(session, handover["steps"])}
    yield handover
    return True


def _plan_writes(session: Session, steps: list[str], tools_too: bool = False) -> list[list[str]]:
    """Each step's writes (`ai/plan_writes.py`), or with `tools_too` the
    tools those writes need."""
    plans = _plans()
    return (plans.plan_tools if tools_too else plans.plan_writes)(session, steps, plan_now())


def plan_now() -> datetime:
    """The naive local time a plan's steps are read against (dates in a step
    such as "on Friday" resolve on the reader's clock)."""
    from tessellate.core import deps
    from tessellate.core.config import user_now

    return user_now(deps.get_config()).replace(tzinfo=None)


def _plans():  # noqa: ANN202
    """`ai/plan_writes.py` through the act registry's leaf (it imports this module)."""
    if act_registry.plans is None:
        raise RuntimeError("tessellate.ai.plan_writes is not imported, so no plan can be read")
    return act_registry.plans


def _change_diff(name: str, arguments: dict, undo: dict | None) -> dict | None:
    """An edit's lines out and in, drawn under its step (row 3's diff after)."""
    if name != "edit_note" or not isinstance(undo, dict) or "content" not in (arguments or {}):
        return None
    return _plans().edit_diff(str((undo.get("arguments") or {}).get("content") or ""), str(arguments["content"]))


def _count_call() -> None:
    """Charge one tool call to the run this turn belongs to, if any (Phase E)."""
    spend = run_budget.current()
    if spend is not None:
        spend.count_call()


def _query_said(name: str, arguments: dict) -> list[dict]:
    """A web search's words, said before they leave this computer (audit 1030 A2)."""
    query = str(arguments.get("query") or "")[:200] if name == "web_search" and isinstance(arguments, dict) else ""
    return [{"type": "status", "stage": "web", "query": query, "said": f"searching the web for “{query}”"}] if query else []


def _run_and_record(
    session: Session, plan: _TurnPlan, state: _TurnState, name: str, arguments: dict
) -> Iterator[dict]:
    """Run a call every guard let through, record what it did on the turn's
    state, yield its tool event, and return the result for the model.

    `_dispatch_call`'s last branch, lifted with no behaviour change (audit
    2026-10-05, ARCH-22: the function was 455 lines). The order inside is
    the branch's own: the taint, the ledgers, the write's change, the advice
    on an error, then the event.
    """
    spend = run_budget.current()
    if name in _WRITE_TOOLS and spend is not None and spend.stop_requested():
        #: Stop landed while the model was answering; the generator cannot be
        #: interrupted there, so the write it asked for is refused here
        #: instead of running before the next yield notices (Brief 101b).
        result = {"error": "Stopped before this ran: you pressed Stop."}
    else:
        yield from _query_said(name, arguments)
        result = tools.execute_tool(
            session, name, arguments, context_tokens=plan.window, model=plan.agent_model
        )
    _count_call()
    # SEC-02: the result carries a clipped or imported note's words (or an
    # imported document's): from here on the turn is tainted, exactly as
    # after a web read. Popped: the flag is for this loop, not the model.
    if isinstance(result, dict) and result.pop("from_outside", False):
        state.outside = True
    # What changed, and the call that would put it back. Popped
    # rather than read: `undo` is for the user, and every field
    # left in the result is resent to the model on every later
    # round of the turn.
    undo = result.pop("undo", None)
    change = None
    signature = (name, json.dumps(arguments, sort_keys=True))
    if "error" not in result and signature not in state.done_calls:
        # Something new worked. That is what buys another round, 
        # see EARNED_ROUNDS. Reads and writes both count: paging
        # through a notebook to find the right note is the work,
        # not a preamble to it.
        state.done_calls.add(signature)
        state.progressed = True
    if "error" not in result and name not in _WRITE_TOOLS:
        # Its result is now in the messages above, and stays valid
        # until something writes.
        state.fresh_reads.add(signature)
    if "error" not in result and name in _OUTSIDE_TOOLS:
        state.outside = True
    if "error" not in result and name == "web_search":
        state.result_pages |= _result_urls(result)
    if "error" not in result and name in _WRITE_TOOLS:
        state.did_write = True
        state.ran_writes.add(name)
        if name == "create_note" and arguments.get("tags"):
            state.implied.add("tag_note")
        # The notebook just changed, so every read taken before now
        # may be out of date. Clearing this is what keeps the
        # repeat-suppression above from ever serving a stale
        # answer: after a write, re-reading is legitimate work
        # rather than a loop, and it has to be allowed through.
        #
        # Deliberately *not* `done_calls`, which is the earned-round
        # ledger: clearing that would let a model repeating one
        # identical write buy a fresh round every time it did so,
        # which is the exact loop EARNED_ROUNDS exists to starve.
        #
        # Deliberately not `failed_calls` either, for the same
        # reason one step removed. A write briefly cleared it here,
        # which sounds symmetrical and is not: a call that failed on
        # its own arguments, a bad note id, a malformed date, fails
        # again for exactly the same reason after an unrelated note
        # is written, and forgetting it hands the model back the
        # infinite retry that `_RECOVERY_HINTS` and the repeat
        # interception exist to break. Only a read can go stale.
        state.fresh_reads.clear()
        change = {
            "tool": name,
            "label": result.get("label") or name,
            "diff": _change_diff(name, arguments, undo),
            "note_id": _change_note_id(name, result),
            "document_id": _change_document_id(name, result),
            "reminder_id": _change_reminder_id(name, result),
            "category_name": _change_category_name(name, result),
            "undo": undo,
        }
    if "error" in result:
        # Hand back advice with the error, not just the error.
        repeated = signature in state.failed_calls
        state.failed_calls.add(signature)
        exhausted = state.count_failure(name) >= MAX_TOOL_FAILURES
        result = {
            **result,
            "what_to_do": (
                # Said on the failure that *reaches* the cap, not
                # only on the blocked call after it, otherwise the
                # model spends one more round discovering a rule it
                # could have been told here.
                TOOL_EXHAUSTED_NOTE
                if exhausted
                else REPEATED_CALL_NOTE
                if repeated
                else _recovery_hint(name, str(result["error"]))
            ),
        }
    event = _tool_event(name, arguments, result)
    if change:
        event["change"] = change
    yield from _tool_events(event, result)
    return result


def _tidied_arguments(name: str, arguments: dict, messages: list[dict]) -> dict:
    """A call's one-line string arguments with stray keys off their edges
    (INBOX 808: a search logged as "a gaming mouse?\\"); multi-line text (a
    note's body, a document) is the person's content and is left alone. A
    search sent with no query is given the request's topic ("NOTEBOOK STATS"
    searched for nothing)."""
    if not isinstance(arguments, dict):
        return arguments
    from tessellate.ai import question_noise

    out = {k: question_noise.strip_strays(v) if isinstance(v, str) and "\n" not in v else v for k, v in arguments.items()}
    if name == "search_notes" and not str(out.get("query") or "").strip():
        asked = next((m.get("content") for m in reversed(messages) if m.get("role") == "user"), "")
        out["query"] = question_noise.topic_of(asked if isinstance(asked, str) else "") or out.get("query", "")
    return out


#: Told to the model when it asks with one choice (INBOX 808, the owner's
#: log: three one-option asks in a row, each "Couldn't ask user").
ONE_OPTION_NOTE = (
    "There is only one option, so there is nothing to ask. Do it now with the "
    "right tool, or answer. ask_user is not available for the rest of this turn."
)


def _one_option_ask(state: "_TurnState", name: str) -> bool:
    """A one-option ask is stopped before it reaches the person: no card and
    no failed step on screen, the model told to answer or act, and ask_user
    taken out of what it is offered for the rest of the turn, so it cannot
    loop on the same refusal. Still counted, so a model that calls it anyway
    meets the cap."""
    state.count_failure(name)
    state.offered = [t for t in state.offered if t.get("function", {}).get("name") != name]
    state.messages.append({"role": "tool", "tool_name": name, "content": json.dumps({"error": ONE_OPTION_NOTE})})
    return False


def _handoff_refused(state: "_TurnState", name: str, signature: tuple, exc: Exception) -> Iterator[dict]:
    """A malformed question, or a skill named that doesn't exist.
    Recoverable mistakes, not dead turns: hand the model the reason and let
    it try again or answer directly. An ask with one choice is not shown at
    all (INBOX 808: three "Couldn't ask user" steps in a row)."""
    if isinstance(exc, tools.OneOptionAsk):
        return _one_option_ask(state, name)
    state.failed_calls.add(signature)
    state.count_failure(name)
    state.messages.append(
        {
            "role": "tool",
            "tool_name": name,
            "content": json.dumps({"error": str(exc), "what_to_do": _HANDOFF_RECOVERY.get(name, _ASK_RECOVERY)}),
        }
    )
    yield {
        "type": "tool",
        "label": f"ph:warning couldn't {name.replace('_', ' ')}",
        "ok": False,
        "error": str(exc),
    }
    return False


def _dispatch_call(
    session: Session,
    plan: _TurnPlan,
    state: _TurnState,
    call: dict,
    history: list[dict] | None,
) -> Iterator[dict]:
    """Stage three: one tool call, from the guards to the result in `messages`.

    Yields the same events `run_agent` yields and **returns True when the turn
    is over** (the handover tools, `ask_user` and `run_skill`, which end it by
    design); False to carry on with the next call. Callers say
    `if (yield from _dispatch_call(...)): return`, which is why the return
    value is a bool rather than a raised signal: the caller has a `finally`-less
    loop and reads better for having the stop be an ordinary value.

    Lifted whole out of `run_agent`'s round loop with no behaviour change
    (WORLD_CLASS_PLAN A5). The order of the guards is load-bearing, each
    branch's comment says why it is where it is, and the existing agent tests
    are the only gate on this split.
    """
    name, arguments = call["name"], _tidied_arguments(call["name"], call.get("arguments") or {}, state.messages)
    spec = tools.TOOLS.get(name)
    signature = (name, json.dumps(arguments, sort_keys=True))
    if name in plan.barred:
        # A run trying to start a run. Refused with the reason, not
        # silently: the model asked for this because it has decided the
        # job is bigger than one step, and the useful answer is "you
        # are already inside the mechanism you are reaching for".
        state.failed_calls.add(signature)
        state.count_failure(name)
        state.messages.append(
            {
                "role": "tool",
                "tool_name": name,
                "content": json.dumps(
                    {
                        "error": f"{name} cannot be used inside a run",
                        "what_to_do": _RECOVERY_HINTS["already_running"],
                    }
                ),
            }
        )
        yield {
            "type": "tool",
            "label": f"ph:warning {name.replace('_', ' ')} isn't available here",
            "ok": False,
            "error": f"{name} cannot be used inside a run",
        }
        return False
    if plan.permitted is not None and name not in plan.permitted:
        # The allowlist is a safety property, not only a prompt: a
        # model that calls a tool it was never offered does not get to
        # run it just because the registry has one by that name.
        result = {"error": f"{name} is not part of this skill's tools"}
        result["what_to_do"] = (
            REPEATED_CALL_NOTE
            if signature in state.failed_calls
            else _RECOVERY_HINTS["not_in_skill"]
        )
        state.failed_calls.add(signature)
        state.count_failure(name)
        yield {
            "type": "tool",
            "label": f"ph:warning {name} isn't part of this skill",
            "ok": False,
            "error": result["error"],
        }
    elif spec is not None and call.get("invalid_arguments") is not None:
        #: The JSON did not read even leniently (`provider.loads_lenient`).
        #: Said as that, with a shape to copy: running the tool with `{}`
        #: told the model "missing something" and it retried the same JSON.
        result = {
            "error": f"{name}: the arguments were not valid JSON, so nothing ran",
            "what_to_do": (
                f"Call {name} again with its arguments as one JSON object, "
                f"for example {tools.example_arguments(name)}."
            ),
        }
        state.failed_calls.add(signature)
        state.count_failure(name)
        yield {
            "type": "tool",
            "tool": name,
            "label": f"ph:warning {name.replace('_', ' ')}, arguments unreadable",
            "ok": False,
            "error": result["error"],
            "arguments": {"unreadable": call["invalid_arguments"]},
        }
    elif spec is not None and spec.ends_turn:
        # `ask_user` and `run_skill`. The turn stops here, and in both
        # cases that is the feature rather than a limitation: the model
        # asked because it does not know what to do next, or it handed
        # the job to a skill that will do it step by step. Carrying on
        # after either would mean carrying on with the guess the
        # handover exists to avoid.
        #
        # No state is parked on the server. The user's choice: or the
        # skill run: is sent as the next message, which means it
        # arrives through the ordinary history the model already reads:
        # nothing to expire, nothing to lose on a reload, and the
        # exchange is visible in the saved conversation like any other.
        try:
            handover = tools.handoff_event(name, arguments, history)
        except tools.ToolError as exc:
            return (yield from _handoff_refused(state, name, signature, exc))
        return (yield from _finish_handover(session, plan, state, name, arguments, handover))
    elif spec is not None and (tools.needs_confirm(name, arguments, state.approved) or (state.tainted and name in _PARK_WHEN_TAINTED and not _cleared_page(state, name, arguments))) and state.parked.get(name, 0) >= MAX_PARKED_CONFIRMS:
        # **A destructive tool cannot paper the turn with confirm
        # cards.** Parking one hands the model `AWAITING_CONFIRMATION`
        # rather than a result, which is honest but is not a *stop*:
        # a model that has misread the job re-parks the same tool with
        # fresh arguments, and every round of that is another card in
        # front of the user for something they never asked for. Two is
        # enough for a genuine "delete this, and that" turn; past that
        # the model is guessing, and guessing at destructive calls is
        # the one place this app should be least willing to keep up.
        result = {
            "error": (
                f"{name} is already waiting for the user's approval "
                f"{state.parked[name]} times in this turn. Nothing more can be "
                "queued for them."
            ),
            "what_to_do": (
                "Stop. The user has to approve what is already waiting "
                "before anything else destructive can be prepared. Tell "
                "them what is queued and why, and do not call this tool again."
            ),
        }
        state.count_failure(name)
        yield {
            "type": "tool",
            "label": f"ph:prohibit {name.replace('_', ' ')}, too many waiting for approval",
            "ok": False,
            "error": result["error"],
        }
    elif spec is not None and (tools.needs_confirm(name, arguments, state.approved) or (state.tainted and name in _PARK_WHEN_TAINTED and not _cleared_page(state, name, arguments))):
        # Park it for the user, never auto-run a destructive tool, nor a
        # tool that reaches out once the turn has read from outside.
        # The confirm card is the honest signal, so count it as an
        # action (don't fire the "nothing happened" safety net): the
        # user can see for themselves that it is waiting on them.
        state.did_write = True
        state.ran_writes.add(name)
        state.parked[name] = state.parked.get(name, 0) + 1
        yield {
            "type": "confirm",
            "name": name,
            "arguments": arguments,
            "label": tools.confirm_label(name, arguments, session),
        }
        result = AWAITING_CONFIRMATION
    elif state.tool_failures.get(name, 0) >= MAX_TOOL_FAILURES:
        # **The tool is spent for this turn.** Unlike the signature
        # check just below, this fires however much the arguments
        # change: which is the whole point, since the loop it was
        # written for produced fresh wrong arguments every round (see
        # `tool_failures`). Blocked *before* execution, so a tool that
        # writes cannot land a change on a fourth guess either.
        result = {
            "error": (
                f"{name} has failed {state.tool_failures[name]} times in this "
                "turn and is no longer available for it"
            ),
            "what_to_do": TOOL_EXHAUSTED_NOTE,
        }
        yield {
            "type": "tool",
            "label": f"ph:prohibit {name.replace('_', ' ')}, stopped after repeated failures",
            "ok": False,
            "error": result["error"],
        }
    elif signature in state.failed_calls:
        # --- NEW INTERCEPTION: Duplicate Failed Calls ---
        # The model is looping on a broken call. Intercept before execution.
        # Counted as a failure too, so a model that alternates between
        # repeating a call and inventing new arguments for the same
        # tool still reaches MAX_TOOL_FAILURES rather than ping-ponging
        # between the two interceptions forever.
        state.count_failure(name)
        result = {
            "error": (
                f"You already called {name} with these exact arguments "
                "and it failed. You must try a different approach, "
                "change your arguments, or stop and ask the user."
            ),
            "what_to_do": REPEATED_CALL_NOTE,
        }
        yield {
            "type": "tool",
            "label": f"ph:warning {name.replace('_', ' ')}, repeated failure",
            "ok": False,
            "error": "Repeated failure intercepted",
        }
    elif name == "create_note" and _copies_what_was_read(arguments, state.messages, state.did_write):
        result = {
            "error": "That note already exists: this is a copy of a note you read or changed this turn.",
            "what_to_do": "Do not make a new note. Tell the user what you did to the existing note.",
        }
        yield {
            "type": "tool",
            "label": "ph:warning create note, a copy of an existing note",
            "ok": False,
            "error": "Copy of an existing note intercepted",
        }
    elif signature in state.done_calls and name in _WRITE_TOOLS:
        # --- NEW INTERCEPTION: Duplicate Writes ---
        # A write that already succeeded this turn. Intercept before executing again.
        result = {
            "error": (
                f"You already called {name} with these exact arguments "
                "earlier in this turn and it succeeded. Do not run the same "
                "write tool twice with the same arguments."
            ),
            "what_to_do": "Move on to the next step of your plan.",
        }
        yield {
            "type": "tool",
            "label": f"ph:warning {name.replace('_', ' ')}, already done",
            "ok": False,
            "error": "Duplicate write intercepted",
        }
    # --- OLD: elif (name, json.dumps(arguments, sort_keys=True)) in fresh_reads: ---
    elif (name, json.dumps(arguments, sort_keys=True)) in state.fresh_reads:
        # note's context in full, after no changes."*
        #
        # Re-running it is not merely wasted time, the result is
        # identical and gets appended to the prompt a second time, so
        # the round that repeats a read costs the window twice and
        # brings back nothing. Handing back a pointer instead is
        # cheaper than the data by an order of magnitude and says the
        # one thing the model needs to hear: you already have this,
        # move on.
        #
        # `done_calls` is emptied whenever a write succeeds (below), so
        # this can never serve a stale read of something the turn
        # itself just changed: which is the only way a cache here
        # could produce a wrong answer rather than a slow one.
        result = {
            "already_done": True,
            "note": (
                f"You already called {name} with these exact arguments. "
                "The information was provided in your previous tool calls "
                "above. Please refer to your chat history to find it, rather "
                "than running the tool again, and move on."
            ),
        }
        yield {
            "type": "tool",
            "label": f"↩︎ {name.replace('_', ' ')}, already read",
            "ok": True,
        }
    else:
        result = yield from _run_and_record(session, plan, state, name, arguments)
    #: Someone else's words in the result (a note's body, a page's text, a
    #: snippet) go to the model fenced as quoted data (`fence`, INBOX 430);
    #: the app's own fields (`what_to_do`, labels, ids) do not.
    # The window's share, but never more than the absolute ceiling,
    # a 128k model would otherwise be allowed tens of thousands of
    # tokens of tool output, which is prefill time on every subsequent
    # round for material the model has usually finished with.
    result_cap = min(plan.budget.tool_result_chars, TOOL_RESULT_BUDGET_CHARS)
    payload = _fit_result(result, name, result_cap - state.spent)
    if payload is None:
        # Not even a shortened copy fits. Hand back the notice instead and
        # withdraw the tools, so the next round has to be an answer. Never
        # a cut string: half a JSON object is worse than none, the model
        # reads it as data and answers from a note cut mid-sentence.
        payload = json.dumps(BUDGET_EXHAUSTED)
        state.offered = []
    state.spent += len(payload)
    state.messages.append(
        {"role": "tool", "tool_name": name, "content": payload}
    )

    return False


def _wrap_up_round(ollama, agent_model: str, mode, state: _TurnState, card: _TurnCard, show_plan: bool) -> Iterator[dict]:  # noqa: ANN001
    """One more round with the tools withdrawn, for an answer, when a turn
    runs out of rounds; yields the answer as it streams and returns its
    text. Lifted from `run_agent` with no behaviour change (audit
    2026-10-05, ARCH-22)."""
    wrapped = ""
    # **One more round, with the tools withdrawn, for an answer** (INBOX
    # 527). Before, a turn that ran out handed the user only "I stopped
    # after 4 rounds", however much it had found: a small model capped at
    # four rounds that had read the right note gave no answer from it.
    # A skill step passes its own note and is left alone: the runner
    # reads the stop, not prose, to mark the step stalled.
    state.messages.append({"role": "user", "content": WRAP_UP_NUDGE})
    try:
        for piece in ollama.chat_tools_stream(agent_model, state.messages, [], mode=mode):
            if "content_delta" in piece:
                wrapped += piece["content_delta"]
                yield {"type": "answer", "delta": piece["content_delta"]}
            elif "final" in piece and not piece["final"].get("streamed"):
                late = (piece["final"].get("content") or "").strip()
                if late and not wrapped:
                    wrapped = late
                    yield {"type": "answer", "delta": late}
    except (OllamaError, ToolsUnsupportedError) as exc:
        logging.getLogger("tessellate.agent").info("wrap-up round failed: %s", exc)
    if card.drawn:
        yield from card.end_round(TURN_ROW_WRAP_UP)
    yield from _check_sources(wrapped, state.messages, show_plan)
    unsupported = unsupported_claims(wrapped, state.ran_writes | state.implied)
    if unsupported:
        yield {
            "type": "answer",
            "delta": f"\n\nHeads up: I said I {', '.join(unsupported)}, but that tool never ran, so it did not happen.",
        }
    return wrapped


@dataclass
class _Loop:
    """The round loop's own counters, kept apart from `_TurnState` (what the
    tools learn) because only the loop and its stage helpers touch them."""

    #: Granted, then earned: see `_prepare_turn` for the two caps.
    allowance: int
    ceiling: int
    round_number: int = -1
    #: One nudge per turn for a round that came back with nothing at all.
    nudged_empty: bool = False
    #: A forced first round that came back without a call is asked once more
    #: with the call required again (`FORCED_PROSE_NUDGE`); set when that
    #: second round is owed, so the retry is forced and the turn gets one.
    retry_forced: bool = False
    #: And one for a round that only said what it would do.
    nudged_intent: bool = False
    #: And one for a reply that claimed an act no tool performed.
    nudged_claim: bool = False
    #: The replies a nudge set aside, for the claim check at the turn's end.
    said_before: str = ""
    #: Only a turn that has done nothing at all is nudged: a skill step that
    #: read its page and then stops is finished, and the runner reads that
    #: silence (`skill_runner`'s paging and postconditions depend on it).
    called_any: bool = False


@dataclass
class _Streamed:
    """What one round's stream produced, filled in as it arrives so the error
    paths can still see whether any prose reached the user."""

    reply: dict = field(default_factory=dict)
    streamed_any: bool = False


def _budget_events(spend, state: _TurnState, loop: _Loop) -> list[dict]:  # noqa: ANN001
    """Checked between rounds, never mid-stream: stopping inside a model call
    would leave half an answer on screen and a tool result nobody read, so the
    most a run can overshoot its budget by is one round."""
    if spend is None or not spend.exceeded():
        return []
    return [
        {
            "type": "limit",
            "reason": "budget",
            "detail": spend.exceeded(),
            "rounds": loop.round_number + 1,
            "tokens": spend.spent_tokens,
            "wrote": sorted(state.ran_writes),
        },
        {"type": "answer", "delta": f"I stopped here: {spend.exceeded()}"},
    ]


def _round_tools(question: str, plan: "_TurnPlan", state: _TurnState, loop: _Loop, session: Session) -> tuple[bool, list[dict]]:
    required = (loop.round_number == 0 or loop.retry_forced) and plan.tier.force_first_call and _requires_a_call(question, plan)
    first = loop.round_number == 0 or (loop.retry_forced and required)
    tools = _first_round_tools(question, plan, state.offered, required, session) if first else state.offered
    loop.retry_forced = False
    return required, tools


def _relay_stream(stream, got: _Streamed, cap: int | None, tier_name: str) -> Iterator[dict]:  # noqa: ANN001
    said = ""
    for piece in stream:
        if "thinking_delta" in piece:
            yield {"type": "thinking", "delta": piece["thinking_delta"]}
        elif "content_delta" in piece:
            got.streamed_any = True
            said += piece["content_delta"]
            yield {"type": "answer", "delta": piece["content_delta"]}
            if cap is not None and len(said) >= cap:
                # Closing the generator closes the HTTP stream with it (the
                # same path Stop takes).
                stream.close()
                logging.getLogger("tessellate.agent").info("reply cap: %s-tier round cut at %d chars", tier_name, len(said))
                yield {"type": "answer", "delta": REPLY_CAP_NOTE}
                got.reply = {"content": said, "tool_calls": [], "streamed": True}
                break
        elif "final" in piece:
            got.reply = piece["final"]


def _unsupported_events(card: _TurnCard, agent_model: str, exc: ToolsUnsupportedError) -> Iterator[dict]:
    # INBOX 272 part 1: named here, once, so every caller that forwards this
    # event (routes_chat.py, skill_runner.py) shows the same remedy instead of
    # dropping it (see tools_unsupported_message's own docstring).
    yield from card.end_round(TURN_ROW_RUNNING, "failed", "the model cannot use tools")
    yield {
        "type": "unsupported",
        "model": agent_model,
        "message": tools_unsupported_message(agent_model, getattr(exc, "declared", True)),
    }


def _model_died_events(card: _TurnCard, agent_model: str, exc: OllamaError, streamed_any: bool) -> Iterator[dict]:
    # Mid-answer death: say so, but don't wipe what already streamed.
    # `offline: True` alongside the normal answer shape (Tier 1 section 3): an
    # ordinary chat turn renders this like any other answer, but skill_runner
    # cannot tell this boilerplate from a real answer without it, and was
    # ticking the step "done" and repeating the identical failure on every
    # later step. It only ever checks the flag's truthiness, never the text.
    # Logged too, so the failure reaches Settings -> Logs and not only the
    # chat bubble (librarian.model_error_message's docstring has the history).
    logging.getLogger("tessellate.chat").warning("agent: model call failed for %r: %s", agent_model, exc)
    prefix = "\n\n" if streamed_any else ""
    yield {"type": "answer", "delta": f"{prefix}{librarian.model_error_message(agent_model, exc)}", "offline": True}
    yield from card.end_round(TURN_ROW_RUNNING, "failed", "the model stopped answering")


def _stream_round(ollama, plan: "_TurnPlan", state: _TurnState, loop: _Loop, question: str, mode, session: Session, card: _TurnCard):  # noqa: ANN001
    """One model call, streamed to the user. Returns (reply, required), or None
    after yielding why the turn cannot go on. Streamed: the model's prose
    reaches the user as it's written, rather than in one lump after a pause."""
    got = _Streamed()
    #: H3: prose this round streams, against the tier's reply cap.
    cap = plan.tier.reply_chars if state.offered else None
    required = False
    try:
        required, tools = _round_tools(question, plan, state, loop, session)
        stream = _round_stream(ollama, plan.agent_model, state.messages, tools, mode, required)
        yield from _relay_stream(stream, got, cap, plan.tier.name)
    except ToolsUnsupportedError as exc:
        yield from _unsupported_events(card, plan.agent_model, exc)
        return None
    except OllamaError as exc:
        yield from _model_died_events(card, plan.agent_model, exc, got.streamed_any)
        return None
    return got.reply, required


def _round_stats(spend, reply: dict, plan: "_TurnPlan", loop: _Loop) -> list[dict]:  # noqa: ANN001
    # Charged whatever the provider reported, once per round, before anything
    # is done with the result: a round that ran cost something even if its
    # answer is thrown away. Agent turns once emitted nothing here, which
    # silently stripped the token counts from the message metadata line.
    if spend is not None:
        spend.charge(reply.get("stats"))
    if not reply.get("stats"):
        return []
    stats = {**reply["stats"], "round": loop.round_number + 1}
    if loop.round_number == 0:
        stats["composition"] = plan.composition_tokens
    return [{"type": "stats", **stats}]


def _nudge(state: _TurnState, card: _TurnCard, answer: str | None, text: str) -> Iterator[dict]:
    if answer is not None:
        state.messages.append({"role": "assistant", "content": answer})
    state.messages.append({"role": "user", "content": text})
    if answer is not None:
        yield {"type": "answer", "delta": "\n\n"}
    yield from card.end_round(TURN_ROW_RECHECK)


def _nudge_empty(state: _TurnState, loop: _Loop, card: _TurnCard, reply: dict, answer: str, required: bool):
    """**A round with no words and no tool call is asked once more.** Reported
    twice with granite4.1:3b in the popup agent ("what can I use the graph
    for?", "make a note"): the model answered with nothing, often having spent
    the round thinking after a long tool list. One plain-words nudge is the
    cheap recovery; a second empty round ends the turn, and the client says the
    model wrote nothing. True when it nudged."""
    if answer or reply.get("streamed") or loop.nudged_empty or loop.called_any:
        return False
    loop.nudged_empty = True
    loop.retry_forced = required
    yield from _nudge(state, card, None, EMPTY_ROUND_NUDGE)
    return True


def _nudge_prose(state: _TurnState, loop: _Loop, card: _TurnCard, answer: str, required: bool):
    """**A forced round that came back as prose is asked once more**, with the
    call required again. One re-prompt per turn: it takes the place of the
    intent and claim nudges, which would otherwise stack a second and third
    round onto the same miss."""
    if not (required and answer and not loop.called_any and not loop.nudged_empty and not loop.nudged_intent):
        return False
    if loop.round_number + 1 >= loop.allowance:
        return False
    loop.nudged_intent = loop.nudged_claim = True
    loop.retry_forced = True
    yield from _nudge(state, card, answer, FORCED_PROSE_NUDGE)
    return True


def _nudge_intent(state: _TurnState, loop: _Loop, card: _TurnCard, answer: str):
    """**Said it would act, and did not.** Asked once to do it; the sentence
    already shown stays as the turn's opening line, and what the tool finds
    follows it. A second such round ends the turn with the claim checks."""
    if loop.nudged_intent or not announces_unacted_tool(answer, state.offered):
        return False
    loop.nudged_intent = True
    yield from _nudge(state, card, answer, UNACTED_INTENT_NUDGE)
    return True


def _nudge_claim(state: _TurnState, loop: _Loop, card: _TurnCard, answer: str, unsupported: list[str]):
    """**Reflect and retry: a claimed act is asked for once** (INBOX 527,
    Qwen2.5-1.5B): "Make a note: buy oat milk" got "I've made a new note for
    you" and no call. The model is told what it claimed and which tool does it,
    once, while it still has a round; the heads-up is what is left when the
    retry does not do it either, checked against everything said this turn."""
    offered = {t["function"]["name"] for t in state.offered}
    needed = [tool for label, _verb, needs in _CLAIMED_ACTIONS if label in unsupported for tool in sorted(needs) if tool in offered]
    if not (unsupported and needed) or loop.nudged_claim or loop.round_number + 1 >= loop.allowance:
        return False
    loop.nudged_claim = True
    loop.said_before += f"{answer}\n"
    text = CLAIM_RETRY_NUDGE.format(claims=", ".join(unsupported), tools=" or ".join(needed))
    yield from _nudge(state, card, answer, text)
    return True


def _claim_notice(state: _TurnState, answer: str, unsupported: list[str]) -> list[dict]:
    if unsupported:
        # Named, not vague: the answer may have claimed five things, and the
        # user needs to know which did not happen, since the rest may be true.
        listed = ", ".join(unsupported)
        return [
            {
                "type": "answer",
                "delta": (
                    f"\n\nHeads up: I said I {listed}, but I didn't "
                    "actually run the tool that does it, so that part did "
                    "not happen and nothing was changed by it. Ask me again "
                    "and I'll do it properly."
                ),
            }
        ]
    if not state.did_write and _CLAIM_PATTERN.search(answer):
        # The looser net, for a claim with no recognisable action in it ("new
        # note titled..."). Only when nothing was written, since it can't say
        # which action it means.
        return [
            {
                "type": "answer",
                "delta": (
                    "\n\nHeads up: I described that, but it looks like I "
                    "didn't actually save it (my model didn't run the tool). "
                    "Nothing was changed: try again, or paste the text into "
                    "a new note yourself."
                ),
            }
        ]
    return []


def _settle_answer(state: _TurnState, loop: _Loop, card: _TurnCard, reply: dict, required: bool, show_plan: bool):
    """A round with no tool call: this text IS the final answer. True when the
    turn is over, False when a nudge asked for another round."""
    answer = reply.get("content", "").strip()
    if (yield from _nudge_empty(state, loop, card, reply, answer, required)):
        return False
    # It has usually streamed already; send it only if the tool-call gate held it back.
    if not reply.get("streamed") and answer:
        yield {"type": "answer", "delta": answer}
    if (yield from _nudge_prose(state, loop, card, answer, required)) or (yield from _nudge_intent(state, loop, card, answer)):
        return False
    # Safety net: a claim to have saved/created something when no write tool
    # ran is a hallucination; say so rather than let the user believe a note
    # exists that doesn't.
    unsupported = unsupported_claims(f"{loop.said_before}{answer}", state.ran_writes | state.implied)
    if (yield from _nudge_claim(state, loop, card, answer, unsupported)):
        return False
    yield from _claim_notice(state, answer, unsupported)
    yield from _check_sources(f"{loop.said_before}{answer}", state.messages, loop.called_any and show_plan)
    yield from card.end_round(TURN_ROW_ANSWER)
    return True


def _replay_message(reply: dict) -> dict:
    """The assistant turn with its calls, replayed so the model keeps its own
    context. **Including the round's own reasoning**, asked for directly: *"it
    often thinks up this whole plan, then it does a tool call and either loses
    track or has to rethink the plan again."* `thinking` was streamed to the
    user and then dropped, so a thinking model spent its output budget
    re-deriving the same plan every round. Carried as content rather than a
    `thinking` field because that field is not portable (Ollama accepts one,
    the OpenAI-compatible dialect does not, and a message shape one backend
    rejects is an outage). Marked and clipped, so it reads as a note-to-self
    and cannot grow into the round's whole budget."""
    replay = reply.get("content") or ""
    reasoning = (reply.get("thinking") or "").strip()
    if reasoning:
        clipped = reasoning[:THINKING_CARRIED_CHARS]
        if len(reasoning) > THINKING_CARRIED_CHARS:
            clipped += "…"
        replay = f"[my reasoning so far: {clipped}]{chr(10) if replay else ''}{replay}"
    return {"role": "assistant", "content": replay, "tool_calls": reply.get("raw_tool_calls") or []}


def _widen_focus(plan: "_TurnPlan", state: _TurnState, calls: list[dict]) -> None:
    # Did the model reach for something it was not shown? Then the focus
    # misread the request, and later rounds should not work from the same
    # misreading. Widening is one-way and lasts the rest of the turn.
    if not plan.focused_only or state.offered is plan.every_tool:
        return
    shown = {t["function"]["name"] for t in state.offered}
    reached_past = [c["name"] for c in calls if c["name"] not in shown]
    if reached_past:
        logging.getLogger("tessellate.agent").info(
            "focus corrected: model called %s, which the question's "
            "words did not suggest, offering the full set from here",
            ", ".join(sorted(set(reached_past))[:5]),
        )
        state.offered = plan.every_tool


def _dispatch_round(session: Session, plan: "_TurnPlan", state: _TurnState, card: _TurnCard, calls: list[dict], history):  # noqa: ANN001
    """Every call of one round; True when a tool ended the turn (the handover
    tools). See `_dispatch_call`."""
    labels: list[str] = []
    ended = False
    for call in calls:
        if (yield from _labelled(_dispatch_call(session, plan, state, call, history), labels)):
            ended = True
            break
    yield from card.end_round(_TurnCard.row_for(labels))
    return ended


def _exhausted_events(ollama, plan: "_TurnPlan", state: _TurnState, loop: _Loop, card: _TurnCard, spend, mode, show_plan: bool, exhausted_note):  # noqa: ANN001
    # Out of rounds with tools still being called: the job is unfinished, and
    # saying so is the honest end. The `limit` event is what distinguishes this
    # from an answer: the skill runner marks the step stalled rather than
    # ticking it off, and the chat UI offers Continue instead of making the
    # user type "carry on".
    yield {"type": "limit", "reason": "rounds", "rounds": loop.round_number + 1, "wrote": sorted(state.ran_writes)}
    wrapped = ""
    if exhausted_note is None and not (spend is not None and spend.exceeded()):
        wrapped = yield from _wrap_up_round(ollama, plan.agent_model, mode, state, card, show_plan)
    yield {
        "type": "answer",
        "delta": exhausted_note
        or (
            ("\n\n" if wrapped.strip() else "")
            + "I stopped after "
            f"{loop.round_number + 1} rounds of tool calls, here's where things "
            "stand. Continue and I'll pick up from here."
        ),
    }


def run_agent(
    session: Session,
    question: str,
    notes: list[dict],
    model_manager: ModelManager,
    ollama: OllamaClient,
    style: str = "friendly",
    profile: str = "",
    history: list[dict] | None = None,
    persona_prompt: str | None = None,
    allowed_tools: list[str] | None = None,
    blocked_tools: frozenset[str] | set[str] | None = None,
    max_rounds: int = MAX_ROUNDS,
    earned_rounds: int = EARNED_ROUNDS,
    exhausted_note: str | None = None,
    mode: str | None = None,
    use_utility_model: bool = False,
    images: list[str] | None = None,
    model_override: str | None = None,
    image_context: str | None = None,
    show_plan: bool = True,
    approved: bool = False,
) -> Iterator[dict]:
    """Yields event dicts:
    {"type": "unsupported", "model": ..., "message": ...}, model can't do
                                                 tools; caller should fall
                                                 back to plain Q&A, and
                                                 should show `message`
                                                 (INBOX 272 part 1) rather
                                                 than drop the event
                                                 (always the first and only event)
    {"type": "thinking", "delta": str}
    {"type": "tool", "label": str, "ok": bool, "error": str|None}
    {"type": "confirm", "name", "arguments", "label"}
    {"type": "limit", "reason": "rounds", ...}, ran out of rounds mid-job;
                                                 the answer that follows is a
                                                 stopping notice, not a result
    {"type": "answer", "delta": str}: the final text
    {"type": "plan"/"step", "kind": "turn", ...}, the turn's own plan card
                                                 (`_TurnCard`); off for a
                                                 skill step (`show_plan`)
    """
    plan = _prepare_turn(
        session,
        question,
        notes,
        model_manager,
        ollama,
        style=style,
        profile=profile,
        history=history,
        persona_prompt=persona_prompt,
        allowed_tools=allowed_tools,
        blocked_tools=blocked_tools,
        max_rounds=max_rounds,
        earned_rounds=earned_rounds,
        mode=mode,
        use_utility_model=use_utility_model,
        images=images,
        model_override=model_override,
        image_context=image_context,
    )
    state = _TurnState(messages=plan.messages, offered=plan.offered, named_hosts=_hosts_named(question), approved=approved)
    # SEC-02: a note retrieved for the question that was clipped from the web
    # or imported is already in the prompt, so the turn starts tainted.
    if any(isinstance(n, dict) and n.get("from_outside") for n in notes or ()):
        state.outside = True
    loop = _Loop(allowance=plan.granted, ceiling=plan.ceiling)
    #: **The run this turn belongs to, if it belongs to one** (Brief 13).
    #: None for an ordinary chat turn: that is bounded per turn already, by
    #: `loop.allowance`, and has no notion of a run to belong to. See
    #: `ai/budget.py` for why this is a scope rather than a parameter.
    spend = run_budget.current()
    card = _TurnCard(question, show_plan)

    while loop.round_number + 1 < loop.allowance:
        stop = _budget_events(spend, state, loop)
        if stop:
            yield from stop
            return
        loop.round_number += 1
        yield from card.start_round(loop.called_any)
        # Set by any tool call that succeeded and had not been made before,
        # the definition of "this round got somewhere". Read at the bottom of
        # the loop, where it buys the next round.
        state.progressed = False
        got = yield from _stream_round(ollama, plan, state, loop, question, mode, session, card)
        if got is None:
            return
        reply, required = got
        yield from _round_stats(spend, reply, plan, loop)
        calls = reply.get("tool_calls") or []
        if not calls:
            if (yield from _settle_answer(state, loop, card, reply, required, show_plan)):
                return
            continue
        loop.called_any = True
        state.messages.append(_replay_message(reply))
        _widen_focus(plan, state, calls)
        state.tainted = state.outside
        if not state.tainted:
            _prefetch_outbound(calls)
        if (yield from _dispatch_round(session, plan, state, card, calls, history)):
            return
        if state.progressed and loop.allowance < loop.ceiling:
            # This round did something new, so the turn gets another one. The
            # cap that stops a runaway is still there: a round that repeats
            # itself or errors buys nothing, so a loop never reaches `ceiling`.
            loop.allowance += 1
    yield from _exhausted_events(ollama, plan, state, loop, card, spend, mode, show_plan, exhausted_note)
