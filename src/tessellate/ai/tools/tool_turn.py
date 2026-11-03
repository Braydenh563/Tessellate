"""The tools that steer a turn: ask the user, run a skill, make a plan, compress the chat, propose an act.

Moved whole from `__init__.py` (audit AR3, gods-2): the code is unchanged, and
`__init__` re-exports every name here that anything reads. Imports run one way,
down the layer list in `__init__.py`'s docstring, never back to `__init__`.
"""

from __future__ import annotations

import json
import re

from tessellate.ai.ollama_client import OllamaError
from sqlalchemy.orm import Session
from tessellate.ai.tools._common import ToolError, _clip
from tessellate.core import deps
from tessellate.ai import librarian, skills


#: How many choices an `ask_user` question may offer. Two is the minimum for a
#: question to be one; six is where a list of buttons stops being quicker to
#: read than just typing the answer.
MIN_ASK_OPTIONS = 2


class OneOptionAsk(ToolError):
    """An ask with one choice is not a question (INBOX 808): the loop takes
    ask_user away for the turn and tells the model to answer or act."""
MAX_ASK_OPTIONS = 6
MAX_ASK_QUESTION = 200
MAX_ASK_OPTION = 80


def _ask_user(session: Session, args: dict) -> dict:
    """Never runs. Reaching this is a bug worth failing loudly on.

    `ask_user` is not executed like other tools: the agent loop sees
    `ends_turn` and stops, handing the question to the UI. The handler exists
    because every `ToolSpec` has one, and it raises because the alternative, 
    returning something plausible: would let a path that bypasses the loop
    (`POST /chat/tools/execute`, say) silently "answer" a question the user
    never saw.
    """
    raise ToolError(
        "ask_user is answered by the person, not by the app, it cannot be run "
        "directly."
    )


def validate_ask(arguments: dict) -> tuple[str, list[str]]:
    """The question and its choices, or a ToolError explaining what's wrong.

    Validated here rather than trusted, because a small model will get this
    wrong in every way available to it: one option, twelve options, options as
    a single comma-separated string, an empty question. Each of those would
    otherwise render as a broken card the user can only ignore, and the model
    would be left waiting for an answer that can never come.
    """
    question = str(arguments.get("question") or "").strip()
    if not question:
        raise ToolError("ask_user needs a question to ask.")
    raw = arguments.get("options")
    if isinstance(raw, str):
        # A model that sent "yes, no" instead of ["yes", "no"]. Recovering is
        # free and the alternative is a dead card.
        raw = [part.strip() for part in raw.split(",")]
    if not isinstance(raw, list):
        raise ToolError("ask_user needs a list of options to choose from.")
    options: list[str] = []
    for item in raw:
        # Accept {"label": ...} too: it is the shape several models reach for,
        # and rejecting it would fail a call that meant the right thing.
        text = item.get("label") if isinstance(item, dict) else item
        text = str(text or "").strip()[:MAX_ASK_OPTION]
        if text and text not in options:
            options.append(text)
    if len(options) < MIN_ASK_OPTIONS:
        raise OneOptionAsk(
            f"ask_user needs at least {MIN_ASK_OPTIONS} different options: "
            "if there is only one sensible answer, just do it."
        )
    return question[:MAX_ASK_QUESTION], options[:MAX_ASK_OPTIONS]


#: How many skill names a "no such skill" error hands back. Enough to pick
#: from, short enough that a mistyped name doesn't cost a round's worth of
#: window.
MAX_SKILL_NAMES = 12
MAX_NAME_ECHO = 40


def _run_skill(session: Session, args: dict) -> dict:
    """Never runs, for the same reason `_ask_user` never runs.

    `run_skill` hands the turn to the skill runner instead of returning a
    result: the agent loop sees `ends_turn` and stops. Executing it here would
    let a path that bypasses the loop (`POST /chat/tools/execute`) start a run
    with no plan drawn, no steps ticked off and no list of what changed, 
    which is every part of §21 that makes a run reviewable.
    """
    raise ToolError(
        "run_skill starts a run rather than returning an answer, it cannot "
        "be executed directly."
    )


def _skill_key(name: str) -> str:
    """A skill name reduced to what a model can be relied on to reproduce.

    The built-ins are named "Auto-tag my notes", and a model asked to pass
    that back will drop the emoji, change the case, or both. Matching on
    letters and digits alone costs nothing and turns the single most likely
    mistake into a run that works.
    """
    return "".join(ch for ch in str(name or "").lower() if ch.isalnum())


def _match_skill(catalog: list[dict], wanted: str) -> dict | None:
    """Exact name first, then the forgiving match. Exact wins on purpose: two
    skills whose names differ only by punctuation must still be reachable."""
    for skill in catalog:
        if skill["name"] == wanted:
            return skill
    key = _skill_key(wanted)
    if not key:
        return None
    for skill in catalog:
        if _skill_key(skill["name"]) == key:
            return skill
    return None


#: How many steps an ad-hoc plan may have.
#:
#: Two is the floor because a one-step plan is just the action, planning it
#: costs a whole extra model round to say what the model could have done in
#: that round. Six is the ceiling because every step is its own turn on a local
#: machine: a ten-step plan on a 3B model is minutes of generation before the
#: user sees the end of it, and a model that needs ten steps has usually
#: written six real ones and four restatements.
MIN_PLAN_STEPS = 2
MAX_PLAN_STEPS = 6

#: Numbering the model writes into the step text itself. It has just been asked
#: for an ordered list, so "1." and "- " are natural things for it to include, 
#: and the plan card numbers the steps itself, so leaving them in prints
#: "1. 1. Search for untagged notes".
_STEP_NUMBERING = re.compile(r"^\s*(?:[-*•]|\(?\d{1,2}[.):])\s*")


def _make_plan(session: Session, args: dict) -> dict:
    """Never runs, for the same reason `_run_skill` never runs.

    `make_plan` hands the turn to the step runner rather than returning a
    result. Executing it here would produce a plan nobody is going to carry
    out: the steps would come back as a JSON list, the model would summarise
    them in the past tense, and the user would be told a job was done that
    nothing had started. That is §35B's hallucinated write, arrived at by a
    different route.
    """
    raise ToolError(
        "make_plan starts a run rather than returning an answer, it cannot "
        "be executed directly."
    )


def _plan_steps(raw) -> list[str]:
    """The model's steps, in the several shapes models actually send them.

    Recovered rather than refused, because every one of these means exactly the
    right thing and a refused plan costs a round to say so: a JSON string
    instead of a list, one newline-separated string, a list of
    `{"step": "..."}` objects, and its own numbering on the front of each.
    """
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = raw.splitlines()
        raw = parsed if isinstance(parsed, list) else str(parsed).splitlines()
    if not isinstance(raw, list):
        return []
    steps: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            item = item.get("step") or item.get("text") or item.get("title") or ""
        text = _STEP_NUMBERING.sub("", " ".join(str(item or "").split()))
        text = text[: skills.MAX_STEP]
        # A model that repeats a step is padding to reach a count it imagined,
        # and a repeated step runs the same turn twice.
        if text and text.lower() not in {s.lower() for s in steps}:
            steps.append(text)
    return steps


#: Turns to summarise in one call. Beyond this the summary itself gets long
#: enough to be worth summarising, which is the wrong direction. Lives here,
#: not in routes_chat.py, because `summarise_turns` below is shared by
#: POST /chat/compress (the manual button) and compress_chat (this tool): 
#: one ceiling, so the two paths can't quietly drift apart.
MAX_COMPRESS_TURNS = 40

COMPRESS_PROMPT = (
    "Summarise this conversation so it can be continued by someone who has "
    "not read it. Keep: what the user asked for, what was decided, facts "
    "established about their notes, and anything still outstanding. Drop "
    "pleasantries and repetition. Write it as short bullet points, under 200 "
    "words, in the third person. Do not add anything that was not said."
)

#: How many of the most recent turns compress_chat leaves alone. Matches the
#: manual button's KEEP_RECENT_TURNS in app.js: compressing the exchange
#: still in progress is how a summary loses the thing being talked about
#: right now.
COMPRESS_KEEP_RECENT = 2


def summarise_turns(turns: list[tuple[str, str]]) -> dict:
    """A summary of these question/answer pairs.

    Raises `OllamaError` when there is no model to ask (offline, or the call
    itself failed) and `ToolError` when the model answered with nothing, the
    two calling paths (the HTTP route and this tool's validator) map each to
    a different response, so the distinction is preserved rather than
    collapsed into one exception type.
    """
    ollama = deps.get_ollama()
    if not ollama.is_running():
        raise OllamaError(librarian.OFFLINE_MESSAGE)
    transcript = "\n\n".join(
        f"User: {q.strip()[:1500]}\nAssistant: {a.strip()[:1500]}" for q, a in turns
    )
    reply = ollama.chat(
        deps.get_model_manager().utility_model(),
        [
            {"role": "system", "content": COMPRESS_PROMPT},
            {"role": "user", "content": transcript},
        ],
    )
    summary = (reply.get("content") or "").strip() if isinstance(reply, dict) else ""
    if not summary:
        # Better to say nothing happened than to hand back an empty summary
        # the caller would send in place of real turns.
        raise ToolError("The AI returned an empty summary. Try again.")
    return {
        "summary": summary,
        "turns": len(turns),
        "chars_before": len(transcript),
        "chars_after": len(summary),
    }


def _compress_chat(session: Session, args: dict) -> dict:
    """Never runs, for the same reason `_ask_user` never runs.

    `compress_chat` hands the summary to the human for review rather than
    applying it: the code this mirrors (`showCompressReview` in chat.js) is
    explicit that a summary nobody can correct is one they have to trust
    blindly, and that safeguard applies exactly as much to a summary the
    agent asked for as to one the user pressed a button for (§37I: decided
    to keep the hand-off, not skip it for the tool path).
    """
    raise ToolError(
        "compress_chat hands the summary to the user for review, it cannot "
        "be executed directly."
    )


def validate_compress_chat(arguments: dict, history: list[dict] | None) -> dict:
    """The summary to show the user, or a ToolError explaining why not yet.

    Takes no arguments from the model, the conversation itself already has
    the turns to summarise, and asking a small model to restate them as
    arguments would be slower, more expensive, and less faithful than reading
    the history the loop already has in hand.

    Always summarises a *prefix* of `history`, starting at turn 0, the same
    shape POST /chat/compress and `applyCompression` in chat.js assume:
    `chatSummary.covered` folds `chatConv.turns.slice(0, covered)`, so a
    window starting anywhere else would make the client fold the wrong turns.
    """
    turns = [(str(t.get("question") or ""), str(t.get("answer") or "")) for t in (history or [])]
    covered = len(turns) - COMPRESS_KEEP_RECENT
    if covered < 2:
        raise ToolError(
            "There isn't enough conversation yet to compress, keep going, or "
            "just answer without calling this."
        )
    # Beyond the ceiling, cover only the first MAX_COMPRESS_TURNS rather than
    # refuse outright: the rest stays in the visible, uncompressed tail.
    covered = min(covered, MAX_COMPRESS_TURNS)
    try:
        result = summarise_turns(turns[:covered])
    except OllamaError as exc:
        raise ToolError(str(exc)) from exc
    result["type"] = "compress_review"
    return result


def validate_make_plan(arguments: dict) -> dict:
    """The plan a run should be built from, or a ToolError saying what's wrong.

    Every failure here is recoverable *in the same turn*, the loop hands the
    message back and the model tries again, which is why they are worded as
    instructions rather than as complaints.
    """
    goal = " ".join(str(arguments.get("goal") or "").split())
    if not goal:
        raise ToolError("A plan needs a goal: the whole job in one sentence.")
    steps = _plan_steps(arguments.get("steps"))
    if len(steps) < MIN_PLAN_STEPS:
        raise ToolError(
            f"A plan needs at least {MIN_PLAN_STEPS} steps. If this job is one "
            "action, don't plan it: just call the tool that does it."
        )
    if len(steps) > MAX_PLAN_STEPS:
        # Truncating would drop the end of the job silently, which is the
        # failure this whole tool exists to prevent.
        raise ToolError(
            f"That is {len(steps)} steps and a plan may have at most "
            f"{MAX_PLAN_STEPS}. Combine the small ones, or plan the first "
            f"{MAX_PLAN_STEPS} and say what is left when they are done."
        )
    return {
        "type": "run_plan",
        "goal": goal[: skills.MAX_GOAL],
        "steps": steps,
        # What the user is about to watch start. The plan card lists the steps
        # a moment later; this is the chip in the timeline that says the model
        # chose to plan rather than answer.
        "label": f"ph:compass Planned {len(steps)} steps: {_clip(goal, 60)}",
    }


def validate_propose_act(arguments: dict, history: list[dict] | None) -> dict:
    """The proposal `propose_act` hands over, or a ToolError saying what is missing.

    The card itself needs the session, which a handover validator does not
    have: the agent loop sees the `act_proposal` type and runs the tool's
    handler (which writes nothing) so the card is drawn and the turn stops
    there, waiting for Confirm.
    """
    sentence = " ".join(str(arguments.get("sentence") or "").split())
    if not sentence:
        raise ToolError("Say the change in the person's words: remind me to ..., tag the note about ... with ...")
    return {"type": "act_proposal", "sentence": sentence}
