"""Ask a question, get back BOTH a conversational answer and the raw
matching entries: the two-result design from the original idea doc.

Two flavours:
- POST /chat: one blocking JSON response (simple, used by tests/API)
- POST /chat/stream: NDJSON: metadata + raw results first, then the
  model's thinking and answer as live token deltas (what the UI uses)

Plain `def` so the blocking LLM call runs in FastAPI's threadpool.

**Where the pieces are (audit AR3, gods-1101).** This file keeps the routes,
the two flows above and what tests patch here (`user_now`, `_prepare`,
`_retrieve_for`) or read here. The helpers it calls were moved out whole and
are re-exported here; each imports only the layers before it in this list,
never this file: `chat_attach` (the attachments), `chat_request` (the request),
`chat_pool` (the note pool), `chat_recent` (the suggestion rows), `chat_web`
(the web), `chat_agent` (the agent's turn), `chat_said` (the composed answer's
lines), `chat_turn` (the streamed turn).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import Iterator
from dataclasses import replace as with_changes
from datetime import date
from itertools import chain

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from tessellate.ai import address, composer_retry, fact_check, composer, composer_social, composer_unplaced, note_language, composer_aware, composer_compose, composer_digest, composer_digest_sentences, composer_suggest, composer_tone, composer_web, composer_lists, find_it, glossary, list_pool, note_rank, note_recency, personal, verdicts, vocative
from tessellate.ai import ask_chips, composer_dialogue, composer_empty, composer_intent, composer_links, composer_smalltalk, composer_talk
from tessellate.ai import consent, consent_store, recognise
from tessellate.ai import (
    acts,
    context,
    followups,
    intent,
    librarian,
    notebook_stats,
    presets,
    question_noise,
    skills,
    source_check,
    starter_acts,
    tool_fallback,
    tools,
    validate,
)
from tessellate.ai.answer_trim import trim_assistant_padding
from tessellate.ai.grounding import (
    ground_answer_sentences,
    support as grounding_support,
)
from tessellate.ai.ollama_client import OllamaError
from tessellate.api import chat_chips, chat_extra, chat_pick, chat_web
from tessellate.core import activity, deps, jobs, model_gate, private_turn
from tessellate.core.database import (
    AuditLog,
    Entry,
)
from tessellate.core.config import user_now
from tessellate.core.deps import get_session
from tessellate.repo import categories as categories_repo
from tessellate.core.logbuffer import safe_value
from tessellate.entry import manager, private_space
from tessellate.entry.manager import UNCATEGORISED
from tessellate.search import chunks as search_chunks
from tessellate.search import search_manager
from sqlalchemy import func
from tessellate.api.chat_attach import _MEDIA_REF, _attached_boards, _attached_documents, _attached_files, _attached_media_files, _attached_notes, _files_on, _grounding_candidates, _note_dates, _time_words
from tessellate.api.chat_request import ChatRequest, ChatResponse, CommandRunBody, CompressBody, FollowupBody, RememberBody, ToolExecuteBody, _StreamRequest, _Turn, take_up_offer, _apply_open, _apply_scope, _chat_model_sees_images, _check_refs, _composed, _event, _image_caption_context, _in_full, _meta_event, _nothing_open, _resolve_chat_images, _resolve_mode, _resolve_persona, _resolve_skill
from tessellate.api.chat_pool import _Found, _NoteCtx, _chat_payload, _composer_reads, _document_row, _frame_matches, _glossary, _holds_read_text, _in_window, _keep_window, _note_content, _or_empty_notebook, _records_beside, _slips_put_right, _whole_pool, _widened, _with_each_side, _with_holders, _with_neighbours, _with_records, _window_documents, _with_sources
from tessellate.api.chat_recent import AGENT_SURFACE, ASK_SURFACE, STARTER_SUGGESTIONS, _about, _asked_key, _feature_for, _fill, _recent_questions
from tessellate.api.chat_web import WEB_PAGES, _can_start_searxng, _torn_events, _home_place, _link_events, _offer_events, _search_service, _unmatched_recents, _web_allowed, _web_chip, _web_first, _web_page_row, _web_pref_on
from tessellate.api.chat_agent import _agent_events, consent_events, run_card_events, _close_quietly, _first_agent_event, _refuse_failed, _refuse_if_off, _starter_read
from tessellate.api.chat_said import MODEL_STOPPED_NOTE, _capability_answer, _miss_events, acts_on_listed_task, _says_cannot, _ROWS_KEPT, _app_answers, _asked_before, _asks_capability, _asks_only_a_time, _awareness, _chart_line, _cited_titles, _composed_lines, _current_notes, _older_dates, _diagram_events, _engine_counts, _engine_stands, _filed_or_counted_events, _first_cited_has_list, _held_reply, _help_events, _in_notes, _late_panel, _linked_notes, _listed_below, _model_said, _name_documents, _newest_titles, _newest_word, _open_note_answer, _ping_offer, _related_elsewhere, _related_sentence, _remember_rows, _reminder_window, _reply_seed, _row_source, _rows_key, _run_title, _said_events, _save_ask_turn, _saved_joke_reply, _search_footer, _sees, _slash_chart, _stats_chart, _stats_listed, _suggest_events, _with_words_only, reply_panel
from tessellate.api.chat_turn import _composed_support, _frame_events, _not_again, _with_frame, _asks_change, _chat_reply, _checks_grounding, _cited_scope, _composes_offline, _detect_intent, _engine_answers, _facts_turn, _insight_level, _insight_memory, _is_composing, _log_question, _may_digest, _meaning_loading, model_chips, _model_stream_events, _note_with_hint, _notes_first, _notes_messages, _relay_events, _searched_question, _social_line, _trim_answer, _uncut, _verdicts, _why, _will_answer


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


def _worked_out(question: str):
    """**Worked out, like a count** (CHAT_PLAN decision 41): a sum, a
    conversion, the time. Its sentence is exact and needs no model, so it
    travels the counted answer's road: no retrieval, said as it is.
    Translating and writing (`utilities.GENERATIVE_VERBS`) are a model's job
    when one runs: those are chat."""
    from tessellate.ai import utilities

    kind = utilities.kind_of(question)
    if kind == "weather" and (deps.get_ollama().is_running() or utilities.web_on()):
        #: "The weather is not something this app knows" is the answer only with
        #: no model and no web; with either, the turn is a general question and
        #: goes to them (the owner, 2026-10-27: a weather follow-up came back
        #: from the composer with a model up and Web on).
        return intent.NOTES, None
    worked = None
    if kind not in ("translate", "generate") or not deps.get_ollama().is_running():
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
    from tessellate.ai import activity, activity_new, review_digest

    now = user_now(deps.get_config())
    return review_digest.answer(question, session, now) or activity.answer(question, session, now=now) or activity.boards(question, session, now) or activity_new.answer(question, session, now)


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
    stats = notebook_stats.answer_chat(question, session, as_of) if detected == intent.NOTES else None
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
    if not asked.window:
        return
    if asked.kind == "recall" or (not found.entries and not asked.terms and asked.window_phrase):
        _in_window(found, session, asked, question)
    elif found.entries:
        _keep_window(found, asked)


def _search_notes(session: Session, question: str, found: _Found, attached: list, as_of, locale: str | None, composed: bool = False, widen: int = 0) -> None:  # noqa: ANN001
    #: Searched with the person's own abbreviations spelt out ("what's due in
    #: CC" also finds the notes that say Cloud Computing, B7).
    found.meaning_loading, found.meaning_off = _meaning_loading(), _meaning_off()
    question = composer_intent.without_event_window(_slips_put_right(question))
    hit = search_manager.retrieve_detailed(
        session, glossary.expand(question, _glossary(session)), deps.get_embeddings(), limit=search_manager.widened_limit(widen),
        locale=locale, unscoped=widen > 0,
    )
    #: "The latest notes about running", "my last 2 notes": the notes the
    #: request counted, not those widened by what the subject sounds like.
    counted = note_recency.recency(question, bare=len(question.split()) <= 3)
    #: The composer's own pool only where the composer answers (decision 75): a model reads the search's.
    if counted is not None and not (composed and _composer_reads(question)) and (counted.subject or counted.said_count or hit.mode == "recent"):
        found.entries = list(hit.entries)
    else:
        entries = _with_neighbours(session, question, _widened(session, question, hit.entries, scope=hit.category), scope=hit.category)
        entries = _with_holders(session, question, _with_records(session, question, _with_each_side(session, question, entries, locale), locale), locale)
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


def _retrieve_for(session: Session, question: str, found: _Found, attached: list, attached_notes_only: bool, as_of, locale: str | None, composed: bool = False, held: bool = False, widen: int = 0) -> None:  # noqa: ANN001
    # `attached_notes_only`: the caller has already chosen the exact, closed set
    # of notes this turn should see; retrieval on top would only add notes
    # nobody asked for, matched against whatever the turn's own instruction
    # text happens to contain. Only when there is something attached to fall
    # back to, or an empty list would search nothing and answer from silence.
    if found.stats is not None:
        # Nothing to retrieve: the answer is a count, and five notes about
        # whatever the question sounded like would only be noise beside it.
        found.mode = "stats"
    elif intent.needs_retrieval(found.detected) and not (attached_notes_only and (attached or held)):
        _search_notes(session, question, found, attached, as_of, locale, composed, widen)
    elif attached_notes_only and attached and as_of is None and not composer_digest_sentences.about_this(question):
        found.entries = _records_beside(session, question, attached, locale)


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


def _placed(dates) -> dict | None:  # noqa: ANN001
    """The first date a note's text names, as the timeline's feed places the note
    (`routes_timeline._place_notes`: the lowest-id mention), or None."""
    first = next(iter(dates), None)
    if first is None:
        return None
    return {"on": first.at.date().isoformat(), "phrase": first.phrase, "precision": first.precision}


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
        "category": ctx.category_names.get(entry.category_id, manager.UNCATEGORISED),
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
        #: The day the timeline files it under when that is not the day it was written
        #: (the first date its text names; INBOX 1739), so an answer says both days.
        "placed": _placed(ctx.time_words.get(entry.id, [])),
        #: Its tags and the files on it, which the model never saw (INBOX 594,
        #: the owner: "it only mentions one of the sketches not all the
        #: sketches").
        "tags": manager.entry_tags(entry),
        "files": ctx.files_on.get(entry.id, []),
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
        manager.bulk_category_names(session, found.entries),
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


def _retrieve_ranked(session: Session, question: str, found: "_Found", attached: list, attached_notes_only: bool, as_of: "date | None", locale: str | None, composed: bool = False, held: bool = False, widen: int = 0) -> None:
    _retrieve_for(session, question, found, attached, attached_notes_only, as_of, locale, composed, held, widen)
    _rewind_as_of(session, question, found, as_of, locale)
    #: One ranker for every shape (audit 1029 C19): the note the subject
    #: names, then the one that defines it, then the rest as retrieved.
    if as_of is None and found.mode != "recent":
        found.entries = note_rank.lead(found.entries, question)
    stray = composed and composer_links.strays(question, found.entries, found.connected_ids)
    found.entries = [e for e in found.entries if e.id not in stray] if stray else found.entries
    #: A chat opened inside an open private space reads its sealed notes too (INBOX 1727).
    if intent.needs_retrieval(found.detected) and found.stats is None:
        found.entries += private_space.chat_notes(session, question, have={e.id for e in found.entries})


def _prepare(
    session: Session,
    question: str,
    note_ids: list[int] | None = None,
    force_notes_intent: bool = False,
    attached_notes_only: bool = False,
    document_ids: list[int] | None = None,
    file_ids: list[int] | None = None, media_file_ids: list[int] | None = None,
    board_ids: list[int] | None = None,
    surface: str = ASK_SURFACE,
    as_of: "date | None" = None,
    locale: str | None = None,
    skip_search: bool = False,
    composed: bool = False, widen: int = 0,  # widen: Ask again reads more notes (E62, decision 75)
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
    attached_files = _attached_files(session, file_ids or []) + _attached_media_files(session, media_file_ids or [])
    attached_boards = _attached_boards(session, board_ids or [])
    detected = _detect_intent(question, force_notes_intent, attached, attached_docs, attached_files, attached_boards)
    detected = _notes_first(session, question, detected)
    detected, stats = _computed_answer(session, question, detected, as_of, attached)
    found = _Found(detected=detected, stats=stats)
    #: `skip_search`: the app's own reader has already answered this turn (a
    #: plan, a countdown, a quiz), so the search and the hydration of every
    #: hit (0.1 to 1 s on 300 notes) are not paid for an answer that ignores them.
    if not skip_search:
        _retrieve_ranked(session, question, found, attached, attached_notes_only, as_of, locale, composed, bool(attached_docs or attached_boards), widen)
    notes = _context_notes(session, found, attached, attached_docs, attached_files, attached_boards, as_of)
    #: Only the notes: a document or a file row has another table's id.
    _frame_matches(session, question, notes[: len(found.entries)], found.match_info, found.mode)
    if not (attached or attached_docs or attached_files or attached_boards or skip_search) and found.stats is None and as_of is None:
        notes = _with_sources(session, question, notes, found.mode) + _window_documents(session, found)
    config = deps.get_config()

    _log_question(session, found, question, surface)
    return _chat_payload(session, found, notes, config, as_of)


@router.post("", response_model=ChatResponse)
@private_turn.route
def chat(body: ChatRequest, session: Session = Depends(get_session)) -> ChatResponse:
    _check_refs(session, body)
    _apply_scope(session, body)
    _apply_open(session, body)
    if _composes_offline(body):
        return _composed_chat(body, session)
    prepared = _prepare(
        session,
        body.question,
        body.note_ids,
        attached_notes_only=body.attached_notes_only,
        document_ids=body.document_ids,
        file_ids=body.file_ids, media_file_ids=body.media_file_ids,
        board_ids=body.board_ids,
        # This endpoint has no tool loop, it retrieves and answers, nothing
        # else: so every turn through it is an ask by construction.
        surface=ASK_SURFACE,
        # Row 23: the same time travel the stream takes.
        as_of=body.as_of,
        locale=body.locale, widen=body.attempt,
    )
    #: This surface's own model, if one is set (model_manager.FEATURES).
    #: A view over the same manager, so everything downstream, the agent
    #: loop included, goes on asking for `chat_model()` and gets this
    #: surface's answer without knowing features exist.
    model_manager = deps.get_model_manager().for_feature(_feature_for(body))
    ollama = deps.get_ollama()
    ollama_running = ollama.is_running()
    #: Captioned once: the capability check below reuses these rather than asking the model again.
    seen = _chat_images(session, body, model_manager, ollama)
    if (plain := _capability_response(body, session, prepared, ollama_running, seen)) is not None:
        return plain
    conversational = not intent.needs_retrieval(prepared["intent"])
    mode = _resolve_mode(body.mode)
    images_raw, images, image_context = seen
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
    ai_response, ai_thinking = _chat_reply(
        body, prepared, model_manager, ollama, mode, images, image_context, shared, conversational
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


def _chat_images(session: Session, body: ChatRequest, model_manager, ollama) -> tuple[list, list[str], str]:  # noqa: ANN001
    """The attached pictures, those the chat model sees itself, and the
    captions written for a model that cannot see them."""
    images_raw = _resolve_chat_images(session, body.image_media_ids)
    chat_sees_images = bool(images_raw) and _chat_model_sees_images(model_manager, ollama)
    images = [uri for _, uri in images_raw] if chat_sees_images else []
    image_context = "" if chat_sees_images else _image_caption_context(images_raw, model_manager, ollama)
    return images_raw, images, image_context


def _composed_chat(body: ChatRequest, session: Session) -> ChatResponse:
    """The non-streaming answer when no model runs: the stream's own turn (the
    composer, the counted answers, the slash commands), read to its end, under
    a line that says why. It used to be an apology over the matching notes
    while the same question in the Chat tab got a composed answer (audit 1031
    AI6)."""
    req = _stream_request(body, session)
    #: This route has no tool loop, so every turn through it is an ask: logged
    #: on the Ask surface, which is what "Ask again" reads back.
    req.use_tools = False
    lead = librarian.offline_message(req.ollama)
    cause = (
        "The AI did not answer in time, so this comes from your notes alone."
        if lead == librarian.BUSY_MESSAGE
        else "The AI is not running, so this comes from your notes alone."
    )
    meta: dict = {}
    text: list[str] = []
    commanded = _guarded_slash_lines(req)
    for line in commanded if commanded is not None else _stream_lines(req):
        event = json.loads(line)
        if event.get("type") == "meta":
            meta = event
        elif event.get("type") == "answer":
            text.append(event.get("delta") or "")
    skip = ("ai_response", "answered_by", "ollama_running", "raw_results", "search_mode")
    fields = {k: meta[k] for k in ChatResponse.model_fields if k in meta and k not in skip}
    return ChatResponse(
        ai_response=f"{cause}\n\n{''.join(text)}".strip(),
        raw_results=meta.get("raw_results") or [],
        search_mode=meta.get("search_mode") or "keyword",
        ollama_running=False,
        **fields,
    )


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


def _composer_voice() -> str:
    """The composer's own register for the same choice: it has two, so
    Playful joins with Natural's words and Plain with Professional's."""
    return {"playful": "natural", "plain": "professional"}.get(_answer_voice(), _answer_voice())


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
    if chat_chips.shows_first(composed):
        today = user_now(deps.get_config()).date()
        composed["frame"] = composer_dialogue.turn_frame(req.question, composed, prepared["notes"], today)
        prepared["preview"] = {
            "type": "composed_preview",
            "text": composed["text"],
            "grounding": composed["grounding"],
            #: The same chips as the no-model answer (F5): the frame's questions, none repeated.
            "next": chat_chips.continue_chips(composed, req.question or "", req.history, prepared["notes"], today, _composer_voice(), _says_cannot),
        }
    if packed and packed["shortened"]:
        prepared["model_notes"] = packed["notes"]
        prepared["brief"] = {
            "before": packed["chars_before"] // context.CHARS_PER_TOKEN,
            "after": packed["chars_after"] // context.CHARS_PER_TOKEN,
        }


#: One shared deadline for reading the hits, so three slow pages cost about
#: this and not three times a page's own timeout (audit 1030 A4: 14.7 s).
WEB_PAGES_DEADLINE = 6.0


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

    futures = [jobs.future("web page", read, hit) for hit in hits]
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


def _notes_answer_due(req: _StreamRequest, tool: str, result: object, notes: list | None) -> bool:
    """A "what is due" question with nothing waiting in Reminders and a day
    ahead in the notes: the notes' computed answer wins over "You have no
    reminders waiting" (CHAT_PLAN Phase 6 P13; measured 2026-10-18)."""
    if tool != "list_reminders" or composer_lists.computed_kind(req.question or "") not in ("dates", "due_for") or not isinstance(result, dict):
        return False
    if any(not r.get("done") for r in result.get("reminders") or []):
        return False
    return composer_lists.holds_days(notes or [], user_now(deps.get_config()).date())


def _reminder_window_args(tool: str, asked: str, now, drawn):  # noqa: ANN001
    """`(say args, drawn)`: only a question that says "reminders" is cut to its window; "what is due this week" lists what waits (1324)."""
    within = _reminder_window(asked, now) if tool == "list_reminders" and "remind" in asked.lower() else None
    return ({"within": within}, None) if within else ({}, drawn)


def _tool_read_events(req: _StreamRequest, notes: list | None = None) -> list[dict]:
    """A read tool run with no model (decision 59, steps 1 and 2): the reading
    names the tool (`reading.tool_of`), Chat runs it with no arguments, and
    the realiser says it in one line and draws it in its form. Empty when the
    sentence names no such tool, so the composer answers as before."""
    from tessellate.ai import act_registry, composer_slots, question_noise, reading, realise, tool_say
    from tessellate.ai import tools as agent_tools

    now = user_now(deps.get_config())
    #: Read as repaired: "shwo me evry tag i hav plz" is the tag list, as
    #: "list my tags" is (the routing gold, `fixtures/composer/routing_1011.json`).
    asked = question_noise.repair(question_noise.tidy(req.question or ""))
    early = _filed_or_counted_events(req, asked, now)
    if early:
        return early
    got = reading.read(asked, now=now, context={"birthday": b} if (b := str(deps.get_config().get_preference("birthday", "") or "")) else None)
    if got.tool not in act_registry.NO_MODEL_READS or got.intent in act_registry.ACTS or composer_slots.asks_state(asked):
        return []  # "which tasks are done" is a checklist's state (E21), never the reminders list
    result = agent_tools.execute_tool(req.session, got.tool, {})
    if _notes_answer_due(req, got.tool, result, notes):
        return []
    drawn = realise.tool_answer(got.tool, result, now.date())
    #: Said with its links to what it lists and the place to open
    #: (`tool_say`); a chart, when the counts make one, stands for the table.
    say_args, drawn = _reminder_window_args(got.tool, asked, now, drawn)
    said = tool_say.say(got.tool, result, say_args, now.date())
    chart = drawn["chart"] if drawn else None
    #: A window's rows are the count the engine said ("You have 2 reminders
    #: this week", or none), not the whole list's total.
    counts = fact_check.said_counts(said["lead"]) if "within" in say_args else fact_check.result_counts(got.tool, result)
    out = _said_events(said["lead"], "\n\n".join(p for p in ("" if chart else said["body"], said["chips"]) if p), counts)
    if chart:
        out.append({"type": "chart", "chart": chart})
    return out


def _capability_response(body: ChatRequest, session: Session, prepared: dict, ollama_running: bool, seen: tuple) -> ChatResponse | None:
    if prepared["intent"] != intent.ABOUT_APP:  # the only intent `_asks_capability` accepts: no request to build for the rest
        return None
    answer = _capability_answer(req, ollama_running, _composer_voice()) if _asks_capability(req := _stream_request(body, session, seen), prepared) else None
    return answer and ChatResponse(ai_response=answer, raw_results=[], search_mode=prepared["search_mode"], ollama_running=ollama_running)


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
    if not (welcome := _welcome(req, seed, recent)):
        return ""
    sees = composer_aware.opening(_awareness(req), seed) if req.body.screen else ""
    #: The welcome already names the last note: no second sentence about it.
    invite = "" if "“" in welcome or "](#/notes/" in welcome else _newest_word(req.session)
    asks = composer_smalltalk.invitation(req.question, invite, _composer_voice(), seed) if invite else composer_smalltalk.greeting_ask(req.question, _composer_voice(), seed)
    how = composer_smalltalk.hello_how(req.question, _composer_voice(), [welcome, *recent], seed)
    welcome = address.greet(welcome, address.name_of(deps.get_config()), req.history)  # first hello only (G7)
    return "\n\n".join(p for p in (" ".join(p for p in (welcome, how or asks) if p), sees) if p)


def _social_reply(req: _StreamRequest, prepared: dict) -> str:
    """The app's own reply to small talk (INBOX 741), never echoing the last
    three replies (the owner: "can it have more varied responses??")."""
    recent, seed = _reply_seed(req)
    last = (req.history or [{}])[-1] if req.history else {}
    #: A next step names only a subject whose notes were found: the turn
    #: before named notes (its `objects`), never "nothing matched" (INBOX 1459).
    asked = str(last.get("question") or "") if last.get("objects") else ""
    kind = composer_smalltalk.social_kind(req.question, prepared["intent"])
    if kind in ("greeting", "morning") and (hello := _hello_reply(req, seed, recent)):
        return hello
    if composer_social.missed(req.question, kind, last):
        return _repair_reply(req, last, seed)
    if kind == "joke" and (joke := _saved_joke_reply(req, seed)):
        return joke
    said = composer_smalltalk.social(
        composer_social.heard(req.question, kind, last),
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
    sees = _sees(req, kind, seed)
    return f"{said}\n\n{sees}" if sees else said


def _repair_reply(req: _StreamRequest, last: dict, seed: str) -> str:
    """"Not what I asked" (INBOX 1485): the miss owned, what the ask before was
    read as, and its better reading (Atlas on itself). Never a search."""
    last = composer_social.repaired_turn(req.history or [], last)
    asked = str(last.get("question") or "")
    better = personal.about_me(asked) or ""
    if not better and question_noise.social_kind(asked) == "who":
        better = composer_smalltalk.social(asked, intent.SMALLTALK, voice=_chat_voice(req), seed=seed)
    return composer_social.repair(asked, last, better, _composer_voice(), seed)


def _call_events(req: _StreamRequest) -> list[dict]:
    """A message that only called the assistant: here, and three things to
    ask next as chips (an "ask" offer; the follow-up strip draws them)."""
    recent, seed = _reply_seed(req)
    line = composer_smalltalk.call(req.address.names, recent=recent, seed=seed, voice=_composer_voice())
    return [
        {"type": "answer", "delta": line},
        {"type": "offer", "offer": {"kind": "ask", "label": "", "asks": composer_smalltalk.call_asks(seed)}},
    ]


def _app_said(req: _StreamRequest, prepared: dict, ollama_running: bool) -> list[dict] | None:
    """What the app says itself when it answers (`_app_answers`): about Atlas
    ("do you have feelings", the owner, 2026-10-11), a capability, a call, a
    place ("where is the bin?", `ai/find_it.py`, with a link that opens it),
    or that nothing is open."""
    itself = chat_extra.talk_events(req.session, req.body.question or "", req.history or [], _reply_seed(req)[1], req.question or "", _composer_voice())
    if itself:
        return itself
    if _asks_capability(req, prepared):
        return [{"type": "answer", "delta": _capability_answer(req, ollama_running, _composer_voice())}]
    if req.address is not None and req.address.call:
        return _call_events(req)
    placed = find_it.answer(req.question or "") if not req.images_raw else None
    if placed is not None:
        return [{"type": "answer", "delta": placed["text"]}, {"type": "offer", "offer": placed["offer"]}]
    if _nothing_open(req.body):
        return [{"type": "answer", "delta": composer_digest_sentences.PHRASES["nothing_open"]}]
    return None


def _stats_events(stats: dict, question: str = "") -> list[dict]:
    """A counted answer, its chart, its panel, and its one acting offer
    (decision 70), drawn as a link on its line."""
    out = [{"type": "answer", "delta": stats["text"] + _listed_below(stats)}]
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
    if figured := chat_extra.figures_events(req.session, req.body.question or "", req.history or [], user_now(deps.get_config()).date(), (req.body.open_note_id, *req.body.note_ids)):
        return figured  # F6: a sum or a comparison over what the last answer showed, with a model up or not
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

    from tessellate.ai.tools._common import _visible
    from tessellate.core.database import Entry

    first, last = req.session.query(func.min(Entry.created_at), func.max(Entry.created_at)).filter(*_visible()).one()
    return composer_empty.empty_window(
        planned.window_phrase,
        first.date() if first else None,
        last.date() if last else None,
        voice=_composer_voice(),
        seed=req.question or "",
        register=_chat_voice(req),
        window=planned.window,
    )


def _with_older(text: str, older: list, result: dict) -> str:
    """The answer, and one line on what an older note said, when the answer
    came from the notes and one was set aside (never silently dropped)."""
    from tessellate.ai import supersede

    if not older or not result.get("grounding"):
        return text
    line = supersede.older_line(older, voice=_composer_voice(), today=user_now(deps.get_config()).date(), seed=len(text))
    #: "It's your only note on that so far" is not true with an older one.
    kept = [part for part in text.split("\n\n") if not composer_digest_sentences.is_only_claim(part)]
    return "\n\n".join([*kept, line])


def _changed_line(req: _StreamRequest, text: str, current: list, result: dict) -> str:
    """"Has the launch date changed": the answer is whether two notes disagree on the day, ahead of the notes themselves."""
    from tessellate.ai import supersede

    said = supersede.changed(req.question or "", current, user_now(deps.get_config()).date()) if result.get("grounding") else ""
    return said or text


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
                _capability_answer(req, ollama_running, _composer_voice()) if _asks_capability(req, prepared) else "",
                composer_aware.model_context(_awareness(req)) if req.body.screen else "", chat_extra.remark_facts(req.session, req.question or ""),  # remark parity, INBOX 1749
            )
            if part
        ),
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


def _unplaced_events(req: _StreamRequest) -> list[dict]:
    """A message nothing placed, with no note to answer it (INBOX 1490): a
    short question back, with the notes and the web as its two chips, never a
    web search the person did not ask for."""
    web_on = _web_pref_on()
    said = composer_unplaced.clarify(req.question or "", web_on=web_on, voice=_composer_voice(), seed=_reply_seed(req)[1])
    asks = composer_unplaced.chips(req.question or "", web_on=web_on, previous=composer_talk.stumped_asks(req.session, req.history, user_now(deps.get_config()).date()))
    return [{"type": "answer", "delta": said}, {"type": "offer", "offer": {"kind": "ask", "label": "", "asks": asks}}]


def _no_notes_events(req: _StreamRequest, ollama_running: bool, prepared: dict) -> list:
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
    return _no_notes_answer(req, ollama_running, prepared) + _web_chip(req)


def _no_notes_answer(req: _StreamRequest, ollama_running: bool, prepared: dict) -> list:
    """The line for a question no note answers, and what else the notebook holds on it."""
    events: list = _miss_events(req, ollama_running, prepared, _or_empty_notebook(req.session, _no_notes_line(req, ollama_running)))
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
    ask = lambda pool: composer.offered(composer_digest.answer(  # noqa: E731
        follow.question if restated else req.question, pool, today=today,
        #: A retry rewords the answer (INBOX 1466) and, over one note, reads the others (L93).
        voice=_answer_voice(), turn=len(req.history or []) + req.body.attempt,
        insight=_insight_level(), learned=_insight_memory(req.session), known=_verdicts(req.session),
    ), req.question)
    try:
        return composer_retry.retried(ask(current), current, ask, req.body.attempt)
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


def _compose_for(req: _StreamRequest, prepared: dict, follow, current: list, today) -> dict:  # noqa: ANN001
    """The composed answer; with a model running it picks among numbered readings (decision 45)."""
    one = lambda pool: _compose_over(req, prepared, follow, pool, today)  # noqa: E731
    return chat_pick.settle(req, one(current), current, one)


def _compose_over(req: _StreamRequest, prepared: dict, follow, current: list, today) -> dict:  # noqa: ANN001
    #: The conversation's turn and salt word this answer; a retry rewords it and earlier words are not reused (decisions 34, 35).
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
        resolved=True, retry=attempt,
        #: Insights the person confirmed are said as their word; the
        #: ones they dismissed are not said (decision 60).
        learned=_insight_memory(req.session),
    )


def _composed_result(req: _StreamRequest, prepared: dict) -> tuple:
    """The composer's result with the follow-up it answered, the notes it read
    and the older ones those replaced."""
    follow = prepared.get("follow_on")
    #: A follow-on that is a question in its own right ("and last month?") is answered like the first turn (B8); "tell me more" and corrections keep the composer's.
    restated = follow is not None and follow.kind in composer_dialogue._RESTATES
    today = user_now(deps.get_config()).date()
    #: O11: a newer note on the same thing is the current one.
    current, older = _current_notes(req, prepared["notes"])
    answer = lambda f, r: _open_note_answer(req, f, current, today) or _digest_for(req, prepared, f, current, r, today) or _compose_for(req, prepared, f, current, today)  # noqa: E731
    result, follow = _not_again(answer, follow, restated, req)
    _with_frame(result, follow, req, current, today)
    if follow is not None and follow.kind == "more" and not result.get("grounding"):
        #: Nothing left unsaid: say so, with how much there is (B8).
        result = composer_digest.all_said(follow.question, prepared["notes"], today=today, voice=_answer_voice()) or result
    if follow is None and result.get("grounding"):
        _remember_rows(req.question, current, today, result)
    #: A question the answer suggests ("ask me “...”") is a chip too (INBOX 1497).
    suggested = ask_chips.lift(str(result.get("text") or ""))
    if suggested:
        result["next"] = list(dict.fromkeys([*suggested, *(result.get("next") or [])]))
    result["next"] = chat_chips.continue_chips(result, req.question or "", req.history, current, today, _composer_voice(), _says_cannot)
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


def _with_next_step(text: str, size: str, req: _StreamRequest, cited: list[str] | None = None, listed: bool = True) -> tuple[str, list[str]]:
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
        req.tip = aware
        return text, []
    if not named:
        return text, []
    #: Its heading, not a whole first line ("Project Atlas budget: Sam says ..."): a chip is short.
    name = named[0] if len(named[0]) <= 40 else named[0].split(": ", 1)[0].strip()
    return text, [f"Open \u201c{name}\u201d", *([f"What is left in \u201c{name}\u201d?"] if listed else [])]


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
    text = _with_older(text, _older_dates(req, current, result, older), result)
    text = _changed_line(req, text, current, result)
    text = _with_words_only(text, prepared, result, req.session)
    text = _with_lapsed(text, current, result, req)
    events: list = [*chat_web.nothing_found_meta(prepared, missed), {"type": "answer", "delta": text}, *(_web_chip(req) if missed else []), *req.tip_events(), *_frame_events(result)]
    #: Every question the finished text suggests is a chip (INBOX 1497); one
    #: the grounding event already carries is not said twice.
    suggested = [q for q in ask_chips.lift(f"{text}\n{req.tip}") if q not in (result.get("next") or []) and q not in asks]
    if result["grounding"]:
        _name_documents(req.session, result["grounding"])
        events.append(_composed_grounding_event(req, result, [*asks, *suggested]))
        #: The notes linked to the ones it cited: the related row (INBOX 1466).
        related = _linked_notes(req.session, result)
        if related:
            events.append({"type": "related", "items": related})
    elif suggested or asks:
        events.append({"type": "offer", "offer": {"kind": "ask", "label": "", "asks": [*asks, *suggested][:4]}})
    return events


def _composed_text(req: _StreamRequest, prepared: dict, result: dict, follow, *, missed: bool, said_none: bool) -> tuple[str, list[str]]:  # noqa: ANN001
    """The composed text and the asks that close it (`_with_next_step`)."""
    text = result["text"]
    asks: list[str] = []
    #: "what is this" is the open note, whatever it holds (audit 1031 C11), never the world.
    if missed and not follow and personal.general(req.question or "") and not composer_digest_sentences.about_this(req.question or ""):
        #: "what's the capital of France": the world, not the notes, and
        #: said so rather than "nothing in your notes about capital".
        text = personal.general_reply(
            _web_allowed(req), web_pref=_web_pref_on(), by_choice=req.body.answer_from == "notes" and req.ollama.is_running())
    if missed:
        text += _search_footer(prepared, result)
    size = composer_tone.length(_resolve_mode(req.body.mode))
    if not follow and ((result["grounding"] and not said_none) or (said_none and req.body.screen)):
        text, asks = _with_next_step(composer_tone.fit(text, size), size, req, _cited_titles(req.session, result), _first_cited_has_list(req.session, result))
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
        return [chat_web.NOT_NOTES, *_web_events(*web)]
    if req.web_down:
        return [chat_web.NOT_NOTES, *_offer_events(composer_web.search_down(req.web_down, *_search_service(), can_start=_can_start_searxng()))]
    return None



def _early_events(req: _StreamRequest, prepared: dict, ollama_running: bool) -> list | None:
    """The events for what is answered before any note is read: a diagram, the
    web when no note answers, banter."""
    bare = not ollama_running and not req.images_raw
    if bare and (drawn := _diagram_events(req, prepared)) is not None:
        return drawn
    #: A question the chart route draws ("chart my notes by category") is not
    #: a search for the word "chart": the line says what the chart shows, so
    #: the two halves agree (audit 1031 AI7). Only when a chart is asked for
    #: by name: a plain count ("how many notes about soup") is the counted
    #: answer's.
    charted = _chart_line(req) if _app_answers(req, ollama_running) and not req.images_raw else ""
    if charted:
        return [{"type": "answer", "delta": charted}]
    if _web_first(req, prepared) and bare and _web_allowed(req):
        #: No note answers, no model runs, and web search is on: the web's
        #: own sentences, cited by address (decision 37).
        down = _web_events_or_down(req, req.question)
        if down:
            return down
    if bare and composer_unplaced.jibe(req.question or ""):
        #: A jibe is banter even when a note holds the word "mum" (audit 1031 C21).
        return _unplaced_events(req)
    return _torn_events(req, prepared) if bare else None


def _no_model_events(req: _StreamRequest, prepared: dict, ollama_running: bool) -> list | None:
    """The events for a notes question the app answers itself (web, nothing
    found, or composed), or None when a model streams the answer."""
    if (early := _early_events(req, prepared, ollama_running)) is not None:
        return early
    if not prepared["notes"] and not req.images_raw:
        return _no_notes_events(req, ollama_running, prepared)
    if _composed(req, ollama_running) or not ollama_running:
        return _composed_events(req, prepared, ollama_running)
    return None


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


def _act_events(req: _StreamRequest, prepared: dict) -> Iterator[dict]:
    """An act with no model (CHAT_PLAN decision 38), through the act registry
    (`ai/acts.py`, decision 53): the line that says what it does, then its
    card. Every act waits for Confirm or a typed yes (`POST /chat/command/run`). An
    object that is not one note is asked about, never guessed. Ask is a
    client too: it names the act it read and says where it is done."""
    from tessellate.ai import act_registry

    parsed = {"intent": "new_note", "content": req.offer_note} if req.offer_note else acts.parse(req.question, user_now(deps.get_config()), req.history)
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
    if parsed["intent"] == "reminder" and not parsed.get("time_given") and not parsed.get("on_list"):
        #: Asked once, never guessed as tomorrow at 9 (decision 50); the
        #: reply's time fills it (`reading._follow_slot`).
        from tessellate.ai import commands

        yield {"type": "answer", "delta": commands.ask_when_for(parsed)}
        return
    yield from _act_planned_events(req, parsed)


def _act_planned_events(req: _StreamRequest, parsed: dict) -> Iterator[dict]:
    """The preview of a parsed act: the line and the card that waits for Confirm
    or a typed yes (`ai/consent.py`); no act runs before one."""
    planned = acts.preview(req.session, parsed, req.body.note_ids)
    card = planned.get("card")
    #: The steps come first and fold up as the answer starts, the order a
    #: model's run shows (owner, 2026-10-12: the steps sat under the result).
    if planned.get("tool") and not card:
        yield planned["tool"]
    #: How Confirm words the run, as the composer would have said it (kept on the server with the card).
    mood = composer_compose.mood_of(req.question or "", voice=_chat_voice(req), seed=_reply_seed(req)[1], intent="act")
    say = {"mood": mood, "intent": parsed["intent"]}
    if card and req.offer_yes and not planned.get("duplicate"):
        #: A bare yes to an offer (a chip, "Shall I remind you ...?"): the offer was the proposal
        #: and the yes is the consent, so it runs now with Undo and no second card.
        for event in run_card_events(req.session, card["label"], card["steps"], card["skipped"], say):
            yield event
        return
    yield {"type": "answer", "delta": planned["line"]}
    if card:
        yield {**card, "_say": say}
    elif planned.get("navigate"):
        yield {"type": "navigate", "surface": planned["navigate"], **({"minutes": planned.get("minutes"), "tab": planned["tab"]} if planned.get("tab") else {})}


def _forced_notes(req: _StreamRequest, follow: object) -> bool:
    """A turn that is about the notebook whatever its words read as: a reply
    to the agent's question, a follow-up, and, in Ask, "list my work notes"
    (an act in Chat, the question it is here: the listing is the answer,
    CHAT_PLAN Phase 6 P12)."""
    if req.body.answering_agent or follow is not None:
        return True
    if not req.body.notes_only:
        return False
    if composer_lists.computed_kind(req.question) is not None or composer_digest_sentences.shows_the_lot(req.question):
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
    now, entry = user_now(deps.get_config()), found[0]
    return composer_this.answer(req.question, entry.content or "", *composer_this.local(now, entry.created_at, entry.edited_at), now.date())


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
        prepared.update(app_first=True, read_by=starter_acts.step(starter[0]))
        return _starter_events(req, starter)
    return _plain_events(req, prepared, ollama_running)


def _starter_events(req: _StreamRequest, starter: tuple[str, dict]) -> Iterator[dict]:
    """The starter's answer line, then its act card (`ai/starter_acts.py`)."""
    kind, slots = starter
    yield from starter_acts.events(
        req.session, kind, slots, user_now(deps.get_config()), req.body.note_ids, req.history,
        document_ids=req.body.document_ids, board_ids=req.body.board_ids,
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
    and its grounding), or the reminders' (`chat_extra.reminder_events`), or none
    (`composer_digest.exact`)."""
    current, _older = _current_notes(req, notes) if notes else (notes, [])
    result = composer_digest.exact(req.question or "", current, today=user_now(deps.get_config()).date()) if notes else None
    if not result:
        return chat_extra.facts_events(req.session, req.question or "", now=user_now(deps.get_config()).replace(tzinfo=None), chat=not req.body.notes_only, voice=_composer_voice()) or []
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


def _follow_up(req: _StreamRequest):
    """The follow-up the turn before gives this one: a spoken act stands in
    for the question itself; a composed turn's "tell me more" is
    `composer.follow_on`'s; None otherwise."""
    if acts_on_listed_task(req.question, req.history, user_now(deps.get_config())):
        return None  # "tick the first one" is the act on the task the list showed (R9-9), not a follow-on to rewrite
    composed = ((req.body.notes_only and req.body.answer_from == "notes") or not req.ollama.is_running()) and not (req.body.as_of and composer_dialogue.said_plainly(req.question))  # as of a day, "what did I write" is that notebook
    more = composer.follow_on(req.question, req.history) if composed else None
    if more is not None and more.kind == "more":
        #: A composed "tell me more" is the turn before again at more length,
        #: not a search for the note it cited: since every answer's links
        #: name its objects (audit 1030 Z53), "more" after a summary was
        #: rewritten to "tell me more about the Lecture 5 note" and searched.
        return more
    if take_up_offer(req):
        return None
    spoken = _spoken_act(req) if req.history and not req.ollama.is_running() else None
    if spoken is not None:
        req.question = spoken
        return None
    return composer.follow_on(req.question, req.history) if composed else None


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
    charted = None if req.skill or req.images_raw or req.body.note_ids or req.body.document_ids else composer_talk.chart_ask(req.session, req.body.question or "", req.history or [], user_now(deps.get_config()).date())
    early = charted or _app_first_events(req, follow, req.ollama.is_running())
    scoped = _cited_scope(req, follow)
    prepared = _prepare(
        req.session,
        _searched_question(req, follow),
        scoped or req.body.note_ids,
        force_notes_intent=_forced_notes(req, follow),
        attached_notes_only=bool(scoped) or req.body.attached_notes_only,
        document_ids=req.body.document_ids,
        file_ids=req.body.file_ids, media_file_ids=req.body.media_file_ids,
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
        composed=_app_answers(req, req.ollama.is_running()), widen=req.body.attempt,
    )
    prepared.update(follow_on=follow, early_events=early, charted=charted is not None)  # charted: chart_ask's reason
    return prepared


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


def _prime_model_notes(req: _StreamRequest, prepared: dict, t: _Turn) -> None:
    if t.will_answer and not t.tools_only:
        _assist(req, prepared)
    if t.will_answer:
        #: B31, B32: the model reads the notes with the person's verdicts
        #: written in, as context; grounding reads them as they are.
        known = _verdicts(req.session)
        if known:
            prepared["model_notes"] = verdicts.for_model(prepared.get("model_notes", prepared["notes"]), known)


def _choose_events(req: _StreamRequest, prepared: dict, t: _Turn) -> tuple:
    """The turn's event source, and the notice to send first (or None).

    Small talk never goes near the agent: "hey" is not a request to do
    anything, and handing it a toolbox invites it to invent an errand."""
    if (named := chat_extra.name_events(req.session, req.question or "")) is not None:
        return iter(named), None  # the person's name, model up or not (G7)
    if t.facts:
        return _fact_events(req, prepared, t), None
    events = _first_events(req, prepared, t.ollama_running, t.tools_only)
    can_agent = (
        not t.composed
        and not prepared.get("tool_read") and not prepared.get("charted")
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
    yield from map(_event, model_chips(req.session, t, grounding))
    if req.body.notes_only and t.answer_text and not req.body.peek and not private_turn.active():
        _save_ask_turn(req.session, _in_full(req), t.answer_text, prepared, grounding, composed=t.written_by_app)
    #: A model that wrote a counted answer's words still gets its panel
    #: (INBOX 1300 C06; decision 75: the panel assists, the model leads).
    yield from map(_event, _late_panel(prepared, req.question, t.answer_text, t.sent_kinds))
    if t.answer_text:
        t.marks["done"] = time.perf_counter() - t.started
        yield _event({"type": "why", "lines": _why(req, prepared, grounding, t.composing, t.will_answer, t.tools_only, t.ollama_running, t.shape, t.marks, t.answer_text)})
    yield _event({"type": "done"})


def _stream_lines(req: _StreamRequest) -> Iterator[str]:
    # Flush a first byte immediately. The semantic search below can be a
    # slow cold start (loading the embedding model, warming the index);
    # emitting this now means the browser's stream opens right away and
    # its "typing…" indicator keeps animating instead of looking frozen
    # while the whole request blocks (user-reported lag).
    yield _event({"type": "status", "stage": "searching"})
    started = time.perf_counter()
    #: A typed yes or no to the card that waits, model on or off: nothing else reads it (`ai/consent.py`).
    if (found := consent.read(req.body.question or "", req.history)) is not None:
        for event in consent_events(req.session, found):
            yield _event(event)
        yield _event({"type": "done"})
        return
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


def _asked(body: ChatRequest, session: Session, skill: dict | None) -> tuple:
    """The question the app reads, the name it was addressed by, and the whole
    of a question the app only read the start of (else None).

    Cleaned before anything reads it (INBOX 801): a stray backslash, a run of
    spaces, a sentence typed in capitals (`question_noise.tidy`). Everything
    that routes, searches or plans reads its first `composer_intent.PLAN_CHARS`
    characters (those passes cost words x length: 38 s for a 20,000-character
    paste); the model is given all of it (`_in_full`)."""
    head, tail = body.question[: composer_intent.PLAN_CHARS], body.question[composer_intent.PLAN_CHARS :]
    #: Filler ("errrmmm. hi") is read past before anything reads it (INBOX 1485).
    question, address = _address(skill["question"] if skill else question_noise.media_kind(question_noise.new_notes_as_newest(question_noise.drop_filler(question_noise.tidy(head)))) or head, session, skill)
    question = recognise.spell_asked_days(question, user_now(deps.get_config()).date(), body.locale, not skill)  # W8 B18
    return question, address, None if skill else (body.raw_question or (question + tail if tail else None))


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


def _stream_request(body: ChatRequest, session: Session, seen: tuple | None = None) -> _StreamRequest:
    """What one chat turn settles before it answers: the same for the stream and
    for the non-streaming route when no model runs."""
    ollama = deps.get_ollama()
    #: This surface's own model, if one is set (model_manager.FEATURES).
    #: A view over the same manager, so everything downstream, the agent
    #: loop included, goes on asking for `chat_model()` and gets this
    #: surface's answer without knowing features exist.
    model_manager = deps.get_model_manager().for_feature(_feature_for(body))
    history = [turn.model_dump(exclude_none=True) for turn in body.history]
    persona_prompt = _resolve_persona(body.persona, session)
    mode = _resolve_mode(body.mode)
    images_raw, images, image_context = seen or _chat_images(session, body, model_manager, ollama)
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
    question = question if skill else chat_extra.slot_reply(session, question, history)
    allowed_tools = skill["tools"] if skill else None
    if skill and skill["acts"]:
        # An action skill without tools is just a paragraph, so the route
        # insists whatever the caller asked for. The frontend now switches the
        # mode itself before it sends (INBOX 39: it announces the switch and
        # leaves it switched), so in the app this branch no longer changes
        # anything; it stays because the API is public and a caller that posts
        # `use_tools: false` with an action skill still means the skill.
        use_tools = True

    return _StreamRequest(
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
    _check_refs(session, body)
    if body.peek:
        body.answer_from = "notes"
    _apply_scope(session, body)
    _apply_open(session, body)
    req = _stream_request(body, session)

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


def _interactive_lines(req):  # noqa: ANN001, ANN202
    """`_stream_lines`, marked as an interactive model call while it runs, so
    background model work waits between its calls (`core/model_gate.py`,
    ARCH-09). Entered on the first line, left when the stream ends or the
    client goes: a generator closed early still runs its `finally`."""
    #: Listed in Activity while it streams, and Stop there ends it (rule 5).
    label = "Running a skill" if req.skill else "Answering in Chat"
    with model_gate.interactive():
        yield from activity.tracked_stream(
            "generation", label, _lines_for(req), title=_run_title(req), stop_event=req.stop,
            stopped_line=activity.STOPPED_DONE,
        )


def _lines_for(req):  # noqa: ANN001, ANN202
    """A skill with no model is the composer's (O7, `_skill_lines`); every
    other turn is `_stream_lines`."""
    return _skill_lines(req) if req.skill and not req.ollama.is_running() else _stream_lines(req)


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
    if why := consent_store.refusal_for_press(body.consent_id, body.name, body.arguments):  # a press spends the card
        raise HTTPException(status_code=409, detail=why)
    result = tools.execute_tool(session, body.name, body.arguments)
    if "error" in result:
        _refuse_failed(body.name, result)
    #: Named fields only, never the whole result: a tool's result can carry
    #: text written for the model, and CodeQL (#552, #553) follows any
    #: whole-result return to the exception text. The Confirm card reads
    #: `label`; `undo` lets a confirmed change be taken back.
    return consent_store.remember(body.consent_id, {"label": str(result.get("label") or ""), "undo": result.get("undo")})


