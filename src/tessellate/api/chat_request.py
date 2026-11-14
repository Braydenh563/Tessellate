"""A chat request and what is settled before anything is searched: the request
and response models, the scope, the open note, the mode, persona, skill and
plan, the images a model may see, and the stream's own request and turn.

Moved whole from `routes_chat.py` (audit AR3, gods-1101): the code is
unchanged, and `routes_chat` re-exports every name here that anything
reads, so `routes_chat.ChatRequest` still works. Imports run one way, down the
layer list in `routes_chat.py`'s docstring, never back to `routes_chat`.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import re
import threading
from dataclasses import dataclass, field
from datetime import date
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from typing import Annotated, Literal

from tessellate.ai import captioning, composer_digest_sentences, composer_talk, consent, composer_frame, composer_open, librarian, memory, presets, questions, skills, tools, vocative
from tessellate.api import bounds
from tessellate.api.chat_attach import _attached_boards, _attached_documents, _attached_notes
from tessellate.api.schemas import EntryOut, TurnFrame
from tessellate.core import activity, deps
from tessellate.core.database import Category, Entry, like_escape, LIKE_ESCAPE, MediaUpload
from tessellate.repo import categories as categories_repo
from tessellate.search import query as search_query


class RememberBody(BaseModel):
    marker_id: int


class FollowupBody(BaseModel):
    """One answered turn, sent back to ask what to offer next.

    Bounded here rather than only inside `followups` because this arrives over
    HTTP: the client is echoing back a turn the server just produced, but
    nothing makes that true of a hand-made request, and both fields end up in a
    model prompt.
    """

    question: str = Field(default="", max_length=search_query.QUESTION_CAP)
    answer: str = Field(default="", max_length=20000)


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
    #: The notes the answer named, by title, for a spoken follow-on such as
    #: "delete the other one" (`reading.follow`, decision 57). Optional, and
    #: dropped from the dump when absent, so a turn without it is unchanged.
    objects: list[Annotated[str, Field(max_length=200)]] | None = Field(default=None, max_length=8)
    #: The label of an act's card this turn left waiting for Confirm, sent by
    #: the page only while the card is showing, so "cancel" can drop it
    #: (`composer_cancel`, CHAT_PLAN X17).
    pending_act: str | None = Field(default=None, max_length=300)
    #: The frame the answer was sent with, echoed back; absent from an older page.
    frame: TurnFrame | None = None
    #: The id the server parked that card under (`ai/consent_store.py`), sent with it so a typed
    #: yes runs what was proposed. The page never sends back steps or arguments.
    pending_id: str | None = Field(default=None, max_length=40)
    #: The id the server parked the answer's note offer under (Gather them, Track your lifts; `consent.py`),
    #: sent on the last turn while the offer stands, so a typed yes makes that note.
    offer_id: str | None = Field(default=None, max_length=40)

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
        #: A curly apostrophe is read as a straight one by every reader ("I’ve"
        #: is "I've", INBOX 1590: a phone keyboard types the curly one); the
        #: model and the saved turn still get what was typed (`raw_question`).
        scanned = bounds.squeeze_blanks(typed).replace("\u2019", "'") if isinstance(typed, str) else typed
        if isinstance(typed, str) and scanned != typed:
            data = {**data, "question": scanned, "raw_question": typed}
        return data

    #: Answer from the notebook as it stood at the end of this day
    #: (WORLD_CLASS_PLAN I5, row 23). Read, never act: the turn runs without
    #: tools, which would read and change the notebook as it is now.
    as_of: date | None = None
    #: The browser's locale (`navigator.language`), so a bare "3/4" in a
    #: question reads in the asker's date order.
    locale: str | None = Field(default=None, max_length=35)
    # Prior turns for follow-on context (Round 1); the server clips this.
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
    note_ids: list[Annotated[int, Field(ge=1, le=9_223_372_036_854_775_807)]] = Field(default_factory=list, max_length=20)
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
    # Files uploaded in the Library (a `MediaUpload` row, not an `Attachment`).
    # The two tables number their rows separately, so these ids cannot ride in
    # `file_ids` (INBOX 1687). Same cap, same extraction.
    media_file_ids: list[int] = Field(default_factory=list, max_length=4)
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
    #: "questions": answer from the notes that hold a question with no answer yet
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
    #: The document or board in front of the person (`agentOpenSubject`): read
    #: like `open_note_id`, by "Summarise this" only, and ahead of it.
    open_document_id: int | None = None
    open_board_id: int | None = None
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
    #: One id per send (E70, L682): a repeated POST with the same id gets the first turn's
    #: result back instead of a second run (`ai/turn_once.py`). A "Try again" is a new send, so a new id.
    turn_id: str | None = Field(default=None, min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
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


def _check_refs(session: Session, body: ChatRequest) -> None:
    """Refuse a turn that names a mode or a note that does not exist.

    These were accepted in silence (audit AI18): an unknown mode ran as
    `normal` and `note_ids: [999999, -1]` answered from unrelated notes as if
    they had been attached. The shared error shape names the field. An unknown
    persona still falls back to the default, by design (a persona deleted
    while it was selected must not break the chat: test_chat_uses_selected_persona).
    """
    wrong: list[tuple[str, str]] = []
    if body.mode and body.mode not in presets.MODES:
        wrong.append(("mode", f"That mode is not one of {', '.join(presets.MODES)}."))
    if body.note_ids:
        have = set(session.scalars(select(Entry.id).where(Entry.id.in_(body.note_ids))))
        if not have.issuperset(body.note_ids):
            wrong.append(("note_ids", "One of the attached notes does not exist."))
    if wrong:
        raise RequestValidationError([{"loc": ("body", field), "msg": msg, "type": "value_error"} for field, msg in wrong])


def _apply_scope(session: Session, body: ChatRequest) -> None:
    """Turn a scope into the closed set of notes it means.

    With no unanswered question anywhere the turn falls back to ordinary
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
    if body.open_note_id and not body.history and composer_digest_sentences.more_of_this(body.question):
        body.question, body.raw_question = "summarise this", None


def _attached_only(body: ChatRequest) -> None:
    """"What is this about" with a note attached is that note alone, never a
    list of the newest (INBOX 1461)."""
    if not body.scope and composer_digest_sentences.about_this(body.question):
        body.attached_notes_only = True


#: "what is in the Sara note", "what does the Tom note say", "what is Tom's
#: note about", "the note called Sara": a question that names a note by its
#: title (audit 1031 C7). The name is checked against the titles; a phrase that
#: is no note's title ("the shopping note" when none is called that) is left to
#: the search.
_TITLED_ASK = re.compile(r"^(?:what|who|when|where|how|which|why|is|does|did|has|have|tell|show|summari[sz]e|read|explain|describe|give|list|any|anything)\b", re.I)


_NOTE_NAMED = (
    re.compile(r"\b(?:the|my|that) (?P<x>[\w'’&-]+(?: [\w'’&-]+){0,3}?) note\b", re.I),
    re.compile(r"\b(?P<x>[\w&-]+(?: [\w&-]+){0,2}?)['’]s note\b", re.I),
    re.compile(r"\bnote (?:called|titled|named) (?P<x>[\w'’&-]+(?: [\w'’&-]+){0,3})", re.I),
)


_NOT_A_NAME = frozenset({"this", "that", "open", "current", "new", "last", "first", "latest", "newest", "oldest", "same", "other", "whole", "entire", "next", "right", "wrong", "whole"})


def _named_note(session: Session, body: ChatRequest) -> bool:
    """Bind the note the question names by title as the closed set the answer
    reads. Only one note with that title counts; two are left to the search."""
    q = " ".join((body.question or "").split()).rstrip("?.! ")
    if not _TITLED_ASK.match(q):
        return False
    for which, pattern in enumerate(_NOTE_NAMED):
        for found in pattern.finditer(q):
            words = found.group("x").split()
            #: "what is Tom's note": the owner is the words next to "'s".
            names = [" ".join(words[i:]) for i in range(len(words))] if which == 1 else [" ".join(words)]
            for name in names:
                if _titled_note(session, body, re.sub(r"^(?:in|from|of|on|at|for|about|with|to)\s+", "", name.strip(), flags=re.I)):
                    #: "called" is how the note was named, not a word to look for.
                    body.question = re.sub(r"\bnote (?:called|titled|named)\b", "note", body.question, flags=re.I)
                    return True
    return False


def _bind_cited(session: Session, body: ChatRequest, sentence: str) -> str:
    """`sentence`, a follow-on already given its referent ("tell me more about the Plumber note"
    for "tell me more about it"), bound to that note as if it had been typed: the binding above
    reads the words the page sent, which name no note. Returns the sentence."""
    if not body.note_ids:
        typed, body.question = body.question, sentence
        try:
            _named_note(session, body)
        finally:
            body.question = typed
    return sentence


def take_up_offer(req: _StreamRequest) -> bool:
    """A bare "yes" takes up the offer the answer before ended with (B23); "open it" names the note the
    answer cited. True when the yes made the note the server held (Gather them, Track your lifts), which
    needs no reading of the question: its text is `req.offer_note`, made on this yes with Undo."""
    from tessellate.core import config

    held = composer_talk.held_offer(req.question, req.history)
    if held is not None:
        req.offer_note, req.offer_yes, req.question = held, True, f"make a note: {held}"
        return True
    now = config.user_now(deps.get_config())
    offered = composer_talk.accepted_offer(req.question, req.history, now)
    req.offer_yes = offered is not None and consent.says(req.question) == "yes"
    cited = offered or composer_talk.cited_question(req.question, req.history, now)
    if cited is not None:
        req.question = _bind_cited(req.session, req.body, cited)
    return False


def _titled_note(session: Session, body: ChatRequest, name: str) -> bool:
    """Bind the one note titled `name`."""
    if not name or name.lower() in _NOT_A_NAME:
        return False
    rows = session.execute(
        select(Entry).where(Entry.is_deleted == False, Entry.is_private == False, Entry.content.ilike(f"%{like_escape(name)}%", escape=LIKE_ESCAPE))  # noqa: E712
        .order_by(Entry.created_at.desc()).limit(80)
    ).scalars()
    titled = [e for e in rows if composer_frame.note_title(e.content or "").strip().lower() == name.lower()]
    if len(titled) != 1:
        return False
    body.note_ids = [titled[0].id]
    body.attached_notes_only = True
    return True


def _open_surface(session: Session, body: ChatRequest) -> bool:
    """The open document or board is what "Summarise this" means; one that is
    gone (or a private board) falls through to the open note, then category."""
    if body.open_document_id and _attached_documents(session, [body.open_document_id]):
        body.document_ids = [body.open_document_id]
    elif body.open_board_id and _attached_boards(session, [body.open_board_id]):
        body.board_ids = [body.open_board_id]
    else:
        return False
    return True


def _apply_open(session: Session, body: ChatRequest) -> None:
    """"Summarise this" on any tab (CHAT_PLAN B10): the open note, else the
    open category, becomes the closed set the answer reads; "summarise
    Travel" reads that category's notes rather than the few a keyword
    search finds. Notes attached by hand, or a scope, win over both."""
    if body.note_ids or body.document_ids or body.scope:
        _attached_only(body)
        return
    if _named_note(session, body):
        return
    _first_more_is_this(body)
    if composer_digest_sentences.about_this(body.question):
        if _apply_open_this(session, body):
            return
    elif body.open_note_id and composer_open.kind(body.question):
        #: "What's left to do?" with a note open is about that note (the
        #: 22-10 bug doc: Ask gave one reply for every note), unless the
        #: question names something the note does not hold.
        opened = _attached_notes(session, [body.open_note_id])
        if opened and composer_open.reads_note(body.question, {"content": opened[0].content}):
            body.note_ids = [body.open_note_id]
    else:
        names = categories_repo.names(session)
        named = composer_digest_sentences.named_category(body.question, names)
        if named:
            body.note_ids = _category_note_ids(session, named)
    if body.note_ids:
        body.attached_notes_only = True


def _apply_open_this(session: Session, body: ChatRequest) -> bool:
    """"Summarise this": the open document or board alone (True, done), else
    the open note, else the open category."""
    if _open_surface(session, body):
        _attached_only(body)
        return True
    #: A note binned or made private since it was opened is not read;
    #: the open category stands in (`_attached_notes`' own rule).
    if body.open_note_id and _attached_notes(session, [body.open_note_id]):
        body.note_ids = [body.open_note_id]
    elif body.open_category:
        body.note_ids = _category_note_ids(session, body.open_category)
    return False


def _nothing_open(body: ChatRequest) -> bool:
    """"Summarise this" with nothing open: said plainly, not answered with
    the newest notes."""
    return composer_digest_sentences.about_this(body.question) and not (body.note_ids or body.document_ids or body.board_ids)


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
    #: The whole of a question longer than `composer_intent.PLAN_CHARS`, which only the
    #: model and the saved turn read; `question` is what the app plans over.
    full_question: str | None = None
    #: Why the web search could not run this turn ("" when it ran): the
    #: reply then names the service and links its setting (`composer_web`).
    web_down: str = ""
    #: The screen-aware next step ("Shall we carry on with ..."), sent as its
    #: own `tip` event so it is never part of the answer's saved, copied or
    #: spoken text (audit 1028 E52).
    tip: str = ""
    #: A bare yes took up an offer ("Shall I remind you ...?"): the offer was the proposal and the
    #: yes is the consent, so its act runs with no second card (`_follow_up`).
    offer_yes: bool = False
    #: The note a held offer makes (`composer_talk.held_offer`); the yes is its consent.
    offer_note: str = ""

    def tip_events(self) -> list[dict]:
        return [{"type": "tip", "text": self.tip}] if self.tip else []


def _in_full(req: _StreamRequest) -> str:
    """The question as asked, for the model and the saved turn."""
    return req.full_question or req.question


def _composed(req: _StreamRequest, ollama_running: bool) -> bool:
    """Whether this turn's answer is composed from the notes (INBOX 688): an
    Ask-box turn that asked for it, or any Ask-box turn with no model to ask.
    The Chat tab composes too, but only when no model runs (`_plain_events`)."""
    return bool(req.body.notes_only) and (req.body.answer_from == "notes" or not ollama_running)


class CommandRunBody(BaseModel):
    """A confirmed act's steps, or an act's undo steps (decision 38). `consent_id`
    is the card's own id: the steps parked under it run, in the card's words."""

    consent_id: str | None = Field(default=None, max_length=40)
    steps: list[dict] = Field(default_factory=list, max_length=60)
    skipped: list[dict] = Field(default_factory=list, max_length=60)


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
    #: The live notice said no model wrote it (`support.by_model` False): the
    #: saved Ask turn keeps that, so its reopened count matches (W1 A5).
    written_by_app: bool = False
    shape: str | None = None
    sent_kinds: set = field(default_factory=set)
    model_checks: dict | None = None


def _event(payload: dict) -> str:
    return json.dumps(consent.attach(payload)) + "\n"


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


class ToolExecuteBody(BaseModel):
    """A tool call the user approved in the UI (confirm step)."""

    name: str = Field(max_length=bounds.LABEL_MAX)
    arguments: dict = Field(default_factory=dict, max_length=100)
    #: The card's own id (`ai/consent_store.py`): pressing Confirm spends it, so a yes typed after runs nothing twice.
    consent_id: str | None = Field(default=None, max_length=40)
    #: A `{"tool": "batch", "steps": [...]}` undo (a change to several notes or
    #: board items): each step is `{"tool", "arguments"}` of a registry tool.
    #: Posted as name "batch" it used to answer 404, so such a change had an
    #: Undo button that could never undo.
    steps: list[dict] = Field(default_factory=list, max_length=bounds.BATCH_STEPS_MAX)
    #: The server's tag on an Undo or redo it handed out (`consent_store.sign_call`): sent back
    #: unchanged, and a call whose name, arguments or steps no longer match it is refused (L566).
    sig: str | None = Field(default=None, max_length=80)
