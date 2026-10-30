"""The Help mini AI chat (ROADMAP.md item 40): app-guidance-only Q&A,
never touching the database, see `ai/help_chat.py` for why."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from tessellate.ai import help_chat
from tessellate.ai.provider import ProviderError
from tessellate.api import routes_entries
from tessellate.api.schemas import EntryCreate
from tessellate.core import activity, deps
from tessellate.core.deps import get_session
from tessellate.entry import manager, sample_notebook

router = APIRouter(prefix="/help", tags=["help"])


class HistoryTurn(BaseModel):
    role: str
    content: str = Field(max_length=help_chat.MAX_HISTORY_TURN_CHARS)


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=help_chat.MAX_MESSAGE_CHARS)
    # Held by the client only (sessionStorage/module state): see
    # `ai/help_chat.py`'s docstring for why nothing here persists it.
    history: list[HistoryTurn] = Field(default_factory=list, max_length=help_chat.MAX_HISTORY_TURNS)

    #: **The window, applied here rather than refused** (INBOX 410). The panel
    #: sends its whole transcript (`helpChatHistory` in settings.js is never
    #: trimmed), and `max_length` on its own refused the fifth question of
    #: every conversation with a 422. The prompt only ever used the last
    #: `MAX_HISTORY_TURNS` turns, so keeping those is the same answer the model
    #: would have given, and the bound above still holds for what is kept.
    @field_validator("history", mode="before")
    @classmethod
    def _keep_the_window(cls, value):
        if isinstance(value, list):
            return value[-help_chat.MAX_HISTORY_TURNS :]
        return value
    #: Which surface the question was asked from, and that surface's own help
    #: copy. Both optional: the Guide is reachable from the header on every tab
    #: now (INBOX 190), and a question asked with something on screen is nearly
    #: always about that thing. `tab` is a short name from a fixed set
    #: (`help_chat.TAB_TOPICS`), unknown values simply add no topics; `context`
    #: is text the client read out of its own DOM, so it is capped here and
    #: again in `help_chat.answer`.
    tab: str | None = Field(default=None, max_length=40)
    context: str | None = Field(default=None, max_length=help_chat.MAX_CONTEXT_CHARS)
    #: The labels of the last few things done, newest last (composer awareness).
    actions: list[str] = Field(default_factory=list, max_length=10)


@router.get("/topics")
def topics() -> dict:
    """Every help entry, grouped, for Settings, Help to list (INBOX 448): one
    source for the page and the Guide, where the page used to be a copy."""
    return help_chat.help_listing()


@router.post("/ask")
def ask(body: AskBody) -> dict:
    try:
        return help_chat.answer(
            body.question,
            deps.get_model_manager().for_feature("guide"),
            deps.get_ollama(),
            history=[turn.model_dump() for turn in body.history],
            tab=body.tab,
            context=body.context,
            actions=body.actions,
        )
    except ProviderError as exc:
        #: A closed tab or a model that failed: the model call was cut, which is
        #: not a server fault. The app's own help answers, with no traceback
        #: in the log (audit 1030 A40).
        logging.getLogger("tessellate.help").info("help/ask: the model call ended: %s", exc)
        return help_chat.offline_answer(body.question, body.tab, body.context)


@router.post("/ask/stream")
def ask_stream(body: AskBody) -> StreamingResponse:
    """The same turn as `/ask`, delivered as it is written.

    Reported of the Guide: the reply "will be blurted out really fast like it
    isnt streaming but just outputting at once", and the thinking "only shows
    up after the response is finished". `/ask` returns one object when the
    whole reply exists, so the panel could only fake the writing with a timer
    and could not show the thinking until there was nothing left to think
    about. `/ask` stays: it is the fallback the client uses when a stream
    cannot be opened, and the shape every test of this module already speaks.

    Newline-delimited JSON, the same wire format and the same
    no-buffering headers the chat stream uses, so one reader in the client
    can be taught both.
    """

    def lines():
        for event in help_chat.answer_stream(
            body.question,
            deps.get_model_manager().for_feature("guide"),
            deps.get_ollama(),
            history=[turn.model_dump() for turn in body.history],
            tab=body.tab,
            context=body.context,
            actions=body.actions,
        ):
            yield json.dumps(event) + "\n"

    return StreamingResponse(
        activity.tracked_stream("generation", "Answering in the Guide", lines()),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


#: Offered once per notebook, not per browser: kept with the notebook's own
#: preferences, so a second window or device does not offer it again.
SAMPLE_ADDED_KEY = "sample_notebook_added"
#: The categories the sample made, so Remove takes those away too.
SAMPLE_CATEGORIES_KEY = "sample_notebook_categories"


@router.get("/sample-notebook")
def sample_notebook_state(session: Session = Depends(get_session)) -> dict:
    """How many sample notes are here, and whether they were ever added."""
    return {
        "live": len(sample_notebook.live_samples(session)),
        "added": bool(deps.get_config().get_preference(SAMPLE_ADDED_KEY, False)),
    }


@router.post("/sample-notebook", status_code=201)
def add_sample_notebook(session: Session = Depends(get_session)) -> dict:
    """The sample notes (WORLD_CLASS_PLAN 25c), each saved the way a typed
    note is (`routes_entries.create_entry`: its dates, its [[links]], its
    search index), with its category named so nothing waits on a model."""
    if sample_notebook.live_samples(session):
        raise HTTPException(status_code=409, detail="The sample notes are already in this notebook.")
    before = sample_notebook.category_ids(session)
    ids = []
    for note in sample_notebook.SAMPLE_NOTES:
        body = EntryCreate(
            content=note["content"],
            category=note["category"],
            tags=[*note["tags"], sample_notebook.SAMPLE_TAG],
        )
        ids.append(routes_entries.create_entry(body=body, session=session).id)
    config = deps.get_config()
    config.set_preference(SAMPLE_ADDED_KEY, True)
    config.set_preference(SAMPLE_CATEGORIES_KEY, sorted(sample_notebook.category_ids(session) - before))
    return {"created": len(ids), "ids": ids}


@router.delete("/sample-notebook")
def remove_sample_notebook(session: Session = Depends(get_session)) -> dict:
    """Every sample note still here, to the bin, where each can be restored."""
    samples = sample_notebook.live_samples(session)
    for entry in samples:
        manager.soft_delete_entry(session, entry)
    config = deps.get_config()
    dropped = sample_notebook.drop_emptied_categories(session, config.get_preference(SAMPLE_CATEGORIES_KEY, []) or [])
    config.set_preference(SAMPLE_CATEGORIES_KEY, [])
    return {"binned": len(samples), "ids": [entry.id for entry in samples], "categories_removed": dropped}
