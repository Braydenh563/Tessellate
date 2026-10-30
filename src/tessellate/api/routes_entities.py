"""The entity layer's own routes (GRAPH_PLAN KG5, INBOX 528).

An entity (a person, place, project, organisation or thing a model found
named in the notes) had a name and its mentions, and nowhere to be looked at:
it was a node on the graph that could not be opened. This is its page (where
it is said, in the sentence that says it; what it is named with; the dates
its notes resolve), its list, and the hand edits a model's guesses need:
a kind, a rename, other names, a merge.

A private note lends nothing here: not a mention, not a sentence, not a date,
not a co-mention.
"""

from __future__ import annotations

import re
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.ai.entities import MergeUndoError, merge_with_undo, undo_merge
from tessellate.core.database import ENTITY_KINDS, Entity, EntityMention, Entry, EntryDate
from tessellate.core.deps import get_session
from tessellate.entry.manager import plain_label
from tessellate.entry.mentions import sentence_around

router = APIRouter(prefix="/entities", tags=["entities"])

#: Rows on a page: a person named in four hundred notes has said enough in
#: the newest sixty, and the list under it is the notes, a click away.
PAGE_MENTIONS = 60
PAGE_RELATED = 12
PAGE_DATES = 20
LIST_MAX = 500


def _visible_ids(session: Session) -> set[int]:
    return set(
        session.scalars(select(Entry.id).where(Entry.is_deleted.is_(False), Entry.is_private.is_(False)))
    )


def _row(entity: Entity, notes: int) -> dict:
    return {
        "id": entity.id,
        "name": entity.name,
        "kind": entity.kind,
        "aliases": list(entity.aliases or []),
        "notes": notes,
    }


def _live(session: Session, entity_id: int) -> Entity:
    """The entity, or the one a merge folded it into; 404 if neither."""
    entity = session.get(Entity, entity_id)
    for _ in range(10):
        if entity is None or entity.merged_into is None:
            break
        entity = session.get(Entity, entity.merged_into)
    if entity is None or entity.merged_into is not None:
        raise HTTPException(status_code=404, detail="That name could not be found.")
    return entity


@router.get("")
def list_entities(
    response: Response,
    limit: int = Query(default=LIST_MAX, ge=1, le=LIST_MAX),
    session: Session = Depends(get_session),
) -> list[dict]:
    """Every entity some visible note names, most named first. Counted in
    SQL (audit 1028 K31: every mention row was read and counted in Python on
    each call, whatever the limit)."""
    notes = func.count(func.distinct(EntityMention.entry_id))
    named = (
        select(Entity, notes)
        .join(EntityMention, EntityMention.entity_id == Entity.id)
        .join(Entry, Entry.id == EntityMention.entry_id)
        .where(Entity.merged_into.is_(None), Entry.is_deleted.is_(False), Entry.is_private.is_(False))
        .group_by(Entity.id)
    )
    rows = [_row(entity, count) for entity, count in session.execute(named)]
    rows.sort(key=lambda r: (-r["notes"], r["name"].casefold()))
    response.headers["X-Total-Count"] = str(len(rows))
    return rows[:limit]


def _hit(content: str, names: list[str]) -> tuple[int, int] | None:
    """The first place the text says any of the names, as written, whole
    words only (so "Sam" is not found in "Samples")."""
    best: tuple[int, int] | None = None
    for name in names:
        if not name:
            continue
        match = re.search(rf"(?<!\w){re.escape(name)}(?!\w)", content, re.IGNORECASE)
        if match and (best is None or match.start() < best[0]):
            best = match.span()
    return best


@router.get("/{entity_id}")
def entity_page(entity_id: int, session: Session = Depends(get_session)) -> dict:
    """An entity's page: its mentions in context, the entities named with
    it, and the dates its notes resolve."""
    entity = _live(session, entity_id)
    visible = _visible_ids(session)
    note_ids = [
        i for i in session.scalars(select(EntityMention.entry_id).where(EntityMention.entity_id == entity.id))
        if i in visible
    ]
    if not note_ids:
        # The list hides an entity no visible note names; so does its page. The
        # name was lifted from a note while it was readable, and by id it would
        # otherwise outlive that note going private (sweep 1004).
        raise HTTPException(status_code=404, detail="That name could not be found.")
    notes = {
        e.id: e for e in session.scalars(select(Entry).where(Entry.id.in_(note_ids)))
    } if note_ids else {}
    # Longest name first, so "Sam Lee" is marked whole rather than its "Sam".
    names = sorted({entity.name, *(entity.aliases or [])}, key=len, reverse=True)
    mentions = []
    for entry in sorted(notes.values(), key=lambda e: e.created_at, reverse=True)[:PAGE_MENTIONS]:
        content = entry.content or ""
        span = _hit(content, names)
        if span:
            context, start, end = sentence_around(content, *span)
        else:
            # The model named it loosely ("the kiln" for "Kiln two"): the
            # note's opening words, nothing marked, rather than no row.
            context, start, end = plain_label(content, 160) or "", 0, 0
        mentions.append(
            {
                "kind": "note",
                "id": entry.id,
                "title": plain_label(content, 60) or "Untitled note",
                "context": context,
                "hit_start": start,
                "hit_end": end,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
            }
        )
    related: Counter[int] = Counter()
    if note_ids:
        for other, entry_id in session.execute(
            select(EntityMention.entity_id, EntityMention.entry_id).where(EntityMention.entry_id.in_(note_ids))
        ):
            if other != entity.id:
                related[other] += 1
    others = {
        e.id: e for e in session.scalars(select(Entity).where(Entity.id.in_(list(related))))
    } if related else {}
    related_rows = [
        {**_row(others[i], n), "notes": n}
        for i, n in sorted(related.items(), key=lambda kv: (-kv[1], others[kv[0]].name.casefold()))
        if i in others and others[i].merged_into is None
    ][:PAGE_RELATED]
    dates = [
        {"entry_id": d.entry_id, "phrase": d.phrase, "at": d.at.isoformat(), "precision": d.precision}
        for d in session.scalars(
            select(EntryDate).where(EntryDate.entry_id.in_(note_ids)).order_by(EntryDate.at).limit(PAGE_DATES)
        )
    ] if note_ids else []
    seen = [e.created_at for e in notes.values() if e.created_at]
    return {
        **_row(entity, len(notes)),
        "mentions": mentions,
        "related": related_rows,
        "dates": dates,
        "first_seen": min(seen).isoformat() if seen else None,
        "last_seen": max(seen).isoformat() if seen else None,
    }


class EntityPatch(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    kind: str | None = Field(default=None, max_length=16)
    aliases: list[str] | None = Field(default=None, max_length=50)


@router.patch("/{entity_id}")
def patch_entity(entity_id: int, body: EntityPatch, session: Session = Depends(get_session)) -> dict:
    """A kind, a better name, other names. Only the fields sent change; an
    empty kind clears it."""
    entity = _live(session, entity_id)
    sent = body.model_fields_set
    if "name" in sent:
        name = (body.name or "").strip()
        if not name:
            raise HTTPException(status_code=422, detail="A name can't be empty.")
        entity.name = name
    if "kind" in sent:
        kind = (body.kind or "").strip().lower() or None
        if kind is not None and kind not in ENTITY_KINDS:
            raise HTTPException(status_code=422, detail="That isn't a kind this notebook knows.")
        entity.kind = kind
    if "aliases" in sent:
        seen = {entity.name.casefold()}
        aliases = []
        for alias in body.aliases or []:
            alias = " ".join(alias.split())[:200]
            if alias and alias.casefold() not in seen:
                seen.add(alias.casefold())
                aliases.append(alias)
        entity.aliases = aliases or None
    session.commit()
    return _row(entity, 0)


class MergeInto(BaseModel):
    into_id: int


@router.post("/{entity_id}/merge")
def merge_into(entity_id: int, body: MergeInto, session: Session = Depends(get_session)) -> dict:
    """Fold this entity into another by hand: every mention follows, and its
    names become the other's aliases."""
    gone, keep = _live(session, entity_id), _live(session, body.into_id)
    if gone.id == keep.id:
        raise HTTPException(status_code=400, detail="That is one name already.")
    moved, undo_id = merge_with_undo(session, keep, gone)
    session.commit()
    return {"kept": keep.id, "name": keep.name, "aliases": keep.aliases or [], "moved": moved, "undo_id": undo_id}


@router.post("/merges/{undo_id}/undo")
def undo_merge_route(undo_id: int, session: Session = Depends(get_session)) -> dict:
    """Split a merge back as it was (INBOX 553(a)): both names, their
    aliases and kinds, and every mention on the side it came from."""
    try:
        back = undo_merge(session, undo_id)
    except MergeUndoError as exc:
        if exc.reason == "missing":
            raise HTTPException(status_code=404, detail="That merge could not be found.") from exc
        if exc.reason == "undone":
            raise HTTPException(status_code=409, detail="That merge was already undone.") from exc
        raise HTTPException(
            status_code=409, detail="These names have changed since the merge, so it can't be undone."
        ) from exc
    session.commit()
    return {"restored": back.id, "name": back.name}
