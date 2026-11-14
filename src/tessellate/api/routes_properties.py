"""A note's properties and the note types (GRAPH_PLAN KG4, INBOX 528).

The properties are the `---` block at the top of the note's own text
(`entry/properties.py`); reading them parses the text, writing them rewrites
that block and saves through `routes_entries.update_entry`, so the revision,
the conflict guard, the wiki sync and the index rebuild happen as on any
save. A type ("Meeting": attendees, date) is a row here; a note is of a type
when its block says `type: Meeting`, and a new note of a type starts with its
fields.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.api import routes_entries
from tessellate.api.schemas import EntryOut, EntryUpdate
from tessellate.core.database import NOTE_FIELD_KINDS, NoteType
from tessellate.core import deps
from tessellate.core.deps import get_session
from tessellate.entry import manager_text
from tessellate.entry import properties as note_properties

router = APIRouter(tags=["properties"])

#: Bounds: a property table is a header, not a database row of a hundred
#: columns, and a value is a phrase.
MAX_PROPERTIES = 40
MAX_VALUE_CHARS = 300


def _type_row(row: NoteType) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "icon": row.icon,
        "colour": row.colour,
        "fields": list(row.fields or []),
    }


@router.get("/entries/{entry_id}/properties")
def entry_properties(entry_id: int, session: Session = Depends(get_session)) -> dict:
    """The note's properties, its type, and that type's fields in order."""
    entry = routes_entries._existing_entry(session, entry_id)
    found, _ = note_properties.split(manager_text.readable_content(entry))
    kind = note_properties.note_type(found)
    row = note_properties.find_type(session, kind)
    return {"properties": found, "type": kind, "fields": list(row.fields or []) if row else []}


class PropertiesIn(BaseModel):
    properties: dict[str, str | int | float | bool | list[str] | None]
    #: The text the editor read, for the same conflict guard a save has.
    base_hash: str | None = None


@router.put("/entries/{entry_id}/properties", response_model=EntryOut)
def put_properties(
    entry_id: int, body: PropertiesIn, response: Response, session: Session = Depends(get_session)
) -> EntryOut:
    """Replace the note's block with these properties; the body is untouched."""
    if len(body.properties) > MAX_PROPERTIES:
        raise HTTPException(status_code=422, detail=f"A note holds {MAX_PROPERTIES} properties at most.")
    clean: dict[str, object] = {}
    for key, value in body.properties.items():
        name = " ".join(str(key).split())[:60]
        if not name or ":" in name:
            raise HTTPException(status_code=422, detail="A property's name can't be empty or hold a colon.")
        if isinstance(value, list):
            clean[name] = [str(v)[:MAX_VALUE_CHARS] for v in value][:40]
        elif isinstance(value, str):
            clean[name] = value[:MAX_VALUE_CHARS]
        else:
            clean[name] = value
    entry = routes_entries._existing_entry(session, entry_id)
    text = note_properties.write(manager_text.readable_content(entry), clean)
    #: By keyword, and with the response passed through: B7 put `response`
    #: and `If-Match` into `update_entry`'s signature, and a positional
    #: `session` landed in `response` while `session` stayed the bare
    #: `Depends` marker, so every properties save was a 500 (found
    #: 2026-10-05 by row 10's test). The ETag the save sets is this
    #: response's too.
    return routes_entries.update_entry(
        entry_id,
        EntryUpdate(content=text, base_hash=body.base_hash),
        response=response,
        session=session,
        if_match=None,
    )


class FieldIn(BaseModel):
    name: str = Field(max_length=60)
    kind: str = "text"


class NoteTypeIn(BaseModel):
    name: str = Field(max_length=60)
    icon: str | None = Field(default=None, max_length=30)
    colour: str | None = Field(default=None, max_length=16)
    fields: list[FieldIn] = Field(default_factory=list, max_length=30)
    #: Undo's door (undo-1005): a deleted type made again with its own id,
    #: read only with `restore` and only while no other type holds it.
    id: int | None = None
    restore: bool = False


class NoteTypePatch(BaseModel):
    name: str | None = Field(default=None, max_length=60)
    icon: str | None = Field(default=None, max_length=30)
    colour: str | None = Field(default=None, max_length=16)
    fields: list[FieldIn] | None = Field(default=None, max_length=30)


def _fields(fields: list[FieldIn]) -> list[dict]:
    out, seen = [], set()
    for field in fields:
        name = " ".join(field.name.split())
        if not name or ":" in name or name.lower() == "type":
            raise HTTPException(status_code=422, detail="A field needs a name (not \"type\", and no colon).")
        if field.kind not in NOTE_FIELD_KINDS:
            raise HTTPException(status_code=422, detail=f"A field is one of: {', '.join(NOTE_FIELD_KINDS)}.")
        if name.lower() not in seen:
            seen.add(name.lower())
            out.append({"name": name, "kind": field.kind})
    return out


@router.get("/note-types")
def list_note_types(
    response: Response,
    limit: int = Query(default=500, ge=1, le=500),
    session: Session = Depends(get_session),
) -> list[dict]:
    note_properties.ensure_builtin_types(session, deps.get_config())
    rows = [_type_row(r) for r in session.scalars(select(NoteType).order_by(NoteType.name))]
    response.headers["X-Total-Count"] = str(len(rows))
    return rows[:limit]


@router.post("/note-types", status_code=201)
def create_note_type(body: NoteTypeIn, session: Session = Depends(get_session)) -> dict:
    name = " ".join(body.name.split())
    if not name:
        raise HTTPException(status_code=422, detail="A note type needs a name.")
    if note_properties.find_type(session, name) is not None:
        raise HTTPException(status_code=409, detail="There is already a note type with that name.")
    row = NoteType(name=name, icon=body.icon, colour=body.colour, fields=_fields(body.fields) or None)
    if body.restore and body.id is not None and session.get(NoteType, body.id) is None:
        row.id = body.id
    else:
        row.id = note_properties.next_type_id(session, deps.get_config())
    session.add(row)
    session.commit()
    return _type_row(row)


def _existing_type(session: Session, type_id: int) -> NoteType:
    row = session.get(NoteType, type_id)
    if row is None:
        raise HTTPException(status_code=404, detail="That note type could not be found.")
    return row


@router.patch("/note-types/{type_id}")
def patch_note_type(type_id: int, body: NoteTypePatch, session: Session = Depends(get_session)) -> dict:
    """A rename changes the type's name here only: notes that say the old
    name keep saying it (their text is theirs), which the list shows."""
    row = _existing_type(session, type_id)
    sent = body.model_fields_set
    if "name" in sent and body.name is not None:
        name = " ".join(body.name.split())
        other = note_properties.find_type(session, name)
        if not name or (other is not None and other.id != row.id):
            raise HTTPException(status_code=409, detail="There is already a note type with that name.")
        row.name = name
    if "icon" in sent:
        row.icon = body.icon
    if "colour" in sent:
        row.colour = body.colour
    if "fields" in sent and body.fields is not None:
        row.fields = _fields(body.fields) or None
    session.commit()
    return _type_row(row)


@router.delete("/note-types/{type_id}")
def delete_note_type(type_id: int, session: Session = Depends(get_session)) -> dict:
    """The type goes; every note keeps its properties, `type:` included."""
    row = _existing_type(session, type_id)
    # What Undo sends back to `POST /note-types` with `restore`.
    kept = _type_row(row)
    session.delete(row)
    session.commit()
    note_properties.remember_deleted_type(type_id, deps.get_config())
    return {"deleted": type_id, "type": kept}
