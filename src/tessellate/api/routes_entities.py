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
from sqlalchemy.orm import Session

from tessellate.ai.entities import MergeUndoError, merge_with_undo, undo_merge
from tessellate.core.database import ENTITY_KINDS, Entity, Entry
from tessellate.core.deps import get_session
from tessellate.entry.manager_text import plain_label
from tessellate.entry.mentions import sentence_around
from tessellate.repo import entities as entities_repo
from tessellate.repo import relations as relations_repo
from tessellate.repo import reminders as reminders_repo

router = APIRouter(prefix="/entities", tags=["entities"])

#: Rows on a page: a person named in four hundred notes has said enough in
#: the newest sixty, and the list under it is the notes, a click away.
PAGE_MENTIONS = 60
PAGE_RELATED = 12
PAGE_DATES = 20
LIST_MAX = 500


def _visible_ids(session: Session) -> set[int]:
    return entities_repo.visible_note_ids(session)


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
    entity = entities_repo.find(session, entity_id)
    for _ in range(10):
        if entity is None or entity.merged_into is None:
            break
        entity = entities_repo.find(session, entity.merged_into)
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
    rows = [_row(entity, count) for entity, count in entities_repo.named_with_counts(session)]
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
    note_ids = [i for i in entities_repo.note_ids_naming(session, entity.id) if i in visible]
    if not note_ids:
        # The list hides an entity no visible note names; so does its page. The
        # name was lifted from a note while it was readable, and by id it would
        # otherwise outlive that note going private (sweep 1004).
        raise HTTPException(status_code=404, detail="That name could not be found.")
    notes = entities_repo.notes_by_ids(session, note_ids)
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
    for other, _entry_id in entities_repo.mention_pairs(session, note_ids):
        if other != entity.id:
            related[other] += 1
    others = entities_repo.by_ids(session, list(related))
    related_rows = [
        {**_row(others[i], n), "notes": n}
        for i, n in sorted(related.items(), key=lambda kv: (-kv[1], others[kv[0]].name.casefold()))
        if i in others and others[i].merged_into is None
    ][:PAGE_RELATED]
    dates = [
        {"entry_id": d.entry_id, "phrase": d.phrase, "at": d.at.isoformat(), "precision": d.precision}
        for d in entities_repo.dates_in(session, note_ids, PAGE_DATES)
    ]
    seen = [e.created_at for e in notes.values() if e.created_at]
    return {
        **_row(entity, len(notes)),
        "mentions": mentions,
        "related": related_rows,
        "dates": dates,
        "open_items": _open_items(session, entity, notes, names),
        "timeline": _timeline(notes),
        "links": _linked_notes(session, notes, visible),
        "first_seen": min(seen).isoformat() if seen else None,
        "last_seen": max(seen).isoformat() if seen else None,
    }


#: WORLD_CLASS B4: what makes the page a person's or a project's.
PAGE_OPEN_ITEMS = 30
PAGE_MONTHS = 24
PAGE_MONTH_NOTES = 3
PAGE_LINKS = 12
#: A markdown task line, the shape the editor writes (`entry/meetings.py`).
_TASK = re.compile(r"^[ \t]*(?:[-*+]|\d{1,3}[.)])[ \t]+\[([ xX])\][ \t]*(.*)$")


def _names_line(line: str, names: list[str]) -> bool:
    """Whether a line says one of the names, or `@` and its first word (the
    app's way of naming the owner of a task: "Sam Lee" is written `@Sam`)."""
    if _hit(line, names):
        return True
    firsts = {n.split()[0].casefold() for n in names if n.split()}
    return any(m.casefold() in firsts for m in re.findall(r"(?<![\w@])@([A-Za-z][\w.'-]{0,39})", line))


def _open_items(session: Session, entity: Entity, notes: dict, names: list[str]) -> list[dict]:
    """The unticked tasks in its notes and the reminders on them, not finished.
    A person's page keeps only the task lines and reminders that name them: a meeting note
    that names Sam holds ten tasks, and two are Sam's; a project's notes are
    about the project, so every open task in them is the project's."""
    only_named = entity.kind == "person"
    items: list[dict] = []
    for entry in sorted(notes.values(), key=lambda e: e.created_at, reverse=True):
        title = plain_label(entry.content or "", 60) or "Untitled note"
        for line in (entry.content or "").splitlines():
            m = _TASK.match(line)
            text = " ".join(m.group(2).split()) if m and m.group(1) == " " else ""
            if text and (not only_named or _names_line(text, names)):
                items.append({"kind": "task", "entry_id": entry.id, "title": title, "text": text})
    reminders = reminders_repo.open_on_notes(session, list(notes))
    items += [
        {"kind": "reminder", "id": r.id, "entry_id": r.entry_id, "text": r.text, "due_at": r.due_at.isoformat()}
        for r in reminders
        if not only_named or _names_line(r.text, names)
    ]
    return items[:PAGE_OPEN_ITEMS]


def _timeline(notes: dict) -> list[dict]:
    """Its notes by the month they were written, newest month first, each
    with its newest few notes: when it came up, and how much."""
    months: dict[str, list[Entry]] = {}
    for entry in sorted(notes.values(), key=lambda e: e.created_at, reverse=True):
        if entry.created_at:
            months.setdefault(entry.created_at.strftime("%Y-%m"), []).append(entry)
    return [
        {
            "month": month,
            "count": len(rows),
            "notes": [{"id": e.id, "title": plain_label(e.content or "", 60) or "Untitled note"} for e in rows[:PAGE_MONTH_NOTES]],
        }
        for month, rows in sorted(months.items(), reverse=True)[:PAGE_MONTHS]
    ]


def _linked_notes(session: Session, notes: dict, visible: set[int]) -> list[dict]:
    """The notes a link joins to its notes and that do not name it, most
    joined first: the wiring diagram a project's plan links to belongs on
    the project's page even though it never says the project's name."""
    if not notes:
        return []
    ids = list(notes)
    joined: Counter[int] = Counter()
    for source, target in relations_repo.touching_any(session, set(ids)):
        other = target if source in notes else source
        if other not in notes and other in visible:
            joined[other] += 1
    top = sorted(joined.items(), key=lambda kv: (-kv[1], kv[0]))[:PAGE_LINKS]
    rows = entities_repo.notes_by_ids(session, [i for i, _ in top])
    return [
        {"id": i, "title": plain_label(rows[i].content or "", 60) or "Untitled note", "links": n}
        for i, n in top if i in rows
    ]


def names_in_note(session: Session, entry: Entry) -> list[dict]:
    """The people, projects and things a note names, for its Connections
    (B4: a page reachable from the mention). A private note lends no names."""
    if entry.is_private:
        return []
    ids = entities_repo.entity_ids_in_note(session, entry.id)
    named = {}
    for entity_id in ids:
        try:
            live = _live(session, entity_id)
        except HTTPException:
            continue
        named[live.id] = live
    return [
        {"id": e.id, "name": e.name, "kind": e.kind}
        for e in sorted(named.values(), key=lambda e: e.name.casefold())
    ]


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
