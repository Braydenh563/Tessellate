"""The agent's turn in the stream: its events, its first event, a starter
read, and the stop a client can send.

Moved whole from `routes_chat.py` (audit AR3, gods-1101): the code is
unchanged, and `routes_chat` re-exports every name here that anything
reads, so `routes_chat._agent_events` still works. Imports run one way, down the
layer list in `routes_chat.py`'s docstring, never back to `routes_chat`.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from fastapi import HTTPException

from tessellate.ai import acts, agent, budget as run_budget, commands, consent_store, skill_runner, starter_acts, tools
from tessellate.ai.tools import tool_off
from tessellate.api.chat_request import _StreamRequest, _in_full, _small_model_mode
from tessellate.core import deps
from tessellate.core.logbuffer import safe_value


def _starter_read(req: _StreamRequest, model_ready: bool) -> tuple[str, dict] | None:
    """A popup agent starter the engine answers when no model can (AGENT_SKILLS_REFORM
    "Deepened 2026-10-10" row 1); with a model the agent has it."""
    if model_ready or req.skill or req.body.notes_only:
        return None
    return starter_acts.read(req.question)


def _agent_events(req: _StreamRequest, prepared: dict, tools_provider) -> Iterator[dict]:  # noqa: ANN001
    """The event stream of a skill run or an agent turn for this request.

    Lifted from `_stream_lines` with no behaviour change (audit 2026-10-05,
    ARCH-22: it was 334 lines)."""
    shared = {
        "style": prepared["style"],
        "profile": prepared["profile"],
        "history": req.history,
        "persona_prompt": req.persona_prompt,
    }
    if req.skill:
        # A skill runs step by step, the runner emits the plan, ticks
        # each step, and ends with what changed. Its first event has
        # the same meaning as the agent's, so the fallback below is
        # unchanged.
        agent_events = skill_runner.run_skill(
            req.session,
            req.skill["skill"],
            req.body.skill_inputs or {},
            prepared["notes"],
            req.model_manager,
            req.ollama,
            start_at=req.body.skill_from_step,
            only_step=req.body.skill_only_step,
            step_text=req.body.skill_step_text,
            manual=req.body.skill_manual,
            manual_note=req.body.skill_manual_note,
            small_model=_small_model_mode(),
            # The run's own budget (Brief 13), read from the user's
            # settings here rather than inside the runner so that the
            # runner stays testable without app state and so a caller
            # with its own budget (an eval, a background job) can pass
            # one instead.
            #: The step count goes with it: the token allowance is per
            #: step, and a nine-step skill held to one step's worth is how
            #: a correct run came to stop after three of them.
            #: And the skill's own declared caps on top (Phase E, decision 3).
            budget=_stoppable(run_budget.for_skill(deps.get_config(), req.skill["skill"]), req),
            **shared,
        )
    elif not req.allowed_tools and (off := tool_off.switched_off_line(_in_full(req))):
        #: Said before any model call (L-chat-2), not as a refusal after the model tried.
        agent_events = iter([{"type": "answer", "delta": off}])
    else:
        agent_events = agent.run_agent(
            req.session,
            _in_full(req),
            prepared.get("model_notes", prepared["notes"]),
            req.model_manager,
            tools_provider,
            mode=req.mode,
            allowed_tools=req.allowed_tools,
            images=req.images,
            image_context=req.image_context,
            **shared,
        )
    return agent_events


def _first_agent_event(req: _StreamRequest, agent_events: Iterator[dict]) -> dict | None:
    """The stream's first event, or an answer saying what went wrong if the
    run failed before it could yield one. Lifted from `_stream_lines` (ARCH-22)."""
    # Everything `agent.run_agent`/`skill_runner.run_skill` themselves
    # expect to go wrong (OllamaError, ToolsUnsupportedError) is
    # already caught inside them and turned into a real event, this
    # is the outer boundary, for whatever isn't. Reported directly: a
    # skill run that "failed before even completing the first step
    # ... no answer and no tool call", an exception here had nothing
    # catching it, so it killed the generator and the stream just
    # ended with nothing rendered, no error, the plan card (if any)
    # never even reaching the page. Silence was the bug, not the
    # underlying failure, which is why this doesn't try to guess
    # which failure it was, it says what actually happened and stays
    # on stage instead of vanishing.
    try:
        first = next(agent_events, None)
    except Exception as exc:  # noqa: BLE001  # the outer boundary
        logging.getLogger("tessellate.chat").exception(
            "%s: unhandled error before the first event: %s",
            "skill run" if req.skill else "agent turn",
            exc,
        )
        first = {
            "type": "answer",
            # CodeQL #419, the same finding as #296 one branch over: this
            # arm was written before `safe_value` existed and kept `exc`'s
            # own str(), which can carry a file path or a connection
            # detail out to the browser. The sanitiser the mid-stream arm
            # below already trusts.
            "delta": (
                "Something went wrong before it could start: "
                f"{safe_value(exc)}"
            ),
        }
    return first


def _close_quietly(source) -> None:  # noqa: ANN001
    close = getattr(source, "close", None)
    try:
        if close is not None:
            close()
    except Exception as exc:  # noqa: BLE001 - the turn has ended; nothing waits on this
        logging.getLogger("tessellate.chat").debug("chat: closing the stopped stream failed: %s", exc)


def _stoppable(spend, req):  # noqa: ANN001, ANN202
    """The run's budget, wired to this turn's Stop."""
    spend.stop_event = req.stop
    return spend


def _refuse_if_off(names) -> None:
    """A tool switched off in Settings is refused for that reason. It used to
    reach `_refuse_failed`, whose sentence ("the note may have changed") is
    about a different cause and sent the person looking in the wrong place."""
    if not all(tools.tool_enabled(name) for name in names):
        raise HTTPException(status_code=409, detail="That tool is turned off in Settings, Tools it can use.")


def _refuse_failed(name: str, result: dict) -> None:
    """A failed confirmed call is a 400 with a sentence about the click.
    `result["error"]` is written for the model (it names the tool and its
    arguments), so it goes to the log, not to the person."""
    if "error" not in result:
        return
    logging.getLogger("tessellate.chat").warning(
        "confirmed tool %r failed: %s", safe_value(name, 40), safe_value(result["error"], 300)
    )
    raise HTTPException(
        status_code=400,
        detail="That couldn't be done. The note or item may have changed since you asked, so check it and try again.",
    )


def _undo_steps(undo) -> list[dict]:  # noqa: ANN001
    """A tool's undo (`{tool, arguments}`, or a batch of them) as the steps an Undo row posts."""
    one = undo.get("steps") if isinstance(undo, dict) and undo.get("tool") == "batch" else [undo]
    return [{"name": u["tool"], "arguments": u.get("arguments") or {}} for u in one if isinstance(u, dict) and u.get("tool") in commands.RUNNABLE]


def run_card_events(session, label: str, steps: list[dict], skipped: list[dict], say: dict | None, consent_id: str = "") -> list[dict]:  # noqa: ANN001
    """An act card's steps run, in the card's own words, with Undo: what Confirm and a
    typed yes both show. `consent_id` names the card a typed yes settles."""
    done = acts.run_said(session, label, steps, skipped, say)
    return [
        {"type": "answer", "delta": done["summary"]},
        {"type": "act", "label": label, "steps": steps, "skipped": skipped, "notice": "", "done": True, "settle": bool(consent_id), "consent_id": consent_id,
         "summary": done["summary"], "undo": done["undo"], "open": done.get("open")},
    ]


def _typed_tool_events(session, tool: dict | None, consent_id: str, label: str) -> list[dict] | None:  # noqa: ANN001
    """A typed yes on a parked tool call: the run, with the Undo row and refresh Confirm gives, or None."""
    if not (tool and str(tool.get("name") or "") in tools.TOOLS and tools.tool_enabled(str(tool["name"]))):
        return None
    result = tools.execute_tool(session, str(tool["name"]), tool.get("arguments") or {})
    if "error" in result:
        logging.getLogger("tessellate.chat").warning("typed-confirmed tool %r failed: %s", safe_value(str(tool["name"]), 40), safe_value(result["error"], 300))
        return None
    summary = acts.done_line(str(result.get("label") or label), label)
    steps = [{"name": tool["name"], "arguments": tool.get("arguments") or {}}] if tool["name"] in commands.RUNNABLE else []
    return [
        {"type": "answer", "delta": summary},
        {"type": "act", "label": label, "steps": steps, "skipped": [], "notice": "", "done": True, "settle": True, "consent_id": consent_id,
         "summary": summary, "undo": _undo_steps(result.get("undo"))},
    ]


def consent_events(session, found: dict) -> list[dict]:  # noqa: ANN001
    """The events for a typed yes or no to the card that waits (`ai/consent.py`).

    No drops the card and writes nothing. Yes runs what the server parked under
    the card's id when it was drawn (`ai/consent_store.py`), by the same doors
    Confirm uses (`commands.RUNNABLE` for an act's steps, the registry for a
    parked tool call), with the same Undo and refresh, and settles the card so
    it is not pressed twice. What the page sends is never what runs."""
    proposal = (consent_store.decline if found["verdict"] == "no" else consent_store.take)(found["id"])
    label = str((proposal or {}).get("label") or found["label"])
    what = label[:1].lower() + label[1:]
    if found["verdict"] == "no":
        return [
            {"type": "answer", "delta": f"Cancelled: {what.rstrip('.')}. Nothing was changed."},
            {"type": "act", "cancel": True, "label": label, "consent_id": found["id"]},
        ]
    if proposal and proposal.get("handoff"):
        #: The page's own skill or plan card: the hand-over goes again, already agreed, and the card settles.
        return [
            {"type": "answer", "delta": f"Starting: {what.rstrip('?.')}."},
            {"type": "act", "settle": True, "label": label, "consent_id": found["id"]},
            {**proposal["handoff"], "consented": True},
        ]
    if proposal and proposal.get("steps") and all(str(step.get("name") or "") in commands.RUNNABLE for step in proposal["steps"]):
        return run_card_events(session, label, proposal["steps"], proposal["skipped"], proposal.get("say"), found["id"])
    if (ran := _typed_tool_events(session, (proposal or {}).get("tool"), found["id"], label)) is not None:
        return ran
    return [{"type": "answer", "delta": "That card is no longer open, so nothing was done. Ask again and I will set it up."}]
