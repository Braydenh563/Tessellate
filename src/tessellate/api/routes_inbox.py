"""The suggestions inbox (GRAPH_PLAN KG9 part two, INBOX 528).

One sheet holds four kinds of suggestion. Link suggestions
(`/entries/link-suggestions`) and tensions (`/entries/tensions`, a model
pass on demand) keep their own routes; this one gathers the other two, entity
merges and link types (`ai/inbox.py`), and takes their decisions. Every
accept and dismissal is a correction (`ai/learning.py`): a dismissal keeps
that suggestion from coming back, and both move what each signal is worth.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, select
from sqlalchemy.orm import Session

from tessellate.ai import inbox, learning
from tessellate.ai.entities import merge_with_undo
from tessellate.api.routes_mentions import note_names
from tessellate.core.database import LINK_TYPES, Entity, EntityMention, Entry
from tessellate.core.deps import get_session
from tessellate.repo import relations as relations_repo
from tessellate.entry import manager
from tessellate.entry.manager import WIKI_LINK, plain_label
from tessellate.entry.mentions import MENTION_MIN_TITLE_CHARS, backlink_spans, sentence_around

router = APIRouter(prefix="/suggestions", tags=["suggestions"])

#: Untyped links read per pass, newest first: an imported vault has
#: thousands, and the sheet shows twenty.
TYPE_SCAN_MAX = 2000
#: The learning's smoothing for the inbox's kinds (`learning.signal_weights`).
INBOX_PRIOR = 3.0


def _visible(session: Session) -> set[int]:
    """The ids of the notes a suggestion may name. **Ids, not rows**: this
    loaded every note as a whole ORM object to test membership, 27% of a
    1.2 s `/suggestions` at 5,000 notes that returned an empty list (audit
    2026-10-05, ARCH-11). The few notes a link-type row shows are read by id
    in `_types`."""
    return set(
        session.scalars(select(Entry.id).where(Entry.is_deleted.is_(False), Entry.is_private.is_(False)))
    )


def _merges(session: Session, visible: set[int]) -> list[dict]:
    notes: dict[int, set[int]] = {}
    for entity_id, entry_id in session.execute(select(EntityMention.entity_id, EntityMention.entry_id)):
        if entry_id in visible:
            notes.setdefault(entity_id, set()).add(entry_id)
    facts = [
        inbox.EntityFacts(id=e.id, name=e.name, notes=frozenset(notes[e.id]))
        for e in session.scalars(select(Entity).where(Entity.merged_into.is_(None)))
        if e.id in notes
    ]
    exclude = {
        frozenset((c.subject.get("a"), c.subject.get("b")))
        for c in learning.corrections(session, kind="dismiss_merge")
    }
    weights = learning.signal_weights(session, accept="accept_merge", dismiss="dismiss_merge", prior=INBOX_PRIOR)
    return inbox.merge_candidates(facts, exclude=exclude, weights=weights)


def _sentence(source: Entry, target: Entry) -> str:
    """The sentence in the source that links to (or names) the target."""
    content = source.content or ""
    names = {name.casefold() for name in note_names(target)}
    for match in WIKI_LINK.finditer(content):
        raw = match.group(1).split("|", 1)[0].split("#", 1)[0].strip().casefold()
        if raw in names:
            return sentence_around(content, *match.span())[0]
    for name in note_names(target):
        if len(name) >= MENTION_MIN_TITLE_CHARS:
            spans = backlink_spans(content, name)[1]
            if spans:
                return sentence_around(content, *spans[0])[0]
    return ""


def _types(session: Session, visible_ids: set[int]) -> list[dict]:
    facts = []
    links = relations_repo.untyped(session, limit=TYPE_SCAN_MAX)
    wanted = sorted(
        {end for link in links for end in (link.source_entry_id, link.target_entry_id) if end in visible_ids}
    )
    visible: dict[int, Entry] = {}
    for start in range(0, len(wanted), 500):
        visible.update(
            (e.id, e) for e in session.scalars(select(Entry).where(Entry.id.in_(wanted[start : start + 500])))
        )
    for link in links:
        source, target = visible.get(link.source_entry_id), visible.get(link.target_entry_id)
        if source is None or target is None:
            continue
        facts.append(
            inbox.LinkFacts(
                id=link.id,
                source_id=source.id,
                target_id=target.id,
                context=_sentence(source, target),
                reason=link.reason or "",
                deduced=link.reason_confidence is not None,
            )
        )
    exclude = {
        (c.subject.get("link_id"), c.subject.get("link_type"))
        for c in learning.corrections(session, kind="dismiss_link_type")
    }
    weights = learning.signal_weights(session, accept="accept_link_type", dismiss="dismiss_link_type", prior=INBOX_PRIOR)
    rows = inbox.type_candidates(facts, exclude=exclude, weights=weights)
    for row in rows:
        row["source_label"] = plain_label(visible[row["source_id"]].content, 60) or "Untitled note"
        row["target_label"] = plain_label(visible[row["target_id"]].content, 60) or "Untitled note"
    return rows


@router.get("")
def suggestions(session: Session = Depends(get_session)) -> dict:
    """Entity merges and link types to decide, surest first, twenty each."""
    visible = _visible(session)
    return {"merges": _merges(session, visible), "types": _types(session, visible)}


class MergeAccept(BaseModel):
    keep_id: int
    merge_id: int
    signals: list[Annotated[str, Field(max_length=40)]] = Field(default_factory=list, max_length=8)


class MergeDismiss(BaseModel):
    a: int
    b: int
    signals: list[Annotated[str, Field(max_length=40)]] = Field(default_factory=list, max_length=8)


@router.post("/merges/accept")
def accept_merge(body: MergeAccept, session: Session = Depends(get_session)) -> dict:
    """Fold one entity into the other; every mention follows."""
    keep, gone = session.get(Entity, body.keep_id), session.get(Entity, body.merge_id)
    if keep is None or gone is None or keep.merged_into is not None or gone.merged_into is not None:
        raise HTTPException(status_code=404, detail="That name could not be found. Refresh the list.")
    if keep.id == gone.id:
        raise HTTPException(status_code=400, detail="That is one name already.")
    moved, undo_id = merge_with_undo(session, keep, gone)
    made = learning.record(session, kind="accept_merge", subject={"a": keep.id, "b": gone.id, "signals": body.signals})
    session.commit()
    return {"kept": keep.id, "name": keep.name, "aliases": keep.aliases or [], "moved": moved, "undo_id": undo_id, "correction_id": made.id}


@router.post("/merges/dismiss")
def dismiss_merge(body: MergeDismiss, session: Session = Depends(get_session)) -> dict:
    learning.record(session, kind="dismiss_merge", subject={"a": body.a, "b": body.b, "signals": body.signals})
    session.commit()
    return {"dismissed": True}


class TypeDecision(BaseModel):
    link_id: int
    link_type: str = Field(max_length=24)


@router.post("/types/accept")
def accept_type(body: TypeDecision, session: Session = Depends(get_session)) -> dict:
    """Give the link the suggested type."""
    link = relations_repo.find(session, body.link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="That link could not be found. Refresh the list.")
    if body.link_type not in LINK_TYPES:
        raise HTTPException(status_code=422, detail="That isn't a kind of link this notebook knows.")
    made = learning.record(
        session,
        kind="accept_link_type",
        subject={"link_id": link.id, "link_type": body.link_type, "signals": [body.link_type]},
    )
    manager.set_link_type(session, link, body.link_type)
    return {"link_id": link.id, "link_type": link.link_type, "correction_id": made.id}


@router.post("/types/dismiss")
def dismiss_type(body: TypeDecision, session: Session = Depends(get_session)) -> dict:
    learning.record(
        session,
        kind="dismiss_link_type",
        subject={"link_id": body.link_id, "link_type": body.link_type, "signals": [body.link_type]},
    )
    session.commit()
    return {"dismissed": True}


# --- what was dismissed, in one place (Brief 86, decision b) -----------------
#
# Settings, Data: "Clear dismissed suggestions". A dismissal is a correction
# (`learning`) or, for a tension, a pair key in preferences. Clearing marks the
# corrections revived rather than deleting them and hands back the old pair
# keys, so the toast's Undo and the Recent changes list can put every one back.


class DismissedRestore(BaseModel):
    ids: list[int] = Field(default_factory=list, max_length=100_000)
    tensions: list[str] = Field(default_factory=list, max_length=100_000)
    #: Each note's "Not suggested" tags, keyed by its id, as they were.
    note_tags: dict[str, list[str]] = Field(default_factory=dict, max_length=100_000)


def _turned_down_on_notes(session: Session) -> dict[int, list[str]]:
    """The tags turned down on notes (the edit form's "Not suggested" line)."""
    import json

    from sqlalchemy import text

    found: dict[int, list[str]] = {}
    rows = session.execute(
        text("SELECT id, discarded_tags FROM entries WHERE is_deleted = 0 AND discarded_tags NOT IN ('', '[]')")
    ).all()
    for entry_id, raw in rows:
        try:
            tags = json.loads(raw or "[]")
        except (TypeError, ValueError):
            continue
        tags = [str(tag) for tag in tags if tag] if isinstance(tags, list) else []
        if tags:
            found[int(entry_id)] = tags
    return found


def _tension_keys() -> list[str]:
    from tessellate.api.routes_entries import TENSION_DISMISSED_KEY
    from tessellate.core import deps

    return [str(key) for key in (deps.get_config().get_preference(TENSION_DISMISSED_KEY, []) or [])]


@router.get("/dismissed")
def dismissed_suggestions(session: Session = Depends(get_session)) -> dict:
    """How many suggestions the person has said no to, by kind."""
    by_kind = learning.dismissal_counts(session)
    pairs = len(_tension_keys())
    note_tags = sum(len(tags) for tags in _turned_down_on_notes(session).values())
    return {
        "total": sum(by_kind.values()) + pairs + note_tags,
        "by_kind": by_kind,
        "tension_pairs": pairs,
        "note_tags": note_tags,
    }


@router.post("/dismissed/clear")
def clear_dismissed_suggestions(session: Session = Depends(get_session)) -> dict:
    """Forget every dismissal; the response is what `/dismissed/restore` takes back."""
    from tessellate.api.routes_entries import TENSION_DISMISSED_KEY
    from tessellate.core import deps

    from sqlalchemy import text

    tensions = _tension_keys()
    ids = learning.revive_dismissals(session)
    on_notes = _turned_down_on_notes(session)
    if on_notes:
        # Raw SQL: forgetting a verdict is not an edit, so no note's updated_at moves.
        clear = text("UPDATE entries SET discarded_tags = '[]' WHERE id IN :ids").bindparams(bindparam("ids", expanding=True))
        session.execute(clear, {"ids": list(on_notes)})
    session.commit()
    if tensions:
        deps.get_config().set_preference(TENSION_DISMISSED_KEY, [])
    count = len(ids) + len(tensions) + sum(len(tags) for tags in on_notes.values())
    return {
        "cleared": count,
        "ids": ids,
        "tensions": tensions,
        "note_tags": {str(entry_id): tags for entry_id, tags in on_notes.items()},
    }


@router.post("/dismissed/restore")
def restore_dismissed_suggestions(body: DismissedRestore, session: Session = Depends(get_session)) -> dict:
    from tessellate.api.routes_entries import TENSION_DISMISSED_KEY
    from tessellate.core import deps

    import json

    from sqlalchemy import text

    restored = learning.restore_dismissals(session, body.ids)
    for raw_id, tags in body.note_tags.items():
        if not raw_id.isdigit() or not tags:
            continue
        done = session.execute(
            text("UPDATE entries SET discarded_tags = :tags WHERE id = :id AND is_deleted = 0 AND discarded_tags IN ('', '[]')"),
            {"tags": json.dumps([str(tag) for tag in tags][-200:]), "id": int(raw_id)},
        )
        restored += len(tags) if done.rowcount else 0
    session.commit()
    if body.tensions:
        have = _tension_keys()
        merged = have + [key for key in body.tensions if key not in have]
        deps.get_config().set_preference(TENSION_DISMISSED_KEY, merged)
    return {"restored": restored + len(body.tensions)}
