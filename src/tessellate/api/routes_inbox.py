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
from tessellate.repo import tags as tag_repo
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
    from tessellate.api.routes_entries_relations import TENSION_DISMISSED_KEY
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
    from tessellate.api.routes_entries_relations import TENSION_DISMISSED_KEY
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
    from tessellate.api.routes_entries_relations import TENSION_DISMISSED_KEY
    from tessellate.core import deps



    restored = learning.restore_dismissals(session, body.ids)
    for raw_id, tags in body.note_tags.items():
        if not raw_id.isdigit() or not tags:
            continue
        # Put back beside any tags still turned down (one Restore leaves the rest).
        have = tag_repo.turned_down_on(session, int(raw_id))
        if have is None:
            continue
        fresh = [str(tag) for tag in tags if str(tag) not in have]
        if fresh:
            tag_repo.set_turned_down_on(session, int(raw_id), have + fresh)
            restored += len(fresh)
    session.commit()
    if body.tensions:
        have = _tension_keys()
        merged = have + [key for key in body.tensions if key not in have]
        deps.get_config().set_preference(TENSION_DISMISSED_KEY, merged)
    return {"restored": restored + len(body.tensions)}


# --- the same list, one row each, with Restore on every row -------------------
#
# Settings, Data: "Dismissed suggestions". A row's key says which store it
# lives in: `c:<id>` a correction, `t:<low>:<high>` a contradiction pair (its
# preference key and its correction are one thing to the person), `n:<note>:<tag>`
# a tag turned down on one note. Restore answers in the shape `/dismissed/clear`
# does, so the toast's Undo is the `/dismissed/restore` route above.

DISMISSED_LIST_MAX = 200

_KIND_LABEL = {
    "dismiss_merge": "Name merge",
    "dismiss_link_type": "Link type",
    "dismiss_link": "Link",
    "dismiss_tension": "Contradiction",
    "dismiss_resurface": "Old note",
    "dismiss_insight": "Insight",
}


class DismissedItem(BaseModel):
    key: str = Field(default="", max_length=400)


def _note_name(session: Session, entry_id: object) -> str:
    try:
        content = session.scalar(select(Entry.content).where(Entry.id == int(entry_id)))  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return ""
    if not content:
        return ""
    name = plain_label(content, 200)
    return name if len(name) <= 36 else name[:35].rstrip() + "…"


def _entity_name(session: Session, entity_id: object) -> str:
    try:
        return session.scalar(select(Entity.name).where(Entity.id == int(entity_id))) or ""  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return ""


def _pair_key(a: object, b: object) -> str | None:
    try:
        low, high = sorted((int(a), int(b)))  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None
    return f"{low}:{high}"


def _subject(payload: dict) -> dict:
    found = payload.get("subject")
    return found if isinstance(found, dict) else {}


def _dismissal_label(session: Session, kind: str, payload: dict) -> str:
    subject = _subject(payload)
    if kind == "dismiss_merge":
        names = [_entity_name(session, subject.get(k)) for k in ("a", "b")]
        if all(names):
            return " and ".join(names)
    elif kind == "dismiss_tension":
        names = [_note_name(session, subject.get(k)) for k in ("a", "b")]
        if all(names):
            return " and ".join(names)
    elif kind == "dismiss_link_type":
        return f"Link type “{subject.get('link_type')}”" if subject.get("link_type") else "A link type"
    else:
        for field in ("entry_id", "source_id", "target_id", "a"):
            name = _note_name(session, subject.get(field))
            if name:
                return name
    said = str(payload.get("from") or payload.get("excerpt") or "").strip()
    return said[:80] or _KIND_LABEL.get(kind, "A suggestion")


@router.get("/dismissed/items")
def dismissed_items(session: Session = Depends(get_session)) -> dict:
    """Each suggestion said no to, newest first, `DISMISSED_LIST_MAX` at most."""
    keys = set(_tension_keys())
    rows: list[tuple[int, dict]] = []
    for row_id, kind, payload in learning.live_dismissals(session):
        subject = _subject(payload)
        if kind == "dismiss_tension" and _pair_key(subject.get("a"), subject.get("b")) in keys:
            continue  # listed once, through its pair key below
        rows.append((row_id, {"key": f"c:{row_id}", "kind": kind, "kind_label": _KIND_LABEL.get(kind, kind), "label": _dismissal_label(session, kind, payload)}))
    for pair in sorted(keys):
        a, _, b = pair.partition(":")
        names = [_note_name(session, a), _note_name(session, b)]
        rows.append((0, {"key": f"t:{pair}", "kind": "dismiss_tension", "kind_label": _KIND_LABEL["dismiss_tension"], "label": " and ".join(names) if all(names) else "A pair of notes"}))
    for entry_id, tags in _turned_down_on_notes(session).items():
        name = _note_name(session, entry_id) or "A note"
        rows.extend((0, {"key": f"n:{entry_id}:{tag}", "kind": "note_tag", "kind_label": f"Tag turned down on {name}", "label": tag}) for tag in tags)
    rows.sort(key=lambda row: -row[0])
    return {"items": [item for _, item in rows[:DISMISSED_LIST_MAX]], "more": max(0, len(rows) - DISMISSED_LIST_MAX)}


def _restore_pair(session: Session, pair: str) -> tuple[list[int], list[str]]:
    from tessellate.api.routes_entries_relations import TENSION_DISMISSED_KEY
    from tessellate.core import deps

    keys = _tension_keys()
    gone = [pair] if pair in keys else []
    if gone:
        deps.get_config().set_preference(TENSION_DISMISSED_KEY, [key for key in keys if key != pair])
    mine = {
        row_id
        for row_id, row_kind, payload in learning.live_dismissals(session)
        if row_kind == "dismiss_tension" and _pair_key(_subject(payload).get("a"), _subject(payload).get("b")) == pair
    }
    return (learning.revive_dismissals(session, mine) if mine else []), gone


def _restore_note_tag(session: Session, rest: str) -> dict:


    raw_id, _, tag = rest.partition(":")
    have = _turned_down_on_notes(session).get(int(raw_id), []) if raw_id.isdigit() else []
    if tag not in have:
        return {}
    tag_repo.set_turned_down_on(session, int(raw_id), [t for t in have if t != tag])
    return {raw_id: [tag]}


@router.post("/dismissed/item/restore")
def restore_one_dismissed(body: DismissedItem, session: Session = Depends(get_session)) -> dict:
    """Offer one dismissed suggestion again. A key that is gone changes nothing."""
    ids: list[int] = []
    tensions: list[str] = []
    note_tags: dict = {}
    kind, _, rest = body.key.partition(":")
    if kind == "c" and rest.isdigit():
        ids = learning.revive_dismissals(session, {int(rest)})
    elif kind == "t":
        ids, tensions = _restore_pair(session, rest)
    elif kind == "n":
        note_tags = _restore_note_tag(session, rest)
    session.commit()
    return {"restored": 1 if (ids or tensions or note_tags) else 0, "ids": ids, "tensions": tensions, "note_tags": note_tags}
