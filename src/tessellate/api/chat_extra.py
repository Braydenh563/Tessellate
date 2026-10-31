"""The route's side of `ai/composer_extra.py` (INBOX 1351): load the notes and
reminders a study, plan or calculation answer reads, and turn its reply into
stream events. Kept out of `routes_chat.py`, which is large enough."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import activity, composer_digest, composer_extra, realise
from tessellate.ai.composer_study import Ctx
from tessellate.ai.tools._common import _visible
from tessellate.core.database import Category, Entry, Reminder

NOTE_LIMIT = 400
log = logging.getLogger("tessellate.chat")


def _notes(session: Session) -> list[dict]:
    rows = (
        session.query(Entry.id, Entry.content, Entry.created_at, Category.name, Entry.archived_at, Entry.is_draft)
        .outerjoin(Category, Entry.category_id == Category.id)
        .filter(*_visible()).order_by(Entry.created_at.desc()).limit(NOTE_LIMIT).all()
    )
    return [{"id": i, "content": c or "", "created_at": made, "category": cat or "", "archived": gone is not None, "draft": bool(draft)} for i, c, made, cat, gone, draft in rows]


def _reminders(session: Session) -> list[dict]:
    rows = session.query(Reminder).filter(Reminder.done == False).order_by(Reminder.due_at).limit(300).all()  # noqa: E712
    return [{"id": r.id, "text": r.text, "due_at": r.due_at, "done": r.done, "entry_id": r.entry_id, "priority": r.priority} for r in rows]


def events(session: Session, question: str, history: list[dict], *, now: datetime, seed: str, open_ids: list[int],
           follow_kind: str = "", said: str = "", asked: str = "", ask: bool = False, voice: str = "natural") -> list[dict] | None:
    """The answer events for a question this module reads, else None. A
    failure is logged and leaves the question to the older readers."""
    #: "Summarise this" and "summarise Travel" read the open note or a whole
    #: category, which the digest does better than a title match here.
    if composer_digest.about_this(question) or composer_digest.named_category(
        question, list(session.execute(select(Category.name)).scalars())
    ):
        return None
    #: "Summarise my week" is the week's recap (`ai/activity`), not a note's summary.
    if activity.as_recap(question) != question:
        return None
    ctx = Ctx(question=question, notes=_notes(session), now=now, history=history, seed=seed, open_ids=open_ids,
              follow_kind=follow_kind, said=said, asked=asked or question, ask=ask, reminders=_reminders(session), voice=voice)
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


def welcome_line(session: Session, now: datetime, *, question: str = "", voice: str = "natural", seed: str = "", said: list[str] | None = None, link: bool = False) -> str:
    """The composed welcome (CHAT_PLAN 1353): the time of day, the reminders
    due today, the title of the last note and the writing streak, built by the
    composition layer in the person's voice. A failure to count anything
    leaves that clause out; it never fails the greeting."""
    from tessellate.ai import composer_compose, greeting_compose, study

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
    #: "N due today" is the dashboard's count: every open reminder due before
    #: tomorrow, an overdue one included.
    tomorrow = now.date() + timedelta(days=1)
    due = sum(1 for r in _reminders(session) if hasattr(r["due_at"], "date") and r["due_at"].date() < tomorrow)
    last = study.title_of(notes[0]["content"]) if notes else ""
    mood = composer_compose.mood_of(question, voice=voice, seed=seed, said=said or [], intent="welcome")
    #: In Chat the last note is a link the client opens (INBOX 1485: "didnt
    #: reference the note and no link or source was shown?").
    href = f"#/notes/{notes[0]['id']}" if link and notes else ""
    return composer_compose.welcome(mood, hour=now.hour, due=due, last=realise.cut_title(last, 60), streak=facts.streak, notes=total, question=question, last_href=href)


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
