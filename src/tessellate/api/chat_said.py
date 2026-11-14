"""What the composed answer (no model) says around its quotes: counted and
filed leads, the stats panel, the app's own answers, the no-notes line, the
rows remembered for a follow-up, and what the answer cites.

Moved whole from `routes_chat.py` (audit AR3, gods-1101): the code is
unchanged, and `routes_chat` re-exports every name here that anything
reads, so `routes_chat._cited_titles` still works. Imports run one way, down the
layer list in `routes_chat.py`'s docstring, never back to `routes_chat`.
"""

from __future__ import annotations

import json
import logging
import re
from collections import OrderedDict
from collections.abc import Iterator
from datetime import datetime
from sqlalchemy import func, or_, select, text as sql_text
from sqlalchemy.orm import Session

from tessellate.ai import capability, composer, composer_aware, composer_lists, composer_open, composer_plan, composer_social, fact_check, filed_name, intent, phrasing, realise
from tessellate.ai import composer_digest_sentences
from tessellate.ai import acts, composer_dialogue, task_acts
from tessellate.ai import composer_frame, composer_read
from tessellate.ai import composer_smalltalk, composer_talk
from tessellate.ai.ollama_client import OllamaError
from tessellate.entry import manager
from tessellate.api import chat_extra
from tessellate.api.chat_request import ChatRequest, _StreamRequest, _Turn, _composed, _meta_event
from tessellate.core import clock, deps, private_turn
from tessellate.core.config import user_now
from tessellate.core.database import AskTurn, Conversation, Entity, Entry, like_escape, LIKE_ESCAPE
from tessellate.repo import documents as documents_repo
from tessellate.repo import relations as relations_repo
from tessellate.repo import reminders as reminder_repo
from tessellate.core.logbuffer import safe_value


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


#: A note's kind, not what it is about ("Idea: build a bird feeder").
_NOT_A_SUBJECT = frozenset("idea ideas note notes todo todos reminder thought thoughts list draft remember".split())


def _save_ask_turn(
    session: Session,
    question: str,
    answer: str,
    prepared: dict,
    grounding: list[dict] | None = None,
    composed: bool = False,
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
            composed=composed,
        )
    )
    session.commit()


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
        documents_repo.mentioning_any(session, words, _RELATED_LIMIT),
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
        reminder_repo.matching(session, _any_word, _RELATED_LIMIT),
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


#: Under an answer composed from the notes because the model stopped mid-turn.
MODEL_STOPPED_NOTE = "The model stopped before it could answer, so this is Atlas's answer from your notes."
#: The model finished, but no sentence of its answer was backed by the notes (review 5899348594).
MODEL_UNBACKED_NOTE = "The model's answer said things your notes do not, so this is Atlas's answer from your notes."


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


def _asks_capability(req: _StreamRequest, prepared: dict) -> bool:
    """"Can you search the web?" (CHAT_PLAN decision 65): a question about
    what Atlas can do, answered from the app's own list on every surface,
    model or none, and never a search, a web call or a tool."""
    return prepared["intent"] == intent.ABOUT_APP and capability.asks(req.question or "")


def _capability_answer(req: _StreamRequest, ollama_running: bool, voice: str) -> str:
    try:
        web = bool(deps.get_config().get_preference("web_search_enabled", False))
    except Exception:  # noqa: BLE001  # an unreadable preference is off
        web = False
    recent, seed = _reply_seed(req)
    return capability.answer(req.question, prefs={"web_search_enabled": web}, model_running=ollama_running,
                             voice=voice, recent=recent, seed=seed)


def _app_answers(req: _StreamRequest, ollama_running: bool) -> bool:
    """Whether the app's own engine gives this turn's finished answer
    (CHAT_PLAN decision 75, the owner: "it SHOULD completely replace it if
    the ai isnt available, otheriwse the composer is an assistant to the
    ai"): with no model, or when the Ask box asked for From your notes.
    With a model up, what the engine found goes to the model as context."""
    return not ollama_running or _composed(req, ollama_running)


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
    return recent, f"{salt}:{clock.today().isoformat()}:{req.body.attempt}"


def _sees(req: _StreamRequest, kind: str | None, seed: str) -> str:
    """What the app can see, said only after a hello."""
    if req.body.screen and kind in ("greeting", "morning", "how"):
        return composer_aware.opening(_awareness(req), seed)
    return ""


def _saved_joke_reply(req: _StreamRequest, seed: str) -> str:
    """One you saved, said as it is written, before owning up to having none
    (audit 1031 C46); empty when no note is a joke."""
    joke = chat_extra.saved_joke(req.session, req.question + seed)
    return f"From your notes: {joke[1]}\n\n[Open the note](#/notes/{joke[0]})" if joke else ""


def _ping_offer(req: _StreamRequest, prepared: dict) -> list[dict]:
    """A ping that says "test" offers its notes as a chip (INBOX 1485)."""
    subject = composer_social.ping_subject(req.question) if composer_smalltalk.social_kind(req.question, prepared["intent"]) == "test" else ""
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
    start = composer_read._title(text)[1]
    for term in query_understanding.search_terms((text[start:] if start else text)[:400]):
        if len(term) >= 4 and term.isalpha() and term not in _NOT_A_SUBJECT and query_understanding.is_topic_word(term) and spelling.is_word(term):
            return term
    return ""


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
    """What a next-step line and the Open chip call a note: its heading, a
    whole short first line, or, for a title-less note, the one name every
    surface gives it (`composer_frame.clipped_words`, R3-15; never its date,
    INBOX 1441)."""
    if not composer_frame.title_line(content):
        return composer_frame.clipped_words({"content": content})
    name, _ = composer_read._title(content)
    return realise.cut_title(name.strip(), 60) if name.strip() else ""


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


def _listed_below(stats: dict) -> str:
    """The rows an answer says are "listed below", written under it (audit
    1031 C44): "Your longest note is ... The top 10 are listed below." with
    nothing below was a promise the stream never kept."""
    rows = [f for f in stats.get("facts") or [] if isinstance(f, dict) and f.get("label") and f.get("id")]
    if not rows or "listed below" not in str(stats.get("text") or ""):
        return ""
    def line(f: dict) -> str:
        #: A row with no count (the notes gone stale) is its link alone, not ", no words" (F13 d, 1110).
        tail = f", {realise.count_noun(int(f['count']), 'word')}" if isinstance(f.get("count"), int) else ""
        return f"- [{f['label']}](#/notes/{f['id']}){tail}"
    return "\n\n" + "\n".join(line(f) for f in rows)


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


def _miss_events(req: _StreamRequest, ollama_running: bool, prepared: dict, line: str) -> list[dict]:
    """**The plain miss, in the model's words** (model-facts-1027 row 6): the answer to a question no note answers.
    With a model up and a notebook that holds something (`line` is still the engine's plain miss; an empty notebook has its
    first steps, which are true as they are), the miss goes to the model as its facts, and the reply stands only if it
    says just that (`fact_check.says_nothing_found`). Held whole until checked, like `_fact_events`; a model that fails or
    claims a find leaves the engine's line, with the reply's cost and no model named. Else the line, as it was."""
    from tessellate.ai import librarian
    from tessellate.ai.answer_trim import trim_assistant_padding
    from tessellate.api.chat_request import _in_full

    if line != librarian.NO_RESULTS_MESSAGE or not ollama_running or _composed(req, ollama_running):
        return [{"type": "answer", "delta": line}]
    messages = librarian.build_facts_messages(
        _in_full(req), line, style=prepared["style"], profile=prepared["profile"], history=req.history,
        persona_prompt=req.persona_prompt, mode=req.mode,
    )
    held = _held_reply(req, messages)
    prose = trim_assistant_padding(held["prose"]).strip()
    if fact_check.says_nothing_found(prose, req.question or ""):
        return [{"type": "answer", "delta": prose}, *([held["stats"]] if held["stats"] else [])]
    if held["prose"]:
        logging.getLogger("tessellate.chat").warning("chat: the model's words did not keep to the app's miss, which stands")
    cost = {k: v for k, v in held["stats"].items() if k != "model"} if held["stats"] else None
    return [{"type": "answer", "delta": line}, *([cost] if cost else [])]


def _current_notes(req: _StreamRequest, notes: list[dict]) -> tuple[list[dict], list]:
    """The notes with any a newer note on the asked subject supersedes left
    out, and those left out (O11, `ai/supersede.py`)."""
    from tessellate.ai import supersede

    return supersede.current(req.question or "", notes)


def _older_dates(req: _StreamRequest, current: list[dict], result: dict, older: list) -> list:
    """`older` when a note was set aside, else the older date of the same event
    for a when-answer: the newest dated fact leads and the older is said once
    (audit 2 G1, `supersede.older_dates`)."""
    from tessellate.ai import supersede

    if older or not result.get("grounding"):
        return older
    return supersede.older_dates(req.question or "", str(result.get("text") or ""), current, user_now(deps.get_config()).date())


def _with_words_only(text: str, prepared: dict, result: dict, session=None) -> str:  # noqa: ANN001
    """"Your only note on it" is a claim about the whole notebook; a search
    that read words only (no search by meaning) cannot make it, so the line
    leaves it out (blind test 2026-10-31, item 3)."""
    words_only = prepared.get("search_mode") == "keyword" or prepared.get("meaning_off") or prepared.get("meaning_loading")
    if not words_only or not result.get("grounding"):
        return text
    #: A notebook of one note has no other to find: the plain claim is true as said (R3-31).
    if session is not None and manager.count_notes(session) <= 1:
        return text
    parts = text.split("\n\n")
    if not any(composer_digest_sentences.is_only_claim(part) for part in parts):
        return text
    #: The claim goes and nothing replaces it: "Only one note has those words; search by meaning
    #: could find others" was a stat line a person would not add (fable-composer-1110 F7.3).
    return "\n\n".join(part for part in parts if not composer_digest_sentences.is_only_claim(part))


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


def _asks_only_a_time(question: str) -> bool:
    """A question that names a time and no subject ("what did I write today")."""
    planned = composer.plan(question or "")
    return bool(planned.window and planned.window_phrase and not planned.terms)


def _related_sentence(related: list) -> str:
    plural = len(related) != 1
    kinds = sorted({item["kind"] for item in related})
    return (
        f" There {'are' if plural else 'is'} {len(related)} other {'items' if plural else 'item'}"
        f" that {'mention' if plural else 'mentions'} it, in your {' and '.join(f'{k}s' for k in kinds)}."
    )


_CHART_ASKED = re.compile(r"\b(?:chart|graph|plot|visuali[sz]e|trend)\b", re.I)


def _chart_line(req: _StreamRequest) -> str:
    """What the chart beside a counting question shows, or ""."""
    from tessellate.api import routes_vision

    if not _CHART_ASKED.search(req.question or ""):
        return ""
    drawn = routes_vision.question_chart(req.session, req.question or "")
    if not drawn or not any(row["value"] for row in drawn["rows"]):
        return ""
    total = f", {drawn['total']:,} in all" if drawn["total"] is not None else ""
    return f"{drawn['title']}{total}."


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


def _asked_before(req: _StreamRequest) -> list[str]:
    """The questions of the last three turns as they stood, a "more" being
    the question it leans on, once each."""
    asked: list[str] = []
    for turn in composer_dialogue._standing([t for t in (req.history or [])[-3:] if str(t.get("question") or "").strip()]):
        if turn["question"] not in asked and not composer_dialogue._MORE.match(turn["question"]):
            asked.append(turn["question"])
    return asked


def _row_source(by_id: dict, row: dict) -> str:
    """A grounding row's sentence as its note wrote it (by place), or as the
    row quotes it."""
    content = by_id.get(row.get("note_id"), "")
    if content and "start" in row and "end" in row:
        return content[row["start"]:row["end"]]
    return str(row.get("source") or "")


def _open_note_answer(req: _StreamRequest, follow, current: list, today):  # noqa: ANN001, ANN202
    """The open note's own answer to "what's left", "when is it due", "who is
    involved" (`ai/composer_open.py`): short, and different for every note."""
    opened = req.body.open_note_id
    #: The notes that record the open one's items ride beside it (F15): the
    #: open note is the one bound, whatever else the context holds.
    bound = set(req.body.note_ids or [])
    mine = [n for n in current if n.get("id") in bound] if bound else current
    if follow or not opened or len(mine) != 1 or mine[0].get("id") != opened:
        return None
    if not composer_open.reads_note(req.question, mine[0]):
        return None
    dialogue = composer.Dialogue.from_history(req.history)
    return composer.open_note_answer(req.question, mine[0], today=today, salt=dialogue.salt)


#: What an answer says when it could not answer: its own "missing" lines and the
#: plain no-result and no-checklist lines.
_CANNOT = re.compile(
    r"None of (?:these|your) (?:notes|records)|do(?:es)? not (?:talk about|mention|address)|couldn't find|I don't see any mention|nothing in these notes|"
    r"No note found brings up|omit(?:s)? |lacks any reference|no recorded information|absence of documentation|No checklist|nothing comes up|"
    r"doesn't seem to be in the notes|I looked, but nothing|Nothing is dated|has anything left to tick",
    re.I,
)


def _says_cannot(text: str) -> bool:
    """The answer says the notes do not hold it, in any of the model's ways."""
    return bool(_CANNOT.search(text))


def _open_title(session: Session, body: ChatRequest) -> str:
    """The title of the plain note or document open, "" for anything else: a
    private, binned or board note is never named (composer_aware's rule)."""
    from tessellate.ai.tools._common import _visible

    if body.screen and body.screen.open_doc_id:
        doc_title = documents_repo.title_of(session, body.screen.open_doc_id)
        if doc_title and doc_title.strip():
            return doc_title.strip()
    if body.open_note_id:
        row = session.query(Entry.content).filter(Entry.id == body.open_note_id, *_visible()).first()
        if row:
            return composer_read._title(str(row[0] or ""))[0].strip()[:60]
    return ""


def _topic_word(asked: str, answer: str) -> str:
    """The first search term of `asked` of four letters or more that `answer`
    also used, as typed (a name keeps its capital: "We were on Sara"), or ""."""
    from tessellate.ai import when as when_words
    from tessellate.search import query as query_understanding

    dates = {w.lower() for _s, _e, phrase in when_words.find(asked) for w in re.findall(r"[A-Za-z]+", phrase)}
    for term in query_understanding.search_terms(asked):
        if term.lower() in dates or composer_aware.is_date_word(term):
            continue
        if len(term) >= 4 and term.isalpha() and query_understanding.is_topic_word(term) and term.lower() in answer:
            typed = re.search(rf"\b{re.escape(term)}\b", asked, re.I)
            return typed.group(0) if typed else term
    return ""


def _chat_topic(history: list[dict]) -> str:
    """What the last question in this chat was about: a word of it the answer
    also used, or "". A word the answer never touched ("left", "write",
    "week") is the question's frame, not its subject (blind test round 2,
    finding 2). A date word ("November", "Friday") is the question's window,
    never a subject: a question about nothing but a day is about that day,
    said as typed ("3 November", INBOX 1739)."""
    from tessellate.ai import when as when_words

    for turn in reversed(history or []):
        answer, asked = str(turn.get("answer") or "").lower(), str(turn.get("question") or "")[:200]
        word = _topic_word(asked, answer)
        if word:
            return word
        day = when_words.find(asked)
        if day and answer:
            return day[0][2]
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
            doc_title = documents_repo.title_of(session, nid)
            title = realise.cut_title(doc_title.strip(), 60) if doc_title is not None else ""
        else:
            row = session.query(Entry.content).filter(Entry.id == nid, *_visible()).first()
            title = _closing_name(str(row[0] or "")) if row else ""
        if title:
            titles.append(title)
    return titles


def _cited_bodies(session: Session, result: dict) -> list[tuple[str, str]]:
    """(title, text) of the notes an answer drew on, for Detailed's supporting sentences."""
    from tessellate.ai.tools._common import _visible

    out: list[tuple[str, str]] = []
    for kind, nid in _cited_ids(result)[:3]:
        row = session.query(Entry.content).filter(Entry.id == nid, *_visible()).first() if kind != "document" else None
        if row and (title := _closing_name(str(row[0] or ""))):
            out.append((title, str(row[0] or "")))
    return out


def _name_documents(session: Session, rows: list[dict]) -> None:
    """A document row a digest quoted names its document, as the composer's own
    rows do, so the page can draw it as a source card (INBOX 1466)."""
    for row in rows:
        if row.get("kind") == "document" and not row.get("title"):
            doc_title = documents_repo.title_of(session, row.get("note_id"))
            row["title"] = (doc_title or "Untitled") if doc_title is not None else ""


def _linked_notes(session: Session, result: dict) -> list[dict]:
    """The notes linked to the ones an answer cited, not cited themselves
    (INBOX 1466): the related row under a composed answer, which a model's
    answer has no use for (it reads the notes it is given and says the rest)."""
    from tessellate.ai.tools._common import _visible

    cited = {nid for kind, nid in _cited_ids(result) if kind == "entry"}
    if not cited:
        return []
    links = relations_repo.touching_any(session, cited)
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


_CHECKLIST = re.compile(r"^\s*[-*+] \[[ xX]\]", re.M)


def _first_cited_has_list(session: Session, result: dict) -> bool:
    """Whether the first note an answer cited keeps a checklist: "What is left
    in it" is a question only such a note answers (audit 1031 C47)."""
    from tessellate.ai.tools._common import _visible

    for kind, nid in _cited_ids(result)[:1]:
        if kind != "document":
            row = session.query(Entry.content).filter(Entry.id == nid, *_visible()).first()
            return bool(row and _CHECKLIST.search(str(row[0] or "")))
    return False


def _search_footer(prepared: dict, result: dict) -> str:
    """How a miss was searched (words only, meaning off or loading). An app-tool
    answer ("undo") never read the notes, so it carries none (Z64)."""
    if result.get("shape") == "help":
        return ""
    for key in ("meaning_loading", "meaning_off"):
        if prepared.get(key):
            return "\n\n" + composer_digest_sentences.PHRASES[key]
    return ""


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
    events = events if req.skill else composer_talk.Closing(req.session, req.body.question or "", user_now(deps.get_config()).date(), history=req.history).apply(events)
    return [json.dumps(e) + "\n" for e in ({"type": "status", "stage": "searching"}, meta, *events, {"type": "done"})]


def acts_on_listed_task(question: str, history: list[dict], now: datetime) -> bool:
    """Whether `question` acts on a task the last answer's list showed ("tick the first one", R9-9)."""
    if not history:
        return False
    shown = history[-1].get("answer") or ""
    listed = set(task_acts.items_in(shown))
    return (acts.parse(question, now, history) or {}).get("about") in listed
