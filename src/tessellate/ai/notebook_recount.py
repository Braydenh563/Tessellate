"""Recount a `notebook_stats.Measure` from its `derived_from` query (CHAT_PLAN A16, L-chat-93): the eval and
the tests re-derive a number a handler stated instead of trusting its prose. None when the source is only a label."""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.ai import composer_frame
from tessellate.ai.notebook_stats import Measure, StatAnswer, _tags_of, _visible
from tessellate.core.database import Category, Document, Entry, EntryLink


def _filtered(session: Session, source: str) -> int | None:
    from tessellate.ai import notebook_filters

    said = notebook_filters.count(session, notebook_filters.parse(source), _visible)
    return None if said is None else int(said[1][0]["count"])


def _tagged(session: Session, rows: list, name: str) -> int:
    return sum(1 for e in rows if name.lower() in {t.lower() for t in _tags_of(e.tags)})


def _categorised(session: Session, rows: list, name: str) -> int:
    cats = {c.id: c.name for c in session.scalars(select(Category)).all()}
    return sum(1 for e in rows if cats.get(e.category_id, "").lower() == name.lower())


def _mentioning(session: Session, rows: list, name: str) -> int:  # noqa: ARG001
    found = re.compile(rf"(?<!\w){re.escape(name)}(?:s|es)?(?!\w)", re.I)
    return sum(1 for e in rows if found.search(e.content or ""))


def _unlinked(session: Session, rows: list, name: str) -> int:  # noqa: ARG001
    linked = {i for pair in session.execute(select(EntryLink.source_entry_id, EntryLink.target_entry_id)).all() for i in pair}
    return sum(1 for e in rows if e.id not in linked)


#: One reader per `derived_from` kind: `(session, live rows, name) -> the number`.
_KINDS = {
    "notes": lambda _s, rows, _n: len(rows),
    "created": lambda _s, rows, _n: len(rows),
    "tag": _tagged,
    "category": _categorised,
    "mention": _mentioning,
    "untagged": lambda _s, rows, _n: sum(1 for e in rows if not _tags_of(e.tags)),
    "tags": lambda _s, rows, _n: len({t for e in rows for t in _tags_of(e.tags)}),
    "words": lambda _s, rows, _n: sum(composer_frame.note_words(e.content) for e in rows),
    "unlinked": _unlinked,
    "categories": lambda s, _r, _n: s.scalar(select(func.count(Category.id))) or 0,
    "documents": lambda s, _r, _n: s.scalar(select(func.count(Document.id))) or 0,
}


def _count(session: Session, source: str) -> int | None:
    if source.startswith("filter:"):
        return _filtered(session, source)
    base, _, window = source.partition("@")
    kind, _, name = base.partition(":")
    if kind not in _KINDS:
        return None
    query = _visible(select(Entry))
    if window:
        first, last = window.split("..")
        query = query.where(Entry.created_at >= datetime.fromisoformat(first), Entry.created_at <= datetime.fromisoformat(last))
    return _KINDS[kind](session, list(session.scalars(query).all()), name)


def recount(session: Session, measure: Measure) -> int | None:
    """The value `measure.derived_from` counts now, or None when it names no query."""
    return None if measure.derived_from.startswith("label:") else _count(session, measure.derived_from)


def holds(session: Session, answer: StatAnswer) -> bool:
    """Whether every recountable measure of the answer is what a fresh count gives."""
    return all((got := recount(session, m)) is None or got == m.value for m in answer.measures())
