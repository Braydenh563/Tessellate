"""Find and merge near-duplicate notes.

Finding them needs no AI, it's word overlap on normalised text, so it works
with nothing running and the score is explainable rather than a black box.

Merging is where judgement helps, so it comes two ways. With the AI running it
can write one note that keeps everything the originals said. Without it, the
notes are joined with a separator, which is worse prose but loses nothing, 
and losing nothing is the only property that actually matters here.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from tessellate.api import paging
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.ai import drafter
from tessellate.core import deps, jobruns
from tessellate.core.database import Entry
from tessellate.core.deps import get_session
from tessellate.entry import duplicates, manager

router = APIRouter(prefix="/duplicates", tags=["duplicates"])

MERGE_PROMPT = (
    "These notes say much the same thing. Combine them into ONE note that "
    "keeps every distinct fact from all of them. Don't invent anything, don't "
    "add a preamble, and keep the user's voice. Reply with the note text only."
)


class MergeBody(BaseModel):
    ids: list[int] = Field(min_length=2, max_length=20)
    # When false, or when the AI isn't running, the notes are joined verbatim.
    use_ai: bool = True


class PreviewBody(BaseModel):
    ids: list[int] = Field(min_length=2, max_length=20)
    use_ai: bool = True


def _load(session: Session, ids: list[int]) -> list[Entry]:
    found = []
    for entry_id in dict.fromkeys(ids):
        entry = session.get(Entry, entry_id)
        if entry is None or entry.is_deleted:
            raise HTTPException(status_code=404, detail=f"Note {entry_id} could not be found.")
        if entry.is_private:
            raise HTTPException(
                status_code=400, detail="Private notes can't be merged this way."
            )
        found.append(entry)
    if len(found) < 2:
        raise HTTPException(status_code=400, detail="Pick at least two notes to merge.")
    return found


def _joined(entries: list[Entry]) -> str:
    """The no-AI merge: every note, in order, separated. Nothing is lost."""
    return "\n\n---\n\n".join(e.content.strip() for e in entries)


#: How many duplicate groups one response carries. A group is several whole
#: notes, so this list is heavier per row than any other in the app, and the
#: screen it feeds is one somebody works through a group at a time.
#: Default equal to the maximum, same reason as the two above: the one caller
#: (`app.js` 36995) reads `{threshold, groups, total}` whole.
DUPLICATE_PAGE_SIZE = 500
DUPLICATE_PAGE_SIZE_MAX = 500


@router.get("")
def list_duplicates(
    response: Response,
    threshold: float = duplicates.DEFAULT_THRESHOLD,
    limit: int = Query(default=DUPLICATE_PAGE_SIZE, ge=1, le=DUPLICATE_PAGE_SIZE_MAX),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = paging.cursor_param(),
    session: Session = Depends(get_session),
) -> dict:
    """A page of the groups of notes that look like the same note.

    `total` is every group the scan found, not the page: the number the screen
    opens with ("11 possible duplicates") has to be the real one, or the first
    thing this feature says is wrong.
    """
    offset = paging.start(cursor, offset)
    threshold = min(max(threshold, 0.4), 1.0)
    # Only the first page is "a scan": the pages after it re-run the same
    # computation to slice it, and recording each would make "last scan" mean
    # "last time someone clicked next".
    if offset == 0:
        with jobruns.job_run("duplicate-scan", origin="you") as run:
            groups = duplicates.find_duplicates(session, threshold)
            run.result = (
                f"{len(groups)} possible duplicate group{'' if len(groups) == 1 else 's'}"
                if groups
                else "no duplicates found"
            )
    else:
        groups = duplicates.find_duplicates(session, threshold)
    paging.finish(response, offset, limit, len(groups))
    return {
        "threshold": threshold,
        "groups": groups[offset : offset + limit],
        "total": len(groups),
    }


@router.post("/preview")
def preview_merge(body: PreviewBody, session: Session = Depends(get_session)) -> dict:
    """What the merged note would say, shown before anything is changed."""
    entries = _load(session, body.ids)
    fallback = _joined(entries)
    ollama = deps.get_ollama()

    if not body.use_ai or not ollama.is_running():
        return {"merged": fallback, "used_ai": False, "ollama_running": ollama.is_running()}

    # The drafter already knows how to rewrite text to an instruction, and
    # crucially it returns the input unchanged when the model can't help.
    merged, _thinking = drafter.compose(
        "", fallback, deps.get_model_manager(), ollama, instruction=MERGE_PROMPT
    )
    used_ai = merged.strip() != fallback.strip()
    return {"merged": merged or fallback, "used_ai": used_ai, "ollama_running": True}


@router.post("/merge")
def merge_notes(body: MergeBody, session: Session = Depends(get_session)) -> dict:
    """Replace several notes with one.

    The originals go to the recycle bin rather than being destroyed. A merge is
    the one operation here that can silently lose writing, so it has to be
    undoable: the bin is that undo.
    """
    entries = _load(session, body.ids)
    preview = preview_merge(PreviewBody(ids=body.ids, use_ai=body.use_ai), session)

    keeper = entries[0]
    # Keep every tag from every note; a tag is a deliberate choice and dropping
    # one during a tidy-up is exactly the kind of quiet loss to avoid.
    tags: list[str] = []
    for entry in entries:
        for tag in manager.entry_tags(entry):
            if tag not in tags:
                tags.append(tag)

    keeper.content = preview["merged"]
    keeper.tags = json.dumps(tags)  # `edited_at` is stamped by the before_flush hook (the text changed)
    manager.log_action(
        session, "edited", "entry", keeper.id, f"merged {len(entries)} notes"
    )
    for entry in entries[1:]:
        manager.soft_delete_entry(session, entry)

    session.commit()
    session.refresh(keeper)
    return {
        "id": keeper.id,
        "content": keeper.content,
        "merged_count": len(entries),
        "used_ai": preview["used_ai"],
        "binned_ids": [e.id for e in entries[1:]],
    }
