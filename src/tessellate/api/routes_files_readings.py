"""Reading-side routes of files and media: ranges, regions, page reads, the reading bin, loop cleaning.

Split out of routes_files.py (K24); mounted onto that module's router at its foot.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from tessellate.ai import captioning, vision_ocr
from tessellate.api import routes_files as rf
from tessellate.api.routes_files import AttachmentGalleryOut, MediaUploadOut, OcrPageReadOut
from tessellate.core import (
    deps,
    ocr,
    pdfpages,
    reading_bin,
)
from tessellate.core.deps import get_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["files"])


class OcrRangeReadOut(BaseModel):
    """Several pages of a document, read by one of the readers above."""

    pages: list[OcrPageReadOut] = []
    #: How many pages the spec asked for *after* clamping to the document, so
    #: the UI can say "read 8 of the 20 you asked for" rather than silently
    #: returning fewer.
    requested: int = 0
    read: int = 0
    page_count: int = 0
    message: str = ""
    #: Set by a page reading's delete: the bin row that holds it now, which
    #: Undo restores (`POST /reading-bin/{id}/restore`).
    binned_id: int | None = None


#: How many pages one range request may read. A vision pass is seconds per
#: page, so "all" on a 300-page scan is not a request anyone means to make
#: synchronously: the cap keeps a mis-click from occupying the model for an
#: hour, and the response says plainly how far it got so the reader can ask
#: for the next block rather than wondering.
MAX_RANGE_PAGES = 25


def _parse_page_spec(spec: str, count: int) -> list[int]:
    """`"all"`, `"3"`, `"1-5"`, `"1,4,7-9"` -> sorted 0-based page indices.

    **One-based on the way in, because that is what the page rail shows and
    what a person means by "page 1".** Anything unparseable is skipped rather
    than raising: a range typed with a stray character should read the pages
    it could understand, not refuse the lot.
    """
    text = (spec or "").strip().lower()
    if not text or text in {"all", "*"}:
        return list(range(count))
    wanted: set[int] = set()
    for part in text.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part[1:]:  # not a leading minus
            start_text, _, end_text = part.partition("-")
            if not (start_text.isdigit() and end_text.isdigit()):
                continue
            start, end = int(start_text), int(end_text)
            if start > end:
                start, end = end, start
            wanted.update(range(start - 1, end))
        elif part.isdigit():
            wanted.add(int(part) - 1)
    return sorted(i for i in wanted if 0 <= i < count)


#: Tesseract reads a rendered page in about a tenth of a second, so the cap
#: that keeps a mis-click from occupying a *model* for an hour has no reason to
#: apply to it. Still bounded: a 2,000-page scan is not a synchronous request
#: either: just bounded by what is actually slow.
MAX_TESSERACT_RANGE_PAGES = 200


def _read_range(
    path: Path,
    spec: str,
    reader: str = "vision",
    key: tuple[str, int] | None = None,
) -> OcrRangeReadOut:
    """Read every page the spec names, reusing the single-page reader.

    Deliberately a loop over `rf._read_page` rather than a second implementation:
    one place decides what "no rasteriser", "no vision model" and "nothing
    legible" mean, and a range read cannot drift away from what the per-page
    button does.
    """
    if not pdfpages.available():
        return OcrRangeReadOut(
            message=(
                "Reading a PDF needs the small PDF rasteriser: install the "
                "“PDF pages” package in Settings, Packages."
            )
        )
    count = pdfpages.page_count(path)
    if count <= 0:
        return OcrRangeReadOut(message="That PDF could not be opened.")
    indices = _parse_page_spec(spec, count)
    if not indices:
        return OcrRangeReadOut(
            page_count=count,
            message=f"No pages matched that range. This document has {count} page(s).",
        )
    requested = len(indices)
    limit = MAX_TESSERACT_RANGE_PAGES if reader in rf.LOCAL_READERS else MAX_RANGE_PAGES
    capped = indices[:limit]
    pages = [rf._read_page(path, index, reader, key) for index in capped]
    read = sum(1 for page in pages if page.text)
    note = ""
    if requested > len(capped):
        last = capped[-1] + 1
        note = (
            f" Stopped after {len(capped)} pages (the limit for one go), "
            f"ask for {last + 1}-{min(last + limit, count)} to carry on."
        )
    return OcrRangeReadOut(
        pages=pages,
        requested=requested,
        read=read,
        page_count=count,
        message=(f"Read {read} of {len(capped)} page(s)." + note).strip(),
    )


def _stored_range(key: tuple[str, int] | None) -> OcrRangeReadOut:
    """What is already known about a document, in the shape a range read returns.

    The same shape on purpose: the workspace has one renderer for "here are
    some pages of text", and giving stored readings a different envelope would
    mean a second one that could drift from it.
    """
    pages = rf._stored_page_reads(key)
    if not pages:
        return OcrRangeReadOut()
    #: Counted on `text`, not on the number of rows: a page that has only been
    #: *described* (Phase 7.3: `PageRead.caption` with no reading beside it)
    #: has a row here too, and calling it "read" would tell the workspace, the
    #: Files row's badge and the lightbox's page chips that a transcription
    #: exists where none does.
    read = sum(1 for page in pages if (page.text or "").strip())
    return OcrRangeReadOut(
        pages=pages,
        requested=len(pages),
        read=read,
        message=(f"{read} page(s) already read." if read != 1 else "1 page already read."),
    )


@router.post("/files/{attachment_id}/ocr-range-read", response_model=OcrRangeReadOut)
def attachment_ocr_range_read(
    attachment_id: int,
    pages: str = "all",
    reader: str = "vision",
    session: Session = Depends(get_session),
) -> OcrRangeReadOut:
    """Read a whole PDF, or the pages named by `pages` (e.g. `1-5`, `2,7`)."""
    reader = rf._checked_reader(reader)
    attachment = rf._existing_attachment(session, attachment_id)
    if Path(attachment.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=415, detail="Only PDFs are read by page range.")
    path = rf._within(deps.get_config().uploads_dir, attachment.stored_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That file is no longer on disk.")
    return _read_range(path, pages, reader, rf._page_read_key(attachment_id, None))


@router.post("/media/{upload_id}/ocr-range-read", response_model=OcrRangeReadOut)
def media_ocr_range_read(
    upload_id: int,
    pages: str = "all",
    reader: str = "vision",
    session: Session = Depends(get_session),
) -> OcrRangeReadOut:
    """Read a whole PDF, or the pages named by `pages` (e.g. `1-5`, `2,7`)."""
    reader = rf._checked_reader(reader)
    upload = rf._existing_upload(session, upload_id)
    if Path(upload.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=415, detail="Only PDFs are read by page range.")
    path = rf._within(deps.get_config().data_dir / "media", upload.filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That file is no longer on disk.")
    return _read_range(path, pages, reader, rf._page_read_key(None, upload_id))


@router.post("/files/{attachment_id}/ocr-page-read", response_model=OcrPageReadOut)
def attachment_ocr_page_read(
    attachment_id: int,
    page: int = 0,
    reader: str = "vision",
    session: Session = Depends(get_session),
) -> OcrPageReadOut:
    reader = rf._checked_reader(reader)
    attachment = rf._existing_attachment(session, attachment_id)
    if Path(attachment.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=415, detail="Only PDF pages are read one at a time.")
    path = rf._within(deps.get_config().uploads_dir, attachment.stored_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That file is no longer on disk.")
    return rf._read_page(path, page, reader, rf._page_read_key(attachment_id, None))


@router.post("/media/{upload_id}/ocr-page-read", response_model=OcrPageReadOut)
def media_ocr_page_read(
    upload_id: int,
    page: int = 0,
    reader: str = "vision",
    session: Session = Depends(get_session),
) -> OcrPageReadOut:
    reader = rf._checked_reader(reader)
    upload = rf._existing_upload(session, upload_id)
    if Path(upload.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=415, detail="Only PDF pages are read one at a time.")
    path = rf._within(deps.get_config().data_dir / "media", upload.filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That file is no longer on disk.")
    return rf._read_page(path, page, reader, rf._page_read_key(None, upload_id))


class OcrRegionReadOut(BaseModel):
    """One rectangle a person drew on a page, read or described.

    Deliberately *not* `OcrPageReadOut`: nothing here is stored, and a shape
    that carries `page` and looks like a stored page reading would be an
    invitation to file it as one. Asked as a question and it is a good one:
    *"can there be a way for the user to manually outline and single out
    regions on a pdf or similar document and then the ai will read what is in
    those regions?? like maybe the user can outline a graph or diagram on a pdf
    slide and then the user cna get the image or ocr model to analyse and
    caption that thing."*
    """

    #: Which page the rectangle was drawn on, echoed back so the answer can be
    #: labelled with it: a result that does not say where it came from is the
    #: thing the region overlay exists to avoid.
    page: int = 0
    #: "read" or "describe", echoed for the same reason.
    mode: str = "read"
    text: str = ""
    model: str = ""
    message: str = ""


#: A drawn rectangle is a crop of a page render, not an upload: at the viewer's
#: own 2x scale a full page is a few hundred KB and a region is far less. The
#: cap is generous enough never to refuse a real crop and small enough that a
#: mistyped request cannot stream 50 MB into memory before anything looks at it.
MAX_REGION_BYTES = 8 * 1024 * 1024


def _region_image(crop: UploadFile) -> bytes:
    """The uploaded crop's bytes, refused if it is not a PNG or too large.

    **Read into memory rather than streamed to disk**, unlike `/media/upload`:
    nothing here is stored, the model is handed a data URI built from these
    bytes, and writing a scratch file the request then has to clean up is more
    moving parts for no gain. The size cap is what makes that safe.

    The magic-number check is not decoration either: this is the one endpoint
    in the app that takes an image nobody in the notebook uploaded, and
    `canvas.toBlob` produces a PNG, so anything else here is a caller doing
    something other than what this route is for.
    """
    data = crop.file.read(MAX_REGION_BYTES + 1)
    if len(data) > MAX_REGION_BYTES:
        raise HTTPException(status_code=413, detail="That region is too large to read.")
    if not data:
        raise HTTPException(status_code=400, detail="That region came through empty.")
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=415, detail="That region has to be a PNG image.")
    return data


def _require_region_reader(local: bool, reader: str) -> None:
    """409 unless the local engine, or the AI model, is there to do the read."""
    if local:
        reason = ocr.unavailable_reason(rf._engine_choice(reader))
        if reason:
            raise HTTPException(status_code=409, detail=reason)
    elif not deps.get_ollama().is_running():
        raise HTTPException(status_code=409, detail="The AI model isn't running.")


def _region_model(mode: str, reader: str, local: bool) -> str:
    """The model that reads or describes a region; 409 when none is installed.

    A read uses whichever reader the workspace's picker named; a describe is
    always the general vision model, for the same reason `rf._describe_page`
    is: a dedicated document reader is tuned to transcribe, not to explain.
    """
    if local:
        model = "tesseract"
    elif mode == "read":
        model = rf._reader_model(reader)
    else:
        model = deps.get_model_manager().resolve_vision_model(deps.get_ollama()) or ""
    if not model:
        raise HTTPException(
            status_code=409,
            detail="No installed model can read images. Install or "
            "pick one in Settings, Models.",
        )
    return model


def _region_text(data: bytes, mode: str, reader: str, local: bool, model: str) -> str:
    """The text of a cropped region: a description, a local read, or a vision read."""
    with tempfile.TemporaryDirectory(prefix="mm-region-") as scratch:
        crop_path = Path(scratch) / "region.png"
        crop_path.write_bytes(data)
        if mode == "describe":
            #: `count=1` and page 0: the prompt's "page N of M" would be a
            #: lie about a crop, and what is wanted here is a description of
            #: the *figure*, which is what the prompt asks for either way.
            return captioning.page_caption_text(crop_path, 0, 1, model, deps.get_ollama())
        if local:
            return (rf._local_region_text(crop_path, rf._engine_choice(reader)) or "").strip()
        return (vision_ocr.vision_ocr_text(crop_path, model, deps.get_ollama()) or "").strip()


def _read_region(crop: UploadFile, page: int, mode: str, reader: str) -> OcrRegionReadOut:
    """Read or describe one drawn rectangle. Never stores anything.

    **Why the crop is uploaded rather than described by four numbers.** The
    obvious alternative is to send the rectangle and let this render and crop
    the page itself: but the workspace already has the page raster on screen,
    the person drew the rectangle *on that raster*, and cropping it in the
    browser guarantees the model is handed exactly what they outlined. It also
    means the same gesture works on a plain image, which has no page to
    re-render at all.

    **Why nothing is stored.** `PageRead` is keyed by page, and a region is a
    part of a page, several of them, usually, each answering a different
    question. Filing one over the page's reading would destroy a transcription
    to save a note about one chart in the corner of it.
    """
    mode = (mode or "read").strip().lower()
    if mode not in {"read", "describe"}:
        raise HTTPException(
            status_code=400, detail="Pick read or describe."
        )
    data = _region_image(crop)
    if mode == "read":
        reader = rf._checked_reader(reader)
    local = mode == "read" and reader in rf.LOCAL_READERS
    _require_region_reader(local, reader)
    model = _region_model(mode, reader, local)
    label = "Describing" if mode == "describe" else "Reading"
    token = vision_ocr.register_page_read(
        f"{label} a region of page {page + 1}",
        model=ocr.engine_name(rf._engine_choice(reader)) if local else model,
    )
    try:
        text = _region_text(data, mode, reader, local, model)
    finally:
        vision_ocr.finish_page_read(token)
    text = (text or "").strip()
    nothing = (
        f"{model} had nothing to say about that region."
        if mode == "describe"
        else "No text was found in that region."
    )
    return OcrRegionReadOut(
        page=page,
        mode=mode,
        text=text,
        model=model if text else "",
        message="" if text else nothing,
    )


@router.post("/files/{attachment_id}/region-read", response_model=OcrRegionReadOut)
def attachment_region_read(
    attachment_id: int,
    crop: UploadFile,
    page: int = Form(0),
    mode: str = Form("read"),
    reader: str = Form("vision"),
    session: Session = Depends(get_session),
) -> OcrRegionReadOut:
    """Read or describe a rectangle drawn on one page of an attached file.

    The attachment is looked up and not otherwise used, and that is the point:
    it is the authorisation check. Without it this would be "run a model on any
    image anyone posts", which is a different endpoint from the one that was
    asked for.
    """
    rf._existing_attachment(session, attachment_id)
    return _read_region(crop, page, mode, reader)


@router.post("/media/{upload_id}/region-read", response_model=OcrRegionReadOut)
def media_region_read(
    upload_id: int,
    crop: UploadFile,
    page: int = Form(0),
    mode: str = Form("read"),
    reader: str = Form("vision"),
    session: Session = Depends(get_session),
) -> OcrRegionReadOut:
    """`attachment_region_read`'s sibling for a `/media/` upload."""
    rf._existing_upload(session, upload_id)
    return _read_region(crop, page, mode, reader)


@router.post("/files/{attachment_id}/page-caption", response_model=OcrPageReadOut)
def attachment_page_caption(
    attachment_id: int,
    page: int = 0,
    session: Session = Depends(get_session),
) -> OcrPageReadOut:
    """Describe the figures on one page of an attached PDF.

    The document half of captioning (UI_MODERNISATION_PLAN Phase 7.3). A file
    already has one whole-file caption; a slide deck needs one per page, since
    "a document with charts in it" describes every page in it equally badly.
    """
    attachment = rf._existing_attachment(session, attachment_id)
    if Path(attachment.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=415, detail="Only PDF pages are described one at a time.")
    path = rf._within(deps.get_config().uploads_dir, attachment.stored_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That file is no longer on disk.")
    return rf._describe_page(path, page, rf._page_read_key(attachment_id, None))


@router.post("/media/{upload_id}/page-caption", response_model=OcrPageReadOut)
def media_page_caption(
    upload_id: int,
    page: int = 0,
    session: Session = Depends(get_session),
) -> OcrPageReadOut:
    """`attachment_page_caption`'s sibling for a `/media/` upload: two id
    spaces, two routes, one implementation underneath."""
    upload = rf._existing_upload(session, upload_id)
    if Path(upload.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=415, detail="Only PDF pages are described one at a time.")
    path = rf._within(deps.get_config().data_dir / "media", upload.filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That file is no longer on disk.")
    return rf._describe_page(path, page, rf._page_read_key(None, upload_id))


class FileReadingOut(BaseModel):
    """One stored reading of a file: the `readings` view's row (F10)."""

    kind: str
    page: int = 0
    text: str
    model: str = ""
    ts: str | None = None


@router.get("/files/readings", response_model=list[FileReadingOut])
def file_readings(
    source: str,
    id: int,  # noqa: A002  # the query name the plan and the tests use
    session: Session = Depends(get_session),
) -> list[FileReadingOut]:
    """Every reading of one file in one shape: caption, Tesseract, vision, pages.

    `source` is "attachment" or "upload". A locked private note's file answers
    409 like the rest of its routes.
    """
    if source == "attachment":
        rf._existing_attachment(session, id)
    elif source == "upload":
        rf._existing_upload(session, id)
    else:
        raise HTTPException(status_code=422, detail="The source must be attachment or upload.")
    rows = session.execute(
        text("SELECT kind, page, text, model, ts FROM readings WHERE source = :s AND source_id = :i ORDER BY page, kind"),
        {"s": source, "i": id},
    ).all()
    return [FileReadingOut(kind=r[0], page=r[1] or 0, text=r[2], model=r[3] or "", ts=str(r[4]) if r[4] else None) for r in rows]


@router.get("/files/{attachment_id}/page-reads", response_model=OcrRangeReadOut)
def attachment_page_reads(
    attachment_id: int,
    session: Session = Depends(get_session),
) -> OcrRangeReadOut:
    """Every page of this attachment that has already been read.

    Asked by the OCR workspace as it opens a document, so a reading that
    finished while the workspace was closed is still there when you come back
    - which is the whole point of `PageRead`. See that model's docstring for
    the report.
    """
    rf._existing_attachment(session, attachment_id)
    return _stored_range(rf._page_read_key(attachment_id, None))


@router.get("/media/{upload_id}/page-reads", response_model=OcrRangeReadOut)
def media_page_reads(
    upload_id: int,
    session: Session = Depends(get_session),
) -> OcrRangeReadOut:
    """Every page of this upload that has already been read."""
    rf._existing_upload(session, upload_id)
    return _stored_range(rf._page_read_key(None, upload_id))


def _forget_page_read(key: tuple[str, int] | None, page: int) -> int | None:
    """Remove one page's stored reading, if there is one.

    **The half of "delete or redo" that redo already had.** Reported directly:
    *"there's also no way to delete or redo ocr text extractions in the ocr
    workspace."* Redo was already there, `PageRead`'s own docstring notes that
    re-reading a page replaces its row rather than appending, it was just
    never labelled as such. Delete genuinely was not: the only way to get rid
    of a wrong reading was to cover it with a better one, which still needs a
    working reader, and there was no way at all to simply take a note off the
    list of "already read" pages.

    Idempotent and quiet either way, matching `_remember_page_read`'s own
    stance that this table is a cache of a reading, not the reading itself, 
    deleting a row that is not there is not an error, it is the state the
    caller wanted.
    """
    if not key:
        return None
    kind, source_id = key
    with deps.get_db().session() as session:
        #: To the bin, not away (WORLD_CLASS_PLAN 28.4 row 2): the row is
        #: copied into `BinnedReading` first, so Undo, and the Library's Bin
        #: after the toast has gone, can put it back.
        binned_id = reading_bin.bin_page(session, kind, source_id, page)
        if binned_id is not None:
            rf._reindex_file(session, kind, source_id)
            session.commit()
        return binned_id


@router.delete("/files/{attachment_id}/page-reads/{page}", response_model=OcrRangeReadOut)
def delete_attachment_page_read(
    attachment_id: int,
    page: int,
    session: Session = Depends(get_session),
) -> OcrRangeReadOut:
    """Forget one page's reading. Returns what is left, in the same envelope
    `GET .../page-reads` uses, so the workspace can repaint from the response
    rather than issuing a second request."""
    rf._existing_attachment(session, attachment_id)
    binned_id = _forget_page_read(rf._page_read_key(attachment_id, None), page)
    return _stored_range(rf._page_read_key(attachment_id, None)).model_copy(update={"binned_id": binned_id})


@router.delete("/media/{upload_id}/page-reads/{page}", response_model=OcrRangeReadOut)
def delete_media_page_read(
    upload_id: int,
    page: int,
    session: Session = Depends(get_session),
) -> OcrRangeReadOut:
    """Forget one page's reading."""
    rf._existing_upload(session, upload_id)
    binned_id = _forget_page_read(rf._page_read_key(None, upload_id), page)
    return _stored_range(rf._page_read_key(None, upload_id)).model_copy(update={"binned_id": binned_id})


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


def _clean_reading_fields(*fields: tuple[str, str | None]) -> dict[str, str | None]:
    """`vision_ocr.cut_reading_loops` run over each field that is set, as a
    dict of only the ones it actually changed, so a caller commits nothing
    when there was nothing to clean.

    Two fields, not one: a picture read twice (Tesseract once, the vision
    model once) can have the loop in either, and a menu item that only
    checked the one the workspace happens to be showing would leave the
    other one looping forever with no way back to it.
    """
    changed: dict[str, str | None] = {}
    for name, value in fields:
        if not value:
            continue
        cleaned = vision_ocr.cut_reading_loops(value).strip()
        if cleaned != value:
            changed[name] = cleaned or None
    return changed


@router.post("/files/{attachment_id}/ocr-clean-loops", response_model=AttachmentGalleryOut)
def clean_attachment_reading_loops(
    attachment_id: int, session: Session = Depends(get_session)
) -> AttachmentGalleryOut:
    """**"Clean up repeated lines"** in the OCR workspace/lightbox menu
    (INBOX 423f). Runs the same `cut_reading_loops` a fresh reading is
    always passed through (ai/vision_ocr.py) over whichever of this
    attachment's readings already have text, in place: the guard at the
    point a reading is produced does nothing for one that was already
    stored before it existed, or one a since-changed model still managed to
    loop, and nothing else ever re-reads a stored reading on its own.
    Idempotent: a reading with no loop, or one already cleaned, comes back
    unchanged.
    """
    attachment = rf._existing_attachment(session, attachment_id)
    changed = _clean_reading_fields(
        ("vision_ocr_text", attachment.vision_ocr_text),
        ("ocr_text", attachment.ocr_text),
    )
    if changed:
        for name, value in changed.items():
            setattr(attachment, name, value)
        session.commit()
    return rf._attachment_out(session, attachment)


@router.post("/media/{upload_id}/ocr-clean-loops", response_model=MediaUploadOut)
def clean_media_reading_loops(
    upload_id: int, session: Session = Depends(get_session)
) -> MediaUploadOut:
    """`clean_attachment_reading_loops`'s sibling for a media upload."""
    upload = rf._existing_upload(session, upload_id)
    changed = _clean_reading_fields(
        ("vision_ocr_text", upload.vision_ocr_text),
        ("ocr_text", upload.ocr_text),
    )
    if changed:
        for name, value in changed.items():
            setattr(upload, name, value)
        session.commit()
    return _media_out(upload)


class VisionOcrBody(BaseModel):
    #: Same "already there and not forced, leave it alone" rule as
    #: `CaptionBody.force`, a manual re-read the user pressed the button
    #: for, not a background pass overwriting a reading they already saw.
    force: bool = False
    #: True only from the workspace's editor: the text is a correction the
    #: person made to the sections on screen, so those sections must stay what
    #: is shown (`rf._set_edited_reading`). Any other text-setting call (a
    #: fixture, a clear, an import) just replaces the stored text and lets the
    #: sections be derived again.
    edited: bool = False
    #: A correction typed by hand, exactly as `OcrBody.text` already allows for
    #: the Tesseract reading: `None` means "read it", any string sets it, and
    #: `""` clears it.
    #:
    #: Reported: a vision model asked to transcribe a picture with no text in
    #: it returned four Pokémon names, and there was no way to remove or edit
    #: them. That failure is inherent to asking a small VLM to read an image
    #: with nothing to read, the prompt already asks it to say so and it
    #: ignored the instruction: so the fix is not a better prompt, it is that
    #: a wrong reading must be correctable like every other AI output in this
    #: app. The Tesseract line has been editable since it shipped; this one
    #: was the odd one out.
    text: str | None = Field(default=None, max_length=10_000)
    #: With `text`: who read it, put back by Undo of a fresh read (L517).
    model: str | None = Field(default=None, max_length=200)


def _store_typed_reading(session: Session, upload, body: VisionOcrBody) -> None:  # noqa: ANN001
    """A hand-typed correction, or "" to clear a wrong reading."""
    # Checked before the backend is: fixing a bad transcription must not require
    # the model that produced it to still be running.
    upload.vision_ocr_text = body.text.strip() or None
    if not upload.vision_ocr_text:
        # Clearing the text clears the attribution with it, "Read by X"
        # under nothing is a claim about a reading that no longer exists.
        upload.vision_ocr_model = None
    elif body.model is not None:
        upload.vision_ocr_model = body.model or None
    session.commit()
    if body.edited:
        rf._set_edited_reading(rf._page_read_key(None, upload.id), upload.vision_ocr_text, "vision")
    else:
        #: A stored edit describes the text it was made on; any other
        #: replacement (a clear, a fixture) makes it stale.
        rf._forget_regions(rf._page_read_key(None, upload.id), only_source="edited-")


def _require_vision_model() -> None:
    if not deps.get_ollama().is_running():
        raise HTTPException(status_code=409, detail="The AI model isn't running.")
    model = deps.get_model_manager().resolve_ocr_model(deps.get_ollama())
    if not model:
        raise HTTPException(
            status_code=409,
            detail="No installed model can read images. Install or "
            "pick one in Settings, Models.",
        )


def _media_out(upload) -> MediaUploadOut:  # noqa: ANN001
    return MediaUploadOut(
        id=upload.id,
        url=f"/media/{upload.filename}",
        original_name=upload.original_name,
        ocr_text=upload.ocr_text or "",
        caption=upload.caption or "",
        caption_model=upload.caption_model or "",
        caption_edited=upload.caption_edited,
        vision_ocr_text=upload.vision_ocr_text or "",
        vision_ocr_model=upload.vision_ocr_model or "",
    )


@router.post("/media/{upload_id}/vision-ocr", response_model=MediaUploadOut)
def vision_ocr_media(
    upload_id: int, body: VisionOcrBody = VisionOcrBody(), session: Session = Depends(get_session)
) -> MediaUploadOut:
    """Read the text in one image with a vision model, the "extractor
    mode" asked for directly, distinct from the local Tesseract pass
    (`ocr_text`, automatic on upload) and from the AI caption (`caption`, a
    description rather than a transcription). Manual only: never triggered
    by `POST /media/upload` itself, unlike captioning.

    Same synchronous, single-round-trip shape as `caption_media` above: 
    one model call, no different from the AI-edit or link-reason calls this
    app already blocks on behind a spinner.
    """
    upload = rf._existing_upload(session, upload_id)
    if Path(upload.filename).suffix.lower() not in vision_ocr.VISION_OCR_SUFFIXES:
        raise HTTPException(status_code=415, detail="Only images can be read this way.")
    if body.text is not None:
        _store_typed_reading(session, upload, body)
        return _media_out(upload)
    _require_vision_model()
    media_dir = deps.get_config().data_dir / "media"
    vision_ocr.vision_ocr_and_store(upload.id, media_dir / upload.filename, force=body.force)
    session.refresh(upload)
    #: A fresh reading replaces a hand edit of the sections, same as Tesseract's.
    rf._forget_regions(rf._page_read_key(None, upload.id), only_source="edited-")
    return _media_out(upload)
