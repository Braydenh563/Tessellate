"""The reading bin's routes: bin a file's or a recording's reading, restore it, purge it.

Split out of routes_files_readings.py (its 800-line cap, tests/test_file_size_ratchet_l624.py);
the code reaches the files module through `rf.<name>`, as the readings routes do, so a patch on it applies.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tessellate.api import routes_files as rf
from tessellate.core import deps, reading_bin
from tessellate.core.deps import get_session

router = APIRouter(tags=["files"])


class ReadingBinnedOut(BaseModel):
    """A whole-file reading moved to the bin: its row there, for Undo."""

    binned_id: int | None = None


_READING_FIELDS = {"tesseract": "ocr_text", "vision": "vision_ocr_text"}


def _bin_file_reading(session: Session, kind: str, source_id: int, source: str) -> ReadingBinnedOut:
    field = _READING_FIELDS.get(source)
    if field is None:
        raise HTTPException(status_code=422, detail="A reading is either tesseract or vision.")
    binned_id = reading_bin.bin_field(session, kind, source_id, field)
    session.commit()
    key = (kind, int(source_id))
    rf._forget_regions(key)
    with deps.get_db().session() as fresh:
        rf._reindex_file(fresh, kind, source_id)
        fresh.commit()
    return ReadingBinnedOut(binned_id=binned_id)


@router.delete("/media/{upload_id}/readings/{source}", response_model=ReadingBinnedOut)
def delete_media_reading(
    upload_id: int, source: str, session: Session = Depends(get_session)
) -> ReadingBinnedOut:
    """Delete an image's whole reading (Tesseract's or the vision model's)
    into the bin (WORLD_CLASS_PLAN 28.4 row 2)."""
    rf._existing_upload(session, upload_id)
    return _bin_file_reading(session, "upload", upload_id, source)


@router.delete("/files/{attachment_id}/readings/{source}", response_model=ReadingBinnedOut)
def delete_attachment_reading(
    attachment_id: int, source: str, session: Session = Depends(get_session)
) -> ReadingBinnedOut:
    """`delete_media_reading`'s sibling for a note's own file."""
    rf._existing_attachment(session, attachment_id)
    return _bin_file_reading(session, "attachment", attachment_id, source)


class ReadingRestoredOut(BaseModel):
    kind: str
    source_id: int
    field: str
    page: int = 0


@router.post("/reading-bin/{bin_id}/restore", response_model=ReadingRestoredOut)
def restore_binned_reading(bin_id: int, session: Session = Depends(get_session)) -> ReadingRestoredOut:
    """Put a deleted reading back where it came from (Undo, or the Bin)."""
    restored = reading_bin.restore(session, bin_id)
    if restored is None:
        raise HTTPException(status_code=404, detail="That reading is no longer in the bin.")
    out = ReadingRestoredOut(
        kind=restored.kind, source_id=restored.source_id, field=restored.field, page=restored.page
    )
    session.commit()
    if out.field != "page":
        rf._forget_regions((out.kind, out.source_id))
    with deps.get_db().session() as fresh:
        rf._reindex_file(fresh, out.kind, out.source_id)
        fresh.commit()
    return out


@router.delete("/reading-bin/{bin_id}/purge")
def purge_binned_reading(bin_id: int, session: Session = Depends(get_session)) -> dict:
    """Delete a binned reading for good, from the Bin's own menu."""
    if not reading_bin.purge(session, bin_id):
        raise HTTPException(status_code=404, detail="That reading is no longer in the bin.")
    session.commit()
    return {"purged": True}
