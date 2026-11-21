"""Ask a question, get back BOTH a conversational answer and the raw
matching entries: the two-result design from the original idea doc.

Two flavours:
- POST /chat: one blocking JSON response (simple, used by tests/API)
- POST /chat/stream: NDJSON: metadata + raw results first, then the
  model's thinking and answer as live token deltas (what the UI uses)

Plain `def` so the blocking LLM call runs in FastAPI's threadpool.

**Where the pieces are (audit AR3, gods-1101; L-world-class-634).** This file
is the thin FastAPI layer: each route parses its body and calls
`chat_service` (the blocking turn, the streamed turn and everything they do),
or one of the helper layers below. Tests patch the module that holds the code
(`chat_service`, `chat_said`, ...), not this file. Each layer imports only the
layers before it in this list, never `routes_chat`: `chat_attach` (the
attachments), `chat_request` (the request), `chat_pool` (the note pool),
`chat_recent` (the suggestion rows), `chat_web` (the web), `chat_agent` (the
agent's turn), `chat_said` (the composed answer's lines), `chat_turn` (the
streamed turn), `chat_service` (the chat turn itself; it sits in `api/`
because the helpers it calls do, and `ai/` never imports `api/`).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from tessellate.ai import consent_store
from tessellate.ai import (
    acts,
    followups,
    presets,
    tools,
)
from tessellate.ai.ollama_client import OllamaError
from tessellate.api import chat_extra, chat_service
from tessellate.core import deps, model_gate, private_turn
from tessellate.core.database import (
    AuditLog,
    Entry,
)
from tessellate.core.config import user_now
from tessellate.core.deps import get_session
from tessellate.repo import categories as categories_repo
from tessellate.entry import manager
from tessellate.entry.manager import UNCATEGORISED
from tessellate.api.chat_request import ChatRequest, ChatResponse, CommandRunBody, CompressBody, FollowupBody, RememberBody, ToolExecuteBody, _with_hunks_skipped, _resolve_mode
from tessellate.api.chat_recent import ASK_SURFACE, STARTER_SUGGESTIONS, _about, _asked_key, _fill, _recent_questions
from tessellate.api.chat_agent import _refuse_failed, _refuse_if_off
from tessellate.api import chat_turn


router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/recent", response_model=list[str])
def recent_questions(session: Session = Depends(get_session)) -> list[str]:
    """The last 5 distinct questions, newest first (quick access)."""
    return _recent_questions(session)


@router.delete("/recent")
def forget_recent_question(question: str, session: Session = Depends(get_session)) -> dict:
    """Take one question off the Ask again row (see `_recent_questions`)."""
    marker = manager.log_action(session, "forgot", ASK_SURFACE, detail=question)
    session.commit()
    return {"forgotten": question, "marker_id": marker.id if marker else None}


@router.post("/recent/restore")
def remember_recent_question(body: RememberBody, session: Session = Depends(get_session)) -> dict:
    """Undo `DELETE /chat/recent`: the chip is offered again (INBOX 898).

    Writes a `remembered` row naming the `forgot` one rather than editing the
    log, which is a history.
    """
    marker = session.get(AuditLog, body.marker_id)
    if marker is None or marker.action != "forgot" or marker.entity_type != ASK_SURFACE:
        raise HTTPException(status_code=404, detail="That question was not forgotten.")
    manager.log_action(session, "remembered", ASK_SURFACE, detail=str(marker.id))
    session.commit()
    return {"remembered": marker.detail}


@router.get("/suggestions", response_model=list[str])
def suggestions(session: Session = Depends(get_session)) -> list[str]:
    """Recommended questions: content-aware ones built from the user's own
    categories, falling back to generic starters for an empty notebook."""
    rows = categories_repo.note_counts(session, Entry.is_deleted == False)  # noqa: E712
    categories = [name for name, _count in rows if name != UNCATEGORISED]

    asked = {_asked_key(question) for question in _recent_questions(session)}

    if not categories:
        return _fill(STARTER_SUGGESTIONS, asked)

    # The first four are what this endpoint has always offered, in the order it
    # offered them. The rest are reserves, reached only when one of the four is
    # dropped for being in "Ask again" already, so the row keeps its length
    # instead of losing a chip to the row below it.
    candidates = chat_extra.starter_leads(session, user_now(deps.get_config()).replace(tzinfo=None))
    candidates += [f"What have I saved about {_about(name)}?" for name in categories[:2]]
    # "my notes in General", not "my general": a category is a filing place,
    # and read as a noun after "my" it made starters like "Summarise my
    # general." on the seeded notebook.
    candidates.append(f"Summarise my notes in {categories[0]}.")
    candidates.append("What have I saved recently?")
    candidates += [f"What have I saved about {_about(name)}?" for name in categories[2:6]]
    candidates += [f"Summarise my notes in {name}." for name in categories[1:3]]
    candidates.append("What are my most common topics?")
    return _fill(candidates, asked)


@router.post("/followups", response_model=list[str])
def chat_followups(body: FollowupBody) -> list[str]:
    """Two or three questions to offer under an answer, or [].

    Its own request rather than part of the turn on purpose: this is a second
    model call, and the answer must not wait on it. The UI fires this after the
    turn is on screen and simply renders nothing if it comes back empty, which
    it does on every failure path, including the AI not running at all.
    """
    if model_gate.busy() or chat_turn.save_power():
        # Save power wakes no model for a suggestion; a second call while the person asks the next thing would queue their question behind it (ARCH-16).
        return []
    return followups.suggest_followups(
        body.question,
        body.answer,
        deps.get_model_manager(),
        deps.get_ollama(),
    )


@router.post("/command/run")
def run_command(body: CommandRunBody, session: Session = Depends(get_session)) -> dict:
    """Run what an act's card showed, after Confirm, or take it back (Undo).
    Only the steps `commands.RUNNABLE` names run, each through the agent's own tool door."""
    from tessellate.ai import commands

    if not body.steps:
        raise HTTPException(status_code=400, detail="There is nothing to run.")
    if any(str(step.get("name") or "") not in commands.RUNNABLE for step in body.steps):
        raise HTTPException(status_code=404, detail="That names a step this app does not run from Chat.")
    if consent_store.was_spent(body.consent_id):
        raise HTTPException(status_code=409, detail="That card was already answered.")
    if body.consent_id and not consent_store.peek(body.consent_id):  # expired: the page's steps are not trusted once the parked card is gone
        raise HTTPException(status_code=409, detail="This offer has expired. Ask again to redo it.")
    done = acts.run_confirmed(session, body.steps, body.skipped, body.consent_id)
    return {"ok": done["ok"], "summary": done["summary"], "undo": done["undo"], "open": done.get("open")}


@router.post("", response_model=ChatResponse)
@private_turn.route
def chat(body: ChatRequest, session: Session = Depends(get_session)) -> ChatResponse:
    return chat_service.blocking_turn(body, session)


@router.post("/stream")
@private_turn.route
def chat_stream(body: ChatRequest, session: Session = Depends(get_session)):
    """NDJSON stream. Line types, in order:
    {"type":"status", "stage": "searching"}   (sent immediately, so the
        browser gets a first byte at once instead of waiting on the, often
        cold-start: semantic search; this is what keeps the UI's typing
        indicator alive instead of appearing frozen)
    {"type":"meta", raw_results, search_mode, answered_by}
    {"type":"thinking", "delta": "..."}   (zero or more)
    {"type":"answer", "delta": "..."}     (one or more)
    {"type":"done"}
    """
    # X-Accel-Buffering: no tells reverse proxies (nginx) not to buffer the
    # stream, so tokens reach the browser as they're produced.
    return StreamingResponse(
        chat_service.stream_lines(body, session),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )



@router.get("/commands")
def list_commands() -> dict:
    """The slash commands (`ai/slash.py`): what the Chat box's "/" menu
    lists and `/help` says, from the one registry."""
    from tessellate.ai import slash

    return {"commands": slash.catalogue()}


@router.get("/modes")
def list_modes() -> dict:
    """The response presets, and which one is currently the default (§11).

    Served rather than hard-coded in `app.js` so the picker cannot drift from
    what the server actually does, adding a fourth preset is then a change to
    `ai/presets.py` alone.
    """
    return {
        "modes": [
            {
                "id": preset.id,
                "label": preset.label,
                "description": preset.description,
            }
            for preset in presets.MODES.values()
        ],
        "active": _resolve_mode(None),
    }


@router.get("/tools")
def list_tools() -> list[dict]:
    """The agent-tool catalog for Settings, Tools toggles."""
    return tools.tool_catalog()


@router.post("/compress")
def compress_history(body: CompressBody) -> dict:
    """A summary of these turns, for sending in place of them.

    Returns the text and nothing else, the client decides whether to use it,
    and keeps the original turns either way. Nothing is stored here, and the
    conversation on screen is not touched: this is a *lossless* operation as
    far as the transcript is concerned, and only the model's view narrows.
    """
    try:
        return tools.summarise_turns([(t.question, t.answer) for t in body.history])
    except OllamaError as exc:
        # Offline, or the call itself failed, either way there is no summary
        # to show, distinct from the model answering with nothing (below).
        # The provider's text names the model and the transport's error: log
        # it, and say the one thing the person can act on.
        logging.getLogger("tessellate.chat").warning("chat summary failed", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="The AI isn't available to summarise this chat right now. Check that it is running, then try again.",
        ) from exc
    except tools.ToolError as exc:
        # An empty reply. Better to say nothing happened than to hand back an
        # empty summary the client would send in place of ten real turns.
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/tools/execute")
def execute_confirmed_tool(
    body: ToolExecuteBody, session: Session = Depends(get_session)
) -> dict:
    """Run one registry tool, how the UI executes a destructive call
    after the user clicks Confirm. Only registry tools can run, and the
    result carries the same human label shown in chat."""
    if body.name == "batch":
        calls = [(str(step.get("tool") or ""), step.get("arguments") or {}) for step in body.steps]
        if not calls or any(name not in tools.TOOLS for name, _ in calls):
            raise HTTPException(status_code=404, detail="That undo names a step this app does not have.")
        _refuse_if_off(name for name, _ in calls)
        # Last change first, the way a stack of edits is taken back. Each
        # step's own result is not sent back: the button only needs to know it
        # worked, and a tool's result can carry text written for the model.
        for name, arguments in reversed(calls):
            _refuse_failed(name, tools.execute_tool(session, name, arguments))
        return {"label": f"Undid {len(calls)} changes."}
    if body.name not in tools.TOOLS:
        raise HTTPException(status_code=404, detail=f"There is no tool called '{body.name}'.")
    _refuse_if_off([body.name])
    arguments = _with_hunks_skipped(session, body)  # the guard below checks the card's own arguments
    if why := consent_store.refusal_for_press(body.consent_id, body.name, body.arguments):  # a press spends the card
        raise HTTPException(status_code=409, detail=why)
    result = tools.execute_tool(session, body.name, arguments)
    if "error" in result:
        _refuse_failed(body.name, result)
    #: Named fields only, never the whole result: a tool's result can carry
    #: text written for the model, and CodeQL (#552, #553) follows any
    #: whole-result return to the exception text. The Confirm card reads
    #: `label`; `undo` lets a confirmed change be taken back.
    return consent_store.remember(body.consent_id, {"label": str(result.get("label") or ""), "undo": result.get("undo")})


