"""Notes by the order they were made (INBOX 1345 b): "the first note I ever
wrote", "my newest note", "the 5th note I wrote", "my 3rd most recent note".

Retrieval cannot answer these (no note is *like* "first"), so they are read
off the creation column, exactly, with no model. One reader serves the Chat
composer, the Agent popup and the Statistics Ask box; the sentence is complete
on its own. Deleted notes, drafts, private notes and boards are not counted,
as in `ai/filters.resolve`.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import Entry

_WORDS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
    "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12,
}
_NTH = r"(?P<n>\d{1,6}(?:st|nd|rd|th)|" + "|".join(_WORDS) + r")"
_BACK = r"(?:most recent|newest|latest|last)"
_NOUN = r"(?:note|entry)\b"
#: A subject after the noun ("my first note about Harbor") makes it a search.
_AFTER = re.compile(r"\b(?:about|mention(?:s|ing)?|tagged|on|with|titled|called|containing)\s+\S")

_ORDINAL = re.compile(rf"\b{_NTH}\s+(?P<back>{_BACK}\s+)?{_NOUN}")
_END = re.compile(rf"\b(?P<end>oldest|earliest|{_BACK}|first)\s+{_NOUN}")
_DID = re.compile(r"\bwhat (?:did|have) i (?:write|wrote|make|made|add|save|put down)\s+(?P<end>first|last)\b")


class Ask(NamedTuple):
    """Which note: the `n`th from the oldest, or from the newest when `newest`."""

    n: int
    newest: bool


def read(question: str) -> Ask | None:
    """The ordinal a question asks for, or None when it asks for something else."""
    text = " ".join((question or "").lower().split())
    found = _ORDINAL.search(text)
    if found and not _AFTER.search(text[found.end():]):
        word = found.group("n")
        return Ask(_WORDS.get(word) or int(word[:-2]), bool(found.group("back")))
    found = _END.search(text)
    if found and not _AFTER.search(text[found.end():]):
        return Ask(1, found.group("end") not in ("oldest", "earliest", "first"))
    found = _DID.search(text)
    if found:
        return Ask(1, found.group("end") == "last")
    return None


def _live(query):  # noqa: ANN001, ANN202
    return query.where(
        Entry.is_deleted.is_(False), Entry.deleted_at.is_(None), Entry.is_draft.is_(False), Entry.is_private.is_(False), Entry.is_board.is_(False)
    )


def count(session: Session) -> int:
    return int(session.scalar(_live(select(func.count(Entry.id)))) or 0)


def nth(session: Session, ask: Ask) -> Entry | None:
    """The note at that place in the creation order, or None past the end."""
    order = (Entry.created_at.desc(), Entry.id.desc()) if ask.newest else (Entry.created_at.asc(), Entry.id.asc())
    return session.scalars(_live(select(Entry)).order_by(*order).offset(ask.n - 1).limit(1)).first()


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _which(ask: Ask) -> str:
    if ask.n == 1:
        return "newest" if ask.newest else "first"
    return f"{_ordinal(ask.n)} most recent" if ask.newest else _ordinal(ask.n)


def date_in_words(made: datetime, zone=None) -> str:  # noqa: ANN001
    made = made if made.tzinfo else made.replace(tzinfo=timezone.utc)
    made = made.astimezone(zone)
    return f"{made.day} {made.strftime('%B %Y')}"


def say(session: Session, ask: Ask, zone=None, linked: bool = True) -> tuple[str, int | None]:  # noqa: ANN001
    """(the sentence, the note's id or None). `linked` writes the title as the
    app's note link; the Statistics box shows plain words."""
    from tessellate.ai import questions, tool_say

    total = count(session)
    if total == 0:
        return "You have no notes yet.", None
    row = nth(session, ask)
    if row is None:
        noun = "note" if total == 1 else "notes"
        return f"You have {total} {noun}, so there is no {_which(ask)} one.", None
    title = questions._title(row.content) or "Untitled"
    shown = tool_say.link(title, tool_say.note_at(row.id)) if linked else title
    return f"Your {_which(ask)} note is from {date_in_words(row.created_at, zone)}: {shown}", row.id
