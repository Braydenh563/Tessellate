"""The notes a computed answer reads (`ai/composer_lists.py`).

A search returns five notes ranked by likeness. "List my work notes" is every
note filed there, "how many times did I mention Porto" is every note that says
Porto, and "what is due this week" reads the days in all of them, so each of
those loads its own pool instead of the five.
"""

from __future__ import annotations

import itertools

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from tessellate.ai import composer_lists
from tessellate.core.database import LIKE_ESCAPE, Category, Entry, like_escape

#: Notes read for one computed answer: the list's count and the mentions are
#: counted over these, so the cap is far above what a notebook files under one name.
LIST_LIMIT = composer_lists.POOL_LIMIT
#: The newest notes that carry a digit, for "what is due".
DATED_LIMIT = 300


def _live():  # noqa: ANN202
    return (Entry.is_deleted == False, Entry.is_private == False, Entry.is_board == False)  # noqa: E712


def _filed(session: Session, name: str, how: str) -> list[Entry]:
    key = name.lower().strip()
    variants = {key, key.rstrip("s"), key + "s"}  # the composer reads "work" and "works" alike
    clauses = []
    if how in ("tag", "either"):
        clauses += [func.lower(Entry.tags).like(f'%"{like_escape(v)}"%', escape=LIKE_ESCAPE) for v in variants]
    if how in ("category", "either"):
        named = [c.id for c in session.scalars(select(Category)) if c.name.lower() in variants]
        clauses.append(Entry.category_id.in_(named))
    return list(session.scalars(select(Entry).where(*_live(), or_(*clauses)).order_by(Entry.created_at.desc()).limit(LIST_LIMIT)))


def _mentioning(session: Session, question: str) -> list[Entry]:
    found = composer_lists.mention_subject(question)
    if not found:
        return []
    needle = found.lower()
    newest = select(Entry).where(*_live()).order_by(Entry.created_at.desc())
    if needle.isascii():
        return list(session.scalars(newest.where(func.lower(Entry.content).like(f"%{like_escape(needle)}%", escape=LIKE_ESCAPE)).limit(LIST_LIMIT)))
    # SQLite folds only ASCII case, so "Ünal" would never match "ünal": read the
    # newest notes and match in Python.
    hits = (e for e in session.scalars(newest.limit(LIST_LIMIT * 10)) if needle in str(e.content or "").lower())
    return list(itertools.islice(hits, LIST_LIMIT))


def _dated(session: Session) -> list[Entry]:
    return list(session.scalars(select(Entry).where(*_live(), Entry.content.op("GLOB")("*[0-9]*")).order_by(Entry.created_at.desc()).limit(DATED_LIMIT)))


def pool(session: Session, question: str, entries: list) -> list:
    """The notes the computed answer for `question` reads, or `entries` when
    it is not one or its pool is empty (the search's own notes then answer)."""
    which = composer_lists.kind(question)
    if which == "listed":
        found = _filed(session, *composer_lists.list_target(question))
    elif which == "mentions":
        found = _mentioning(session, question)
    elif which == "dates":
        found = _dated(session)
    else:
        return entries
    if which == "mentions" and not found:
        return []  # nothing says it: the search's five near misses would be quoted as if they did
    have = {e.id for e in found}
    return found + [e for e in entries if e.id not in have] if found else entries
