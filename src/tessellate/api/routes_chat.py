"""Ask a question, get back BOTH a conversational answer and the raw
matching entries: the two-result design from the original idea doc.

Two flavours:
- POST /chat: one blocking JSON response (simple, used by tests/API)
- POST /chat/stream: NDJSON: metadata + raw results first, then the
  model's thinking and answer as live token deltas (what the UI uses)

Plain `def` so the blocking LLM call runs in FastAPI's threadpool.
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
import re
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from dataclasses import replace as with_changes
from datetime import date, timezone
from itertools import chain
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from tessellate.ai import budget as run_budget, capability, composer, composer_digest, composer_lists, find_it, glossary, list_pool, neighbours, personal, phrasing, verdicts, toolwords, vocative, why
from tessellate.ai import (
    acts,
    agent,
    captioning,
    context,
    fence,
    followups,
    intent,
    librarian,
    memory,
    notebook_stats,
    presets,
    question_noise,
    questions,
    skill_runner,
    skills,
    source_check,
    starter_acts,
    tool_fallback,
    tools,
    validate,
    vision_ocr,
)
from tessellate.ai.answer_trim import trim_assistant_padding
from tessellate.ai.grounding import (
    SentenceGrounder,
    ground_answer_sentences,
    support as grounding_support,
)
from tessellate.ai.ollama_client import OllamaError
from tessellate.api.schemas import EntryOut
from tessellate.core import activity, deps, docview, model_gate
from tessellate.core.database import (
    LIKE_ESCAPE,
    Attachment,
    AskTurn,
    AuditLog,
    Category,
    Conversation,
    Document,
    Entity,
    Entry,
    MediaUpload,
    Reminder,
    like_escape,
)
from tessellate.core.config import days_from_today, user_now
from tessellate.core.deps import get_session
from tessellate.core.imagesize import image_size
from tessellate.core.logbuffer import safe_value
from tessellate.entry import manager
from tessellate.entry.manager import UNCATEGORISED
from tessellate.search import chunks as search_chunks
from tessellate.search import search_manager
from sqlalchemy import func

#: `/media/<filename>` as it appears inside note and document content, 
#: the only record a note keeps of a picture it holds.
_MEDIA_REF = re.compile(r"/media/([A-Za-z0-9._-]{1,200})")

router = APIRouter(prefix="/chat", tags=["chat"])


#: **Asking and requesting are logged apart, and this is why.** Reported
#: directly: "tasks that I have put in the agent show in the 'ask' again
#: section, the things that I will ask the agent are different to what I would
#: ask if searching in my notebook."
#:
#: Every turn through this module used to write one `queried`/`chat` audit row,
#: so "Ask again", which reads that log, offered back "tag everything about
#: the trip" and "delete the draft" as though they were questions about the
#: notebook. They are instructions, they have already been carried out, and
#: running one a second time from a chip is at best pointless and at worst a
#: repeat of an action the user did not mean to repeat.
#:
#: The rule the user gave, in their words: "if I was in the chat and using the
#: 'ask' mode, then those queries should count, but only those, and my previous
#: requests in the 'ask' subtab in notes should be registered." So the two
#: reading surfaces: the Notes tab's Ask box (`notes_only`) and the Chat tab
#: in Ask mode (tools off): write `chat`; Request mode and the Ctrl+Shift+A
#: palette, both of which act, write `agent`. Both stay in the audit log, which
#: is a record of what happened and should not lose the requests; only the
#: chip row narrows.
ASK_SURFACE = "chat"
AGENT_SURFACE = "agent"


def _feature_for(body: "ChatRequest") -> str:
    """Which feature row a turn runs under: the Ask box or the Chat tab.

    Both post here. `notes_only` is set by the Notes tab's Ask box and never
    by the Chat tab (see the field), so it is the one fact that already tells
    the two apart without a second flag to keep in step.
    """
    return "ask" if body.notes_only else "chat"


def _recent_questions(session: Session, limit: int = 5) -> list[str]:
    """The last `limit` distinct questions asked at the Ask box, newest first.
    Read straight from the audit log, no extra bookkeeping.

    Scoped to `ASK_SURFACE`, so an instruction given to the agent is never
    offered back as something to ask again.

    **Clearable, without editing the log** (the owner, 2026-10-10: "There's
    no way to clear your ask history"; "no way to ... delete individual
    records??"). The log is a history, so nothing is deleted from it: Clear
    history writes a `cleared` row, and walking back stops there; forgetting
    one chip writes a `forgot` row naming it, which hides the earlier askings
    of that question and not a later one."""
    rows = session.scalars(
        select(AuditLog)
        .where(
            AuditLog.action.in_(("queried", "forgot", "cleared", "remembered")),
            AuditLog.entity_type == ASK_SURFACE,
        )
        .order_by(AuditLog.id.desc())
        .limit(100)
    )
    questions: list[str] = []
    forgotten: set[str] = set()
    #: A `remembered` row is Undo of a `forgot` or `cleared` one (INBOX 898):
    #: it names that row's id, and walking back, the row it names no longer counts.
    lifted: set[str] = set()
    for row in rows:
        if row.action == "remembered":
            lifted.add(row.detail or "")
            continue
        if str(row.id) in lifted:
            continue
        if row.action == "cleared":
            break
        if row.action == "forgot":
            forgotten.add(row.detail or "")
        elif row.detail and row.detail not in questions and row.detail not in forgotten:
            questions.append(row.detail)
        if len(questions) == limit:
            break
    return questions


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


class RememberBody(BaseModel):
    marker_id: int


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


def _asked_key(question: str) -> str:
    """One spelling of a question, for comparing the two suggestion rows.

    Only case and surrounding space: a chip is clicked verbatim, so a repeat
    is character-for-character the same string, and anything cleverer here
    (dropping the question mark, stemming) would start deciding that two
    *different* questions are the same one."""
    return " ".join(question.split()).casefold()


#: **The two suggestion rows do not show each other's chips.** Reported (INBOX
#: 120, the owner): "the try asking and ask again suggestions are nearly
#: identical", with "Try asking:" above "Ask again:" and two of the five chips
#: below repeating the row above word for word. The rows answer different
#: questions, what you could ask and what you already asked, so neither should
#: be showing the other's answer.
#:
#: The rule, decided with the report: the history row wins a duplicate, because
#: it is a fact about this notebook rather than something generated, and the
#: generated row fills the gap with its next candidate. Which is why this is
#: settled here, on the server that builds both rows, rather than in the two
#: independent `loadSuggestions`/`loadRecentQuestions` calls in the client,
#: where it would depend on which request came back first.
SUGGESTIONS_SHOWN = 4


def _fill(candidates: list[str], asked: set[str]) -> list[str]:
    """The first `SUGGESTIONS_SHOWN` candidates that are neither a repeat of
    each other nor already offered by "Ask again"."""
    picks: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = _asked_key(candidate)
        if key in seen or key in asked:
            continue
        seen.add(key)
        picks.append(candidate)
        if len(picks) == SUGGESTIONS_SHOWN:
            break
    return picks


# Shown when the chat is empty, to teach the feature (Round 1).
STARTER_SUGGESTIONS = [
    "What have I saved recently?",
    "Summarise my notes.",
    "What are my most common topics?",
]


def _about(name: str) -> str:
    """A category name as the object of "What have I saved about ...?".

    Lower-cased word by word as a noun in running text ("Travel plans" to
    "travel plans"), but a word with capitals inside it is a name and keeps
    them ("iPhone"), as does the app's own name, and a category already named
    "About X" gives "X": the seeded notebook's "About Tessellate" came out as
    "What have I saved about about ..." (the devibe pass, a 1440 still of the
    empty chat).
    """
    words = name.split()
    if len(words) > 1 and words[0].lower() == "about":
        words = words[1:]
    return " ".join(
        w if w in _NAMES or any(c.isupper() for c in w[1:]) else w.lower() for w in words
    )


#: Proper nouns `_about` keeps capitalised although they have no inner capital.
_NAMES = frozenset({"Tessellate"})


@router.get("/suggestions", response_model=list[str])
def suggestions(session: Session = Depends(get_session)) -> list[str]:
    """Recommended questions: content-aware ones built from the user's own
    categories, falling back to generic starters for an empty notebook."""
    rows = session.execute(
        select(Category.name, func.count(Entry.id))
        .join(Entry, Entry.category_id == Category.id)
        .where(Entry.is_deleted == False)  # noqa: E712
        .group_by(Category.name)
        .order_by(func.count(Entry.id).desc())
    ).all()
    categories = [name for name, _count in rows if name != UNCATEGORISED]

    asked = {_asked_key(question) for question in _recent_questions(session)}

    if not categories:
        return _fill(STARTER_SUGGESTIONS, asked)

    # The first four are what this endpoint has always offered, in the order it
    # offered them. The rest are reserves, reached only when one of the four is
    # dropped for being in "Ask again" already, so the row keeps its length
    # instead of losing a chip to the row below it.
    candidates = [f"What have I saved about {_about(name)}?" for name in categories[:2]]
    # "my notes in General", not "my general": a category is a filing place,
    # and read as a noun after "my" it made starters like "Summarise my
    # general." on the seeded notebook.
    candidates.append(f"Summarise my notes in {categories[0]}.")
    candidates.append("What have I saved recently?")
    candidates += [f"What have I saved about {_about(name)}?" for name in categories[2:6]]
    candidates += [f"Summarise my notes in {name}." for name in categories[1:3]]
    candidates.append("What are my most common topics?")
    return _fill(candidates, asked)


class FollowupBody(BaseModel):
    """One answered turn, sent back to ask what to offer next.

    Bounded here rather than only inside `followups` because this arrives over
    HTTP: the client is echoing back a turn the server just produced, but
    nothing makes that true of a hand-made request, and both fields end up in a
    model prompt.
    """

    question: str = Field(default="", max_length=2000)
    answer: str = Field(default="", max_length=20000)


@router.post("/followups", response_model=list[str])
def chat_followups(body: FollowupBody) -> list[str]:
    """Two or three questions to offer under an answer, or [].

    Its own request rather than part of the turn on purpose: this is a second
    model call, and the answer must not wait on it. The UI fires this after the
    turn is on screen and simply renders nothing if it comes back empty, which
    it does on every failure path, including the AI not running at all.
    """
    if model_gate.busy():
        # The person is already asking the next thing: a second model call
        # now would put their question behind suggestions they can no longer
        # use (audit ARCH-16).
        return []
    return followups.suggest_followups(
        body.question,
        body.answer,
        deps.get_model_manager(),
        deps.get_ollama(),
    )


class ChatTurn(BaseModel):
    question: str
    answer: str
    #: The notes the answer named, by title, for a spoken follow-up such as
    #: "delete the other one" (`reading.follow`, decision 57). Optional, and
    #: dropped from the dump when absent, so a turn without it is unchanged.
    objects: list[Annotated[str, Field(max_length=200)]] | None = Field(default=None, max_length=8)


class PlanRun(BaseModel):
    """A plan the model made for one request, sent back to be worked through.

    Bounded here as well as in `tools.validate_make_plan`, because this arrives
    over HTTP: the client is echoing back what the server just produced, but
    nothing makes that true of a hand-made request, and the run it starts
    writes to the notebook.
    """

    goal: str = Field(min_length=1, max_length=skills.MAX_GOAL)
    steps: list[str] = Field(min_length=1, max_length=skills.MAX_STEPS)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    #: Answer from the notebook as it stood at the end of this day
    #: (WORLD_CLASS_PLAN I5, row 23). Read, never act: the turn runs without
    #: tools, which would read and change the notebook as it is now.
    as_of: date | None = None
    # Prior turns for follow-up context (Round 1); the server clips this.
    history: list[ChatTurn] = Field(default_factory=list)
    # Persona name; None → the active persona preference.
    persona: str | None = None
    # Agent mode: may the model call tools to change things?
    # None → the saved "tools_enabled" preference (default on).
    use_tools: bool | None = None
    # How much effort this turn is worth (§11): "quick", "normal" or
    # "detailed". None → the saved "response_mode" preference. Carries the
    # reply cap, the temperature, the thinking toggle and a length hint, so
    # one picker moves all four together rather than four settings that have
    # to be kept consistent by hand.
    mode: str | None = None
    # Notes the user attached by hand. These are always given to the model,
    # ahead of anything retrieval finds, "this note, specifically" is a
    # stronger signal than any similarity score.
    note_ids: list[int] = Field(default_factory=list, max_length=20)
    # Documents attached by hand (§89.2): same idea as note_ids, a separate
    # field because Document is a separate table from Entry (see its own
    # docstring in core/database.py for why). The frontend has sent this
    # since the composer's staging UI shipped; nothing here ever read it, 
    # an attached document showed as a chip on the message and the model
    # never saw its content, which is worse than not offering the feature at
    # all, since it looks like it worked. Capped at 4, matching the
    # composer's own `attachedDocuments.length >= 4` limit.
    document_ids: list[int] = Field(default_factory=list, max_length=4)
    # Files from the Library, attached by hand. Asked for directly: "I want to
    # be able to attach not just existing notes to a chat for context, but also
    # already uploaded files, documents, and images." A PDF, a spreadsheet or a
    # source file is an Attachment row, not a Document and not an Entry, so it
    # needs a field of its own for the same reason document_ids does. Its text
    # is extracted at request time by the same `core.docview` the file viewer
    # uses, so what the model reads is what the Files tab shows.
    file_ids: list[int] = Field(default_factory=list, max_length=4)
    # Mind maps attached by hand (MINDMAP_PLAN.md §5 item 11: "a map can be
    # attached to a note, a document and a chat message, exactly as a file can
    # today: routes_chat.py's `file_ids` is the pattern to copy"). A map is a
    # board, which is an Entry, so this *could* have gone through `note_ids`, 
    # and that is exactly what must not happen: a board's `content` is the
    # single line `# My map`, so attaching one that way sends the model a
    # heading and calls it a map. What reaches the model instead is the
    # outline `read_mindmap` builds, which is the form the plan chose for a
    # small model to act on. Capped at 4, matching `document_ids`/`file_ids`
    # and the composer's own ceiling.
    board_ids: list[int] = Field(default_factory=list, max_length=4)
    # Vision-capable models (ROADMAP.md's largest open item): ids from the
    # existing `/media/upload` (the same endpoint the document/note editors
    # already use for drag-and-drop images), not a second upload path. Small
    # cap: a local model paying attention to four images at once is already
    # optimistic, and each one inflates the request by ~33% once base64'd.
    image_media_ids: list[int] = Field(default_factory=list, max_length=4)
    # Running a saved skill (§21). The name of one, built-in or the user's
    # own: plus values for whatever inputs it declares. The server builds the
    # instruction, so what a skill *is* lives in one place rather than being
    # assembled in `app.js` and hoped for here.
    skill: str | None = Field(default=None, max_length=skills.MAX_NAME)
    skill_inputs: dict[str, str] | None = None
    # Resuming a run that stopped part-way (reported: *"it cuts out half way
    # through and has to restart"*). Steps before this index are marked as done
    # in an earlier run and are not repeated, which matters because most of
    # them write to the notebook, so "restart" meant tagging and linking the
    # same notes a second time.
    skill_from_step: int = Field(default=0, ge=0, le=skills.MAX_STEPS)
    # Re-running one step, optionally reworded (AGENT_SKILLS_REFORM.md Phase D).
    # A run that stalled on step 4 because the step was written for a bigger
    # model is fixed by rewriting step 4, and without this the only way to find
    # out whether the rewrite works is to run the whole skill again, every
    # earlier step of which writes to the notebook. The step's contract is not
    # editable from here on purpose: rewording an instruction must not quietly
    # drop the condition it has to meet.
    skill_only_step: int | None = Field(default=None, ge=0, le=skills.MAX_STEPS)
    skill_step_text: str | None = Field(default=None, max_length=skills.MAX_STEP)
    # Manual (step-through) mode, asked for directly: a pause after every
    # completed step with a Continue button and a text box, rather than a
    # skill running straight through unattended. `skill_manual_note` is what
    # was typed in at that pause, folded into the very next step's own
    # instruction, not stored anywhere.
    skill_manual: bool = False
    skill_manual_note: str | None = Field(default=None, max_length=skills.MAX_MANUAL_NOTE)
    # A plan the model drew for this request and handed back to be worked
    # through (§35K). Same shape as a skill run and the same runner, the
    # difference is only that nobody saved it. Sent by the client rather than
    # parked on the server, exactly as `ask_user` and `run_skill` are: nothing
    # to expire, nothing lost on a reload, and the plan is visible in the saved
    # conversation like any other message.
    plan: PlanRun | None = None
    # Notes-only: this turn is an interrogation of the notebook and nothing
    # else (§35A). Set by the Notes tab's Ask box, never by the Chat tab.
    #
    # Reported directly: *"the ask tab should be for reviewing, revisiting, and
    # searching up/asking about your notes, the chatbot can be for the chat
    # tab"*. Saying "hey" there was answered like a chatbot, because both
    # surfaces share this endpoint and `intent.classify` correctly routes
    # small talk away from retrieval.
    #
    # The fix is deliberately NOT a better classifier. The classifier is right;
    # what was missing is that one of the two callers does not *want* the
    # conversational path to exist. A flag on the request cannot misfire, costs
    # no model round, and leaves the Chat tab exactly as it was.
    notes_only: bool = False
    # The reverse problem (Tier 1 §4): the agent's own `ask_user` question
    # gets a one-word reply, "yes", "ok", "sure", all real answers a person
    # gives: and `intent.classify` correctly calls a bare "yes" small talk.
    # Routed as small talk it lands in the conversational path, which has no
    # tools at all, so the answer to the agent's own question could not be
    # acted on even if the model understood it perfectly. `TOOLS_GUIDE` tells
    # the model several turns are normal; the classifier was quietly cutting
    # this one off after the first. Same fix as `notes_only`: a flag the
    # client sets when it already knows the context, not a smarter
    # classifier trying to guess it from three letters.
    answering_agent: bool = False
    # A deliberately closed set of notes, e.g. Trace's "Generate story from
    # path", where retrieval finding *more* is pollution, not help. Without
    # this, attaching notes still ran the normal retrieval search on the
    # turn's own text alongside them (`_attached_notes` only ever added to
    # what search found, never replaced it), so a generic instruction like
    # "weave these into a narrative", no real subject to search for, still
    # keyword/semantic-matched against the whole notebook and appended
    # whatever it found after the notes the user actually chose. Reported as
    # the feature "needing to mainly use the notes within the trace", it
    # was already doing that, plus however many unrelated notes the
    # instruction text itself happened to match.
    attached_notes_only: bool = False
    #: "questions": answer from the notes that still hold an open question
    #: (WORLD_CLASS_PLAN I3, row 7: "what am I still undecided about?"), and
    #: only from them. Resolved into `note_ids` and `attached_notes_only` by
    #: `_apply_scope` before anything reads either.
    scope: Literal["questions"] | None = None
    #: What is open where the question was asked (CHAT_PLAN B10): the note
    #: being read or edited, and the category the sidebar filters to. Read
    #: only by a question about "this" ("Summarise this"), never to widen
    #: or narrow any other; `_apply_open` turns it into `note_ids`.
    open_note_id: int | None = None
    open_category: str | None = Field(default=None, max_length=100)
    #: Who writes a notes-only answer (INBOX 688): "notes" asks for the answer
    #: composed from the notes' own sentences (`ai/composer.py`) even while a
    #: model runs; anything else is the model's, when one runs. The Ask box's
    #: "AI" / "From your notes" switch sends it. A plain string rather than a
    #: Literal, because the switch's stored value reaches here as read off the
    #: device and an unknown word must mean the default, not a 422.
    answer_from: str | None = Field(default=None, max_length=16)
    #: "Try again" on the same question (CHAT_PLAN decision 34): the how-many-
    #: th retry, so an answer composed from the notes is worded anew rather
    #: than repeated word for word. 0 for a first ask.
    attempt: int = Field(default=0, ge=0, le=10_000)


def _apply_scope(session: Session, body: ChatRequest) -> None:
    """Turn a scope into the closed set of notes it means.

    With no open question anywhere the turn falls back to ordinary
    retrieval: an Ask over an empty set would answer from nothing, and the
    Ask box says beforehand that there are none (`askScopeQuestions`).
    """
    if body.scope != "questions":
        return
    ids = questions.open_note_ids(session)
    if ids:
        body.note_ids = ids
        body.attached_notes_only = True


#: The most notes a "summarise Travel" reads: the overview's own limit.
OPEN_CATEGORY_NOTES = 24


def _category_note_ids(session: Session, name: str) -> list[int]:
    rows = session.execute(
        select(Entry.id)
        .join(Category, Entry.category_id == Category.id)
        .where(Entry.is_deleted == False, Entry.is_private == False, func.lower(Category.name) == name.lower())  # noqa: E712
        .order_by(Entry.created_at.desc())
        .limit(OPEN_CATEGORY_NOTES)
    ).scalars()
    return list(rows)


def _apply_open(session: Session, body: ChatRequest) -> None:
    """"Summarise this" on any tab (CHAT_PLAN B10): the open note, else the
    open category, becomes the closed set the answer reads; "summarise
    Travel" reads that category's notes rather than the few a keyword
    search finds. Notes attached by hand, or a scope, win over both."""
    if body.note_ids or body.document_ids or body.scope:
        return
    if composer_digest.about_this(body.question):
        #: A note binned or made private since it was opened is not read;
        #: the open category stands in (`_attached_notes`' own rule).
        if body.open_note_id and _attached_notes(session, [body.open_note_id]):
            body.note_ids = [body.open_note_id]
        elif body.open_category:
            body.note_ids = _category_note_ids(session, body.open_category)
    else:
        names = list(session.execute(select(Category.name)).scalars())
        named = composer_digest.named_category(body.question, names)
        if named:
            body.note_ids = _category_note_ids(session, named)
    if body.note_ids:
        body.attached_notes_only = True


def _nothing_open(body: ChatRequest) -> bool:
    """"Summarise this" with nothing open: said plainly, not answered with
    the newest notes."""
    return composer_digest.about_this(body.question) and not (body.note_ids or body.document_ids or body.board_ids)


def _resolve_mode(requested: str | None) -> str:
    """The response preset for this turn (§11).

    A request may name one; otherwise the saved preference decides, and an
    unrecognised name in either place falls through to `normal` rather than
    raising: `presets.resolve` does that last part, so a hand-edited
    preferences file costs the setting and not the chat.
    """
    if requested:
        return requested
    return str(
        deps.get_config().get_preference("response_mode", presets.DEFAULT_MODE)
        or presets.DEFAULT_MODE
    )


def _resolve_persona(name: str | None, session: Session | None = None) -> str | None:
    """Persona name → its system prompt (shared with greetings and titles).

    With a session, the user's standing preferences ride along, see
    `ai/memory.py`. **They used to reach only the agent path**, so a rule
    typed into Settings → "What it remembers" was obeyed in Request mode and
    silently ignored in Ask, which is where most questions are asked. Passed
    optionally because the two callers that build a *greeting* or a chat
    *title* genuinely do not want them: neither is answering the user, and a
    title prefixed with someone's writing-style rules is nonsense.
    """
    prompt = librarian.resolve_persona_prompt(name, deps.get_config())
    if session is None:
        return prompt
    return memory.persona_with_memory(session, prompt)


# Base64 inflates size by ~33%; a generous per-image cap keeps one photo
# straight off a phone (often 5-10MB) from making a single turn bigger than
# what most local models' num_ctx could hold in the first place.
MAX_CHAT_IMAGE_BYTES = 8 * 1024 * 1024


def _resolve_chat_images(session: Session, media_ids: list[int]) -> list[tuple[MediaUpload, str]]:
    """Attached-by-id media uploads → (upload row, data URI) pairs.

    `media_ids` come from the same `/media/upload` the note/document editors
    already use for drag-and-drop images, this reuses that upload, rather
    than adding a second upload path for the composer alone. A data URI
    (not bare base64) is the app's neutral shape: `ollama_client` strips the
    prefix for Ollama's wire format, `openai_client` hands the URI straight
    to `image_url.url` unchanged (see both modules' `_to_*_messages`). The
    upload row travels alongside it so `_image_caption_context` below can
    read or generate a caption for it without a second query.

    An id that doesn't resolve, isn't readable, is too large, or isn't
    actually an image (the same upload endpoint also accepts PDFs) is
    silently dropped rather than 500ing the whole turn, the UI already
    confirmed each upload succeeded before sending its id here, so a miss
    means the file moved or was deleted after that, not a bad request.
    """
    if not media_ids:
        return []
    media_dir = deps.get_config().data_dir / "media"
    images = []
    for media_id in media_ids:
        upload = session.get(MediaUpload, media_id)
        if upload is None:
            continue
        try:
            data = (media_dir / upload.filename).read_bytes()
        except OSError:
            continue
        if len(data) > MAX_CHAT_IMAGE_BYTES:
            continue
        mime = mimetypes.guess_type(upload.filename)[0] or ""
        if not mime.startswith("image/"):
            continue
        uri = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
        images.append((upload, uri))
    return images


def _chat_model_sees_images(model_manager, ollama) -> bool:
    """Whether the model this turn would otherwise use can take an image
    directly. Only a definite "yes" counts: an unknown answer (`None`, the
    same three-way `supports()` itself returns for anything it cannot
    report on) falls back to the caption path in `_image_caption_context`
    rather than gambling a real photo on a model that might silently
    ignore it."""
    supports = getattr(ollama, "supports", None)
    if not callable(supports):
        return False
    return supports(model_manager.chat_model(), "vision") is True


def _image_caption_context(
    images: list[tuple[MediaUpload, str]], model_manager, ollama
) -> str:
    """What a chat model with no vision of its own gets instead of the raw
    image bytes: a vision model's own caption, folded into the question
    text by `librarian.answer`/`converse`/`agent.run_agent`'s own
    `image_context` parameter.

    Asked for directly: "if I am using a chat model with no vision
    capabilities, it will use the vision model to caption the image, then
    the chat model will take that caption and use it for its response", 
    replacing the earlier behaviour of silently swapping the whole turn to
    a different model the user did not choose as their chat model.

    Runs synchronously, in-request: unlike the background trigger on
    upload (routes_files.py's own POST /media/upload), this turn's answer
    depends on having the caption before the chat model is asked anything.
    `caption_and_store` is the same write-once-unless-forced helper that
    trigger uses, so an image already captioned by either path is never
    captioned twice.
    """
    if not images:
        return ""
    media_dir = deps.get_config().data_dir / "media"
    lines = []
    for upload, _uri in images:
        caption = upload.caption or captioning.caption_and_store(
            upload.id, media_dir / upload.filename
        )
        if caption:
            lines.append(f"- {caption}")
    if not lines:
        return ""
    plural = "image" if len(lines) == 1 else "images"
    return (
        f"[{len(lines)} attached {plural}, described by a vision model since "
        "the chat model can't see them directly:\n" + "\n".join(lines) + "]"
    )


def _small_model_mode() -> bool | None:
    """Whether this run gets the small-model treatment: one tool per step and
    a worked example of the call.

    Three states, and the third is the useful one. "auto" returns **None**,
    which is the runner's own "decide from the model", deliberately not
    resolved here, because the run is the thing that knows which model it is
    about to use. `on`/`off` are the override for the two cases a name-based
    guess cannot get right: a 30B that still can't hold five schemas, and a 4B
    that copes fine and would rather have the whole toolbox.
    """
    setting = str(
        deps.get_config().get_preference("small_model_mode", "auto") or "auto"
    ).lower()
    if setting in ("on", "true", "always"):
        return True
    if setting in ("off", "false", "never"):
        return False
    return None


def _resolve_skill(body: ChatRequest) -> dict | None:
    """Turn "run this skill" into the request the model actually receives.

    404 for a skill that isn't there and 422 for one missing a required input:
    a skill that quietly ran with a blank `{{topic}}` would search the whole
    notebook for nothing and read as the model ignoring the user.
    """
    if not body.skill:
        return None
    found = skills.find(deps.get_config(), body.skill, set(tools.TOOLS))
    if found is None:
        raise HTTPException(status_code=404, detail=f"No skill called “{body.skill}”.")
    missing = skills.missing_inputs(found, body.skill_inputs or {})
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"“{found['name']}” needs {', '.join(missing)} before it can run.",
        )
    return {
        "skill": found,
        "question": skills.run_instruction(found, body.skill_inputs or {}),
        "tools": found["tools"] or None,
        "acts": skills.is_action(found),
    }


def _resolve_plan(body: ChatRequest) -> dict | None:
    """Turn "work through this plan" into a run, in the same shape as a skill.

    Re-validated through `tools.validate_make_plan` rather than trusted, so a
    plan that arrives with one step, twenty steps or its own numbering is
    refused (or tidied) by the same rules that produced it. 422 rather than a
    silent trim: a plan that quietly loses its last two steps is exactly the
    "did the first part and stopped" failure this whole mechanism exists to
    prevent, arriving from the other end.
    """
    if body.plan is None:
        return None
    try:
        checked = tools.validate_make_plan(
            {"goal": body.plan.goal, "steps": body.plan.steps}
        )
    except tools.ToolError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    plan = skills.ad_hoc_plan(checked["goal"], checked["steps"])
    return {
        "skill": plan,
        "question": skills.run_instruction(plan, {}),
        # No allowlist: see `skills.ad_hoc_plan`. Each step is focused on its
        # own text instead of on a guess made from one sentence.
        "tools": None,
        "acts": True,
    }


class ChatResponse(BaseModel):
    ai_response: str
    # A thinking model's reasoning, when it produced any.
    ai_thinking: str | None = None
    raw_results: list[EntryOut]
    # 'hybrid', 'semantic', 'keyword', 'dated' or 'recent', how they were found.
    search_mode: str
    # Which of raw_results are here by connection rather than by matching.
    connected_ids: list[int] = []
    # Why each result showed up, keyed by str(entry id): {"type": "semantic",
    # "score": 0.81} etc. (JSON object keys are always strings; the client
    # converts back). Not every id in raw_results has an entry here: dated/
    # recent/attached results are already explained by search_mode itself.
    match_info: dict[str, dict] = {}
    # Words for the retrieved notes' pictures, by url (INBOX 502).
    picture_alts: dict[str, str] = {}
    # Their real [width, height], so an answer's figure holds its space (INBOX 526).
    picture_sizes: dict[str, list[int]] = {}
    # Which chat model wrote the answer, or None when it didn't answer.
    answered_by: str | None = None
    # Whether Ollama is reachable, lets the UI distinguish "offline"
    # from "nothing to answer" honestly.
    ollama_running: bool = False
    # The time phrase the search narrowed on ("last week", "recently"), or "".
    # An empty dated result has two facts to report and only saying the first
    #, "no matching records", is what makes a working narrow search look
    # like a broken one. The client needs the phrase to say the second.
    when_phrase: str = ""
    # ROADMAP.md item 36: which retrieved note backs which sentence of the
    # answer, direct-Q&A path only (this endpoint, not /chat/stream's
    # conversational/agentic modes). Omitted, not wrong, for a sentence with
    # no note clearing the overlap threshold, see ai/grounding.py.
    sentence_grounding: list[dict] = []


def _grounding_candidates(
    session: Session, notes: list[dict], touched_note_ids: list[int]
) -> list[dict]:
    """The retrieval set plus every note a tool read this turn, as
    `{id, content}` rows for `ground_answer_sentences`.

    Same refusals as `_attached_notes`: a binned or private note never
    becomes a citation, whatever a tool result said. A tool reads a note
    through `_require_note`, which already refuses both, so this is the
    guard kept where the shape is kept (CLAUDE.md section 6, shape 3) rather
    than a second opinion. Documents are left out on purpose: a document id
    and a note id share a number space in the citation UI, which opens the
    *note* with that id.
    """
    #: A note's attached files count as what it says (INBOX 604, the owner:
    #: "it didnt intext number reference the referenced notes??"). Two of
    #: three sketches are one word and a picture: the answer described them
    #: from their captions, which the prompt carries (`_files_on`), and the
    #: grounding, reading `content` alone, found no note saying it.
    rows = [
        {**note, "content": f"{note.get('content') or ''}\n\n" + "\n".join(note["files"])}
        if note.get("files") else note
        for note in notes
        if note.get("id") is not None
    ]
    seen = {note["id"] for note in rows}
    for note_id in dict.fromkeys(touched_note_ids):
        if note_id in seen:
            continue
        entry = session.get(Entry, note_id)
        if entry is None or entry.is_deleted or entry.is_private:
            continue
        seen.add(note_id)
        rows.append({"id": entry.id, "content": entry.content})
    return rows


def _attached_notes(session: Session, note_ids: list[int]) -> list[dict]:
    """The notes the user picked, in the order they picked them.

    Binned notes are skipped: attaching one would quietly resurrect content the
    user has already thrown away. Private notes are skipped too, a client-
    supplied id list is the one path into this prompt that never went through
    `tools._require_note`, which is the only thing that otherwise refuses a
    private note (CLAUDE.md's own reminder of exactly this shape of bug). A
    forged/stale `note_ids` entry for a private note would otherwise put its
    id and category straight into what the model sees, private-notebook rule
    or not: no plaintext leaks (the content column is ciphertext either way,
    unreadable without `manager.readable_content`), but its existence should
    not be either.
    """
    found = []
    for note_id in dict.fromkeys(note_ids):  # de-duplicate, keep order
        entry = session.get(Entry, note_id)
        if entry is None or entry.is_deleted or entry.is_private:
            continue
        found.append(entry)
    return found


def _attached_documents(session: Session, document_ids: list[int]) -> list[Document]:
    """The documents the user attached by hand, in the order picked.

    No privacy/soft-delete filter here, unlike Entry, Document has neither
    field (core/database.py's own Document docstring: it's the long-form
    editor, not the notebook), so there's nothing to check beyond existing.
    """
    found = []
    for document_id in dict.fromkeys(document_ids):
        document = session.get(Document, document_id)
        if document is not None:
            found.append(document)
    return found


#: How much of one attached file's text is given to the model. A file can be a
#: 300-page PDF, and every character here is resent on every round of the turn
#: -- the same budget reasoning `MEDIA_READING_CHARS` below records. Generous
#: enough for a report or a source file, bounded enough that four of them
#: cannot fill a small local model's whole context on their own.
ATTACHED_FILE_CHARS = 12000


def _attached_files(session: Session, file_ids: list[int]) -> list[dict]:
    """The Library files the user attached, as note-shaped context rows.

    Text is extracted here rather than stored: `core.docview.extract` is the
    same call `GET /files/{id}/text` makes, so an attached spreadsheet reaches
    the model as the table the Files tab would show, and a file whose text
    cannot be read (a scanned PDF with no reader available, an image) still
    reaches it as its name and kind rather than silently as nothing -- a
    filename is a real clue, and a chip in the transcript that corresponded to
    nothing at all is the failure mode `document_ids` already shipped once.
    """
    found: list[dict] = []
    uploads = deps.get_config().uploads_dir
    for file_id in dict.fromkeys(file_ids):
        attachment = session.get(Attachment, file_id)
        if attachment is None:
            continue
        body = ""
        try:
            viewed = docview.extract(
                uploads / attachment.stored_name,
                vision_reader=vision_ocr.pdf_reader_or_none(),
            )
            body = (viewed.text or "").strip()
        except Exception:  # noqa: BLE001 - an unreadable file is still worth naming
            body = ""
        if len(body) > ATTACHED_FILE_CHARS:
            body = body[:ATTACHED_FILE_CHARS] + "\n\n[…truncated]"
        header = f"File: {attachment.filename}"
        found.append(
            {
                "id": attachment.id,
                "content": f"{header}\n\n{body}" if body else f"{header}\n\n(no readable text)",
                "category": "File",
                "kind": "file",
                "attached": True,
                "connected": False,
                "match_info": None,
            }
        )
    return found


#: How much of one attached map's outline reaches the model.
#:
#: Smaller than `ATTACHED_FILE_CHARS` by an order of magnitude, on purpose: a
#: file is prose the model reads once, while an outline is *structure*, and
#: past a few hundred nodes the tree stops being context and becomes the whole
#: window: `read_mindmap`'s own `MAX_OUTLINE_NODES` makes the same call for
#: the same reason. Four maps at this cap is ~12k characters, the same ceiling
#: one attached file already has, and every character is resent on every round
#: of the turn.
ATTACHED_MAP_CHARS = 3000


def _attached_boards(session: Session, board_ids: list[int]) -> list[dict]:
    """The mind maps the user attached, as note-shaped context rows holding
    the same indented outline `read_mindmap` returns.

    **One renderer, not two.** The outline is built by calling the map tool's
    own helpers rather than by walking the tree again here: the agent, the
    export and this must not disagree about what a map says, and a second walk
    is how they come to (§9.1 lists three edge cases, a dangling parent, a
    ring, board scoping: that a second copy gets subtly differently).

    A private board is skipped in silence rather than refused. Attaching is a
    deliberate act, so this is not the guard that matters, but `read_mindmap`
    refuses a private board on the AI's behalf, and a hand-attached one
    reaching the model by a different door would make that guard decorative.
    """
    from tessellate.api.routes_whiteboard import _board_settings, _build_tree, _map_objects
    from tessellate.entry import manager as entry_manager

    found: list[dict] = []
    for board_id in dict.fromkeys(board_ids):
        entry = session.get(Entry, board_id)
        if entry is None or entry.is_deleted or entry.is_private:
            continue
        board_type, _layout = _board_settings(entry)
        title = entry_manager.extract_title(entry.content) or f"Board {board_id}"
        objects = _map_objects(session, board_id)
        lines: list[str] = []
        _outline_into(_build_tree(session, objects), 0, lines)
        outline = "\n".join(lines) if lines else "(empty: no nodes yet)"
        if len(outline) > ATTACHED_MAP_CHARS:
            outline = outline[:ATTACHED_MAP_CHARS] + "\n[…truncated]"
        found.append(
            {
                "id": board_id,
                "content": (
                    f"Mind map: {title}\n"
                    f"({len(objects)} node{'' if len(objects) == 1 else 's'}, "
                    f"laid out as a {board_type})\n\n{outline}"
                ),
                "category": "Mind map",
                "kind": "map",
                "attached": True,
                "connected": False,
                "match_info": None,
            }
        )
    return found


starter_acts.ATTACHED_BOARDS = _attached_boards


def _outline_into(nodes: list[dict], depth: int, out: list[str]) -> None:
    """The tree as indented text, two spaces per level, one node per line.

    The same shape `ai/tools/whiteboard.py::_outline_lines` produces, minus its
    `[id N]` markers: those exist so the *model* can name a node in the next
    tool call, and an attached map is context for a question, not a handle for
    an edit. Keeping the ids would spend a third of the budget on numbers
    nothing in this path can use.
    """
    for node in nodes:
        text = node["text"] or "(untitled)"
        mark = "" if node["kind"] == "topic" else f" [{node['kind']}]"
        out.append(f"{'  ' * depth}- {text}{mark}")
        _outline_into(node["children"], depth + 1, out)


#: At most this many pictures from one note are described to the model, and at
#: most this much of each reading. A note can hold a dozen scans; the readings
#: are a *hint* about what is in the note, not a second copy of the notebook,
#: and every character here is resent on every round of the turn.
MEDIA_READINGS_PER_NOTE = 4
#: 1,200, not 240 (INBOX 491): a screenshot of typed notes is the note, and
#: 240 characters of it is a line and a half. The note's own allowance
#: (`librarian.note_for_prompt`) still caps the whole, readings included.
MEDIA_READING_CHARS = 1200

#: A retrieved note whose own words (pictures' Markdown taken out) are this
#: short is mostly its pictures, so it gets their readings too (INBOX 491:
#: "What are the specific feature suggestions?" over a note that was one
#: screenshot of typed ideas reached the model as `![image.png](...)`, and
#: the answer said the note gave no specifics, though retrieval had found the
#: note *by* that picture's text). A note with words of its own stays as it
#: is, so ten search hits do not spend the budget on incidental pictures.
MOSTLY_PICTURE_CHARS = 200
_IMAGE_MARKDOWN = re.compile(r"!\[[^\]]*\]\([^)]*\)")


#: How many of the retrieved notes' pictures get words for their thumbnails.
PICTURE_ALTS_MAX = 40
PICTURE_ALT_CHARS = 160


def _picture_alts(session: Session, entries: list) -> dict[str, str]:
    """`/media/<file>` -> words that say what a retrieved note's picture is.

    INBOX 502 (the owner: "should the ai chats be able to pull images and
    sketches and render them in chat responses?? with accompanying references
    and hyperlinks??", decision taken: yes). An answer draws a grounded note's
    pictures as thumbnails beside its citation, and a thumbnail needs alt
    text: the caption the app already wrote, else the start of the text read
    off it. A lookup, never a pipeline, for `_media_readings`' reason: a
    picture with no reading yet gets its Markdown alt on the page instead.
    One query for every note, sent once with the results.
    """
    filenames = list(
        dict.fromkeys(name for entry in entries for name in _MEDIA_REF.findall(entry.content or ""))
    )[:PICTURE_ALTS_MAX]
    if not filenames:
        return {}
    alts = {}
    for upload in session.query(MediaUpload).filter(MediaUpload.filename.in_(filenames)).all():
        words = (upload.caption or "").strip() or " ".join(
            (upload.vision_ocr_text or upload.ocr_text or "").split()
        )
        if words:
            alts[f"/media/{upload.filename}"] = words[:PICTURE_ALT_CHARS]
    return alts


def _picture_sizes(entries: list) -> dict[str, list[int]]:
    """`/media/<file>` -> [width, height] for the same pictures, read from the
    file headers (`core/imagesize`), so an answer's figure (INBOX 526) holds
    its space before the image loads. A picture whose size is unknown is left
    out and the figure sizes itself."""
    names = list(
        dict.fromkeys(name for entry in entries for name in _MEDIA_REF.findall(entry.content or ""))
    )[:PICTURE_ALTS_MAX]
    media_dir = deps.get_config().data_dir / "media"
    sizes = {}
    for name in names:
        size = image_size(media_dir / Path(name).name)
        if size:
            sizes[f"/media/{name}"] = list(size)
    return sizes


def _mostly_pictures(content: str) -> bool:
    """True when a note is little more than its pictures."""
    if not _MEDIA_REF.search(content or ""):
        return False
    words = _IMAGE_MARKDOWN.sub("", content or "")
    return len(" ".join(words.split())) < MOSTLY_PICTURE_CHARS


def _note_dates(entry, zone) -> str:  # noqa: ANN001
    """"Wednesday 23 September 2026, 09:40", and ", edited ..." when it has been
    since: spelled out, the form `_long_date` explains (a small model reasons
    about weekdays better than ISO dates)."""

    def day(when):  # noqa: ANN001, ANN202
        if when is None:
            return ""
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        when = when.astimezone(zone)
        #: With the time: notes written the same day are told apart only by
        #: it (measured: the model picked the wrong one of two on one day).
        return f"{when:%A} {when.day} {when:%B %Y}, {when:%H:%M}"

    written = day(getattr(entry, "created_at", None))
    edited = day(getattr(entry, "edited_at", None))
    return f"{written}, edited {edited}" if edited and edited != written else written


def _time_words(dates, today) -> list[str]:  # noqa: ANN001
    """Each resolved time phrase in a note, worded for the model with how far
    it is from today: '"this Friday" meant Friday 25 September 2026, 8 days
    ago' (INBOX 441). The app resolves the phrase against the day the note was
    written; without this the model read "this Friday" as this week's."""
    out = []
    for item in dates:
        when = item.at
        day = f"{when:%A} {when.day} {when:%B %Y}"
        if item.precision == "minute":
            span = f"{day} at {when:%H:%M}"
        else:
            span = day if item.precision == "day" else f"the {item.precision} of {day}"
        out.append(f'"{item.phrase}" meant {span}, {days_from_today(when.date(), today)}')
    return out


def _one_line(text: str) -> str:
    """A picture's read text as one line, its lines joined by " / "."""
    return " / ".join(line.strip() for line in text.splitlines() if line.strip())


def _media_readings(session: Session, content: str, captions_only: bool = False) -> str:
    """What the app already knows about the pictures inside a note.

    Asked directly: *"if there is an image/sketch/file in that note, can the ai
    read the captions or ocr in those attachments if they already exist??"* It
    could not. A note's content carries `/media/<filename>` references and
    nothing else: so a note whose entire point was a photographed whiteboard
    reached the model as a sentence and a link, and the caption and OCR text
    the app had already generated for that exact image sat unread in the
    database two tables away.

    "If they already exist" is the operative half, and it is why this is a
    lookup and not a pipeline: nothing here generates a caption or runs vision
    OCR. Captioning is a background job that may not have run yet, may be off,
    or may have no model to run against, and a chat turn is the worst possible
    place to start one, it would block the answer on a second model load. A
    picture with no reading yet simply contributes nothing.
    """
    filenames = _MEDIA_REF.findall(content or "")
    if not filenames:
        return ""
    # De-duplicated, in the order they appear in the note, the same order the
    # reader sees them in, so "the second diagram" means the same thing to both.
    ordered = list(dict.fromkeys(filenames))[:MEDIA_READINGS_PER_NOTE]
    rows = {
        upload.filename: upload
        for upload in session.query(MediaUpload)
        .filter(MediaUpload.filename.in_(ordered))
        .all()
    }
    lines = []
    for filename in ordered:
        upload = rows.get(filename)
        if upload is None:
            continue
        caption = (upload.caption or "").strip()
        text = "" if captions_only else (upload.vision_ocr_text or upload.ocr_text or "").strip()
        #: One line a picture: the text's own lines joined by " / " (INBOX
        #: 787: a reading over several lines broke the block, and the answer
        #: quoted `text in it: "Ranked Solo/Duo.` and stopped).
        text = _one_line(text)
        if not caption and not text:
            continue
        parts = []
        if caption:
            parts.append(f"shows {caption[:MEDIA_READING_CHARS]}")
        if text:
            parts.append(f'text in it: "{text[:MEDIA_READING_CHARS]}"')
        name = (upload.original_name or filename).strip()
        lines.append(f"- {name}: {'; '.join(parts)}")
    if not lines:
        return ""
    # Bracketed and labelled so the model can tell the app's reading of a
    # picture from the user's own words. It is evidence about the note, not
    # part of it.
    return "\n\n[Pictures in this note, as this app read them:\n" + "\n".join(lines) + "]"


#: A file's caption as the prompt gives it beside a retrieved note: one line,
#: enough for "a sketch of a bean" to be seen as a sketch, not the reading
#: `_attachment_readings` gives a note picked by hand.
FILE_CAPTION_CHARS = 160


def _files_on(session: Session, entry_ids: list[int]) -> dict[int, list[str]]:
    """Each note's attached files, "sketch.png (a blue bean drawn in pen)",
    in one query. Names and stored captions only: nothing is read from disk
    here, so ten notes cost one SELECT."""
    if not entry_ids:
        return {}
    out: dict[int, list[str]] = {}
    rows = (
        session.query(Attachment.entry_id, Attachment.filename, Attachment.caption)
        .filter(Attachment.entry_id.in_(entry_ids))
        .order_by(Attachment.id)
        .all()
    )
    for entry_id, filename, caption in rows:
        names = out.setdefault(entry_id, [])
        if len(names) >= MEDIA_READINGS_PER_NOTE:
            continue
        said = " ".join((caption or "").split())[:FILE_CAPTION_CHARS]
        names.append(f"{filename} ({said})" if said else filename)
    return out


def _attachment_readings(session: Session, entry_id: int) -> str:
    """What's inside the *files* attached to a note (PDFs, Office documents,
    code, plain text): `_media_readings` above's own sibling, and the gap it
    left. Asked about directly in the same spirit as that function's own
    report: a note whose entire point was an attached spreadsheet or PDF
    reached the model as a filename and nothing else, even when the note
    carrying it was hand-attached to the very question being asked.

    Same "attached notes get more, retrieved ones don't" budget
    `_media_readings` already uses, and read live rather than cached: unlike
    a caption or an OCR pass (a background job that may not have run yet),
    extraction here is `docview.extract` (core/docview.py): exactly what
    `/documents/import` and `/files/{id}/text` already pay synchronously per
    request: bounded to a handful of files on a note the user explicitly
    picked, not a background sweep over the whole notebook.
    """
    attachments = (
        session.query(Attachment)
        .filter(Attachment.entry_id == entry_id)
        .order_by(Attachment.id)
        .limit(MEDIA_READINGS_PER_NOTE)
        .all()
    )
    if not attachments:
        return ""
    uploads_dir = deps.get_config().uploads_dir
    lines = []
    for attachment in attachments:
        path = uploads_dir / attachment.stored_name
        if not path.is_file():
            continue
        try:
            viewed = docview.extract(path)
        except Exception:  # noqa: BLE001  # a bad file must not cost the answer
            continue
        text = viewed.text.strip()
        if not text:
            continue
        lines.append(f"- {attachment.filename}: {text[:MEDIA_READING_CHARS]}")
    if not lines:
        return ""
    return "\n\n[Files attached to this note, as this app read them:\n" + "\n".join(lines) + "]"


#: A topic asked about as a whole reads this many notes (INBOX 787): "games
#: notes" answered from the five a similarity search ranked counted five, and
#: the overview says how many there are.
OVERVIEW_LIMIT = 24
#: Notes found by what their pictures show or say, beside retrieval.
PICTURE_MATCHES = 3


#: The person's abbreviations, learned once per state of the notebook (the
#: count and the newest edit), not once per question.
_GLOSSARY: dict[str, object] = {"key": None, "terms": {}}


def _glossary(session: Session) -> dict[str, str]:
    """`ai/glossary.learn` over every note (CHAT_PLAN B7): "CC" is Cloud
    Computing because the notes say so, or name it in full beside it."""
    live = Entry.is_deleted == False  # noqa: E712
    key = session.execute(select(func.count(Entry.id), func.max(Entry.updated_at)).where(live)).one()
    if _GLOSSARY["key"] != tuple(key):
        texts = session.execute(select(Entry.content).where(live)).scalars()
        _GLOSSARY.update(key=tuple(key), terms=glossary.learn(texts))
    return _GLOSSARY["terms"]  # type: ignore[return-value]


def _widened(session: Session, question: str, entries: list, scope: str = "") -> list:
    """The retrieved notes, plus the notes whose pictures match the question
    (keyword search reads a note's words, not its pictures' readings: "what
    did I note about binary search trees" missed the lecture slide), plus,
    for a topic asked about as a whole, its notes by keyword and by tag."""
    from tessellate.ai import composer_overview

    extra = _picture_notes(session, composer.subject_terms(question))
    subject = composer_overview.topic(question)
    if subject:
        extra += search_manager.keyword_search(session, subject, limit=OVERVIEW_LIMIT)
        extra += _filed_under(session, composer.subject_terms(subject))
    seen = {entry.id for entry in entries}
    out = list(entries)
    for entry in extra:
        #: A question scoped to a category ("my notes in Health") keeps its
        #: answer there: "notes in Health" reads as a topic too, and its word
        #: "notes" matched an Ideas note.
        if scope and manager.category_name_for(session, entry) != scope:
            continue
        if entry.id not in seen and not entry.is_deleted and not entry.is_private:
            seen.add(entry.id)
            out.append(entry)
    return out[: max(len(entries), OVERVIEW_LIMIT)]


#: Notes read for "the topic whole" come from the first of the retrieved
#: ones that rank at the top, never from every graph neighbour.
NEIGHBOUR_SEEDS = 3
#: Past this many retrieved notes the topic is already read whole.
NEIGHBOUR_ROOM = 6


def _with_neighbours(session: Session, question: str, entries: list, scope: str = "") -> list:
    """The retrieved notes plus, for a question about a topic as a whole, the
    notes sharing a rare tag with the best of them (`ai/neighbours.py`: the
    keyword search wants every word, so "how's the gym going?" never read the
    second gym note)."""
    if neighbours.asks_left(question) and not scope:
        return _with_open(session, question, entries)
    if not entries or scope or len(entries) > NEIGHBOUR_ROOM or not neighbours.reads_whole(question):
        return entries
    rows = session.execute(
        select(Entry.id, Entry.tags)
        .where(Entry.is_deleted == False, Entry.is_private == False, Entry.is_board == False, Entry.tags != "[]")  # noqa: E712
        .order_by(Entry.created_at.desc())
        .limit(2000)
    ).all()
    chosen = neighbours.pick([e.id for e in entries[:NEIGHBOUR_SEEDS]], [(i, manager.tags_from_json(t)) for i, t in rows])
    have = {e.id for e in entries}
    extra = [session.get(Entry, i) for i in chosen if i not in have]
    return entries + [e for e in extra if e is not None]


def _with_open(session: Session, question: str, entries: list) -> list:
    """For "what do I need to buy" and "what's left", the notes that hold
    something still open: an unticked box, "still to" or "need to", and, for
    buying, the shopping notes by tag or category. Search by the words of the
    question ("buy") finds none of them."""
    clauses = [Entry.content.like("%- [ ]%"), Entry.content.like("%still to %"), Entry.content.like("%need to %")]
    if re.search(r"\b(buy|shop|get)\b", question, re.I):
        shops = ("grocer", "shopping", "shop list")
        clauses += [func.lower(Entry.tags).like(f"%{like_escape(w)}%", escape=LIKE_ESCAPE) for w in shops]
        named = select(Category.id).where(or_(*(func.lower(Category.name).like(f"%{like_escape(w)}%", escape=LIKE_ESCAPE) for w in shops)))
        clauses.append(Entry.category_id.in_(named))
    found = session.scalars(
        select(Entry)
        .where(Entry.is_deleted == False, Entry.is_private == False, Entry.is_board == False, or_(*clauses))  # noqa: E712
        .order_by(Entry.created_at.desc())
        .limit(NEIGHBOUR_ROOM)
    )
    have = {e.id for e in entries}
    return entries + [e for e in found if e.id not in have]


def _filed_under(session: Session, terms: list[str]) -> list:
    """Notes tagged with, or filed in a category named for, a word of the
    topic ("games" finds the notes tagged games that never say the word)."""
    words = [t.lower() for t in terms if len(t) >= 3][:3]
    if not words:
        return []
    clauses = [func.lower(Entry.tags).like(f'%"{like_escape(w.rstrip("s"))}%', escape=LIKE_ESCAPE) for w in words]
    named = select(Category.id).where(or_(*(func.lower(Category.name).like(f"{like_escape(w.rstrip('s'))}%", escape=LIKE_ESCAPE) for w in words)))
    clauses.append(Entry.category_id.in_(named))
    query = (
        select(Entry)
        .where(Entry.is_deleted == False, Entry.is_private == False, or_(*clauses))  # noqa: E712
        .order_by(Entry.created_at.desc())
        .limit(OVERVIEW_LIMIT)
    )
    return list(session.scalars(query))


def _picture_notes(session: Session, terms: list[str]) -> list:
    """Notes holding a picture whose caption or read text has every word of
    the question's subject, at most `PICTURE_MATCHES`."""
    words = [t.lower() for t in terms if len(t) >= 3][:4]
    if not words:
        return []
    said = func.lower(func.coalesce(MediaUpload.caption, "") + " " + func.coalesce(MediaUpload.vision_ocr_text, "") + " " + func.coalesce(MediaUpload.ocr_text, ""))
    names = list(session.scalars(
        select(MediaUpload.filename).where(*(said.like(f"%{like_escape(w)}%", escape=LIKE_ESCAPE) for w in words)).limit(PICTURE_MATCHES)
    ))
    if not names:
        return []
    holding = or_(*(Entry.content.like(f"%{like_escape(name)}%", escape=LIKE_ESCAPE) for name in names))
    return list(session.scalars(select(Entry).where(Entry.is_deleted == False, holding).limit(PICTURE_MATCHES)))  # noqa: E712


def _prepare(
    session: Session,
    question: str,
    note_ids: list[int] | None = None,
    force_notes_intent: bool = False,
    attached_notes_only: bool = False,
    document_ids: list[int] | None = None,
    file_ids: list[int] | None = None,
    board_ids: list[int] | None = None,
    surface: str = ASK_SURFACE,
    as_of: "date | None" = None,
) -> dict:
    """The shared first half of both chat endpoints: retrieve entries,
    bump their usage counters, log the question, gather AI settings.

    A message that isn't about the notebook skips retrieval entirely, there's
    nothing to search for, and searching anyway is what made "hey" come back
    with a list of notes.
    """
    from tessellate.api.routes_entries import _to_out  # avoids a route-module cycle

    detected = intent.classify(question)
    # `body.answering_agent` (Tier 1 §4): a reply to the agent's own question
    # is about the notebook by construction, however smalltalk-shaped the
    # reply itself reads ("yes", "ok"). Same override shape as `attached`
    # below, and the same reason: this route's job is to route what the
    # request actually is, and the client already knows.
    if force_notes_intent:
        detected = intent.NOTES
    # Attaching a note (or a document) is itself a statement that this is
    # about the notebook, so it overrides the classifier, "what do you
    # think?" with three notes clipped to it is a question about those notes.
    attached = _attached_notes(session, note_ids or [])
    attached_docs = _attached_documents(session, document_ids or [])
    attached_files = _attached_files(session, file_ids or [])
    attached_boards = _attached_boards(session, board_ids or [])
    if attached or attached_docs or attached_files or attached_boards:
        detected = intent.NOTES
    #: **A question about the notebook's shape is answered by counting it.**
    #: Asked for directly: "enhance the semantic search so it can pick up stuff
    #: like if I ask 'what are my most common tags', or maybe 'categories with
    #: the most notes'."
    #:
    #: Retrieval cannot answer those, and no amount of tuning would: semantic
    #: search finds the notes most *like* a question, and "what are my most
    #: common tags" is not like any note. It used to retrieve five arbitrary
    #: notes and tell the model to answer from those alone, so the model
    #: either declined or invented a ranking from a five-note sample.
    #:
    #: The facts are computed here, exactly, from rows. The model still writes
    #: the sentence when it is running (the answer is handed to it as ground
    #: truth below), which means the phrasing is natural and the numbers cannot
    #: be invented: and with the model stopped the computed sentence is
    #: already a complete answer on its own.
    meaning_loading = False
    stats = notebook_stats.answer(question, session) if detected == intent.NOTES and as_of is None else None
    if detected == intent.UTILITY:
        #: **Worked out, like a count** (CHAT_PLAN decision 41): a sum, a
        #: conversion, the time. Its sentence is exact and needs no model, so
        #: it travels the counted answer's road: no retrieval, said as it is.
        #: Translating is a model's job when one runs: that one is chat.
        from tessellate.ai import utilities

        worked = None
        if utilities.kind_of(question) != "translate" or not deps.get_ollama().is_running():
            worked = composer.compose(question, [], today=user_now(deps.get_config()).date(), now=user_now(deps.get_config()).replace(tzinfo=None))
        if worked and worked["shape"] == "utility":
            stats = notebook_stats.StatAnswer(kind="utility", text=worked["text"], facts=[])
        else:
            detected = intent.SMALLTALK
    if stats is None and as_of is None and not attached:
        #: **The app's own records** (CHAT_PLAN A3): "what did I search
        #: yesterday", "what ran overnight", "when did I last back up" are
        #: read from History, the job records and the backup folder, with
        #: times, and never searched for in the notes.
        from tessellate.ai import records

        if records.asks(question):
            config = deps.get_config()
            stats = records.answer(question, session, now=user_now(config), data_dir=config.data_dir)
    connected_ids: set[int] = set()
    match_info: dict = {}
    when_phrase = ""
    # `attached_notes_only`: the caller has already chosen the exact, closed
    # set of notes this turn should see, running retrieval on top would only
    # add notes nobody asked for, matched against whatever the turn's own
    # instruction text happens to contain rather than anything the user
    # picked. Only takes effect when there is something attached to fall
    # back to; an empty attachment list with this flag set would otherwise
    # search nothing at all and answer from silence.
    if stats is not None:
        #: Nothing to retrieve: the answer is a count, and five notes about
        #: whatever the question sounded like would only be noise beside it.
        entries, mode = [], "stats"
    elif intent.needs_retrieval(detected) and not (attached_notes_only and attached):
        #: Searched with the person's own abbreviations spelt out ("what's
        #: due in CC" also finds the notes that say Cloud Computing, B7).
        meaning_loading = _meaning_loading()
        found = search_manager.retrieve_detailed(
            session, glossary.expand(question, _glossary(session)), deps.get_embeddings(), limit=5
        )
        entries, mode = found.entries, found.mode
        entries = _with_neighbours(session, question, _widened(session, question, entries, scope=found.category), scope=found.category)
        entries = list_pool.pool(session, question, entries)
        # Which of these are here because they are *connected* to a match
        # rather than because they matched. The user asked about one thing and
        # is being shown notes about another; without saying why, the panel
        # looks like the search misfired, and the model, told nothing, would
        # report them as results.
        connected_ids = found.connected_ids
        match_info = found.match_info
        when_phrase = found.when_phrase
        #: **A recall by time reads the window, not a ranking** (CHAT_PLAN
        #: decision 31): "what did I do last week" is every note of that week,
        #: newest first, which five notes ranked by likeness never were.
        if not attached and as_of is None:
            asked = composer.plan(question, user_now(deps.get_config()).date())
            if asked.kind == "recall" and asked.window:
                entries = search_manager.entries_between(session, asked.window[0], asked.window[1])
                mode, connected_ids, match_info, when_phrase = "window", set(), {}, asked.window_phrase
    else:
        entries, mode = [], "none"

    #: **As of a date** (WORLD_CLASS_PLAN I5, row 23; `ai/timetravel.py`):
    #: the candidates are today's matches and every note whose past text
    #: matches, each read as it stood at the end of that day, those that did
    #: not exist then dropped. With none left the answer is the honest empty
    #: one, said without a model, never today's notebook.
    as_of_then: dict = {}
    if as_of is not None and intent.needs_retrieval(detected):
        from tessellate.ai import timetravel

        found = search_manager.retrieve_detailed(session, question, deps.get_embeddings(), limit=20)
        candidates = found.entries + timetravel.revision_candidates(session, question)
        zone = user_now(deps.get_config()).tzinfo
        rewound = timetravel.rewind(session, question, timetravel.end_of_day(as_of, zone), candidates, limit=5)
        entries, mode = [then.entry for then in rewound], "as of"
        connected_ids, match_info = set(), {}
        as_of_then = {then.entry.id: then for then in rewound}
        if not rewound:
            stats = notebook_stats.StatAnswer(
                kind="as_of_empty",
                text=(
                    f"There are no notes from on or before {timetravel.day_words(as_of)} to answer "
                    "from, so there is nothing to say about how things stood then."
                ),
                facts=[],
            )

    # Attached notes come first and are never dropped by the retrieval limit.
    # Anything retrieval also found is de-duplicated against them.
    attached_ids = {entry.id for entry in attached}
    entries = attached + [e for e in entries if e.id not in attached_ids]
    if attached:
        mode = "attached" if mode == "none" else f"attached + {mode}"

    def as_note(entry) -> dict:
        content = as_of_then[entry.id].text if entry.id in as_of_then else entry.content
        if entry.id in attached_ids:
            # Only for notes the user picked by hand. A retrieved note is a
            # candidate; an attached one is the subject of the question, and
            # that is worth the extra characters, doing this for all ten
            # search hits would spend the notes budget on pictures nobody
            # asked about.
            content = f"{content}{_media_readings(session, content)}{_attachment_readings(session, entry.id)}"
        elif _mostly_pictures(content):
            content = f"{content}{_media_readings(session, content)}"
        elif _MEDIA_REF.search(content or ""):
            #: **A picture's caption is the note's content** (CHAT_PLAN
            #: decision 37; the owner: "Note captions arent counted as note
            #: content"): every retrieved note with a picture brings what its
            #: pictures show, one line each, so an answer can quote the
            #: caption. The text read in them stays for a note that is mostly
            #: pictures or was picked by hand: it can run to pages.
            content = f"{content}{_media_readings(session, content, captions_only=True)}"
        return {
            # id lets agent-mode tool calls target these notes;
            # the plain librarian prompt simply ignores it.
            "id": entry.id,
            "content": content,
            #: How many pictures the note holds: the prompt says so, because
            #: the answer shows them beside this note's citation (INBOX 502).
            "pictures": len(set(_MEDIA_REF.findall(entry.content or ""))),
            "category": manager.category_name_for(session, entry),
            # Marked so the prompt can say which notes the user chose.
            "attached": entry.id in attached_ids,
            # Clipped from the web or imported (SEC-02): the agent starts the
            # turn tainted, so writes and reaching out ask first.
            "from_outside": manager.came_from_outside(entry),
            # …and which arrived by the graph rather than by the search. The
            # prompt renders this as a caveat, so an answer can say "you linked
            # this to the note about X" instead of implying it was a hit.
            "connected": entry.id in connected_ids,
            # Already computed (match_info feeds the frontend's own similarity/
            # hops badges) and already shown to the user, just never reached
            # the model itself before. Asked for directly: "can the ai see the
            # link reasons and similarity scores in the searches?" It's the
            # score half of that; a linked note's own reason text would need
            # tracing back to the specific Link row, a bigger change not made
            # here.
            "match_info": match_info.get(entry.id),
            #: The day it was written, and edited if since (wrapup-0927 10 n):
            #: with no dates a model guessed "your last entry" from the order
            #: the notes were listed in.
            "written": _note_dates(entry, zone)
            + (f", as it read on {as_of.day} {as_of:%B %Y}" if entry.id in as_of_then else ""),
            "dates": _time_words(time_words.get(entry.id, []), today),
            #: Its tags and the files on it, which the model never saw (INBOX
            #: 594, the owner: "it only mentions one of the sketches not all
            #: the sketches"). Two of three sketches were notes whose text is
            #: one word with a `sketch.png` attached and `#Sketches` on them;
            #: shown "[Hobbies] whoaaahhh", the model called them "too vague".
            "tags": manager.entry_tags(entry),
            "files": files_on.get(entry.id, []),
        }

    now = user_now(deps.get_config())
    zone, today = now.tzinfo, now.date()
    time_words = manager.entry_dates_bulk(session, [entry.id for entry in entries])
    files_on = _files_on(session, [entry.id for entry in entries])
    notes = [as_note(entry) for entry in entries]
    #: Listed newest first for "my last note": said on the first, which a
    #: small model otherwise ignores the order of (measured on a 1.5B model).
    if mode == "recent" and notes:
        notes[0]["newest"] = True
    # Same shape `as_note` builds, by hand rather than through it, a
    # Document has no category/tags and its id lives in a different table
    # than Entry's, so folding it through the Entry-shaped helper above
    # would be the wrong abstraction, not a shortcut. `connected`/
    # `match_info` are never true for a hand-picked document, same as an
    # attached note.
    notes.extend(
        {
            "id": document.id,
            "content": f"{document.title}\n\n{document.content}",
            "category": "Document",
            "kind": "document",
            "attached": True,
            "connected": False,
            "match_info": None,
        }
        for document in attached_docs
    )
    # Library files, already shaped as context rows by `_attached_files`.
    notes.extend(attached_files)
    # Mind maps, likewise: `_attached_boards` builds the outline.
    notes.extend(attached_boards)
    config = deps.get_config()
    # The name and the capped "About me", or nothing while the profile switch
    # is off: `librarian.profile_from_config` is the one place that decides.
    profile = librarian.profile_from_config(config)

    # Every entry this question surfaced counts as "used".
    for entry in entries:
        entry.access_count += 1
    manager.log_action(session, "queried", surface, detail=question)
    session.commit()
    logging.getLogger("tessellate.chat").info(
        "chat: %d note(s) via %s search for %r",
        len(entries),
        mode,
        # The question is the user's own text, and it reaches the terminal as
        # well as the in-app viewer, a bare %r of it can forge a log line.
        safe_value(question, 80),
    )

    return {
        "notes": notes,
        "intent": detected,
        #: The computed answer, when this was a question about the notebook's
        #: shape rather than its contents. `text` is already a complete answer
        #:, which is what makes these work with the model stopped, and the
        #: prompt below hands it to the model as ground truth rather than
        #: asking it to work the numbers out.
        "stats": (
            {"kind": stats.kind, "text": stats.text, "facts": stats.facts, "offer": stats.offer}
            if stats is not None
            else None
        ),
        #: The search model was still loading, so this one read words only
        #: (`search_manager.query_vector`): said in Why, and when nothing
        #: matched, said with the answer.
        "meaning_loading": meaning_loading,
        "raw_results": [
            _to_out(session, entry).model_copy(update={"content": as_of_then[entry.id].text})
            if entry.id in as_of_then
            else _to_out(session, entry)
            for entry in entries
        ],
        #: The day asked about and, per note, the revision its text came from
        #: (None for a note that read the same then as now).
        "as_of": as_of.isoformat() if as_of is not None else None,
        "as_of_revisions": {str(i): then.revision_id for i, then in as_of_then.items()},
        #: Words for each retrieved note's pictures, for the thumbnails an
        #: answer draws beside a citation (INBOX 502, `_picture_alts`).
        "picture_alts": _picture_alts(session, entries),
        "picture_sizes": _picture_sizes(entries),
        "search_mode": mode,
        # Ids that came along because they are *connected* to a match, so the
        # results panel can label them rather than presenting a note about
        # something else as though the search had found it. Sent beside the
        # results rather than as a field on EntryOut: it is a fact about this
        # search, not about the note, and every other route that returns an
        # entry would otherwise carry a field that is always false.
        "connected_ids": sorted(connected_ids),
        # str() keys: match_info is keyed by entry id internally, but JSON
        # object keys are always strings and Pydantic's dict[str, dict]
        # won't silently coerce an int key for us here.
        "match_info": {str(k): v for k, v in match_info.items()},
        "when_phrase": when_phrase,
        "style": config.get_preference("communication_style", "friendly"),
        "profile": profile,
    }


@router.post("", response_model=ChatResponse)
def chat(body: ChatRequest, session: Session = Depends(get_session)) -> ChatResponse:
    _apply_scope(session, body)
    _apply_open(session, body)
    prepared = _prepare(
        session,
        body.question,
        body.note_ids,
        attached_notes_only=body.attached_notes_only,
        document_ids=body.document_ids,
        file_ids=body.file_ids,
        board_ids=body.board_ids,
        # This endpoint has no tool loop, it retrieves and answers, nothing
        # else: so every turn through it is an ask by construction.
        surface=ASK_SURFACE,
        # Row 23: the same time travel the stream takes.
        as_of=body.as_of,
    )
    #: This surface's own model, if one is set (model_manager.FEATURES).
    #: A view over the same manager, so everything downstream, the agent
    #: loop included, goes on asking for `chat_model()` and gets this
    #: surface's answer without knowing features exist.
    model_manager = deps.get_model_manager().for_feature(_feature_for(body))
    ollama = deps.get_ollama()
    ollama_running = ollama.is_running()
    conversational = not intent.needs_retrieval(prepared["intent"])
    mode = _resolve_mode(body.mode)
    images_raw = _resolve_chat_images(session, body.image_media_ids)
    chat_sees_images = bool(images_raw) and _chat_model_sees_images(model_manager, ollama)
    images = [uri for _, uri in images_raw] if chat_sees_images else []
    image_context = (
        "" if chat_sees_images else _image_caption_context(images_raw, model_manager, ollama)
    )
    #: A counted answer *is* an answer, and it does not need a model running to
    #: be one: which is the whole point of computing it. Without this the
    #: response would carry a correct sentence and simultaneously report that
    #: nothing had been answered.
    answered = prepared["stats"] is not None or (
        (conversational or bool(prepared["notes"]) or bool(images_raw)) and ollama_running
    )
    shared = {
        "style": prepared["style"],
        "profile": prepared["profile"],
        "history": [turn.model_dump(exclude_none=True) for turn in body.history],
        "persona_prompt": _resolve_persona(body.persona, session),
    }
    if prepared["stats"] is not None:
        #: **Counted, not generated.** The answer to "what are my most common
        #: tags" is a fact about rows, and `notebook_stats` has already written
        #: it as a sentence. Handing it to the model to rephrase would put a
        #: generator between the user and a number that is already exact, for
        #: nothing but style: and would make the one feature here that works
        #: with the model stopped depend on the model. So it is returned as it
        #: stands, instantly, whether or not anything is running.
        ai_response, ai_thinking = prepared["stats"]["text"], None
    elif conversational and body.notes_only:
        # Same rule as the streaming route: this box interrogates the
        # notebook and does not chat (§35A).
        ai_response, ai_thinking = librarian.ASK_IS_FOR_NOTES, None
    elif conversational:
        ai_response, ai_thinking = librarian.converse(
            body.question,
            prepared["intent"],
            model_manager,
            ollama,
            mode=mode,
            images=images,
            image_context=image_context,
            **shared,
        )
    else:
        ai_response, ai_thinking = librarian.answer(
            body.question,
            prepared["notes"],
            model_manager,
            ollama,
            mode=mode,
            images=images,
            image_context=image_context,
            # The Ask box (`notes_only`) gets the overview brief instead of
            # the chat one: see `librarian.ASK_OVERVIEW`.
            ask_overview=body.notes_only,
            **shared,
        )
    # Direct Q&A only: conversational replies aren't grounded in retrieved
    # notes at all (there may be none), and grounding one would attach a
    # note to a sentence that has nothing to do with it.
    sentence_grounding = (
        ground_answer_sentences(
            ai_response, prepared["notes"],
            meaning=search_chunks.meaning_scorer(session, deps.get_embeddings()),
        )
        if not conversational and answered
        else []
    )
    return ChatResponse(
        ai_response=ai_response,
        ai_thinking=ai_thinking,
        raw_results=prepared["raw_results"],
        picture_alts=prepared.get("picture_alts") or {},
        picture_sizes=prepared.get("picture_sizes") or {},
        search_mode=prepared["search_mode"],
        connected_ids=prepared["connected_ids"],
        match_info=prepared["match_info"],
        when_phrase=prepared["when_phrase"],
        #: **A counted answer was not answered by a model, and must not say it
        #: was.** `answered` is true for one (see its own note above) but
        #: `answered_by` names *who* wrote the sentence, and for these the
        #: honest answer is nobody, the numbers came from rows. Naming the
        #: chat model here would put its name under a sentence it never saw,
        #: which is exactly the kind of small false claim this app cannot
        #: afford to make about its own AI.
        answered_by=(
            None
            if prepared["stats"] is not None
            else (model_manager.served_chat_model(ollama) if answered else None)
        ),
        ollama_running=ollama_running,
        sentence_grounding=sentence_grounding,
    )


def _save_ask_turn(
    session: Session,
    question: str,
    answer: str,
    prepared: dict,
    grounding: list[dict] | None = None,
) -> None:
    """Durable record of one Ask-box turn, for routes_ask_history.py's browse
    panel. Only ever called for `notes_only` requests (the Ask box's own
    flag, §35A) with a real answer, a small-talk turn on that box always
    exits through the "hint" branch below instead, never reaching this call,
    so nothing here needs to re-check for that case.
    """
    session.add(
        AskTurn(
            question=question,
            answer=answer,
            raw_result_ids=json.dumps([r.id for r in prepared["raw_results"]]),
            search_mode=prepared["search_mode"],
            when_phrase=prepared["when_phrase"],
            match_info=json.dumps(prepared["match_info"]),
            connected_ids=json.dumps(prepared["connected_ids"]),
            #: The citations as they were written, so the history panel can
            #: redraw the numbered markers and the "grounded in" chips rather
            #: than reopening a turn as bare prose (INBOX 241). The rows are
            #: already plain dicts of primitives by the time they reach here.
            grounding=json.dumps(grounding or []),
        )
    )
    session.commit()


# **"Nothing in your notes" should not be the end of the answer.**
#
# Asked for directly: "idk if the ai should be able to look for related
# semantic results for alternate items like reminders, chat sessions, docs etc
# related to the notes if no notes are found?? like similar items??"
#
# Retrieval only ever searched notes, so a question whose answer sits in a
# document, a saved chat or a reminder came back as a flat "I couldn't find
# any saved notes matching that question", true, useless, and on a notebook
# that has grown documents and chats, misleading about how much the app holds.
#
# Keyword matching on purpose rather than embeddings: this runs *only* on the
# already-empty path, where being slightly less clever costs nothing and
# another model round trip would just buy a second wait for a second
# disappointment. Workspace scoping comes from `WorkspaceMixin`, as everywhere.
_RELATED_LIMIT = 4


def _related_elsewhere(session: Session, question: str) -> list[dict]:
    """Documents, saved chats and reminders matching a question no note answered."""
    words = re.findall(r"[\w']{3,}", (question or "").lower())[:6]
    if not words:
        return []
    found: list[dict] = []

    def _add(rows, kind: str, label_of, id_of) -> None:
        for row in rows:
            if len(found) >= _RELATED_LIMIT:
                return
            found.append({"kind": kind, "id": id_of(row), "label": label_of(row)})

    # One query per kind, not one per (kind, word).
    #
    # This used to loop the six words and run three queries inside the loop,
    # so a question with six usable words cost eighteen round trips, each of
    # them an `ILIKE '%word%'` whose leading wildcard no index can serve: a
    # full scan of `documents.content` and `conversations.messages`, the two
    # widest text columns in the schema. Measured on a notebook of 2,000
    # documents, 2,000 saved chats and 2,000 reminders, 400 words of body
    # each: 139.8 ms median, on the path every chat answer takes when no note
    # answered the question. Folding the words into one OR per kind does the
    # same three scans once instead of six times.
    #
    # What changes: a document matching only the sixth word can now outrank
    # one matching the first, because the order is `updated_at` across the
    # whole match set rather than word by word. That is the better order for
    # this panel anyway (it says "related elsewhere", not "related to your
    # first noun"), and the kinds still fill in the same order, documents,
    # then chats, then reminders, so a question whose matches are all
    # documents still gets four documents.
    def _any_word(*columns):
        return or_(
            *(
                col.ilike(f"%{like_escape(word)}%", escape=LIKE_ESCAPE)
                for col in columns
                for word in words
            )
        )

    _add(
        session.scalars(
            select(Document)
            .where(_any_word(Document.title, Document.content))
            .order_by(Document.updated_at.desc())
            .limit(_RELATED_LIMIT)
        ).all(),
        "document",
        lambda d: d.title or "Untitled",
        lambda d: d.id,
    )
    _add(
        session.scalars(
            select(Conversation)
            .where(_any_word(Conversation.title, Conversation.messages))
            .order_by(Conversation.updated_at.desc())
            .limit(_RELATED_LIMIT)
        ).all(),
        "chat",
        lambda c: c.title or "Untitled chat",
        lambda c: c.id,
    )
    _add(
        session.scalars(
            select(Reminder)
            .where(_any_word(Reminder.text))
            .order_by(Reminder.due_at.desc())
            .limit(_RELATED_LIMIT)
        ).all(),
        "reminder",
        lambda r: r.text,
        lambda r: r.id,
    )
    # De-duplicated on (kind, id): one word matching a document's title and
    # another matching its body would otherwise list it twice.
    seen: set[tuple[str, int]] = set()
    unique: list[dict] = []
    for item in found:
        key = (item["kind"], item["id"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:_RELATED_LIMIT]




@dataclass(slots=True)
class _StreamRequest:
    """Everything one `/chat/stream` call settles before it opens the stream.

    These fifteen values were locals read off a closure, which is fine until
    the two closures reading them are 150 and 219 lines long and the route
    they sit in is 424 (WORLD_CLASS_PLAN A5). As a record they can be passed
    to a module-level stage, and the route reads as what it is: resolve the
    request, then stream it.
    """

    body: ChatRequest
    session: Session
    ollama: object
    model_manager: object
    history: list[dict]
    persona_prompt: str | None
    mode: str
    #: The uploads themselves, with their data URIs, for the caption fallback.
    images_raw: list
    #: The data URIs actually sent to the model, empty when it cannot see them.
    images: list[str]
    #: What the captions say instead, when it cannot.
    image_context: str
    use_tools: bool
    #: The skill or plan this turn is running, None for an ordinary question.
    skill: dict | None
    #: The skill's own instruction when there is one, else what the user asked.
    question: str
    allowed_tools: list[str] | None
    #: Set by Stop in Activity. The run's Activity job and its budget share it,
    #: so a write the model asked for as Stop landed is refused (Brief 101b).
    stop: threading.Event = field(default_factory=threading.Event)
    #: What the message called the assistant ("hey lil bro, ..."), taken off
    #: `question` (`vocative.split`); `call` when that was all it said.
    address: vocative.Address | None = None
    #: The whole of a question longer than `composer.PLAN_CHARS`, which only the
    #: model and the saved turn read; `question` is what the app plans over.
    full_question: str | None = None


def _in_full(req: _StreamRequest) -> str:
    """The question as asked, for the model and the saved turn."""
    return req.full_question or req.question


def _composed(req: _StreamRequest, ollama_running: bool) -> bool:
    """Whether this turn's answer is composed from the notes (INBOX 688): an
    Ask-box turn that asked for it, or any Ask-box turn with no model to ask.
    The Chat tab composes too, but only when no model runs (`_plain_events`)."""
    return bool(req.body.notes_only) and (req.body.answer_from == "notes" or not ollama_running)


def _answer_voice() -> str:
    """The voice an answer with no model is said in (CHAT_PLAN decision 72),
    the `composer_voice` preference: "natural" (Warm and concise, the
    default), "professional" (Neutral), "playful" or "plain"."""
    try:
        value = deps.get_config().get_preference("composer_voice", "natural")
    except Exception:  # noqa: BLE001  # no preference is the default voice
        return "natural"
    return value if value in ("natural", "professional", "playful", "plain") else "natural"


def _insight_level() -> str:
    """How much Atlas volunteers past the answer (CHAT_PLAN decision 73), the
    `insight_level` preference: "off", "one" line (the default) or "all"."""
    try:
        value = deps.get_config().get_preference("insight_level", "one")
    except Exception:  # noqa: BLE001  # no preference is the default
        return "one"
    return value if value in composer_digest.INSIGHT_LEVELS else "one"


def _composer_voice() -> str:
    """The composer's own register for the same choice: it has two, so
    Playful joins with Natural's words and Plain with Professional's."""
    return {"playful": "natural", "plain": "professional"}.get(_answer_voice(), _answer_voice())


def _meaning_loading() -> bool:
    """Whether a search now would read words only, the search model not
    loaded yet (the owner's 27 s first question, 2026-10-11)."""
    try:
        embeddings = deps.get_embeddings()
        cold = getattr(embeddings, "loads_cold", None)
        from tessellate.ai import embeddings as embedding_service

        return bool(callable(cold) and cold()) or (embedding_service.warmup_running() and not embeddings.is_ready())
    except Exception:  # noqa: BLE001  # no backend is a state, not an error
        return False


def _composer_embed():  # noqa: ANN202
    """The embedder's `embed_many` when a backend is ready, else None: the
    composer then measures meaning by shared words (INBOX 725, embeddings
    optional by decision)."""
    try:
        embeddings = deps.get_embeddings()
        return embeddings.embed_many if embeddings is not None and embeddings.is_ready() else None
    except Exception:  # noqa: BLE001  # no backend is a state, not an error
        return None


def _assist(req: _StreamRequest, prepared: dict) -> None:
    """The composer's two parts in a turn a model answers (CHAT_PLAN, "the
    composer everywhere" 9 and 10; the owner, 2026-10-06: "ai should still be
    the core when it is available, but the composer should be used to lessen
    the load ... as well as cheapen the run cost of the ai").

    `prepared["preview"]`: the composed answer, sent before the model's first
    token and replaced by it (`composed_preview`). `prepared["model_notes"]`:
    the notes cut to the parts on the question (`composer.brief`), what the
    model reads; `prepared["notes"]` stays whole, since grounding the model's
    answer and saving the turn read the notes as they are.

    Neither for a skill or plan run (its steps read the notes their own way),
    a counted answer, small talk, a "newest notes" question, a picture asked
    about or attached (the composer reads words, and the model is asked about
    what it sees), or a turn with nothing retrieved.
    """
    prepared["model_notes"] = prepared["notes"]
    prepared["preview"] = None
    if (
        req.skill
        or prepared["stats"] is not None
        or not prepared["notes"]
        or not intent.needs_retrieval(prepared["intent"])
        or req.images_raw
        or librarian.PICTURE_ASK.search(req.question or "")
    ):
        return
    recent = str(prepared.get("search_mode") or "").endswith("recent")
    embed = _composer_embed()
    try:
        composed = composer.compose(
            req.question, prepared["notes"], today=user_now(deps.get_config()).date(), recent=recent, embed=embed,
            voice=_composer_voice(),
        )
        packed = composer.brief(req.question, prepared["notes"], recent=recent, embed=embed, composed=composed)
    except Exception:  # noqa: BLE001  # the model answers from the notes as they are
        logging.getLogger("tessellate.chat").exception("chat: the composer's brief failed")
        return
    if composed.get("grounding"):
        prepared["preview"] = {
            "type": "composed_preview",
            "text": composed["text"],
            "grounding": composed["grounding"],
            "next": composed["next"],
        }
    if packed and packed["shortened"]:
        prepared["model_notes"] = packed["notes"]
        prepared["brief"] = {
            "before": packed["chars_before"] // context.CHARS_PER_TOKEN,
            "after": packed["chars_after"] // context.CHARS_PER_TOKEN,
        }


#: How many web pages an answer with no model reads, and how much of each:
#: enough for a sentence that answers, never a crawl (decision 37).
WEB_PAGES = 3
WEB_PAGE_CHARS = 4000


def _web_first(req: _StreamRequest, prepared: dict) -> bool:
    """The web before the notes: when no note matched, or when the turn asks
    for the web outright ("search the web for ...")."""
    return not prepared["notes"] or toolwords.asks_web(req.question)


def _web_allowed(req: _StreamRequest) -> bool:
    """Web sources only when the person turned web search on in Settings and
    the turn may use tools (decision 43: never fetched without the toggle)."""
    try:
        return bool(deps.get_config().get_preference("web_search_enabled", False)) and bool(req.use_tools)
    except Exception:  # noqa: BLE001  # no preference is off
        return False


def _web_pages(websearch, results: list[dict]) -> list[dict]:  # noqa: ANN001
    """The top hits read as pages, each a source of kind "web"; a page that cannot be read is skipped."""
    pages: list[dict] = []
    for i, hit in enumerate(results[:WEB_PAGES]):
        try:
            page = websearch.fetch_readable_cached(str(hit.get("url") or ""))
        except websearch.WebSearchError:
            continue
        text = str(page.get("text") or "")[:WEB_PAGE_CHARS]
        title = " ".join(str(page.get("title") or hit.get("title") or page.get("domain") or "A web page").split())
        if text.strip():
            pages.append({
                "id": -(i + 1), "kind": "web", "url": str(page.get("url") or hit.get("url")), "domain": page.get("domain", ""),
                "content": f"{title}\n\n{text}",
                #: The result's one line for the panel: the engine's snippet,
                #: else the page's opening.
                "snippet": " ".join(str(hit.get("snippet") or text[:200]).split())[:200],
            })
    return pages


def _web_answer(req: _StreamRequest, question: str) -> tuple[dict, list[dict]] | None:
    """An answer composed from web pages (CHAT_PLAN decision 37, the second
    half): the search the agent's `web_search` uses, the top pages read as
    text (`fetch_readable_cached`, the reader's own checks), each page a
    source of kind "web" cited by its address. None when nothing answers."""
    from tessellate.search import websearch

    config = deps.get_config()
    searxng_url, provider = websearch.settings_from(config)
    try:
        results = websearch.search_web(composer_digest.web_query(question), limit=5, searxng_url=searxng_url or None, provider=provider)
    except websearch.WebSearchError:
        logging.getLogger("tessellate.chat").info("chat: web search failed for a composed answer", exc_info=True)
        return None
    pages = _web_pages(websearch, results)
    if not pages:
        return None
    composed = composer.compose(question, pages, today=user_now(deps.get_config()).date(), voice=_composer_voice())
    #: Decision 66: pages found are always an answer, in decision 70's shape,
    #: the composer's best span of each page first.
    result = composer_digest.web(question, pages, composed)
    if result is None:
        return None
    sources = [{"title": p["content"].split("\n", 1)[0], "url": p["url"], "domain": p["domain"], "snippet": p["snippet"]} for p in pages]
    return result, sources


def _composed_support(result: dict) -> dict:
    """The support of an answer no model wrote (`by_model: False`): every
    sentence of it is quoted or the app's own joining words, so the notice
    says something only when most of what it quotes is how the app read a
    picture (INBOX 787: "Only 0 of 2 sentences here are quoted" under an
    answer that had nothing else to say)."""
    rows = result.get("grounding") or []
    pictures = sum(1 for row in rows if row.get("said") == "picture")
    return {**result["support"], "by_model": False, "low": pictures * 2 > len(rows) > 0}


def _web_events(result: dict, sources: list[dict]) -> Iterator[dict]:
    yield {"type": "answer", "delta": result["text"]}
    yield {
        "type": "grounding",
        "sentences": result["grounding"],
        "next": result["next"],
        "support": _composed_support(result),
        "exact": True,
    }
    #: The pages read, for the scrollable list inside the bubble.
    yield {"type": "web_sources", "sources": sources}


#: Under an answer composed from the notes because the model stopped mid-turn.
MODEL_STOPPED_NOTE = "The model stopped before it could answer, so this is Atlas's answer from your notes."

#: A how-to about the app, answered from its Help when no model writes the
#: answer (CHAT_PLAN decision 36, the help register).
#: "why is the chat so slow" is a how-to too: the Guide answers it (Performance mode).
_HOW_TO = re.compile(r"^\s*(?:how (?:do|can|would|should) i|how to|where (?:is|are|do i find|can i find)|why (?:is|does))\b", re.I)


#: A counted answer's facts drawn as a bar of counts (decision 59, step 2):
#: the stats kinds whose facts are a count per name, and what a bar names.
_STATS_BY = {"tags": "tag", "categories": "category", "subjects": "tag"}


def _stats_chart(stats: dict) -> dict | None:
    from tessellate.ai import realise

    by = _STATS_BY.get(str(stats.get("kind") or ""))
    rows = [{"name": str(f.get("label")), "notes": int(f.get("count") or 0)} for f in stats.get("facts") or [] if isinstance(f, dict) and "count" in f]
    if by is None or realise.form_of(rows) != "chart":
        return None
    return realise.chart(f"Notes per {by}", by, rows)


def _tool_read_events(req: _StreamRequest) -> list[dict]:
    """A read tool run with no model (decision 59, steps 1 and 2): the reading
    names the tool (`reading.tool_of`), Chat runs it with no arguments, and
    the realiser says it in one line and draws it in its form. Empty when the
    sentence names no such tool, so the composer answers as before."""
    from tessellate.ai import act_registry, commands, question_noise, reading, realise, tool_say
    from tessellate.ai import tools as agent_tools

    now = user_now(deps.get_config())
    #: Read as repaired: "shwo me evry tag i hav plz" is the tag list, as
    #: "list my tags" is (the routing gold, `fixtures/composer/routing_1011.json`).
    asked = question_noise.repair(question_noise.tidy(req.question or ""))
    filed = commands.filed_listing(asked)
    if filed:
        #: "list my work notes": the Work notes, or the notes tagged work
        #: (ledger row 442); a name that is neither is the composer's.
        for key in ("category", "tag"):
            args = {key: filed}
            result = agent_tools.execute_tool(req.session, "list_notes", args)
            if isinstance(result, dict) and result.get("total_matching"):
                said = tool_say.say("list_notes", result, args, now.date())
                return [{"type": "answer", "delta": said["text"]}]
    got = reading.read(asked, now=now)
    if got.tool not in act_registry.NO_MODEL_READS or got.intent in act_registry.ACTS:
        return []
    result = agent_tools.execute_tool(req.session, got.tool, {})
    drawn = realise.tool_answer(got.tool, result, now.date())
    #: Said with its links to what it lists and the place to open
    #: (`tool_say`); a chart, when the counts make one, stands for the table.
    said = tool_say.say(got.tool, result, {}, now.date())
    chart = drawn["chart"] if drawn else None
    parts = (said["lead"], "" if chart else said["body"], said["chips"])
    out = [{"type": "answer", "delta": "\n\n".join(p for p in parts if p)}]
    if chart:
        out.append({"type": "chart", "chart": chart})
    return out


def _asks_capability(req: _StreamRequest, prepared: dict) -> bool:
    """"Can you search the web?" (CHAT_PLAN decision 65): a question about
    what Atlas can do, answered from the app's own list on every surface,
    model or none, and never a search, a web call or a tool."""
    return prepared["intent"] == intent.ABOUT_APP and capability.asks(req.question or "")


def _app_answers(req: _StreamRequest, ollama_running: bool) -> bool:
    """Whether the app's own engine gives this turn's finished answer
    (CHAT_PLAN decision 75, the owner: "it SHOULD completely replace it if
    the ai isnt available, otheriwse the composer is an assistant to the
    ai"): with no model, or when the Ask box asked for From your notes.
    With a model up, what the engine found goes to the model as context."""
    return not ollama_running or _composed(req, ollama_running)


def _capability_answer(req: _StreamRequest, ollama_running: bool) -> str:
    try:
        web = bool(deps.get_config().get_preference("web_search_enabled", False))
    except Exception:  # noqa: BLE001  # an unreadable preference is off
        web = False
    recent, seed = _reply_seed(req)
    return capability.answer(
        req.question, prefs={"web_search_enabled": web}, model_running=ollama_running,
        voice=_composer_voice(), recent=recent, seed=seed,
    )


def _in_notes(session: Session):  # noqa: ANN202
    """Whether any note, or any person or thing the notes name, holds a
    word: such a word is never taken for an invented nickname. Asked only of
    a word that is otherwise invented, so at most once or twice a message."""

    def holds(word: str) -> bool:
        if not word.isalpha():
            return False
        try:
            found = session.execute(
                sql_text("SELECT 1 FROM entries_fts WHERE entries_fts MATCH :w LIMIT 1"), {"w": f'"{word}"'}
            ).first()
            return found is not None or session.scalar(select(Entity.id).where(func.lower(Entity.name) == word).limit(1)) is not None
        except Exception:  # noqa: BLE001  # no index yet: nothing is known
            return False

    return holds


def _reply_seed(req: _StreamRequest) -> tuple[list[str], str]:
    """The last replies in this conversation, oldest first, and its seed: the
    chat's salt, the day and the Ask again count, so a new chat on a new day
    opens differently and a replayed one says the same."""
    history = req.history or []
    recent = [str(turn.get("answer") or "") for turn in history[-phrasing.RECENT :]]
    salt = composer.Dialogue.from_history(history).salt
    return recent, f"{salt}:{date.today().isoformat()}:{req.body.attempt}"


def _social_reply(req: _StreamRequest, prepared: dict) -> str:
    """The app's own reply to small talk (INBOX 741), never echoing the last
    three replies (the owner: "can it have more varied responses??")."""
    recent, seed = _reply_seed(req)
    last = (req.history or [{}])[-1] if req.history else {}
    return composer.social(
        req.question,
        prepared["intent"],
        str(last.get("answer") or ""),
        str(last.get("question") or ""),
        voice=_composer_voice(),
        recent=recent,
        seed=seed,
        invite=_newest_word(req.session),
    )


def _newest_word(session: Session) -> str:
    """A word the newest note is about, for a hello's invitation (O5): its
    first search term of four letters or more that is an everyday word, so
    "what did I write about golf" finds the note it came from; "" when
    there is none."""
    from tessellate.ai import spelling
    from tessellate.ai.tools._common import _visible
    from tessellate.core.database import Entry
    from tessellate.search import query as query_understanding

    newest = session.query(Entry.content).filter(*_visible()).order_by(Entry.created_at.desc()).first()
    if not newest:
        return ""
    for term in query_understanding.search_terms(str(newest[0] or "")[:400]):
        if len(term) >= 4 and term.isalpha() and term not in _NOT_A_SUBJECT and spelling.is_word(term):
            return term
    return ""


#: A note's kind, not what it is about ("Idea: build a bird feeder").
_NOT_A_SUBJECT = frozenset("idea ideas note notes todo todos reminder thought thoughts list draft remember".split())


def _call_events(req: _StreamRequest) -> list[dict]:
    """A message that only called the assistant: here, and three things to
    ask next as chips (an "ask" offer; the follow-up strip draws them)."""
    recent, seed = _reply_seed(req)
    line = composer.call(req.address.names, recent=recent, seed=seed, voice=_composer_voice())
    return [
        {"type": "answer", "delta": line},
        {"type": "offer", "offer": {"kind": "ask", "label": "", "asks": composer.call_asks(seed)}},
    ]


def _app_said(req: _StreamRequest, prepared: dict, ollama_running: bool) -> list[dict] | None:
    """What the app says itself when it answers (`_app_answers`): about Atlas
    ("do you have feelings", the owner, 2026-10-11), a capability, a call, a
    place ("where is the bin?", `ai/find_it.py`, with a link that opens it),
    or that nothing is open."""
    itself = personal.about_me(req.question or "")
    if itself:
        return [{"type": "answer", "delta": itself}]
    if _asks_capability(req, prepared):
        return [{"type": "answer", "delta": _capability_answer(req, ollama_running)}]
    if req.address is not None and req.address.call:
        return _call_events(req)
    placed = find_it.answer(req.question or "") if not req.images_raw else None
    if placed is not None:
        return [{"type": "answer", "delta": placed["text"]}, {"type": "offer", "offer": placed["offer"]}]
    if _nothing_open(req.body):
        return [{"type": "answer", "delta": composer_digest.PHRASES["nothing_open"]}]
    return None


def _stats_events(stats: dict) -> list[dict]:
    """A counted answer, its chart, and its one acting offer (decision 70),
    drawn as a link on its line."""
    out = [{"type": "answer", "delta": stats["text"]}]
    drawn = _stats_chart(stats)
    if drawn is not None:
        out.append({"type": "chart", "chart": drawn})
    if stats.get("offer"):
        out.append({"type": "offer", "offer": stats["offer"]})
    return out


def _exact_events(req: _StreamRequest, prepared: dict, ollama_running: bool) -> list[dict] | None:
    """**A counted answer, streamed as one piece**, or a read tool's answer
    with no model. See the same branch in `chat()`: the number is already
    exact and already a sentence, so there is nothing to generate and nothing
    to wait for. It arrives before a local model would have finished loading,
    and it arrives at all when no model is running. None when the stream
    goes on to compose or generate."""
    said = _app_said(req, prepared, ollama_running) if _app_answers(req, ollama_running) else None
    if said is not None:
        return said
    if prepared["stats"] is not None:
        return _stats_events(prepared["stats"])
    if not ollama_running or prepared.get("tool_read"):
        shown = prepared["tool_read"] if "tool_read" in prepared else _tool_read_events(req)
        if shown:
            return list(shown)
    return None


def _no_notes_line(req: _StreamRequest, ollama_running: bool) -> str:
    """A subject-less question about a time with no note in it ("what did I
    write last month"), said as that with where the notes are; for any
    other question, or when a model answers, the plain "nothing matched" (O1)."""
    if ollama_running and not _composed(req, ollama_running):
        return librarian.NO_RESULTS_MESSAGE
    planned = composer.plan(req.question or "")
    if not planned.window or planned.terms or not planned.window_phrase:
        return librarian.NO_RESULTS_MESSAGE
    from sqlalchemy import func

    from tessellate.ai.tools._common import _visible
    from tessellate.core.database import Entry

    first, last = req.session.query(func.min(Entry.created_at), func.max(Entry.created_at)).filter(*_visible()).one()
    return composer.empty_window(
        planned.window_phrase,
        first.date() if first else None,
        last.date() if last else None,
        voice=_composer_voice(),
        seed=req.question or "",
    )


def _current_notes(req: _StreamRequest, notes: list[dict]) -> tuple[list[dict], list]:
    """The notes with any a newer note on the asked subject supersedes left
    out, and those left out (O11, `ai/supersede.py`)."""
    from tessellate.ai import supersede

    return supersede.current(req.question or "", notes)


def _with_older(text: str, older: list, result: dict) -> str:
    """The answer, and one line on what an older note said, when the answer
    came from the notes and one was set aside (never silently dropped)."""
    from tessellate.ai import supersede

    if not older or not result.get("grounding"):
        return text
    line = supersede.older_line(older, voice=_composer_voice(), today=user_now(deps.get_config()).date(), seed=len(text))
    #: "It's your only note on that so far" is not true with an older one.
    only = {composer_digest._BASE["only_note"], *(v.get("only_note", "") for v in composer_digest.VOICES.values())}
    kept = [part for part in text.split("\n\n") if part.strip() not in only]
    return "\n\n".join([*kept, line])


def _with_lapsed(text: str, current: list, result: dict, req: _StreamRequest) -> str:
    """The answer, and one line when the note it came from says how long it
    holds and that has passed (O11, `supersede.lapsed`)."""
    from tessellate.ai import supersede

    if not current or not result.get("grounding"):
        return text
    today = user_now(deps.get_config()).date()
    found = supersede.lapsed(req.question or "", current, today)
    if found is None:
        return text
    return text + "\n\n" + supersede.lapsed_line(found, voice=_composer_voice(), today=today, seed=len(text))


def _plain_events(req: _StreamRequest, prepared: dict, ollama_running: bool) -> Iterator[dict]:
    """The pre-Wave-G behaviour: stream a grounded answer, no tools."""
    exact = _exact_events(req, prepared, ollama_running)
    if exact is not None:
        yield from exact
        return
    conversational = not intent.needs_retrieval(prepared["intent"])
    if conversational and prepared["intent"] == intent.ABOUT_APP and _HOW_TO.match(req.question or "") and (
        _composed(req, ollama_running) or not ollama_running
    ):
        helped = composer.compose(req.question, [], voice="help")
        if helped["shape"] == "help":
            yield {"type": "answer", "delta": helped["text"]}
            return
    if conversational and _composed(req, ollama_running):
        #: The app answers small talk itself when the answer is composed (the
        #: Ask box's From your notes, or no model): "what can you do" or
        #: "hello" there used to get no answer at all (engine probe P2).
        yield {"type": "answer", "delta": _social_reply(req, prepared)}
        return
    #: A question about what Atlas can do is not small talk: with a model
    #: up it goes to the model with the app's own line (decision 75).
    if conversational and req.body.notes_only and not _asks_capability(req, prepared):
        # The Notes tab's Ask box has one job (§35A). A greeting is the one
        # input it has nothing to do with, so it says what it is for rather
        # than spending a model round chatting back.
        #
        # Its own event type, not an "answer". Reported after the first
        # version shipped: a paragraph of instructions sitting where the
        # answer goes, beside a results panel reading "No matching
        # records", reads as the app having failed. As a hint the client
        # can render it as what it is, a prompt with questions you can
        # click: and can leave the empty results panel out, since nothing
        # was searched for.
        yield {
            "type": "hint",
            "text": librarian.ASK_IS_FOR_NOTES,
            "examples": librarian.ASK_EXAMPLES,
        }
        return
    if conversational:
        # Small talk: no notes, no grounding, no "I couldn't find any
        # notes matching that" in reply to "hey".
        if not ollama_running:
            #: The app's own voice, warm and varied (INBOX 741): with no model
            #: running Chat still answers from the notes, so small talk says
            #: so rather than "the AI model isn't running".
            yield {"type": "answer", "delta": _social_reply(req, prepared)}
            return
        #: Small talk reaches the model as it was said, its nickname and all
        #: ("thanks legend"): the name came off only so nothing searched it.
        said = question_noise.tidy(req.body.question) if req.address is not None else req.question
        messages = librarian.build_conversational_messages(
            f"{said}\n\n{req.image_context}" if req.image_context else said,
            prepared["intent"],
            style=prepared["style"],
            profile=prepared["profile"],
            history=req.history,
            persona_prompt=req.persona_prompt,
            mode=req.mode,
            images=req.images,
            #: Decision 75: the capability line reaches the model as a fact.
            context=_capability_answer(req, ollama_running) if _asks_capability(req, prepared) else "",
        )
    elif _web_first(req, prepared) and not req.images_raw and not ollama_running and _web_allowed(req) and (
        web := _web_answer(req, req.question)
    ):
        #: No note answers, no model runs, and web search is on: the web's
        #: own sentences, cited by address (decision 37).
        yield from _web_events(*web)
        return
    elif not prepared["notes"] and not req.images_raw:
        # An attached image and "no matching notes" are unrelated: 
        # retrieval never sees the image, so an empty search result
        # must not stand in for "there's nothing to look at" (same fix
        # as `librarian.answer`'s own guard).
        yield {"type": "answer", "delta": _no_notes_line(req, ollama_running)}
        # …but the notebook is more than its notes. See
        # `_related_elsewhere`: a question answered by a document, a saved
        # chat or a reminder used to end here regardless.
        related = _related_elsewhere(req.session, req.question)
        if related:
            kinds = sorted({item["kind"] for item in related})
            yield {
                "type": "answer",
                "delta": (
                    " There "
                    + ("is" if len(related) == 1 else "are")
                    + f" {len(related)} other "
                    + ("item" if len(related) == 1 else "items")
                    + " that mention it, in your "
                    + " and ".join(f"{k}s" for k in kinds)
                    + "."
                ),
            }
            yield {"type": "related", "items": related}
        return
    elif _composed(req, ollama_running) or not ollama_running:
        #: **A composed answer** (INBOX 688): the notes' own sentences, chosen
        #: by the question's shape and laid out as an answer, every clause a
        #: quote or a measured value (`ai/composer.py` says how). One piece,
        #: no stream to wait on; its grounding rows are exact, marked so, and
        #: the re-grounding below leaves them alone.
        #:
        #: **And the Chat tab's answer whenever no model runs** (INBOX 725, the
        #: owner: "the composer response should also be able to be viewed in
        #: chat messages"). It replaced `extractive.answer` here, the forty-
        #: word passages under an apology: the composer quotes whole sentences
        #: under the same rule. A running model still answers every Chat turn.
        follow = prepared.get("follow_on")
        #: The conversation the history describes (decisions 34 and 35): its
        #: turn and salt word this answer, a retry ("Try again") rewords it,
        #: and the words earlier answers used are not used again.
        dialogue = composer.Dialogue.from_history(req.history)
        #: The answer a person would give (decision 70, INBOX 812: "I may as
        #: well just read the notes I made on the right"): a count and a
        #: span, the facts under labels, what is missing, one offer. A
        #: follow-on, a "newest notes" turn or a sum keeps the composer's.
        digest = None
        #: A follow-on that is a question in its own right ("what about
        #: running?", "and last month?", "the second one") is answered the
        #: same way as the first turn (B8); "tell me more", "shorter" and a
        #: correction lean on the turn before and keep the composer's.
        restated = follow is not None and follow.kind in composer._RESTATES
        today = user_now(deps.get_config()).date()
        #: "where do I live", "what's my sister's name", "what do you know
        #: about me": what the notebook says of its writer (`ai/personal.py`),
        #: read from every note, not only the ones the search found.
        digest = None if follow else personal.answer(req.question, lambda: personal.notes_of(req.session), today)
        #: O11: a newer note on the same thing is the current one.
        current, older = _current_notes(req, prepared["notes"])
        if digest is None and (not follow or restated) and _may_digest(prepared, req.question):
            try:
                digest = composer_digest.answer(
                follow.question if restated else req.question, current, today=user_now(deps.get_config()).date(),
                voice=_answer_voice(), turn=len(req.history or []),
                insight=_insight_level(), learned=_insight_memory(req.session), known=_verdicts(req.session),
            )
            except Exception:  # noqa: BLE001  # the composer's answer stands
                logging.getLogger("tessellate.chat").exception("chat: the digest failed")
        result = digest or composer.compose(
            follow.question if follow else req.question,
            current,
            today=user_now(deps.get_config()).date(),
            recent=str(prepared.get("search_mode") or "").endswith("recent"),
            embed=_composer_embed(),
            said=follow.said if follow else "",
            voice=_composer_voice(),
            #: The turn before's answer, so this one opens differently (INBOX 741).
            previous=str((req.history or [{}])[-1].get("answer") or "") if req.history else "",
            now=user_now(deps.get_config()).replace(tzinfo=None),
            salt=f"{dialogue.salt}:{req.body.attempt}" if req.body.attempt else dialogue.salt,
            turn=len(req.history or []) + 1 + req.body.attempt,
            dialogue=dialogue,
            prefer=follow.prefer if follow else "",
            resolved=True,
            #: Insights the person confirmed are said as their word; the
            #: ones they dismissed are not said (decision 60).
            learned=_insight_memory(req.session),
        )
        if follow is not None and follow.kind == "more" and not result.get("grounding"):
            #: Nothing left unsaid: say so, with how much there is (B8).
            result = composer_digest.all_said(follow.question, prepared["notes"], today=user_now(deps.get_config()).date()) or result
        if not result["grounding"] and not ollama_running and _web_allowed(req):
            web = _web_answer(req, follow.question if follow else req.question)
            if web:
                yield from _web_events(*web)
                return
        text = result["text"]
        if not result["grounding"] and not follow and personal.general(req.question or ""):
            #: "what's the capital of France": the world, not the notes, and
            #: said so rather than "nothing in your notes about capital".
            text = personal.general_reply(_web_allowed(req))
        if not result["grounding"] and prepared.get("meaning_loading"):
            text += "\n\n" + composer_digest.PHRASES["meaning_loading"]
        text = _with_older(text, older, result)
        text = _with_lapsed(text, current, result, req)
        yield {"type": "answer", "delta": text}
        if result["grounding"]:
            yield {
                "type": "grounding",
                "sentences": result["grounding"],
                #: What to ask next, built from what the answer found and did
                #: not say (INBOX 725): the chips under a composed answer,
                #: which asks no model for them.
                "next": result["next"],
                #: `by_model: False`: no model wrote a word of it, so a low count
                #: is the app's own joining words and picture readings, and the
                #: notice says that rather than "the model's own writing".
                "support": _composed_support(result),
                "exact": True,
                #: The engine's own answer through the same validators
                #: (decisions 52 to 54): empty when every maxim holds.
                "checks": validate.report(result, req.question)["findings"],
                #: The insight lines said, for their Confirm and Not right.
                "insights": result.get("insights", []),
                #: A digest (decision 70) cites one mark a line and is not
                #: followed by the sources again: the right column is them.
                "digest": bool(result.get("digest")),
                "offer": result.get("offer"),
            }
        return
    else:
        if prepared.get("preview"):
            #: The composed answer at once, while the model writes its own;
            #: the client draws it as a draft and the model's first token
            #: replaces it (`_assist`).
            yield prepared["preview"]
        messages = librarian.build_messages(
            f"{_in_full(req)}\n\n{req.image_context}" if req.image_context else _in_full(req),
            prepared.get("model_notes") or prepared["notes"],
            style=prepared["style"],
            profile=prepared["profile"],
            history=req.history,
            persona_prompt=req.persona_prompt,
            mode=req.mode,
            images=req.images,
            # The streaming path is the one people actually use, and it was
            # the one with no cap on how much of the notebook it sent. Same
            # budget the blocking `librarian.answer` now builds: measured
            # against the model this turn will really stream from, which is
            # the same `chat_model()` passed to `chat_stream` below.
            budget=librarian.plan_budget(
                req.model_manager.chat_model(),
                req.ollama,
                prepared["style"],
                prepared["profile"],
                req.persona_prompt,
                req.mode,
            ),
            # The Ask box's own brief on the streaming path too, this is
            # the one people actually use, so a fix only on the blocking
            # route above would be a fix nobody sees.
            ask_overview=req.body.notes_only,
        )
    # §88.4 item 4: the same per-stage token estimate agent.py's tool
    # path now attaches to its own stats event (chars/4, no tool
    # schemas on this path by definition, see build_messages' own
    # docstring above). Computed once, not per streamed chunk.
    composition_tokens = {
        "system": len(messages[0]["content"]) // context.CHARS_PER_TOKEN,
        "history": sum(len(m["content"]) for m in messages[1:-1]) // context.CHARS_PER_TOKEN,
        "notes": len(messages[-1]["content"]) // context.CHARS_PER_TOKEN,
        "tool_schemas": 0,
    }
    if prepared.get("brief"):
        #: The notes' tokens before and after the composer cut them, so the
        #: saving is a number on every turn rather than a claim.
        composition_tokens["notes_brief"] = prepared["brief"]
    streamed_any = False
    try:
        for piece in req.ollama.chat_stream(req.model_manager.chat_model(), messages, req.mode):
            if "thinking_delta" in piece:
                yield {"type": "thinking", "delta": piece["thinking_delta"]}
            elif "stats" in piece:
                # Token counts + timings for the message metadata line.
                yield {"type": "stats", **piece["stats"], "composition": composition_tokens}
            else:
                streamed_any = True
                yield {"type": "answer", "delta": piece["content_delta"]}
    except OllamaError as exc:
        # The model died mid-answer, tell the user, keep the results.
        # By construction this is reached only after the `elif not
        # ollama_running` branch above already passed, so this is never
        # "Ollama isn't running" (see librarian.model_error_message's
        # own docstring for why that distinction matters).
        #
        # Logged, not just shown in the answer: reported directly: this
        # failure reached the chat bubble but never the Settings → Logs
        # viewer, since nothing here ever routed it through `logging` at
        # all. The exception is already fully described in the message
        # this yields; logging it is what makes it show up in the one
        # place the caveat at the top of CLAUDE.md says to check first.
        logging.getLogger("tessellate.chat").warning(
            "chat: model call failed for %r: %s", req.model_manager.chat_model(), exc
        )
        preview = prepared.get("preview")
        if preview and preview.get("text") and not streamed_any:
            #: **The answer composed from the notes survives the model**
            #: (CHAT_PLAN Phase 6, the first tests: a model dying mid-answer
            #: used to leave only the error). The composed answer the page
            #: already drew as a draft is sent as the answer, under one line
            #: saying the model stopped.
            yield {"type": "answer", "delta": f"{preview['text']}\n\n{MODEL_STOPPED_NOTE}"}
            return
        prefix = "\n\n" if streamed_any else ""
        yield {
            "type": "answer",
            "delta": f"{prefix}{librarian.model_error_message(req.model_manager.chat_model(), exc)}",
        }


#: An act asked in the Ask box, which looks things up: said where to do it.
def _verdicts(session: Session):  # noqa: ANN202
    """The person's word on sentences (`ai/verdicts.py`), or None when it
    cannot be read: an answer is never lost to it."""
    try:
        return verdicts.known(session)
    except Exception:  # noqa: BLE001
        logging.getLogger("tessellate.chat").warning("chat: the verdicts could not be read", exc_info=True)
        return None


def _insight_memory(session: Session):  # noqa: ANN202
    """What the person said of insights, or None when it cannot be read: an
    answer is never lost to the learned store."""
    from tessellate.ai import insights

    try:
        return insights.memory(session)
    except Exception:  # noqa: BLE001
        logging.getLogger("tessellate.chat").warning("chat: the insight memory could not be read", exc_info=True)
        return None


def _act_events(req: _StreamRequest, prepared: dict) -> Iterator[dict]:
    """An act with no model (CHAT_PLAN decision 38), through the act registry
    (`ai/acts.py`, decision 53): the line that says what it does, then its
    card. A reminder, a new note, a pin run at once with Undo; a delete, a
    rename, a move or a tag wait for Confirm (`POST /chat/command/run`). An
    object that is not one note is asked about, never guessed. Ask is a
    client too: it names the act it read and says where it is done."""
    parsed = acts.parse(req.question, user_now(deps.get_config()))
    if req.body.notes_only:
        yield {"type": "answer", "delta": acts.ask_line(parsed)}
        return
    if parsed is None:
        yield {"type": "answer", "delta": acts.capability_line()}
        return
    if parsed["intent"] == "reminder" and not parsed.get("time_given"):
        #: Asked once, never guessed as tomorrow at 9 (decision 50); the
        #: reply's time fills it (`reading._follow_slot`).
        from tessellate.ai import commands

        yield {"type": "answer", "delta": commands.ask_when(parsed.get("said") or parsed["text"])}
        return
    planned = acts.preview(req.session, parsed, req.body.note_ids)
    card = planned.get("card")
    if card and planned.get("run"):
        done = acts.run(req.session, card["steps"], card.get("skipped"))
        if done["ok"] and parsed["intent"] == "reminder":
            #: Said as the card says it (INBOX 734): "Done: remind you on
            #: Friday at 9: call the dentist."
            done["summary"] = f"Done: {card['label'][:1].lower()}{card['label'][1:]}."
        yield {"type": "answer", "delta": done["summary"]}
        yield {**card, "done": True, "summary": done["summary"], "undo": done["undo"], "open": done.get("open")}
        return
    #: The steps come first and fold up as the answer starts, the order a
    #: model's run shows (owner, 2026-10-12: the steps sat under the result).
    if planned.get("tool") and not card:
        yield planned["tool"]
    yield {"type": "answer", "delta": planned["line"]}
    if card:
        yield card
    elif planned.get("navigate"):
        yield {"type": "navigate", "surface": planned["navigate"]}


def _may_digest(prepared: dict, question: str) -> bool:
    """The digest answers unless this is a "newest notes" turn, which keeps
    the composer's: but "all the dates in my notes" reads as newest-first
    and is a computed answer (`ai/composer_lists.py`)."""
    return not str(prepared.get("search_mode") or "").endswith("recent") or composer_lists.kind(question) is not None


def _forced_notes(req: _StreamRequest, follow: object) -> bool:
    """A turn that is about the notebook whatever its words read as: a reply
    to the agent's question, a follow-up, and, in Ask, "list my work notes"
    (an act in Chat, the question it is here: the listing is the answer,
    CHAT_PLAN Phase 6 P12)."""
    return bool(req.body.answering_agent or follow is not None or (req.body.notes_only and composer_lists.kind(req.question) is not None))


def _first_events(req: _StreamRequest, prepared: dict, ollama_running: bool, tools_only: bool) -> Iterator[dict]:
    """The turn's events before the agent is asked: an act, a starter the
    engine answers with no model, or the plain answer."""
    if prepared["intent"] == intent.ACT:
        return _act_events(req, prepared)
    starter = _starter_read(req, ollama_running or tools_only)
    if starter:
        return _starter_events(req, starter)
    return _plain_events(req, prepared, ollama_running)


def _starter_read(req: _StreamRequest, model_ready: bool) -> tuple[str, dict] | None:
    """A popup agent starter the engine answers when no model can (AGENT_SKILLS_REFORM
    "Deepened 2026-10-10" row 1); with a model the agent has it."""
    if model_ready or req.skill or req.body.notes_only:
        return None
    return starter_acts.read(req.question)


def _starter_events(req: _StreamRequest, starter: tuple[str, dict]) -> Iterator[dict]:
    """The starter's answer line, then its act card (`ai/starter_acts.py`)."""
    kind, slots = starter
    yield from starter_acts.events(
        req.session, kind, slots, user_now(deps.get_config()), req.body.note_ids, req.history,
        document_ids=req.body.document_ids, board_ids=req.body.board_ids,
    )


class CommandRunBody(BaseModel):
    """A confirmed act's steps, or an act's undo steps (decision 38)."""

    steps: list[dict] = Field(default_factory=list, max_length=60)
    skipped: list[dict] = Field(default_factory=list, max_length=60)


@router.post("/command/run")
def run_command(body: CommandRunBody, session: Session = Depends(get_session)) -> dict:
    """Run what an act's card showed, after Confirm, or take it back (Undo).
    Only the steps `commands.RUNNABLE` names run, each through the agent's
    own tool door, so permissions and the event log are the agent's."""
    from tessellate.ai import commands

    if not body.steps:
        raise HTTPException(status_code=400, detail="There is nothing to run.")
    if any(str(step.get("name") or "") not in commands.RUNNABLE for step in body.steps):
        raise HTTPException(status_code=404, detail="That names a step this app does not run from Chat.")
    done = acts.run(session, body.steps, body.skipped)
    return {"ok": done["ok"], "summary": done["summary"], "undo": done["undo"], "open": done.get("open")}


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
    else:
        agent_events = agent.run_agent(
            req.session,
            _in_full(req),
            prepared.get("model_notes") or prepared["notes"],
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


def _spoken_act(req: _StreamRequest) -> str | None:
    """A spoken follow-up that is an act ("and delete it", "same for
    Tuesday", "pin the other one"), resolved over the chat's last five turns
    (`reading.follow`, decision 59 step 3): the sentence it stands for, or
    None so a question's follow-up stays `composer.follow_on`'s."""
    from tessellate.ai import reading

    now = user_now(deps.get_config())
    turns = [{"text": str(t.get("question") or ""), "objects": t.get("objects") or []} for t in (req.history or [])[-reading.FOLLOW_TURNS:]]
    resolved = reading.follow(req.question, turns, now)
    if resolved is None or acts.parse(resolved[0], now) is None:
        return None
    return resolved[0]


def _lists_reminders(req: _StreamRequest) -> bool:
    """A reminder, task or due question ("what reminders do I have", "whats
    due this week"): answered from the reminders themselves with a model up
    too (decision 75, the model must not do worse than the composer). A
    1.5B model read the notes and said "two reminders" when there were
    three; a list is exact data, like a count, so it is never retold."""
    from tessellate.ai import act_registry, question_noise, reading

    if req.skill:
        return False
    asked = question_noise.repair(question_noise.tidy(req.question or ""))
    got = reading.read(asked, now=user_now(deps.get_config()))
    return got.tool == "list_reminders" and got.intent not in act_registry.ACTS


def _note_tool_read(req: _StreamRequest, prepared: dict, ollama_running: bool) -> None:
    """A read tool answered with no model (decision 59) is the whole
    notebook's, so the notes retrieval found are not its sources."""
    if prepared["stats"] is None and prepared["intent"] != intent.ACT and (not ollama_running or _lists_reminders(req)):
        prepared["tool_read"] = _tool_read_events(req)
        if prepared["tool_read"]:
            #: Not composed from them either: the Ask box's "Composed from
            #: your notes" label is for a quoted answer (INBOX 801).
            prepared["notes"] = []


def _follow_up(req: _StreamRequest):
    """The follow-up the turn before gives this one: a spoken act stands in
    for the question itself; a composed turn's "tell me more" is
    `composer.follow_on`'s; None otherwise."""
    spoken = _spoken_act(req) if req.history and not req.ollama.is_running() else None
    if spoken is not None:
        req.question = spoken
        return None
    if req.history and ((req.body.notes_only and req.body.answer_from == "notes") or not req.ollama.is_running()):
        return composer.follow_on(req.question, req.history)
    return None


def _searched_question(req: _StreamRequest, follow) -> str:
    """A correction ("no, the gym one") searches the question it corrects
    with the note it names (decision 35)."""
    if follow is None:
        return req.question
    return f"{follow.question} {follow.prefer}" if follow.prefer else follow.question


def _checks_grounding(prepared: dict, agentic: bool, composing: bool, conversational: bool) -> bool:
    """Whether the grounding check reads this answer: a model's prose, not a
    plan, a composed line or small talk. A counted answer (`notebook_stats`,
    a worked utility) is the engine's own sentence, streamed as written: its
    numbers are counts of rows, in no note, and "Heads up: I could not find
    96 in your notes" under "You have 96 notes" was the check misreading it
    (Brief 89)."""
    return not agentic and not composing and not conversational and prepared["stats"] is None


def _engine_answers(req: _StreamRequest, prepared: dict) -> bool:
    """Whether the app's own engine answers this turn with no model (INBOX
    801): a count, a worked utility, a read tool, an act, a starter, or notes
    the composer can quote. The Needle extra never shadows those: it picked
    search_notes with an empty query for "NOTEBOOK STATS" and "None of my
    tools fits that" for "5 + 5", which the engine answers exactly."""
    return (
        prepared["stats"] is not None
        or bool(prepared.get("tool_read"))
        or prepared["intent"] in (intent.UTILITY, intent.ACT)
        or bool(prepared["notes"])
        or _starter_read(req, False) is not None
    )


def _tools_provider(req: _StreamRequest, prepared: dict, ollama_running: bool):  # noqa: ANN202
    """Who answers a tool-using turn. INBOX 302 (the owner, 2026-09-24: needle
    "Yes, as an extra"): with no backend answering, a turn that may use tools
    can still run them through the needle extra when it is installed
    (`ai/tool_fallback.py` says why the order is what it is). Only the agent
    branch uses it: needle writes no prose, so a plain answer or a skill's
    written steps still need a model server, and `ollama_running` keeps
    saying the truth about that one. INBOX 801: and only for a turn the
    engine has no answer for (`_engine_answers`)."""
    if not ollama_running and req.use_tools and not req.skill and not _engine_answers(req, prepared):
        return tool_fallback.for_tools(req.ollama) or req.ollama
    return req.ollama


def _stream_lines(req: _StreamRequest) -> Iterator[str]:
    def event(payload: dict) -> str:
        return json.dumps(payload) + "\n"

    # Flush a first byte immediately. The semantic search below can be a
    # slow cold start (loading the embedding model, warming the index);
    # emitting this now means the browser's stream opens right away and
    # its "typing…" indicator keeps animating instead of looking frozen
    # while the whole request blocks (user-reported lag).
    yield event({"type": "status", "stage": "searching"})
    #: B30: the seconds each stage landed at, for "Why this answer".
    started = time.perf_counter()
    marks: dict[str, float] = {}

    # Retrieval happens INSIDE the stream now, not before it, that's the
    # whole latency win. Nothing before this line touches the model.
    #: **A follow-up read against the turn before** (INBOX 725): "tell me
    #: more" or "the second one" means nothing searched on its own. Only for a
    #: turn the composer answers (Ask's From your notes, or any turn with no
    #: model), and only with a turn before it: a model reads the history
    #: itself, and the routing below (`_composed`) is unchanged by it.
    follow = _follow_up(req)
    prepared = _prepare(
        req.session,
        _searched_question(req, follow),
        req.body.note_ids,
        force_notes_intent=_forced_notes(req, follow),
        attached_notes_only=req.body.attached_notes_only,
        document_ids=req.body.document_ids,
        file_ids=req.body.file_ids,
        board_ids=req.body.board_ids,
        # Asking vs requesting, decided from what the caller can already
        # do rather than from a new flag: `notes_only` is the Notes tab's
        # Ask box, and tools-off is the Chat tab's Ask mode. Anything that
        # can reach for a tool, Request mode, the palette, a skill or plan
        # run: is a request. `use_tools` is resolved above, so the saved
        # preference is accounted for and an unset flag cannot land a
        # Request turn in the chip row.
        surface=ASK_SURFACE if (req.body.notes_only or not req.use_tools) else AGENT_SURFACE,
        as_of=None if req.skill else req.body.as_of,
    )
    prepared["follow_on"] = follow
    marks["read"] = marks["searched"] = time.perf_counter() - started
    ollama_running = req.ollama.is_running()
    if prepared["intent"] == intent.ACT and ollama_running and req.use_tools and not req.body.notes_only:
        #: With a model in Agent mode, an act is the agent's: its tools are the
        #: same, and it can ask and plan (decision 38 is for no model).
        prepared["intent"] = intent.NOTES
    composed = _composed(req, ollama_running)
    _note_tool_read(req, prepared, ollama_running)
    tools_provider = _tools_provider(req, prepared, ollama_running)
    tools_only = tools_provider is not req.ollama
    # In agent mode the model can act even when nothing matched, "save a
    # note about X" must work on an empty notebook.
    #: A turn with no model, no tool fallback and notes to quote is composed
    #: in `_plain_events` whatever surface asked (INBOX 725): labelled so,
    #: and its quotes are never trimmed or re-grounded.
    composing = composed or (
        not ollama_running
        and not tools_only
        and prepared["stats"] is None
        and intent.needs_retrieval(prepared["intent"])
        and bool(prepared["notes"])
    )
    conversational = not intent.needs_retrieval(prepared["intent"])
    model_can_answer = ollama_running if conversational else (ollama_running or tools_only)
    will_answer = not composed and not prepared.get("tool_read") and not (_asks_capability(req, prepared) and _app_answers(req, ollama_running)) and prepared["intent"] not in (intent.UTILITY, intent.ACT) and model_can_answer and (
        bool(prepared["notes"])
        or bool(req.images_raw)
        or req.use_tools
        or conversational
    )
    if will_answer and not tools_only:
        _assist(req, prepared)
    if will_answer:
        #: B31, B32: the model reads the notes with the person's verdicts
        #: written in, as context; grounding reads them as they are.
        known = _verdicts(req.session)
        if known:
            prepared["model_notes"] = verdicts.for_model(prepared.get("model_notes") or prepared["notes"], known)

    yield event(
        {
            "type": "meta",
            "raw_results": [] if prepared.get("tool_read") else [r.model_dump(mode="json") for r in prepared["raw_results"]],
            "picture_alts": prepared.get("picture_alts") or {},
            "picture_sizes": prepared.get("picture_sizes") or {},
            "search_mode": prepared["search_mode"],
            "connected_ids": prepared["connected_ids"],
            "match_info": prepared["match_info"],
            "when_phrase": prepared["when_phrase"],
            "as_of": prepared.get("as_of"),
            "as_of_revisions": prepared.get("as_of_revisions") or {},
            "answered_by": (
                "needle (tools only)"
                if tools_only and will_answer
                else req.model_manager.served_chat_model(req.ollama) if will_answer else None
            ),
            "ollama_running": ollama_running,
            #: The Ask box labels the answer "Composed from your notes, no AI".
            "composed": composing,
        }
    )

    events = _first_events(req, prepared, ollama_running, tools_only)
    agentic = False
    # Small talk never goes near the agent: "hey" is not a request to do
    # anything, and handing it a toolbox invites it to invent an errand.
    if not composed and not prepared.get("tool_read") and (ollama_running or tools_only) and req.use_tools and intent.needs_retrieval(prepared["intent"]):
        agent_events = _agent_events(req, prepared, tools_provider)
        first = _first_agent_event(req, agent_events)
        if first is None or first.get("type") == "unsupported":
            # The active model can't do tool calls, plain Q&A, never
            # a hard dependency. INBOX 272 part 1: this used to be a silent
            # `pass`, so Agent mode was asked for and downgraded with
            # nothing on screen to say so or how to fix it. `first` (built
            # in ai/agent.py) already carries the remedy; forward it before
            # falling through to the plain-answer stream below.
            if first is not None:
                yield event(first)
        else:
            events = chain([first], agent_events)
            agentic = True
    # ROADMAP.md item 36's frontend half: the non-streaming /chat already
    # grounds its answer, but the live Ask box only ever calls this
    # streaming route. Accumulated here (not computed per-delta: the
    # sentence splitter needs the whole answer, and this is a handful of
    # deltas' worth of string concatenation, not a hot loop) and sent as
    # its own event once the answer is fully in, direct-Q&A only.
    answer_text = ""
    # Every note a tool read during the turn is a grounding candidate,
    # not only the retrieval set. Reported: an agent answer that named
    # three notes cited one, and a skill run cited none. The retrieval
    # set is what the *search* found before the model started; in
    # Agent mode and in a skill run the model then reads notes of its
    # own choosing through `get_note`, `search_notes`, `related_notes`,
    # and those are exactly the notes its answer is about. `touched` on
    # each tool event already names them (it is what the transcript's
    # action line opens), so this collects ids and loads the text once,
    # after the answer is in.
    touched_note_ids: list[int] = []
    # **A blank line wherever the transcript starts a new paragraph.**
    #
    # Measured while fixing INBOX 40. A multi-round turn (an agent answer,
    # every skill run) emits its prose in bursts with a step or a tool
    # call between them, and the client draws each burst as its own block
    # (`agentTimeline.startAnswer`, and `timeline.text()` joins them with
    # a blank line). Concatenating the raw deltas here instead glued the
    # last sentence of one round to the first of the next: "…in it.I
    # checked…". `split_sentences` splits on `.` followed by whitespace,
    # so that pair is one unsplittable "sentence" that exists in no
    # paragraph on screen: the grounding row it produces can never be
    # found by the client's citation walker, and both real sentences lose
    # their marker. On a nine-step run the whole answer collapsed into a
    # single such sentence and the run cited nothing at all, which is
    # exactly what was reported.
    #
    # The set below is the events that begin a new prose block in the
    # transcript, so this string keeps the same shape as what the reader
    # sees. Anything else (`meta`, `token`, `stats`) is bookkeeping and
    # must not break a paragraph in half.
    paragraph_breaks = {"thinking", "tool", "step", "plan", "result"}
    in_prose = False
    conversational = not intent.needs_retrieval(prepared["intent"])
    #: **Grounding as the answer streams** (INBOX 320). The Ask tab numbers
    #: its Matching records from the answer's citations, and those used to
    #: arrive in one event after the last token, so the column sat unnumbered
    #: for the whole answer. Each completed sentence is grounded as it lands
    #: and the rows so far go out as `grounding_live`, which the client treats
    #: as provisional: the `grounding` event below is still computed over the
    #: whole, trimmed answer and is what the saved turn and the support line
    #: read. Plain answers only: an agent turn's candidates grow with every
    #: note a tool reads, so a live row there could name a set the final pass
    #: would not.
    live_grounder = (
        SentenceGrounder(
            prepared["notes"], meaning=search_chunks.meaning_scorer(req.session, deps.get_embeddings())
        )
        if not agentic and not conversational and not composing and prepared["notes"]
        else None
    )
    #: The fence markers a small model echoes back are taken out of the
    #: answer before anything reads or saves it (`fence.AnswerScrubber`).
    scrubber = fence.AnswerScrubber()
    #: Rows an answer brought with it, exact by construction (the composed
    #: and the extractive answers): kept, saved, and never re-grounded.
    exact_grounding: list[dict] | None = None
    shape: str | None = None
    try:
        for payload in events:
            kind = payload.get("type")
            live_rows: list[dict] = []
            if kind == "grounding" and payload.get("exact"):
                exact_grounding = payload.get("sentences") or []
            if kind == "grounding":
                shape = (payload.get("support") or {}).get("shape") or shape
            if kind == "answer" and "answered" not in marks:
                marks["answered"] = time.perf_counter() - started
            if kind == "answer":
                payload = {**payload, "delta": scrubber.feed(payload.get("delta") or "")}
                if not payload["delta"]:
                    continue
            else:
                held = scrubber.flush()
                if held:
                    answer_text += held
                    yield event({"type": "answer", "delta": held})
            if kind == "answer":
                if answer_text and not in_prose:
                    answer_text += "\n\n"
                delta = payload.get("delta") or ""
                answer_text += delta
                in_prose = True
                #: Only when this delta could have ended a sentence: a split of
                #: the whole answer per token is wasted work on every other one.
                if live_grounder is not None and any(ch in delta for ch in ".!?\n"):
                    live_rows = live_grounder.feed(answer_text)
            elif kind in paragraph_breaks:
                in_prose = False
                if kind == "tool":
                    for item in payload.get("touched") or []:
                        if item.get("kind") == "note" and isinstance(item.get("id"), int):
                            touched_note_ids.append(item["id"])
            yield event(payload)
            if live_rows:
                yield event({"type": "grounding_live", "sentences": list(live_grounder.rows)})
        held = scrubber.flush()
        if held:
            answer_text += held
            yield event({"type": "answer", "delta": held})
    except Exception as exc:  # noqa: BLE001  # same outer boundary as above,
        # for a failure that shows up partway through rather than before
        # the first event (a later skill step, say). Same fix: say what
        # happened instead of the stream just stopping.
        logging.getLogger("tessellate.chat").exception(
            "%s: unhandled error mid-stream: %s",
            "skill run" if req.skill else "agent turn",
            exc,
        )
        # CodeQL: "information exposure through an exception" (#296): 
        # `exc`'s own str() is untrusted and can embed a file path or
        # connection detail; same sanitiser librarian.model_error_message
        # already trusts for this exact shape.
        yield event({"type": "answer", "delta": f"\n\nSomething went wrong: {safe_value(exc)}"})
    #: **The greeting and the sign-off come off before anything else reads it**
    #: (the owner, 2026-09-21). Here, not in the browser: grounding marks
    #: sentences by their offsets in this string, the saved turn stores it, and
    #: an export reads it back, so trimming anywhere else would leave three
    #: copies of the answer disagreeing about where sentence two starts.
    #: Not a composed answer: its opening line is a fixed phrase, and its
    #: quotes are the person's words, which no trim may touch.
    trimmed_answer = answer_text if composing else trim_assistant_padding(answer_text)
    if trimmed_answer != answer_text:
        answer_text = trimmed_answer
        #: The browser has already drawn the untrimmed text, so it is sent the
        #: finished answer to replace it with. One event at the end rather than
        #: a filter on every delta: a stream that edits what it already said,
        #: token by token, flickers.
        yield event({"type": "answer_final", "text": answer_text})
    #: **The model proposes, the engine decides** (CHAT_PLAN decision 53): a
    #: model's plain answer passes the same validators as the engine's, so a
    #: number or name in none of the notes it was given, nor the question, is
    #: said under it. The agent path checks its own (`agent.py`, H2).
    model_checks = None
    #: A model that stopped leaves the composed answer under MODEL_STOPPED_NOTE:
    #: the engine's words, quoted from the notes, not the model's.
    by_model = MODEL_STOPPED_NOTE not in answer_text
    if _checks_grounding(prepared, agentic, composing, conversational) and exact_grounding is None and by_model and answer_text:
        model_checks = validate.check_model_answer(
            answer_text,
            [
                req.question,
                str(req.image_context or ""),
                #: The date the prompt told the model, so "today is 10 October" is backed.
                user_now(deps.get_config()).strftime("%A %d %B %Y %H:%M"),
                *(str(n.get("content") or "") for n in [*prepared["notes"], *(prepared.get("model_notes") or [])]),
            ],
        )
        if model_checks["unbacked"]:
            heads = source_check.heads_up(model_checks["unbacked"])
            answer_text += heads
            yield event({"type": "answer", "delta": heads})
    candidates = _grounding_candidates(req.session, prepared["notes"], touched_note_ids)
    #: Kept past the branch below so the saved turn carries the same rows the
    #: client was just sent (INBOX 241). A conversational turn, or one nothing
    #: could be grounded against, saves an empty list, which is the truth about
    #: that answer rather than a gap.
    grounding: list[dict] = list(exact_grounding or [])
    if exact_grounding is None and not conversational and candidates and answer_text:
        grounding = (
            ground_answer_sentences(
                answer_text, candidates, numbered=len(prepared["notes"]),
                meaning=search_chunks.meaning_scorer(req.session, deps.get_embeddings()),
            )
            or []
        )
        if grounding:
            # A touched note is not in `raw_results`, so the client has
            # no text to name it by; the label rides on each entry.
            labels = {
                note["id"]: " ".join(str(note.get("content") or "").split())[:60]
                for note in candidates
            }
            for row in grounding:
                row["label"] = labels.get(row["note_id"], "")
            #: **How much of the answer the notebook actually backs, beside
            #: which sentences it backs.** CHAT_PLAN Phase 1's fourth gate
            #: line: the marks have always said which sentences are
            #: supported, and nothing said how many of them there were, so an
            #: answer with one cited sentence in six read at a glance exactly
            #: like one with six in six. The threshold travels with the
            #: numbers (`grounding.support`) rather than being picked again
            #: in the frontend.
            yield event({
                "type": "grounding",
                "sentences": grounding,
                "support": grounding_support(answer_text, grounding),
                **({"checks": model_checks["findings"]} if model_checks else {}),
            })
    if req.body.notes_only and answer_text:
        _save_ask_turn(req.session, _in_full(req), answer_text, prepared, grounding)
    if answer_text:
        marks["done"] = time.perf_counter() - started
        yield event({"type": "why", "lines": _why(req, prepared, grounding, composing, will_answer, tools_only, ollama_running, shape, marks)})
    yield event({"type": "done"})



def _why(req, prepared, grounding, composing, will_answer, tools_only, ollama_running, shape, marks) -> list[dict]:
    """B30's lines for this turn (`ai/why.py`)."""
    return why.lines(
        intent=prepared["intent"],
        mode=prepared.get("search_mode"),
        matched=len(prepared.get("raw_results") or []),
        used=len({row.get("note_id") for row in grounding if isinstance(row.get("note_id"), int)}),
        when=prepared.get("when_phrase"),
        scoped=bool(req.body.attached_notes_only or req.body.note_ids),
        composed=composing,
        model=("Atlas's tools" if tools_only else req.model_manager.served_chat_model(req.ollama)) if will_answer else None,
        shape=shape,
        context=will_answer and ollama_running and _asks_capability(req, prepared),
        loading=bool(prepared.get("meaning_loading")),
        marks=marks,
    )


def _asked(body: ChatRequest, session: Session, skill: dict | None) -> tuple:
    """The question the app reads, the name it was addressed by, and the whole
    of a question the app only read the start of (else None).

    Cleaned before anything reads it (INBOX 801): a stray backslash, a run of
    spaces, a sentence typed in capitals (`question_noise.tidy`). Everything
    that routes, searches or plans reads its first `composer.PLAN_CHARS`
    characters (those passes cost words x length: 38 s for a 20,000-character
    paste); the model is given all of it (`_in_full`)."""
    head, tail = body.question[: composer.PLAN_CHARS], body.question[composer.PLAN_CHARS :]
    question, address = _address(skill["question"] if skill else question_noise.tidy(head) or head, session, skill)
    return question, address, (None if skill or not tail else question + tail)


def _address(question: str, session: Session, skill: dict | None) -> tuple:
    """The question and a name in address position (a `vocative.Address`,
    or None), taken off before anything reads the question, so "brotato
    what's on today" searches for today, not for brotato, and "yo
    brotatockiibidyrizzler" is a call, never a search. A skill's question
    is its own."""
    #: Keys pressed at random are not a nickname for the assistant.
    address = None if skill or intent.is_mash(question) or intent.is_test(question) else vocative.split(question, in_notes=_in_notes(session))
    if address is None or not address.names:
        return question, None
    #: A slipped word at the end of a command is the command's, not a name:
    #: "pin the dentist noe" lost "noe" as a nickname and pinned nothing (O3).
    now = user_now(deps.get_config())
    if acts.parse(question, now) is not None and acts.parse(address.question, now) is None:
        return question, None
    return address.question, address


@router.post("/stream")
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
    _apply_scope(session, body)
    _apply_open(session, body)
    ollama = deps.get_ollama()
    #: This surface's own model, if one is set (model_manager.FEATURES).
    #: A view over the same manager, so everything downstream, the agent
    #: loop included, goes on asking for `chat_model()` and gets this
    #: surface's answer without knowing features exist.
    model_manager = deps.get_model_manager().for_feature(_feature_for(body))
    history = [turn.model_dump(exclude_none=True) for turn in body.history]
    persona_prompt = _resolve_persona(body.persona, session)
    mode = _resolve_mode(body.mode)
    images_raw = _resolve_chat_images(session, body.image_media_ids)
    chat_sees_images = bool(images_raw) and _chat_model_sees_images(model_manager, ollama)
    images = [uri for _, uri in images_raw] if chat_sees_images else []
    image_context = (
        "" if chat_sees_images else _image_caption_context(images_raw, model_manager, ollama)
    )
    use_tools = (
        body.use_tools
        if body.use_tools is not None
        else bool(deps.get_config().get_preference("tools_enabled", True))
    )
    # A skill run replaces the question with the skill's own instruction: 
    # steps, values and declared tools included, and narrows the toolbox to
    # what it declared. Retrieval runs on that instruction too, so a skill
    # gets the notes its own words find rather than the ones the chip's label
    # happens to match.
    # A plan run goes down exactly the same path as a skill run, the runner
    # cannot tell them apart, which is what gives a plan the ticked steps, the
    # change list and the Undo on each without a second implementation.
    skill = _resolve_skill(body) or _resolve_plan(body)
    if body.as_of is not None and not skill:
        use_tools = False
    question, address, full_question = _asked(body, session, skill)
    allowed_tools = skill["tools"] if skill else None
    if skill and skill["acts"]:
        # An action skill without tools is just a paragraph, so the route
        # insists whatever the caller asked for. The frontend now switches the
        # mode itself before it sends (INBOX 39: it announces the switch and
        # leaves it switched), so in the app this branch no longer changes
        # anything; it stays because the API is public and a caller that posts
        # `use_tools: false` with an action skill still means the skill.
        use_tools = True

    req = _StreamRequest(
        body=body,
        session=session,
        ollama=ollama,
        model_manager=model_manager,
        history=history,
        persona_prompt=persona_prompt,
        mode=mode,
        images_raw=images_raw,
        images=images,
        image_context=image_context,
        use_tools=use_tools,
        skill=skill,
        question=question,
        allowed_tools=allowed_tools,
        address=address,
        full_question=full_question,
    )

    # X-Accel-Buffering: no tells reverse proxies (nginx) not to buffer the
    # stream, so tokens reach the browser as they're produced.
    return StreamingResponse(
        _answer_lines(req),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


def _stoppable(spend, req):  # noqa: ANN001, ANN202
    """The run's budget, wired to this turn's Stop."""
    spend.stop_event = req.stop
    return spend


def _interactive_lines(req):  # noqa: ANN001, ANN202
    """`_stream_lines`, marked as an interactive model call while it runs, so
    background model work waits between its calls (`core/model_gate.py`,
    ARCH-09). Entered on the first line, left when the stream ends or the
    client goes: a generator closed early still runs its `finally`."""
    #: Listed in Activity while it streams, and Stop there ends it (rule 5).
    label = "Running a skill" if req.skill else "Answering in Chat"
    with model_gate.interactive():
        yield from activity.tracked_stream(
            "generation", label, _lines_for(req), title=_run_title(req), stop_event=req.stop
        )


def _lines_for(req):  # noqa: ANN001, ANN202
    """A skill with no model is the composer's (O7, `_skill_lines`); every
    other turn is `_stream_lines`."""
    return _skill_lines(req) if req.skill and not req.ollama.is_running() else _stream_lines(req)


def _run_title(req) -> str:  # noqa: ANN001
    """The process ledger's words for this turn (INBOX 805): what was asked,
    in the asker's words, cut to a line. A trailing backslash or quote a
    paste left on the question is not part of it."""
    asked = " ".join(str(getattr(req.body, "question", "") or "").split()).strip("\\'\" ")
    if len(asked) > 60:
        asked = asked[:59] + "…"
    if req.skill:
        name = str(req.skill.get("name") or req.skill.get("title") or "a skill")
        return f"Running {name}" + (f": '{asked}'" if asked else "")
    agent = req.use_tools and not getattr(req.body, "notes_only", False)
    return f"{'Agent: ' if agent else 'Answering '}'{asked}'"


def _answer_lines(req: _StreamRequest) -> Iterator[str]:
    """The turn's stream: a slash command's exact lines, else the full turn."""
    commanded = _guarded_slash_lines(req)
    return iter(commanded) if commanded is not None else _interactive_lines(req)


def _guarded_slash_lines(req: _StreamRequest) -> list[str] | None:
    """`_slash_lines`, but a command that raises is no 500: the turn carries
    on as an ordinary one. The log names the failure's class through
    `safe_value`, never the exception's text or the question, which can quote
    the person's notes."""
    try:
        return _slash_lines(req)
    except Exception as exc:  # noqa: BLE001  # an unforeseen command failure is an ordinary turn
        logging.getLogger("tessellate.chat").warning(
            "chat: slash command failed (%s); answering as an ordinary turn", safe_value(type(exc).__name__, 60),
        )
        return None


def _slash_lines(req: _StreamRequest) -> list[str] | None:
    """**A slash command answers exactly, before any search** (O6,
    `ai/slash.py`): the stream's lines for a typed `/command`, or for an
    ordinary sentence that asks for one when no model answers ("which notes
    have no tags"); None otherwise, and for a skill's run."""
    from tessellate.ai import slash

    if req.skill:
        return None
    typed_only = req.ollama.is_running() and not _composed(req, True)
    said = slash.answer(req.session, req.body.question or "", user_now(deps.get_config()).replace(tzinfo=None), typed_only=typed_only)
    if said is None:
        return None
    return _composed_lines(req, [{"type": "answer", "delta": said}])


def _composed_lines(req: _StreamRequest, events: list[dict]) -> list[str]:
    """A turn the app answers itself, whole: the status, a meta line marking it
    composed (the Ask box labels it "Composed from your notes, no AI"), the
    events, done."""
    meta = {"type": "meta", "raw_results": [], "picture_alts": {}, "picture_sizes": {}, "search_mode": "command",
            "connected_ids": [], "match_info": {}, "when_phrase": None, "as_of": None, "as_of_revisions": {},
            "answered_by": None, "ollama_running": req.ollama.is_running(), "composed": True}
    return [json.dumps(e) + "\n" for e in ({"type": "status", "stage": "searching"}, meta, *events, {"type": "done"})]


def _skill_lines(req: _StreamRequest) -> Iterator[str]:
    """**A skill with no model running** (O7, `ai/skill_composer.py`): the
    composer runs the ones whose job is a reading of the notebook, and the
    rest say they need a model, instead of a model-less runner answering the
    skill's instruction as if it were a question about the notes."""
    from tessellate.ai import skill_composer

    skill = req.skill["skill"]
    run = skill_composer.plan(skill, req.body.skill_inputs)
    if run is None:
        yield from _composed_lines(req, [{"type": "answer", "delta": skill_composer.needs_a_model(skill)}])
    elif run[0] == "ask":
        asked = req.body.model_copy(update={"question": run[1], "skill": None, "skill_inputs": None})
        yield from _stream_lines(with_changes(req, body=asked, skill=None, question=run[1], use_tools=False, allowed_tools=None))
    elif run[0] == "starter":
        now = user_now(deps.get_config())
        said = starter_acts.events(req.session, run[1], {}, now, req.body.note_ids, req.history, document_ids=req.body.document_ids, board_ids=req.body.board_ids)
        yield from _composed_lines(req, said)
    else:
        yield from _composed_lines(req, [{"type": "answer", "delta": skill_composer.REPORTS[run[1]](req.session)}])


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
    """The agent-tool catalog for Settings → Tools toggles."""
    return tools.tool_catalog()


# --- compressing a long conversation (§35I) -----------------------------------
#
# Asked for directly: *"there should be a tool as well as a manual command or
# something to be able to compress chat context on longer chats so the AI can
# better continue."*
#
# What happens today without it is worth stating plainly, because it is not
# "the request gets big", the client sends at most the last four turns and
# `context.fit_history` drops whole pairs from the *oldest* end until the rest
# fits. So a long conversation does not overflow; it silently forgets its own
# beginning, and the model starts re-asking things it was told an hour ago.
#
# A summary is strictly better than a drop: the same few hundred characters
# carry the gist of ten turns instead of the whole of one. And it is the
# **manual** half that shipped first, exactly as §35I argued, a button the
# user presses, whose output they can read before it is used, cannot misfire.
#
# §37I: the tool that lets the agent do it unprompted (`compress_chat` in
# ai/tools.py) shares this endpoint's summarising logic via
# `tools.summarise_turns`, and keeps the same human-review step, the model's
# turn ends and `showCompressReview` renders exactly the panel this endpoint
# already feeds, so a summary the agent asked for is never applied unread any
# more than one this button produced would be.

#: Turns to summarise in one call. Beyond this the summary itself gets long
#: enough to be worth summarising, which is the wrong direction. Re-exported
#: from ai/tools.py, the one place the ceiling is defined, so this route and
#: the agent's own compress_chat tool can't drift to different limits.
MAX_COMPRESS_TURNS = tools.MAX_COMPRESS_TURNS


class CompressBody(BaseModel):
    """The turns to summarise, oldest first."""

    history: list[ChatTurn] = Field(min_length=1, max_length=MAX_COMPRESS_TURNS)


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


class ToolExecuteBody(BaseModel):
    """A tool call the user approved in the UI (confirm step)."""

    name: str
    arguments: dict = Field(default_factory=dict)
    #: A `{"tool": "batch", "steps": [...]}` undo (a change to several notes or
    #: board items): each step is `{"tool", "arguments"}` of a registry tool.
    #: Posted as name "batch" it used to answer 404, so such a change had an
    #: Undo button that could never undo.
    steps: list[dict] = Field(default_factory=list)


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
        # Last change first, the way a stack of edits is taken back. Each
        # step's own result is not sent back: the button only needs to know it
        # worked, and a tool's result can carry text written for the model.
        for name, arguments in reversed(calls):
            _refuse_failed(name, tools.execute_tool(session, name, arguments))
        return {"label": f"Undid {len(calls)} changes."}
    if body.name not in tools.TOOLS:
        raise HTTPException(status_code=404, detail=f"There is no tool called '{body.name}'.")
    result = tools.execute_tool(session, body.name, body.arguments)
    if "error" in result:
        _refuse_failed(body.name, result)
    #: Named fields only, never the whole result: a tool's result can carry
    #: text written for the model, and CodeQL (#552, #553) follows any
    #: whole-result return to the exception text. The Confirm card reads
    #: `label`; `undo` lets a confirmed change be taken back.
    return {"label": str(result.get("label") or ""), "undo": result.get("undo")}


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
