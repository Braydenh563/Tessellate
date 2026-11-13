"""The streamed turn: the messages and events of a model's answer, grounding
run live over its words, the relay that folds and trims them, and the facts
of a turn.

Moved whole from `routes_chat.py` (audit AR3, gods-1101): the code is
unchanged, and `routes_chat` re-exports every name here that anything
reads, so `routes_chat._relay_events` still works. Imports run one way, down the
layer list in `routes_chat.py`'s docstring, never back to `routes_chat`.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Iterator
from sqlalchemy import update
from sqlalchemy.orm import Session

from tessellate.ai import composer_digest, composer_lists, composer_slots, composer_talk, context, fence, intent, librarian, question_noise, recognise, verdicts, why
from tessellate.ai import composer_digest_sentences
from tessellate.ai import composer_dialogue
from tessellate.ai.answer_trim import trim_assistant_padding
from tessellate.ai.grounding import SentenceGrounder, composed_support
from tessellate.ai.ollama_client import OllamaError
from tessellate.api import chat_degrade
from tessellate.api.chat_agent import _starter_read
from tessellate.api.chat_pool import _Found
from tessellate.api.chat_extra import _turn_label
from tessellate.api.chat_request import ChatRequest, _StreamRequest, _Turn, _event, _in_full
from tessellate.api.chat_said import _app_answers, _asks_capability, _cited_titles, _first_cited_has_list, _in_notes
from tessellate.core import deps, private_turn
from tessellate.core.config import user_now
from tessellate.core.database import Entry
from datetime import datetime
from tessellate.core.logbuffer import safe_value
from tessellate.entry import manager
from tessellate.repo import visible_notes
from tessellate.search import chunks as search_chunks


def _detect_intent(question: str, force_notes_intent: bool, *attachments: list) -> str:
    detected = intent.classify(question)
    #: "i wanna make a note" is the Guide's how-to for a bare question, but in
    #: the chat it is the act with nothing to say yet, and the reply asks what
    #: the note says (INBOX 1507; INBOX 1649 had taken it as a how-to).
    if detected == intent.ABOUT_APP:
        from tessellate.ai import commands

        bare = commands.read(question, datetime.now())
        if bare and bare.get("intent") in ("new_note", "reminder") and (bare.get("no_subject") or not bare.get("text", bare.get("content"))):
            return intent.ACT
    # `body.answering_agent` (Tier 1 section 4): a reply to the agent's own
    # question is about the notebook by construction, however smalltalk-shaped
    # the reply itself reads ("yes", "ok"). Attaching a note (or a document) is
    # likewise a statement that this is about the notebook, so it overrides the
    # classifier: the client already knows what the request actually is.
    if force_notes_intent or any(attachments):
        return intent.NOTES
    return detected


def _log_question(session: Session, found: "_Found", question: str, surface: str) -> None:
    if private_turn.active():
        #: A private chat is not a use of the notes and not an ask to offer
        #: again; the log line carries no words of it either.
        logging.getLogger("tessellate.chat").info("chat: %d note(s) via %s search (private)", len(found.entries), found.mode)
        return
    # Every entry this question surfaced counts as "used": one UPDATE that names
    # `updated_at`, which stops its `onupdate` moving the note's edit time. Reading a
    # note is not editing it, and everything keyed on the newest edit (the abbreviation
    # glossary: every note re-read per question, 40 to 130 ms) was dropped by the bump.
    used = list(dict.fromkeys(entry.id for entry in found.entries if getattr(entry, "id", None) is not None))
    if used:
        session.execute(
            update(Entry)
            .where(Entry.id.in_(used))
            .values(access_count=Entry.access_count + 1, updated_at=Entry.updated_at)
            .execution_options(synchronize_session=False)
        )
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


def _chat_reply(  # noqa: ANN001
    body: ChatRequest, prepared: dict, model_manager, ollama, mode, images, image_context, shared: dict,
    conversational: bool,
) -> tuple[str, str | None]:
    """The text for `chat`: a counted answer, the Ask box's refusal to chat,
    a conversational reply, or a grounded answer, by state."""
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
    return ai_response, ai_thinking


def _composes_offline(body: ChatRequest) -> bool:
    """A turn about the notes is composed from them when no model runs; a hello
    or a question about the app is not, it keeps the plain offline greeting
    ("No model is no reason to answer a hello with an error": a hello was
    getting "this comes from your notes alone" over a welcome). A turn with
    pictures, or with a model running, goes the model's way."""
    if body.image_media_ids or deps.get_ollama().is_running():
        return False
    kind = _detect_intent(body.question, False, body.note_ids, body.document_ids, body.file_ids, body.media_file_ids, body.board_ids)
    return kind not in (intent.SMALLTALK, intent.ABOUT_APP)


def _insight_level() -> str:
    """How much Atlas volunteers past the answer (CHAT_PLAN decision 73), the
    `insight_level` preference: "off", "one" line (the default) or "all"."""
    try:
        value = deps.get_config().get_preference("insight_level", "one")
    except Exception:  # noqa: BLE001  # no preference is the default
        return "one"
    return value if value in composer_digest.INSIGHT_LEVELS else "one"


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
    if dropped := librarian.history_dropped(req.history, messages):
        #: Exchanges the window left out, for the chat's one-line notice (E57).
        composition_tokens["history_dropped"] = dropped
    if prepared.get("brief"):
        #: The notes' tokens before and after the composer cut them, so the
        #: saving is a number on every turn rather than a claim.
        composition_tokens["notes_brief"] = prepared["brief"]
    streamed_any = False
    said: list[str] = []
    stats = None
    try:
        for piece in req.ollama.chat_stream(req.model_manager.chat_model(), messages, req.mode):
            if "thinking_delta" in piece:
                yield {"type": "thinking", "delta": piece["thinking_delta"]}
            elif "stats" in piece:
                #: Token counts + timings for the message metadata line, held to the end so a fallback can mark them.
                stats = piece["stats"]
            else:
                streamed_any = True
                said.append(piece["content_delta"])
                yield {"type": "answer", "delta": piece["content_delta"]}
        if chat_degrade.falls_back("".join(said), prepared, req.question or ""):
            yield from chat_degrade.fallback_events(prepared, stats, composition_tokens, streamed_any)
        elif stats is not None:
            yield {"type": "stats", **stats, "composition": composition_tokens}
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
        if preview and preview.get("text"):
            #: **The answer composed from the notes survives the model**
            #: (CHAT_PLAN Phase 6, the first tests: a model dying mid-answer
            #: used to leave only the error). The composed answer the page
            #: already drew as a draft is sent as the answer, under one line
            #: saying the model stopped. After some words (L122) it replaces
            #: them (`answer_final`) rather than following half a sentence.
            yield from chat_degrade.fallback_events(prepared, stats, composition_tokens, streamed_any)
            return
        prefix = "\n\n" if streamed_any else ""
        yield {
            "type": "answer",
            "delta": f"{prefix}{librarian.model_error_message(req.model_manager.chat_model(), exc)}",
        }


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


def _may_digest(prepared: dict, question: str) -> bool:
    """The digest answers unless this is a "newest notes" turn, which keeps
    the composer's: but "all the dates in my notes" reads as newest-first
    and is a computed answer (`ai/composer_lists.py`)."""
    return not str(prepared.get("search_mode") or "").endswith("recent") or composer_lists.computed_kind(question) is not None or composer_digest_sentences.shows_the_lot(question)


def _cited_scope(req: _StreamRequest, follow) -> list[int]:  # noqa: ANN001
    """The note the last answer led with, when this question only leans on it
    ("when is it", "how much does it cost", "what time", "what did we decide
    about it": audit 1030 Z53). It is read like an open note: the follow-on
    keeps its subject, and the slot runs on that note rather than on
    whichever note best matches the bare words."""
    if follow is not None and follow.note_ids and not req.body.note_ids:
        return _framed_scope(req, follow)
    objects = ((req.history or [{}])[-1].get("objects") or []) if req.history else []
    if not objects or req.body.note_ids or (follow is not None and follow.kind != "pronoun") or not composer_dialogue.refers_back(req.question):
        return []
    label = str(objects[0]).strip().lower()
    rows = visible_notes.holding(req.session, label, limit=25)
    return [row.id for row in rows if _turn_label(row.content).lower() == label][:1]


def _framed_scope(req: _StreamRequest, follow) -> list[int]:  # noqa: ANN001
    """The notes the last answer's frame binds this turn to (fable-composer-1110 F1). The ids are
    client input, so each is read again: a deleted or private note is never reached through them.
    Not bound, and searched instead, when the turn's own words are held by another note and not by
    this one ("what is the standard deviation" after the Harbor answer), or the thing it names is
    another note's title ("did I finish it" when the answer before cited the wrong note)."""
    rows = visible_notes.by_ids(req.session, follow.note_ids)
    ids = [row.id for row in rows]
    bound = " ".join(row.content or "" for row in rows).lower()
    if _said_plainly_instead(req, follow, bound):
        return []
    asked = composer_dialogue.subject_terms(req.question) if follow.kind == "bound" else []
    own = _own_words(asked, bound)
    if follow.kind == "bound" and not own and not _slot_cue(req.question):
        follow.question = req.question  # "how many sets": the note holds the words, so they are asked as typed
    if not ids or any(_visible_elsewhere(req.session, t, ids) for t in own) or any(_visible_elsewhere(req.session, t, ids, titled=True) for t in [*asked, *composer_dialogue.subject_terms(follow.question)]):
        follow.question = req.question if follow.kind == "bound" else follow.question  # let go: the turn's own words, searched
        return []
    return ids


def _said_plainly_instead(req: _StreamRequest, follow, bound: str) -> bool:  # noqa: ANN001
    """"who am I going with" after an answer binds to that note; when it has no such line the question is the trip note's (F13 a)."""
    plain = composer_dialogue.said_plainly(req.question)
    if follow.kind != "bound" or plain is None or not plain.question.endswith("travelling with") or "going with" in bound:
        return False
    follow.question, follow.kind, follow.note_ids = plain.question, "subject", ()
    return True


def _own_words(asked: list[str], bound: str) -> list[str]:
    """The question's words the bound notes do not hold; a cue ("fast") is never one."""
    return [t for t in asked if t.lower() not in bound and t.lower() not in composer_slots.SLOT_CUES]


def _slot_cue(question: str) -> bool:
    """"how fast", "how long": a cue to read on the note before, not words to find in another note;
    the rewritten question ("how long about banana bread?") is kept, not the bare typed one."""
    return bool(composer_slots.SLOT_CUES.intersection(question.lower().replace("?", " ").split()))


def _visible_elsewhere(session, term: str, ids: list[int], *, titled: bool = False) -> bool:  # noqa: ANN001
    """Whether a visible note outside `ids` holds `term`, or with `titled`, is titled `term` ("Mia")."""
    rows = visible_notes.holding(session, term, limit=25 if titled else 1, besides=ids)
    return any(_turn_label(row.content).lower() == term.lower() for row in rows) if titled else bool(rows)


def _composed_support(result: dict) -> dict:
    """The support of an answer no model wrote (`grounding.composed_support`)."""
    return composed_support(result["support"], result.get("grounding") or [])


def _not_again(answer, follow, restated: bool, req: _StreamRequest) -> tuple:  # noqa: ANN001
    """`answer(follow, restated)`, asked again plainly when the follow-on's reading gave the answer
    before again: "and kyoto?" after the budget is never the budget twice (fable-composer-1110 F1)."""
    result = answer(follow, restated)
    if follow is not None and follow.fallback and composer_dialogue.repeats(str(result.get("text") or ""), req.history):
        follow = composer_dialogue.FollowOn(follow.fallback, follow.previous, kind="subject")
        result = answer(follow, True)
    return result, follow


def _with_frame(result: dict, follow, req: _StreamRequest, current: list, today) -> None:  # noqa: ANN001
    """The frame the answer is sent with (`composer_dialogue.turn_frame`), read from the question
    as the follow-on put it. A slot read on the note before ("how much flour") is still about that
    note's subject, so "what temperature" next is asked of the banana bread, not of "flour"."""
    result["frame"] = frame = composer_dialogue.turn_frame(follow.question if follow else req.question, result, current, today)
    before = ((req.history or [{}])[-1] or {}).get("frame") or {}
    if frame and follow is not None and follow.kind == "bound" and before.get("subject") and frame["note_ids"][:1] == before.get("note_ids", [])[:1]:
        frame["subject"] = before["subject"]


def _frame_events(result: dict) -> list[dict]:
    return [{"type": "frame", "frame": result["frame"]}] if result.get("frame") else []


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


def model_chips(session: Session, t: "_Turn", grounding: list[dict]) -> list[dict]:
    """The next steps under a model's answer (first audit F14; 26 of 30 model
    turns had none): the chips the composer puts under an answer that cites a
    note, "Open it" and "What is left in it", and any question the model's
    own words suggest (`ask_chips`). Only a model-written answer that sent no
    offer of its own, so the composer's and the engine's chips stand."""
    if not t.ollama_running or t.written_by_app or t.conversational or "offer" in t.sent_kinds or not t.answer_text:
        return []
    from tessellate.ai import ask_chips

    result = {"grounding": grounding}
    titles = _cited_titles(session, result)[:1]
    asks = [f"Open \u201c{titles[0]}\u201d", *([f"What is left in \u201c{titles[0]}\u201d?"] if _first_cited_has_list(session, result) else [])] if titles else []
    asks += [q for q in ask_chips.lift(t.answer_text) if q not in asks]
    return [{"type": "offer", "offer": {"kind": "ask", "label": "", "asks": asks[:4]}}] if asks else []


def _uncut(title: str) -> str:
    return title.rstrip("…. ").lower()


def _facts_turn(req: _StreamRequest, prepared: dict, t: _Turn) -> bool:
    """Whether a model writes this turn from the engine's exact answer (CHAT_PLAN
    decision 75; the owner, 2026-10-27: "why is it responding as the composer
    when my ai is in use??"): a count, a worked sum, the app's records or a
    read tool's rows, with a model up, on every surface but the Ask box's From
    your notes (`_composed`). Not a skill run, which reads its own way.

    Not "nothing matched" (`_no_notes_events`): the check on the model's words
    (`fact_check.keeps`) reads figures, and that answer has none. That turn has
    its own check, which reads the negative (`fact_check.says_nothing_found`,
    `chat_said._miss_events`). With tools (the popup agent, Chat's Agent
    mode) the agent has that turn and can search."""
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
            t.written_by_app = (payload.get("support") or {}).get("by_model") is False
        t.shape = (payload.get("support") or {}).get("shape") or t.shape
    if kind == "answer" and "answered" not in t.marks:
        t.marks["answered"] = time.perf_counter() - t.started


def _fold_break(t: _Turn, kind: str, payload: dict) -> None:
    """A tool or step event ends the paragraph; a tool's touched notes are kept."""
    t.in_prose = False
    if kind == "tool":
        for item in payload.get("touched") or []:
            if item.get("kind") == "note" and isinstance(item.get("id"), int):
                t.touched_note_ids.append(item["id"])


def _fold_event(t: _Turn, kind: str, payload: dict, live_grounder) -> list:  # noqa: ANN001
    """Fold one event into the running answer; the live grounding rows when
    this delta could have closed a sentence."""
    if kind in _PARAGRAPH_BREAKS:
        _fold_break(t, kind, payload)
        return []
    if kind == "answer_final":
        #: The server's own replacement of what streamed (a model that died mid-answer).
        t.answer_text, t.in_prose = payload.get("text") or t.answer_text, True
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
    #: A composed turn ends with Next chips (INBOX 1729 a).
    closing = composer_talk.Closing(req.session, req.body.question or "", user_now(deps.get_config()).date(), t.composing or t.composed or prepared["stats"] is not None, req.history)
    try:
        for payload in events:
            kind = payload.get("type")
            payload = closing.see(payload, t.answer_text)
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
        yield from map(_event, closing.finish(t.answer_text))
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
        yield _event({"type": "answer", "delta": "\n\nThat did not work. Nothing was changed."})


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


def _why(req, prepared, grounding, composing, will_answer, tools_only, ollama_running, shape, marks, text="") -> list[dict]:
    """B30's lines for this turn (`ai/why.py`). A note the answer links is a
    note it used, whether or not retrieval or a grounding row counted it
    (audit 1028 E72: a summary read its note and said "nothing matched")."""
    linked = set(re.findall(r"\(#/notes/(\d+)\)", text or ""))
    return why.lines(
        intent=prepared["intent"],
        mode=prepared.get("search_mode"),
        matched=len(prepared.get("raw_results") or []),
        used=len({str(row.get("note_id")) for row in grounding if isinstance(row.get("note_id"), int)} | linked),
        when=prepared.get("when_phrase"),
        scoped=bool(req.body.attached_notes_only or req.body.note_ids),
        composed=composing,
        model=("Atlas's tools" if tools_only else req.model_manager.served_chat_model(req.ollama)) if will_answer else None,
        shape=shape,
        context=will_answer and ollama_running and _asks_capability(req, prepared),
        loading=bool(prepared.get("meaning_loading")),
        read_by=str(prepared.get("read_by") or ""),
        marks=marks,
    )


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
