"""Note groups and a note's further categories (L-world-class-172, 173).

A group is a set a person gathers by hand: no model files into it and no
sort moves a note out of it. A note's further categories sit beside the one
the filer decides. Both are written only here, by a person (or the agent's
own routes later), and read back on every note as `groups` and `also_in`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.core.database import Entry
from tessellate.core.deps import get_session
from tessellate.entry import manager
from tessellate.repo import memberships

router = APIRouter(tags=["groups"])

#: A note can sit in this many further categories; more is a tag's job.
ALSO_IN_MAX = 8


class GroupBody(BaseModel):
    name: str = Field(min_length=1, max_length=memberships.NAME_MAX)


class NotesBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=2000)


class AlsoInBody(BaseModel):
    categories: list[str] = Field(default_factory=list, max_length=ALSO_IN_MAX)


@router.get("/groups")
def list_groups(session: Session = Depends(get_session)) -> list[dict]:
    return memberships.list_groups(session)


@router.post("/groups", status_code=201)
def create_group(body: GroupBody, session: Session = Depends(get_session)) -> dict:
    group = memberships.create_group(session, body.name)
    manager.log_action(session, "created", "group", group.id, group.name)
    session.commit()
    return {"id": group.id, "name": group.name, "count": 0}


@router.patch("/groups/{group_id}")
def rename_group(group_id: int, body: GroupBody, session: Session = Depends(get_session)) -> dict:
    group = memberships.rename_group(session, group_id, body.name)
    manager.log_action(session, "renamed", "group", group.id, group.name)
    session.commit()
    return {"id": group.id, "name": group.name}


@router.delete("/groups/{group_id}")
def delete_group(group_id: int, session: Session = Depends(get_session)) -> dict:
    group = memberships.find_group(session, group_id)
    name = group.name
    memberships.delete_group(session, group_id)
    manager.log_action(session, "deleted", "group", group_id, name)
    session.commit()
    return {"deleted": True}


@router.post("/groups/{group_id}/notes")
def add_to_group(group_id: int, body: NotesBody, session: Session = Depends(get_session)) -> dict:
    added = memberships.add_notes(session, group_id, body.ids)
    session.commit()
    return {"added": added}


@router.post("/groups/{group_id}/notes/remove")
def remove_from_group(group_id: int, body: NotesBody, session: Session = Depends(get_session)) -> dict:
    removed = memberships.remove_notes(session, group_id, body.ids)
    session.commit()
    return {"removed": removed}


@router.put("/entries/{entry_id}/also-in")
def set_also_in(entry_id: int, body: AlsoInBody, session: Session = Depends(get_session)) -> dict:
    """Replace the categories this note is also in. The one it is filed under
    stays as it is (and is dropped from the list if named)."""
    entry = session.get(Entry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="That note no longer exists.")
    space = manager.entry_space(entry)
    named = [n.strip()[: manager.MAX_CATEGORY_LENGTH] for n in body.categories if n and n.strip()]
    categories = [manager.get_or_create_category(session, name, workspace_id=space) for name in dict.fromkeys(named)]
    kept = memberships.set_also_in(session, entry, categories)
    manager.log_action(session, "edited", "entry", entry.id, "also in: " + (", ".join(kept) or "none"))
    session.commit()
    return {"id": entry.id, "also_in": kept}
