"""A checklist said to be finished (CHAT_PLAN C9, L-chat-112): "I finished everything on my list".

The list is the one named ("the garden jobs list"), else the newest-touched note that holds boxes. A fully
ticked one is remarked on ("All 3 items on the Garden jobs list are ticked."); an open one is counted, never
cheered. None when the turn says nothing of the kind.
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from tessellate.ai import composer_frame
from tessellate.ai.notebook_tasks import _BOX
from tessellate.ai.tools._common import _visible
from tessellate.core.database import Entry

_FINISHED = re.compile(
    r"^\s*(?:i(?:'ve| have)?\s+)?(?:finished|completed|done|ticked off|crossed off)\s+(?:everything|all(?: of)?(?: the| my)?(?: items| tasks)?|it all|the (?:whole )?list)"
    r"(?:\s+(?:on|in|from|of)\s+(?:my|the)\s+(?P<name>[\w' -]+?))?\s*[.!]*$",
    re.I,
)


def _list_of(session: Session, name: str) -> Entry | None:
    rows = session.query(Entry).filter(Entry.content.contains("["), *_visible()).order_by(Entry.updated_at.desc()).limit(80).all()
    rows = [r for r in rows if _BOX.search(r.content or "")]
    wanted = re.sub(r"\s*(?:check)?list$", "", name or "", flags=re.I).strip().casefold()
    if wanted:
        rows = [r for r in rows if wanted in composer_frame.note_title(r.content or "").casefold()]
    return rows[0] if rows else None


def remark(content: str) -> str | None:
    """"All 3 items on the **Garden jobs** list are ticked." when every box of this note's text is ticked, else None."""
    marks = _BOX.findall(content or "")
    if not marks or " " in marks:
        return None
    return f"All {len(marks)} items on {_named(content)} are ticked."


def _named(content: str) -> str:
    title = composer_frame.note_title(content or "") or "Untitled"
    return f"**{title}**" if re.search(r"list$", title, re.I) else f"the **{title}** list"


def finished(session: Session, typed: str) -> str | None:
    """The remark, or the count of what is still open, for a list said to be done."""
    said = _FINISHED.match(typed or "")
    note = _list_of(session, said.group("name") or "") if said else None
    if note is None:
        return None
    marks = _BOX.findall(note.content or "")
    return remark(note.content) or f"Not yet: {marks.count(' ')} of the {len(marks)} items on {_named(note.content)} are still open."
