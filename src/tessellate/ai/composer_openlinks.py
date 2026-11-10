"""What is linked to the note just opened or answered (F13 j, fable-composer-1110).

"what links to it", "what's related" and "why are they linked" lean on a note, not on a
word: "it" is the note open in the page, else the one the last answer was about. They
were searched as the word "links". The answer is the stored links (`repo/relations`),
each with the reason its maker gave, from notes the person can see; nothing here writes.
None when the turn asks none of this or names no note to ask of.
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from tessellate.ai import composer_frame
from tessellate.ai.tools._common import _visible
from tessellate.core.database import Entry
from tessellate.repo import relations

_LEAD = r"^\s*(?:(?:and|so|ok|okay|then|now)[, ]+)*"
_THIS = r"(?:it|this|that|this note|that note|them|these|those)"
_LINKS = re.compile(
    _LEAD + r"(?:what|which notes?|which)(?: else)?(?:'s| is| are)? (?:linked|links?|connected|connects?|related|relates|joined|points?) (?:back )?(?:to|with)\s+" + _THIS + r"\s*[?.!]*$"
    r"|" + _LEAD + r"what(?:'s| is| are)? (?:linked|related|connected)\s*[?.!]*$"
    r"|" + _LEAD + r"what links here\s*[?.!]*$",
    re.I,
)
_WHY = re.compile(_LEAD + r"why (?:is|are) (?:they|these|those|it|the two|the notes) (?:linked|connected|related|joined)(?: together)?\s*[?.!]*$", re.I)


def _subject(session: Session, history: list[dict], open_ids: list[int]) -> list[int]:
    """The notes "it" is: the open note, else the last answer's own, rechecked as visible."""
    frame = next((t.get("frame") for t in reversed(history or []) if isinstance(t, dict) and t.get("frame")), None) or {}
    wanted = [i for i in [*open_ids, *(frame.get("note_ids") or [])] if isinstance(i, int)]
    seen = {i for (i,) in session.query(Entry.id).filter(Entry.id.in_(wanted or [0]), *_visible())}
    return [i for i in dict.fromkeys(wanted) if i in seen]


def _name_of(note: Entry) -> str:
    return composer_frame.note_title(note.content or "") or "Untitled"


def _ref(note: Entry) -> str:
    return f"[**{_name_of(note)}**](#/notes/{note.id})"


def _neighbours(session: Session, note_id: int) -> list[tuple[Entry, str]]:
    """(the note at the other end, the reason given) of every link of `note_id` whose other end is visible."""
    links = relations.touching(session, note_id)
    ends = {(link.target_entry_id if link.source_entry_id == note_id else link.source_entry_id): (link.reason or "").strip() for link in links}
    rows = session.query(Entry).filter(Entry.id.in_(ends or [0]), *_visible()).all()
    return [(row, ends[row.id]) for row in sorted(rows, key=lambda r: r.id)]


def _line(note: Entry, reason: str) -> str:
    return f"- {_ref(note)}" + (f": {composer_frame.reason_said(reason)}." if reason else "")


def _why(session: Session, ids: list[int]) -> str:
    """Why the two notes just shown are linked."""
    note, other = session.get(Entry, ids[0]), session.get(Entry, ids[1])
    reasons = [r for n, r in _neighbours(session, ids[0]) if n.id == ids[1]]
    if not reasons:
        return f"No link joins {_ref(note)} and {_ref(other)}."
    tail = f": {composer_frame.reason_said(reasons[0])}." if reasons[0] else ", with no reason given."
    return f"You linked {_ref(note)} to {_ref(other)}{tail}"


def _listed(session: Session, note_id: int, why: bool) -> str:
    note = session.get(Entry, note_id)
    found = _neighbours(session, note_id)
    if not found:
        return f"Nothing is linked to {_ref(note)} yet."
    if why:
        head = f"{_ref(note)} is linked to {len(found)} note{'s' if len(found) != 1 else ''}, each for its reason:"
    else:
        head = ("One note is" if len(found) == 1 else f"{len(found)} notes are") + f" linked to {_ref(note)}:"
    return "\n".join([head, "", *(_line(n, r) for n, r in found[:8])])


def answer(session: Session, typed: str, history: list[dict] | None, open_ids: list[int]) -> str | None:
    """The links of the note "it" is, or why the notes just shown are linked."""
    text = " ".join(str(typed or "").split())
    why = bool(_WHY.match(text))
    if not (why or _LINKS.match(text)):
        return None
    ids = _subject(session, history or [], list(open_ids or []))
    if not ids:
        return None
    return _why(session, ids) if why and len(ids) >= 2 else _listed(session, ids[0], why)
