"""The meeting-prep brief (L-general-11): when a reminder fires and its words
name a person or a topic the notebook knows, the last few notes about it come
with the notice, so "Call Sam" arrives with what was last written about Sam.

Known means an entity (a person, place, project, organisation or thing the
notebook extracted, by name or alias) or a tag, matched as whole words. No
model runs: this is a lookup at fire time, cheap enough for every reminder.
Private notes and a private space's reminder give nothing.
"""

from __future__ import annotations

import json
import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from tessellate.core.database import Entity, EntityMention, Entry, LIKE_ESCAPE, like_escape
from tessellate.entry.manager_text import extract_title, plain_label, readable_content
from tessellate.entry.properties import strip as strip_properties

#: Notes on the card, and subjects one reminder can name.
NOTES = 3
SUBJECTS = 2
#: Shorter names ("Al", tag "ai") match too much ordinary text.
MIN_NAME = 3


def _named(text: str, name: str) -> bool:
    words = r"[\s_-]+".join(re.escape(part) for part in re.split(r"[\s_-]+", name.strip()) if part)
    return bool(words) and re.search(rf"(?<!\w){words}(?!\w)", text, re.IGNORECASE) is not None


def _visible():
    return (Entry.is_deleted == False, Entry.is_private == False, Entry.is_board == False)  # noqa: E712


def _entity_names(session: Session, text: str) -> dict[str, tuple[str, str]]:
    found: dict[str, tuple[str, str]] = {}
    for entity in session.scalars(select(Entity).where(Entity.merged_into.is_(None))):
        for name in [entity.name, *(entity.aliases or [])]:
            if isinstance(name, str) and len(name.strip()) >= MIN_NAME and _named(text, name):
                found.setdefault(name.strip().lower(), ("entity", entity.name))
    return found


def _tag_names(session: Session, text: str) -> dict[str, tuple[str, str]]:
    found: dict[str, tuple[str, str]] = {}
    for raw in session.scalars(select(Entry.tags).where(*_visible(), Entry.tags != "[]")):
        try:
            tags = json.loads(raw or "[]")
        except (TypeError, ValueError):
            continue
        for tag in tags if isinstance(tags, list) else []:
            tag = str(tag).strip()
            if len(tag) >= MIN_NAME and tag.lower() not in found and _named(text, tag):
                found[tag.lower()] = ("tag", tag)
    return found


def subjects(session: Session, text: str) -> list[tuple[str, str]]:
    """`(kind, name)` for what `text` names, longest first so "Sam Lee" wins
    over "Sam": `("entity", ...)` for an extracted name, `("tag", ...)`."""
    found = {**_tag_names(session, text), **_entity_names(session, text)}
    picked: list[tuple[str, str]] = []
    for key, subject in sorted(found.items(), key=lambda kv: -len(kv[0])):
        if subject in picked or any(_named(name, key) for _, name in picked):
            continue  # "sam" inside an already picked "Sam Lee"
        picked.append(subject)
        if len(picked) == SUBJECTS:
            break
    return picked


def _title(entry: Entry) -> str:
    text = strip_properties(readable_content(entry))
    return extract_title(text) or plain_label(text, 60) or "Untitled"


def brief(session: Session, reminder, *, private: bool = False) -> dict:  # noqa: ANN001
    """`{"subjects": [...], "notes": [{"id", "title", "updated_at"}]}`, the
    newest notes about what the reminder names, its own note left out (the
    notice already says what it is about). Empty for a private reminder."""
    if private or not (reminder.text or "").strip():
        return {"subjects": [], "notes": []}
    named = subjects(session, reminder.text)
    if not named:
        return {"subjects": [], "notes": []}
    clauses = []
    entity_names = [name for kind, name in named if kind == "entity"]
    if entity_names:
        ids = select(EntityMention.entry_id).join(Entity, Entity.id == EntityMention.entity_id).where(Entity.name.in_(entity_names))
        clauses.append(Entry.id.in_(ids))
    for kind, name in named:
        if kind == "tag":
            clauses.append(Entry.tags.like(f'%"{like_escape(name)}"%', escape=LIKE_ESCAPE))
    query = select(Entry).where(*_visible(), or_(*clauses))
    if reminder.entry_id is not None:
        query = query.where(Entry.id != reminder.entry_id)
    rows = session.scalars(query.order_by(Entry.updated_at.desc(), Entry.id.desc()).limit(NOTES)).all()
    return {
        "subjects": [name for _, name in named],
        "notes": [{"id": e.id, "title": _title(e), "updated_at": e.updated_at.isoformat() if e.updated_at else None} for e in rows],
    }
