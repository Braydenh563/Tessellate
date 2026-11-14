"""Thoughts → note drafts (the writing room).

Write loose thoughts, get a draft, edit it, add more thoughts, repeat until
it's right: then save it as a note like any other.

There's no draft table: the draft lives in the browser until you save it. A
half-finished draft isn't a note, and quietly filling the notebook with them
would be worse than losing one.
"""

from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.ai import composer_mermaid, diagram_ask, drafter, no_model_text
from tessellate.api.chat_agent import stop_when_gone
from tessellate.core import activity, deps
from tessellate.core.database import Entry

router = APIRouter(prefix="/drafts", tags=["drafts"])

#: How many notes may be handed to one pass. Six is what fits beside a draft
#: in a small model's window at `drafter.SOURCE_CHARS` each, and it is also
#: about as many sources as a person picks before they are really asking for
#: a search instead.
MAX_SOURCES = 6


class ComposeBody(BaseModel):
    # What the user has just typed. Empty is allowed when they only want the
    # model to act on a one-off instruction against the existing draft.
    thoughts: str = Field(default="", max_length=8000)
    # The draft as it stands, including any edits the user made by hand.
    draft: str = Field(default="", max_length=20000)
    # An optional steer for this pass only ("make it shorter").
    instruction: str = Field(default="", max_length=300)
    # Which job this is: draft, continue, rewrite, expand, bullets. Validated
    # in `drafter.build_messages`, which drops anything it does not know
    # rather than interpolating it into a prompt.
    kind: str = Field(default="", max_length=20)
    tone: str = Field(default="", max_length=20)
    length: str = Field(default="", max_length=20)
    # Notes from the notebook to write *from*. Ids, not text: the client
    # should not be the one deciding what a note says.
    source_ids: list[int] = Field(default_factory=list, max_length=MAX_SOURCES)


def _sources(session: Session, note_ids: list[int]) -> list[dict]:
    """The notes the user picked, in the order they picked them.

    Binned and private notes are skipped, the same guard `_attached_notes`
    keeps in routes_chat.py and for the same reason: a client-supplied id
    list is the one path into a prompt that never went through a tool's own
    checks, so attaching a binned note would quietly resurrect content the
    user has thrown away, and a private one would put writing the private
    notebook rule exists to hold back in front of the model.
    """
    found: list[dict] = []
    for note_id in list(dict.fromkeys(note_ids))[:MAX_SOURCES]:  # de-duplicate, keep order
        entry = session.get(Entry, note_id)
        if entry is None or entry.is_deleted or entry.is_private:
            continue
        #: `written` dates a note in the write-up the composer makes with no
        #: model (`composer_write.write_up`); the model's prompt ignores it.
        written = entry.created_at.date().isoformat() if entry.created_at else ""
        found.append({"title": "", "content": entry.content or "", "written": written})
    return found


class TitleBody(BaseModel):
    draft: str = Field(min_length=1, max_length=20000)


def _with_diagram(body: ComposeBody, result: dict) -> dict:
    """A diagram pass (1546 P3, D8) also says what the diagram builder needs:
    `diagram`, the Mermaid source in the reply, or `diagram_error`, one
    sentence for why the reply holds none. The Writing room reads `draft`
    as before; the builder never inserts a reply it could not read."""
    if body.kind != "diagram":
        return result
    #: A pass that did nothing (offline, nothing to draw) answers with its own message.
    if result.get("message") and not result.get("said"):
        return {**result, "diagram": "", "diagram_error": result["message"]}
    source, why = composer_mermaid.source_of(result.get("draft") or "")
    return {**result, "diagram": source, "diagram_error": why}


@router.post("/compose")
def compose_draft(
    body: ComposeBody, session: Session = Depends(deps.get_session)
) -> dict:
    """Write or revise a draft from thoughts.

    Kept beside `/compose/stream`, which is what the writing room calls: this
    is the fallback for a client that cannot open a stream, and the shape most
    of this feature's tests speak.
    """
    if not body.thoughts.strip() and not body.draft.strip() and not body.source_ids:
        raise HTTPException(status_code=400, detail="Write a thought first.")

    ollama = deps.get_ollama()
    if not ollama.is_running():
        #: With no model the composer does what it can by rule (INBOX 1466).
        return _with_diagram(body, drafter.composed(
            body.thoughts, body.draft, instruction=body.instruction, kind=body.kind,
            tone=body.tone, length=body.length, sources=_sources(session, body.source_ids),
        ))
    text, note = drafter.compose(
        body.thoughts,
        body.draft,
        deps.get_model_manager().for_feature("writing"),
        ollama,
        instruction=body.instruction,
        kind=body.kind,
        tone=body.tone,
        length=body.length,
        sources=_sources(session, body.source_ids),
    )
    #: Asked, not inferred from a string: see `drafter.was_offline`.
    offline = drafter.was_offline(note)
    return _with_diagram(body, {
        "draft": text,
        # Distinguishes "the model reasoned" from "the model wasn't there".
        "thinking": None if offline else note,
        "message": note if offline else "",
        "ollama_running": not offline,
    })


@router.post("/compose/stream")
def compose_draft_stream(
    body: ComposeBody, session: Session = Depends(deps.get_session)
) -> StreamingResponse:
    """The same pass as `/compose`, delivered as it is written.

    Newline-delimited JSON, the same wire format and the same no-buffering
    headers the chat and help streams use, so one reader in the client is
    taught all three. The sources are resolved here, before the generator
    starts: the session is closed by the time the body is streamed.
    """
    if not body.thoughts.strip() and not body.draft.strip() and not body.source_ids:
        raise HTTPException(status_code=400, detail="Write a thought first.")

    sources = _sources(session, body.source_ids)

    def lines():
        for event in drafter.compose_stream(
            body.thoughts,
            body.draft,
            deps.get_model_manager().for_feature("writing"),
            deps.get_ollama(),
            instruction=body.instruction,
            kind=body.kind,
            tone=body.tone,
            length=body.length,
            sources=sources,
        ):
            yield json.dumps(event) + "\n"

    stop = activity.StopEvent()
    return StreamingResponse(
        stop_when_gone(stop, activity.tracked_stream("generation", "Drafting", lines(), stop_event=stop, stopped_line=activity.STOPPED_DONE)),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


class DiagramNodeIn(BaseModel):
    id: str = Field(min_length=1, max_length=60)
    text: str = Field(default="", max_length=200)
    shape: str = Field(default="rect", max_length=20)
    group: str | None = Field(default=None, max_length=60)


class DiagramEdgeIn(BaseModel):
    model_config = {"populate_by_name": True}
    source: str = Field(alias="from", max_length=60)
    to: str = Field(max_length=60)
    label: str = Field(default="", max_length=200)


class DiagramGroupIn(BaseModel):
    id: str = Field(min_length=1, max_length=60)
    title: str = Field(default="", max_length=200)
    parent: str | None = Field(default=None, max_length=60)


class DiagramModelIn(BaseModel):
    """The D1 model as the builder holds it, capped at the pane's own limits (`diagram_ask.MAX_BLOCKS`)."""

    nodes: list[DiagramNodeIn] = Field(default_factory=list, max_length=diagram_ask.MAX_BLOCKS)
    edges: list[DiagramEdgeIn] = Field(default_factory=list, max_length=600)
    subgraphs: list[DiagramGroupIn] = Field(default_factory=list, max_length=60)


class KindBlockIn(BaseModel):
    """One block of a mind map, timeline or sequence as the builder flattens it (`diagram_ask_kinds`)."""

    model_config = {"populate_by_name": True}
    uid: str = Field(min_length=1, max_length=60)
    type: str = Field(max_length=2)
    text: str = Field(default="", max_length=200)
    parent: str | None = Field(default=None, max_length=60)
    id: str | None = Field(default=None, max_length=60)
    source: str | None = Field(default=None, alias="from", max_length=60)
    to: str | None = Field(default=None, max_length=60)


class KindModelIn(BaseModel):
    nodes: list[KindBlockIn] = Field(default_factory=list, max_length=diagram_ask.MAX_BLOCKS)


class DiagramAskBody(BaseModel):
    ask: str = Field(max_length=diagram_ask.ASK_CHARS)
    model: DiagramModelIn = Field(default_factory=DiagramModelIn)
    #: The other kinds (L-documents-27): the kind and its flat blocks; absent is the flowchart.
    kind: Literal["flowchart", "mindmap", "timeline", "sequence"] = "flowchart"
    kind_model: KindModelIn = Field(default_factory=KindModelIn)


@router.post("/diagram-ask")
def diagram_ask_ops(body: DiagramAskBody) -> dict:
    """An ask in the diagram builder as operations on its model (dgai-1110 F1 to F5): by rule with no model, from
    the model when it runs, the same five verbs either way and every op checked against the model."""
    if not body.ask.strip():
        raise HTTPException(status_code=400, detail="Write what to change first.")
    ollama = deps.get_ollama()
    if body.kind != "flowchart":
        from tessellate.ai import diagram_ask_kinds  # lazy: the flowchart's ask does not pay for it

        blocks = body.kind_model.model_dump(by_alias=True, exclude_none=True)
        if not ollama.is_running():
            return diagram_ask_kinds.by_rule(body.kind, body.ask, blocks)
        return diagram_ask_kinds.with_model(body.kind, body.ask, blocks, deps.get_model_manager().for_feature("writing").chat_model(), ollama)
    model = body.model.model_dump(by_alias=True)
    if not ollama.is_running():
        return diagram_ask.by_rule(body.ask, model)
    return diagram_ask.with_model(body.ask, model, deps.get_model_manager().for_feature("writing").chat_model(), ollama)


@router.post("/title")
def draft_title(body: TitleBody) -> dict:
    """A suggested title for a finished draft ("" when unavailable). With no
    model it is taken from the draft's own words (`no_model_text.draft_title`,
    owner-1026b K3) and `by` says so."""
    ollama = deps.get_ollama()
    if not ollama.is_running():
        return {"title": no_model_text.draft_title(body.draft), "by": "composer"}
    return {
        "title": drafter.suggest_title(body.draft, deps.get_model_manager().for_feature("writing"), ollama)
    }
