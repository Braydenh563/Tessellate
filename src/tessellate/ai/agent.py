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
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime

from sqlalchemy.orm import Session

from tessellate.ai import act_registry, consent_store, librarian, tools
from tessellate.ai import budget as run_budget
from tessellate.ai.agent_policy import (
    _CLAIMED_ACTIONS,
    _RECOVERY_HINTS,
    _WRITE_TOOLS,
    BUDGET_EXHAUSTED,
    CLAIM_RETRY_NUDGE,
    EARNED_ROUNDS,
    EMPTY_ROUND_NUDGE,
    FORCED_PROSE_NUDGE,
    MAX_PARKED_CONFIRMS,
    MAX_ROUNDS,
    MAX_TOOL_FAILURES,
    PRIVATE_BLOCKED,
    REPEATED_CALL_NOTE,
    REPLY_CAP_NOTE,
    THINKING_CARRIED_CHARS,
    TOOL_EXHAUSTED_NOTE,
    TOOL_RESULT_BUDGET_CHARS,
    TURN_ROW_ANSWER,
    TURN_ROW_RECHECK,
    TURN_ROW_RUNNING,
    TURN_ROW_WRAP_UP,
    UNACTED_INTENT_NUDGE,
    WRAP_UP_NUDGE,
    _change_category_name,
    _change_document_id,
    _change_note_id,
    _change_reminder_id,
    _check_sources,
    _hosts_named,
    _labelled,
    _recovery_hint,
    _result_urls,
    _TurnCard,
    announces_unacted_tool,
    claims_a_write,
    parks_when_tainted,
    reads_outside,
    unsupported_claims,
)
from tessellate.ai.agent_turn import (
    AWAITING_CONFIRMATION,
    all_it_names,
    from_outside as _from_outside,
    _cleared_page,
    _copies_what_was_read,
    _first_round_tools,
    _fit_result,
    _prefetch_outbound,
    _prepare_turn,
    _requires_a_call,
    _round_stream,
    _tool_event,
    _tool_events,
    _TurnPlan,
    _TurnState,
    recovery_for,
)
from tessellate.ai.model_manager import ModelManager
from tessellate.ai.ollama_client import (
    OllamaClient,
    OllamaError,
    ToolsUnsupportedError,
)
from tessellate.ai.provider import tools_unsupported_message
from tessellate.core import private_turn


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
    return _plans().edit_diff(
        str((undo.get("arguments") or {}).get("content") or ""), str(arguments["content"])
    )


def _count_call() -> None:
    """Charge one tool call to the run this turn belongs to, if any (Phase E)."""
    spend = run_budget.current()
    if spend is not None:
        spend.count_call()


def _query_said(name: str, arguments: dict) -> list[dict]:
    """A web search's words, said before they leave this computer (audit 1030 A2)."""
    query = (
        str(arguments.get("query") or "")[:200]
        if name == "web_search" and isinstance(arguments, dict)
        else ""
    )
    return (
        [
            {
                "type": "status",
                "stage": "web",
                "query": query,
                "said": f"searching the web for “{query}”",
            }
        ]
        if query
        else []
    )


def _record_call(
    state: _TurnState, name: str, arguments: dict, result: dict, undo: dict | None, signature: tuple
) -> dict | None:
    """The turn's ledgers after a call, and the change a write made (None for a read or a failure)."""
    ok = "error" not in result
    change = None
    if ok and signature not in state.done_calls:
        # Something new worked. That is what buys another round,
        # see EARNED_ROUNDS. Reads and writes both count: paging
        # through a notebook to find the right note is the work,
        # not a preamble to it.
        state.done_calls.add(signature)
        state.progressed = True
    if ok and name not in _WRITE_TOOLS:
        # Its result is now in the messages above, and stays valid
        # until something writes.
        state.fresh_reads.add(signature)
    if ok and reads_outside(name):
        state.outside = True
    if ok and name == "web_search":
        state.result_pages |= _result_urls(result)
    if ok and name in _WRITE_TOOLS:
        state.did_write = True
        state.ran_writes.add(name)
        if name == "create_note" and arguments.get("tags"):
            state.implied.add("tag_note")
        # The notebook just changed, so every read before now may be stale:
        # re-reading is legitimate work after a write, not a loop. Not
        # `done_calls` (the earned-round ledger: clearing it would let one
        # repeated write buy a fresh round each time, the loop EARNED_ROUNDS
        # starves). Not `failed_calls` either: a call that failed on its own
        # arguments (a bad note id, a malformed date) fails again for the same
        # reason after an unrelated write, and forgetting it hands the model
        # back the infinite retry `_RECOVERY_HINTS` exists to break.
        state.fresh_reads.clear()
        change = {
            "tool": name,
            "label": result.get("label") or name,
            "diff": _change_diff(name, arguments, undo),
            "note_id": _change_note_id(name, result),
            "document_id": _change_document_id(name, result),
            "reminder_id": _change_reminder_id(name, result),
            "category_name": _change_category_name(name, result),
            "undo": consent_store.signed(undo),
            #: Redo runs this same call again, so it needs the server's tag too (L-world-class-28).
            "redo_sig": consent_store.sign_call(name, arguments),
        }
    return change


def _with_advice(state: _TurnState, name: str, signature: tuple, result: dict) -> dict:
    """A failed call's result with advice beside the error, and the failure counted."""
    repeated = signature in state.failed_calls
    state.failed_calls.add(signature)
    exhausted = state.count_failure(name) >= MAX_TOOL_FAILURES
    # The exhausted note is said on the failure that *reaches* the cap, not
    # only on the blocked call after it, so the model does not spend one more
    # round discovering the rule.
    advice = (
        TOOL_EXHAUSTED_NOTE
        if exhausted
        else REPEATED_CALL_NOTE
        if repeated
        else _recovery_hint(name, str(result["error"]))
    )
    return {**result, "what_to_do": advice}


def _run_and_record(
    session: Session, plan: _TurnPlan, state: _TurnState, name: str, arguments: dict
) -> Iterator[dict]:
    """Run a call every guard let through, record what it did on the turn's
    state, yield its tool event, and return the result for the model.

    `_dispatch_call`'s last branch, lifted with no behaviour change (ARCH-22).
    Order: the taint, the ledgers, the write's change, the advice, the event.
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
    signature = (name, json.dumps(arguments, sort_keys=True))
    change = _record_call(state, name, arguments, result, undo, signature)
    if "error" in result:
        result = _with_advice(state, name, signature, result)
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

    out = {
        k: question_noise.strip_strays(v) if isinstance(v, str) and "\n" not in v else v
        for k, v in arguments.items()
    }
    if name == "search_notes" and not str(out.get("query") or "").strip():
        asked = next((m.get("content") for m in reversed(messages) if m.get("role") == "user"), "")
        out["query"] = question_noise.topic_of(asked if isinstance(asked, str) else "") or out.get(
            "query", ""
        )
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
    state.messages.append(
        {"role": "tool", "tool_name": name, "content": json.dumps({"error": ONE_OPTION_NOTE})}
    )
    return False


def _handoff_refused(
    state: "_TurnState", name: str, signature: tuple, exc: Exception
) -> Iterator[dict]:
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
            "content": json.dumps({"error": str(exc), "what_to_do": recovery_for(name)}),
        }
    )
    yield {
        "type": "tool",
        "label": f"ph:warning couldn't {name.replace('_', ' ')}",
        "ok": False,
        "error": str(exc),
    }
    return False


@dataclass(slots=True)
class _Call:
    """One tool call as the guards below see it: the turn's plan and state,
    and the call's own name, arguments and signature, worked out once."""

    session: Session
    plan: _TurnPlan
    state: _TurnState
    call: dict
    name: str
    arguments: dict
    #: `(name, arguments as sorted JSON)`: the same call, however the model
    #: ordered its keys.
    signature: tuple
    spec: Any

    def refuse(
        self, error: str, what_to_do: str, label: str, shown: str | None = None, **extra: Any
    ) -> tuple[dict, list[dict]]:
        """What a guard says: the result the model is handed in place of running
        the tool, and the one failed step the person sees (`shown` when it is
        worded differently from the model's own error)."""
        label = f"ph:{label}".replace("{}", self.name.replace("_", " "))
        event = {"type": "tool", "label": label, "ok": False, "error": shown or error, **extra}
        return {"error": error, "what_to_do": what_to_do}, [event]

    def failed(self) -> None:
        """Remember this exact call failed, and count it against the tool."""
        self.state.failed_calls.add(self.signature)
        self.state.count_failure(self.name)


#: What a guard decides: the result the model is handed in place of running
#: the tool, and the events the person sees.
_Verdict = tuple[dict, list[dict]]


def _barred(c: _Call) -> _Verdict | None:
    """A run trying to start a run. Refused with the reason, not silently: the
    model asked for this because it has decided the job is bigger than one
    step, and the useful answer is "you are already inside the mechanism you
    are reaching for"."""
    if c.name not in c.plan.barred:
        return None
    c.failed()
    return c.refuse(f"{c.name} cannot be used inside a run", _RECOVERY_HINTS["already_running"], "warning {} isn't available here")


def _not_permitted(c: _Call) -> _Verdict | None:
    """The allowlist is a safety property, not only a prompt: a model that
    calls a tool it was never offered does not get to run it just because the
    registry has one by that name."""
    if c.plan.permitted is None or c.name in c.plan.permitted:
        return None
    hint = REPEATED_CALL_NOTE if c.signature in c.state.failed_calls else _RECOVERY_HINTS["not_in_skill"]
    c.failed()
    return c.refuse(f"{c.name} is not part of this skill's tools", hint, f"warning {c.name} isn't part of this skill")


def _unreadable_arguments(c: _Call) -> _Verdict | None:
    """The JSON did not read even leniently (`provider.loads_lenient`). Said as
    that, with a shape to copy: running the tool with `{}` told the model
    "missing something" and it retried the same JSON."""
    if c.spec is None or c.call.get("invalid_arguments") is None:
        return None
    c.failed()
    return c.refuse(
        f"{c.name}: the arguments were not valid JSON, so nothing ran",
        f"Call {c.name} again with its arguments as one JSON object, for example {tools.example_arguments(c.name)}.",
        "warning {}, arguments unreadable",
        tool=c.name,
        arguments={"unreadable": c.call["invalid_arguments"]},
    )


def _hand_over(c: _Call, history: list[dict] | None) -> Iterator[dict]:
    """`ask_user` and `run_skill`. The turn stops here, and in both cases that
    is the feature rather than a limitation: the model asked because it does
    not know what to do next, or it handed the job to a skill that will do it
    step by step. Carrying on after either would mean carrying on with the
    guess the handover exists to avoid.

    No state is parked on the server. The user's choice, or the skill run, is
    sent as the next message, which means it arrives through the ordinary
    history the model already reads: nothing to expire, nothing to lose on a
    reload, and the exchange is visible in the saved conversation like any
    other. Returns True when the turn is over."""
    try:
        handover = tools.handoff_event(c.name, c.arguments, history)
    except tools.ToolError as exc:
        return (yield from _handoff_refused(c.state, c.name, c.signature, exc))
    return (yield from _finish_handover(c.session, c.plan, c.state, c.name, c.arguments, handover))


def _confirm_gate(c: _Call) -> _Verdict | None:
    """A call that needs the person's say-so is parked for them, never run: a
    destructive tool, nor a tool that reaches out once the turn has read from
    outside. The confirm card is the honest signal, so it counts as an action
    (the "nothing happened" safety net does not fire).

    **A destructive tool cannot paper the turn with confirm cards.** Parking
    hands the model `AWAITING_CONFIRMATION` rather than a result, which is
    honest but is not a *stop*: a model that has misread the job re-parks the
    same tool with fresh arguments, and every round is another card in front
    of the user for something they never asked for. A dozen covers a genuine
    "make these three notes" turn (every write waits now, owner 2026-11-10); past that the model is guessing, and guessing
    at destructive calls is where this app should be least willing to keep up."""
    if c.spec is None:
        return None
    outside = c.state.tainted and parks_when_tainted(c.name) and not _cleared_page(c.state, c.name, c.arguments)
    if not (tools.needs_confirm(c.name, c.arguments, c.state.approved) or outside):
        return None
    if (whole := all_it_names(c.session, c.state, c.name, c.arguments, plan_now)) is not None:
        return whole
    waiting = c.state.parked.get(c.name, 0)
    if waiting >= MAX_PARKED_CONFIRMS:
        c.state.count_failure(c.name)
        return c.refuse(
            f"{c.name} is already waiting for the user's approval {waiting} times in this turn. "
            "Nothing more can be queued for them.",
            "Stop. The user has to approve what is already waiting before anything else destructive "
            "can be prepared. Tell them what is queued and why, and do not call this tool again.",
            "prohibit {}, too many waiting for approval",
        )
    c.state.did_write = True
    c.state.ran_writes.add(c.name)
    c.state.implied |= {"tag_note"} if c.name == "create_note" and c.arguments.get("tags") else set()  # the card carries the tags
    c.state.parked[c.name] = waiting + 1
    label = tools.confirm_label(c.name, c.arguments, c.session)
    return AWAITING_CONFIRMATION, [{"type": "confirm", "name": c.name, "arguments": c.arguments, "label": label}]


def _tool_spent(c: _Call) -> _Verdict | None:
    """**The tool is spent for this turn.** Unlike the signature check below,
    this fires however much the arguments change, which is the whole point:
    the loop it was written for produced fresh wrong arguments every round (see
    `tool_failures`). Blocked *before* execution, so a tool that writes cannot
    land a change on a fourth guess either."""
    failures = c.state.tool_failures.get(c.name, 0)
    if failures < MAX_TOOL_FAILURES:
        return None
    return c.refuse(
        f"{c.name} has failed {failures} times in this turn and is no longer available for it",
        TOOL_EXHAUSTED_NOTE,
        "prohibit {}, stopped after repeated failures",
    )


def _repeated_failure(c: _Call) -> _Verdict | None:
    """The model is looping on a broken call: intercepted before execution.
    Counted as a failure too, so a model that alternates between repeating a
    call and inventing new arguments for the same tool still reaches
    MAX_TOOL_FAILURES rather than ping-ponging between the two interceptions
    for ever."""
    if c.signature not in c.state.failed_calls:
        return None
    c.state.count_failure(c.name)
    return c.refuse(
        f"You already called {c.name} with these exact arguments and it failed. You must try a "
        "different approach, change your arguments, or stop and ask the user.",
        REPEATED_CALL_NOTE,
        "warning {}, repeated failure",
        "Repeated failure intercepted",
    )


def _note_copy(c: _Call) -> _Verdict | None:
    if c.name != "create_note" or not _copies_what_was_read(c.arguments, c.state.messages, c.state.did_write):
        return None
    return c.refuse(
        "That note already exists: this is a copy of a note you read or changed this turn.",
        "Do not make a new note. Tell the user what you did to the existing note.",
        "warning create note, a copy of an existing note",
        "Copy of an existing note intercepted",
    )


def _repeated_write(c: _Call) -> _Verdict | None:
    """A write that already succeeded this turn is not run a second time."""
    if c.signature not in c.state.done_calls or c.name not in _WRITE_TOOLS:
        return None
    return c.refuse(
        f"You already called {c.name} with these exact arguments earlier in this turn and it succeeded. "
        "Do not run the same write tool twice with the same arguments.",
        "Move on to the next step of your plan.",
        "warning {}, already done",
        "Duplicate write intercepted",
    )


def _repeated_read(c: _Call) -> _Verdict | None:
    """*"note's context in full, after no changes."* Re-running a read is not
    merely wasted time: the result is identical and gets appended to the prompt
    a second time, so the round that repeats a read costs the window twice and
    brings back nothing. A pointer is cheaper than the data by an order of
    magnitude and says the one thing the model needs to hear: you already have
    this, move on. `fresh_reads` is emptied whenever a write succeeds, so this
    can never serve a stale read of something the turn itself just changed,
    which is the only way a cache here could produce a wrong answer rather
    than a slow one."""
    if c.signature not in c.state.fresh_reads:
        return None
    note = (
        f"You already called {c.name} with these exact arguments. The information was provided in "
        "your previous tool calls above. Please refer to your chat history to find it, rather than "
        "running the tool again, and move on."
    )
    return {"already_done": True, "note": note}, [
        {"type": "tool", "label": f"↩︎ {c.name.replace('_', ' ')}, already read", "ok": True}
    ]


#: The guards in the order they must run, which is the order of precedence: an
#: unusable call is refused before a handover, and a handover before the
#: approval, spent-tool and repeat checks (a copy of a note is refused before it asks).
_BEFORE_HANDOVER = (_not_permitted, _unreadable_arguments)
_AFTER_HANDOVER = (_note_copy, _confirm_gate, _tool_spent, _repeated_failure, _repeated_write, _repeated_read)


def _first_verdict(c: _Call, guards: tuple) -> _Verdict | None:
    return next((v for v in (guard(c) for guard in guards) if v is not None), None)


def _hold_result(plan: _TurnPlan, state: _TurnState, name: str, result: dict) -> None:
    """Put a tool's result in front of the model, fitted to what is left of the
    turn's budget. Someone else's words in the result (a note's body, a page's
    text, a snippet) go to the model fenced as quoted data (`fence`, INBOX
    430); the app's own fields (`what_to_do`, labels, ids) do not."""
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
    state.messages.append({"role": "tool", "tool_name": name, "content": payload})


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

    Lifted out of `run_agent`'s round loop with no behaviour change (WORLD_CLASS_PLAN
    A5), then split by guard (cc-1101). The order of the guards is load-bearing:
    see `_BEFORE_HANDOVER` and `_AFTER_HANDOVER`.
    """
    name = call["name"]
    arguments = _tidied_arguments(name, call.get("arguments") or {}, state.messages)
    signature = (name, json.dumps(arguments, sort_keys=True))
    c = _Call(session, plan, state, call, name, arguments, signature, tools.TOOLS.get(name))
    barred = _barred(c)
    if barred is not None:
        # The refusal is the whole message, unfitted: there is no result to size.
        result, events = barred
        state.messages.append({"role": "tool", "tool_name": name, "content": json.dumps(result)})
        yield from events
        return False
    verdict = _first_verdict(c, _BEFORE_HANDOVER)
    if verdict is None and c.spec is not None and c.spec.ends_turn:
        return (yield from _hand_over(c, history))
    verdict = verdict or _first_verdict(c, _AFTER_HANDOVER)
    if verdict is None:
        result = yield from _run_and_record(session, plan, state, name, arguments)
    else:
        result, events = verdict
        yield from events
    _hold_result(plan, state, name, result)
    return False


def _wrap_up_round(
    ollama, agent_model: str, mode, state: _TurnState, card: _TurnCard, show_plan: bool
) -> Iterator[dict]:  # noqa: ANN001
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


def _round_tools(
    question: str, plan: "_TurnPlan", state: _TurnState, loop: _Loop, session: Session
) -> tuple[bool, list[dict]]:
    required = (
        (loop.round_number == 0 or loop.retry_forced)
        and plan.tier.force_first_call
        and _requires_a_call(question, plan)
    )
    first = loop.round_number == 0 or (loop.retry_forced and required)
    tools = (
        _first_round_tools(question, plan, state.offered, required, session)
        if first
        else state.offered
    )
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
                logging.getLogger("tessellate.agent").info(
                    "reply cap: %s-tier round cut at %d chars", tier_name, len(said)
                )
                yield {"type": "answer", "delta": REPLY_CAP_NOTE}
                got.reply = {"content": said, "tool_calls": [], "streamed": True}
                break
        elif "final" in piece:
            got.reply = piece["final"]


def _unsupported_events(
    card: _TurnCard, agent_model: str, exc: ToolsUnsupportedError
) -> Iterator[dict]:
    # INBOX 272 part 1: named here, once, so every caller that forwards this
    # event (routes_chat.py, skill_runner.py) shows the same remedy instead of
    # dropping it (see tools_unsupported_message's own docstring).
    yield from card.end_round(TURN_ROW_RUNNING, "failed", "the model cannot use tools")
    yield {
        "type": "unsupported",
        "model": agent_model,
        "message": tools_unsupported_message(agent_model, getattr(exc, "declared", True)),
    }


def _model_died_events(
    card: _TurnCard, agent_model: str, exc: OllamaError, streamed_any: bool
) -> Iterator[dict]:
    # Mid-answer death: say so, but don't wipe what already streamed.
    # `offline: True` alongside the normal answer shape (Tier 1 section 3): an
    # ordinary chat turn renders this like any other answer, but skill_runner
    # cannot tell this boilerplate from a real answer without it, and was
    # ticking the step "done" and repeating the identical failure on every
    # later step. It only ever checks the flag's truthiness, never the text.
    # Logged too, so the failure reaches Settings -> Logs and not only the
    # chat bubble (librarian.model_error_message's docstring has the history).
    logging.getLogger("tessellate.chat").warning(
        "agent: model call failed for %r: %s", agent_model, exc
    )
    prefix = "\n\n" if streamed_any else ""
    yield {
        "type": "answer",
        "delta": f"{prefix}{librarian.model_error_message(agent_model, exc)}",
        "offline": True,
    }
    yield from card.end_round(TURN_ROW_RUNNING, "failed", "the model stopped answering")


def _stream_round(
    ollama,
    plan: "_TurnPlan",
    state: _TurnState,
    loop: _Loop,
    question: str,
    mode,
    session: Session,
    card: _TurnCard,
):  # noqa: ANN001
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


def _nudge_empty(
    state: _TurnState, loop: _Loop, card: _TurnCard, reply: dict, answer: str, required: bool
):
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
    if not (
        required
        and answer
        and not loop.called_any
        and not loop.nudged_empty
        and not loop.nudged_intent
    ):
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


def _nudge_claim(
    state: _TurnState, loop: _Loop, card: _TurnCard, answer: str, unsupported: list[str]
):
    """**Reflect and retry: a claimed act is asked for once** (INBOX 527,
    Qwen2.5-1.5B): "Make a note: buy oat milk" got "I've made a new note for
    you" and no call. The model is told what it claimed and which tool does it,
    once, while it still has a round; the heads-up is what is left when the
    retry does not do it either, checked against everything said this turn."""
    offered = {t["function"]["name"] for t in state.offered}
    needed = [
        tool
        for label, _verb, needs in _CLAIMED_ACTIONS
        if label in unsupported
        for tool in sorted(needs)
        if tool in offered
    ]
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
    if not state.did_write and claims_a_write(answer):
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


def _settle_answer(
    state: _TurnState, loop: _Loop, card: _TurnCard, reply: dict, required: bool, show_plan: bool
):
    """A round with no tool call: this text IS the final answer. True when the
    turn is over, False when a nudge asked for another round."""
    answer = reply.get("content", "").strip()
    if (yield from _nudge_empty(state, loop, card, reply, answer, required)):
        return False
    # It has usually streamed already; send it only if the tool-call gate held it back.
    if not reply.get("streamed") and answer:
        yield {"type": "answer", "delta": answer}
    if (yield from _nudge_prose(state, loop, card, answer, required)) or (
        yield from _nudge_intent(state, loop, card, answer)
    ):
        return False
    # Safety net: a claim to have saved/created something when no write tool
    # ran is a hallucination; say so rather than let the user believe a note
    # exists that doesn't.
    unsupported = unsupported_claims(
        f"{loop.said_before}{answer}", state.ran_writes | state.implied
    )
    if (yield from _nudge_claim(state, loop, card, answer, unsupported)):
        return False
    yield from _claim_notice(state, answer, unsupported)
    yield from _check_sources(
        f"{loop.said_before}{answer}", state.messages, loop.called_any and show_plan
    )
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


def _dispatch_round(
    session: Session,
    plan: "_TurnPlan",
    state: _TurnState,
    card: _TurnCard,
    calls: list[dict],
    history,
):  # noqa: ANN001
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


def _exhausted_events(
    ollama,
    plan: "_TurnPlan",
    state: _TurnState,
    loop: _Loop,
    card: _TurnCard,
    spend,
    mode,
    show_plan: bool,
    exhausted_note,
):  # noqa: ANN001
    # Out of rounds with tools still being called: the job is unfinished, and
    # saying so is the honest end. The `limit` event is what distinguishes this
    # from an answer: the skill runner marks the step stalled rather than
    # ticking it off, and the chat UI offers Continue instead of making the
    # user type "carry on".
    yield {
        "type": "limit",
        "reason": "rounds",
        "rounds": loop.round_number + 1,
        "wrote": sorted(state.ran_writes),
    }
    wrapped = ""
    if exhausted_note is None and not (spend is not None and spend.exceeded()):
        wrapped = yield from _wrap_up_round(ollama, plan.agent_model, mode, state, card, show_plan)
    yield {
        "type": "answer",
        "delta": exhausted_note
        or (
            ("\n\n" if wrapped.strip() else "") + "I stopped after "
            f"{loop.round_number + 1} rounds of tool calls, here's where things "
            "stand. Continue and I'll pick up from here."
        ),
    }


def _blocked_for_turn(
    blocked_tools: frozenset[str] | set[str] | None,
) -> frozenset[str] | set[str] | None:
    """The tools a turn may not call: the caller's, plus the private set while a private turn runs."""
    return (
        (frozenset(blocked_tools or ()) | PRIVATE_BLOCKED)
        if private_turn.active()
        else blocked_tools
    )


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
        blocked_tools=_blocked_for_turn(blocked_tools),
        max_rounds=max_rounds,
        earned_rounds=earned_rounds,
        mode=mode,
        use_utility_model=use_utility_model,
        images=images,
        model_override=model_override,
        image_context=image_context,
    )
    state = _TurnState(
        messages=plan.messages,
        offered=plan.offered,
        named_hosts=_hosts_named(question),
        approved=approved,
        asked=question or "",
    )
    state.outside = _from_outside(notes)
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
    yield from _exhausted_events(
        ollama, plan, state, loop, card, spend, mode, show_plan, exhausted_note
    )
