"""The database half of `link_wording`: two notes' facts and the notebook's
counts, read once and kept (INBOX 691).

`manager._deduce_reason` asks `reason_for` every time it links two notes, so
the notebook's counts (how many notes hold each tag, name and word) are
built once per notebook state and reused: the key is the scope and a cheap
stamp (how many notes, the newest edit), so a new or edited note rebuilds
them and nothing else does. Measured on the 77-note showcase: 4 ms to build.

Imports nothing that imports `manager`, for the reason `link_wording` gives.
"""

from __future__ import annotations

import json
import logging
import threading

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import Category, Entity, EntityMention, Entry, writes
from tessellate.entry import link_wording

_lock = threading.Lock()
_cache: dict[object, tuple[tuple, link_wording.Counts]] = {}


def _scope_key(session: Session) -> object:
    return session.info.get("workspace_id") or "*"


def _live():  # noqa: ANN202
    return (Entry.is_deleted == False, Entry.is_private == False, Entry.is_board == False)  # noqa: E712


def _tags(raw: str | None) -> tuple[str, ...]:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return ()
    return tuple(str(t) for t in value if t) if isinstance(value, list) else ()


def notes(session: Session, ids: list[int] | None = None) -> dict[int, link_wording.PairNote]:
    """`PairNote`s for the live, non-private notes (all, or `ids`). A private
    note has no facts here: its text is ciphertext at rest, and a reason
    built from it would put its words into a plain column."""
    query = select(Entry.id, Entry.content, Entry.tags, Entry.category_id, Entry.created_at).where(*_live())
    if ids is not None:
        query = query.where(Entry.id.in_(ids))
    rows = session.execute(query).all()
    if not rows:
        return {}
    cats = dict(session.execute(select(Category.id, Category.name)).all())
    wanted = [r.id for r in rows]
    ents: dict[int, set[str]] = {}
    for entry_id, name in session.execute(
        select(EntityMention.entry_id, Entity.name)
        .join(Entity, Entity.id == EntityMention.entity_id)
        .where(EntityMention.entry_id.in_(wanted))
    ):
        ents.setdefault(entry_id, set()).add(name)
    return {
        r.id: link_wording.PairNote(
            id=r.id,
            text=r.content or "",
            tags=_tags(r.tags),
            category=cats.get(r.category_id),
            created_at=r.created_at,
            entities=frozenset(ents.get(r.id, ())),
        )
        for r in rows
    }


def counts(session: Session) -> link_wording.Counts:
    """The notebook's clue counts, rebuilt only when a note was added,
    removed or edited since the last build."""
    stamp = (
        writes(Entry),
        *session.execute(select(func.count(Entry.id), func.max(Entry.id), func.max(Entry.updated_at)).where(*_live())).one(),
    )
    key = _scope_key(session)
    with _lock:
        hit = _cache.get(key)
        if hit and hit[0] == stamp:
            return hit[1]
    built = link_wording.Counts.of(notes(session).values())
    with _lock:
        _cache[key] = (stamp, built)
    return built


def forget() -> None:
    """Drop the kept counts (tests, a restored backup)."""
    with _lock:
        _cache.clear()


def reason_for(session: Session, source_id: int, target_id: int) -> str | None:
    """The specific reason for linking two notes, or None (the caller keeps
    the generic one). Never raises: a reason is never worth a failed link."""
    try:
        pair = notes(session, [source_id, target_id])
        if source_id not in pair or target_id not in pair:
            return None
        return link_wording.specific_reason(pair[source_id], pair[target_id], counts(session))
    except Exception:  # noqa: BLE001  # a wording failure falls back to the generic reason
        logging.getLogger(__name__).debug("reason_for: a wording failure falls back to the generic reason", exc_info=True)
        return None
