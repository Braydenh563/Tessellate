"""The route's side of `ai/composer_extra.py` (INBOX 1351): load the notes and
reminders a study, plan or calculation answer reads, and turn its reply into
stream events. Kept out of `routes_chat.py`, which is large enough."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import composer_digest, composer_extra
from tessellate.ai.composer_study import Ctx
from tessellate.ai.tools._common import _visible
from tessellate.core.database import Category, Entry, Reminder

NOTE_LIMIT = 400
log = logging.getLogger("tessellate.chat")


def _notes(session: Session) -> list[dict]:
    rows = session.query(Entry.id, Entry.content, Entry.created_at).filter(*_visible()).order_by(Entry.created_at.desc()).limit(NOTE_LIMIT).all()
    return [{"id": i, "content": c or "", "created_at": made} for i, c, made in rows]


def _reminders(session: Session) -> list[dict]:
    rows = session.query(Reminder).filter(Reminder.done == False).order_by(Reminder.due_at).limit(300).all()  # noqa: E712
    return [{"id": r.id, "text": r.text, "due_at": r.due_at, "done": r.done, "entry_id": r.entry_id, "priority": r.priority} for r in rows]


def events(session: Session, question: str, history: list[dict], *, now: datetime, seed: str, open_ids: list[int],
           follow_kind: str = "", said: str = "", asked: str = "", ask: bool = False) -> list[dict] | None:
    """The answer events for a question this module reads, else None. A
    failure is logged and leaves the question to the older readers."""
    #: "Summarise this" and "summarise Travel" read the open note or a whole
    #: category, which the digest does better than a title match here.
    if composer_digest.about_this(question) or composer_digest.named_category(
        question, list(session.execute(select(Category.name)).scalars())
    ):
        return None
    ctx = Ctx(question=question, notes=_notes(session), now=now, history=history, seed=seed, open_ids=open_ids,
              follow_kind=follow_kind, said=said, asked=asked or question, ask=ask, reminders=_reminders(session))
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
