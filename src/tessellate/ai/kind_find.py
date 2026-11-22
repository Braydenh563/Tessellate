"""Documents, boards and files asked for by what they are about or when they
were made (CHAT_PLAN section 8 row 3: "my documents about the harbor", "boards
from June", "files named invoice"), answered from the app's own rows with no
model. One reader, `read`, then `answer`: each row a link to where it opens,
the lead a count, nothing said that the rows do not hold. "Which documents do I
have" stays the list tool's; this takes the asks that name a subject or a time.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import composer_frame, realise, tool_say
from tessellate.core.lazyre import lazy_compile

_NOUNS = {"document": "document", "documents": "document", "doc": "document", "docs": "document", "board": "board", "boards": "board", "whiteboard": "board", "whiteboards": "board", "file": "file", "files": "file"}
_LEAD = lazy_compile(r"^(?:(?:can|could|would) you )?(?:please |pls )?(?:(?:show|list|find|get|open|pull up|give)(?: me)?|which|what|do i have|have i got|any)?\s*(?:of )?(?:(?:all|any|every) )?(?:(?:my|the) )?(?:(?:a|an|any) )?", re.I)
_ABOUT = lazy_compile(r"^(?:about|on|mentioning|mentions?|that mention|containing|contains?|with|named|called|titled|matching|for)\s+(?:the |my )?(.+)$", re.I)
_FILLER = frozenset("the a an my of and or to in is".split())


class Find(NamedTuple):
    kind: str  # document, board or file
    words: tuple[str, ...]
    window: tuple[date, date] | None
    phrase: str


def read(question: str, today: date) -> Find | None:
    """The kind, the subject words and the window an ask names; None when it
    names no subject and no time (the plain list) or is about something else."""
    text = re.sub(r"\s+", " ", (question or "").strip().rstrip("?.! ")).strip()
    got = _LEAD.match(text)
    rest = text[got.end():] if got else text
    head, _, tail = rest.partition(" ")
    kind = _NOUNS.get(head.lower())
    if not kind:
        return None
    tail = re.sub(r"^(?:do )?i have\b\s*", "", tail.strip(), flags=re.I).strip()
    if not tail:
        return None
    subject = _ABOUT.match(tail)
    window, phrase = _window(text, tail, today)
    if subject and not window:
        words = tuple(w for w in re.findall(r"[\w'’-]+", subject.group(1).lower()) if w not in _FILLER)
        return Find(kind, words, None, "") if words else None
    return Find(kind, (), window, phrase) if window else None


def _window(text: str, tail: str, today: date) -> tuple[tuple[date, date] | None, str]:
    """The time the ask names, said either as a phrase or as "from June"."""
    from tessellate.ai import composer

    plan = composer.plan(text, today)
    window = tuple(plan.window) if plan.window and plan.window_phrase else None
    if window is None and (found := re.match(r"^(?:from|in|made in|written in|edited in|updated in|created in)\s+(.+)$", tail, re.I)):
        plan = composer.plan(f"notes from {found.group(1)}", today)
        window = tuple(plan.window) if plan.window else None
    return window, plan.window_phrase or ""


def _in(window: tuple[date, date] | None, moment: datetime | None) -> bool:
    return window is None or (moment is not None and window[0] <= moment.date() <= window[1])


def _has(words: tuple[str, ...], *texts: str) -> bool:
    low = " ".join(texts).lower()
    return all(w in low for w in words)


Row = tuple[str, str, datetime | None]


def _document_rows(session: Session, find: Find) -> list[Row]:
    from tessellate.core.database import Document

    docs = session.scalars(select(Document).order_by(Document.updated_at.desc()))
    return [(d.title or "Untitled", tool_say.document_at(d.id), d.updated_at) for d in docs if _has(find.words, d.title or "", d.content or "") and _in(find.window, d.updated_at)]


def _board_rows(session: Session, find: Find) -> list[Row]:
    from tessellate.core.database import Entry

    out: list[Row] = []
    for e in session.scalars(select(Entry).where(Entry.is_board.is_(True), Entry.is_deleted.is_(False), Entry.is_private.is_(False)).order_by(Entry.updated_at.desc())):
        title = composer_frame.note_title(e.content) or "Untitled board"
        if _has(find.words, title, e.content or "") and _in(find.window, e.updated_at):
            out.append((title, tool_say.board_at(e.id), e.updated_at))
    return out


def _file_rows(session: Session, find: Find) -> list[Row]:
    from tessellate.ai import tools as agent_tools

    got = agent_tools.execute_tool(session, "search_files", {"query": " ".join(find.words)} if find.words else {})
    out: list[Row] = []
    for f in (got.get("files") if isinstance(got, dict) else None) or []:
        made = datetime.fromisoformat(f["created_at"]) if f.get("created_at") else None
        if _in(find.window, made):
            out.append((str(f.get("name") or "File"), tool_say.FILES, made))
    return sorted(out, key=lambda r: r[2] or datetime.min, reverse=True)


def _rows(session: Session, find: Find) -> list[Row]:
    """(title, address, when) for the rows that match, newest first."""
    return {"document": _document_rows, "board": _board_rows}.get(find.kind, _file_rows)(session, find)


def answer(session: Session, find: Find) -> tuple[str, str, dict]:
    """(lead, the list under it, the counts the lead was said from)."""
    rows = _rows(session, find)
    noun = {"document": "document", "board": "board", "file": "file"}[find.kind]
    about = f" about “{' '.join(find.words)}”" if find.words else ""
    when = f" from {find.phrase}" if find.phrase and not find.words else ""
    if not rows:
        return f"You have no {noun}s{about}{when}.", "", {noun: {"0"}}
    lead = f"You have {realise.count_noun(len(rows), noun)}{about}{when}" + (", newest first." if len(rows) > 1 else ".")
    body = realise.bullets([f"{tool_say.link(title, address)}" + (f" ({at:%-d %B %Y})" if at else "") for title, address, at in rows[:10]])
    return lead, body, {noun: {str(len(rows))}}
