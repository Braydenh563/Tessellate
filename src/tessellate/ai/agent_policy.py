"""The agent loop, layer one: the rules (audit 1031 AI23).

Size tiers, the nudges the loop sends, intent and claim checks, the tool guide,
recovery hints, what a call touched and the sources it names, the write tools'
change extractors and the outbound-page taint. A pure move out of `agent.py`,
text unchanged; it imports nothing from `agent.py` or `agent_turn.py`, and
`agent.X` still reaches every name here.
"""

from __future__ import annotations

import json
import re
from typing import NamedTuple
from urllib.parse import urlsplit

from tessellate.ai import fence, memory, source_check, tools
from tessellate.ai.model_manager import SMALL_MODEL_PARAMS_B, parameter_count
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
#: of `run_agent`): what it found is worth an answer even if the job is unfinished.
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
        self.title = (
            title if len(title) <= _TITLE_CHARS else title[: _TITLE_CHARS - 1].rstrip() + "…"
        )
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
        self.rows[index : index + 1] = [text]
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
    'For "remind me… in 10 minutes / tomorrow at 9", call set_reminder '
    "with when in the user's own words; the app works out the date. "
    # Both halves of this earned their place and both were briefly cut. Without
    # the first the model acts and then says nothing, so the user watches tool
    # chips scroll past and gets no answer; without the second it narrates work
    # it never did. They are opposite failures and the pair is the fix.
    "After acting, tell the user briefly what you did. NEVER say you created, "
    "saved, edited, deleted, tagged, linked or unlinked anything unless you "
    'called the tool: "we linked…" is claiming it just as much as "I '
    'linked…", and a list of work you did not do is the worst thing you can '
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
    'Users never see note ids: name a note by a few of its own words ("your '
    'gym routine note"), not "note 28". '
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

#: What a private chat's AI may not do (INBOX 1481): teach itself something.
PRIVATE_BLOCKED = frozenset({"save_user_preference"})

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
    return next(
        (_RECOVERY_HINTS[key] for phrases, key in table if any(p in lowered for p in phrases)), None
    )


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
    if name in ("web_search", "read_url") and not any(
        m in lowered for m in ("was given", "is required", "required", "must be")
    ):
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


def _source_row(title: object, url: object, snippet: object) -> dict:
    return {"title": clip_words(title, SOURCE_SNIPPET_CHARS), "url": url, "snippet": clip_words(snippet, SOURCE_SNIPPET_CHARS)}


def _search_sources(result: dict) -> list[dict]:
    """One row per web hit; a hit with no title is named by its address."""
    rows = []
    for hit in (result.get("results") or [])[:SOURCE_LIMIT]:
        if isinstance(hit, dict):
            url = str(hit.get("url") or "")
            row = _source_row(hit.get("title"), url, hit.get("snippet"))
            rows.append({**row, "title": row["title"] or url})
    return rows


def _page_source(result: dict) -> list[dict]:
    """The page a read opened: itself, named by its address when it has no title."""
    url = str(result.get("url") or "")
    row = _source_row(result.get("title"), url, result.get("text"))
    return [{**row, "title": row["title"] or url}]


def _file_sources(result: dict) -> list[dict]:
    """The files a read or search drew on: one row per match, or the one file
    a plain read opened (which carries its own path rather than a match list)."""
    matches = result.get("matches") or result.get("results") or []
    if isinstance(matches, list) and matches:
        return [
            _source_row(hit.get("path") or hit.get("name"), "", hit.get("snippet") or hit.get("text"))
            for hit in matches[:SOURCE_LIMIT]
            if isinstance(hit, dict)
        ]
    if result.get("path") or result.get("name"):
        return [_source_row(result.get("path") or result.get("name"), "", result.get("text") or result.get("content"))]
    return []


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
    if name == "web_search":
        rows = _search_sources(result)
    elif name == "read_url":
        rows = _page_source(result)
    elif name in {"read_file", "search_files"}:
        rows = _file_sources(result)
    else:
        rows = []
    #: A row with nothing to say is not a source. Dropping it here keeps the
    #: "is there anything to show" test in the front end a length check.
    return [row for row in rows if row["title"] or row["url"]]


MAX_TOOL_FAILURES = 3

# How many confirm cards one destructive tool may put in front of the user in
# a single turn. See the `parked` check in `run_agent`.
MAX_PARKED_CONFIRMS = 12

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
_PASSIVE = (
    r"(?:has|have|is now|are now)\s+(?:now\s+|just\s+|also\s+)?(?:been\s+)?(?:successfully\s+)?"
)
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
    (
        re.compile(
            r"\b(?:added|moved)\b(?=[^.!?\n]{0,40}\bto\s+(?:your\s+|the\s+)?favou?rites\b)", re.I
        ),
        "pinned",
    ),
    (
        re.compile(r"\bremoved\b(?=[^.!?\n]{0,40}\bfrom\s+(?:your\s+|the\s+)?favou?rites\b)", re.I),
        "unpinned",
    ),
    (re.compile(r"\b(?:added|removed|applied)\b(?=[^.!?\n]{0,30}\btags?\b)", re.I), "tagged"),
    (
        re.compile(
            r"\b(?:added|appended)\b(?=[^.!?\n]{0,60}\bto\s+(?:your|the|that)\s+[^.!?\n]{0,40}\bnote\b)",
            re.I,
        ),
        "updated",
    ),
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
    "your tool results. If neither answers the question, say so honestly. " + fence.FENCE_RULE
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


def parks_when_tainted(name: str) -> bool:
    return name in _PARK_WHEN_TAINTED


def reads_outside(name: str) -> bool:
    return name in _OUTSIDE_TOOLS


def claims_a_write(answer: str) -> bool:
    return bool(_CLAIM_PATTERN.search(answer))


#: **Which pages a tainted turn may keep opening without a card** (SEC-02's last
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
