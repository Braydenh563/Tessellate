"""A note then and now (CHAT_PLAN A17, L-chat-94): "what did I say about the trip then and now".

The note is the one the subject names; "then" is its oldest saved revision, "now" its text. The answer quotes
the first changed claim both ways (`timetravel.then_and_now`), or says the claims have not changed. None when
the turn does not ask it or no note with a past version is named.
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from tessellate.ai import composer_frame, timetravel
from tessellate.ai.tools._common import _visible
from tessellate.core.database import Entry, EntryRevision, like_escape, LIKE_ESCAPE

_ASK = re.compile(r"\b(?:then and now|now and then|then versus now|then vs\.? now|before and after)\b(?:\s+(?:about|on)\s+(?:the\s+)?(?P<tail>.+?))?\s*[?.!]*$|\babout\s+(?:the\s+)?(?P<name>.+?)\s+(?:then and now|now and then|before and after)\b", re.I)
_SUBJECT = re.compile(r"\b(?:say|said|write|wrote|written|note|noted|think|thought|know)\b.*?\b(?:about|on|of)\s+(?:the\s+|my\s+)?(?P<name>.+?)(?=\s+(?:then and now|now and then|before and after)\b)", re.I)


def answer(session: Session, typed: str) -> str | None:
    """The old and the current claim of the named note, or None."""
    text = " ".join(str(typed or "").lower().replace("?", " ").split())
    if not re.search(r"\b(?:then and now|now and then|before and after)\b", text):
        return None
    named = _SUBJECT.search(text)
    wanted = re.sub(r"\s+(?:notes?|plans?)$", "", named.group("name").strip()) if named else ""
    if not wanted:
        return None
    rows = session.query(Entry).filter(Entry.content.ilike(f"%{like_escape(wanted)}%", escape=LIKE_ESCAPE), *_visible()).order_by(Entry.updated_at.desc()).limit(20).all()
    for note in rows:
        first = session.query(EntryRevision).filter(EntryRevision.entry_id == note.id).order_by(EntryRevision.id).first()
        if first is not None and first.content != note.content:
            return _said(note, timetravel.then_and_now(first.content or "", note.content or ""))
    return None


def _said(note: Entry, found: dict) -> str:
    title = composer_frame.note_title(note.content or "") or "Untitled"
    first = next(iter(found["changed"]), None)
    if first is None:
        return f"**{title}** says the same now as it did when you first saved it."
    then = found["then"][first["then"]] if first["then"] is not None else ""
    now = found["now"][first["now"]] if first["now"] is not None else ""
    if then and now:
        return f"Then, **{title}** said “{then}” Now it says “{now}”"
    return f"Then, **{title}** said “{then}” and it is gone now." if then else f"Now **{title}** says “{now}” and it did not before."
