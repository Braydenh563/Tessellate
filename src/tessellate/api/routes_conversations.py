"""Saved chats.

The frontend streams answers via /chat/stream, then records the finished
turn here: keeping the streaming path simple and the history durable.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.exceptions import RequestValidationError

from tessellate.api import bounds, paging
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from tessellate.core import deps
from tessellate.core.conversation_text import conversation_matches
from tessellate.core.database import LIKE_ESCAPE, Conversation, like_escape, utcnow
from tessellate.repo import uploads as uploads_repo
from tessellate.core.deps import get_session
from tessellate.ai import consent_store
from tessellate.api.schemas import TurnFrame
from tessellate.ai.grounding import composed_support, support as grounding_support
from tessellate.entry.manager import log_action

router = APIRouter(prefix="/conversations", tags=["conversations"])


class TurnBody(BaseModel):
    #: The same bound as `ChatTurn` (routes_chat.py): a 2 MB answer was stored
    #: in 97 ms by one call (audit AI4), and every later list, export and
    #: search of that chat paid for it.
    question: str = Field(min_length=1, max_length=bounds.TURN_TEXT_MAX)
    answer: str = Field(max_length=bounds.TURN_TEXT_MAX)
    thinking: str | None = Field(default=None, max_length=bounds.TURN_TEXT_MAX)
    # Tool-activity chips shown in the bubble, persisted so they
    # survive a reload instead of vanishing. Each item is {label, ok}.
    tools: list[dict] | None = None
    # The agent's work in the order it happened: thinking, tool calls and
    # prose interleaved, so reopening a chat shows the same step-by-step run
    # the user watched live rather than a flattened summary of it. Kept
    # alongside `answer`/`tools` rather than replacing them, so an older saved
    # chat (and any other client) still renders.
    steps: list[dict] | None = Field(default=None, max_length=200)
    # What this answer cost, as the model reported it. Stored per turn so a
    # conversation can show its running total: "how much context am I
    # carrying?" is only answerable per-message today, which is the wrong
    # granularity: the total is what decides whether to start a new chat.
    tokens: int | None = None
    # The whole metadata line, not just its total: which model answered, how
    # long it took, prompt→output counts, how full the window got, whether
    # those counts were measured or estimated.
    #
    # Reported in IDEAS.md as "chat message metadata disappears on reload".
    # `tokens` above is a sum, which is the right shape for the conversation
    # total and the wrong one for the per-message line, you cannot rebuild
    # "3.9k of 8k, 12 tok/s, llama3.2" from a single integer, so on reload the
    # line simply vanished and the chat looked like it had been answered by
    # nothing in particular.
    #
    # A free-form dict rather than a model with fields: it is written by the
    # provider and read by one function in `app.js`, and pinning its shape here
    # would mean a third place to edit every time a provider learns to report
    # something new. Bounded instead by only ever storing what the client sends
    # back from a `stats` event.
    stats: dict | None = None
    # Wall-clock for the whole turn, measured by the client because it is the
    # only thing that saw all of it: the server reports per-round timings, and
    # an agent turn is several rounds plus the tool calls between them.
    elapsed_ms: int | None = None
    # The "N matching notes" disclosure's own data: the same shape the
    # `/chat/stream` "meta" event already carries. Reported: "semantic
    # search results in chat messages keep disappearing and don't persist" -
    # true on every reload, since none of this was ever saved here at all;
    # it only ever existed for the duration of the live stream render.
    raw_results: list[dict] | None = None
    search_mode: str | None = None
    match_info: dict | None = None
    connected_ids: list[int] | None = None
    # The "Grounded in" chips' own data (ai/grounding.py's per-sentence
    # note_id/sentence pairs). Same unfixed-until-now gap as raw_results
    # above, reported separately: reopening a chat, or just leaving the
    # tab, dropped the sources line because nothing here ever stored it.
    sentence_grounding: list[dict] | None = None
    #: A composed answer's own support as the live stream sent it (digest, shape,
    #: figure, offer), so a reopened chat draws the same foot and notice (INBOX
    #: 1706). Read only when `by.composed`; a model answer's is recounted below.
    support: dict | None = None
    # Which MediaUpload ids this turn actually attached, asked for
    # directly, and load-bearing beyond just redisplaying them on reopen:
    # media_gc.py's orphan scan can only see `/media/…` references inside
    # note, document and whiteboard content, so a sent chat image had no
    # record anywhere that anything still used it. Persisted here so
    # media_gc._referenced_filenames can look conversations up too, instead
    # of "Clean orphaned media" silently deleting a real, sent attachment.
    image_media_ids: list[int] | None = None
    #: Documents this turn attached, a file dropped on the chat that was not
    #: an image is imported into Documents (`POST /documents/import`) rather
    #: than sent as pixels, and until now the message kept no record that it
    #: had happened. Reported as attachments that "arent rendered with the
    #: chat messages… and they arent previewable or quick navigatable to
    #: their stored location in the library or documents": with nothing
    #: stored, there was nothing to render and nowhere to navigate to.
    document_ids: list[int] | None = None
    #: Library files this turn attached, an Attachment row, not a Document
    #: and not a MediaUpload, so it needs its own list for the same reason
    #: `document_ids` does. Without it a reopened conversation showed the
    #: images and documents a question was given and silently dropped the
    #: files, which is the shape this field's two neighbours were both added
    #: to fix.
    file_ids: list[int] | None = None
    #: Library uploads this turn attached (a MediaUpload row: its ids are not an Attachment's, INBOX 1687).
    media_file_ids: list[int] | None = None
    #: Notes clipped to this question with the paperclip. Reported: *"if the
    #: user attaches a note to a chat message how does it show that that note
    #: is attached to that message??"*, it did not, anywhere. The ids were
    #: sent to `/chat/stream`, used to build that one prompt, and thrown away:
    #: the bubble showed plain text, and reopening the conversation showed the
    #: same plain text, so the answer's whole basis was invisible after the
    #: fact. Same fix as images and documents above, one release later.
    note_ids: list[int] | None = None
    #: Mind maps attached to this question. Kept apart from `note_ids` for the
    #: reason the request keeps them apart (a board's text is one heading; the
    #: model reads its outline), and stored so a reloaded chat draws the same
    #: card the send did (INBOX 1460: "Restored chats (reload) render the same").
    board_ids: list[int] | None = Field(default=None, max_length=4)
    #: Which mode actually answered this turn, Ask (read-only) or Request
    #: (tools allowed). Reported directly: a conversation can span mode
    #: switches, and each past message should say what answered it, not what
    #: the live #chat-mode-seg toggle happens to show now (ROADMAP §89.4).
    used_tools: bool | None = None
    #: What the chat's Resume and Edit-step buttons need in order to exist
    #: again after the conversation is reopened. Reported: the buttons "arent
    #: persistent and disappeared when I came back to the chat", because they
    #: were built from the live stream's own variables and nothing wrote the
    #: run's state down. Kept as an opaque dict for the same reason `stats`
    #: and `steps` are: the client owns its shape, and a schema here would
    #: have to be changed in lockstep with a button's options.
    resume: dict | None = None
    #: Which persona wrote this reply, by name. The owner: "if different
    #: personas are used in different chats for the chat messages the avatars
    #: need to persist for what persona was used." A conversation can switch
    #: persona between turns, so this is per reply, the same reasoning as
    #: `used_tools` above: the page draws each bubble's face from it and never
    #: from the live picker. Kept in the messages JSON rather than a column,
    #: because a message is not a row here (`Conversation`'s docstring), so
    #: there is nothing to migrate: a reply saved before this has no key and
    #: reads as the default assistant. Bounded as a name, not a prompt.
    persona: str | None = Field(default=None, max_length=80)
    #: The question whose suggested follow-up this one was, as its words (INBOX
    #: 490: "hyperlinked bread crumbs ... if a suggested follow suggested
    #: question is used"). Words rather than a turn index, because deleting a
    #: turn renumbers every turn after it and an index would then point at the
    #: wrong question; the page walks back to the nearest earlier question
    #: with these words, and a deleted one simply ends the trail there.
    followup_of: str | None = Field(default=None, max_length=4000)
    #: Words for the pictures of the notes this answer drew on, by url, as
    #: the stream's `meta` sent them (INBOX 502, `routes_chat._picture_alts`),
    #: so a reopened chat's thumbnails keep their alt text.
    picture_alts: dict[str, str] | None = Field(default=None, max_length=40)
    #: Their [width, height] (INBOX 526), so a reopened figure holds its space.
    picture_sizes: dict[str, list[int]] | None = Field(default=None, max_length=40)
    #: Who wrote the reply (`{composed, model}`), so a reopened chat draws
    #: the same badge, note card and timing line the live answer did (INBOX 1693).
    by: dict | None = None
    #: The Why this answer trail's lines, kept for the same reload.
    why: list | None = Field(default=None, max_length=40)
    #: Stopped before it finished, and changed the notebook (W1): a reopened
    #: chat says Stopped on the meta line, and Regenerate asks before a
    #: write runs again (audit 1028 E2). Kept only when true.
    stopped: bool | None = None
    wrote: bool | None = None
    #: The act cards the turn showed (Confirm and Cancel, or Undo), so a reopened chat draws them
    #: again instead of an answer that says "Confirm or Cancel below" over nothing. The state is
    #: never saved here, it is read from the server's parked card on the way out (`_act_state`).
    acts: list[dict] | None = None
    #: What the answer showed (`composer_dialogue.turn_frame`) and the notes it named, so a reopened
    #: chat binds "and the other one" as the live one did instead of falling back to the text
    #: reading (O4). Bounded by the same model the live request uses.
    frame: TurnFrame | None = None
    objects: list[Annotated[str, Field(max_length=200)]] | None = Field(default=None, max_length=8)

    @field_validator("acts", mode="before")
    @classmethod
    def _few_acts(cls, value: object) -> object:
        """Cut, never refused: a turn with many cards must still save (`MAX_ACTS`)."""
        return value[:MAX_ACTS] if isinstance(value, list) else value


class RenameBody(BaseModel):
    #: Trimmed before it is measured, so a title of spaces is refused rather than
    #: saved as a blank row in the list (audit 1030 A33).
    title: str = Field(min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def _trimmed(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A title needs at least one character.")
        return value


class PinBody(BaseModel):
    pinned: bool


def _user_message(turn: TurnBody, asked: datetime) -> dict:
    user: dict = {"role": "user", "content": turn.question, "at": asked.isoformat()}
    if turn.image_media_ids:
        user["image_media_ids"] = turn.image_media_ids
    if turn.document_ids:
        user["document_ids"] = turn.document_ids
    if turn.file_ids:
        user["file_ids"] = turn.file_ids
    if turn.media_file_ids:
        user["media_file_ids"] = turn.media_file_ids
    if turn.note_ids:
        user["note_ids"] = turn.note_ids
    if turn.board_ids:
        user["board_ids"] = turn.board_ids
    followup_of = (turn.followup_of or "").strip()
    if followup_of:
        user["followup_of"] = followup_of
    return user


def _saved_support(turn: TurnBody) -> dict:
    """The notice's numbers for a saved turn, always recounted here from the
    sentence rows, never trusted from the client. A composed answer
    (`by.composed`, built only from notes, so never the model-draft warning;
    INBOX 1706) takes `composed_support`'s base-less count; the page's own
    `support` contributes only the digest display keys, type-checked, and can
    never clear `by_model`."""
    if not (turn.by or {}).get("composed"):
        return grounding_support(turn.answer, turn.sentence_grounding)
    saved = composed_support(None, turn.sentence_grounding)
    sent = turn.support if isinstance(turn.support, dict) else {}
    if sent.get("digest") is True:
        saved["digest"] = True
    for key in ("shape", "figure"):
        if isinstance(sent.get(key), str) and len(sent[key]) <= 24:
            saved[key] = sent[key]
    return saved


MAX_ACTS = 6
EXPIRED = "This offer has expired. Ask again to redo it."
_ACT_KEYS = ("type", "label", "notice", "summary", "consent_id", "ask_label", "name")
_OFFER_KINDS = ("note", "checklist", "reminder")


def _saved_offer(offer: object) -> dict | None:
    """A note, checklist or reminder offer as a redraw needs it (words only; what runs is the page's own call)."""
    if not isinstance(offer, dict) or offer.get("kind") not in _OFFER_KINDS:
        return None
    kept: dict = {k: str(offer[k])[:4000] for k in ("kind", "label", "line", "text", "surface") if isinstance(offer.get(k), str)}
    kept["items"] = [str(i)[:400] for i in offer["items"][:60]] if isinstance(offer.get("items"), list) else []
    return kept


def _saved_offer_card(act: dict, card: dict) -> bool:
    """Fill an offer card from its offer; False when the offer is not one to keep."""
    offer = _saved_offer(act.get("offer"))
    if offer is None:
        return False
    card["offer"] = offer
    card["consent_id"] = str((act.get("offer") or {}).get("offer_id") or act.get("consent_id") or "")[:40]
    card["label"] = offer.get("label", "")
    return True


def _saved_act_extras(kind: str, act: dict, card: dict) -> None:
    """The per-kind parts of a card: a confirm's arguments, an act's steps, skipped, undo and done."""
    if kind == "confirm":
        args = act.get("arguments")
        if isinstance(args, dict) and len(json.dumps(args)) <= 20_000:
            card["arguments"] = args
        else:
            card["lost"] = True  # too large to keep: it reads as expired, never as something to press
    if kind != "act":
        return
    for key in ("steps", "skipped", "undo"):
        if isinstance(act.get(key), list) and len(act[key]) <= 60:
            card[key] = [step for step in act[key] if isinstance(step, dict)]
    if act.get("done") is True:
        card["done"] = True


def _saved_acts(acts: list[dict]) -> list[dict]:
    """The cards a turn drew (an act's, an agent's tool confirm, a note offer), cut to what a redraw
    needs: words, what the card showed, the undo it offered, whether it had already run. None of it
    runs anything: Confirm runs what the server parked under `consent_id`, never these."""
    kept = []
    for act in acts[:MAX_ACTS]:
        kind = act.get("type") if isinstance(act, dict) else None
        if kind not in ("act", "confirm", "offer"):
            continue
        card: dict = {k: str(act[k])[:600] for k in _ACT_KEYS if isinstance(act.get(k), str) and act[k]}
        if kind == "offer" and not _saved_offer_card(act, card):
            continue
        _saved_act_extras(kind, act, card)
        kept.append(card)
    return kept


def _act_state(act: dict) -> str:
    """Where a saved card stands now, read from the server: its recorded outcome, else done while it
    ran at once or its press left a result, waiting while the server still holds it, done when it
    was spent elsewhere (a typed yes), else expired. A note offer with no parked id waits until pressed."""
    if act.get("outcome") in ("done", "cancelled", "undone"):
        return act["outcome"]
    if act.get("done"):
        return "done"
    if act.get("lost"):
        return "expired"
    key = act.get("consent_id")
    if consent_store.was_declined(key):
        return "cancelled"
    if consent_store.peek(key):
        return "pending"
    if consent_store.was_spent(key):
        return "done"
    return "pending" if act.get("type") == "offer" and not key else "expired"


def _acts_field(turn: TurnBody) -> dict:
    """`{"acts": [...]}` when the turn drew cards worth keeping, else nothing."""
    acts = _saved_acts(turn.acts) if turn.acts else []
    return {"acts": acts} if acts else {}


def _hydrate_act(message: dict, slot: int, act: dict) -> None:
    act["state"] = _act_state(act)
    act["act_slot"] = slot
    act["notice"] = {"expired": EXPIRED, "undone": "Undone.", "cancelled": "Cancelled: nothing was changed."}.get(act["state"], act.get("notice", ""))
    if act.get("type") == "offer" and isinstance(message.get("support"), dict):
        #: Back in the answer's support, where the page draws the offer from, with its place in `acts`.
        message["support"] = {**message["support"], "offer": {**act["offer"], "offer_id": act.get("consent_id", ""), "state": act["state"], "notice": act["notice"] if act["state"] != "done" else "", "summary": act.get("summary", ""), "act_slot": slot}}
    result = consent_store.result_of(act.get("consent_id")) if act["state"] == "done" and not act.get("outcome") else None
    if result:
        act["summary"] = str(result.get("summary") or result.get("label") or act.get("label") or "")[:600]
        act["undo"] = [step for step in (result.get("undo") or []) if isinstance(step, dict)]


def _hydrate_acts(messages: list[dict]) -> None:
    """Each saved card gets its state, and a pressed one the summary and Undo the server kept; a note offer goes back into the turn's support."""
    for message in messages:
        for slot, act in enumerate(message.get("acts") or []):
            _hydrate_act(message, slot, act)


def _frame_fields(turn: TurnBody) -> dict:
    """What the next turn leans on, kept only when the answer had any (O4)."""
    frame = turn.frame.model_dump() if turn.frame else {}
    return {k: v for k, v in (("frame", frame if any(frame.values()) else None), ("objects", turn.objects)) if v}


def _turn_messages(turn: TurnBody) -> list[dict]:
    # Stamped here, not by the page: the turn is saved when the answer ends,
    # so the answer's time is now and the question's is now minus the
    # wall-clock the client measured for the whole turn (`elapsed_ms`). A page
    # in a wrong-clock browser can then never put a message in the future.
    now = utcnow()
    asked = now - timedelta(milliseconds=max(0, min(turn.elapsed_ms or 0, 86_400_000)))
    assistant = {"role": "assistant", "content": turn.answer, "thinking": turn.thinking, "at": now.isoformat()}
    #: Kept only when the turn has them, so an old reader sees the same message shape.
    assistant.update({k: getattr(turn, k) for k in ("tools", "steps", "resume", "tokens", "stats", "why", "stopped", "wrote") if getattr(turn, k)})
    if turn.elapsed_ms is not None:
        assistant["elapsed_ms"] = turn.elapsed_ms
    if turn.raw_results:
        assistant["raw_results"] = turn.raw_results
        assistant["search_mode"] = turn.search_mode
        assistant["match_info"] = turn.match_info or {}
        assistant["connected_ids"] = turn.connected_ids or []
    if turn.picture_alts:
        assistant["picture_alts"] = {
            url[:300]: str(words)[:160] for url, words in turn.picture_alts.items() if url.startswith("/media/")
        }
    if turn.picture_sizes:
        assistant["picture_sizes"] = {
            url[:300]: [int(n) for n in size[:2]]
            for url, size in turn.picture_sizes.items()
            if url.startswith("/media/") and len(size) >= 2
        }
    if turn.sentence_grounding:
        assistant["sentence_grounding"] = turn.sentence_grounding
        #: How much of the answer the notebook backs, from the one counter
        #: (`grounding.support`) the live stream used, so a reopened chat keeps
        #: the notice it had (CHAT_PLAN Phase 1's last line). Computed here
        #: rather than trusted from the client: the answer and its marks are
        #: both on the turn, and the frontend must not grow a second counter.
        assistant["support"] = _saved_support(turn)
    if turn.used_tools is not None:
        assistant["used_tools"] = turn.used_tools
    persona = (turn.persona or "").strip()
    if persona:
        assistant["persona"] = persona
    assistant.update(_acts_field(turn))
    assistant.update(_frame_fields(turn))
    if turn.by:
        assistant["by"] = {
            "composed": bool(turn.by.get("composed")),
            "model": str(turn.by.get("model") or "")[:120],
        }
    return [_user_message(turn, asked), assistant]


def _summary(conversation: Conversation) -> dict:
    messages = json.loads(conversation.messages)
    first_question = next(
        (m.get("content", "") for m in messages if m.get("role") == "user"), ""
    )
    return {
        "id": conversation.id,
        "title": conversation.title,
        "updated_at": conversation.updated_at.isoformat(),
        "turns": len(messages) // 2,
        "pinned": bool(conversation.pinned),
        # A line of the first question, so the list says what a chat was
        # about when its title doesn't.
        "preview": first_question[:120],
        "tokens": sum(int(m.get("tokens") or 0) for m in messages),
        "archived_at": conversation.archived_at.isoformat() if conversation.archived_at else None,
        # When the chat was last spoken in, for the sessions list: the last
        # message's own stamp, or the row's time for a chat saved before
        # messages carried one.
        "last_at": (messages[-1].get("at") if messages else None) or conversation.updated_at.isoformat(),
    }


def _existing(session: Session, conversation_id: int) -> Conversation:
    return deps.get_or_404(session, Conversation, conversation_id, "That conversation could not be found.")


def _process_committed_media(session: Session, turn: TurnBody) -> None:
    """A sent chat message is one of the three "committed" moments
    core/media_process.py waits for (asked for directly): an image
    attached to the composer and never sent must not trigger OCR/
    captioning/vision-OCR just for having been uploaded. Keyed off
    `image_media_ids` directly (a conversation's own content is a question
    string, not markdown with an inline `/media/…` reference)."""
    from tessellate.core import media_process

    media_process.process_committed_upload_ids(
        session, deps.get_config().data_dir / "media", turn.image_media_ids or []
    )


#: A page of the chat list, not a ceiling on how many chats a notebook may
#: hold. 200 matches `GET /documents` and `GET /entries`, which are read the
#: same way: a caller that wants all of them asks for the next page until
#: `X-Total-Count` is satisfied (`apiPagedList` in documents.js).
CONVERSATIONS_PAGE_SIZE = 200
MAX_CONVERSATIONS_PAGE = 1000

#: How deep a *search* reads before it answers. The SQL filter over-matches
#: (the messages column is JSON, so its keys are text too), so the real
#: matching happens in Python over what SQL returns, and that is a scan: this
#: is the ceiling on it. High enough that a notebook with a few thousand chats
#: searches all of them, low enough that one request cannot read a table of
#: any size into memory.
SEARCH_SCAN_CAP = 5000


@router.get("")
def list_conversations(
    response: Response,
    q: str = "",
    limit: int = Query(default=CONVERSATIONS_PAGE_SIZE, ge=1, le=MAX_CONVERSATIONS_PAGE),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = paging.cursor_param(),
    session: Session = Depends(get_session),
) -> list[dict]:
    """Pinned first, then most recently used, one page at a time.

    `q` searches titles *and* message text: you remember what you asked
    about far more often than what the chat ended up being called, and
    title-only search can't find that.

    **The cap this replaces made old chats unreachable.** It was a flat
    `.limit(200)` with no offset, so the 201st chat could not be opened from
    the sidebar, and could not be found by searching either, because the
    search filtered *after* the limit: the post-filter ran over the 200 most
    recent rows and everything else was never looked at. Same finding as
    INBOX 117 on documents, reminders and media, one list later.

    The id is a tiebreaker in the ordering for the same reason it is there:
    two chats sharing an `updated_at` could otherwise swap places between two
    pages and hide one of them.
    """
    offset = paging.start(cursor, offset)
    term = (q or "").strip()
    # Archived chats are kept, but out of the way, same shape as an
    # archived note dropping out of the Notes tab. Reachable via the
    # Library's Shelved filter (routes_library._shelved), not this list.
    live = Conversation.archived_at.is_(None)
    order = (
        Conversation.pinned.desc(),
        Conversation.updated_at.desc(),
        Conversation.id.desc(),
    )

    if not term:
        total = session.scalar(select(func.count(Conversation.id)).where(live)) or 0
        rows = list(
            session.scalars(
                select(Conversation).where(live).order_by(*order).limit(limit).offset(offset)
            )
        )
        response.headers["X-Total-Count"] = str(total)
        paging.finish(response, offset, limit, total)
        return [_summary(c) for c in rows]

    # A cheap SQL prefilter, which over-matches (JSON keys count as text), so
    # everything it returns is then checked properly in Python. The page is
    # taken *after* that check, never before: slicing first is what made the
    # old version answer "nothing found" for a chat it had simply not read.
    like = f"%{like_escape(term)}%"
    candidates = session.scalars(
        select(Conversation)
        .where(
            live,
            Conversation.title.ilike(like, escape=LIKE_ESCAPE)
            | Conversation.messages.ilike(like, escape=LIKE_ESCAPE),
        )
        .order_by(*order)
        .limit(SEARCH_SCAN_CAP)
    )
    matched = [c for c in candidates if conversation_matches(c, term)]
    response.headers["X-Total-Count"] = str(len(matched))
    paging.finish(response, offset, limit, len(matched))
    return [_summary(c) for c in matched[offset : offset + limit]]


@router.put("/{conversation_id}/pin")
def pin_conversation(
    conversation_id: int, body: PinBody, session: Session = Depends(get_session)
) -> dict:
    conversation = _existing(session, conversation_id)
    # updated_at carries `onupdate=utcnow`, which fires on *any* write to the
    # row: so the obvious `conversation.pinned = …; commit()` also marks the
    # chat as just-used, and unpinning would leave it at the top of the list
    # it was meant to drop back down. Passing the current value explicitly is
    # what suppresses the default: pinning is organising, not using.
    session.execute(
        update(Conversation)
        .where(Conversation.id == conversation.id)
        .values(pinned=body.pinned, updated_at=conversation.updated_at)
    )
    session.commit()
    session.refresh(conversation)
    return _summary(conversation)


@router.put("/{conversation_id}/archive")
def archive_conversation(
    conversation_id: int, session: Session = Depends(get_session)
) -> dict:
    """Kept, but out of the way (BACKLOG §30b's named remaining scope), 
    same shape as `routes_entries.archive_entry`: never deleted, never
    auto-cleared, drops out of the sidebar list and out of the way, still
    reachable from the Library's Shelved filter."""
    conversation = _existing(session, conversation_id)
    if not conversation.archived_at:
        # Same suppression as pinning above: archiving is organising, not
        # using, so `updated_at` must not jump to now.
        session.execute(
            update(Conversation)
            .where(Conversation.id == conversation.id)
            .values(archived_at=utcnow(), updated_at=conversation.updated_at)
        )
        log_action(session, "archived", "conversation", conversation.id)
        session.commit()
        session.refresh(conversation)
    return _summary(conversation)


@router.put("/{conversation_id}/unarchive")
def unarchive_conversation(
    conversation_id: int, session: Session = Depends(get_session)
) -> dict:
    conversation = _existing(session, conversation_id)
    if conversation.archived_at:
        session.execute(
            update(Conversation)
            .where(Conversation.id == conversation.id)
            .values(archived_at=None, updated_at=conversation.updated_at)
        )
        log_action(session, "unarchived", "conversation", conversation.id)
        session.commit()
        session.refresh(conversation)
    return _summary(conversation)


@router.post("", status_code=201)
def create_conversation(body: TurnBody, session: Session = Depends(get_session)) -> dict:
    """First turn of a new chat, the question becomes the title."""
    title = _question_title(body.question)
    conversation = Conversation(
        title=title, messages=json.dumps(_turn_messages(body))
    )
    session.add(conversation)
    session.flush()
    log_action(session, "created", "conversation", conversation.id)
    session.commit()
    _process_committed_media(session, body)
    return _summary(conversation)


def _hydrate_attachments(session: Session, messages: list[dict]) -> None:
    """Turn the stored id lists into something renderable, in place.

    A message stores ids because ids are what survives a rename and what
    `media_gc` needs. A *bubble* needs a thumbnail, a name, and the caption
    and transcription the app already holds for that picture, so the read
    path resolves them here, once for the whole conversation, rather than
    leaving the browser to fire one request per attachment per reopen.

    **Missing is normal and is not an error.** An attachment can be deleted
    from the Library long after the message that carried it; the id then
    resolves to nothing and the bubble simply shows one fewer thumbnail,
    which is what happened before this existed. Nothing here 404s.
    """
    #: In the order a bubble shows them: pictures, documents, files, notes, maps.
    keys = ("image_media_ids", "document_ids", "file_ids", "media_file_ids", "note_ids", "board_ids")
    wanted = {key: {i for m in messages for i in (m.get(key) or [])} for key in keys}
    if not any(wanted.values()):
        return
    notes, maps = _entry_cards(session, wanted["note_ids"], wanted["board_ids"])
    cards = {
        "image_media_ids": _media_cards(session, wanted["image_media_ids"]),
        "document_ids": _document_cards(session, wanted["document_ids"]),
        "file_ids": _file_cards(session, wanted["file_ids"]),
        "media_file_ids": _upload_cards(session, wanted["media_file_ids"]),
        "note_ids": notes,
        "board_ids": maps,
    }
    for message in messages:
        attachments = [cards[key][i] for key in keys for i in (message.get(key) or []) if i in cards[key]]
        if attachments:
            message["attachments"] = attachments


def _media_cards(session: Session, ids: set) -> dict:
    return {
        upload.id: {
            "id": upload.id,
            "kind": "image",
            "url": f"/media/{upload.filename}",
            "name": upload.original_name,
            # The two readings the Library tile shows, so the same
            # picture reads the same way wherever it appears.
            "caption": upload.caption or "",
            "text": (upload.vision_ocr_text or upload.ocr_text or "").strip(),
        }
        for upload in uploads_repo.by_ids(session, ids)
    }


def _document_cards(session: Session, ids: set) -> dict:
    from tessellate.repo import documents

    return {d.id: {"id": d.id, "kind": "diagram" if d.file_type == "mmd" else "document", "name": d.title} for d in documents.by_ids(session, ids)}


def _file_cards(session: Session, ids: set) -> dict:
    from tessellate.core.database import Attachment

    rows = session.query(Attachment).filter(Attachment.id.in_(ids)).all() if ids else []
    return {a.id: {"id": a.id, "kind": "file", "name": a.filename} for a in rows}


def _upload_cards(session: Session, ids: set) -> dict:
    rows = uploads_repo.by_ids(session, ids)
    return {u.id: {"id": u.id, "kind": "file", "store": "media", "name": u.original_name} for u in rows}


def _entry_cards(session: Session, note_ids: set, board_ids: set) -> tuple[dict, dict]:
    """Note and map cards. A binned or private one is treated exactly like a
    deleted upload: the card disappears. Listing a private note's first line
    in a conversation would put it back on screen in the one place the
    private-notebook rule cannot reach. A map is held to the same."""
    from tessellate.core.database import Entry
    from tessellate.entry import manager_text
    from tessellate.entry.properties import strip as strip_properties

    notes: dict = {}
    maps: dict = {}
    ids = note_ids | board_ids
    for entry in session.query(Entry).filter(Entry.id.in_(ids)).all() if ids else []:
        if entry.is_deleted or entry.is_private:
            continue
        if entry.id in note_ids:
            # Notes have no title of their own, so the card says what the
            # note says. The *words* are the page's to make (`noteNamePlain`,
            # which also reads the Markdown), exactly as at send time; here is
            # only the first line after the properties block, uncut (bounded
            # for the wire), so send and reload cannot name one note twice.
            lines = [ln.strip() for ln in strip_properties(entry.content or "").splitlines() if ln.strip()]
            notes[entry.id] = {"id": entry.id, "kind": "note", "name": lines[0][:400] if lines else ""}
        if entry.id in board_ids:
            maps[entry.id] = {"id": entry.id, "kind": "map", "name": manager_text.extract_title(entry.content) or "Mind map"}
    return notes, maps


@router.get("/{conversation_id}")
def get_conversation(
    conversation_id: int, session: Session = Depends(get_session)
) -> dict:
    conversation = _existing(session, conversation_id)
    messages = json.loads(conversation.messages)
    #: Chats saved before the composed rule above kept the model counter's
    #: notice on a notes-only answer; mended on the way out (INBOX 1706).
    for message in messages:
        if (message.get("by") or {}).get("composed") and message.get("sentence_grounding") and (message.get("support") or {}).get("by_model") is not False:
            message["support"] = composed_support(None, message["sentence_grounding"])
    _hydrate_attachments(session, messages)
    _hydrate_acts(messages)
    return {**_summary(conversation), "messages": messages}


@router.post("/{conversation_id}/turns")
def append_turn(
    conversation_id: int, body: TurnBody, session: Session = Depends(get_session)
) -> dict:
    conversation = _existing(session, conversation_id)
    messages = json.loads(conversation.messages)
    messages.extend(_turn_messages(body))
    conversation.messages = json.dumps(messages)
    conversation.updated_at = utcnow()
    session.commit()
    _process_committed_media(session, body)
    return _summary(conversation)


TITLE_PROMPT = (
    "Write a very short title (2 to 5 words) for this conversation. Reply with "
    "the title only: no quotes, no punctuation at the end, no explanation."
)


def _question_title(question: str) -> str:
    """A question as a chat's name: one line, a stray trailing backslash (a
    pasted escape, "what is there about a gaming mouse?\\") dropped, cut at 60."""
    text = " ".join((question or "").split()).rstrip("\\ ")
    return text if len(text) <= 60 else text[:59].rstrip() + "…"


def _clean_title(raw: str) -> str | None:
    text = (raw or "").strip().splitlines()[0] if (raw or "").strip() else ""
    text = text.strip().strip("\"'`*#").rstrip(".!,;:\\").strip()
    if not text or len(text) > 60 or len(text.split()) > 8:
        return None
    # Models frequently reply in lowercase, a title should start capitalised.
    return text[0].upper() + text[1:]


@router.post("/{conversation_id}/retitle")
def retitle_conversation(
    conversation_id: int, session: Session = Depends(get_session)
) -> dict:
    """Name a chat with the local model, falling back to the first question.

    Best-effort by design: if the model is down or answers with something
    unusable, the conversation simply keeps a sensible non-AI title.
    """
    from tessellate.ai import librarian
    from tessellate.core import deps

    conversation = _existing(session, conversation_id)
    messages = json.loads(conversation.messages)
    first_question = next(
        (m["content"] for m in messages if m.get("role") == "user"), ""
    )
    fallback = _question_title(first_question)

    title = None
    ollama = deps.get_ollama()
    if ollama.is_running():
        # A short transcript is plenty to name the thread.
        transcript = "\n".join(
            f"{m.get('role')}: {str(m.get('content'))[:400]}" for m in messages[:4]
        )
        # Name it in the active persona's voice, so titles match the
        # assistant the user actually chose.
        persona = librarian.resolve_persona_prompt(None, deps.get_config())
        system = f"{persona.strip()} {TITLE_PROMPT}" if persona else TITLE_PROMPT
        try:
            reply = ollama.chat(
                deps.get_model_manager().utility_model(),
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": transcript},
                ],
            )
            title = _clean_title(reply.get("content", "") if isinstance(reply, dict) else "")
        except Exception:  # noqa: BLE001  # a failed rename is never fatal
            title = None

    conversation.title = title or fallback or conversation.title
    conversation.updated_at = utcnow()
    session.commit()
    return {**_summary(conversation), "ai_named": bool(title)}


@router.put("/{conversation_id}/turns/last")
def replace_last_turn(
    conversation_id: int, body: TurnBody, session: Session = Depends(get_session)
) -> dict:
    """Regenerate: swap the most recent Q&A pair for a fresh answer, in
    place, instead of appending a duplicate below it (user request)."""
    conversation = _existing(session, conversation_id)
    messages = json.loads(conversation.messages)
    if len(messages) >= 2:
        messages = messages[:-2]  # drop the last user+assistant pair
    messages.extend(_turn_messages(body))
    conversation.messages = json.dumps(messages)
    conversation.updated_at = utcnow()
    session.commit()
    _process_committed_media(session, body)
    return _summary(conversation)


@router.delete("/{conversation_id}/turns/{index}")
def delete_turn(
    conversation_id: int, index: int, session: Session = Depends(get_session)
) -> dict:
    """Remove a single question/answer exchange (a turn) from a saved chat.

    Messages are stored as flat user/assistant pairs, so turn `index` maps to
    messages[2*index : 2*index+2]. Deleting the last remaining turn removes the
    conversation itself, since an empty chat is only clutter.
    """
    conversation = _existing(session, conversation_id)
    messages = json.loads(conversation.messages)
    start = index * 2
    if index < 0 or start >= len(messages):
        raise HTTPException(status_code=404, detail="That turn could not be found.")
    removed = messages[start : start + 2]
    del messages[start : start + 2]
    if not messages:
        # The last turn takes the chat with it, so Undo needs the whole row.
        kept = _restore_row(conversation)
        log_action(session, "deleted", "conversation", conversation.id)
        session.delete(conversation)
        session.commit()
        return {"deleted": True, "conversation_deleted": True, "turns": 0, "restore": kept}
    conversation.messages = json.dumps(messages)
    conversation.updated_at = utcnow()
    session.commit()
    return {**_summary(conversation), "deleted": True, "conversation_deleted": False, "removed": removed}


class TurnRestoreBody(BaseModel):
    messages: list[dict] = Field(min_length=1, max_length=2)


@router.post("/{conversation_id}/turns/{index}/restore")
def restore_turn(
    conversation_id: int, index: int, body: TurnRestoreBody, session: Session = Depends(get_session)
) -> dict:
    """Undo a deleted message (CHAT_PLAN 8 row 5): the pair the turn's DELETE
    answered with, put back at its own index."""
    conversation = _existing(session, conversation_id)
    messages = json.loads(conversation.messages)
    start = index * 2
    if index < 0 or start > len(messages):
        raise HTTPException(status_code=404, detail="That turn could not be put back there.")
    if any(m.get("role") not in ("user", "assistant") for m in body.messages):
        raise HTTPException(status_code=422, detail="Only a question and its answer can be put back.")
    messages[start:start] = body.messages
    conversation.messages = json.dumps(messages)
    conversation.updated_at = utcnow()
    session.commit()
    return _summary(conversation)


class TruncateBody(BaseModel):
    """Drop this turn and everything after it."""

    from_turn: int = Field(ge=0)


@router.post("/{conversation_id}/truncate")
def truncate_conversation(
    conversation_id: int, body: TruncateBody, session: Session = Depends(get_session)
) -> dict:
    """Cut the conversation back to just before `from_turn`.

    This is what editing a question needs: the answers that followed it were
    replies to the old wording, so leaving them would make the thread read as
    though the assistant answered a question nobody asked.
    """
    conversation = _existing(session, conversation_id)
    messages = json.loads(conversation.messages)
    keep = messages[: body.from_turn * 2]
    if len(keep) == len(messages):
        return {**_summary(conversation), "removed": 0}

    removed = (len(messages) - len(keep)) // 2
    #: What Undo sends back (INBOX 898): the cut-off messages, or the whole row
    #: when the cut took the chat with it.
    cut = messages[len(keep):]
    if not keep:
        kept = _restore_row(conversation)
        log_action(session, "deleted", "conversation", conversation.id)
        session.delete(conversation)
        session.commit()
        return {"removed": removed, "conversation_deleted": True, "turns": 0, "restore": kept}

    conversation.messages = json.dumps(keep)
    conversation.updated_at = utcnow()
    session.commit()
    return {**_summary(conversation), "removed": removed, "conversation_deleted": False, "removed_messages": cut}


class TruncateRestoreBody(BaseModel):
    from_turn: int = Field(ge=0)
    messages: list[dict] = Field(min_length=1, max_length=2000)


@router.post("/{conversation_id}/truncate/restore")
def restore_truncated(
    conversation_id: int, body: TruncateRestoreBody, session: Session = Depends(get_session)
) -> dict:
    """Undo of `truncate`: the cut-off messages put back from `from_turn` on (INBOX 898)."""
    conversation = _existing(session, conversation_id)
    messages = json.loads(conversation.messages)
    start = body.from_turn * 2
    if start != len(messages):
        raise HTTPException(status_code=409, detail="That chat has moved on since, so the messages can't go back.")
    if any(m.get("role") not in ("user", "assistant") for m in body.messages):
        raise HTTPException(status_code=422, detail="Only questions and answers can be put back.")
    conversation.messages = json.dumps(messages + body.messages)
    conversation.updated_at = utcnow()
    session.commit()
    return _summary(conversation)


class ForkBody(BaseModel):
    """Where to cut the copy. Omitted means the whole conversation."""

    #: The turn to keep *up to and including*. Same indexing `truncate` uses: 
    #: one turn is a user message and its answer, so the message slice is
    #: `(up_to + 1) * 2`. `None` means "all of it", which is the plain
    #: duplicate case.
    up_to: int | None = Field(default=None, le=bounds.HISTORY_MAX_TURNS * 100)
    title: str | None = Field(default=None, max_length=120)
    #: Words after the chat's own title, "Planning (before the edit)" (audit 1028
    #: E48): the chat client holds no title, so it cannot build one. A `title` wins.
    suffix: str | None = Field(default=None, max_length=40)


@router.post("/{conversation_id}/fork", status_code=201)
def fork_conversation(
    conversation_id: int, body: ForkBody, session: Session = Depends(get_session)
) -> dict:
    """Copy a conversation, optionally only as far as one turn.

    Asked for directly: *"ability to fork conversations"*. The need is the one
    every chat interface eventually grows: a thread reaches a good state and
    you want to try a different direction **without losing the one you have**.
    Today the only way is to keep asking and then delete what you did not
    want, which is destructive and cannot be undone.

    A copy rather than a branch pointer, deliberately. Conversations here are
    one JSON blob per row (see `Conversation`'s own docstring on why that is
    the right size for a single-user app), and a real branch would mean
    turning that into a tree with shared ancestry, a merge story and a
    migration: an enormous amount of machinery so that two threads can share
    the bytes of the first three messages. Copying is O(one chat) of disk and
    behaves exactly as a reader expects: the fork is a normal conversation
    from the moment it exists, and editing it cannot reach back into its
    parent.
    """
    conversation = _existing(session, conversation_id)
    messages = json.loads(conversation.messages)
    if body.up_to is not None:
        if body.up_to >= (len(messages) + 1) // 2:
            #: Past the last turn is not a place to cut (audit AI18: 999 forked
            #: the whole chat and answered 201): the one error shape names it.
            raise RequestValidationError([{"loc": ("body", "up_to"), "msg": "That turn is past the end of this chat.", "type": "value_error"}])
        #: `max(0, …)` rather than refusing a negative: a fork with nothing in
        #: it is a new chat, which is a reasonable thing to have asked for and
        #: a silly thing to return an error about.
        messages = messages[: max(0, (body.up_to + 1) * 2)]
    #: The name says where it came from, because a Library listing two
    #: identically-named chats is the thing that makes forking unusable.
    title = (body.title or "").strip() or f"{conversation.title} ({(body.suffix or '').strip() or 'fork'})"
    fork = Conversation(
        title=title[:120],
        messages=json.dumps(messages),
        workspace_id=conversation.workspace_id,
    )
    session.add(fork)
    session.commit()
    log_action(session, "created", "conversation", fork.id)
    return _summary(fork)


class FollowupsBody(BaseModel):
    """The "what to ask next" chips a finished turn produced."""

    #: Bounded on both axes: these are one row of buttons under an answer, and
    #: a body that arrives with two hundred of them is a bug or an attack, not
    #: a longer list of good questions.
    followups: list[str] = Field(default_factory=list, max_length=6)


@router.put("/{conversation_id}/turns/{index}/followups")
def set_turn_followups(
    conversation_id: int,
    index: int,
    body: FollowupsBody,
    session: Session = Depends(get_session),
) -> dict:
    """Remember the follow-up chips for one turn.

    Reported directly: "suggested repsponse continuation prompts in chat doesnt
    persist and disappears once I switch chat sessions or quit the app." They
    did not persist because nothing ever stored them, they were generated by
    a second model call after the turn was already saved, appended to a live
    DOM node, and that was the whole of their existence.

    Its own endpoint rather than a field on the turn body, because of *when*
    it happens: the turn is written the moment the answer finishes, and the
    suggestions arrive after that, deliberately (they are a second model call
    and must never delay the answer). A turn that has since been deleted is a
    204-shaped no-op, not an error, the reader moved on, which is fine.
    """
    conversation = _existing(session, conversation_id)
    messages = json.loads(conversation.messages)
    position = index * 2 + 1  # the assistant half of the pair
    if position >= len(messages) or messages[position].get("role") != "assistant":
        return {"saved": False}

    cleaned = [text.strip()[:200] for text in body.followups if text.strip()]
    if cleaned:
        messages[position]["followups"] = cleaned
    else:
        messages[position].pop("followups", None)
    # `updated_at` is deliberately held where it was, and holding it takes an
    # explicit assignment, because the column carries `onupdate=utcnow` and
    # would otherwise move on any UPDATE at all. A suggestion the user has not
    # read is not activity: bumping it would reshuffle the chat list under
    # them seconds after they stopped reading, which is exactly the kind of
    # thing that makes a sidebar feel unstable for no reason anyone can see.
    # A Core UPDATE naming both columns, not `conversation.messages = …`.
    # Assigning the same `updated_at` back through the ORM does nothing: it is
    # not a change, so the column is left out of the SET clause and `onupdate`
    # fills it in: which is the behaviour being avoided. `values()` puts it in
    # the statement explicitly, and an explicit value beats `onupdate`.
    session.execute(
        update(Conversation)
        .where(Conversation.id == conversation.id)
        .values(messages=json.dumps(messages), updated_at=conversation.updated_at)
    )
    session.commit()
    return {"saved": True, "followups": cleaned}


class ActOutcomeBody(BaseModel):
    outcome: str = Field(pattern="^(done|cancelled|undone)$")
    #: Which card this is for, checked against the one stored at (turn, slot): the page counts its
    #: bubbles, and a bubble that never saved shifts the count, so the index alone is not trusted.
    consent_id: str = Field(default="", max_length=40)
    label: str = Field(default="", max_length=600)
    #: A note offer's own words (the page made the note; only an offer takes this).
    summary: str = Field(default="", max_length=600)


def _may_become(card: dict, outcome: str) -> bool:
    """The only moves a card makes: done once (a card the server saw pressed; an offer from the page),
    cancelled once while it waits, undone only from done; an offer may be pressed again after its Undo."""
    state = _act_state(card)
    key = card.get("consent_id") or ""
    if outcome == "undone":
        return state == "done"
    if card.get("type") == "offer":
        return outcome == "done" and state in ("pending", "undone")
    if outcome == "cancelled":
        return state == "cancelled" or (state in ("pending", "expired") and not consent_store.was_spent(key))
    return state == "done" and not card.get("outcome") and not card.get("done")


def _apply_outcome(card: dict, body: ActOutcomeBody) -> None:
    """The server-side effect of an outcome: spend the offer's id, keep the result and Undo, or decline the parked card."""
    key = card.get("consent_id") or ""
    if body.outcome == "done" and card.get("type") == "offer":
        consent_store.take(key)
        card["summary"] = body.summary
    elif body.outcome == "done":
        result = consent_store.result_of(key) or {}
        card["summary"] = str(result.get("summary") or result.get("label") or card.get("label") or "")[:600]
        card["undo"] = [step for step in (result.get("undo") or []) if isinstance(step, dict)]
    elif body.outcome == "cancelled":
        consent_store.decline(key)


@router.put("/{conversation_id}/turns/{index}/acts/{n}")
def set_turn_act_outcome(
    conversation_id: int, index: int, n: int, body: ActOutcomeBody, session: Session = Depends(get_session)
) -> dict:
    """Remember how a card of a saved turn was answered, so the chat reopens with it settled.

    Nothing here is taken on the page's word: the card at (turn, slot) must carry the given id and
    label; Done needs the press the server saw (its kept result gives the summary and Undo, a note
    offer's press spends its id); Cancel spends the parked card, so one drawn again cannot run. A turn
    or card that is gone is a no-op. `updated_at` is held, as for follow-ups: a press is not a message."""
    conversation = _existing(session, conversation_id)
    messages = json.loads(conversation.messages)
    position = index * 2 + 1
    acts = messages[position].get("acts") if 0 <= position < len(messages) else None
    if not acts or not 0 <= n < len(acts):
        return {"saved": False}
    card = acts[n]
    if (card.get("consent_id") or "") != body.consent_id or (card.get("label") or "") != body.label:
        raise HTTPException(status_code=409, detail="That is not the card saved there.")
    if card.get("outcome") == body.outcome:
        return {"saved": True, "state": body.outcome}
    if not _may_become(card, body.outcome):
        raise HTTPException(status_code=409, detail="That card was already answered.")
    _apply_outcome(card, body)
    card["outcome"] = body.outcome
    session.execute(
        update(Conversation).where(Conversation.id == conversation.id).values(messages=json.dumps(messages), updated_at=conversation.updated_at)
    )
    session.commit()
    return {"saved": True, "state": body.outcome}


class AnswerBody(BaseModel):
    content: str = Field(min_length=1)


def _rewrite_answer_steps(steps: list[dict] | None, content: str) -> list[dict] | None:
    """Point a saved step timeline at an edited answer.

    `steps` carries its own copy of the prose, and it is the copy the client
    actually renders when reopening a chat, `content` is only used for the
    copy button. So editing `content` alone left the edit invisible the moment
    the chat was reopened: replay redrew the model's original wording and the
    correction looked like it had never been saved.

    The reasoning and tool steps are deliberately left alone. They record what
    the model actually did, which the user's correction doesn't change. Only
    the prose is theirs to rewrite, so the answer steps collapse into the one
    block they typed: the same shape the frontend produces when it edits a
    timeline in place.
    """
    if not steps:
        return steps
    out: list[dict] = []
    written = False
    for step in steps:
        if step.get("kind") != "answer":
            out.append(step)
            continue
        if written:
            continue  # a second prose block would duplicate the correction
        out.append({**step, "text": content})
        written = True
    if not written:
        # A turn whose timeline held only reasoning and tools still needs the
        # edited prose, or replay would render no answer at all.
        out.append({"kind": "answer", "text": content})
    return out


@router.put("/{conversation_id}/turns/{index}/answer")
def edit_answer(
    conversation_id: int,
    index: int,
    body: AnswerBody,
    session: Session = Depends(get_session),
) -> dict:
    """Edit the assistant's text of one turn, keeping everything else.

    Questions have been editable for a while; answers weren't, so the only
    way to fix a model's near-miss was to regenerate and hope. An edited
    answer is marked so the transcript never passes your words off as the
    model's: that distinction is the whole point of keeping a transcript.
    """
    conversation = _existing(session, conversation_id)
    messages = json.loads(conversation.messages)
    position = index * 2 + 1  # user, assistant, user, assistant, …
    if index < 0 or position >= len(messages):
        raise HTTPException(status_code=404, detail="That turn could not be found.")
    messages[position]["content"] = body.content
    messages[position]["edited"] = True
    steps = _rewrite_answer_steps(messages[position].get("steps"), body.content)
    if steps:
        messages[position]["steps"] = steps
    conversation.messages = json.dumps(messages)
    conversation.updated_at = utcnow()
    session.commit()
    return {**_summary(conversation), "edited_turn": index}


@router.put("/{conversation_id}")
def rename_conversation(
    conversation_id: int, body: RenameBody, session: Session = Depends(get_session)
) -> dict:
    conversation = _existing(session, conversation_id)
    conversation.title = body.title
    session.commit()
    return _summary(conversation)


def _restore_row(conversation: Conversation) -> dict:
    """The whole row, for Undo to send back to `POST /conversations/restore`
    (undo-1005): a chat is one row, so this is all of it."""
    def iso(when: datetime | None) -> str | None:
        return when.isoformat() if when else None

    return {
        "id": conversation.id,
        "title": conversation.title,
        "messages": conversation.messages,
        "pinned": bool(conversation.pinned),
        "archived_at": iso(conversation.archived_at),
        "created_at": iso(conversation.created_at),
        "updated_at": iso(conversation.updated_at),
        "workspace_id": conversation.workspace_id,
    }


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: int, session: Session = Depends(get_session)
) -> dict:
    conversation = _existing(session, conversation_id)
    kept = _restore_row(conversation)
    log_action(session, "deleted", "conversation", conversation.id)
    session.delete(conversation)
    session.commit()
    return {"deleted": True, "restore": kept}


class RestoreBody(BaseModel):
    id: int
    title: str = Field(max_length=120)
    messages: str
    pinned: bool = False
    archived_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    workspace_id: str | None = Field(default=None, max_length=60)


@router.post("/restore", status_code=201)
def restore_conversation(body: RestoreBody, session: Session = Depends(get_session)) -> dict:
    """Undo a chat's delete (undo-1005): the row its DELETE answered with,
    under its own id and in its own space. Refused while that id is taken,
    so a second Undo cannot make a copy."""
    try:
        messages = json.loads(body.messages)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="That chat's turns could not be read.") from error
    if not isinstance(messages, list):
        raise HTTPException(status_code=422, detail="That chat's turns could not be read.")
    table = Conversation.__table__
    if session.execute(select(table.c.id).where(table.c.id == body.id)).first():
        raise HTTPException(status_code=409, detail="That conversation is already here.")
    def plain(when: datetime | None) -> datetime | None:
        return when.replace(tzinfo=None) if when else None

    conversation = Conversation(
        id=body.id, title=body.title, messages=body.messages, pinned=body.pinned,
        archived_at=plain(body.archived_at),
        created_at=plain(body.created_at) or utcnow(),
        updated_at=plain(body.updated_at) or utcnow(),
    )
    if body.workspace_id:
        conversation.workspace_id = body.workspace_id
    session.add(conversation)
    session.flush()
    log_action(session, "restored", "conversation", conversation.id)
    session.commit()
    return _summary(conversation)
