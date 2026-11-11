"""ROADMAP.md item 34: a lightweight entity/concept layer above notes.

Every edge in the graph before this connected two whole notes; there was no
node for "this person" or "this project" independent of any one note
mentioning them. Deliberately smaller than a full ontology (see ANALYSIS.md
§59's read of a sibling project's LLM-entity-extraction, which this borrows
the *idea* of, not the code): no entity-to-entity graph, no type system, a
single free-text name per entity, and membership (`EntityMention`) as the
only edge kind. Extraction is one `suggest_tags`-shaped completion call per
note, on the utility model, run a few notes at a time by the autonomous
background pass (`ai/autonomous.py`) when `auto_entities_enabled` is on.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import presets
from tessellate.ai.model_manager import ModelManager
from tessellate.ai.ollama_client import OllamaClient
from tessellate.core import model_gate
from tessellate.core.database import (
    ENTITY_KINDS,
    LIKE_ESCAPE,
    Entity,
    EntityMention,
    Entry,
    like_escape,
    utcnow,
)

logger = logging.getLogger("tessellate.entities")

# A note this short rarely names anything worth its own node, cheaper to
# skip than to spend a model call finding nothing, the same reasoning
# `suggest_tags`' caller already applies before asking for tags.
MIN_CONTENT_LENGTH = 20

# Per note, per pass, a name-dropping note ("thanks Sam, Priya and Jo for
# the trip") shouldn't flood the entity table any more than five topic tags
# would.
MAX_ENTITIES_PER_NOTE = 5


#: The model's words for a kind, read onto `ENTITY_KINDS` (GRAPH_PLAN KG5). A
#: small model writes "org", "company", "location" as often as the word asked
#: for; anything else is no kind rather than a guess.
KIND_WORDS = {
    "person": "person", "people": "person", "name": "person",
    "place": "place", "location": "place", "city": "place", "country": "place",
    "project": "project",
    "organisation": "organisation", "organization": "organisation", "org": "organisation",
    "company": "organisation", "team": "organisation",
    "thing": "thing", "object": "thing", "product": "thing", "tool": "thing",
}


def suggest_entities_with_kinds(
    text: str,
    model_manager: ModelManager,
    ollama: OllamaClient,
    limit: int = MAX_ENTITIES_PER_NOTE,
) -> list[tuple[str, str | None]]:
    """Named people, places, projects, organisations and things this note
    mentions, each with its kind when the model said one (`name|kind`).
    Raises OllamaError if the model is unavailable, the caller decides what
    to do, same contract as `suggest_tags`.
    """
    system = (
        "You extract named entities from a note, real people, projects, "
        "places, organisations or things it names, not generic topics (a "
        "topic is a tag, not an entity: 'baking' is a topic, 'the sourdough "
        "starter' is a thing). Reply with ONLY a comma-separated list of "
        f"{limit} or fewer, each written name|kind where kind is one of "
        f"{', '.join(ENTITY_KINDS)}, the name as short as it's naturally "
        "called (a first name is fine), no explanation. Example: "
        "Sam|person, Leeds|place. If the note names nothing worth tracking "
        "as its own thing, reply with NONE."
    )
    reply = ollama.chat(
        model_manager.utility_model(),
        [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
        mode=presets.BACKGROUND_MODE,
    )
    raw = reply["content"].strip()
    if not raw or raw.upper().startswith("NONE"):
        return []
    seen: set[str] = set()
    found: list[tuple[str, str | None]] = []
    for piece in raw.replace("\n", ",").split(","):
        name, _, kind = piece.partition("|")
        name = name.strip().strip("\"'").lstrip("-•").strip()
        key = name.lower()
        if name and key not in seen and len(name) <= 200:
            seen.add(key)
            found.append((name, KIND_WORDS.get(kind.strip().strip("\"'.").lower())))
    return found[:limit]


def suggest_entities(
    text: str,
    model_manager: ModelManager,
    ollama: OllamaClient,
    limit: int = MAX_ENTITIES_PER_NOTE,
) -> list[str]:
    """The names alone, for a caller that has no use for the kinds."""
    return [name for name, _ in suggest_entities_with_kinds(text, model_manager, ollama, limit)]


def _find_or_create_entity(session: Session, name: str, cache: dict[str, Entity]) -> Entity:
    """Case-folded exact match within this pass's own cache first (so the
    same note's five names don't each hit the database), then the table
    itself, then a name an entity carries as an alias, then a new row. A
    match on an entity a merge emptied follows `merged_into` to the survivor
    (GRAPH_PLAN KG5), so a merge is never undone by the next extraction.
    Two different real-world Sarahs proposed as "Sarah" across two notes are
    still one entity, a real ambiguity accepted rather than solved.
    """
    key = name.lower()
    if key in cache:
        return cache[key]
    existing = session.scalars(
        select(Entity).where(Entity.name.ilike(like_escape(name), escape=LIKE_ESCAPE))
    ).first()
    if existing is None:
        #: The alias map, built once per pass and kept in the same cache under
        #: a key no name can be (names are stripped, never a NUL).
        aliases = cache.get("\0aliases")
        if aliases is None:
            aliases = {}
            for row in session.scalars(select(Entity).where(Entity.aliases.is_not(None))):
                for alias in row.aliases or []:
                    aliases.setdefault(str(alias).casefold(), row)
            cache["\0aliases"] = aliases  # type: ignore[assignment]
        existing = aliases.get(name.casefold())  # type: ignore[union-attr]
    existing = _survivor(session, existing)
    entity = existing or Entity(name=name)
    if not existing:
        session.add(entity)
        session.flush()  # need entity.id for the EntityMention below
    cache[key] = entity
    return entity


def _survivor(session: Session, entity: Entity | None) -> Entity | None:
    """The entity a chain of merges ends at (ten hops at most: a cycle is a
    bug elsewhere and must not hang a background pass)."""
    for _ in range(10):
        if entity is None or entity.merged_into is None:
            return entity
        entity = session.get(Entity, entity.merged_into)
    return entity


def merge_entities(session: Session, keep: Entity, gone: Entity) -> int:
    """Fold `gone` into `keep`: every mention moves (one per note), `gone`'s
    names become `keep`'s aliases, and `gone` points at `keep` so a later
    extraction of its name lands on the survivor. Returns the mentions moved.
    Flushes; the caller commits.
    """
    if keep.id == gone.id:
        return 0
    have = set(session.scalars(select(EntityMention.entry_id).where(EntityMention.entity_id == keep.id)))
    moved = 0
    for mention in session.scalars(select(EntityMention).where(EntityMention.entity_id == gone.id)).all():
        if mention.entry_id in have:
            session.delete(mention)
        else:
            mention.entity_id = keep.id
            have.add(mention.entry_id)
            moved += 1
    names = [*(keep.aliases or []), gone.name, *(gone.aliases or [])]
    seen = {keep.name.casefold()}
    aliases = []
    for alias in names:
        folded = str(alias).casefold()
        if folded not in seen:
            seen.add(folded)
            aliases.append(str(alias))
    keep.aliases = aliases or None
    keep.kind = keep.kind or gone.kind
    gone.aliases = None
    gone.merged_into = keep.id
    for earlier in session.scalars(select(Entity).where(Entity.merged_into == gone.id)).all():
        earlier.merged_into = keep.id
    session.flush()
    return moved


#: The audit action a merge's snapshot is kept under, for its Undo.
MERGE_ACTION = "entity_merge"


def _entity_state(entity: Entity) -> dict:
    return {
        "id": entity.id,
        "name": entity.name,
        "kind": entity.kind,
        "aliases": list(entity.aliases) if entity.aliases else None,
        "merged_into": entity.merged_into,
    }


def merge_with_undo(session: Session, keep: Entity, gone: Entity) -> tuple[int, int]:
    """`merge_entities`, keeping what Undo needs to split them back exactly
    (INBOX 553(a), the owner's decision). Returns `(moved, undo_id)`.

    The snapshot is both entities as they were, every mention `gone` had (by
    row id, so the same rows go back), and the entities an earlier merge had
    pointed at `gone`. `keep`'s own mentions are never touched by a merge,
    so they need no record. Kept as an audit row: one store for "what
    happened", and the row says in words what it was.
    """
    from tessellate.core.database import AuditLog

    snapshot = {
        "keep": _entity_state(keep),
        "gone": _entity_state(gone),
        "mentions": [
            {
                "id": row.id,
                "entry_id": row.entry_id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in session.scalars(select(EntityMention).where(EntityMention.entity_id == gone.id)).all()
        ],
        "redirected": list(session.scalars(select(Entity.id).where(Entity.merged_into == gone.id))),
    }
    moved = merge_entities(session, keep, gone)
    row = AuditLog(
        action=MERGE_ACTION,
        entity_type="entity",
        entity_id=keep.id,
        detail=f"merged {gone.name[:80]} into {keep.name[:80]}",
        payload=snapshot,
        actor="user",
    )
    session.add(row)
    session.flush()
    return moved, row.id


class MergeUndoError(Exception):
    """Why an Undo cannot run: `reason` is `missing`, `undone` or `changed`;
    the route words each one."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def undo_merge(session: Session, undo_id: int) -> Entity:
    """Split a merge back exactly as it was. Returns the entity brought back.

    Refused (`MergeUndoError`) when there is no such merge, when it was
    already undone, or when the two have changed since in a way a split
    would overwrite: the folded entity no longer points at the survivor.
    Mentions are put back by row id; one the merge dropped as a duplicate
    is written again with its own id and date, unless its note has gone.
    """
    from datetime import datetime

    from tessellate.core.database import AuditLog

    row = session.get(AuditLog, undo_id)
    if row is None or row.action != MERGE_ACTION or not isinstance(row.payload, dict):
        raise MergeUndoError("missing")
    snapshot = dict(row.payload)
    if snapshot.get("undone"):
        raise MergeUndoError("undone")
    keep = session.get(Entity, snapshot["keep"]["id"])
    gone = session.get(Entity, snapshot["gone"]["id"])
    if keep is None or gone is None or gone.merged_into != keep.id:
        raise MergeUndoError("changed")
    for entity, state in ((keep, snapshot["keep"]), (gone, snapshot["gone"])):
        entity.name = state["name"]
        entity.kind = state["kind"]
        entity.aliases = list(state["aliases"]) if state["aliases"] else None
        entity.merged_into = state["merged_into"]
    for earlier_id in snapshot.get("redirected") or []:
        earlier = session.get(Entity, earlier_id)
        if earlier is not None and earlier.merged_into == keep.id:
            earlier.merged_into = gone.id
    for mention in snapshot.get("mentions") or []:
        existing = session.get(EntityMention, mention["id"])
        if existing is not None and existing.entry_id == mention["entry_id"]:
            existing.entity_id = gone.id
            continue
        if session.get(Entry, mention["entry_id"]) is None:
            continue
        created = mention.get("created_at")
        session.add(
            EntityMention(
                id=None if existing is not None else mention["id"],
                entity_id=gone.id,
                entry_id=mention["entry_id"],
                created_at=datetime.fromisoformat(created) if created else utcnow(),
            )
        )
    snapshot["undone"] = True
    row.payload = snapshot
    session.flush()
    return gone


def extract_entities_pass(
    session: Session,
    model_manager: ModelManager,
    ollama: OllamaClient,
    limit: int = 5,
) -> int:
    """Entity-extract up to `limit` not-yet-scanned notes. Returns how many
    were processed (successfully or not: a note that fails still gets
    marked scanned, the same "don't retry forever" reasoning
    `entities_extracted_at` exists for at all).

    Never raises: called from the autonomous pass's own worker thread,
    which the rest of that module's docstrings already establish must not
    propagate an exception past its own top level.
    """
    candidates = list(
        session.scalars(
            select(Entry)
            .where(
                Entry.entities_extracted_at.is_(None),
                Entry.is_deleted == False,  # noqa: E712
                Entry.is_private == False,  # noqa: E712
            )
            .order_by(Entry.id.desc())
            .limit(limit)
        )
    )
    if not candidates:
        return 0

    cache: dict[str, Entity] = {}
    processed = 0
    # Snapshot what the loop needs, then end the read: the model call below
    # is seconds to minutes, and it must never run with a write pending
    # (ARCH-01, measured: a flushed write held across a model call made every
    # save in the meantime fail after the 5 s busy timeout). Each note is
    # asked with nothing open, then written and committed on its own.
    work = [(entry, (entry.content or "").strip()) for entry in candidates]
    session.commit()
    for entry, content in work:
        try:
            found: list[tuple[str, str | None]] = []
            if len(content) >= MIN_CONTENT_LENGTH:
                # A chat turn in flight goes first (ARCH-09).
                model_gate.yield_to_interactive()
                found = suggest_entities_with_kinds(content, model_manager, ollama)
            for name, kind in found:
                entity = _find_or_create_entity(session, name, cache)
                if kind and not entity.kind:
                    entity.kind = kind
                already = session.scalars(
                    select(EntityMention).where(
                        EntityMention.entity_id == entity.id,
                        EntityMention.entry_id == entry.id,
                    )
                ).first()
                if not already:
                    session.add(EntityMention(entity_id=entity.id, entry_id=entry.id))
        except Exception:  # noqa: BLE001  # one bad note must not stop the pass
            logger.debug("entity extraction failed on entry %s", entry.id, exc_info=True)
            # A write that failed half way leaves the session unusable; drop
            # this note's partial rows so the stamp below can still commit.
            session.rollback()
            cache.clear()
        finally:
            entry.entities_extracted_at = utcnow()
            processed += 1
            session.commit()
    return processed
