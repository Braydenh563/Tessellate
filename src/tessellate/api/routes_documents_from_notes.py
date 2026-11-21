"""Many notes composed into one draft document (L-graph-1).

The graph's selection (or a cluster) is several notes; `expandNoteIntoDocument`
promoted one. This takes the ids and writes one document: a section per note
under its own title, oldest first (the order they were written reads as an
account), and a closing line naming the notes it came from. No model: the
structure is the notes'. Private notes never go in, whether the vault is
open or not, because a document is not sealed and would carry their words
out in the clear.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.api.routes_documents import _full
from tessellate.core import filetypes
from tessellate.core.database import Entry
from tessellate.core.deps import get_session
from tessellate.entry import manager_text
from tessellate.entry.properties import strip as strip_properties
from tessellate.repo import documents as document_repo

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_NOTES = 200


class FromNotes(BaseModel):
    note_ids: list[int] = Field(max_length=MAX_NOTES)
    title: str = ""


def _section(entry: Entry) -> str:
    text = strip_properties(manager_text.readable_content(entry)).strip()
    lines = text.splitlines()
    heading = manager_text.extract_title(text)
    if heading:
        rest = "\n".join(lines[1:]).strip()
    else:
        heading, rest = (lines[0].strip() if lines else "Untitled"), "\n".join(lines[1:]).strip()
    return f"## {heading[:120] or 'Untitled'}\n\n{rest}".strip()


@router.post("/from-notes", status_code=201)
def document_from_notes(body: FromNotes, session: Session = Depends(get_session)) -> dict:
    wanted = list(dict.fromkeys(body.note_ids))
    rows = [
        e
        for e in session.scalars(select(Entry).where(Entry.id.in_(wanted))).all()
        if not (e.is_deleted or e.is_board or e.is_private or e.is_draft)
    ]
    if not rows:
        raise HTTPException(status_code=422, detail="None of those notes can go in a document.")
    rows.sort(key=lambda e: (e.created_at, e.id))
    ids = ", ".join(f"#{e.id}" for e in rows)
    content = "\n\n".join(_section(e) for e in rows) + f"\n\n---\n\nComposed from notes {ids}.\n"
    title = body.title.strip()[:120] or f"Draft from {len(rows)} notes"
    document = document_repo.create(session, title=title, content=content, file_type=filetypes.DEFAULT_FILE_TYPE)
    session.commit()
    return _full(document, session)
