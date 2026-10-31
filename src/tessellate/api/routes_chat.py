"""Ask a question, get back BOTH a conversational answer and the raw
matching entries: the two-result design from the original idea doc.

Two flavours:
- POST /chat: one blocking JSON response (simple, used by tests/API)
- POST /chat/stream: NDJSON: metadata + raw results first, then the
  model's thinking and answer as live token deltas (what the UI uses)

Plain `def` so the blocking LLM call runs in FastAPI's threadpool.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import mimetypes
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Iterator
from dataclasses import dataclass, field
from dataclasses import replace as with_changes
from datetime import date, datetime, timezone
from itertools import chain
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import or_, select
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from tessellate.api import bounds
from tessellate.ai import budget as run_budget, capability, fact_check, filed_name, composer, composer_social, composer_unplaced, note_language, composer_plan, composer_aware, composer_compose, composer_digest, composer_frame, composer_open, composer_suggest, composer_tone, composer_web, composer_lists, composer_money, composer_slots, composer_sum, composer_versus, find_it, glossary, list_pool, neighbours, note_rank, note_recency, personal, phrasing, realise, verdicts, toolwords, vocative, why
from tessellate.ai import recognise
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
from tessellate.api import chat_extra
from tessellate.api.schemas import EntryOut
from tessellate.core import activity, background, deps, docview, model_gate, private_turn
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
    EntryLink,
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
from tessellate.search import engine
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


#: A note link in an answer: `[Dentist](#/notes/13)`.
_NOTE_LINK = re.compile(r"\[([^\]\n]{1,200})\]\(#/notes/\d+\)")


def _linked_labels(answer: str) -> list[str]:
    """The notes an answer linked, as `_turn_label` names them, in order: a
    date list cites no sources, but its links say what it was about (audit
    1030 Z53, "what time" after "what is on 4 November")."""
    labels: list[str] = []
    for text in _NOTE_LINK.findall(answer or ""):
        label = re.split(r"[:.!?]", re.sub(r"[*_`]|…$", "", text).strip())[0].strip()[:80]
        if label and label not in labels:
            labels.append(label)
    return labels[:5]


class ChatTurn(BaseModel):
    question: str = Field(max_length=bounds.TURN_TEXT_MAX)
    answer: str = Field(max_length=bounds.TURN_TEXT_MAX)
    #: The notes the answer named, by title, for a spoken follow-up such as
    #: "delete the other one" (`reading.follow`, decision 57). Optional, and
    #: dropped from the dump when absent, so a turn without it is unchanged.
    objects: list[Annotated[str, Field(max_length=200)]] | None = Field(default=None, max_length=8)

    @model_validator(mode="after")
    def _objects_from_links(self):  # noqa: ANN202
        #: The client names them from the answer's sources; an answer with
        #: none (a date list) is named by the links it wrote.
        if not self.objects:
            self.objects = _linked_labels(self.answer) or None
        return self


class PlanRun(BaseModel):
    """A plan the model made for one request, sent back to be worked through.

    Bounded here as well as in `tools.validate_make_plan`, because this arrives
    over HTTP: the client is echoing back what the server just produced, but
    nothing makes that true of a hand-made request, and the run it starts
    writes to the notebook.
    """

    goal: str = Field(min_length=1, max_length=skills.MAX_GOAL)
    steps: list[str] = Field(min_length=1, max_length=skills.MAX_STEPS)


class ScreenBody(BaseModel):
    """What the person is looking at and just did, sent small and local with an
    Ask, Chat or Guide request (`ai/composer_aware.py`). Ids, not names: the
    server names a note or document only when it is a plain one."""

    tab: str | None = Field(default=None, max_length=40)
    open_doc_id: int | None = None
    actions: list[str] = Field(default_factory=list, max_length=10)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=20000)
    #: What was typed, when `question` (the copy every reader scans) had a run
    #: of blanks squeezed out of it: the model and the saved turn read this, so
    #: pasted code keeps its indent. Never taken from the client. Capped like
    #: `question`: squeezing blanks out must not be a way past the cap.
    raw_question: str | None = Field(default=None, exclude=True, max_length=20000)

    @model_validator(mode="before")
    @classmethod
    def _squeezed(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        data = {k: v for k, v in data.items() if k != "raw_question"}
        typed = data.get("question")
        if isinstance(typed, str) and bounds.squeeze_blanks(typed) != typed:
            data = {**data, "question": bounds.squeeze_blanks(typed), "raw_question": typed}
        return data

    #: Answer from the notebook as it stood at the end of this day
    #: (WORLD_CLASS_PLAN I5, row 23). Read, never act: the turn runs without
    #: tools, which would read and change the notebook as it is now.
    as_of: date | None = None
    #: The browser's locale (`navigator.language`), so a bare "3/4" in a
    #: question reads in the asker's date order.
    locale: str | None = Field(default=None, max_length=35)
    # Prior turns for follow-up context (Round 1); the server clips this.
    history: list[ChatTurn] = Field(default_factory=list, max_length=bounds.HISTORY_MAX_TURNS)
    # Persona name; None → the active persona preference.
    persona: str | None = Field(default=None, max_length=bounds.LABEL_MAX)
    # Agent mode: may the model call tools to change things?
    # None → the saved "tools_enabled" preference (default on).
    use_tools: bool | None = None
    # How much effort this turn is worth (§11): "quick", "normal" or
    # "detailed". None → the saved "response_mode" preference. Carries the
    # reply cap, the temperature, the thinking toggle and a length hint, so
    # one picker moves all four together rather than four settings that have
    # to be kept consistent by hand.
    mode: str | None = Field(default=None, max_length=bounds.LABEL_MAX)
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
    skill_inputs: dict[str, Annotated[str, Field(max_length=bounds.TURN_TEXT_MAX)]] | None = Field(
        default=None, max_length=40
    )
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
    #: A side fetch of the other answer to the question just asked (K26: the
    #: Ask box's "From your notes" under an AI answer): read-only, so it is
    #: not saved as a second turn in Ask history, and always the composed one.
    peek: bool = False
    #: "Try again" on the same question (CHAT_PLAN decision 34): the how-many-
    #: th retry, so an answer composed from the notes is worded anew rather
    #: than repeated word for word. 0 for a first ask.
    attempt: int = Field(default=0, ge=0, le=10_000)
    #: **A private chat** (INBOX 1481): the turn answers from the notes and
    #: leaves nothing behind. No `queried` row (so no Ask again chip), no
    #: note's use count, no Ask history row, no learned thing read (what the
    #: AI remembers, the person's word on insights and sentences) and none
    #: written (the AI cannot save a preference), and the process ledger
    #: names the run without the question. The page sends it for every turn
    #: of a chat that is private and keeps the turns in memory only.
    private: bool = False
    #: The screen and the last few actions (composer awareness, 2026-10-25).
    screen: ScreenBody | None = None


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


def _first_more_is_this(body: ChatRequest) -> None:
    """"Tell me more" as the first thing said with a note open is about that
    note (audit 1030 Z54), read as "summarise this"."""
    if body.open_note_id and not body.history and composer_digest.more_of_this(body.question):
        body.question, body.raw_question = "summarise this", None


def _attached_only(body: ChatRequest) -> None:
    """"What is this about" with a note attached is that note alone, never a
    list of the newest (INBOX 1461)."""
    if not body.scope and composer_digest.about_this(body.question):
        body.attached_notes_only = True


def _apply_open(session: Session, body: ChatRequest) -> None:
    """"Summarise this" on any tab (CHAT_PLAN B10): the open note, else the
    open category, becomes the closed set the answer reads; "summarise
    Travel" reads that category's notes rather than the few a keyword
    search finds. Notes attached by hand, or a scope, win over both."""
    if body.note_ids or body.document_ids or body.scope:
        _attached_only(body)
        return
    _first_more_is_this(body)
    if composer_digest.about_this(body.question):
        #: A note binned or made private since it was opened is not read;
        #: the open category stands in (`_attached_notes`' own rule).
        if body.open_note_id and _attached_notes(session, [body.open_note_id]):
            body.note_ids = [body.open_note_id]
        elif body.open_category:
            body.note_ids = _category_note_ids(session, body.open_category)
    elif body.open_note_id and composer_open.kind(body.question):
        #: "What's left to do?" with a note open is about that note (the
        #: 22-10 bug doc: Ask gave one reply for every note), unless the
        #: question names something the note does not hold.
        opened = _attached_notes(session, [body.open_note_id])
        if opened and composer_open.reads_note(body.question, {"content": opened[0].content}):
            body.note_ids = [body.open_note_id]
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


#: The words of a title that do not name it: a kind, or too common to.
_TITLE_FILLER = frozenset(
    "a an the my of on in for and to with board boards whiteboard map maps mind mindmap document documents doc docs "
    "note notes untitled new copy".split()
)
_KIND_SAID = re.compile(r"\b(?:(?:white)?boards?|mind ?maps?|maps?|documents?|docs?)\b", re.I)


def _title_words(text: str) -> set[str]:
    return {w.rstrip("s") for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 2}


def _named_sources(session: Session, question: str) -> tuple[list, list[int]]:
    """Documents, boards and maps the question names by their title (INBOX
    1357, class F: "what's on my revision board" found nothing, because the
    note search reads notes only). A title counts as named when every word
    of it that names it is in the question, and the question either says a
    kind ("board", "map", "document") or the title has two such words, so a
    one-word title does not match every question that uses the word. At most
    three; the newest first."""
    asked = _title_words(question)
    if not asked or len(question or "") > 300:
        return [], []
    says_kind = bool(_KIND_SAID.search(question or ""))

    def named(title: str) -> bool:
        words = {w for w in _title_words(title) if w not in {f.rstrip("s") for f in _TITLE_FILLER}}
        return bool(words) and words <= asked and (says_kind or len(words) >= 2)

    documents = [
        d for d in session.scalars(
            select(Document).where(Document.deleted_at.is_(None)).order_by(Document.updated_at.desc()).limit(400)
        ) if named(d.title or "")
    ][:3]
    boards = [
        e.id for e in session.scalars(
            select(Entry).where(Entry.is_board == True, Entry.is_deleted == False, Entry.is_private == False)  # noqa: E712
            .order_by(Entry.created_at.desc()).limit(400)
        ) if named(manager.extract_title(e.content) or "")
    ][:3]
    return documents, boards


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
                #: A file's words were written by somebody else (audit 1028
                #: E4): the turn starts tainted, so a write asks first.
                "from_outside": True,
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
        #: A board is said as a board (INBOX 744: "a board must say board").
        is_map = board_type == "map"
        found.append(
            {
                "id": board_id,
                "content": (
                    f"{'Mind map' if is_map else 'Board'}: {title}\n"
                    f"({len(objects)} {'node' if is_map else 'item'}{'' if len(objects) == 1 else 's'}"
                    + (f", laid out as a {board_type})" if is_map else ")") + f"\n\n{outline}"
                ),
                "category": "Mind map" if is_map else "Board",
                "kind": "map" if is_map else "board",
                #: Its own day, so a newer note on the same thing is not
                #: set aside for a board that says none (`supersede`).
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
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
        #: A plain text box says nothing by its kind; a shape or a link does.
        mark = "" if node["kind"] in ("topic", "text") else f" [{node['kind']}]"
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
        #: The notes filed under the subject (its category, its tag) come first:
        #: a keyword rank by how often a word repeats put a note that says
        #: "reading" nine times above the Books note (audit 1031 C4).
        filed = _filed_under(session, composer.subject_terms(subject))
        said = filed + search_manager.keyword_search(session, subject, limit=OVERVIEW_LIMIT)
        extra += said if len({e.id for e in said}) >= 2 else said + _by_synonym(session, subject)
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


def _by_synonym(session: Session, subject: str) -> list:
    """The notes that name a topic by another word ("uni" for "university"):
    read only when the topic's own word finds fewer than two, which is no
    overview (`composer_overview.members`)."""
    found: list = []
    for word in composer.subject_terms(subject)[:3]:
        for other in sorted(a for a in composer._alternatives(composer._stem(word)) if len(a) >= 3 and a.isalpha()):  # noqa: SLF001
            found += search_manager.keyword_search(session, other, limit=OVERVIEW_LIMIT) + _filed_under(session, [other])
    return found


def _filed_under(session: Session, terms: list[str]) -> list:
    """Notes tagged with, or filed in a category named for, a word of the
    topic ("games" finds the notes tagged games that never say the word)."""
    words = [t.lower() for t in terms if len(t) >= 3][:3]
    if not words:
        return []
    clauses = [func.lower(Entry.tags).like(f'%"{like_escape(w.rstrip("s"))}%', escape=LIKE_ESCAPE) for w in words]
    #: A word at the start of the name or after a space in it ("study" is in "Courses & study").
    said = [like_escape(w.rstrip("s")) for w in words]
    named = select(Category.id).where(or_(*(func.lower(Category.name).like(pattern, escape=LIKE_ESCAPE) for w in said for pattern in (f"{w}%", f"% {w}%"))))
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


@dataclass
class _Found:
    """What `_prepare` learns about one question, filled in stage by stage."""

    detected: str
    stats: object = None
    entries: list = field(default_factory=list)
    mode: str = "none"
    meaning_loading: bool = False
    meaning_off: bool = False
    #: Notes that mention the one day asked about (E6).
    mentioned: set = field(default_factory=set)
    #: Ids that are here because they are *connected* to a match rather than
    #: because they matched. The user asked about one thing and is shown notes
    #: about another; without saying why, the panel looks like the search
    #: misfired, and the model, told nothing, would report them as results.
    connected_ids: set = field(default_factory=set)
    match_info: dict = field(default_factory=dict)
    when_phrase: str = ""
    #: As of a date: per note, the revision its text came from.
    as_of_then: dict = field(default_factory=dict)


@dataclass
class _NoteCtx:
    """What turning an entry into a prompt row needs besides the entry."""

    session: Session
    found: _Found
    attached_ids: set
    zone: object
    today: object
    time_words: dict
    files_on: dict
    as_of: "date | None"


def _detect_intent(question: str, force_notes_intent: bool, *attachments: list) -> str:
    detected = intent.classify(question)
    # `body.answering_agent` (Tier 1 section 4): a reply to the agent's own
    # question is about the notebook by construction, however smalltalk-shaped
    # the reply itself reads ("yes", "ok"). Attaching a note (or a document) is
    # likewise a statement that this is about the notebook, so it overrides the
    # classifier: the client already knows what the request actually is.
    if force_notes_intent or any(attachments):
        return intent.NOTES
    return detected


def _worked_out(question: str):
    """**Worked out, like a count** (CHAT_PLAN decision 41): a sum, a
    conversion, the time. Its sentence is exact and needs no model, so it
    travels the counted answer's road: no retrieval, said as it is.
    Translating is a model's job when one runs: that one is chat."""
    from tessellate.ai import utilities

    kind = utilities.kind_of(question)
    if kind == "weather" and (deps.get_ollama().is_running() or utilities.web_on()):
        #: "The weather is not something this app knows" is the answer only with
        #: no model and no web; with either, the turn is a general question and
        #: goes to them (the owner, 2026-10-27: a weather follow-up came back
        #: from the composer with a model up and Web on).
        return intent.NOTES, None
    worked = None
    if kind != "translate" or not deps.get_ollama().is_running():
        now = user_now(deps.get_config())
        worked = composer.compose(question, [], today=now.date(), now=now.replace(tzinfo=None))
    if worked and worked["shape"] == "utility":
        return intent.UTILITY, notebook_stats.StatAnswer(kind="utility", text=worked["text"], facts=[])
    return intent.SMALLTALK, None


def _from_records(question: str, session: Session):
    """**The app's own records** (CHAT_PLAN A3): "what did I search yesterday",
    "what ran overnight", "when did I last back up" are read from History, the
    job records and the backup folder, with times, and never searched for in
    the notes."""
    from tessellate.ai import records

    if not records.asks(question):
        return None
    config = deps.get_config()
    return records.answer(question, session, now=user_now(config), data_dir=config.data_dir)


def _activity(session: Session, question: str):
    """**What the person did in a window, every kind** (owner-1026b K20):
    notes, documents, boards, maps and reminders made, edited, binned or
    ticked off, read from the rows (`ai/activity.py`); None when the
    question is not an own-activity question with a window."""
    from tessellate.ai import activity, activity_new

    now = user_now(deps.get_config())
    return activity.answer(question, session, now=now) or activity.boards(question, session, now) or activity_new.answer(question, session, now)


def _computed_answer(session: Session, question: str, detected: str, as_of, attached: list) -> tuple[str, object]:  # noqa: ANN001
    #: **A question about the notebook's shape is answered by counting it**
    #: ("what are my most common tags", "categories with the most notes").
    #: Retrieval cannot answer those, and no tuning would: semantic search finds
    #: the notes most *like* a question, and that is not like any note. It used
    #: to retrieve five arbitrary notes and have the model decline or invent a
    #: ranking from a five-note sample. The facts are computed exactly, from
    #: rows; the model still writes the sentence when it runs (the answer is
    #: handed to it as ground truth), and with the model stopped the computed
    #: sentence is a complete answer on its own.
    #: "is this working" listed the week's notes (INBOX 1485): a social turn
    #: is never read as a question about what was done.
    if detected == intent.SMALLTALK and _social_line(question):
        return detected, None
    stats = _activity(session, question) if as_of is None and not attached else None
    if stats is not None:
        return intent.NOTES, stats
    stats = notebook_stats.answer_chat(question, session) if detected == intent.NOTES and as_of is None else None
    if detected == intent.UTILITY:
        detected, stats = _worked_out(question)
    if stats is None and as_of is None and not attached:
        stats = _from_records(question, session)
    return detected, stats


def _recall_window(session: Session, question: str, found: _Found) -> None:
    #: **A recall by time reads the window, not a ranking** (CHAT_PLAN decision
    #: 31): "what did I do last week" is every note of that week, newest first,
    #: which five notes ranked by likeness never were.
    asked = composer.plan(question, user_now(deps.get_config()).date())
    if asked.kind == "recall" and asked.window:
        found.entries = search_manager.entries_between(session, asked.window[0], asked.window[1], archived=question_noise.asks_archived(question))
        found.mode, found.connected_ids, found.match_info, found.when_phrase = "window", set(), {}, asked.window_phrase
    elif asked.window and not found.entries and not asked.terms and asked.window_phrase:
        #: "How much did I save in October": the question's own verb is no
        #: term, so nothing was searched; the window's notes are the pool the
        #: readers ask (audit 1031 C3).
        stems = composer.window_verb_stems(question, asked.window_phrase)
        window = search_manager.entries_between(session, asked.window[0], asked.window[1], limit=1000 if stems else 40, archived=question_noise.asks_archived(question))
        found.entries = [e for e in window if composer.holds_any(stems, e.content or "")][:40] if stems else window
        found.mode, found.connected_ids, found.match_info, found.when_phrase = "window", set(), {}, asked.window_phrase
    elif asked.window and found.entries:
        #: **A subject inside a window keeps the window** (1324): "what did I
        #: write about sourdough last week" was answered with sourdough notes
        #: from six weeks, under a header that said "last week". The notes
        #: inside the window are the answer when there are any.
        inside = [
            e for e in found.entries
            if e.id in found.mentioned or (e.created_at and asked.window[0] <= e.created_at.date() <= asked.window[1])
        ]
        if inside:
            found.entries = inside
            found.when_phrase = found.when_phrase or asked.window_phrase


def _with_each_side(session: Session, question: str, entries: list, locale: str | None) -> list:  # noqa: ANN001
    """A comparison needs both things in hand: a search for "Lisbon vs Porto"
    can fill its few slots with one side, so each side is searched on its own
    and the best of each is added."""
    sides = composer.compare_sides(question)
    if not sides:
        return entries
    merged = list(entries)
    seen = {e.id for e in merged}
    for side in sides:
        for entry in search_manager.retrieve_detailed(session, side, deps.get_embeddings(), limit=3, locale=locale).entries:
            if entry.id not in seen:
                seen.add(entry.id)
                merged.append(entry)
    return merged


def _with_records(session: Session, question: str, entries: list, locale: str | None) -> list:  # noqa: ANN001
    """An open checklist item may be done in a later note ("Renewed my library
    membership today" beside "[ ] Renew library membership"): a question
    about the checklist's state also fetches the notes that name its open
    items, so the answer reads one state for the item (second eye F3)."""
    if not composer_slots.asks_open(question):
        return entries
    doings = [d for e in entries for d in composer_slots.open_doings(e.content or "")][:6]
    merged, seen = list(entries), {e.id for e in entries}
    for doing in doings:
        for entry in search_manager.retrieve_detailed(session, doing, deps.get_embeddings(), limit=2, locale=locale).entries:
            if entry.id not in seen:
                seen.add(entry.id)
                merged.append(entry)
    return merged


_CHECKBOX = re.compile(r"^\s*[-*]\s*\[[ xX]\]", re.M)


def _whole_pool(session: Session, question: str, found: _Found) -> None:
    """"How much have I spent", "my biggest expense", "what's unpacked": the
    answer is over every note that records the thing (spending, an amount, a
    checklist), which the five likest never were ("spent" does not match
    "Spending October"; 2026-10-30 sweep). None at all keeps the ordinary
    retrieval, so the answer can say no note holds it."""
    mode = "money"
    if composer_money.asks(question) or composer_sum.asks_most(question):
        holds = lambda text: composer_money.records_amounts(text) or composer_sum.holds_amount(question, text)  # noqa: E731
    elif composer_slots.asks_state(question):
        holds, mode = (lambda text: bool(_CHECKBOX.search(text))), "checklist"  # noqa: E731
    else:
        return
    if recorded := _scan_notes(session, holds):
        found.entries = recorded
        found.mode, found.connected_ids, found.match_info = mode, set(), {}


def _scan_notes(session: Session, holds) -> list:  # noqa: ANN001
    """The newest notes `holds` is true of, page by page and stopping at the
    scan's hit cap, never at the first page (a notebook past 400 notes
    answered "no amounts"; second eye F1)."""
    found: list = []
    offset = 0
    while len(found) < composer_money.SCAN_HITS:
        page = manager.list_entries(session, limit=composer_money.SCAN_PAGE, offset=offset)
        found += [e for e in page if holds(e.content or "")]
        if len(page) < composer_money.SCAN_PAGE:
            break
        offset += composer_money.SCAN_PAGE
    return found[: composer_money.SCAN_HITS]


def _composer_reads(question: str) -> bool:
    """Whether a counted-notes request is one the composer answers whole
    (a ranking, an order, a count at one end of it) and so reads its own pool."""
    return composer_versus.asks(question) or bool(composer_lists.list_order(question) or composer_lists.counted_order(question))


def _search_notes(session: Session, question: str, found: _Found, attached: list, as_of, locale: str | None, composed: bool = False) -> None:  # noqa: ANN001
    #: Searched with the person's own abbreviations spelt out ("what's due in
    #: CC" also finds the notes that say Cloud Computing, B7).
    found.meaning_loading = _meaning_loading()
    found.meaning_off = _meaning_off()
    hit = search_manager.retrieve_detailed(
        session, glossary.expand(question, _glossary(session)), deps.get_embeddings(), limit=5,
        locale=locale,
    )
    #: "The latest notes about running", "my last 2 notes": the notes the
    #: request counted, not those widened by what the subject sounds like.
    counted = note_recency.recency(question, bare=len(question.split()) <= 3)
    #: The composer's own pool only where the composer answers (decision 75): a model reads the search's.
    if counted is not None and not (composed and _composer_reads(question)) and (counted.subject or counted.said_count or hit.mode == "recent"):
        found.entries = list(hit.entries)
    else:
        entries = _with_neighbours(session, question, _widened(session, question, hit.entries, scope=hit.category), scope=hit.category)
        entries = _with_records(session, question, _with_each_side(session, question, entries, locale), locale)
        found.entries = list_pool.pool(session, question, entries)
    found.mode = hit.mode
    found.connected_ids = hit.connected_ids
    found.match_info = hit.match_info
    found.when_phrase = hit.when_phrase
    found.mentioned = set(hit.mentioned)
    if not attached and as_of is None:
        _recall_window(session, question, found)
    if not attached:
        _whole_pool(session, question, found)


def _retrieve_for(session: Session, question: str, found: _Found, attached: list, attached_notes_only: bool, as_of, locale: str | None, composed: bool = False) -> None:  # noqa: ANN001
    # `attached_notes_only`: the caller has already chosen the exact, closed set
    # of notes this turn should see; retrieval on top would only add notes
    # nobody asked for, matched against whatever the turn's own instruction
    # text happens to contain. Only when there is something attached to fall
    # back to, or an empty list would search nothing and answer from silence.
    if found.stats is not None:
        # Nothing to retrieve: the answer is a count, and five notes about
        # whatever the question sounded like would only be noise beside it.
        found.mode = "stats"
    elif intent.needs_retrieval(found.detected) and not (attached_notes_only and attached):
        _search_notes(session, question, found, attached, as_of, locale, composed)


def _rewind_as_of(session: Session, question: str, found: _Found, as_of, locale: str | None) -> None:  # noqa: ANN001
    #: **As of a date** (WORLD_CLASS_PLAN I5, row 23; `ai/timetravel.py`): the
    #: candidates are today's matches and every note whose past text matches,
    #: each read as it stood at the end of that day, those that did not exist
    #: then dropped. With none left the answer is the honest empty one, said
    #: without a model, never today's notebook.
    if as_of is None or not intent.needs_retrieval(found.detected):
        return
    from tessellate.ai import timetravel

    hit = search_manager.retrieve_detailed(session, question, deps.get_embeddings(), limit=20, locale=locale)
    candidates = hit.entries + timetravel.revision_candidates(session, question)
    zone = user_now(deps.get_config()).tzinfo
    rewound = timetravel.rewind(session, question, timetravel.end_of_day(as_of, zone), candidates, limit=5)
    found.entries, found.mode = [then.entry for then in rewound], "as of"
    found.connected_ids, found.match_info = set(), {}
    found.as_of_then = {then.entry.id: then for then in rewound}
    if not rewound:
        found.stats = notebook_stats.StatAnswer(
            kind="as_of_empty",
            text=(
                f"There are no notes from on or before {timetravel.day_words(as_of)} to answer "
                "from, so there is nothing to say about how things stood then."
            ),
            facts=[],
        )


#: Text this app read out of a picture or an attached file and put under a
#: note (`_media_readings`, `_attachment_readings`) is not the person's words:
#: a note carrying it taints the turn like a clipped page (audit 1028 E4).
_READ_TEXT_MARKERS = ('text in it: "', "[Files attached to this note, as this app read them:")


def _holds_read_text(content: str) -> bool:
    return any(marker in content for marker in _READ_TEXT_MARKERS)


def _note_content(ctx: _NoteCtx, entry) -> str:  # noqa: ANN001
    session, found = ctx.session, ctx.found
    content = found.as_of_then[entry.id].text if entry.id in found.as_of_then else entry.content
    if entry.id in ctx.attached_ids:
        # Only for notes the user picked by hand. A retrieved note is a
        # candidate; an attached one is the subject of the question, and that is
        # worth the extra characters: doing this for all ten search hits would
        # spend the notes budget on pictures nobody asked about.
        return f"{content}{_media_readings(session, content)}{_attachment_readings(session, entry.id)}"
    if _mostly_pictures(content):
        return f"{content}{_media_readings(session, content)}"
    if _MEDIA_REF.search(content or ""):
        #: **A picture's caption is the note's content** (CHAT_PLAN decision
        #: 37; the owner: "Note captions arent counted as note content"): every
        #: retrieved note with a picture brings what its pictures show, one line
        #: each, so an answer can quote the caption. The text read in them stays
        #: for a note that is mostly pictures or was picked by hand: it can run
        #: to pages.
        return f"{content}{_media_readings(session, content, captions_only=True)}"
    return content


def _context_note(ctx: _NoteCtx, entry) -> dict:  # noqa: ANN001
    found, as_of = ctx.found, ctx.as_of
    content = _note_content(ctx, entry)
    return {
        # id lets agent-mode tool calls target these notes; the plain librarian
        # prompt simply ignores it.
        "id": entry.id,
        "content": content,
        #: How many pictures the note holds: the prompt says so, because the
        #: answer shows them beside this note's citation (INBOX 502).
        "pictures": len(set(_MEDIA_REF.findall(entry.content or ""))),
        "category": manager.category_name_for(ctx.session, entry),
        # Marked so the prompt can say which notes the user chose.
        "attached": entry.id in ctx.attached_ids,
        # Clipped from the web or imported (SEC-02): the agent starts the turn
        # tainted, so writes and reaching out ask first.
        "from_outside": manager.came_from_outside(entry) or _holds_read_text(content),
        # ...and which arrived by the graph rather than by the search. The
        # prompt renders this as a caveat, so an answer can say "you linked this
        # to the note about X" instead of implying it was a hit.
        "connected": entry.id in found.connected_ids,
        "dated_in_window": entry.id in found.mentioned,
        # Already computed (match_info feeds the frontend's similarity/hops
        # badges) and shown to the user, just never reached the model itself.
        # Asked for directly: "can the ai see the link reasons and similarity
        # scores in the searches?"
        "match_info": found.match_info.get(entry.id),
        #: The day it was written, and edited if since (wrapup-0927 10 n): with
        #: no dates a model guessed "your last entry" from the listing order.
        "written": _note_dates(entry, ctx.zone)
        + (f", as it read on {as_of.day} {as_of:%B %Y}" if entry.id in found.as_of_then else ""),
        "dates": _time_words(ctx.time_words.get(entry.id, []), ctx.today),
        #: Its tags and the files on it, which the model never saw (INBOX 594,
        #: the owner: "it only mentions one of the sketches not all the
        #: sketches").
        "tags": manager.entry_tags(entry),
        "files": ctx.files_on.get(entry.id, []),
    }


def _document_row(document, session: Session | None = None) -> dict:  # noqa: ANN001
    # The same shape `_context_note` builds, by hand rather than through it: a
    # Document has no category/tags and its id lives in a different table than
    # Entry's, so folding it through the Entry-shaped helper would be the wrong
    # abstraction, not a shortcut. `connected`/`match_info` are never true for a
    # hand-picked document, same as an attached note.
    return {
        "id": document.id,
        "content": f"{document.title}\n\n{document.content}",
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "category": "Document",
        "kind": "document",
        #: An imported document's text is somebody else's (audit 1028 E4).
        "from_outside": bool(session is not None and manager.document_came_from_outside(session, document.id)),
        "attached": True,
        "connected": False,
        "match_info": None,
    }


def _context_notes(session: Session, found: _Found, attached: list, attached_docs: list, attached_files: list, attached_boards: list, as_of) -> list[dict]:  # noqa: ANN001
    # Attached notes come first and are never dropped by the retrieval limit.
    # Anything retrieval also found is de-duplicated against them.
    attached_ids = {entry.id for entry in attached}
    found.entries = attached + [e for e in found.entries if e.id not in attached_ids]
    if attached:
        found.mode = "attached" if found.mode == "none" else f"attached + {found.mode}"
    now = user_now(deps.get_config())
    ids = [entry.id for entry in found.entries]
    ctx = _NoteCtx(
        session, found, attached_ids, now.tzinfo, now.date(),
        manager.entry_dates_bulk(session, ids), _files_on(session, ids), as_of,
    )
    notes = [_context_note(ctx, entry) for entry in found.entries]
    #: Listed newest first for "my last note": said on the first, which a small
    #: model otherwise ignores the order of (measured on a 1.5B model).
    if found.mode == "recent" and notes:
        notes[0]["newest"] = True
    notes.extend(_document_row(document, session) for document in attached_docs)
    # Library files, already shaped as context rows by `_attached_files`; mind
    # maps likewise (`_attached_boards` builds the outline).
    notes.extend(attached_files)
    notes.extend(attached_boards)
    return notes


def _stats_out(stats) -> dict | None:  # noqa: ANN001
    #: The computed answer, when this was a question about the notebook's shape
    #: rather than its contents. `text` is already a complete answer, which is
    #: what makes these work with the model stopped.
    if stats is None:
        return None
    return {"kind": stats.kind, "text": stats.text, "facts": stats.facts, "offer": stats.offer}


def _raw_results(session: Session, found: _Found) -> list:
    from tessellate.api.routes_entries import _to_out  # avoids a route-module cycle

    rows = []
    for entry in found.entries:
        out = _to_out(session, entry)
        if entry.id in found.as_of_then:
            out = out.model_copy(update={"content": found.as_of_then[entry.id].text})
        rows.append(out)
    return rows


def _chat_payload(session: Session, found: _Found, notes: list[dict], config, as_of) -> dict:  # noqa: ANN001
    return {
        "notes": notes,
        "intent": found.detected,
        "stats": _stats_out(found.stats),
        #: The search model was still loading, so this one read words only
        #: (`search_manager.query_vector`): said in Why, and when nothing
        #: matched, said with the answer.
        "meaning_loading": found.meaning_loading,
        "meaning_off": found.meaning_off,
        "raw_results": _raw_results(session, found),
        #: The day asked about and, per note, the revision its text came from
        #: (None for a note that read the same then as now).
        "as_of": as_of.isoformat() if as_of is not None else None,
        "as_of_revisions": {str(i): then.revision_id for i, then in found.as_of_then.items()},
        #: Words for each retrieved note's pictures, for the thumbnails an
        #: answer draws beside a citation (INBOX 502, `_picture_alts`).
        "picture_alts": _picture_alts(session, found.entries),
        "picture_sizes": _picture_sizes(found.entries),
        "search_mode": found.mode,
        # Sent beside the results rather than as a field on EntryOut: it is a
        # fact about this search, not about the note, and every other route that
        # returns an entry would otherwise carry a field that is always false.
        "connected_ids": sorted(found.connected_ids),
        # str() keys: JSON object keys are always strings and Pydantic's
        # dict[str, dict] won't silently coerce an int key.
        "match_info": {str(k): v for k, v in found.match_info.items()},
        "when_phrase": found.when_phrase,
        "style": config.get_preference("communication_style", "friendly"),
        # The name and the capped "About me", or nothing while the profile
        # switch is off: `librarian.profile_from_config` decides.
        "profile": librarian.profile_from_config(config),
    }


def _frame_matches(session: Session, question: str, notes: list[dict], match_info: dict, mode: str) -> None:
    """Why each Matching records card is there, in words, and which shown
    notes the person linked (INBOX 1310, the owner: "it has no frame of
    reference for how related each shown matching record is or why it was
    shown and how the shown notes link"). Each note gets `linked_to`, the
    shown notes it is linked to; each entry's `match_info` gets `why`, made
    for a note that came by date or recency too. Facts either way: the model
    reads them as context, the composer says them (decision 75)."""
    ids = [n["id"] for n in notes]
    if not ids:
        return
    linked: dict[int, list[int]] = {i: [] for i in ids}
    rows = session.query(EntryLink.source_entry_id, EntryLink.target_entry_id).filter(
        EntryLink.source_entry_id.in_(ids), EntryLink.target_entry_id.in_(ids)
    )
    for a, b in rows:
        #: Once each: two notes linked both ways are one link to the reader.
        if b not in linked[a]:
            linked[a].append(b)
        if a not in linked[b]:
            linked[b].append(a)
    for note in notes:
        note["linked_to"] = linked[note["id"]]
    for key, reason in composer_frame.reasons(question, notes, mode).items():
        match_info.setdefault(int(key), {})["why"] = reason
    for note in notes:
        note["match_info"] = match_info.get(note["id"])


def _named_rows(session: Session, question: str) -> list[dict]:
    """A document, board or map the question names by title, read first as
    itself (not as an attachment the person picked)."""
    named_docs, named_boards = _named_sources(session, question)
    #: Said by its title and words, as a note is (`_board_rows`).
    boards = _board_rows(_attached_boards(session, named_boards))
    named = [_document_row(d, session) for d in named_docs] + boards
    for row in named:
        row["attached"] = False
        row["named"] = True
    return named


#: How many boards, maps and documents a question's words may bring in.
MATCHED_SOURCES = 3


def _holds_every(text: str, terms: list[str]) -> bool:
    """Every term is a word (or the start of one) in `text`."""
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return all(any(w.startswith(t.lower()) for w in words) for t in terms)


def _board_rows(boards: list[dict], terms: list[str] | None = None) -> list[dict]:
    """Attached-board rows said as notes are: the title and its words, without
    the "Mind map: X (4 nodes)" head that is for a model. With `terms`, only
    those holding every term."""
    kept = []
    for row in boards:
        head, _, outline = row["content"].partition("\n\n")
        title = head.split(": ", 1)[-1].splitlines()[0]
        if terms is not None and not _holds_every(f"{title} {outline}", terms):
            continue
        row["content"] = f"# {title}\n\n{outline}"
        kept.append(row)
    return kept


def _holding(session: Session, hits: list, terms: list[str], skip: set[tuple[str, int]]) -> tuple[list, list[int]]:
    """The documents and board ids among search `hits` not yet in, a document
    kept only where its text holds every term."""
    docs, boards = [], []
    for hit in hits:
        if ("document" if hit.kind == "document" else "board", hit.ref_id) in skip:
            continue
        doc = session.get(Document, hit.ref_id) if hit.kind == "document" else None
        if doc is not None and doc.deleted_at is None and _holds_every(f"{doc.title} {doc.content}", terms):
            docs.append(doc)
        elif hit.kind != "document":
            boards.append(hit.ref_id)
    return docs, boards


def _matched_rows(session: Session, question: str, skip: set[tuple[str, int]]) -> list[dict]:
    """Boards, maps and documents whose own words hold the question's words
    (composer work list 1: "tell me about IaaS" found nothing when IaaS was a
    node on a map, because the note search reads notes). Found by the one
    search index, then kept only where every term is really in the text, so a
    partial match does not bring a source in. Read as the named ones are, so
    the answer says the kind ("on your Cloud map"). `skip` holds
    (document or board, id) pairs already in."""
    terms = [t for t in search_manager._meaningful_terms(question or "") if t not in composer._ASKING_WORDS]  # noqa: SLF001
    if not terms or len(question or "") > 300:
        return []
    hits = engine.search(session, " ".join(terms), kinds=["board", "map", "document"], limit=8, hybrid=False)
    docs, boards = _holding(session, hits, terms, skip)
    rows = [_document_row(d, session) for d in docs] + _board_rows(_attached_boards(session, boards), terms)
    for row in rows:
        row["attached"] = False
        row["named"] = True
    return rows[:MATCHED_SOURCES]


def _with_sources(session: Session, question: str, notes: list[dict], mode: str) -> list[dict]:
    """The notes with the boards, maps and documents the question names or
    whose words hold it. Where the note search found nothing by its words, a
    source that holds them leads; where it did, the notes lead and it follows."""
    named = _named_rows(session, question)
    taken = {("document" if r["kind"] == "document" else "board", r["id"]) for r in named}
    matched = _matched_rows(session, question, taken)
    return named + (matched + notes if mode in ("recent", "none") else notes + matched)


def _retrieve_ranked(session: Session, question: str, found: "_Found", attached: list, attached_notes_only: bool, as_of: "date | None", locale: str | None, composed: bool = False) -> None:
    _retrieve_for(session, question, found, attached, attached_notes_only, as_of, locale, composed)
    _rewind_as_of(session, question, found, as_of, locale)
    #: One ranker for every shape (audit 1029 C19): the note the subject
    #: names, then the one that defines it, then the rest as retrieved.
    if as_of is None and found.mode != "recent":
        found.entries = note_rank.lead(found.entries, question)


def _log_question(session: Session, found: "_Found", question: str, surface: str) -> None:
    if private_turn.active():
        #: A private chat is not a use of the notes and not an ask to offer
        #: again; the log line carries no words of it either.
        logging.getLogger("tessellate.chat").info("chat: %d note(s) via %s search (private)", len(found.entries), found.mode)
        return
    # Every entry this question surfaced counts as "used".
    for entry in found.entries:
        entry.access_count += 1
    manager.log_action(session, "queried", surface, detail=question)
    session.commit()
    logging.getLogger("tessellate.chat").info(
        "chat: %d note(s) via %s search for %r",
        len(found.entries),
        found.mode,
        # The question is the user's own text, and it reaches the terminal as
        # well as the in-app viewer, a bare %r of it can forge a log line.
        safe_value(question, 80),
    )


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
    locale: str | None = None,
    skip_search: bool = False,
    composed: bool = False,
) -> dict:
    """The shared first half of both chat endpoints: retrieve entries,
    bump their usage counters, log the question, gather AI settings.

    A message that isn't about the notebook skips retrieval entirely, there's
    nothing to search for, and searching anyway is what made "hey" come back
    with a list of notes.
    """
    recognise.note_locale(locale)  # the browser's own language and region: which half of the year "summer" is
    attached = _attached_notes(session, note_ids or [])
    attached_docs = _attached_documents(session, document_ids or [])
    attached_files = _attached_files(session, file_ids or [])
    attached_boards = _attached_boards(session, board_ids or [])
    detected = _detect_intent(question, force_notes_intent, attached, attached_docs, attached_files, attached_boards)
    detected = _notes_first(session, question, detected)
    detected, stats = _computed_answer(session, question, detected, as_of, attached)
    found = _Found(detected=detected, stats=stats)
    #: `skip_search`: the app's own reader has already answered this turn (a
    #: plan, a countdown, a quiz), so the search and the hydration of every
    #: hit (0.1 to 1 s on 300 notes) are not paid for an answer that ignores them.
    if not skip_search:
        _retrieve_ranked(session, question, found, attached, attached_notes_only, as_of, locale, composed)
    notes = _context_notes(session, found, attached, attached_docs, attached_files, attached_boards, as_of)
    #: Only the notes: a document or a file row has another table's id.
    _frame_matches(session, question, notes[: len(found.entries)], found.match_info, found.mode)
    if not (attached or attached_docs or attached_files or attached_boards or skip_search) and found.stats is None and as_of is None:
        notes = _with_sources(session, question, notes, found.mode)
    config = deps.get_config()

    _log_question(session, found, question, surface)
    return _chat_payload(session, found, notes, config, as_of)


@router.post("", response_model=ChatResponse)
@private_turn.route
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
        locale=body.locale,
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
    stop: threading.Event = field(default_factory=activity.StopEvent)
    #: What the message called the assistant ("hey lil bro, ..."), taken off
    #: `question` (`vocative.split`); `call` when that was all it said.
    address: vocative.Address | None = None
    #: The whole of a question longer than `composer.PLAN_CHARS`, which only the
    #: model and the saved turn read; `question` is what the app plans over.
    full_question: str | None = None
    #: Why the web search could not run this turn ("" when it ran): the
    #: reply then names the service and links its setting (`composer_web`).
    web_down: str = ""


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


def _chat_voice(req: _StreamRequest) -> str:
    """The voice this turn is composed in: the Settings choice, unless it is
    the default and the chat's persona asks for another by its own words
    ("a witty pirate" is playful, a precise archivist formal; CHAT_PLAN
    1353). The built-in persona asks for nothing."""
    chosen = _answer_voice()
    prompt = req.persona_prompt
    if chosen != "natural" or not prompt or str(prompt).startswith(str(librarian.DEFAULT_PERSONA)):
        return chosen
    return composer_compose.persona_cue(prompt) or chosen


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

        if not embedding_service._package_present():
            #: Not installed never loads (E30): saying "still loading" told
            #: the person to wait for something that would not come.
            return False
        return bool(callable(cold) and cold()) or (embedding_service.warmup_running() and not embeddings.is_ready())
    except Exception:  # noqa: BLE001  # no backend is a state, not an error
        return False


def _meaning_off() -> bool:
    """Search by meaning is not installed (or its engine is gone), so a miss
    read words only for good, not for a few seconds (E30)."""
    try:
        from tessellate.ai import embeddings as embedding_service

        backend = deps.get_embeddings()
        models = getattr(backend, "_models", None)
        if models is None or models.embedding_backend() == "ollama":
            return False
        return not embedding_service._package_present() and type(backend).embed_text is embedding_service.EmbeddingService.embed_text
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
    prepared["model_notes"] = [] if _unmatched_recents(req, prepared) else prepared["notes"]
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
            register=_chat_voice(req),
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


def _unmatched_recents(req: _StreamRequest, prepared: dict) -> bool:
    """A question with subject words that matched no note, answered by the
    "never look empty" fallback of the newest notes: those are not evidence,
    and a model prompt carrying about 6 KB of them answers from the wrong
    notes (audit 1030 A12). A question with no subject ("my latest notes",
    "what is in my notebook"), or one with notes attached, keeps them."""
    if not str(prepared.get("search_mode") or "") == "recent" or req.body.note_ids or req.images_raw or req.skill:
        return False
    if not req.ollama.is_running() or _composed(req, True):
        return False
    from tessellate.search.search_manager import is_recency_ask

    #: Two or more subject words is a topic ("mortgage rate zebra paddock");
    #: one is as often the notebook itself ("tell me about my notebook").
    return not is_recency_ask(req.question or "") and len(note_rank.subject(req.question or "")) >= 2


def _web_first(req: _StreamRequest, prepared: dict) -> bool:
    """The web before the notes: when no note matched, or when the turn asks
    for the web outright ("search the web for ...")."""
    return toolwords.asks_web(req.question) or (not prepared["notes"] and composer_unplaced.worthy(req.question or ""))


def _web_allowed(req: _StreamRequest) -> bool:
    """Web sources only when the person turned web search on in Settings and
    the turn may use tools (decision 43: never fetched without the toggle)."""
    try:
        on = bool(deps.get_config().get_preference("web_search_enabled", False)) and bool(req.use_tools)
        #: A spending total is the notes' sum: the web cannot know it.
        q = req.question or ""
        #: A first-person question is the person's own record: only an
        #: explicit "search the web for" sends it out (audit 1030 A1, A2).
        own = personal.about_own_notes(q) or composer_money.asks(q) or (personal.about_own_record(q) and not toolwords.asks_web(q))
        return on and not own
    except Exception:  # noqa: BLE001  # no preference is off
        return False


def _web_pref_on() -> bool:
    """Settings, Web search is on (whatever this turn's mode can do with it)."""
    try:
        return bool(deps.get_config().get_preference("web_search_enabled", False))
    except Exception:  # noqa: BLE001  # no preference is off
        return False


#: One shared deadline for reading the hits, so three slow pages cost about
#: this and not three times a page's own timeout (audit 1030 A4: 14.7 s).
WEB_PAGES_DEADLINE = 6.0


def _web_page_row(i: int, hit: dict, page: dict) -> dict | None:
    text = str(page.get("text") or "")[:WEB_PAGE_CHARS]
    title = " ".join(str(page.get("title") or hit.get("title") or page.get("domain") or "A web page").split())
    if not text.strip():
        return None
    return {
        "id": -(i + 1), "kind": "web", "url": str(page.get("url") or hit.get("url")), "domain": page.get("domain", ""),
        "content": f"{title}\n\n{text}",
        #: The result's one line for the panel: the engine's snippet,
        #: else the page's opening.
        "snippet": " ".join(str(hit.get("snippet") or text[:200]).split())[:200],
    }


def _web_pages(websearch, results: list[dict]) -> list[dict]:  # noqa: ANN001
    """The top hits read as pages, in parallel under one deadline, each a
    source of kind "web"; a page that cannot be read is skipped. When none
    reads, the engine's own snippets stand in for the pages (they are the
    search's answer), so a down page never turns results into "nothing"."""
    hits = results[:WEB_PAGES]

    def read(hit: dict) -> dict | None:
        try:
            return websearch.fetch_readable_cached(str(hit.get("url") or ""))
        except websearch.WebSearchError:
            return None

    futures = [background.future("web page", read, hit) for hit in hits]
    deadline = time.monotonic() + WEB_PAGES_DEADLINE
    pages: list[dict] = []
    for i, (hit, future) in enumerate(zip(hits, futures)):
        try:
            page = future.result(timeout=max(0.0, deadline - time.monotonic()))
        except Exception as exc:  # noqa: BLE001  # a late or failed read is skipped
            logging.getLogger("tessellate.chat").info("chat: web page %s skipped: %s", hit.get("url"), type(exc).__name__)
            continue
        row = _web_page_row(i, hit, page) if page else None
        if row:
            pages.append(row)
    if pages:
        return pages
    #: No page read: the snippets, each cited by its address.
    for i, hit in enumerate(hits):
        snippet = " ".join(str(hit.get("snippet") or "").split())
        if snippet:
            row = _web_page_row(i, hit, {"url": hit.get("url"), "title": hit.get("title"), "domain": hit.get("domain", ""), "text": snippet})
            if row:
                pages.append(row)
    return pages


def _home_place(config) -> str:  # noqa: ANN001
    """The person's city, read off their reported timezone ("Australia/Brisbane"
    is Brisbane), for a local web search; "" for none or a bare zone (UTC)."""
    name = str(config.get_preference("timezone", "") or "").strip()
    return name.rsplit("/", 1)[-1].replace("_", " ") if "/" in name and not name.startswith("Etc/") else ""


def _web_answer(req: _StreamRequest, question: str) -> tuple[dict, list[dict]] | None:
    """An answer composed from web pages (CHAT_PLAN decision 37, the second
    half): the search the agent's `web_search` uses, the top pages read as
    text (`fetch_readable_cached`, the reader's own checks), each page a
    source of kind "web" cited by its address. None when nothing answers."""
    from tessellate.search import websearch

    config = deps.get_config()
    searxng_url, provider = websearch.settings_from(config)
    try:
        results = websearch.search_web(composer_digest.web_query(question, _home_place(config)), limit=5, searxng_url=searxng_url or None, provider=provider)
    except websearch.WebSearchError as exc:
        #: One line: a refused optional service (SearXNG not running) is not a bug.
        logging.getLogger("tessellate.chat").info("chat: web search failed for a composed answer: %s", exc)
        req.web_down = str(exc)
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
#: "Can I use ChatGPT with this" is a how-to as much as "how do I" (audit
#: 1028 E32): the Models help answers it, not the "what I do" line.
_HOW_TO = re.compile(r"^\s*(?:how (?:do|can|would|should) i|how to|where (?:is|are|do i find|can i find)|why (?:is|does)|(?:can|could|does|will) (?:i|it|this|you) (?:use|connect|work with|run|support))\b", re.I)


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


def _notes_answer_due(req: _StreamRequest, tool: str, result: object, notes: list | None) -> bool:
    """A "what is due" question with nothing waiting in Reminders and a day
    ahead in the notes: the notes' computed answer wins over "You have no
    reminders waiting" (CHAT_PLAN Phase 6 P13; measured 2026-10-18)."""
    if tool != "list_reminders" or composer_lists.computed_kind(req.question or "") not in ("dates", "due_for") or not isinstance(result, dict):
        return False
    if any(not r.get("done") for r in result.get("reminders") or []):
        return False
    return composer_lists.holds_days(notes or [], user_now(deps.get_config()).date())


def _count_lead(result: dict, args: dict, counted: str) -> str:
    """"You have 4 notes in Work.", with the per-category split for the whole notebook."""
    total = int(result.get("total") or result.get("count") or 0)
    where = ""
    if counted:
        where = f" in {args['category'][:1].upper() + args['category'][1:]}" if "category" in args else f" tagged {args['tag']}"
    lead = f"You have {total} note{'' if total == 1 else 's'}{where}."
    per = result.get("by_category") or {}
    if not counted and len(per) > 1:
        lead += " Per category: " + ", ".join(f"{k} {v}" for k, v in sorted(per.items(), key=lambda kv: -int(kv[1]))[:6]) + "."
    return lead


def _counted_lead(req: _StreamRequest, asked: str) -> tuple[str, dict]:
    """"how many notes do I have about work": a figure, not a quote, with
    the counts it was said from (`fact_check.result_counts`)."""
    from tessellate.ai import tools as agent_tools

    counted = composer_lists.counted_filing(asked)
    if counted is None:
        return "", {}
    for args in ({"category": counted}, {"tag": counted}) if counted else ({},):
        result = agent_tools.execute_tool(req.session, "count_notes", args)
        if isinstance(result, dict) and (result.get("total") or result.get("count")) and not result.get("error"):
            return _count_lead(result, args, counted), fact_check.result_counts("count_notes", result)
    return "", {}


def _things_lead(name: str, result: dict) -> str:
    """"You have three recipes: A, B and C." The names only when they are few."""
    from tessellate.ai import study

    total = int(result.get("total_matching") or 0)
    titles = [study.title_of(str(n.get("content") or "")) for n in result.get("notes") or [] if isinstance(n, dict)]
    noun = name if total != 1 or not name.endswith("s") else name[:-1]
    lead = f"You have {realise.count_word(total)} {noun}"
    if total <= 6 and len(titles) == total and all(titles):
        lead += ": " + realise.join_items(titles)
    return lead + "."


def _things_counted(req: _StreamRequest, asked: str) -> tuple[str, dict]:
    """"how many recipes have I saved": the notes filed or tagged under that
    name, counted and, a few at most, named; ("", {}) when the name is
    neither a category nor a tag."""
    from tessellate.ai import tools as agent_tools

    name = composer_lists.counted_things(asked)
    tries = [(key, value) for value in dict.fromkeys((name, name.removesuffix("s"))) for key in ("category", "tag")] if name else []
    for key, value in tries:
        result = agent_tools.execute_tool(req.session, "list_notes", {key: value})
        if isinstance(result, dict) and result.get("total_matching"):
            return _things_lead(name, result), fact_check.result_counts("list_notes", result)
    return "", {}


def _filed_said(req: _StreamRequest, asked: str, now: datetime) -> tuple[str, str, dict]:
    """"list my work notes": the Work notes, or the notes tagged work
    (ledger row 442), as (lead, the list under it, its counts); a name that
    is neither is the composer's ("", "", {})."""
    from tessellate.ai import commands, tool_say
    from tessellate.ai import tools as agent_tools

    filed = commands.filed_listing(asked)
    #: In Ask "show me my X notes" is the overview, not this listing (decision 81).
    if req.body.notes_only and filed_name.shows_the_lot(asked):
        filed = None
    for key in ("category", "tag") if filed else ():
        args = {key: filed}
        result = agent_tools.execute_tool(req.session, "list_notes", args)
        if isinstance(result, dict) and result.get("total_matching"):
            said = tool_say.say("list_notes", result, args, now.date())
            return said["lead"], "\n\n".join(p for p in (said["body"], said["chips"]) if p), fact_check.result_counts("list_notes", result)
    return "", "", {}


def _said_events(lead: str, rest: str = "", counts: dict | None = None) -> list[dict]:
    """An engine answer as its lead and, apart, the list under it: the same
    text as one answer, but a model that writes the lead (decision 75) keeps
    the list as the engine drew it (`_fact_events`, the `attached` flag),
    and its words are checked against the counts the lead was said from
    (`counts`). Both marks are the server's own, taken off in `_relay_events`."""
    if not lead:
        return [{"type": "answer", "delta": rest}] if rest else []
    first = {"type": "answer", "delta": lead, **({"counts": counts} if counts else {})}
    return [first, *([{"type": "answer", "delta": f"\n\n{rest}", "attached": True}] if rest else [])]


def _filed_or_counted_events(req: _StreamRequest, asked: str, now: datetime) -> list[dict]:
    """A filed listing or a count of notes, said from the tool's figures;
    empty when the sentence is neither."""
    lead, rest, counts = _filed_said(req, asked, now)
    if lead:
        return _said_events(lead, rest, counts)
    lead, counts = _counted_lead(req, asked)
    if not lead:
        lead, counts = _things_counted(req, asked)
    return _said_events(lead, counts=counts)


def _reminder_window(asked: str, now: datetime) -> tuple | None:
    """(phrase, first day, last day) of the window a reminders question names.
    What is due is read forwards (`composer_plan.window`: "tomorrow", "next
    week", "on friday", "the next 3 days", "this week" to Sunday); a window
    in the past ("last week") is the recall plan's."""
    today = now.date()
    window = composer.plan(asked, today)
    ahead = composer_plan.window(asked, today)
    if ahead:
        start, end, phrase = ahead
        #: "this week" keeps the days already gone: what was due on Monday
        #: and is still waiting is this week's.
        if phrase in ("this week", "this month") and window.window and window.window_phrase == phrase:
            start = min(start, window.window[0])
        return phrase, start, end
    if not (window.window and window.window_phrase):
        return None
    start, end = window.window
    return window.window_phrase, start, end


def _tool_read_events(req: _StreamRequest, notes: list | None = None) -> list[dict]:
    """A read tool run with no model (decision 59, steps 1 and 2): the reading
    names the tool (`reading.tool_of`), Chat runs it with no arguments, and
    the realiser says it in one line and draws it in its form. Empty when the
    sentence names no such tool, so the composer answers as before."""
    from tessellate.ai import act_registry, question_noise, reading, realise, tool_say
    from tessellate.ai import tools as agent_tools

    now = user_now(deps.get_config())
    #: Read as repaired: "shwo me evry tag i hav plz" is the tag list, as
    #: "list my tags" is (the routing gold, `fixtures/composer/routing_1011.json`).
    asked = question_noise.repair(question_noise.tidy(req.question or ""))
    early = _filed_or_counted_events(req, asked, now)
    if early:
        return early
    got = reading.read(asked, now=now)
    if got.tool not in act_registry.NO_MODEL_READS or got.intent in act_registry.ACTS:
        return []
    result = agent_tools.execute_tool(req.session, got.tool, {})
    if _notes_answer_due(req, got.tool, result, notes):
        return []
    drawn = realise.tool_answer(got.tool, result, now.date())
    #: Said with its links to what it lists and the place to open
    #: (`tool_say`); a chart, when the counts make one, stands for the table.
    say_args: dict = {}
    #: Only a question that says "reminders" is cut to its window; "what is
    #: due this week" lists what waits, as before (1324 widened it to both).
    if got.tool == "list_reminders" and "remind" in asked.lower():
        within = _reminder_window(asked, now)
        if within:
            say_args["within"] = within
            drawn = None
    said = tool_say.say(got.tool, result, say_args, now.date())
    chart = drawn["chart"] if drawn else None
    #: A window's rows are the count the engine said ("You have 2 reminders
    #: this week", or none), not the whole list's total.
    counts = fact_check.said_counts(said["lead"]) if "within" in say_args else fact_check.result_counts(got.tool, result)
    out = _said_events(said["lead"], "\n\n".join(p for p in ("" if chart else said["body"], said["chips"]) if p), counts)
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
        #: A word, or two ("project atlas") that a note or a person names.
        if not word.replace(" ", "").isalpha():
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


def _welcome(req: _StreamRequest, seed: str, recent: list[str]) -> str:
    """The composed welcome for a hello (CHAT_PLAN 1353), or empty when the
    day's numbers cannot be read (the stored greetings answer then)."""
    try:
        return chat_extra.welcome_line(
            req.session, user_now(deps.get_config()).replace(tzinfo=None), question=req.question,
            voice=_chat_voice(req), seed=seed, said=recent, link=True,
        )
    except Exception:  # noqa: BLE001  # the stored greetings answer
        logging.getLogger("tessellate.chat").exception("chat: the composed welcome failed")
        return ""


def _hello_reply(req: _StreamRequest, seed: str, recent: list[str]) -> str:
    """A hello answered with a welcome built from the day (CHAT_PLAN 1353), or
    "" when the day's numbers cannot be read."""
    welcome = _welcome(req, seed, recent)
    if not welcome:
        return ""
    sees = composer_aware.opening(_awareness(req), seed) if req.body.screen else ""
    #: The welcome already names the last note: no second sentence about it.
    invite = "" if "“" in welcome or "](#/notes/" in welcome else _newest_word(req.session)
    asks = composer.invitation(req.question, invite, _composer_voice(), seed) if invite else composer.greeting_ask(req.question, _composer_voice(), seed)
    return "\n\n".join(p for p in (" ".join(p for p in (welcome, asks) if p), sees) if p)


def _social_reply(req: _StreamRequest, prepared: dict) -> str:
    """The app's own reply to small talk (INBOX 741), never echoing the last
    three replies (the owner: "can it have more varied responses??")."""
    recent, seed = _reply_seed(req)
    last = (req.history or [{}])[-1] if req.history else {}
    #: A next step names only a subject whose notes were found: the turn
    #: before named notes (its `objects`), never "nothing matched" (INBOX 1459).
    asked = str(last.get("question") or "") if last.get("objects") else ""
    kind = composer.social_kind(req.question, prepared["intent"])
    if kind in ("greeting", "morning") and (hello := _hello_reply(req, seed, recent)):
        return hello
    if kind == "repair":
        return _repair_reply(req, last, seed)
    said = composer.social(
        req.question,
        prepared["intent"],
        str(last.get("answer") or ""),
        asked,
        voice=_chat_voice(req),
        recent=recent,
        seed=seed,
        invite=_newest_word(req.session),
    )
    #: Only a hello says what the app can see (composer awareness): after
    #: "lol" or a groan it was a line with nothing to say (INBOX 1459).
    if kind == "test" and (subject := composer_social.ping_subject(req.question)):
        said = composer_social.ping(said, chat_extra.mentioning(req.session, subject), subject, _composer_voice(), seed)
    hello = kind in ("greeting", "morning", "how")
    sees = composer_aware.opening(_awareness(req), seed) if req.body.screen and hello else ""
    return f"{said}\n\n{sees}" if sees else said


def _repair_reply(req: _StreamRequest, last: dict, seed: str) -> str:
    """"Not what I asked" (INBOX 1485): the miss owned, what the message
    before was read as, and its better reading: Atlas on itself when it
    asked what Atlas is. Never a search for the repair's own words."""
    asked = str(last.get("question") or "")
    better = personal.about_me(asked) or ""
    if not better and question_noise.social_kind(asked) == "who":
        better = composer.social(asked, intent.SMALLTALK, voice=_chat_voice(req), seed=seed)
    return composer_social.repair(asked, last, better, _composer_voice(), seed)


def _ping_offer(req: _StreamRequest, prepared: dict) -> list[dict]:
    """A ping that says "test" offers its notes as a chip (INBOX 1485)."""
    subject = composer_social.ping_subject(req.question) if composer.social_kind(req.question, prepared["intent"]) == "test" else ""
    if not subject or not chat_extra.mentioning(req.session, subject):
        return []
    return [{"type": "offer", "offer": {"kind": "ask", "label": "", "asks": composer_social.ping_asks(subject)}}]


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
    #: Not a word of its title: "Weekly review" is about weekly nothing.
    text = str(newest[0] or "")
    start = composer._title(text)[1]
    for term in query_understanding.search_terms((text[start:] if start else text)[:400]):
        if len(term) >= 4 and term.isalpha() and term not in _NOT_A_SUBJECT and query_understanding.is_topic_word(term) and spelling.is_word(term):
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


def _offer_events(found: dict) -> list[dict]:
    """A reply with the one button it offers (an `open` offer: the setting)."""
    events: list[dict] = [{"type": "answer", "delta": found["text"]}]
    if found.get("offer"):
        events.append({"type": "offer", "offer": found["offer"]})
    return events


def _search_service() -> tuple[str, str]:
    """(SearXNG address, provider) as Settings has them, for a failure's wording."""
    from tessellate.search import websearch

    try:
        return websearch.settings_from(deps.get_config())
    except Exception:  # noqa: BLE001  # an unreadable setting is no address
        return "", ""


def _can_start_searxng() -> bool:
    """Whether the app can launch the search service itself (`composer_web.can_start`)."""
    return composer_web.can_start(*_search_service())


def _link_events(req: _StreamRequest, url: str) -> list[dict]:
    """A pasted link to be read (`composer_web`): fetched and told back when
    web access is on, else the setting that allows it. Never a notes search."""
    from tessellate.search import websearch

    if not _web_allowed(req):
        return _offer_events(composer_web.web_off(url))
    try:
        page = websearch.fetch_readable_cached(url)
    except websearch.WebSearchError as exc:
        return _offer_events(composer_web.unreadable(url, str(exc)))
    return _offer_events(composer_web.page_summary(page, url))


def _suggest_events(found: dict) -> list[dict]:
    events: list[dict] = [{"type": "answer", "delta": found["text"]}]
    if found["asks"]:
        events.append({"type": "offer", "offer": {"kind": "ask", "label": "", "asks": found["asks"]}})
    return events


def _newest_titles(session: Session, count: int = 4) -> list[str]:
    """The names of the newest notes, newest first, for a choice to open one."""
    from tessellate.ai.tools._common import _visible

    rows = session.query(Entry.content).filter(*_visible()).order_by(Entry.created_at.desc()).limit(count * 3).all()
    titles: list[str] = []
    for (content,) in rows:
        title = _closing_name(str(content or ""))
        if title and title not in titles:
            titles.append(title)
    return titles[:count]


def _closing_name(content: str) -> str:
    """What a next-step line calls a note: its heading, a whole short first
    line, or, for a title-less note whose first words would be cut mid
    sentence, its first sentence whole (audit 1030 Z38; never its date,
    INBOX 1441)."""
    name, start = composer._title(content)
    name = name.strip()
    if start == 0 and name.endswith("…"):
        name = re.split(r"(?<=[.!?;])\s|\n", content.strip(), maxsplit=1)[0].strip(" .:;")
    return realise.cut_title(name, 60) if name else ""


#: The stats kinds that ask about the notebook as a whole, which carry the
#: Statistics panel of cards (INBOX 1300 C06).
_STATS_PANEL_KINDS = {"overview", "coverage"}


def reply_panel(kind: str, question: str) -> dict | None:
    """The panel an answer carries under its words (INBOX 1300 C06): the
    notebook's cards for a question about it as a whole, the calculator for a
    sum or a conversion. Sent whoever writes the words (decision 75: it
    assists the model, never replaces it); `renderReplyPanel` draws it."""
    if kind in _STATS_PANEL_KINDS or kind == "stats":
        return {"type": "panel", "panel": "statistics"}
    if kind == "calc" or (kind == "utility" and _worked_kind(question) in _CALCULATOR_KINDS):
        return {"type": "panel", "panel": "calculator", "input": question.strip()}
    return None


#: The utility answers the calculator can redo: a sum, a list's total, a
#: root, a percentage, a unit and a currency (not a clock, a date or a
#: translation, which it does not work out).
_CALCULATOR_KINDS = {"sum", "list", "root", "percent", "units", "currency"}


def _worked_kind(question: str) -> str | None:
    from tessellate.ai import utilities

    return utilities.kind_of(question)


def _late_panel(prepared: dict, question: str | None, answer_text: str, sent_kinds: set) -> list[dict]:
    counted = prepared.get("stats")
    if not counted or not answer_text or "panel" in sent_kinds:
        return []
    panel = reply_panel(str(counted.get("kind") or ""), question or "")
    return [panel] if panel is not None else []


def _stats_events(stats: dict, question: str = "") -> list[dict]:
    """A counted answer, its chart, its panel, and its one acting offer
    (decision 70), drawn as a link on its line."""
    out = [{"type": "answer", "delta": stats["text"]}]
    drawn = _stats_chart(stats)
    if drawn is not None:
        out.append({"type": "chart", "chart": drawn})
    panel = reply_panel(str(stats.get("kind") or ""), question)
    if panel is not None:
        out.append(panel)
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
        return _stats_events(prepared["stats"], req.question or "")
    if not ollama_running or prepared.get("tool_read"):
        shown = prepared["tool_read"] if "tool_read" in prepared else _tool_read_events(req, prepared["notes"])
        if shown:
            return list(shown)
    return None


def _fact_events(req: _StreamRequest, prepared: dict, t: _Turn) -> Iterator[dict]:
    """**The engine's facts, the model's words** (CHAT_PLAN decision 75; the
    owner, 2026-10-27: "I want the ai to be able to do what the composer can
    do but better"). The engine's exact answer (`_exact_events`: a count, a
    worked sum, the app's records, a read tool's rows) goes to the model as
    facts (`librarian.build_facts_messages`); the model writes the reply, and
    the engine's own parts ride under it unchanged: the list it drew (the
    `attached` answer), its chart, its panel, its offer.

    The reply is held until it is checked, never streamed then withdrawn: a
    reply of one or two sentences, against a figure the person may act on.
    Prose that states a figure the facts lack, or a count without its figure,
    or a model that fails, leaves the engine's own answer, with no model named
    under it (a second `meta`, which every client reads as the latest)."""
    engine = list(_exact_events(req, prepared, True) or [])
    answers = [e for e in engine if e.get("type") == "answer"]
    listed = [{"type": "answer", "delta": e["delta"]} for e in answers if e.get("attached")]
    listed = listed or (_stats_listed(prepared["stats"]) if prepared["stats"] is not None else [])
    facts = "".join(str(e.get("delta") or "") for e in answers)
    counts = _engine_counts(prepared, answers)
    messages = librarian.build_facts_messages(
        _in_full(req), facts, style=prepared["style"], profile=prepared["profile"], history=req.history,
        persona_prompt=req.persona_prompt, mode=req.mode,
    )
    held = _held_reply(req, messages)
    prose = trim_assistant_padding(held["prose"]).strip()
    needs_figure = prepared["stats"] is not None and not listed
    if facts and fact_check.keeps(prose, facts, req.question or "", counts, needs_figure, user_now(deps.get_config())):
        yield from held["thinking"]
        yield from _model_said(prose, listed, engine, held["stats"])
        return
    yield from _engine_stands(req, prepared, t, engine, held)


def _engine_stands(req: _StreamRequest, prepared: dict, t: _Turn, engine: list, held: dict) -> Iterator[dict]:
    """A refused or failed reply: the engine's own answer, a `meta` naming no
    model, and what the reply cost, with no model named either (the badge and
    the facts line read `stats.model` first, `chat-attach.js`, `palette.js`)."""
    if held["prose"]:
        logging.getLogger("tessellate.chat").warning("chat: the model's words did not keep to the app's answer, which stands")
    t.will_answer = False
    yield _meta_event(req, prepared, t)
    yield from engine
    if held["stats"] is not None:
        yield {k: v for k, v in held["stats"].items() if k != "model"}


#: Rows that sum a count up rather than list what was counted ("untagged",
#: "total"): a figure for the words, not a list to show.
_SUMMARY_ROWS = {"total", "untagged", "unlinked"}


def _stats_listed(stats: dict) -> list[dict]:
    """A statistic that is itself a list, as the list to show under the
    model's words (`_fact_events`): the lines under a first line that leads
    into them ("You have 3 boards, last changed first:"), or its named rows
    ("- Work (3)"). Not a sum's "Read as ..." line, which explains, not lists.
    The no-model answer stays the engine's own (`_stats_events`)."""
    first, _sep, rest = str(stats.get("text") or "").partition("\n")
    if first.rstrip().endswith(":") and rest.strip():
        return [{"type": "answer", "delta": "\n\n" + rest.strip()}]
    rows = [r for r in stats.get("facts") or [] if isinstance(r, dict) and r.get("label") and isinstance(r.get("count"), int)]
    if len(rows) < 2 or any(str(r["label"]).lower() in _SUMMARY_ROWS for r in rows):
        return []
    return [{"type": "answer", "delta": "\n\n" + "\n".join(f"- {r['label']} ({r['count']})" for r in rows)}]


def _engine_counts(prepared: dict, answers: list) -> dict:
    """What the engine counted, by noun: the counts carried from the tool
    result (`_said_events`), the statistic's rows, and the counted statements
    of its own lead sentences (never the list under them, never a date)."""
    return fact_check.merged(
        *(e.get("counts") or {} for e in answers),
        *(fact_check.said_counts(str(e.get("delta") or "")) for e in answers if not e.get("attached")),
        fact_check.rows_counts(prepared["stats"]) if prepared["stats"] is not None else {},
    )


def _model_said(prose: str, listed: list, engine: list, stats: dict | None) -> Iterator[dict]:
    """The model's words, then the engine's list, chart, panel and offer."""
    yield {"type": "answer", "delta": prose}
    yield from listed
    yield from (e for e in engine if e.get("type") != "answer")
    if stats is not None:
        yield stats


def _held_reply(req: _StreamRequest, messages: list) -> dict:
    """The model's reply, held whole until it is checked: its words, its
    thinking (shown only with words that are kept), its token counts. A model
    that fails leaves no words."""
    held: dict = {"prose": "", "thinking": [], "stats": None}
    try:
        for piece in req.ollama.chat_stream(req.model_manager.chat_model(), messages, req.mode):
            if "thinking_delta" in piece:
                held["thinking"].append({"type": "thinking", "delta": piece["thinking_delta"]})
            elif "stats" in piece:
                held["stats"] = {"type": "stats", **piece["stats"]}
            else:
                held["prose"] += piece.get("content_delta") or ""
    except OllamaError as exc:
        logging.getLogger("tessellate.chat").warning("chat: the model could not say the app's answer: %s", safe_value(exc))
        held["prose"] = ""
    return held


def _no_notes_line(req: _StreamRequest, ollama_running: bool) -> str:
    """A subject-less question about a time with no note in it ("what did I
    write last month"), said as that with where the notes are; for any
    other question, or when a model answers, the plain "nothing matched" (O1)."""
    if ollama_running and not _composed(req, ollama_running):
        return librarian.NO_RESULTS_MESSAGE
    planned = composer.plan(req.question or "")
    #: Only a recall ("what did I write in May") says nothing was written; "how
    #: much did I save in May" asks about what the notes hold (audit 1031 C3).
    if not planned.window or planned.terms or not planned.window_phrase or planned.kind != "recall":
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
        register=_chat_voice(req),
        window=planned.window,
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
    kept = [part for part in text.split("\n\n") if not composer_digest.is_only_claim(part)]
    return "\n\n".join([*kept, line])


def _with_words_only(text: str, prepared: dict, result: dict) -> str:
    """"Your only note on it" is a claim about the whole notebook; a search
    that read words only (no search by meaning) cannot make it, so the line
    says what was measured instead (blind test 2026-10-31, item 3)."""
    words_only = prepared.get("search_mode") == "keyword" or prepared.get("meaning_off") or prepared.get("meaning_loading")
    if not words_only or not result.get("grounding"):
        return text
    parts = text.split("\n\n")
    if not any(composer_digest.is_only_claim(part) for part in parts):
        return text
    swapped = [composer_digest.only_words_line(part) if composer_digest.is_only_claim(part) else part for part in parts]
    return "\n\n".join(swapped)


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


def _help_events(req: _StreamRequest, prepared: dict, ollama_running: bool) -> list | None:
    """A how-to the app answers itself: with no model, or when composed."""
    if not (
        prepared["intent"] == intent.ABOUT_APP
        and _HOW_TO.match(req.question or "")
        and (_composed(req, ollama_running) or not ollama_running)
    ):
        return None
    helped = composer.compose(req.question, [], voice="help")
    return [{"type": "answer", "delta": helped["text"]}] if helped["shape"] == "help" else None


def _small_talk_events(req: _StreamRequest, prepared: dict, ollama_running: bool) -> list | None:
    """The events for small talk the app answers itself, or None when a model
    should (the caller builds its messages)."""
    helped = _help_events(req, prepared, ollama_running)
    if helped is not None:
        return helped
    if _composed(req, ollama_running):
        #: The app answers small talk itself when the answer is composed (the
        #: Ask box's From your notes, or no model): "what can you do" or
        #: "hello" there used to get no answer at all (engine probe P2).
        return [{"type": "answer", "delta": _social_reply(req, prepared)}, *_ping_offer(req, prepared)]
    #: A question about what Atlas can do is not small talk: with a model
    #: up it goes to the model with the app's own line (decision 75).
    if req.body.notes_only and not _asks_capability(req, prepared):
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
        return [{"type": "hint", "text": librarian.ASK_IS_FOR_NOTES, "examples": librarian.ASK_EXAMPLES}]
    if not ollama_running:
        #: The app's own voice, warm and varied (INBOX 741): with no model
        #: running Chat still answers from the notes, so small talk says
        #: so rather than "the AI model isn't running".
        return [{"type": "answer", "delta": _social_reply(req, prepared)}, *_ping_offer(req, prepared)]
    return None


def _conversational_messages(req: _StreamRequest, prepared: dict, ollama_running: bool) -> list:
    #: Small talk reaches the model as it was said, its nickname and all
    #: ("thanks legend"): the name came off only so nothing searched it.
    said = question_noise.tidy(req.body.question) if req.address is not None else req.question
    return librarian.build_conversational_messages(
        f"{said}\n\n{req.image_context}" if req.image_context else said,
        prepared["intent"],
        style=prepared["style"],
        profile=prepared["profile"],
        history=req.history,
        persona_prompt=req.persona_prompt,
        mode=req.mode,
        images=req.images,
        #: Decision 75: the capability line reaches the model as a fact.
        context="\n".join(
            part
            for part in (
                _capability_answer(req, ollama_running) if _asks_capability(req, prepared) else "",
                composer_aware.model_context(_awareness(req)) if req.body.screen else "",
            )
            if part
        ),
    )


def _asks_only_a_time(question: str) -> bool:
    """A question that names a time and no subject ("what did I write today")."""
    planned = composer.plan(question or "")
    return bool(planned.window and planned.window_phrase and not planned.terms)


def _related_sentence(related: list) -> str:
    plural = len(related) != 1
    kinds = sorted({item["kind"] for item in related})
    return (
        f" There {'are' if plural else 'is'} {len(related)} other {'items' if plural else 'item'}"
        f" that mention it, in your {' and '.join(f'{k}s' for k in kinds)}."
    )


def _personal_unsearched(req: _StreamRequest, ollama_running: bool) -> str:
    """What the notebook says of its writer ("what have I been studying
    lately"), read from every note, when the search found none: "lately"
    narrowed the search to recent notes, and the note that says it was
    older (audit 1030 Z59). Only where the app answers itself."""
    if ollama_running and not _composed(req, ollama_running):
        return ""
    own = personal.answer(req.question, lambda: personal.notes_of(req.session), user_now(deps.get_config()).date())
    return str(own["text"]) if own else ""


def _web_chip(req: _StreamRequest) -> list[dict]:
    """A miss on an ask that names the person's notes: the web is a chip to
    press, never the first stop (INBOX 1490), and only with web search on."""
    asked = req.question or ""
    if not (_web_pref_on() and composer_unplaced.says_notes(asked)) or toolwords.asks_web(asked):
        return []
    terms = composer.plan(asked).terms
    if not terms:
        return []
    return [{"type": "offer", "offer": {"kind": "ask", "label": "", "asks": [f"Search the web for {' '.join(terms[:3])}"]}}]


def _unplaced_events(req: _StreamRequest) -> list[dict]:
    """A message nothing placed, with no note to answer it (INBOX 1490): a
    short question back, with the notes and the web as its two chips, never a
    web search the person did not ask for."""
    web_on = _web_pref_on()
    said = composer_unplaced.clarify(req.question or "", web_on=web_on, voice=_composer_voice(), seed=_reply_seed(req)[1])
    asks = composer_unplaced.chips(req.question or "", web_on=web_on)
    return [{"type": "answer", "delta": said}, {"type": "offer", "offer": {"kind": "ask", "label": "", "asks": asks}}]


def _no_notes_events(req: _StreamRequest, ollama_running: bool) -> list:
    # An attached image and "no matching notes" are unrelated: retrieval never
    # sees the image, so an empty search result must not stand in for "there's
    # nothing to look at" (same fix as `librarian.answer`'s own guard).
    unknown = None if req.images_raw else composer_suggest.unknown_action(
        req.question or "", _newest_titles(req.session), embed=_composer_embed(), seed=_reply_seed(req)[1])
    if unknown is not None and not ollama_running:
        #: An instruction nothing understood is not a search for its words.
        return _suggest_events(unknown)
    own = _personal_unsearched(req, ollama_running)
    if own:
        return [{"type": "answer", "delta": own}]
    if not ollama_running and not req.images_raw and composer_unplaced.unplaced(req.question or ""):
        return _unplaced_events(req)
    return _no_notes_answer(req, ollama_running) + _web_chip(req)


def _no_notes_answer(req: _StreamRequest, ollama_running: bool) -> list:
    """The line for a question no note answers, and what else the notebook holds on it."""
    events: list = [{"type": "answer", "delta": _no_notes_line(req, ollama_running)}]
    #: A day with nothing in it graphs where the notes run (INBOX 1333 b).
    if _asks_only_a_time(req.question) and not (ollama_running and not _composed(req, ollama_running)):
        from tessellate.ai import slash_more

        strip = slash_more.empty_timeline(req.session, user_now(deps.get_config()).date())
        if strip is not None:
            events.append(strip)
    # …but the notebook is more than its notes. See `_related_elsewhere`: a
    # question answered by a document, a saved chat or a reminder used to end
    # here regardless.
    #: Not for a question that is only a day ("what did I write today"): the
    #: items it would name matched the words "write" and "today", and "it" had
    #: no referent (audit 1029 C12).
    related = [] if _asks_only_a_time(req.question) else _related_elsewhere(req.session, req.question)
    if related:
        events.append({"type": "answer", "delta": _related_sentence(related)})
        events.append({"type": "related", "items": related})
    return events


def _digest_for(req: _StreamRequest, prepared: dict, follow, current: list, restated: bool, today):  # noqa: ANN001, ANN202
    """The answer a person would give (decision 70, INBOX 812: "I may as well
    just read the notes I made on the right"): a count and a span, the facts
    under labels, what is missing, one offer. A follow-on, a "newest notes"
    turn or a sum keeps the composer's."""
    #: "where do I live", "what's my sister's name", "what do you know
    #: about me": what the notebook says of its writer (`ai/personal.py`),
    #: read from every note, not only the ones the search found.
    digest = None if follow else personal.answer(req.question, lambda: personal.notes_of(req.session), today)
    if digest is not None or (follow and not restated) or not _may_digest(prepared, req.question):
        return digest
    try:
        return composer.offered(composer_digest.answer(
            follow.question if restated else req.question, current, today=today,
            #: A retry rewords the answer itself: since the closing offer became the
            #: chips (INBOX 1466) the body is the only thing "Try again" can change.
            voice=_answer_voice(), turn=len(req.history or []) + req.body.attempt,
            insight=_insight_level(), learned=_insight_memory(req.session), known=_verdicts(req.session),
        ), req.question)
    except Exception:  # noqa: BLE001  # the composer's answer stands
        logging.getLogger("tessellate.chat").exception("chat: the digest failed")
        return None


def _told_sources(req: _StreamRequest, current: list, today) -> str:  # noqa: ANN001
    """The sentences the earlier answers drew on, as the notes wrote them,
    found by where they sit in the notes (composer work list 4). An answer
    that put a sentence in its own words ("the week of 13 July" for "this
    week") is not found in its text, so "tell me more" quoted it again; its
    grounding rows say which sentence it was. The earlier questions are
    answered again over the same notes for their rows only."""
    by_id = {n.get("source_id", n.get("id")): str(n.get("content") or "") for n in current}
    told: list[str] = []
    for question in _asked_before(req):
        for row in _earlier_rows(question, current, today):
            told.extend(_row_source(by_id, part) for part in [row, *(row.get("parts") or [])])
    return "\n".join(t for t in told if t)


#: The grounding rows of the latest answers by (question, day, notes), so a
#: "tell me more" reads the rows the answer before it wrote instead of
#: answering up to three earlier questions again over the same notes (second
#: eye F8: four reads of every note on a "more" turn).
_ROWS_KEPT: OrderedDict[tuple, list] = OrderedDict()
_ROWS_LIMIT = 24


def _rows_key(question: str, current: list, today) -> tuple:  # noqa: ANN001
    return (question, today, tuple((n.get("id"), hash(str(n.get("content") or "")), n.get("updated_at")) for n in current))


def _remember_rows(question: str, current: list, today, result: dict) -> None:  # noqa: ANN001
    if private_turn.active():
        return  # a private question is not kept, not even in memory
    _ROWS_KEPT[_rows_key(question, current, today)] = list(result.get("grounding") or [])
    while len(_ROWS_KEPT) > _ROWS_LIMIT:
        _ROWS_KEPT.popitem(last=False)


def _earlier_rows(question: str, current: list, today) -> list:  # noqa: ANN001
    """The grounding rows an earlier question's answer would have: the ones
    that answer wrote when it is remembered, else the question answered again."""
    key = _rows_key(question, current, today)
    if key in _ROWS_KEPT:
        _ROWS_KEPT.move_to_end(key)
        return _ROWS_KEPT[key]
    try:
        result = composer_digest.answer(question, current, today=today, voice=_answer_voice()) or composer.compose(
            question, current, today=today, voice=_composer_voice(), now=user_now(deps.get_config()).replace(tzinfo=None)
        )
    except Exception:  # noqa: BLE001  # the words of the earlier answers still stand
        logging.getLogger("tessellate.chat").exception("chat: an earlier question could not be answered again for its sources")
        return []
    _remember_rows(question, current, today, result)
    return result.get("grounding") or []


def _asked_before(req: _StreamRequest) -> list[str]:
    """The questions of the last three turns as they stood, a "more" being
    the question it leans on, once each."""
    asked: list[str] = []
    for turn in composer._standing([t for t in (req.history or [])[-3:] if str(t.get("question") or "").strip()]):
        if turn["question"] not in asked and not composer._MORE.match(turn["question"]):
            asked.append(turn["question"])
    return asked


def _row_source(by_id: dict, row: dict) -> str:
    """A grounding row's sentence as its note wrote it (by place), or as the
    row quotes it."""
    content = by_id.get(row.get("note_id"), "")
    if content and "start" in row and "end" in row:
        return content[row["start"]:row["end"]]
    return str(row.get("source") or "")


def _compose_for(req: _StreamRequest, prepared: dict, follow, current: list, today) -> dict:  # noqa: ANN001
    #: The conversation the history describes (decisions 34 and 35): its
    #: turn and salt word this answer, a retry ("Try again") rewords it,
    #: and the words earlier answers used are not used again.
    dialogue = composer.Dialogue.from_history(req.history)
    attempt = req.body.attempt
    return composer.compose(
        follow.question if follow else req.question,
        current,
        today=today,
        recent=str(prepared.get("search_mode") or "").endswith("recent"),
        embed=_composer_embed(),
        said="\n".join([follow.said, _told_sources(req, current, today)]) if follow and follow.kind == "more" else follow.said if follow else "",
        voice=_composer_voice(),
        register=_chat_voice(req),
        #: The turn before's answer, so this one opens differently (INBOX 741).
        previous=str(req.history[-1].get("answer") or "") if req.history else "",
        now=user_now(deps.get_config()).replace(tzinfo=None),
        salt=f"{dialogue.salt}:{attempt}" if attempt else dialogue.salt,
        turn=len(req.history or []) + 1 + attempt,
        dialogue=dialogue,
        prefer=follow.prefer if follow else "",
        resolved=True,
        #: Insights the person confirmed are said as their word; the
        #: ones they dismissed are not said (decision 60).
        learned=_insight_memory(req.session),
    )


def _open_note_answer(req: _StreamRequest, follow, current: list, today):  # noqa: ANN001, ANN202
    """The open note's own answer to "what's left", "when is it due", "who is
    involved" (`ai/composer_open.py`): short, and different for every note."""
    opened = req.body.open_note_id
    if follow or not opened or len(current) != 1 or current[0].get("id") != opened:
        return None
    if not composer_open.reads_note(req.question, current[0]):
        return None
    dialogue = composer.Dialogue.from_history(req.history)
    return composer.open_note_answer(req.question, current[0], today=today, salt=dialogue.salt)


def _composed_result(req: _StreamRequest, prepared: dict) -> tuple:
    """The composer's result with the follow-up it answered, the notes it read
    and the older ones those replaced."""
    follow = prepared.get("follow_on")
    #: A follow-on that is a question in its own right ("what about
    #: running?", "and last month?", "the second one") is answered the
    #: same way as the first turn (B8); "tell me more", "shorter" and a
    #: correction lean on the turn before and keep the composer's.
    restated = follow is not None and follow.kind in composer._RESTATES
    today = user_now(deps.get_config()).date()
    #: O11: a newer note on the same thing is the current one.
    current, older = _current_notes(req, prepared["notes"])
    result = _open_note_answer(req, follow, current, today) or _digest_for(req, prepared, follow, current, restated, today) or _compose_for(req, prepared, follow, current, today)
    if follow is not None and follow.kind == "more" and not result.get("grounding"):
        #: Nothing left unsaid: say so, with how much there is (B8).
        result = composer_digest.all_said(follow.question, prepared["notes"], today=today, voice=_answer_voice()) or result
    if follow is None and result.get("grounding"):
        _remember_rows(req.question, current, today, result)
    return result, follow, current, older


def _composed_grounding_event(req: _StreamRequest, result: dict, asks: list[str] | tuple = ()) -> dict:
    return {
        "type": "grounding",
        "sentences": result["grounding"],
        #: What to ask next, built from what the answer found and did
        #: not say (INBOX 725): the chips under a composed answer,
        #: which asks no model for them.
        #: Four at most, the closing asks (the note's own) kept whole.
        "next": [*result["next"][: 4 - len(asks)], *asks],
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


def _open_title(session: Session, body: ChatRequest) -> str:
    """The title of the plain note or document open, "" for anything else: a
    private, binned or board note is never named (composer_aware's rule)."""
    from tessellate.ai.tools._common import _visible

    if body.screen and body.screen.open_doc_id:
        doc = session.query(Document.title).filter(Document.id == body.screen.open_doc_id, Document.deleted_at.is_(None)).first()
        if doc and str(doc[0] or "").strip():
            return str(doc[0]).strip()
    if body.open_note_id:
        row = session.query(Entry.content).filter(Entry.id == body.open_note_id, *_visible()).first()
        if row:
            return composer._title(str(row[0] or ""))[0].strip()[:60]
    return ""


def _chat_topic(history: list[dict]) -> str:
    """What the last question in this chat was about: its first search term of
    four letters or more that the answer to it also used, or "". A word the
    answer never touched ("left", "write", "week") is the question's frame,
    not its subject (blind test round 2, finding 2)."""
    from tessellate.search import query as query_understanding

    for turn in reversed(history or []):
        answer = str(turn.get("answer") or "").lower()
        for term in query_understanding.search_terms(str(turn.get("question") or "")[:200]):
            if len(term) >= 4 and term.isalpha() and query_understanding.is_topic_word(term) and term.lower() in answer:
                #: As it was typed, so a name keeps its capital ("We were on Sara").
                typed = re.search(rf"\b{re.escape(term)}\b", str(turn.get("question") or ""), re.I)
                return typed.group(0) if typed else term
    return ""


def _awareness(req: _StreamRequest) -> composer_aware.Awareness:
    screen = req.body.screen
    return composer_aware.build(
        tab=screen.tab if screen else None,
        open_title=_open_title(req.session, req.body) if (screen or req.body.open_note_id) else "",
        actions=screen.actions if screen else None,
        topic=_chat_topic(req.history),
    )


def _cited_ids(result: dict) -> list[tuple[str, int]]:
    """(kind, id) of what an answer drew on, in the order it cited them: a
    document's id is another table's, and reading it as a note's named an
    unrelated note in the closing line (INBOX 1357)."""
    ids: list[tuple[str, int]] = []
    for row in result.get("grounding") or []:
        try:
            key = ("document" if row.get("kind") == "document" else "entry", int(row.get("note_id")))
        except (TypeError, ValueError):
            continue
        if key not in ids:
            ids.append(key)
    return ids


def _cited_titles(session: Session, result: dict) -> list[str]:
    """The titles of the notes an answer drew on, in the order it cited them."""
    from tessellate.ai.tools._common import _visible

    titles: list[str] = []
    for kind, nid in _cited_ids(result)[:3]:
        if kind == "document":
            doc = session.query(Document.title).filter(Document.id == nid, Document.deleted_at.is_(None)).first()
            title = realise.cut_title(str(doc[0] or "").strip(), 60) if doc else ""
        else:
            row = session.query(Entry.content).filter(Entry.id == nid, *_visible()).first()
            title = _closing_name(str(row[0] or "")) if row else ""
        if title:
            titles.append(title)
    return titles


def _name_documents(session: Session, rows: list[dict]) -> None:
    """A document row a digest quoted names its document, as the composer's own
    rows do, so the page can draw it as a source card (INBOX 1466)."""
    for row in rows:
        if row.get("kind") == "document" and not row.get("title"):
            doc = session.query(Document.title).filter(Document.id == row.get("note_id"), Document.deleted_at.is_(None)).first()
            row["title"] = str(doc[0] or "Untitled") if doc else ""


def _linked_notes(session: Session, result: dict) -> list[dict]:
    """The notes linked to the ones an answer cited, not cited themselves
    (INBOX 1466): the related row under a composed answer, which a model's
    answer has no use for (it reads the notes it is given and says the rest)."""
    from tessellate.ai.tools._common import _visible

    cited = {nid for kind, nid in _cited_ids(result) if kind == "entry"}
    if not cited:
        return []
    links = session.execute(
        select(EntryLink.source_entry_id, EntryLink.target_entry_id)
        .where(or_(EntryLink.source_entry_id.in_(cited), EntryLink.target_entry_id.in_(cited)))
        .order_by(EntryLink.id.desc())
    ).all()
    found: list[int] = []
    for pair in links:
        for other in pair:
            if other not in cited and other not in found:
                found.append(other)
    items: list[dict] = []
    for nid in found:
        row = session.query(Entry.content).filter(Entry.id == nid, *_visible()).first()
        if row and len(items) < _RELATED_LIMIT:
            items.append({"kind": "note", "id": nid, "label": _closing_name(str(row[0] or "")) or "Untitled note"})
    return items


def _with_next_step(text: str, size: str, req: _StreamRequest, cited: list[str] | None = None) -> tuple[str, list[str]]:
    """The answer's next step: the screen-aware closing line when the screen
    is known, else the chips for the cited note (INBOX 1466: the prose offer
    "Next, I can open ..." is the follow-up strip's now, not both). Left off
    by Quick and by an answer that already ends in a question."""
    if size == "short" or text.rstrip().endswith("?"):
        return text, []
    recent, seed = _reply_seed(req)
    #: An answer scoped to the open note or category does not close on the
    #: notebook's newest note, which may be about something else entirely.
    #: Nor on a note the answer never used ("what caused ww1" ended with an
    #: offer to open the Biology note): a closer names a note the answer cited.
    named = [] if req.body.note_ids else (cited if cited is not None else _newest_titles(req.session, 1))[:1]
    #: An answer from the notes ends on the notes, never on a how-to for the
    #: app ("what have I written about uni" closed on "A good next question
    #: here: how do I ask about one note", INBOX 1420).
    aware = composer_aware.closing(_awareness(req), f"{seed}:{req.question}", recent, related=not cited, asked=req.question or "", cited=cited or ()) if req.body.screen else ""
    if aware:
        return f"{text}\n\n{aware}", []
    if not named:
        return text, []
    #: Its heading, not a whole first line ("Project Atlas budget: Sam says ..."): a chip is short.
    name = named[0] if len(named[0]) <= 40 else named[0].split(": ", 1)[0].strip()
    return text, [f"Open \u201c{name}\u201d", f"What is left in \u201c{name}\u201d?"]


def _composed_events(req: _StreamRequest, prepared: dict, ollama_running: bool) -> list:
    """**A composed answer** (INBOX 688): the notes' own sentences, chosen
    by the question's shape and laid out as an answer, every clause a
    quote or a measured value (`ai/composer.py` says how). One piece,
    no stream to wait on; its grounding rows are exact, marked so, and
    the re-grounding leaves them alone.

    **And the Chat tab's answer whenever no model runs** (INBOX 725, the
    owner: "the composer response should also be able to be viewed in
    chat messages"). It replaced `extractive.answer` here, the forty-
    word passages under an apology: the composer quotes whole sentences
    under the same rule. A running model still answers every Chat turn."""
    result, follow, current, older = _composed_result(req, prepared)
    #: The open note said it holds none ("This note does not give a date"): a
    #: finished answer, not a miss to send to the web or to "general knowledge".
    said_none = str(result.get("shape") or "").startswith("open_")
    #: A note's own day is an answer with no quote to ground (`composer._written_when`).
    missed = not result["grounding"] and not said_none and not result.get("answered")
    if missed:
        redirected = _missed_events(req, follow, ollama_running, result)
        if redirected is not None:
            return redirected
    text, asks = _composed_text(req, prepared, result, follow, missed=missed, said_none=said_none)
    text = _with_older(text, older, result)
    text = _with_words_only(text, prepared, result)
    text = _with_lapsed(text, current, result, req)
    events: list = [{"type": "answer", "delta": text}, *(_web_chip(req) if missed else [])]
    if result["grounding"]:
        _name_documents(req.session, result["grounding"])
        events.append(_composed_grounding_event(req, result, asks))
        #: The notes linked to the ones it cited: the related row (INBOX 1466).
        related = _linked_notes(req.session, result)
        if related:
            events.append({"type": "related", "items": related})
    return events


def _search_footer(prepared: dict, result: dict) -> str:
    """How a miss was searched (words only, meaning off or loading). An app-tool
    answer ("undo") never read the notes, so it carries none (Z64)."""
    if result.get("shape") == "help":
        return ""
    for key in ("meaning_loading", "meaning_off"):
        if prepared.get(key):
            return "\n\n" + composer_digest.PHRASES[key]
    return ""


def _composed_text(req: _StreamRequest, prepared: dict, result: dict, follow, *, missed: bool, said_none: bool) -> tuple[str, list[str]]:  # noqa: ANN001
    """The composed text and the asks that close it (`_with_next_step`)."""
    text = result["text"]
    asks: list[str] = []
    if missed and not follow and personal.general(req.question or ""):
        #: "what's the capital of France": the world, not the notes, and
        #: said so rather than "nothing in your notes about capital".
        text = personal.general_reply(
            _web_allowed(req), web_pref=_web_pref_on(), by_choice=req.body.answer_from == "notes" and req.ollama.is_running())
    if missed:
        text += _search_footer(prepared, result)
    size = composer_tone.length(_resolve_mode(req.body.mode))
    if not follow and ((result["grounding"] and not said_none) or (said_none and req.body.screen)):
        text, asks = _with_next_step(composer_tone.fit(text, size), size, req, _cited_titles(req.session, result))
    return text, asks


def _missed_events(req: _StreamRequest, follow, ollama_running: bool, result: dict) -> list | None:  # noqa: ANN001
    """The composer found nothing: ask what was meant (an unknown action, or a
    message nothing placed), or turn to the web when it is on and was asked
    for or the question is about the world; None leaves the composer's own words."""
    if not follow and not ollama_running and not req.images_raw:
        asked = _asked_back_events(req, result)
        if asked is not None:
            return asked
    if ollama_running or not _web_allowed(req):
        return None
    return _web_events_or_down(req, follow.question if follow else req.question) if follow or composer_unplaced.worthy(req.question or "") else None


def _asked_back_events(req: _StreamRequest, result: dict) -> list | None:
    """What an instruction nothing understood asks back (`composer_suggest`),
    or the question for banter and bare words (`_unplaced_events`)."""
    unknown = composer_suggest.unknown_action(
        req.question or "", _newest_titles(req.session), embed=_composer_embed(), seed=_reply_seed(req)[1])
    if unknown is not None:
        return _suggest_events(unknown)
    #: A feature word the composer answered ("timer": one of the app's own tools)
    #: is its answer, not a message nothing placed.
    placed = result.get("shape") == "help"
    return _unplaced_events(req) if not placed and composer_unplaced.unplaced(req.question or "") else None


def _web_events_or_down(req: _StreamRequest, question: str) -> list | None:
    """The web's answer to `question`, or the buttons that fix a search that
    could not run; None when it ran and found nothing."""
    web = _web_answer(req, question)
    if web:
        return list(_web_events(*web))
    if req.web_down:
        return _offer_events(composer_web.search_down(req.web_down, *_search_service(), can_start=_can_start_searxng()))
    return None


def _diagram_events(req: _StreamRequest, prepared: dict) -> list | None:
    """"Make a diagram of my notes on X", "turn this into a flowchart" with no
    model (INBOX 1466): a ```mermaid fence the page draws, written by rule
    (`ai/composer_mermaid.py`) from the notes found, the open note, the text
    after a colon, or the answer before."""
    from tessellate.ai import composer_mermaid

    if not composer_mermaid.asks(req.question or ""):
        return None
    opened = next((str(n.get("content") or "") for n in prepared["notes"] if req.body.open_note_id and n.get("id") == req.body.open_note_id), "")
    previous = str(req.history[-1].get("answer") or "") if req.history else ""
    result = composer_mermaid.answer(req.question or "", prepared["notes"], previous=previous, opened=opened)
    return [{"type": "answer", "delta": result["text"]}] if result else None


def _no_model_events(req: _StreamRequest, prepared: dict, ollama_running: bool) -> list | None:
    """The events for a notes question the app answers itself (web, nothing
    found, or composed), or None when a model streams the answer."""
    if not ollama_running and not req.images_raw:
        drawn = _diagram_events(req, prepared)
        if drawn is not None:
            return drawn
    if _web_first(req, prepared) and not req.images_raw and not ollama_running and _web_allowed(req):
        #: No note answers, no model runs, and web search is on: the web's
        #: own sentences, cited by address (decision 37).
        down = _web_events_or_down(req, req.question)
        if down:
            return down
    if not prepared["notes"] and not req.images_raw:
        return _no_notes_events(req, ollama_running)
    if _composed(req, ollama_running) or not ollama_running:
        return _composed_events(req, prepared, ollama_running)
    return None


def _notes_messages(req: _StreamRequest, prepared: dict) -> list:
    return librarian.build_messages(
        f"{_in_full(req)}\n\n{req.image_context}" if req.image_context else _in_full(req),
        prepared.get("model_notes", prepared["notes"]),
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


def _model_stream_events(req: _StreamRequest, prepared: dict, messages: list) -> Iterator[dict]:
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
        # By construction this is reached only after the not-running
        # branches passed, so this is never "Ollama isn't running" (see
        # librarian.model_error_message's own docstring for why that
        # distinction matters).
        #
        # Logged, not just shown in the answer: reported directly: this
        # failure reached the chat bubble but never the Settings, Logs
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


def _plain_events(req: _StreamRequest, prepared: dict, ollama_running: bool) -> Iterator[dict]:
    """The pre-Wave-G behaviour: stream a grounded answer, no tools."""
    exact = _exact_events(req, prepared, ollama_running)
    if exact is not None:
        yield from exact
        return
    if not intent.needs_retrieval(prepared["intent"]):
        # Small talk: no notes, no grounding, no "I couldn't find any
        # notes matching that" in reply to "hey".
        own = _small_talk_events(req, prepared, ollama_running)
        if own is None:
            messages = _conversational_messages(req, prepared, ollama_running)
    else:
        own = _no_model_events(req, prepared, ollama_running)
        if own is None:
            if prepared.get("preview"):
                #: The composed answer at once, while the model writes its own;
                #: the client draws it as a draft and the model's first token
                #: replaces it (`_assist`).
                yield prepared["preview"]
            messages = _notes_messages(req, prepared)
    if own is not None:
        yield from own
        return
    yield from _pre_answer_events(req, prepared)
    yield from _model_stream_events(req, prepared, messages)


def _pre_answer_events(req: _StreamRequest, prepared: dict) -> list[dict]:
    """**What the composer says before a model, offered to the model's turn**
    (K26, the owner: "the ai should be able to do just as much"): the personal
    digest ("where do I live"), a place in the app, a capability, drawn as a
    card above the AI text and never in place of it. Ask box only, where the
    card is drawn; a counted answer never gets here (`_exact_events`)."""
    if not req.body.notes_only or req.body.peek:
        return []
    try:
        said = _app_said(req, prepared, True)
        if said is None:
            #: Only the personal digest: `composer_digest` answers nearly every
            #: question, so as a card it would repeat the composed answer.
            own = personal.answer(req.question, lambda: personal.notes_of(req.session), user_now(deps.get_config()).date())
            said = [{"type": "answer", "delta": own["text"]}] if own else None
    except Exception:  # noqa: BLE001  # the model answers on its own
        logging.getLogger("tessellate.chat").exception("chat: the pre-answer card failed")
        return []
    if not said or said[0].get("type") != "answer":
        return []
    offer = next((e["offer"] for e in said if e.get("type") == "offer"), None)
    return [{"type": "panel", "panel": "pre_answer", "text": said[0]["delta"], **({"offer": offer} if offer else {})}]


#: An act asked in the Ask box, which looks things up: said where to do it.
def _verdicts(session: Session):  # noqa: ANN202
    """The person's word on sentences (`ai/verdicts.py`), or None when it
    cannot be read: an answer is never lost to it. None in a private chat."""
    if private_turn.active():
        return None
    try:
        return verdicts.known(session)
    except Exception:  # noqa: BLE001
        logging.getLogger("tessellate.chat").warning("chat: the verdicts could not be read", exc_info=True)
        return None


def _insight_memory(session: Session):  # noqa: ANN202
    """What the person said of insights, or None when it cannot be read: an
    answer is never lost to the learned store. None in a private chat."""
    from tessellate.ai import insights

    if private_turn.active():
        return None
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
    from tessellate.ai import act_registry

    parsed = acts.parse(req.question, user_now(deps.get_config()))
    app_verb = act_registry.app_verb(req.question) if parsed is None else None
    if app_verb:
        yield {"type": "answer", "delta": act_registry.app_verb_line(app_verb)}
        return
    if req.body.notes_only and (parsed or {}).get("intent") != "find":
        yield {"type": "answer", "delta": acts.ask_line(parsed)}
        return
    if parsed is None:
        yield {"type": "answer", "delta": acts.capability_line()}
        return
    if parsed["intent"] == "reminder" and not parsed.get("time_given"):
        #: Asked once, never guessed as tomorrow at 9 (decision 50); the
        #: reply's time fills it (`reading._follow_slot`).
        from tessellate.ai import commands

        yield {"type": "answer", "delta": commands.ask_when_for(parsed)}
        return
    yield from _act_planned_events(req, parsed)


def _act_planned_events(req: _StreamRequest, parsed: dict) -> Iterator[dict]:
    """The preview of a parsed act: run at once with its card, or the line and
    the card that waits for Confirm."""
    planned = acts.preview(req.session, parsed, req.body.note_ids)
    card = planned.get("card")
    if card and planned.get("run"):
        mood = composer_compose.mood_of(req.question or "", voice=_chat_voice(req), seed=_reply_seed(req)[1], intent="act")
        done = acts.run(req.session, card["steps"], card.get("skipped"), lambda what: composer_compose.frame("act_done", mood, what=f"{what[:1].lower()}{what[1:]}"))
        if done["ok"] and parsed["intent"] == "reminder":
            #: Said as the card says it (INBOX 734): "Done: remind you on
            #: Friday at 9: call the dentist."
            what = f"{card['label'][:1].lower()}{card['label'][1:]}"
            done["summary"] = composer_compose.frame("act_card", mood, what=what)
        elif done["ok"] and parsed["intent"] == "complete":
            #: Already ticked, so said as done, not "I will mark it done"
            #: (audit 1030 Z60).
            what = re.sub(r"^Mark (“.*”) done", r"ticked off \1", card["label"])
            done["summary"] = composer_compose.frame("act_done", mood, what=what)
        yield {"type": "answer", "delta": done["summary"]}
        #: Run already, with Undo: the card's "nothing changes until you
        #: confirm" would contradict it.
        yield {**card, "notice": "", "done": True, "summary": done["summary"], "undo": done["undo"], "open": done.get("open")}
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
    return not str(prepared.get("search_mode") or "").endswith("recent") or composer_lists.computed_kind(question) is not None or composer_digest.shows_the_lot(question)


def _forced_notes(req: _StreamRequest, follow: object) -> bool:
    """A turn that is about the notebook whatever its words read as: a reply
    to the agent's question, a follow-up, and, in Ask, "list my work notes"
    (an act in Chat, the question it is here: the listing is the answer,
    CHAT_PLAN Phase 6 P12)."""
    if req.body.answering_agent or follow is not None:
        return True
    if not req.body.notes_only:
        return False
    if composer_lists.computed_kind(req.question) is not None or composer_digest.shows_the_lot(req.question):
        return True
    #: "summarise my gym notes": a look-up, and Ask is where look-ups are
    #: answered, so it is read as the question it is (1324). A find is
    #: listed in `_act_events`.
    parsed = acts.parse(req.question, user_now(deps.get_config()))
    return bool(parsed and parsed["intent"] == "summarise")


#: "delete everything", "wipe all my notes": a request the app never does in
#: one step, answered with the way it can be done (1324: it was answered with
#: a quote of the first notes that said "everything").
_BULK_DELETE = re.compile(
    r"^(?:please |pls )?(?:delete|erase|wipe|remove|clear|bin|trash)(?: out)? (?:everything|all(?: of)?(?: (?:my|the))?(?: notes| entries| data| stuff)?|every note|my (?:whole )?notebook)[?.!]*$",
    re.I,
)


def _this_note_said(req: _StreamRequest) -> str | None:
    """"When did I make this note?" with one note attached or open: said from
    that note's own record, no other note read (INBOX 1461, `composer_this`)."""
    from tessellate.ai import composer_this

    ids = req.body.note_ids or ([req.body.open_note_id] if req.body.open_note_id else [])
    if not composer_this.kind(req.question or "") or len(ids) > 1:
        return None
    if not ids:
        #: "This note" with none attached or open: asked, never the week's list.
        return composer_this.NOTHING_ATTACHED
    found = _attached_notes(req.session, ids)
    if not found:
        return None
    now = user_now(deps.get_config())

    def mine(when):  # noqa: ANN001, ANN202  # stored in UTC, said in the person's time
        if when is None:
            return None
        aware = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        return aware.astimezone(now.tzinfo).replace(tzinfo=None) if now.tzinfo else aware.replace(tzinfo=None)

    entry = found[0]
    return composer_this.answer(req.question, entry.content or "", mine(entry.created_at), mine(entry.edited_at), now.date())


def _extra_events(req: _StreamRequest, follow) -> list[dict] | None:  # noqa: ANN001
    """`chat_extra`'s readers (a study, a plan, a sum) on this turn."""
    return chat_extra.events(
        req.session, follow.question if follow else req.question, req.history or [], now=user_now(deps.get_config()).replace(tzinfo=None),
        seed=_reply_seed(req)[1], open_ids=[i for i in [req.body.open_note_id, *req.body.note_ids] if i],
        follow_kind=follow.kind if follow else "", said=follow.said if follow else "", asked=req.body.question, ask=bool(req.body.notes_only),
        voice=_chat_voice(req),
    )


def _this_note_events(req: _StreamRequest) -> list[dict] | None:
    said = _this_note_said(req)
    return [{"type": "answer", "delta": said}] if said else None


def _app_first_events(req: _StreamRequest, follow, ollama_running: bool) -> list[dict] | None:  # noqa: ANN001
    """What the app's own engine says before an act or a note search, when it
    answers this turn (no model, or From your notes): a study, plan or sum
    reader, a pasted link, an open-ended ask. None leaves the turn to the rest."""
    if req.images_raw or not _app_answers(req, ollama_running):
        return None
    question = req.question or ""
    if not req.skill:
        found = _this_note_events(req) or _extra_events(req, follow)
        if found is not None:
            return found
    link = composer_web.url_in(question)
    if link and composer_web.reads_link(question):
        return _link_events(req, link)
    #: "japanese note", "notes written in French" (INBOX 1490): notes found by
    #: their language, never a web search for the word.
    if spoken := note_language.asked(question):
        return chat_extra.language_events(req.session, spoken, web_on=_web_pref_on())
    if composer_suggest.open_ended(question):
        #: "do smth cool", "open a note": ask what was meant, with choices.
        return _suggest_events(composer_suggest.reply(req.question, _newest_titles(req.session), seed=_reply_seed(req)[1]))
    return None


def _first_events(req: _StreamRequest, prepared: dict, ollama_running: bool, tools_only: bool) -> Iterator[dict]:
    """The turn's events before the agent is asked: an act, a starter the
    engine answers with no model, or the plain answer."""
    if _BULK_DELETE.match(" ".join((req.question or "").split())):
        #: A refusal in fixed words, model or none: the guard is the point.
        return iter([{"type": "answer", "delta": (
            "I will not delete everything in one go. Name one note instead, for example “delete the boiler note”: "
            "it waits for your Confirm, and Undo brings it back."
        )}])
    own = prepared.get("early_events")
    if own is not None:
        #: The app's own reader wrote it (a plan, a countdown, a quiz): its
        #: times and counts are worked here, so no note is expected to hold them.
        prepared["app_first"] = True
        return iter(own)
    if prepared["intent"] == intent.ACT:
        #: Kept the engine's with a model up, deliberately (decision 75's one
        #: exception): an act with no tools to hand (Chat's Ask mode, the Ask
        #: box) is done, not discussed, and its confirmation is the card's own
        #: line. With tools, `_plan_turn` gives the act to the agent instead.
        #: `_facts_turn` never takes an act, even one whose words also count,
        #: but a read said as one ("list my work notes", `_note_tool_read`).
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


def _exact_note_events(req: _StreamRequest, notes: list) -> list[dict]:
    """The engine's exact answer over the turn's notes, as events (an answer
    and its grounding), or none (`composer_digest.exact`)."""
    if not notes:
        return []
    current, _older = _current_notes(req, notes)
    result = composer_digest.exact(req.question or "", current, today=user_now(deps.get_config()).date())
    if not result:
        return []
    return [{"type": "answer", "delta": result["text"]}, _composed_grounding_event(req, result)]


def _note_tool_read(req: _StreamRequest, prepared: dict, t: _Turn) -> None:
    """A read tool's answer (decision 59) is the whole notebook's, so the
    notes retrieval found are not its sources. Read with a model up too: a
    list is exact data, like a count, and the model is handed it as facts to
    say (`_fact_events`, decision 75) rather than reading the notes and
    miscounting (a 1.5B model said "two reminders" when there were three,
    2026-10-12). Not for a skill, whose steps read their own way.

    An act is the act's own (`_first_events`), except a read said as one
    ("list my work notes") with a model up to say it: that is facts too."""
    reads = prepared["intent"] != intent.ACT or (t.ollama_running and not t.composed and not _asks_change(req.question or ""))
    if prepared["stats"] is None and reads and not req.skill:
        prepared["tool_read"] = _tool_read_events(req, prepared["notes"])
        if not prepared["tool_read"] and t.ollama_running and not t.composed and prepared["intent"] != intent.ACT:
            #: A figure or a tick the notes settle (a sum, a day, "did I"):
            #: the engine's own, handed to the model as facts too, so the
            #: answer is the same with a model on and off (second eye F6).
            prepared["tool_read"] = _exact_note_events(req, prepared["notes"])
        if prepared["tool_read"]:
            #: Not composed from them either: the Ask box's "Composed from
            #: your notes" label is for a quoted answer (INBOX 801).
            prepared["notes"] = []


def _cited_question(req: _StreamRequest) -> str | None:
    """"Open it", "tell me more about the starter" (audit 1029 C44): the
    question with its referent named, the leading note the last answer
    cited, so it is never searched by its own words. Model up or down."""
    from tessellate.ai import reading

    turns = [{"text": str(t.get("question") or ""), "objects": t.get("objects") or []} for t in (req.history or [])[-reading.FOLLOW_TURNS:]]
    return reading.cited_follow(req.question, turns, user_now(deps.get_config()))


def _follow_up(req: _StreamRequest):
    """The follow-up the turn before gives this one: a spoken act stands in
    for the question itself; a composed turn's "tell me more" is
    `composer.follow_on`'s; None otherwise."""
    composed = bool(req.history) and ((req.body.notes_only and req.body.answer_from == "notes") or not req.ollama.is_running())
    more = composer.follow_on(req.question, req.history) if composed else None
    if more is not None and more.kind == "more":
        #: A composed "tell me more" is the turn before again at more length,
        #: not a search for the note it cited: since every answer's links
        #: name its objects (audit 1030 Z53), "more" after a summary was
        #: rewritten to "tell me more about the Lecture 5 note" and searched.
        return more
    cited = _cited_question(req) if req.history else None
    if cited is not None:
        req.question = cited
    spoken = _spoken_act(req) if req.history and not req.ollama.is_running() else None
    if spoken is not None:
        req.question = spoken
        return None
    return composer.follow_on(req.question, req.history) if composed else None


def _turn_label(content: str) -> str:
    """A note as a history turn names it (`chatTurnObjects` in chat-attach.js):
    its first line without heading or list marks, up to the first stop."""
    first = re.sub(r"^[#*>\-\s]+", "", (content or "").strip().split("\n", 1)[0])
    return re.split(r"[:.!?]", first)[0].strip()[:80]


def _cited_scope(req: _StreamRequest, follow) -> list[int]:  # noqa: ANN001
    """The note the last answer led with, when this question only leans on it
    ("when is it", "how much does it cost", "what time", "what did we decide
    about it": audit 1030 Z53). It is read like an open note: the follow-on
    keeps its subject, and the slot runs on that note rather than on
    whichever note best matches the bare words."""
    objects = ((req.history or [{}])[-1].get("objects") or []) if req.history else []
    if not objects or req.body.note_ids or (follow is not None and follow.kind != "pronoun") or not composer.refers_back(req.question):
        return []
    label = str(objects[0]).strip().lower()
    rows = req.session.execute(
        select(Entry.id, Entry.content).where(
            Entry.is_deleted == False, Entry.is_private == False, Entry.content.ilike(f"%{like_escape(label)}%", escape=LIKE_ESCAPE)  # noqa: E712
        ).limit(25)
    ).all()
    return [row.id for row in rows if _turn_label(row.content).lower() == label][:1]


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
    return not agentic and not composing and not conversational and prepared["stats"] is None and not prepared.get("tool_read") and not prepared.get("app_first")


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


@dataclass
class _Turn:
    """What one streamed turn carries from its stages to the next. The stages
    are separate functions so each can be read, and tested, on its own."""

    ollama_running: bool = False
    composed: bool = False
    tools_provider: object = None
    tools_only: bool = False
    composing: bool = False
    conversational: bool = False
    will_answer: bool = False
    #: The engine has the exact answer and a model says it (`_fact_events`).
    facts: bool = False
    agentic: bool = False
    #: B30: the seconds each stage landed at, for "Why this answer".
    started: float = 0.0
    marks: dict = field(default_factory=dict)
    answer_text: str = ""
    in_prose: bool = False
    #: Every note a tool read during the turn is a grounding candidate, not
    #: only the retrieval set: an agent answer that named three notes cited
    #: one before this. `touched` on each tool event names them.
    touched_note_ids: list = field(default_factory=list)
    #: Rows an answer brought with it, exact by construction (the composed
    #: and the extractive answers): kept, saved, and never re-grounded.
    exact_grounding: list | None = None
    shape: str | None = None
    sent_kinds: set = field(default_factory=set)
    model_checks: dict | None = None


def _event(payload: dict) -> str:
    return json.dumps(payload) + "\n"


def _stream_prepare(req: _StreamRequest) -> dict:
    """Retrieval happens INSIDE the stream, not before it: that is the whole
    latency win. Nothing before this touches the model.

    **A follow-up read against the turn before** (INBOX 725): "tell me more"
    or "the second one" means nothing searched on its own. Only for a turn the
    composer answers (Ask's From your notes, or any turn with no model), and
    only with a turn before it: a model reads the history itself, and the
    routing (`_composed`) is unchanged by it."""
    recognise.note_locale(req.body.locale)
    follow = _follow_up(req)
    early = _app_first_events(req, follow, req.ollama.is_running())
    scoped = _cited_scope(req, follow)
    prepared = _prepare(
        req.session,
        _searched_question(req, follow),
        scoped or req.body.note_ids,
        force_notes_intent=_forced_notes(req, follow),
        attached_notes_only=bool(scoped) or req.body.attached_notes_only,
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
        locale=req.body.locale,
        skip_search=early is not None,
        composed=_app_answers(req, req.ollama.is_running()),
    )
    prepared["follow_on"] = follow
    prepared["early_events"] = early
    return prepared


def _is_composing(prepared: dict, composed: bool, ollama_running: bool, tools_only: bool) -> bool:
    """A turn with no model, no tool fallback and notes to quote is composed in
    `_plain_events` whatever surface asked (INBOX 725): labelled so, and its
    quotes are never trimmed or re-grounded. So is one the app's own reader
    answered before any search (a plan, a countdown, the week's notes)."""
    return composed or prepared.get("early_events") is not None or (
        not ollama_running
        and not tools_only
        and prepared["stats"] is None
        and intent.needs_retrieval(prepared["intent"])
        and bool(prepared["notes"])
    )


def _will_answer(req: _StreamRequest, prepared: dict, t: _Turn) -> bool:
    """Whether a model writes this turn's prose."""
    if t.composed or prepared.get("tool_read"):
        return False
    if _asks_capability(req, prepared) and _app_answers(req, t.ollama_running):
        return False
    if prepared["intent"] in (intent.UTILITY, intent.ACT):
        return False
    if not (t.ollama_running if t.conversational else (t.ollama_running or t.tools_only)):
        return False
    return bool(prepared["notes"]) or bool(req.images_raw) or req.use_tools or t.conversational


def _offered_open(req: _StreamRequest) -> bool:
    """"Open the note about <title>", one of the choices the app itself
    offered (`composer_suggest.reply`), is done by the app with a model up
    too: the note is named exactly, and a small model sent it to a search for
    another note's words (INBOX 1455)."""
    parsed = acts.parse(req.question or "", user_now(deps.get_config()))
    if not parsed or parsed.get("intent") != "open" or not parsed.get("about"):
        return False
    asked = _uncut(parsed["about"])
    #: A cut choice ("I had work today…") is a prefix: one offered under an
    #: older cut still names the note now called by its whole first sentence
    #: (audit 1030 Z38). Without the cut mark the title must be whole.
    cut = (req.question or "").rstrip(" ?.").endswith("…")
    return any(name == asked or (cut and name.startswith(asked)) for name in map(_uncut, _newest_titles(req.session)))


def _uncut(title: str) -> str:
    return title.rstrip("…. ").lower()


def _plan_turn(req: _StreamRequest, prepared: dict) -> _Turn:
    t = _Turn()
    t.ollama_running = req.ollama.is_running()
    if prepared["intent"] == intent.ACT and t.ollama_running and req.use_tools and not req.body.notes_only and not _offered_open(req):
        #: With a model in Agent mode, an act is the agent's: its tools are the
        #: same, and it can ask and plan (decision 38 is for no model).
        prepared["intent"] = intent.NOTES
    t.composed = _composed(req, t.ollama_running)
    _note_tool_read(req, prepared, t)
    t.tools_provider = _tools_provider(req, prepared, t.ollama_running)
    t.tools_only = t.tools_provider is not req.ollama
    t.composing = _is_composing(prepared, t.composed, t.ollama_running, t.tools_only)
    t.conversational = not intent.needs_retrieval(prepared["intent"])
    t.facts = _facts_turn(req, prepared, t)
    t.will_answer = t.facts or _will_answer(req, prepared, t)
    return t


def _facts_turn(req: _StreamRequest, prepared: dict, t: _Turn) -> bool:
    """Whether a model writes this turn from the engine's exact answer (CHAT_PLAN
    decision 75; the owner, 2026-10-27: "why is it responding as the composer
    when my ai is in use??"): a count, a worked sum, the app's records or a
    read tool's rows, with a model up, on every surface but the Ask box's From
    your notes (`_composed`). Not a skill run, which reads its own way.

    Not "nothing matched" (`_no_notes_events`): the check on the model's words
    (`fact_check.keeps`) reads figures, and that answer has none, so a model
    saying "here is what I found" over it could not be caught. With tools (the
    popup agent, Chat's Agent mode) the agent has that turn and can search."""
    if not t.ollama_running or t.composed or req.skill:
        return False
    if _asks_change(req.question or "") or (prepared["intent"] == intent.ACT and not prepared.get("tool_read")):
        #: "save my first note" read as the first-note count: a request to do
        #: something is never a figure to say. With tools it is the agent's,
        #: which has the tools to do it; with none it is the act's own path
        #: (`_first_events`), done rather than discussed, on every mode. A
        #: read said as an act ("list my work notes") is facts (`_note_tool_read`).
        return False
    return prepared["stats"] is not None or bool(prepared.get("tool_read"))


#: The words before a request ("can you please", "hey, could you"), any
#: number of them, then the verb of a change, then its object (`_asks_change`).
_LEAD_IN = re.compile(
    r"^\s*(?:(?:please|pls|plz|kindly|hey|hi|ok|okay|so|now|just|can you|could you|would you|will you|go ahead and)\b[\s,]*)*",
    re.I,
)
_CHANGE_VERB = re.compile(
    r"(?:save|create|make|add(?!\s+(?:up|together)\b)|write|draft|delete|remove|bin|move|tag|untag|rename|pin|unpin|set|"
    r"link|unlink|file|archive|restore|edit|update|change|mark|tick|complete|merge|split|tidy|clean|clear|put|jot)\b"
    r"(?:\s+(?:up|down|off|away|out)\b)?",
    re.I,
)
#: "remind me" is a change only with what to be reminded of or when
#: ("remind me to call mum", "remind me tomorrow"), not "remind me how many".
#: A time phrase straight after it is the recogniser's to find (the one
#: reader of date words, tests/test_one_reader.py).
_REMIND = re.compile(r"remind\s+me\s+(?:to|at|in|on|by|every|before|after)\b", re.I)
_REMIND_ME = re.compile(r"remind\s+me\s+", re.I)
#: "remind me about my first note", "remind me of ..." name what to be
#: reminded of; "remind me of what is due" asks (`_QUESTION_WORDS`).
_REMIND_OF = re.compile(r"remind\s+me\s+(?:about|of)\s+(?!(?:how|what|when|where|which|who|whether|why)\b)\w", re.I)
#: What a change can be done to: the app's things, or a word pointing at one.
_CHANGE_OBJECTS = {
    "note", "notes", "entry", "entries", "reminder", "reminders", "task", "tasks", "to-do", "to-dos", "todo", "todos",
    "tag", "tags", "label", "labels", "category", "categories", "folder", "folders", "document", "documents", "doc",
    "docs", "file", "files", "pdf", "pdfs", "board", "boards", "map", "maps", "link", "links", "skill", "skills",
    "page", "pages", "checklist", "checklists", "item", "items", "it", "them", "this", "that", "these", "those",
    "everything",
    #: What of a note a change is done to ("change the title of my first note").
    "title", "name", "body", "text", "date", "contents", "content", "description", "summary", "colour", "color",
}
#: After an object, the word that makes it a figure asked for ("clean my
#: notes count", "mark my reminders count"), not a thing to change.
_COUNT_WORDS = {"count", "counts", "total", "totals", "number", "tally", "size", "length"}
#: Words that end the object before a thing is named ("set of tags", "make
#: sense of", "update on", "add three and four", "update me on").
_OBJECT_STOPS = {
    "of", "on", "in", "for", "about", "with", "and", "or", "me", "us", "how", "what", "when", "where",
    "which", "who", "whether", "why", "is", "are", "do", "does", "i",
}


def _asks_change(question: str) -> bool:
    """Whether a sentence asks for a change, not a figure (`_facts_turn`): an
    imperative verb whose object, within four words and before a stop, is a
    thing the app can change ("save my first note", "tag it work"). "to" and
    "from" are passed ("add to my first note"); "of" is a stop unless a part
    of a note was named first ("change the title of my first note").
    "tag cloud of my notes", "file count", "clean my notes count" and "add
    three and four" name none."""
    start = _LEAD_IN.match(question).end()
    if _REMIND.match(question, start) or _REMIND_OF.match(question, start):
        return True
    remind = _REMIND_ME.match(question, start)
    if remind and any(at == 0 for at, _, _ in recognise.find(question[remind.end():])):
        return True
    verb = _CHANGE_VERB.match(question, start)
    if not verb:
        return False
    words = re.findall(r"[a-z]+(?:-[a-z]+)*|\d+", question[verb.end():].lower())[:5]
    for i, word in enumerate(words[:4]):
        if word in _CHANGE_OBJECTS:
            return not (i + 1 < len(words) and words[i + 1] in _COUNT_WORDS)
        if word in _OBJECT_STOPS:
            return False
    return False


def _prime_model_notes(req: _StreamRequest, prepared: dict, t: _Turn) -> None:
    if t.will_answer and not t.tools_only:
        _assist(req, prepared)
    if t.will_answer:
        #: B31, B32: the model reads the notes with the person's verdicts
        #: written in, as context; grounding reads them as they are.
        known = _verdicts(req.session)
        if known:
            prepared["model_notes"] = verdicts.for_model(prepared.get("model_notes", prepared["notes"]), known)


def _meta_event(req: _StreamRequest, prepared: dict, t: _Turn) -> dict:
    if t.tools_only and t.will_answer:
        answered_by = "needle (tools only)"
    else:
        answered_by = req.model_manager.served_chat_model(req.ollama) if t.will_answer else None
    return {
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
        "answered_by": answered_by,
        "ollama_running": t.ollama_running,
        #: The Ask box labels the answer "Composed from your notes, no AI".
        "composed": t.composing,
    }


def _choose_events(req: _StreamRequest, prepared: dict, t: _Turn) -> tuple:
    """The turn's event source, and the notice to send first (or None).

    Small talk never goes near the agent: "hey" is not a request to do
    anything, and handing it a toolbox invites it to invent an errand."""
    if t.facts:
        return _fact_events(req, prepared, t), None
    events = _first_events(req, prepared, t.ollama_running, t.tools_only)
    can_agent = (
        not t.composed
        and not prepared.get("tool_read")
        and (t.ollama_running or t.tools_only)
        and req.use_tools
        and intent.needs_retrieval(prepared["intent"])
    )
    if not can_agent:
        return events, None
    agent_events = _agent_events(req, prepared, t.tools_provider)
    first = _first_agent_event(req, agent_events)
    if first is None or first.get("type") == "unsupported":
        # The active model can't do tool calls, plain Q&A, never a hard
        # dependency. INBOX 272 part 1: this used to be a silent `pass`, so
        # Agent mode was asked for and downgraded with nothing on screen to
        # say so or how to fix it. `first` (built in ai/agent.py) already
        # carries the remedy; the caller forwards it before the plain stream.
        return events, first
    t.agentic = True
    return chain([first], agent_events), None


#: The events that begin a new prose block in the transcript. A multi-round
#: turn emits its prose in bursts with a step or a tool call between them, and
#: the client draws each burst as its own block; gluing raw deltas made "…in
#: it.I checked…", one unsplittable sentence no citation walker can find
#: (INBOX 40). Anything else (`meta`, `token`, `stats`) is bookkeeping and
#: must not break a paragraph in half.
_PARAGRAPH_BREAKS = {"thinking", "tool", "step", "plan", "result"}


def _note_kind(t: _Turn, kind: str, payload: dict) -> None:
    t.sent_kinds.add(kind)
    if kind == "grounding":
        if payload.get("exact"):
            t.exact_grounding = payload.get("sentences") or []
        t.shape = (payload.get("support") or {}).get("shape") or t.shape
    if kind == "answer" and "answered" not in t.marks:
        t.marks["answered"] = time.perf_counter() - t.started


def _fold_event(t: _Turn, kind: str, payload: dict, live_grounder) -> list:  # noqa: ANN001
    """Fold one event into the running answer; the live grounding rows when
    this delta could have closed a sentence."""
    if kind in _PARAGRAPH_BREAKS:
        t.in_prose = False
        if kind == "tool":
            for item in payload.get("touched") or []:
                if item.get("kind") == "note" and isinstance(item.get("id"), int):
                    t.touched_note_ids.append(item["id"])
        return []
    if kind != "answer":
        return []
    if t.answer_text and not t.in_prose:
        t.answer_text += "\n\n"
    delta = payload.get("delta") or ""
    t.answer_text += delta
    t.in_prose = True
    #: Only when this delta could have ended a sentence: a split of the whole
    #: answer per token is wasted work on every other one.
    if live_grounder is not None and any(ch in delta for ch in ".!?\n"):
        return live_grounder.feed(t.answer_text)
    return []


def _live_grounder(req: _StreamRequest, prepared: dict, t: _Turn):  # noqa: ANN202
    """**Grounding as the answer streams** (INBOX 320). The Ask tab numbers its
    Matching records from the answer's citations, which used to arrive in one
    event after the last token. Each completed sentence is grounded as it lands
    and the rows so far go out as `grounding_live`, which the client treats as
    provisional: the `grounding` event is still computed over the whole,
    trimmed answer. Plain answers only: an agent turn's candidates grow with
    every note a tool reads, so a live row there could name a set the final
    pass would not."""
    if t.agentic or t.conversational or t.composing or not prepared["notes"]:
        return None
    return SentenceGrounder(prepared["notes"], meaning=search_chunks.meaning_scorer(req.session, deps.get_embeddings()))


def _relay_events(req: _StreamRequest, prepared: dict, t: _Turn, events) -> Iterator[str]:  # noqa: ANN001
    live_grounder = _live_grounder(req, prepared, t)
    #: The fence markers a small model echoes back are taken out of the answer
    #: before anything reads or saves it (`fence.AnswerScrubber`).
    scrubber = fence.AnswerScrubber()
    try:
        for payload in events:
            kind = payload.get("type")
            _note_kind(t, kind, payload)
            if kind == "answer":
                #: `attached` and `counts` are the server's own marks (`_said_events`), not the client's.
                payload = {**{k: v for k, v in payload.items() if k not in ("attached", "counts")}, "delta": scrubber.feed(payload.get("delta") or "")}
                if not payload["delta"]:
                    continue
            else:
                held = scrubber.flush()
                if held:
                    t.answer_text += held
                    yield _event({"type": "answer", "delta": held})
            live_rows = _fold_event(t, kind, payload, live_grounder)
            yield _event(payload)
            if live_rows:
                yield _event({"type": "grounding_live", "sentences": list(live_grounder.rows)})
        held = scrubber.flush()
        if held:
            t.answer_text += held
            yield _event({"type": "answer", "delta": held})
    except Exception as exc:  # noqa: BLE001  # a failure partway through rather
        # than before the first event (a later skill step, say): say what
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
        yield _event({"type": "answer", "delta": f"\n\nSomething went wrong: {safe_value(exc)}"})


def _trim_answer(t: _Turn) -> Iterator[str]:
    """**The greeting and the sign-off come off before anything else reads it**
    (the owner, 2026-09-21). Here, not in the browser: grounding marks
    sentences by their offsets in this string, the saved turn stores it, and an
    export reads it back, so trimming anywhere else would leave three copies of
    the answer disagreeing about where sentence two starts. Not a composed
    answer: its opening line is a fixed phrase, and its quotes are the
    person's words, which no trim may touch."""
    trimmed = t.answer_text if t.composing else trim_assistant_padding(t.answer_text)
    if trimmed != t.answer_text:
        t.answer_text = trimmed
        #: The browser has already drawn the untrimmed text, so it is sent the
        #: finished answer to replace it with. One event at the end rather than
        #: a filter on every delta: a stream that edits what it already said,
        #: token by token, flickers.
        yield _event({"type": "answer_final", "text": t.answer_text})


def _note_with_hint(note: dict) -> str:
    """A note's words plus the time words the prompt worked out for it ("in 5
    days"): the model is told those figures, so they are backed (Z69)."""
    return f"{note.get('content') or ''}{librarian._dates_hint(note)}"


def _check_model_prose(req: _StreamRequest, prepared: dict, t: _Turn) -> Iterator[str]:
    """**The model proposes, the engine decides** (CHAT_PLAN decision 53): a
    model's plain answer passes the same validators as the engine's, so a
    number or name in none of the notes it was given, nor the question, is
    said under it. The agent path checks its own (`agent.py`, H2). A model that
    stopped leaves the composed answer under MODEL_STOPPED_NOTE: the engine's
    words, not the model's."""
    if MODEL_STOPPED_NOTE in t.answer_text or t.exact_grounding is not None or not t.answer_text:
        return
    if not _checks_grounding(prepared, t.agentic, t.composing, t.conversational):
        return
    t.model_checks = validate.check_model_answer(
        t.answer_text,
        [
            req.question,
            str(req.image_context or ""),
            #: The date the prompt told the model, so "today is 10 October" is backed.
            user_now(deps.get_config()).strftime("%A %d %B %Y %H:%M"),
            *(_note_with_hint(n) for n in [*prepared["notes"], *(prepared.get("model_notes") or [])]),
        ],
        question=req.question or "",
    )
    if t.model_checks["unbacked"]:
        heads = source_check.heads_up(t.model_checks["unbacked"])
        t.answer_text += heads
        yield _event({"type": "answer", "delta": heads})


def _ground_final(req: _StreamRequest, prepared: dict, t: _Turn) -> tuple:
    """The rows the saved turn carries and the `grounding` event for them
    (INBOX 241). A conversational turn, or one nothing could be grounded
    against, saves an empty list, which is the truth about that answer."""
    candidates = _grounding_candidates(req.session, prepared["notes"], t.touched_note_ids)
    grounding: list[dict] = list(t.exact_grounding or [])
    if t.exact_grounding is not None or t.conversational or not candidates or not t.answer_text:
        return grounding, None
    grounding = (
        ground_answer_sentences(
            t.answer_text, candidates, numbered=len(prepared["notes"]),
            meaning=search_chunks.meaning_scorer(req.session, deps.get_embeddings()),
        )
        or []
    )
    if not grounding:
        return grounding, None
    # A touched note is not in `raw_results`, so the client has no text to
    # name it by; the label rides on each entry.
    labels = {note["id"]: " ".join(str(note.get("content") or "").split())[:60] for note in candidates}
    for row in grounding:
        row["label"] = labels.get(row["note_id"], "")
    #: How much of the answer the notebook backs, beside which sentences it
    #: backs (CHAT_PLAN Phase 1): the threshold travels with the numbers
    #: rather than being picked again in the frontend.
    return grounding, {
        "type": "grounding",
        "sentences": grounding,
        "support": grounding_support(t.answer_text, grounding),
        **({"checks": t.model_checks["findings"]} if t.model_checks else {}),
    }


def _unsaid_greeting(req: _StreamRequest, prepared: dict, t: _Turn) -> Iterator[str]:
    """A model that answered small talk with nothing at all ("hello" under an
    empty reply) leaves a blank bubble: the app's own reply stands in (Z71).
    A turn that already said what it is for (the Ask box's hint) asked no
    model, so nothing is unsaid."""
    if t.conversational and t.ollama_running and not t.answer_text.strip() and "hint" not in t.sent_kinds:
        t.answer_text = _social_reply(req, prepared)
        yield _event({"type": "answer", "delta": t.answer_text})


def _settle_turn(req: _StreamRequest, prepared: dict, t: _Turn) -> Iterator[str]:
    yield from _unsaid_greeting(req, prepared, t)
    yield from _trim_answer(t)
    yield from _check_model_prose(req, prepared, t)
    grounding, grounding_event = _ground_final(req, prepared, t)
    if grounding_event is not None:
        yield _event(grounding_event)
    if req.body.notes_only and t.answer_text and not req.body.peek and not private_turn.active():
        _save_ask_turn(req.session, _in_full(req), t.answer_text, prepared, grounding)
    #: A model that wrote a counted answer's words still gets its panel
    #: (INBOX 1300 C06; decision 75: the panel assists, the model leads).
    yield from map(_event, _late_panel(prepared, req.question, t.answer_text, t.sent_kinds))
    if t.answer_text:
        t.marks["done"] = time.perf_counter() - t.started
        yield _event({"type": "why", "lines": _why(req, prepared, grounding, t.composing, t.will_answer, t.tools_only, t.ollama_running, t.shape, t.marks)})
    yield _event({"type": "done"})


def _stream_lines(req: _StreamRequest) -> Iterator[str]:
    # Flush a first byte immediately. The semantic search below can be a
    # slow cold start (loading the embedding model, warming the index);
    # emitting this now means the browser's stream opens right away and
    # its "typing…" indicator keeps animating instead of looking frozen
    # while the whole request blocks (user-reported lag).
    yield _event({"type": "status", "stage": "searching"})
    started = time.perf_counter()
    prepared = _stream_prepare(req)
    t = _plan_turn(req, prepared)
    t.started = started
    t.marks["read"] = t.marks["searched"] = time.perf_counter() - started
    _prime_model_notes(req, prepared, t)
    yield _event(_meta_event(req, prepared, t))
    events, notice = _choose_events(req, prepared, t)
    if notice is not None:
        yield _event(notice)
    yield from _relay_events(req, prepared, t, events)
    yield from _settle_turn(req, prepared, t)



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
    #: Filler ("errrmmm. hi") is read past before anything reads it (INBOX 1485).
    question, address = _address(skill["question"] if skill else question_noise.drop_filler(question_noise.tidy(head)) or head, session, skill)
    return question, address, None if skill else (body.raw_question or (question + tail if tail else None))


_BARE_NAME = re.compile(r"^(?:(?:what|who)(?:'s| is| was) |tell me about |about )?(?P<name>[a-z][a-z-]{2,})\??$", re.I)


def _names_a_note_word(session: Session, question: str, detected: str) -> bool:
    """"What is Atlas" and a bare "atlas" are a lookup when a note holds the
    word, not a question about the assistant that shares the name (audit 1030
    Z50): the notebook comes first."""
    if detected not in (intent.ABOUT_APP, intent.SMALLTALK) or _social_line(question):
        return False
    found = _BARE_NAME.match(" ".join((question or "").split()))
    return bool(found and _in_notes(session)(found.group("name").lower()))


def _social_line(question: str) -> bool:
    """A ping, keys pressed at random or a social turn ("test", "hi test
    test", "r u an ai??", "not what I asked"): never a lookup, a count or
    a search, even when a note holds its words (INBOX 1485)."""
    return intent.is_test(question) or intent.is_mash(question) or bool(question_noise.social_kind(question))


def _notes_first(session: Session, question: str, detected: str) -> str:
    """The intent, but NOTES for a lookup of a word a note holds and for a
    checklist's state ("what's unpacked", "what have I ticked off"), which is
    never general knowledge."""
    return intent.NOTES if _names_a_note_word(session, question, detected) or composer_slots.asks_state(question) else detected


def _address(question: str, session: Session, skill: dict | None) -> tuple:
    """The question and a name in address position (a `vocative.Address`,
    or None), taken off before anything reads the question, so "brotato
    what's on today" searches for today, not for brotato, and "yo
    brotatockiibidyrizzler" is a call, never a search. A skill's question
    is its own."""
    #: Keys pressed at random are not a nickname for the assistant.
    #: "thxxx" is "thx", never a nickname "Thxxx" (INBOX 1459).
    plain = question_noise.destretch(question)
    address = None if skill or intent.is_mash(question) or intent.is_test(question) else vocative.split(plain, in_notes=_in_notes(session))
    if address is None or not address.names:
        return question, None
    #: A bare word that a note holds is that note's name, not a call.
    if address.call and _in_notes(session)(address.names[0].lower()):
        return question, None
    #: A slipped word at the end of a command is the command's, not a name:
    #: "pin the dentist noe" lost "noe" as a nickname and pinned nothing (O3).
    now = user_now(deps.get_config())
    if acts.parse(question, now) is not None and acts.parse(address.question, now) is None:
        return question, None
    return address.question, address


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
    if body.peek:
        body.answer_from = "notes"
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
        _stop_when_gone(req, private_turn.stepped(_answer_lines(req), body.private)),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


async def _stop_when_gone(req, lines):  # noqa: ANN001
    """The turn's lines, with the browser's Stop (or a closed tab) made the
    model's Stop (audit 1028 E3). Starlette cancels this generator when the
    client goes; the abort used to end only the HTTP response, so the model
    kept generating to the end and the next question queued behind it. The
    cancel sets the turn's stop flag, which cuts the upstream request
    (`activity.stop_aware`); the sync generator is closed once its current
    step returns, so its `finally` blocks run."""
    source = iter(lines)
    done = object()

    def step():  # noqa: ANN202
        return next(source, done)

    try:
        while True:
            task = asyncio.ensure_future(run_in_threadpool(step))
            try:
                line = await asyncio.shield(task)
            except asyncio.CancelledError:
                req.stop.set()
                task.add_done_callback(lambda t: (t.cancelled() or t.exception(), _close_quietly(source)))
                raise
            if line is done:
                return
            yield line
    finally:
        req.stop.set()


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
    if private_turn.active():
        return "Private chat"
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
    now = user_now(deps.get_config()).replace(tzinfo=None)
    said = slash.answer(req.session, req.body.question or "", now, typed_only=typed_only)
    if said is None:
        return None
    events = [{"type": "answer", "delta": said}]
    typed = slash.parse(req.body.question or "")
    drawn = _slash_chart(req.session, typed[0]) if typed else None
    if drawn is not None:
        events.append({"type": "chart", "chart": drawn})
    strip = slash.timeline(req.session, typed[0], typed[1], now) if typed else None
    if strip is not None:
        events.append(strip)
    panel = reply_panel(typed[0], typed[1]) if typed else None
    return _composed_lines(req, events + ([panel] if panel else []))


def _slash_chart(session: Session, name: str) -> dict | None:
    """/categories and /tags draw the bar the same question asked in words
    does (`_stats_chart`; INBOX 1333 b: "/categories" was one prose line)."""
    from tessellate.ai import realise, slash_more

    if name == "categories":
        pairs = slash_more.category_counts(session)[0]
    elif name == "tags":
        pairs = slash_more.tag_counts(session).most_common(15)
    else:
        return None
    by = _STATS_BY[name]
    rows = [{"name": str(label), "notes": int(n)} for label, n in pairs]
    return realise.chart(f"Notes per {by}", by, rows) if realise.form_of(rows) == "chart" else None


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
    """The agent-tool catalog for Settings, Tools toggles."""
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

    name: str = Field(max_length=bounds.LABEL_MAX)
    arguments: dict = Field(default_factory=dict, max_length=100)
    #: A `{"tool": "batch", "steps": [...]}` undo (a change to several notes or
    #: board items): each step is `{"tool", "arguments"}` of a registry tool.
    #: Posted as name "batch" it used to answer 404, so such a change had an
    #: Undo button that could never undo.
    steps: list[dict] = Field(default_factory=list, max_length=bounds.BATCH_STEPS_MAX)


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
    result = tools.execute_tool(session, body.name, body.arguments)
    if "error" in result:
        _refuse_failed(body.name, result)
    #: Named fields only, never the whole result: a tool's result can carry
    #: text written for the model, and CodeQL (#552, #553) follows any
    #: whole-result return to the exception text. The Confirm card reads
    #: `label`; `undo` lets a confirmed change be taken back.
    return {"label": str(result.get("label") or ""), "undo": result.get("undo")}


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
