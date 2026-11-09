"""Deleted OCR readings go to the bin (WORLD_CLASS_PLAN 28.4 row 2).

A page's reading (`PageRead`) and a file's whole reading (`ocr_text`,
`vision_ocr_text` on a MediaUpload or an Attachment) are copied into
`BinnedReading` before they are removed, so a delete is undoable after the
toast has gone and after a reload, the same promise the bin makes for a note.
Restoring writes the text back where it came from; a newer reading in that
place is binned in its turn rather than overwritten, so neither is lost.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from tessellate.core.database import Attachment, BinnedReading, MediaUpload, PageRead, utcnow

def page_reads_of(session: Session, kind: str, source_ids: list[int]) -> list[dict]:
    """Every stored page reading of these files as plain dicts, for an undo
    payload: a delete drops them (ids are reused), Undo puts them back."""
    from tessellate.core import undo_bin

    if not source_ids:
        return []
    rows = session.query(PageRead).filter(PageRead.kind == kind, PageRead.source_id.in_(source_ids)).all()
    return [undo_bin.row_dict(r) for r in rows]


def forget_page_reads(session: Session, kind: str, source_ids: list[int]) -> None:
    """Drop the page readings of files that are going: SQLite hands a freed
    highest id to the next file, which would otherwise show the old file's
    words and boxes. Does not commit."""
    if source_ids:
        session.execute(delete(PageRead).where(PageRead.kind == kind, PageRead.source_id.in_(source_ids)))


def put_page_reads_back(session: Session, kind: str, source_id: int, rows: list[dict]) -> None:
    """Undo of `forget_page_reads`, under the id the file came back with."""
    from tessellate.core import undo_bin

    for data in rows or []:
        row = undo_bin.row_from(PageRead, data, keep_id=False)
        row.kind, row.source_id = kind, int(source_id)
        session.add(row)


FIELDS = ("ocr_text", "vision_ocr_text")


def _owner(session: Session, kind: str, source_id: int) -> MediaUpload | Attachment | None:
    model = MediaUpload if kind == "upload" else Attachment
    return session.get(model, int(source_id))


def _label(owner: MediaUpload | Attachment | None) -> str:
    if owner is None:
        return ""
    return (getattr(owner, "original_name", None) or getattr(owner, "filename", "") or "")[:300]


def bin_page(session: Session, kind: str, source_id: int, page: int) -> int | None:
    """Move one page's reading into the bin. Its id, or None when there was no
    reading to move. Does not commit."""
    row = (
        session.query(PageRead)
        .filter(PageRead.kind == kind, PageRead.source_id == int(source_id), PageRead.page == int(page))
        .one_or_none()
    )
    if row is None:
        return None
    binned = BinnedReading(
        kind=kind,
        source_id=int(source_id),
        field="page",
        page=int(page),
        reader=row.reader or "",
        model=row.model or "",
        text=row.text or "",
        caption=row.caption or "",
        caption_model=row.caption_model or "",
        label=_label(_owner(session, kind, source_id)),
        deleted_at=utcnow(),
    )
    session.add(binned)
    session.delete(row)
    session.flush()
    return binned.id


def bin_field(session: Session, kind: str, source_id: int, field: str) -> int | None:
    """Move a file's whole reading (`field`, one of FIELDS) into the bin and
    clear it. Its id, or None when the field held nothing. Does not commit."""
    if field not in FIELDS:
        raise ValueError(f"not a reading field: {field}")
    owner = _owner(session, kind, source_id)
    text = (getattr(owner, field, None) or "").strip() if owner is not None else ""
    if not text:
        return None
    model = (getattr(owner, "vision_ocr_model", None) or "") if field == "vision_ocr_text" else "Tesseract"
    binned = BinnedReading(
        kind=kind,
        source_id=int(source_id),
        field=field,
        page=0,
        reader="vision" if field == "vision_ocr_text" else "tesseract",
        model=model,
        text=text,
        label=_label(owner),
        deleted_at=utcnow(),
    )
    session.add(binned)
    setattr(owner, field, None)
    if field == "vision_ocr_text" and hasattr(owner, "vision_ocr_model"):
        owner.vision_ocr_model = None
    session.flush()
    return binned.id


def restore(session: Session, bin_id: int) -> BinnedReading | None:
    """Put a binned reading back. The restored row (detached from the bin), or
    None when it is not in the bin or its file is gone. Does not commit."""
    binned = session.get(BinnedReading, int(bin_id))
    if binned is None:
        return None
    if binned.field == "page":
        bin_page(session, binned.kind, binned.source_id, binned.page)
        session.add(
            PageRead(
                kind=binned.kind,
                source_id=binned.source_id,
                page=binned.page,
                reader=binned.reader or "vision",
                model=binned.model or "",
                text=binned.text or "",
                caption=binned.caption or "",
                caption_model=binned.caption_model or "",
                regions="",
            )
        )
    else:
        owner = _owner(session, binned.kind, binned.source_id)
        if owner is None:
            return None
        bin_field(session, binned.kind, binned.source_id, binned.field)
        setattr(owner, binned.field, binned.text)
        if binned.field == "vision_ocr_text" and hasattr(owner, "vision_ocr_model"):
            owner.vision_ocr_model = binned.model or None
    session.delete(binned)
    session.flush()
    return binned


def binned(session: Session) -> list[BinnedReading]:
    """What is in the bin, newest first."""
    return session.query(BinnedReading).order_by(BinnedReading.deleted_at.desc()).all()


def purge(session: Session, bin_id: int) -> bool:
    """Delete one binned reading for good. Does not commit."""
    row = session.get(BinnedReading, int(bin_id))
    if row is None:
        return False
    session.delete(row)
    return True


def empty(session: Session) -> int:
    """Delete every binned reading. Does not commit."""
    return session.query(BinnedReading).delete(synchronize_session=False)


def purge_expired(session: Session, days: int) -> int:
    """Drop readings binned more than `days` ago. Does not commit."""
    cutoff = utcnow() - timedelta(days=days)
    return (
        session.query(BinnedReading)
        .filter(BinnedReading.deleted_at < cutoff)
        .delete(synchronize_session=False)
    )
