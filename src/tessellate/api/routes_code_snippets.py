"""The code editor's snippets library (INBOX 788; DOCUMENTS_PLAN "Placed from
INBOX, 2026-10-10 (code as documents)").

The owner: "maybe even add a code modules library like with the whiteboard
and mindmap??". The board library's pattern, and its rows: a snippet is a
`board_library_items` row of kind `snippet` in the person's "Yours" library,
so it is notebook-wide like a saved shape, has the same bin (`deleted_at`,
with `DELETE /board-library/{id}` and its `restore` as the toast's Undo) and
needs no new table. The board's own listing leaves snippets out unless asked
by kind (`routes_board_library.list_library`), and its export does too, so a
board library file never carries code its import would refuse.

The built-in snippets are the editor's completion snippets
(`DOC_CODE_SNIPPETS` in documents-code.js), listed by the client from that
table: one list of them, not a second copy here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.api.routes_board_library import MAX_NAME, SNIPPET_KIND, _clean_tags, _item_out, _yours
from tessellate.core import events, filetypes
from tessellate.core.database import BoardLibraryItem, utcnow
from tessellate.core.deps import get_session
from tessellate.repo import board_library as board_library_repo

router = APIRouter(tags=["code-snippets"])

#: A snippet is a piece of a file, never a file's worth: 64 KB of code.
MAX_CODE_CHARS = 64 * 1024


class SnippetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_NAME)
    language: str = Field(default="txt", max_length=40)
    code: str = Field(min_length=1, max_length=MAX_CODE_CHARS)
    tags: list[str] = []


class SnippetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=MAX_NAME)
    language: str | None = Field(default=None, max_length=40)
    code: str | None = Field(default=None, min_length=1, max_length=MAX_CODE_CHARS)
    tags: list[str] | None = None
    favourite: bool | None = None


def _payload(language: str, code: str) -> dict:
    if not code.strip():
        raise HTTPException(status_code=422, detail="A snippet needs some code.")
    return {"language": filetypes.normalise(language), "code": code}


def _snippet_or_404(db: Session, snippet_id: int) -> BoardLibraryItem:
    row = db.get(BoardLibraryItem, snippet_id)
    if row is None or row.kind != SNIPPET_KIND:
        raise HTTPException(status_code=404, detail="That snippet could not be found.")
    return row


@router.get("/code-snippets")
def list_snippets(
    language: str | None = None,
    q: str | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_session),
) -> dict:
    """The person's snippets, newest first; `language` and `q` (words in the
    name, the tags or the code's language) narrow it."""
    rows = board_library_repo.snippets(db, SNIPPET_KIND)
    wanted = filetypes.normalise(language) if language else None
    words = (q or "").lower().split()
    items = []
    for row in rows:
        lang = (row.payload or {}).get("language", "txt")
        haystack = " ".join([row.name.lower(), lang, *(row.tags or [])])
        if (wanted is None or lang == wanted) and all(w in haystack for w in words):
            items.append(_item_out(row).model_dump(mode="json"))
    return {"items": items[:limit], "total": len(items)}


@router.post("/code-snippets", status_code=201)
@events.writes("library_item", "created")
def create_snippet(body: SnippetCreate, db: Session = Depends(get_session)) -> dict:
    row = BoardLibraryItem(
        library_id=_yours(db).id, kind=SNIPPET_KIND, name=body.name.strip()[:MAX_NAME],
        tags=_clean_tags(body.tags), payload=_payload(body.language, body.code),
        favourite=False, use_count=0, version=1,
    )
    db.add(row)
    db.flush()
    events.record(db, "created", "library_item", row.id, row.name[:80], payload={"after": {"name": row.name, "kind": SNIPPET_KIND}})
    db.commit()
    db.refresh(row)
    return _item_out(row).model_dump(mode="json")


@router.put("/code-snippets/{snippet_id}")
@events.writes("library_item", "edited")
def update_snippet(snippet_id: int, body: SnippetUpdate, db: Session = Depends(get_session)) -> dict:
    row = _snippet_or_404(db, snippet_id)
    before = {"name": row.name, "tags": row.tags, "favourite": row.favourite, "version": row.version}
    if body.name is not None:
        row.name = body.name.strip()[:MAX_NAME]
    if body.tags is not None:
        row.tags = _clean_tags(body.tags)
    if body.favourite is not None:
        row.favourite = body.favourite
    if body.code is not None or body.language is not None:
        current = row.payload or {}
        row.payload = _payload(body.language or current.get("language", "txt"), body.code or current.get("code", ""))
        row.version = (row.version or 1) + 1
    row.updated_at = utcnow()
    events.record(db, "edited", "library_item", row.id, row.name[:80],
                  payload={"before": before, "after": {"name": row.name, "tags": row.tags, "favourite": row.favourite, "version": row.version}})
    db.commit()
    db.refresh(row)
    return _item_out(row).model_dump(mode="json")
