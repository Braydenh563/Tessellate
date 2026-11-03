"""Tag manager endpoints: see, rename, merge and delete tags across notes, and
add or remove tags on a chosen set of notes.

Every write here is one transaction, records a revision and an `edited` event
per note it touched (the way `PUT /entries/{id}` does, so each note's history
shows it), and answers with `before`: the tags each changed note had, which is
what `POST /tags/restore` takes to undo it in one transaction too."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.core.deps import get_session
from tessellate.repo import tags as tags_repo

router = APIRouter(prefix="/tags", tags=["tags"])


class RenameBody(BaseModel):
    old: str = Field(min_length=1)
    new: str = Field(min_length=1, max_length=60)


class DeleteBody(BaseModel):
    #: One tag (`name`) or several (`names`), taken off in one transaction.
    name: str = ""
    names: list[str] = Field(default_factory=list, max_length=200)


#: How many tags one response carries. Higher than the other page sizes on
#: purpose: this list feeds a tag cloud and a filter picker, and a picker
#: showing the first page of your tags is a picker that has lost some, so the
#: cap is a guard against a pathological notebook rather than a page anyone
#: is expected to walk. `X-Total-Count` is what says it was reached.
TAGS_PAGE_SIZE = 1000


@router.get("")
def list_tags(
    response: Response,
    limit: int = Query(default=TAGS_PAGE_SIZE, ge=1, le=5000),
    session: Session = Depends(get_session),
) -> dict[str, int]:
    """Every tag in use → how many entries carry it (most used first)."""
    counts, total = tags_repo.page(session, limit=limit)
    response.headers["X-Total-Count"] = str(total)
    return counts


class MergeBody(BaseModel):
    names: list[str] = Field(min_length=1, max_length=200)
    into: str = Field(min_length=1, max_length=60)


class BulkBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=5000)
    add: list[str] = Field(default_factory=list, max_length=100)
    remove: list[str] = Field(default_factory=list, max_length=100)


class RestoreBody(BaseModel):
    #: JSON object keys are strings; they are note ids.
    notes: dict[int, list[str]] = Field(max_length=5000)


def _answer(before: dict[int, list[str]]) -> dict:
    return {"changed": len(before), "before": {str(i): tags for i, tags in before.items()}}


@router.post("/rename")
def rename_tag(body: RenameBody, session: Session = Depends(get_session)) -> dict:
    """Rename a tag everywhere; renaming onto an existing tag merges them."""
    try:
        before = tags_repo.rename(session, [body.old], body.new)
    except ValueError as exc:
        # A blank new name: a plain 400, not a tag of "" on every note.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.commit()
    return _answer(before)


@router.post("/merge")
def merge_tags(body: MergeBody, session: Session = Depends(get_session)) -> dict:
    """Fold several tags into one name (which may be new or already exist)."""
    try:
        before = tags_repo.rename(session, body.names, body.into)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.commit()
    return _answer(before)


@router.post("/delete")
def delete_tag(body: DeleteBody, session: Session = Depends(get_session)) -> dict:
    """Take a tag off every note that has it. The notes stay."""
    wanted = [t for t in [body.name, *body.names] if t.strip()]
    if not wanted:
        raise HTTPException(status_code=400, detail="Say which tag to remove.")
    before = tags_repo.remove(session, wanted)
    session.commit()
    return _answer(before)


@router.post("/bulk")
def bulk_edit_tags(body: BulkBody, session: Session = Depends(get_session)) -> dict:
    """Add tags to, and remove tags from, the chosen notes in one go."""
    before = tags_repo.bulk_edit(session, body.ids, body.add, body.remove)
    session.commit()
    return _answer(before)


@router.post("/restore")
def restore_tags(body: RestoreBody, session: Session = Depends(get_session)) -> dict:
    """Put notes' tags back to the given lists: the undo of the writes above."""
    before = tags_repo.restore(session, body.notes)
    session.commit()
    return _answer(before)


#: How many turned-down tags the tag manager lists.
TURNED_DOWN_LISTED = 50


@router.get("/turned-down")
def list_turned_down(
    response: Response,
    limit: int = Query(default=TURNED_DOWN_LISTED, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> list[dict]:
    """The tags turned down when offered, most often first, and whether that
    now makes them offered less (INBOX 781: learning from discards across
    notes, with a way back)."""
    from tessellate.ai import tagging

    rows = sorted(tagging.turned_down(session).values(), key=lambda row: (-row[1], row[0].casefold()))
    response.headers["X-Total-Count"] = str(len(rows))
    return [
        {"tag": tag, "notes": notes, "damped": notes >= tagging.TURNED_DOWN_OFTEN}
        for tag, notes in rows[:limit]
    ]


class OfferAgainBody(BaseModel):
    tag: str = Field(min_length=1, max_length=60)


@router.post("/turned-down/offer-again")
def offer_tag_again(body: OfferAgainBody, session: Session = Depends(get_session)) -> dict:
    """Forget the turn-downs so far: the tag is offered as before."""
    from tessellate.ai import tagging

    tagging.offer_again(session, body.tag)
    return {"ok": True}
