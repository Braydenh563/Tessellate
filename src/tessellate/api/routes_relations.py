"""Kinds of link a person adds (GRAPH_PLAN KG3, INBOX 528).

The six built-ins stay in code and are listed first; a person adds their own
here, each with the name it has from the other end ("Part of" / "Has part").
The routes read the request and shape the answer; every query, the key a
name makes and the delete that leaves links untyped are
`repo/relation_types.py`'s (INBOX 1499).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.core.deps import get_session
from tessellate.repo import relation_types

router = APIRouter(prefix="/relation-types", tags=["relation-types"])


class RelationIn(BaseModel):
    name: str = Field(max_length=60)
    inverse: str | None = Field(default=None, max_length=60)
    directed: bool = True
    colour: str | None = Field(default=None, max_length=16)
    #: Undo's door (undo-1005): a deleted kind made again as it was. Its key
    #: is sent, not derived, because a rename keeps the key (`part_of` named
    #: "Piece of"); `link_ids` are the links its delete left untyped, which
    #: take the kind back unless they have been given another one since.
    restore: bool = False
    key: str | None = Field(default=None, max_length=24)
    link_ids: list[int] = Field(default_factory=list, max_length=100_000)


class RelationPatch(BaseModel):
    name: str | None = Field(default=None, max_length=60)
    inverse: str | None = Field(default=None, max_length=60)
    directed: bool | None = None
    colour: str | None = Field(default=None, max_length=16)


@router.get("")
def list_types(
    response: Response,
    limit: int = Query(default=500, ge=1, le=500),
    session: Session = Depends(get_session),
) -> list[dict]:
    rows = list(relation_types.kinds(session).values())
    response.headers["X-Total-Count"] = str(len(rows))
    return rows[:limit]


@router.post("", status_code=201)
def create_type(body: RelationIn, session: Session = Depends(get_session)) -> dict:
    restore = body.restore and bool(body.key)
    made = relation_types.create(
        session,
        name=body.name,
        inverse=body.inverse,
        directed=body.directed,
        colour=body.colour,
        key=body.key if restore else None,
        link_ids=body.link_ids if body.restore else (),
    )
    session.commit()
    return made


@router.patch("/{key}")
def patch_type(key: str, body: RelationPatch, session: Session = Depends(get_session)) -> dict:
    changed = relation_types.update(session, key, {name: getattr(body, name) for name in body.model_fields_set})
    session.commit()
    return changed


@router.delete("/{key}")
def delete_type(key: str, session: Session = Depends(get_session)) -> dict:
    """Delete a custom kind; its links stay, untyped (`relation_types.delete`)."""
    untyped, restore = relation_types.delete(session, key)
    session.commit()
    return {"deleted": key, "links_untyped": untyped, "restore": restore}
