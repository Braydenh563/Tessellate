"""Thoughts → note drafts (the writing room).

Write loose thoughts, get a draft, edit it, add more thoughts, repeat until
it's right: then save it as a note like any other.

There's no draft table: the draft lives in the browser until you save it. A
half-finished draft isn't a note, and quietly filling the notebook with them
would be worse than losing one.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.ai import drafter, no_model_text
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
        found.append({"title": "", "content": entry.content or ""})
    return found


class TitleBody(BaseModel):
    draft: str = Field(min_length=1, max_length=20000)


@router.post("/compose")
def compose_draft(
    body: ComposeBody, session: Session = Depends(deps.get_session)
) -> dict:
    """Write or revise a draft from thoughts.

    Kept beside `/compose/stream`, which is what the writing room calls: this
    is the fallback for a client that cannot open a stream, and the shape most
    of this feature's tests speak.
    """
    if not body.thoughts.strip() and not body.draft.strip():
        raise HTTPException(status_code=400, detail="Write a thought first.")

    text, note = drafter.compose(
        body.thoughts,
        body.draft,
        deps.get_model_manager().for_feature("writing"),
        deps.get_ollama(),
        instruction=body.instruction,
        kind=body.kind,
        tone=body.tone,
        length=body.length,
        sources=_sources(session, body.source_ids),
    )
    #: Asked, not inferred from a string: see `drafter.was_offline`.
    offline = drafter.was_offline(note)
    return {
        "draft": text,
        # Distinguishes "the model reasoned" from "the model wasn't there".
        "thinking": None if offline else note,
        "message": note if offline else "",
        "ollama_running": not offline,
    }


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
    if not body.thoughts.strip() and not body.draft.strip():
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

    return StreamingResponse(
        activity.tracked_stream("generation", "Drafting", lines()),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


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
