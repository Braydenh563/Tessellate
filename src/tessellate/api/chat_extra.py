"""The route's side of `ai/composer_extra.py` (INBOX 1351): load the notes and
reminders a study, plan or calculation answer reads, and turn its reply into
stream events. Kept out of `routes_chat.py`, which is large enough."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import activity, composer_cancel, composer_thennow, composer_extra, composer_suggest, composer_talk, composer_web, realise
from tessellate.ai import composer_digest_sentences
from tessellate.ai.composer_study import Ctx
from tessellate.ai.tools._common import _visible
from tessellate.core import deps
from tessellate.core.database import Category, Entry
from tessellate.repo import categories as categories_repo
from tessellate.repo import reminders as reminder_repo

NOTE_LIMIT = 400
log = logging.getLogger("tessellate.chat")


def _notes(session: Session) -> list[dict]:
    rows = (
        session.query(Entry.id, Entry.content, Entry.created_at, Category.name, Entry.archived_at, Entry.is_draft, Entry.tags)
        .outerjoin(Category, Entry.category_id == Category.id)
        .filter(*_visible()).order_by(Entry.created_at.desc()).limit(NOTE_LIMIT).all()
    )
    return [{"id": i, "content": c or "", "created_at": made, "category": cat or "", "archived": gone is not None, "draft": bool(draft), "tags": _tags(tags)} for i, c, made, cat, gone, draft, tags in rows]


def _tags(raw: str | None) -> list[str]:
    """A note's tags (the column is a JSON array); none when it is not one."""
    try:
        got = json.loads(raw or "[]")
    except ValueError:
        return []
    return [str(t) for t in got] if isinstance(got, list) else []


def _reminders(session: Session) -> list[dict]:
    rows = reminder_repo.every(session, include_done=True, limit=300)
    return [{"id": r.id, "text": r.text, "due_at": r.due_at, "done": r.done, "entry_id": r.entry_id, "priority": r.priority} for r in rows]


_PATTERNS = re.compile(
    r"^(?:what|which|anything)\b.*\b(?:keeps?|keep) coming up\b|\bany (?:patterns?|trends?)\b|\bwhat (?:patterns?|trends?)\b"
    r"|\b(?:recurring|repeated|repeating) (?:themes?|topics?|subjects?)\b|\bwhat do i keep (?:writing|mentioning)\b",
    re.IGNORECASE,
)
_CONTRADICTIONS = re.compile(r"\b(?:contradict\w*|conflicting notes?|changed my mind|change of mind|disagree\w*)\b|\b(?:conflicts?|disagreements?) (?:in|between|among|across) (?:my |the |these )?notes\b"
                             r"|\binconsistenc(?:y|ies)\b|^\W*(?:please )?(?:check|look|search|scan|go through)(?: (?:through|over) )?(?: (?:my|the) notes)? for (?:any )?(?:contradictions?|conflicts?|clashes)\b|\b(?:any (?:of )?(?:my |the )?notes?|(?:anything|something)\b[^?.]{0,30}\bnotes?)\b[^?.]{0,30}\b(?:inconsistent|contradictory|conflict(?:s|ing)?\b(?!\s+with\b(?!\s+(?:each|one|another|other))))", re.IGNORECASE)  # notes among themselves, never "conflicts with the dentist"
#: "What am I forgetting" is what is still open; "what have I forgotten" is the faded notes
#: (second eye F13d), which the older readers list as titles.
_FORGETTING = re.compile(r"\bwhat (?:am i|have i been|did i) forget\w*\b|\banything (?:i(?:'m| am)|i have) forgett\w+\b", re.IGNORECASE)


def _changes_of_mind(session: Session, now: datetime, question: str = "") -> str:
    """The insights reader's dated changes of mind, then each subject a newer
    note replaced (`supersede.changes`, the pairing answers are read through), L-chat-8."""
    from tessellate.ai import insights, supersede

    subject = supersede.ask_subject(question)
    #: A named subject keeps only its own changes (L-chat-245): the words in the line or in either note.
    lines = [i.text for i in insights.from_session(session, now.date(), limit=12) if i.rule in ("contrast", "drift") and supersede.about(subject, i.text)][:4]
    lines += [supersede.changes_line(r, now.date()) for r in supersede.changes(_notes(session)) if supersede.about(subject, str(r.older.get("content")), str(r.newer.get("content")))][-4:]
    if not lines and subject:
        return f"I found no change of mind about {subject} in your dated notes."
    if not lines:
        return "I found no change of mind in your dated notes. Notes that say different things about the same subject on different days would show here."
    return "Each change of mind in your dated notes:\n\n" + "\n".join(f"- {line}" for line in lines)


def notebook_events(session: Session, question: str, *, now: datetime) -> list[dict] | None:
    """The answer to a question about the notebook's shape that rules can
    settle: the Patterns line ("what keeps coming up"), the dated changes of
    mind ("any contradictions"), what is overdue or open ("what am I
    forgetting"). With no model it is the answer; with one it is handed over
    as facts, so both paths say the same (second audit G11, parity)."""
    from tessellate.ai import composer_plan, insights

    text = " ".join((question or "").split())
    try:
        if _FORGETTING.search(text):
            ctx = Ctx(question=text, notes=_notes(session), now=now, reminders=_reminders(session))
            reply = composer_plan._left(ctx)  # noqa: SLF001
            said = reply.text if reply else ""
        elif _CONTRADICTIONS.search(text):
            said = _changes_of_mind(session, now, text)
        elif _PATTERNS.search(text):
            found = insights.from_session(session, now.date(), limit=4)
            said = ("\n".join(f"- {line}" for line in insights.listed(found)) if found else
                    "Nothing repeats enough to call a pattern yet. A subject needs to turn up in several notes over a few weeks.")
        else:
            return None
    except Exception:  # noqa: BLE001  # the older readers answer
        log.exception("chat: the notebook-shape reader failed")
        return None
    return [{"type": "answer", "delta": said}] if said else None


def starter_leads(session: Session, now: datetime) -> list[str]:
    """Starter chips that name something in the notebook: what is due this
    week first, then `composer_voice.suggested_searches` (the latest on the
    newest titled note, what is still open), in place of category names said
    as topics (second composer audit G12)."""
    from datetime import timedelta

    from tessellate.ai import composer_voice

    leads: list[str] = []
    try:
        week = now.date() + timedelta(days=7)
        if any(not r["done"] and r["due_at"] is not None and now.date() <= r["due_at"].date() <= week for r in _reminders(session)):
            leads.append("What's due this week?")
        leads += [str(s["query"]) for s in composer_voice.suggested_searches(_notes(session), today=now.date(), limit=2)]
    except Exception:  # noqa: BLE001  # the category chips stand in
        log.exception("chat: the starter leads failed")
    return leads


def _early_events(session: Session, typed: str, history: list[dict], now: datetime) -> list[dict] | None:
    """The readers that go before any note is read. Each reads what was typed, not the rewritten
    question: a follow-up rewrites that ("no cancel it" became a question about a note)."""
    #: "cancel" while a card waits drops that card (CHAT_PLAN X17); the card waiting is not a topic.
    if (dropped := composer_cancel.reply(typed, history)) is not None:
        return dropped
    if (undone := composer_cancel.undo_reply(session, typed, history)) is not None:
        return undone
    if (changed := composer_thennow.answer(session, typed)) is not None:
        return [{"type": "answer", "delta": changed}]
    #: A follow-on that reads the turn before ("any other diagrams", "what are those tags", INBOX 1729 b).
    if (talked := composer_talk.reply(session, typed, history, now.date())) is not None:
        return talked
    return notebook_events(session, typed, now=now)


def events(session: Session, question: str, history: list[dict], *, now: datetime, seed: str, open_ids: list[int],
           follow_kind: str = "", said: str = "", asked: str = "", ask: bool = False, voice: str = "natural") -> list[dict] | None:
    """The answer events for a question this module reads, else None. A
    failure is logged and leaves the question to the older readers."""
    if (early := _early_events(session, asked or question, history, now)) is not None:
        return early
    if _summary_goes_elsewhere(session, question):
        return None
    if (read := read_events(session, asked or question, model=deps.get_ollama().is_running())) is not None:
        return read
    ctx = Ctx(question=question, notes=_notes(session), now=now, history=history, seed=seed, open_ids=open_ids,
              follow_kind=follow_kind, said=said, asked=asked or question, ask=ask, reminders=_reminders(session), voice=voice)
    return _extra_events(ctx)


def _summary_goes_elsewhere(session: Session, question: str) -> bool:
    """"Summarise this" and "summarise Travel" read the open note or a whole
    category, which the digest does better than a title match; "summarise my
    week" is the week's recap (`ai/activity`), not a note's summary."""
    return bool(
        composer_digest_sentences.about_this(question)
        or composer_digest_sentences.named_category(question, categories_repo.names(session))
        or activity.as_recap(question) != question
    )


def _extra_events(ctx: Ctx) -> list[dict] | None:
    try:
        reply = composer_extra.answer(ctx)
    except Exception:  # noqa: BLE001  # the older readers answer
        log.exception("chat: the study, plan or calc reader failed")
        return None
    if reply is None:
        return None
    out: list[dict] = [{"type": "answer", "delta": reply.text}]
    if reply.offer:
        out.append({"type": "offer", "offer": reply.offer})
    elif reply.asks:
        out.append({"type": "offer", "offer": {"kind": "ask", "label": "", "asks": reply.asks}})
    return out


def reminder_events(session: Session, question: str, *, now: datetime) -> list[dict] | None:
    """What the reminders answer to `question` ("do I have any reminders today",
    "did I pay the phone bill", "when do the bins go out"), as an answer event,
    or None. With no model it is the answer (`composer_extra`); with one it is
    handed over as facts, so both paths read the same reminders (audit 2 G3 parity)."""
    from tessellate.ai import composer_plan, composer_reminders
    from tessellate.ai.composer_study import Ctx

    text = " ".join((question or "").split())
    try:
        ctx = Ctx(question=text, notes=[], now=now, reminders=_reminders(session))
        reply = composer_reminders.answer(ctx) or composer_plan._when_reply(ctx, text)  # noqa: SLF001
        if reply is None:
            #: "what's on today": the agenda the composer lays out, the notes' dates and the reminders together.
            reply = composer_plan.answer(Ctx(question=text, notes=_notes(session), now=now, reminders=ctx.reminders))
    except Exception:  # noqa: BLE001  # the model answers as before
        log.exception("chat: the reminder reader failed")
        return None
    if not reply:
        return notebook_events(session, text, now=now)
    return [{"type": "answer", "delta": reply.text}]


def hello_events(session: Session, question: str, *, now: datetime, voice: str = "natural") -> list[dict] | None:
    """The facts of a hello (the streak, the last note, the reminders due), so
    a model that answers "good morning" writes from the same numbers the
    composed welcome says (parity, decision 75). None for any other turn."""
    from tessellate.ai import composer_remark, composer_smalltalk

    #: A hello that leads a request is the request's turn, not a hello (review of 1749).
    if composer_smalltalk.social_kind(question) not in ("greeting", "morning") or not composer_remark.bare_hello(question):
        return None
    if composer_remark.register(question) == "casual":
        #: A tapped hello is answered in a line, in the composer voice, for the model too (INBOX 1749, parity).
        return [{"type": "answer", "delta": composer_remark.casual_hello(question, voice)}]
    try:
        line = welcome_line(session, now, question=question)
    except Exception:  # noqa: BLE001  # the model greets as before
        log.exception("chat: the welcome facts failed")
        return None
    return [{"type": "answer", "delta": line}] if line else None


def casual_greeting(question: str, voice: str, recent: list[str], seed: str, history: list[dict] | None) -> str:
    """A tapped hello ("heyy", "yo") answered in a line in the person's own
    register, with no status report, card or link (INBOX 1749); "" for a
    written hello, which keeps the welcome."""
    from tessellate.ai import address, composer_remark, composer_smalltalk, intent, question_noise

    #: A greeting that leads a request ("hey what's been happening?") is the request's, not a hello.
    if intent.classify(question) != intent.SMALLTALK:
        return ""
    if composer_smalltalk.social_kind(question) not in ("greeting", "morning") or composer_remark.register(question) != "casual" or not composer_remark.bare_hello(question):
        return ""
    line = composer_remark.casual_hello(question, voice, recent, seed, asked_how=question_noise.asks_how(question))
    how = composer_smalltalk.hello_how(question, voice, [line, *recent], seed)
    return address.greet(" ".join(p for p in (line, how) if p), address.name_of(deps.get_config()), history)


def remark_facts(session: Session, question: str) -> str:
    """What a model is told about a remark: that it is one, and the one note that bears on it."""
    from tessellate.ai import composer_remark

    return composer_remark.facts(question, lambda word: note_bearing(session, word))


def facts_events(session: Session, question: str, *, now: datetime, chat: bool = True, voice: str = "natural") -> list[dict] | None:
    """What the app knows that a model is handed as facts: the reminders'
    answer, the agenda, a hello's numbers (Chat only: the Ask box answers a hello with its hint), or one of the reads the agent has a
    tool for (`ai/parity_reads`)."""
    return reminder_events(session, question, now=now) or (hello_events(session, question, now=now, voice=voice) if chat else None) or read_events(session, question, model=True)


def read_events(session: Session, question: str, *, model: bool = False) -> list[dict] | None:
    """The bin, earlier chats or the export hand-off, said once for the
    composer and, with a model up, handed over as facts (`ai/parity_reads`)."""
    from tessellate.ai import parity_reads

    try:
        found = parity_reads.answer(session, question, model=model)
    except Exception:  # noqa: BLE001  # the older readers answer
        log.exception("chat: a parity read failed")
        return None
    if found is None:
        return None
    return [{"type": "answer", "delta": found}]


def name_events(session: Session, question: str) -> list[dict] | None:
    """"what's my name", "who am I": answered from the profile, with a model up
    or not (G7; the name is local data, so the profile switch does not gate it)."""
    from tessellate.ai import address, personal
    from tessellate.core import deps

    kind = address.asks(question)
    if kind is None:
        return None
    line = address.answer(address.name_of(deps.get_config()))
    if kind == "who":
        own = personal.answer(question, lambda: personal.notes_of(session))
        if own and own.get("grounding"):
            line = f"{line}\n\n{own['text']}"
    return [{"type": "answer", "delta": line}]


def figures_events(session: Session, typed: str, history: list[dict], today, open_ids: tuple = ()) -> list[dict] | None:  # noqa: ANN001  # a date
    """A comparison, count or sum over the figures the last answers showed (`ai/composer_figures`, F6),
    or the links of the note "it" is (`ai/composer_openlinks`, F13 j)."""
    from tessellate.ai import composer_checklist, composer_figures, composer_openlinks

    try:
        said = composer_figures.answer(session, typed, history, today) or composer_openlinks.answer(session, typed, history, list(open_ids)) or composer_checklist.finished(session, typed)
    except Exception:  # noqa: BLE001  # the ordinary readers answer
        log.exception("chat: the figures reader failed")
        return None
    return [{"type": "answer", "delta": said}] if said else None


def note_bearing(session: Session, topic: str) -> tuple[int, str] | None:
    """`(id, title)` of the newest note that names `topic` as a word (or its
    stem: "run" finds "running"), for the one gentle link under a remark
    (INBOX 1749); None when no note does. Archived notes and drafts do not count."""
    from tessellate.ai import study

    from tessellate.ai import composer_remark

    if not (pattern := composer_remark.topic_pattern(topic)):
        return None
    word = re.compile(pattern, re.I)
    for n in _notes(session):
        if not n["archived"] and not n["draft"] and word.search(n["content"]):
            return n["id"], realise.cut_title(study.title_of(n["content"]), 60)
    return None


def talk_events(session: Session, typed: str, history: list[dict], seed: str, question: str, voice: str = "natural") -> list[dict] | None:
    """The turn when it is about the talk itself (`ai/composer_chat`: a feeling,
    "shorter", "which is higher") or about Atlas ("do you have feelings"), read
    on what was typed since a follow-on rewrites `question`. A feeling or a
    missed name offers the notes on its subject only when some are found."""
    from tessellate.ai import composer_chat, composer_remark, personal, phrasing

    if (named := name_events(session, question)) is not None:
        return named
    recent = [str(t.get("answer") or "") for t in history][-phrasing.RECENT :]
    if hello := casual_greeting(typed, voice, recent, seed, history):
        return [{"type": "answer", "delta": hello}]
    said = composer_chat.reply(typed, history, seed)
    if said is None and (remark := composer_remark.reply(typed, history, seed, voice)) is not None:
        #: A remark gets a human line and, when a note clearly bears on it, one link (INBOX 1749).
        said = composer_remark.with_link(remark[0], remark[1], lambda word: note_bearing(session, word), seed, voice)
    if said is None:
        itself = personal.about_me(question)
        return [{"type": "answer", "delta": itself}] if itself else None
    out: list[dict] = [{"type": "answer", "delta": said}]
    subject = composer_chat.feeling_subject(typed)
    if subject and mentioning(session, subject.split()[-1]):
        out.append({"type": "offer", "offer": {"kind": "ask", "label": "", "asks": [f"What do my notes say about {subject}?"]}})
    return out


def welcome_line(session: Session, now: datetime, *, question: str = "", voice: str = "natural", seed: str = "", said: list[str] | None = None, link: bool = False, bare: bool = False) -> str:
    """The composed welcome (CHAT_PLAN 1353): the time of day, the reminders
    due today, the title of the last note and the writing streak, built by the
    composition layer in the person's voice. A failure to count anything
    leaves that clause out; it never fails the greeting."""
    from tessellate.ai import composer_compose, due_summary, greeting_compose, study

    #: The dashboard counts neither a draft nor an archived note as a note, so
    #: neither is "the last note" here (audit 1028 S11).
    notes = [n for n in _notes(session) if not n["archived"] and not n["draft"]][:1]
    try:
        facts = greeting_compose.gather(session, now)
        total = facts.total
    except Exception:  # noqa: BLE001  # the clause is left out
        log.exception("welcome: the notebook's numbers failed")
        facts = greeting_compose.NotebookFacts()
        total = len(notes)
    #: The count is `due_summary`'s: today's and the overdue are said apart, as the dashboard says them.
    counted = due_summary.of(_reminders(session), now)
    last = study.title_of(notes[0]["content"]) if notes else ""
    mood = composer_compose.mood_of(question, voice=voice, seed=seed, said=said or [], intent="welcome")
    #: In Chat the last note is a link the client opens (INBOX 1485: "didnt
    #: reference the note and no link or source was shown?").
    href = f"#/notes/{notes[0]['id']}" if link and notes else ""
    return composer_compose.welcome(mood, hour=now.hour, due=counted.today, overdue=counted.overdue, last=realise.cut_title(last, 60), streak=facts.streak, notes=total, question=question, last_href=href, bare=bare)


def language_events(session: Session, language: str, *, web_on: bool) -> list[dict]:
    """The notes in a language the person named ("japanese note", INBOX 1490):
    found by script or everyday words (`ai/note_language.py`), listed with
    their links, never a web search. None found says so and, with web search
    on, offers the web as a chip."""
    from tessellate.ai import note_language, tool_say

    found = [n for n in _notes(session) if not n["archived"] and not n["draft"] and note_language.is_in(n["content"], language)]
    label = note_language.label(language)
    if not found:
        events: list[dict] = [{"type": "answer", "delta": f"None of your notes look {label} to me."}]
        if web_on:
            events.append({"type": "offer", "offer": {"kind": "ask", "label": "", "asks": [f"Search the web for {language}"]}})
        return events
    lead, body, chips = tool_say._found_notes(f"I found {realise.count_noun(len(found), 'note')} in {label}.", [{"id": n["id"], "content": n["content"]} for n in found], len(found), "")  # noqa: SLF001
    return [{"type": "answer", "delta": "\n\n".join(part for part in (lead, body, chips) if part)}]


_JOKE_FILED = frozenset({"joke", "jokes", "funny", "humour", "humor"})


def saved_joke(session: Session, seed: str = "") -> tuple[int, str] | None:
    """`(note id, its text)` of a note the person filed as a joke, by tag or by
    category (#jokes, Fun, Humour), newest first and the next one for each
    `seed`; None when there is none: "tell me a joke" is answered from them
    before the app owns up to having none (audit 1031 C46)."""
    from tessellate.entry import manager

    found = []
    for entry in session.scalars(select(Entry).where(*_visible()).order_by(Entry.created_at.desc()).limit(500)):
        filed = {t.lower() for t in manager.shown_tags(entry)} | {str(manager.category_name_for(session, entry) or "").lower()}
        if filed & _JOKE_FILED or "fun" in filed:
            found.append(entry)
    if not found:
        return None
    entry = found[sum(map(ord, seed)) % len(found)]
    return entry.id, str(entry.content or "").strip()


def mentioning(session: Session, word: str) -> int:
    """How many notes the notes search finds for `word` ("test" finds
    "testing"), for a ping's one line (INBOX 1485). The search the listing
    runs (`search_notes`), so the count offered, the list shown and the answer
    given are one number (INBOX 1487); 0 when unreadable."""
    from tessellate.ai import tool_say
    from tessellate.ai import tools as agent_tools

    if not word.isalpha():
        return 0
    try:
        return tool_say.matched(agent_tools.execute_tool(session, "search_notes", {"query": word}))
    except Exception:  # noqa: BLE001  # no index yet: nothing is counted
        log.exception("chat: counting the notes a ping names failed")
        return 0


def _turn_label(content: str) -> str:
    """(Lives here, not in chat_turn: slot_reply reads it and chat_turn imports this
    module, so the other way round was an import cycle, CodeQL 1998.)
    A note as a history turn names it (`chatTurnObjects` in chat-attach.js):
    its first line without heading or list marks, up to the first stop."""
    first = re.sub(r"^[#*>\-\s]+", "", (content or "").strip().split("\n", 1)[0])
    return re.split(r"[:.!?]", first)[0].strip()[:80]


def notes_instead(history: list[dict]) -> str:
    """The question the "Search my notes instead" chip was offered under: the
    last turn's, or "" when there is none (L217)."""
    return str(history[-1].get("question") or "").strip() if history else ""


def slot_reply(session: Session, question: str, history: list[dict]) -> str:
    """The reply to "Which note do you want pinned?" completes that act before anything
    routes it ("erm, the interesting bean one" is "Pin note 3"; INBOX 1570). The
    question itself when the last answer was not asking for a note."""
    if question.strip() == composer_web.NOTES_INSTEAD:
        return notes_instead(history) or question
    if not composer_suggest.pending_kind(history):
        return question
    #: The notes the other readers here read (`_notes`: visible, newest 400), not a query of its own.
    return composer_suggest.fill_slot(question, history, [(n["id"], _turn_label(n["content"])) for n in _notes(session)]) or question
