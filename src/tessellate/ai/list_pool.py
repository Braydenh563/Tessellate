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

from tessellate.ai import composer, composer_lists, composer_small, composer_versus, filed_name, resurface
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
    if key in filed_name.KEPT_WORDS:  # L254: a note headed "Goals" or "Shopping list" is one too
        clauses.append(func.lower(Entry.content).like(f"%{like_escape(key)}%", escape=LIKE_ESCAPE))  # narrowed by title below
    found = session.scalars(select(Entry).where(*_live(), or_(*clauses)).order_by(Entry.created_at.desc()).limit(LIST_LIMIT * 4))
    keep = (lambda e: _tagged(e, variants) or filed_name.titled(key, str(e.content or "").strip().split("\n")[0])) if key in filed_name.KEPT_WORDS else (lambda e: True)
    return [e for e in found if keep(e)][:LIST_LIMIT]


def _tagged(entry: Entry, variants: set[str]) -> bool:
    return any(f'"{v}"' in str(entry.tags or "").lower() for v in variants)


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


def _naming(session: Session, question: str) -> list[Entry]:
    """The notes that name every word of a "which trip is sooner" question's
    subject, as a word or the start of one ("bak" for "baking", "bake"): the
    search's five may leave out the oldest or the newest of them."""
    words = [w.rstrip("e") for w in composer_versus.subject_of(question) if len(w) > 2]
    if not words or not all(w.isascii() for w in words):
        return []
    clauses = [func.lower(Entry.content).like(f"%{like_escape(w)}%", escape=LIKE_ESCAPE) | func.lower(Entry.tags).like(f"%{like_escape(w)}%", escape=LIKE_ESCAPE) for w in words]
    return list(session.scalars(select(Entry).where(*_live(), *clauses).order_by(Entry.created_at.desc()).limit(LIST_LIMIT)))


def _leaving_out(session: Session, question: str) -> list[Entry]:
    """The notes a "notes about Tokyo but not Lisbon" answer reads: those that
    name every word of the subject kept (as a word or the start of one), or
    the newest of all when only a word is left out. The words left out are
    judged by the answer, which needs the notes that hold them too."""
    kept = (composer_lists.without_ask(question) or ("", ""))[0]
    words = [composer._stem(w).rstrip("e") for w in kept.split() if len(w) > 2]  # noqa: SLF001
    if any(not w.isascii() for w in words):
        return []
    clauses = [func.lower(Entry.content).like(f"%{like_escape(w)}%", escape=LIKE_ESCAPE) | func.lower(Entry.tags).like(f"%{like_escape(w)}%", escape=LIKE_ESCAPE) for w in words]
    return list(session.scalars(select(Entry).where(*_live(), *clauses).order_by(Entry.created_at.desc()).limit(LIST_LIMIT)))


def _in_order(session: Session, question: str) -> list[Entry]:
    """The notes at the end of the order asked, so "oldest first" holds the oldest."""
    first = Entry.created_at.asc() if composer_lists.list_order(question) == "oldest" else Entry.created_at.desc()
    return list(session.scalars(select(Entry).where(*_live()).order_by(first).limit(LIST_LIMIT)))


def _counting(session: Session, question: str) -> list[Entry]:
    """The notes a "my 2 latest baking notes" question counts from: those that
    name every word of its subject (as a word or the start of one, in the text
    or a tag), at the end of the order asked."""
    oldest, _, subject = composer_lists.counted_order(question) or (False, 0, "")
    words = [composer._stem(w).rstrip("e") for w in subject.split() if len(w) > 2]  # noqa: SLF001
    if any(not w.isascii() for w in words):
        return []
    clauses = [func.lower(Entry.content).like(f"%{like_escape(w)}%", escape=LIKE_ESCAPE) | func.lower(Entry.tags).like(f"%{like_escape(w)}%", escape=LIKE_ESCAPE) for w in words]
    first = Entry.created_at.asc() if oldest else Entry.created_at.desc()
    return list(session.scalars(select(Entry).where(*_live(), *clauses).order_by(first).limit(LIST_LIMIT)))


def _dated(session: Session) -> list[Entry]:
    return list(session.scalars(select(Entry).where(*_live(), Entry.content.op("GLOB")("*[0-9]*")).order_by(Entry.created_at.desc()).limit(DATED_LIMIT)))


def _of_kind(session: Session, kind: str) -> list[Entry]:
    """The newest notes that can be of `kind` (audit 1029 C34): a note with a
    tick box, a digit, or any note for a list (bullets are read in code)."""
    if kind == "dates":
        return _dated(session)
    newest = select(Entry).where(*_live()).order_by(Entry.created_at.desc())
    if kind == "tasks":
        newest = newest.where(or_(Entry.content.like("%[ ]%"), Entry.content.like("%[x]%")))
    if kind == "tables":
        newest = newest.where(Entry.content.like("%|%"))
    return list(session.scalars(newest.limit(LIST_LIMIT)))


def _faded(session: Session) -> list[Entry]:
    """The notes "show me something old" picks from: the most faded ones
    (`resurface.ranked`), else the oldest, when no score has been kept yet."""
    found = resurface.ranked(session, limit=composer_small.OLD_POOL)
    return found or list(session.scalars(select(Entry).where(*_live(), Entry.is_draft == False, Entry.archived_at.is_(None)).order_by(Entry.created_at.asc()).limit(composer_small.OLD_POOL)))  # noqa: E712


def _holding_words(session: Session, words: list[str]) -> list[Entry]:
    """The newest notes that hold every word of a "where did I write X" (by its
    stem, so "habits" meets "habit"): the search ranks by likeness and may not
    bring the note the words are in."""
    query = select(Entry).where(*_live(), Entry.is_draft == False, Entry.archived_at.is_(None))  # noqa: E712
    for word in words:
        query = query.where(func.lower(Entry.content).like(f"%{like_escape(composer_small.stem_of(word))}%", escape=LIKE_ESCAPE))
    return list(session.scalars(query.order_by(Entry.created_at.desc()).limit(composer_small.WHERE_POOL)))


def pool(session: Session, question: str, entries: list) -> list:
    """The notes the answer for `question` reads: the faded ones for "show me
    something old", the ones holding the words of a "where did I write", else
    the computed answer's (`_computed`)."""
    if composer_small.asks_old(question):
        return _faded(session) or entries
    if words := composer_small.where_asked(question):
        held = _holding_words(session, words)
        return held + [e for e in entries if e.id not in {h.id for h in held}] if held else entries
    return _computed(session, question, entries)


def _computed(session: Session, question: str, entries: list) -> list:
    """The notes the computed answer for `question` reads, or `entries` when
    it is not one or its pool is empty (the search's own notes then answer)."""
    which = composer_lists.computed_kind(question)
    if which == "listed":
        found = _filed(session, *composer_lists.list_target(question))
    elif which == "mentions":
        found = _mentioning(session, question)
    elif which == "without":
        found = _leaving_out(session, question)
    elif which == "ordered":
        found = _in_order(session, question)
    elif which == "which":
        found = _naming(session, question)
    elif which == "counted":
        found = _counting(session, question)
    elif which in ("dates", "due_for"):
        found = _dated(session)
    elif which == "holding":
        found = _of_kind(session, composer_lists.holding_ask(question)[0])  # type: ignore[index]
    else:
        return entries
    if which == "mentions" and not found:
        return []  # nothing says it: the search's five near misses would be quoted as if they did
    return _joined(found, entries, which, question)


def _joined(found: list, entries: list, which: str, question: str) -> list:
    """The computed pool, then the search's own notes; for "what are my goals"
    the goals alone, not the near misses (L254)."""
    have = {e.id for e in found}
    if found and which == "listed" and filed_name.kept_word(question):
        return found
    return found + [e for e in entries if e.id not in have] if found else entries
