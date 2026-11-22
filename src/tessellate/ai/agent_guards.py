"""The per-call guard chain: the checks one tool call passes before it runs.

Moved out of `agent.py` whole (line cap, `tests/test_module_line_caps.py`).
Each guard takes the `_Call` and returns a `_Verdict` (the result the model is
handed in place of running the tool, and the events the person sees) or None
to let the call through; `agent._dispatch_call` runs them in the order set by
`_BEFORE_HANDOVER` and `_AFTER_HANDOVER`. `_hand_over` stays in `agent.py`
because it finishes the turn with `_finish_handover`, which lives there, and
this layer imports nothing from it. `plan_now` lives here because
`_confirm_gate` needs it and `agent.py` imports this module, not the reverse.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from tessellate.ai import tools
from tessellate.ai.agent_policy import (
    _RECOVERY_HINTS,
    _WRITE_TOOLS,
    MAX_PARKED_CONFIRMS,
    MAX_TOOL_FAILURES,
    REPEATED_CALL_NOTE,
    TOOL_EXHAUSTED_NOTE,
    parks_when_tainted,
)
from tessellate.ai.agent_turn import (
    AWAITING_CONFIRMATION,
    _cleared_page,
    _copies_what_was_read,
    _TurnPlan,
    _TurnState,
    all_it_names,
)


def plan_now() -> datetime:
    """The naive local time a plan's steps are read against (dates in a step
    such as "on Friday" resolve on the reader's clock)."""
    from tessellate.core import deps
    from tessellate.core.config import user_now

    return user_now(deps.get_config()).replace(tzinfo=None)


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

