"""Tags, a category and properties for the documents and files a selection
holds (decision 65, L-world-class-392 and 393): what the Library's Documents
and Media selection bars write. One transaction per call; every write answers
with `before`, which `/restore` takes for the one Undo."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.core.deps import get_session
from tessellate.repo import library_meta

router = APIRouter(prefix="/library/meta", tags=["library"])


class BulkBody(BaseModel):
    #: "document" or "media"; the repository refuses any other.
    kind: str
    ids: list[int] = Field(min_length=1, max_length=5000)
    add: list[str] = Field(default_factory=list, max_length=100)
    remove: list[str] = Field(default_factory=list, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    clear_category: bool = False
    property_name: str | None = Field(default=None, max_length=library_meta.MAX_NAME)
    property_value: str | None = Field(default=None, max_length=library_meta.MAX_VALUE)


class RestoreBody(BaseModel):
    kind: str
    items: list[dict] = Field(min_length=1, max_length=5000)


@router.get("")
def read_meta(kind: str, ids: str = Query(max_length=40000), session: Session = Depends(get_session)) -> dict:
    """Each named row's tags, category and properties."""
    wanted = [int(i) for i in ids.split(",") if i.strip().isdigit()][:5000]
    return {"items": library_meta.read(session, kind, wanted)}


@router.post("/bulk")
def bulk(body: BulkBody, session: Session = Depends(get_session)) -> dict:
    before = library_meta.bulk_edit(
        session, body.kind, body.ids, add=body.add, remove=body.remove, category=body.category,
        clear_category=body.clear_category, prop_name=body.property_name, prop_value=body.property_value,
    )
    session.commit()
    return {"changed": len(before), "before": before}


@router.post("/restore")
def restore(body: RestoreBody, session: Session = Depends(get_session)) -> dict:
    before = library_meta.restore(session, body.kind, body.items)
    session.commit()
    return {"changed": len(before), "before": before}
