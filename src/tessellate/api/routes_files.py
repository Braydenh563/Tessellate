"""File attachments on entries.

Bytes live in the uploads folder under a random name (no path traversal
possible); the original filename is kept only for downloads.
"""

from __future__ import annotations

import base64
import binascii
import logging
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.ai import captioning, docreader, vision_ocr
from tessellate.api import bounds, paging
from tessellate.api.edit_conflicts import content_hash, refuse_if_stale
from tessellate.api.routes_entries import _existing_entry, _to_out
from tessellate.api.schemas import EntryOut
from tessellate.api.this_computer import this_computer_only
from tessellate.core import (
    deps,
    diskspace,
    docview,
    jobs,
    media_gc,
    media_process,
    ocr,
    paths,
    pdfpages,
    reading_bin,
    undo_bin,
)
from tessellate.core.database import Attachment, Entry, MediaUpload
from tessellate.core.deps import get_session
from tessellate.core.subproc import NO_WINDOW
from tessellate.entry import manager
from tessellate.entry import manager_text
from tessellate.entry import manager_purge
from tessellate.repo import uploads as uploads_repo
from tessellate.repo.content import FILES

logger = logging.getLogger(__name__)

router = APIRouter(tags=["files"])

# `/media/{filename}` and `/files/{attachment_id}` are the two routes an
# `<img src>` points at directly rather than something the frontend fetches
# with its own X-Auth-Token header, see `require_unlock_media`'s own
# docstring in routes_auth.py for why they need a separate router (a
# router-level dependency and a route-level one are additive, not an
# override, so the header-only gate on `router` can't be loosened per-route).
media_router = APIRouter(tags=["files"])

MAX_FILE_BYTES = 50 * 1024 * 1024  # a personal notebook, not a fileserver

#: Note attachments, unlike /media/upload above, had no allowlist at all, 
#: any file, of any type, attached without a single refusal (asked for
#: directly: "make sure incompatible files are currently refused upon
#: attempted upload with an error message"). This one is broader than
#: MEDIA_SUFFIXES on purpose: attachments are downloaded (FileResponse's
#: default Content-Disposition: attachment, not rendered inline the way
#: /media/{name} is), so the stored-XSS concern that shaped that allowlist
#: doesn't apply here in the same way, but video and audio are still out
#: (no player exists for video; a recording is an object of its own,
#: `routes_recordings.py`, never an attachment: WORLD_CLASS_PLAN "Audio in
#: the notebook", decision 2) and so are the obvious
#: executable/script shapes, since nothing in this app ever needs to run
#: an attachment.
ATTACHMENT_SUFFIXES = frozenset(
    {
        # Images
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".bmp", ".ico", ".svg", ".tiff", ".tif",
        # Documents
        ".pdf", ".docx", ".doc", ".odt", ".rtf",
        ".pptx", ".ppt", ".odp",
        ".xlsx", ".xls", ".ods", ".csv",
        # Text & markup
        ".txt", ".md", ".markdown", ".json", ".xml", ".yaml", ".yml", ".html", ".htm", ".css",
        # Code
        ".js", ".ts", ".jsx", ".tsx", ".py", ".java", ".c", ".h", ".cpp", ".hpp", ".cs", ".go",
        ".rs", ".rb", ".php", ".sh", ".sql", ".swift", ".kt",
        # Archives
        ".zip",
    }
    #: Everything the chat's file picker offers (`docview.VIEWABLE_SUFFIXES`),
    #: so the Quick capture card, which takes the same files and attaches them
    #: here on Save, never meets a 415 for a type its picker let through. All
    #: are downloaded, not rendered inline, the reason this list is the wider one.
    | frozenset(docview.VIEWABLE_SUFFIXES)
)


@router.post("/entries/{entry_id}/files", response_model=EntryOut, status_code=201)
def upload_file(
    entry_id: int, file: UploadFile, session: Session = Depends(get_session)
) -> EntryOut:
    entry = _existing_entry(session, entry_id)
    suffix = Path(file.filename or "file").suffix[:12].lower()
    if suffix not in ATTACHMENT_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"'{suffix or 'that file type'}' can't be attached. "
                "Images, PDFs, office documents, text and code files are supported, "
                "video and audio attachments aren't yet."
            ),
        )
    uploads_dir: Path = deps.get_config().uploads_dir
    # The folder is created at startup, but it only has to go missing once, 
    # a cleanup tool, a synced or unmounted data directory, a restore that
    # didn't include an empty folder, and every upload fails with a 500 and a
    # traceback instead of saving. Sketches are the usual casualty, since the
    # note saves first and only the drawing is lost.
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Random stored name, original extension kept for double-click opening.
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    destination = uploads_dir / stored_name

    #: `partial_write`, because the 413 above was the only failure this
    #: write cleaned up after. Measured on a data dir filled to 100% (INBOX
    #: 266, item 6): the upload answered 507, correctly, and left a
    #: zero-byte file in `uploads/` that no database row pointed at and
    #: nothing would ever remove. On a disk with 30 MB left and a 40 MB file
    #: that is 30 MB of orphan, and the person is further from being able to
    #: save anything than before they started.
    size = 0
    with diskspace.partial_write(destination):
        with destination.open("wb") as out:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_FILE_BYTES:
                    out.close()
                    destination.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="That file is larger than 50 MB.")
                out.write(chunk)

    attachment = manager_purge.add_attachment(
        session,
        entry,
        filename=bounds.display_name(file.filename, stored_name),
        stored_name=stored_name,
        mime=file.content_type or "application/octet-stream",
        size=size,
    )
    #: **A document says what it is without being asked.** An image gets
    #: Tesseract and a caption on background threads the moment it lands; an
    #: attachment got neither, so every row in the Files sub-tab was a
    #: filename until somebody opened each one by hand, which is the "no bg
    #: process, nothing" half of the owner's report. `read_in_background`
    #: extracts the text locally and, where a model is running, writes a
    #: description of it. Fire and forget, so this response is not held.
    #:
    #: `getattr` because `add_attachment` has not always returned the row, and
    #: a missing return here must not turn an upload that worked into a 500.
    new_id = getattr(attachment, "id", None)
    if new_id is not None:
        docreader.read_in_background(new_id)
    return _to_out(session, entry)


def _refuse_while_sealed(session: Session, attachment: Attachment) -> Attachment:
    """SEC-A2: a file is part of its note, so a locked private note's files
    answer 409 like its export and history do (`manager.note_is_sealed`)."""
    owner = session.get(Entry, attachment.entry_id)
    if owner is not None and manager.note_is_sealed(owner.is_private):
        raise HTTPException(status_code=409, detail="Unlock first.")
    return attachment


def _existing_attachment(session: Session, attachment_id: int) -> Attachment:
    return _refuse_while_sealed(
        session, deps.get_or_404(session, Attachment, attachment_id, "That attachment could not be found.")
    )


def _existing_upload(session: Session, upload_id: int) -> MediaUpload:
    """SEC-A2: the `/media/{id}/...` routes read a picture's text, so a picture
    only a locked private note uses answers 409 like that note's files do."""
    upload = deps.get_or_404(session, MediaUpload, upload_id, "That upload could not be found.")
    if media_gc.sealed_only(session, upload.filename):
        raise HTTPException(status_code=409, detail="Unlock first.")
    return upload


@media_router.get("/files/{attachment_id}")
def download_file(attachment_id: int, session: Session = Depends(get_session)) -> FileResponse:
    attachment = _existing_attachment(session, attachment_id)
    path = _within(deps.get_config().uploads_dir, attachment.stored_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That file is no longer on disk.")
    #: **Never the type the uploader declared, unless it is a picture or a
    #: PDF** (SEC-11, security audit 2026-10-05). `script-src 'self'` covers
    #: every URL on this origin, and `Content-Disposition: attachment` stops a
    #: navigation but not a `<script src="/files/1">`, which a `.js` upload
    #: served as text/javascript would have run. The sandbox CSP and CORP
    #: make the response inert anywhere it is not simply downloaded; a PDF
    #: keeps the app's own policy, since Chrome's viewer will not open in a
    #: sandboxed response and a PDF runs no script in the page anyway.
    mime = (attachment.mime or "").split(";", 1)[0].strip().lower()
    if not (mime.startswith("image/") or mime == "application/pdf"):
        mime = "application/octet-stream"
    headers = {"Cross-Origin-Resource-Policy": "same-origin"}
    if mime != "application/pdf":
        headers["Content-Security-Policy"] = "sandbox; default-src 'none'; img-src 'self'; style-src 'unsafe-inline'"
    return FileResponse(path, filename=attachment.filename, media_type=mime, headers=headers)


class AttachmentGalleryOut(BaseModel):
    """One note's own file, shaped for the Library's Images/Files gallery: 
    not `MediaUploadOut`: an `Attachment` has never been OCR'd, captioned, or
    read by a vision model (those are `MediaUpload`-only features, see that
    model's own docstring), so reusing that shape would mean either faking
    fields that don't apply or leaving the gallery to guess why they're
    always empty. This is deliberately the smaller, honest set of what an
    attachment actually has.

    Reported directly, and root-caused rather than patched around: "a pdf I
    uplaoded to a note doesnt show in the libary" / "my uploaded pdf file
    isnt shown in the library files subtab". `renderLibraryImagesGallery()`
    (library.js) has only ever called `GET /media`, which is `MediaUpload`
    rows: a file attached to a note through the composer or note editor
    (`POST /entries/{id}/files`, this file, above) is an `Attachment` row
    instead, a completely different table, and so never appeared no matter
    how the gallery itself was styled or filtered.
    """

    id: int
    #: `/files/{id}`, gated the same way as `/media/{name}` (the media
    #: cookie, see `require_unlock_media` in routes_auth.py).
    #: Deliberately has no file extension (an attachment is served by id,
    #: not by stored name), which is why the gallery classifies Images vs.
    #: Files from `mime` here rather than sniffing the url the way it does
    #: for a `MediaUpload` row's `/media/{name}.ext`.
    url: str
    original_name: str
    mime: str
    created_at: str
    #: The one note this file hangs on, an attachment's "used in", where a
    #: `MediaUpload` row can be referenced from several places at once.
    #: Shaped as a single-item `used_by` list rather than a new field so the
    #: gallery tile's existing "used in" rendering (ROADMAP item 43) needs
    #: no branch for which kind of row it is looking at.
    used_by: list[dict] = []
    #: The file's size on disk, in bytes; 0 when it cannot be stat'ed (the
    #: row outliving its file is a real state, see the "Image deleted"
    #: placeholder the gallery already renders). The comment above says a
    #: byte count was left out because it "would cost one `stat` per row on
    #: every gallery load for a number nobody asked for", it has since been
    #: asked for directly ("file details such as the type, size, topic/
    #: category"), which settles the trade the other way. It is one `stat`
    #: per row against a local disk, on the same pass that already walks
    #: every row.
    size_bytes: int = 0
    #: What this file says, see `Attachment`'s own docstring for why these
    #: now exist on an attachment at all. Never null over the wire, the same
    #: convention `MediaUploadOut` keeps, so the gallery can filter on them
    #: with a plain substring test.
    caption: str = ""
    caption_model: str = ""
    caption_edited: bool = False
    ocr_text: str = ""
    vision_ocr_text: str = ""
    vision_ocr_model: str = ""
    #: True when this file has renderable pages (a PDF), so the tile can show
    #: the first one instead of a generic file glyph, asked for directly:
    #: "in the files tab, there is no preview".
    has_pages: bool = False
    #: How many of this document's pages have a stored reading (`PageRead`).
    #: UI_MODERNISATION_PLAN Phase 7.5: the Files row states "N pages read · N
    #: words" instead of clamping a paragraph nobody can read at that size, and
    #: counting pages by splitting the joined text would miscount any reading
    #: that happens to contain a blank line. 0 for anything never read, which
    #: is also the honest answer for an image.
    pages_read: int = 0


#: The gallery's page (WORLD_CLASS_PLAN F2): the response no longer grows with
#: the notebook. The default was the maximum until 2026-09-24, because five
#: callers read this endpoint whole through `apiJson`, one of them the
#: Library's own Files sub-tab, and a 200-row default under them would have
#: cut the Library off at two hundred attachments. They read to the end
#: through `apiPagedList` now, by `X-Total-Count`, and
#: `tests/test_gallery_paging.py` fails on a caller that reads one page.
GALLERY_PAGE_SIZE = 200
GALLERY_PAGE_SIZE_MAX = 1000


@router.get("/files/gallery", response_model=list[AttachmentGalleryOut])
def list_attachment_gallery(
    response: Response,
    limit: int = Query(default=GALLERY_PAGE_SIZE, ge=1, le=GALLERY_PAGE_SIZE_MAX),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = paging.cursor_param(),
    session: Session = Depends(get_session),
) -> list[AttachmentGalleryOut]:
    """A page of the note-attached files the Library's gallery may show, the
    `Attachment` half of what `GET /media` (this file, `list_media`) already
    covers for `MediaUpload` rows. See `AttachmentGalleryOut` for why this is
    a separate, smaller shape rather than folded into that endpoint.

    Same privacy rule as the Library's own overview list (`_images()` in
    routes_library.py): a private note's attachment is as private as the
    note, so it is excluded here rather than shown in a browsing surface the
    note itself is hidden from. Workspace scoping comes for free from
    `Attachment`'s own `WorkspaceMixin`, the ambient session filter already
    applies before this query ever runs, the same as every other
    workspace-scoped read in this app.
    """
    offset = paging.start(cursor, offset)
    visible = (
        select(Attachment, Entry)
        .join(Entry, Attachment.entry_id == Entry.id)
        .where(
            Entry.is_deleted == False,  # noqa: E712
            Entry.is_private == False,  # noqa: E712
        )
    )
    # Paged for the reason `GET /media` beside it is (WORLD_CLASS_PLAN F2):
    # this used to be the whole table, and the table is one row per attached
    # file for the life of the notebook. `X-Total-Count` is the real size
    # whatever the page, and the id breaks a tie on `created_at` so two files
    # attached in the same second cannot swap places between pages and hide a
    # row.
    total = session.scalar(select(func.count()).select_from(visible.subquery())) or 0
    response.headers["X-Total-Count"] = str(total)
    paging.finish(response, offset, limit, total)
    rows = session.execute(
        visible.order_by(Attachment.created_at.desc(), Attachment.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    ids = [attachment.id for attachment, _ in rows]
    page_text = _page_read_text_map("attachment", ids)
    pages_read = _page_read_count_map("attachment", ids)
    return [
        AttachmentGalleryOut(
            id=attachment.id,
            pages_read=pages_read.get(attachment.id, 0),
            url=f"/files/{attachment.id}",
            original_name=attachment.filename,
            mime=attachment.mime or "application/octet-stream",
            created_at=attachment.created_at.isoformat(),
            used_by=[{"kind": "note", "id": entry.id, "label": manager_text.plain_label(entry.content)}],
            caption=attachment.caption or "",
            caption_model=attachment.caption_model or "",
            caption_edited=bool(attachment.caption_edited),
            ocr_text=attachment.ocr_text or "",
            #: Falls back to the page-by-page reading -- see
            #: `_page_read_text_map` for why the two were not joined before.
            vision_ocr_text=attachment.vision_ocr_text or page_text.get(attachment.id, ""),
            vision_ocr_model=attachment.vision_ocr_model or "",
            has_pages=Path(attachment.filename).suffix.lower() == ".pdf" and pdfpages.available(),
            size_bytes=_attachment_size(session, attachment),
        )
        for attachment, entry in rows
    ]


class AttachmentAnalyseBody(BaseModel):
    """What to read out of a file, or what to store instead of reading it."""

    #: "caption", a vision model describes it. "ocr", Tesseract (an image)
    #: or this app's own document extractor (anything else). "vision", a
    #: vision model transcribes the pages, which is the one that answers a
    #: scanned PDF or a diagram nothing else can read.
    kind: str = Field(pattern="^(caption|ocr|vision)$")
    #: Set the value by hand instead of running anything, "the text and
    #: analysis needs to be… modifyable by the user". `""` clears it back to
    #: "nothing here", the same as the `/media` endpoints this mirrors.
    text: str | None = Field(default=None, max_length=200_000)
    #: True only from the workspace's editor: the text is a correction the
    #: person made to the sections on screen, so those sections must stay what
    #: is shown (`_set_edited_reading`). Any other text-setting call (a
    #: fixture, a clear, an import) just replaces the stored text and lets the
    #: sections be derived again.
    edited: bool = False
    #: With `text` on a vision reading: who read it, put back by Undo of a
    #: fresh read (L517), so "Read by" names the reader of the text restored.
    model: str | None = Field(default=None, max_length=200)
    #: The local engine for `kind="ocr"` on a picture (INBOX 717): "" for the
    #: automatic pick, or "tesseract" / "rapidocr" by name.
    engine: str = Field(default="", max_length=20)
    #: Re-run even when there is already a value (a caption is written once
    #: and left alone otherwise, so nothing an AI wrote and a person read can
    #: silently change under them).
    force: bool = False


def _attachment_size(session: Session, attachment: Attachment) -> int:
    """Bytes on disk, or 0 when the file is gone.

    Same contract as `MediaUploadOut.size_bytes`: a row can outlive its file,
    and the gallery draws a placeholder for that rather than dropping the row,
    so this must report a number instead of raising.

    `Attachment.size` is written at upload time (`manager_purge.add_attachment`)
    and kept current by every route that replaces the bytes on disk, so the
    column is normally already the right answer, read it first and skip the
    filesystem call `GET /files/gallery` used to pay once per attachment on
    every open (`list_media`'s sibling gallery has the same bug, open as
    PLAN.md P6; nothing here changes that one). `stat()` only runs for a row
    whose `size` is still NULL/0 (a pre-existing attachment from before this
    column existed) and whose file is actually there, and the result is
    written back so the next call, in this request's own list, and every
    request after: reads the column instead of the disk again.
    """
    if attachment.size:
        return attachment.size
    try:
        size = _within(deps.get_config().uploads_dir, attachment.stored_name).stat().st_size
    except (OSError, HTTPException):
        return 0
    if size:
        attachment.size = size
        session.commit()
    return size


def _attachment_out(session: Session, attachment: Attachment) -> AttachmentGalleryOut:
    entry = session.get(Entry, attachment.entry_id)
    return AttachmentGalleryOut(
        id=attachment.id,
        url=f"/files/{attachment.id}",
        original_name=attachment.filename,
        mime=attachment.mime or "application/octet-stream",
        created_at=attachment.created_at.isoformat(),
        used_by=(
            [{"kind": "note", "id": entry.id, "label": manager_text.plain_label(entry.content)}]
            if entry is not None
            else []
        ),
        caption=attachment.caption or "",
        caption_model=attachment.caption_model or "",
        caption_edited=bool(attachment.caption_edited),
        ocr_text=attachment.ocr_text or "",
        vision_ocr_text=attachment.vision_ocr_text or "",
        vision_ocr_model=attachment.vision_ocr_model or "",
        has_pages=Path(attachment.filename).suffix.lower() == ".pdf" and pdfpages.available(),
        size_bytes=_attachment_size(session, attachment),
    )


def _store_typed_reading(session: Session, attachment: Attachment, body: AttachmentAnalyseBody) -> AttachmentGalleryOut:
    """The reader typed a caption, an OCR reading or a vision reading by hand."""
    stripped = (body.text or "").strip() or None
    if body.kind == "caption":
        attachment.caption = stripped
        if stripped:
            attachment.caption_edited = True
        else:
            attachment.caption_model = None
            attachment.caption_edited = False
    elif body.kind == "ocr":
        attachment.ocr_text = stripped
    else:
        attachment.vision_ocr_text = stripped
        if not stripped:
            attachment.vision_ocr_model = None
        elif body.model is not None:
            attachment.vision_ocr_model = body.model or None
    session.commit()
    if body.edited and body.kind in {"ocr", "vision"}:
        _set_edited_reading(
            _page_read_key(attachment.id, None),
            stripped,
            "tesseract" if body.kind == "ocr" else "vision",
        )
    else:
        _forget_regions(_page_read_key(attachment.id, None))
    return _attachment_out(session, attachment)


def _read_locally(
    session: Session, attachment: Attachment, path: Path, body: AttachmentAnalyseBody, is_image: bool
) -> AttachmentGalleryOut:
    """The `ocr` kind: Tesseract for a picture; this app's own document
    extractor for everything else: a .docx or a text-layer PDF has real text
    in it that no OCR pass should be guessing at.

    Announced as a reading (`jobs.reading`) even though no model is involved: Tesseract on
    a long scan is one of the slowest things this app does, and "is it
    working or is it stuck" is the same question whether the work is a model
    or a binary.
    """
    choice = _checked_engine(body.engine) if is_image else ""
    if is_image and (reason := ocr.unavailable_reason(choice)):
        raise HTTPException(status_code=409, detail=reason)
    with jobs.reading("ocr", attachment.id, attachment.filename):
        if is_image:
            text = _local_text(path, choice)
        else:
            # No `vision_reader` passed on purpose: this is the "read it
            # locally, no model" path, and the vision kind is the one that
            # costs a model round trip. A scan with no text layer comes back
            # empty here, which is the honest answer and is exactly what
            # sends the reader to "Read with AI".
            text = docview.extract(path).text
    attachment.ocr_text = (text or "").strip() or None
    session.commit()
    _forget_regions(_page_read_key(attachment.id, None))
    return _attachment_out(session, attachment)


def _describe_from_text(
    session: Session, attachment: Attachment, path: Path, body: AttachmentAnalyseBody, suffix: str
) -> AttachmentGalleryOut | None:
    """**Describing a document needs no vision model, only its own text.**

    Reported on 2026-09-09: "the describe with ai button in the files tab
    doesnt work. it should be a button for generating a
    description/summary of the file from the readable and/or extractable
    content of the file." It refused with a 415 for everything that was not a
    picture or a PDF, and even a PDF went to a vision model, which most
    machines do not have installed.

    This runs above the vision-model checks deliberately: a .md, a .docx, a
    .csv or a text-layer PDF is described by the utility model that already
    writes tag suggestions, on a machine with no vision model at all.
    `ocr_text` first when it is there, since that is this file's reading as
    the reader has it (corrections included) rather than a second extraction
    that may disagree with what they can see.

    **`vision_ocr_text` was missing from this chain entirely.** Reported
    directly: a scan already read page by page with the AI document reader
    (fourteen pages stored here) still had "Describe with AI" call a vision
    model itself, on one raw page image, because this fallback only ever
    checked the Tesseract field and a fresh local extraction, never the field
    this exact reading is written to. Checked second, after `ocr_text`:
    Tesseract's own reading, when both exist, is the one already corrected by
    hand and shown as the file's own text; the AI reader's is the one likelier
    to exist at all for a scan, since it needs no separate OCR binary.
    `docview.extract` stays last of the three, since it is a *native* text
    layer and only a text-layer PDF or a `.docx`/`.csv`/etc. has one at all.

    A file whose text extraction comes back empty is a scan with nothing
    already read either, and returns None here so the caller falls through to
    the vision path, which rasterises its first page. A file whose text is
    there but whose model had nothing to say stores nothing and says so:
    those are different answers and must not share a branch.
    """
    if attachment.caption and not body.force:
        return _attachment_out(session, attachment)
    readable = (
        (attachment.ocr_text or "").strip()
        or (attachment.vision_ocr_text or "").strip()
        or (docview.extract(path).text or "").strip()
    )
    if readable:
        if not deps.get_ollama().is_running():
            raise HTTPException(status_code=409, detail="The AI model isn't running.")
        models = deps.get_model_manager()
        with jobs.reading("describe", attachment.id, attachment.filename, models.utility_model()):
            described = captioning.describe_document(readable, models, deps.get_ollama())
        attachment.caption = described or None
        attachment.caption_model = models.utility_model() if described else None
        attachment.caption_edited = False
        session.commit()
        return _attachment_out(session, attachment)
    if suffix != ".pdf":
        raise HTTPException(
            status_code=415,
            detail="There is no readable text in this file to describe.",
        )
    return None


def _vision_model() -> str:
    """The installed vision model, or the 409 that says there is none."""
    if not deps.get_ollama().is_running():
        raise HTTPException(status_code=409, detail="The AI model isn't running.")
    model = deps.get_model_manager().resolve_vision_model(deps.get_ollama())
    if not model:
        raise HTTPException(
            status_code=409,
            detail="No installed model can read images. Install or "
            "pick one in Settings, Models.",
        )
    return model


def _caption_with_vision(attachment: Attachment, path: Path, is_image: bool, model: str) -> None:
    ollama = deps.get_ollama()
    # `pdf_vision_reader` returns the reader callable itself (docview's
    # `vision_reader` contract), not an object with a `.read`: calling
    # `.read(path)` on it was the reported 500 on "generate a caption" for
    # a PDF ("'function' object has no attribute 'read'").
    with jobs.reading("describe", attachment.id, attachment.filename, model):
        text = (
            captioning.caption_text(path, model, ollama)
            if is_image
            else vision_ocr.pdf_vision_reader(model, ollama)(path)
        )
    attachment.caption = (text or "").strip() or None
    attachment.caption_model = model if attachment.caption else None
    attachment.caption_edited = False


def _read_with_vision(attachment: Attachment, path: Path, is_image: bool, model: str) -> None:
    ollama = deps.get_ollama()
    # A PDF is rasterised page by page (`pdf_vision_reader`), which is
    # the whole point for a scan, where there is no text layer to read
    # and Tesseract has already found nothing.
    with jobs.reading("vision", attachment.id, attachment.filename, model):
        text = (
            vision_ocr.vision_ocr_text(path, model, ollama)
            if is_image
            else vision_ocr.pdf_vision_reader(model, ollama)(path)
        )
    attachment.vision_ocr_text = (text or "").strip() or None
    attachment.vision_ocr_model = model if attachment.vision_ocr_text else None
    _forget_regions(_page_read_key(attachment.id, None), only_source="edited-")


@router.post("/files/{attachment_id}/analyse", response_model=AttachmentGalleryOut)
def analyse_attachment(
    attachment_id: int,
    body: AttachmentAnalyseBody,
    session: Session = Depends(get_session),
) -> AttachmentGalleryOut:
    """Read a note's attached file with the local models, or store a reading
    typed by hand.

    One endpoint for all three readings rather than three near-identical
    ones (the `/media` side grew that way and is three copies of the same
    twenty lines). The split that matters is not caption/ocr/vision, it is
    *image or document*: an image goes to Tesseract, a document goes through
    `docview` (the same extractor the file viewer already uses), and the
    vision path rasterises PDF pages so a scan with no text layer at all
    still has something a model can look at.
    """
    attachment = _refuse_while_sealed(session, FILES.writable(session, attachment_id))
    path = _within(deps.get_config().uploads_dir, attachment.stored_name)
    suffix = Path(attachment.filename).suffix.lower()
    is_image = suffix in captioning.CAPTION_SUFFIXES

    if body.text is not None:
        return _store_typed_reading(session, attachment, body)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That file is no longer on disk.")
    if body.kind == "ocr":
        return _read_locally(session, attachment, path, body, is_image)
    if body.kind == "caption" and not is_image:
        done = _describe_from_text(session, attachment, path, body, suffix)
        if done is not None:
            return done

    # Both remaining kinds need a vision model.
    model = _vision_model()
    if body.kind == "caption":
        if attachment.caption and not body.force:
            return _attachment_out(session, attachment)
        _caption_with_vision(attachment, path, is_image, model)
    else:
        if attachment.vision_ocr_text and not body.force:
            return _attachment_out(session, attachment)
        _read_with_vision(attachment, path, is_image, model)
    session.commit()
    return _attachment_out(session, attachment)


class AttachedFileTextOut(BaseModel):
    """One attached file, read as text for the in-app viewer."""

    filename: str
    #: "markdown" | "code" | "plain", how to render `text`, not what the file
    #: is. A converted .docx comes back as markdown, so it renders like one.
    kind: str
    #: "file" | "converted" | "vision-ocr". Shown to the reader, not merely
    #: logged: a vision model's transcription of a scan is a *reading* of the
    #: file, and presenting it identically to text read out of a .txt would be
    #: the app stating a guess as a fact.
    source: str
    text: str = ""
    truncated: bool = False
    #: Why there is no text, when there is none. Never an error status: "this
    #: file has no viewer yet" and "install markitdown" are both answers, and
    #: a 4xx would make the viewer show a failure for a file that is fine.
    message: str = ""
    #: The optional package that would read it (`ViewedFile.extra`), so the
    #: viewer can offer Install beside the message.
    extra: str = ""
    #: Whether this file may be saved back over (`docview.editability`). True
    #: only where the text *is* the file, .md, .txt, .csv, code, so a .docx
    #: never is, and neither is a file too long to have been shown in full.
    editable: bool = False
    #: Why not, when `editable` is False. Written to be shown next to a
    #: disabled Edit button: §R7.1 item 2 asks for the honest reason in the UI
    #: rather than a control that does nothing.
    edit_message: str = ""
    #: The hash of `text` (`edit_conflicts.content_hash`): a save sends it back
    #: as `base_hash` so a file changed meanwhile is not overwritten unseen.
    content_hash: str = ""


@router.get("/files/{attachment_id}/text", response_model=AttachedFileTextOut)
def attached_file_text(
    attachment_id: int, session: Session = Depends(get_session)
) -> AttachedFileTextOut:
    """An attached file's text, for reading it without leaving the app.

    Deliberately returns *text*, never the file. `download_file` above hands
    the browser the bytes with `Content-Disposition: attachment`, and
    `media_file` at the bottom of this module explains at length why serving
    anything new inline is the thing to avoid. A viewer built by widening
    either of those would inherit that problem once per file type; this one
    cannot, because what it sends has already stopped being a .docx.

    Read-only, and that is a property of the extraction rather than a missing
    feature: see `core/docview.py`'s module docstring. Editing an attached
    file's text would mean writing text back into a format it was never in.
    """
    attachment = _existing_attachment(session, attachment_id)
    path = _within(deps.get_config().uploads_dir, attachment.stored_name)
    # The scanned-PDF fallback, passed rather than omitted. `docview` has
    # always taken a `vision_reader` and this, its only caller, passed
    # nothing, so the whole path was wired and never once ran: exactly the
    # "features that never executed" shape CLAUDE.md warns about. It only does
    # any work for a PDF with no text layer, and only when the pdfpages extra
    # and a vision model are both present; every other file returns before it
    # is consulted.
    viewed = docview.extract(path, vision_reader=vision_ocr.pdf_reader_or_none())
    editable, edit_message = docview.editability(path, viewed)
    return AttachedFileTextOut(
        filename=attachment.filename,
        kind=viewed.kind,
        source=viewed.source,
        text=viewed.text,
        truncated=viewed.truncated,
        message=viewed.message,
        extra=viewed.extra,
        editable=editable,
        edit_message=edit_message,
        content_hash=content_hash(viewed.text),
    )


class FileTextIn(BaseModel):
    """The edited text of a file, on its way back to disk."""

    text: str = Field(max_length=bounds.FILE_TEXT_MAX)
    #: The `content_hash` of the text this edit started from (two windows, one file).
    base_hash: str | None = Field(default=None, max_length=64)


@router.put("/files/{attachment_id}/text", response_model=AttachedFileTextOut)
def save_attached_file_text(
    attachment_id: int, payload: FileTextIn, session: Session = Depends(get_session)
) -> AttachedFileTextOut:
    """Save an edited text file back over itself.

    **This does not widen the read-only rule above; it draws the line where
    the rule's own reason stops applying.** That reason is that extraction is
    one-way: text pulled out of a .docx is not a .docx. For a .md, a .txt, a
    .csv or a source file, "extraction" is `bytes.decode()`: the text *is* the
    file, and writing it back is lossless. `docview.editability` owns which is
    which, so this route and the viewer cannot disagree about it.

    Re-checked here rather than trusting the `editable` flag the GET returned:
    a client is not the authority on what may be overwritten, and the file can
    have been replaced between the two calls.
    """
    attachment = _refuse_while_sealed(session, FILES.writable(session, attachment_id))
    path = _within(deps.get_config().uploads_dir, attachment.stored_name)
    viewed = docview.extract(path)
    editable, edit_message = docview.editability(path, viewed)
    if not editable:
        raise HTTPException(status_code=409, detail=edit_message)
    refuse_if_stale(
        base_hash=payload.base_hash,
        current_text=viewed.text,
        new_text=payload.text,
        current=lambda: {"content": viewed.text, "content_hash": content_hash(viewed.text)},
        noun="file",
    )
    docview.write_text_file(path, payload.text)
    #: The row's `size` is what the Library shows beside the name, so it has to
    #: follow the file rather than stay at whatever was uploaded. Nothing here
    #: touches the semantic index: that indexes *notes*, and a file's text has
    #: never been in it, `search_files` reads the file itself.
    attachment.size = path.stat().st_size
    session.commit()
    saved = docview.extract(path)
    return AttachedFileTextOut(
        filename=attachment.filename,
        kind=saved.kind,
        source=saved.source,
        text=saved.text,
        truncated=saved.truncated,
        message=saved.message,
        editable=True,
        content_hash=content_hash(saved.text),
    )


class PdfInfoOut(BaseModel):
    #: Whether the matching pdf-page endpoint can serve anything for this
    #: file: `media_pdf_page` for a `/media/` upload, `attached_file_pdf_page`
    #: for a note's own attachment. Moved up here, ahead of both `pdf-info`
    #: endpoints that return it: a FastAPI route decorator's `response_model`
    #: evaluates at import time, not lazily like a `from __future__ import
    #: annotations` type hint, so this has to exist before either decorator
    #: runs rather than merely before either function is called.
    available: bool
    #: Real page count, or 0 when `available` is False.
    pages: int
    #: Why `available` is False, for a caller that wants to say so rather
    #: than just hide the button. "" when `available` is True.
    message: str = ""


@router.get("/files/{attachment_id}/pdf-info", response_model=PdfInfoOut)
def attached_file_pdf_info(attachment_id: int, session: Session = Depends(get_session)) -> PdfInfoOut:
    """`media_pdf_info`'s sibling for a note's own attached PDF (the
    `Attachment` model, `uploads_dir`, a different file and a different
    table from a `/media/` upload, which is why this is a second endpoint
    rather than one that takes either id). See that docstring for why this
    exists apart from `attached_file_text` at all."""
    attachment = _existing_attachment(session, attachment_id)
    if Path(attachment.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=422, detail="Not a PDF.")
    path = _within(deps.get_config().uploads_dir, attachment.stored_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That file is no longer on disk.")
    if not pdfpages.available():
        return PdfInfoOut(
            available=False,
            pages=0,
            message=(
                "Viewing PDF pages needs a small rasteriser: install "
                "“Read scanned PDFs” in Settings, Packages."
            ),
        )
    count = pdfpages.page_count(path)
    if count == 0:
        return PdfInfoOut(
            available=False,
            pages=0,
            message=(
                "This PDF couldn't be opened. It may be corrupted, "
                "password-protected, or saved in a way this app's reader "
                "doesn't support."
            ),
        )
    return PdfInfoOut(available=True, pages=count)


@media_router.get("/files/{attachment_id}/pdf-page/{index}")
def attached_file_pdf_page(
    attachment_id: int, index: int, thumb: bool = False, session: Session = Depends(get_session)
) -> Response:
    """`media_pdf_page`'s sibling for an attached PDF, see that docstring
    for why this is always a freshly rendered PNG, never the file's own
    bytes. On `media_router`, same reason: loaded via `mediaSrc()`-tokened
    `<img src>`, not `apiJson`."""
    attachment = _existing_attachment(session, attachment_id)
    if Path(attachment.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="Not a PDF.")
    path = _within(deps.get_config().uploads_dir, attachment.stored_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That file is no longer on disk.")
    png = pdfpages.render_page(path, index, thumb=thumb)
    if png is None:
        raise HTTPException(status_code=404, detail="That page doesn't exist.")
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


#: The policy the HTML preview's own response carries, and every token in it
#: is load-bearing.
#:
#: **Why a response of its own rather than a `blob:` iframe.** The first
#: version built a Blob in the browser and framed it, and a `blob:` document
#: inherits its creator's CSP, so the app's `style-src 'self'` applied to the
#: framed page and **the page's own `<style>` block was refused.** Measured in
#: Chromium: "Refused to apply inline style", and `background-color` came back
#: `rgba(0, 0, 0, 0)` on a page that sets `#eef`. A preview that strips the
#: file's styling is not a preview of that file, and relaxing the *app's*
#: `style-src` to fix it would trade the notebook's own protection for a
#: viewer feature. A same-origin HTTP response carries its own policy instead,
#: and this is it.
#:
#: - `sandbox` (no tokens): opaque origin, no scripts, no forms, no
#:   navigation, no storage. This is what makes serving a file this app did
#:   not write safe to render at all.
#: - `script-src 'none'`: belt and braces beside the sandbox.
#: - `style-src 'unsafe-inline'`: the whole point: a page's own `<style>`
#:   and `style=` attributes. Harmless inside an opaque, scriptless frame.
#: - `img-src data:`: inline images only. **No `'self'`**, so a page cannot
#:   probe this app's own endpoints by pointing an `<img>` at them.
#: - `default-src 'none'` catches everything unlisted: no fetch, no fonts, no
#:   frames, no media, nothing off the network.
#: - `frame-ancestors 'self'`: **named explicitly, and it has to be.**
#:   `default-src 'none'` covers `frame-ancestors` too, so without this line
#:   the response forbids *being framed at all* and the pane renders
#:   `chrome-error://`. Measured, after the first version shipped with only
#:   `default-src 'none'`. The matching `X-Frame-Options: SAMEORIGIN` below
#:   is for the same reason: the app's middleware `setdefault`s `DENY` on
#:   every response, which a route that knows better may override.
HTML_PREVIEW_CSP = (
    "sandbox; default-src 'none'; script-src 'none'; "
    "style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'; "
    "frame-ancestors 'self'"
)


@media_router.get("/files/{attachment_id}/html-preview")
def attached_file_html_preview(
    attachment_id: int, session: Session = Depends(get_session)
) -> Response:
    """Render an attached .html file, for the viewer's preview pane.

    **This is the one exception to "nothing new is ever served inline", and it
    is narrow enough to state exactly.** `core/docview.py`'s docstring gives
    the rule and its reason: an inline viewer is a script host, and widening a
    file-serving endpoint's allowlist would inherit that problem once per type
    added. Here the response is `sandbox`ed with `script-src 'none'`, so it is
    the opposite of a script host, and it serves .html *only*, one suffix,
    checked below rather than by an allowlist that can be widened later.

    What is sent is the file's own text, read through `docview.extract`, the
    same clip and the same forgiving decode every other reader in the app
    gets, so a 40 MB file cannot be handed to the browser whole.

    On `media_router` because an `<iframe src>` is a declarative load and
    cannot attach a header: `require_unlock_media` is the gate that accepts
    the media cookie, the same way `<img src>` already does.
    """
    attachment = _existing_attachment(session, attachment_id)
    if Path(attachment.filename).suffix.lower() not in {".html", ".htm"}:
        raise HTTPException(status_code=404, detail="Not an HTML file.")
    path = _within(deps.get_config().uploads_dir, attachment.stored_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That file is no longer on disk.")
    viewed = docview.extract(path)
    return Response(
        content=viewed.text,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Security-Policy": HTML_PREVIEW_CSP,
            # The middleware `setdefault`s DENY; this is the one response in
            # the app that is *meant* to be framed, by the app itself.
            "X-Frame-Options": "SAMEORIGIN",
            # No sniffing past the type we declared, and no caching of one
            # notebook's file into another view.
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/files/{attachment_id}")
def delete_file(
    attachment_id: int,
    strip_references: bool = False,
    session: Session = Depends(get_session),
) -> EntryOut:
    """`strip_references` is `delete_media`'s flag on the other table, same
    reason, same default. An attached image can be embedded in the note it is
    attached to (`![](/files/12)`), and deleting the file used to leave that
    markdown behind forever."""
    attachment = _refuse_while_sealed(session, FILES.writable(session, attachment_id))
    entry = _existing_entry(session, attachment.entry_id)
    config = deps.get_config()
    changed: dict = {}
    if strip_references:
        _strip_embeds(session, f"/files/{attachment.id}", changed)
    #: Kept in the undo bin first (`core/undo_bin.py`): the row and its bytes,
    #: so Undo's `POST /files/restore` can put the file back (INBOX 898).
    token = undo_bin.stash(
        config.data_dir,
        "attachment",
        {
            "row": undo_bin.row_dict(attachment),
            "notes": changed,
            "reads": reading_bin.page_reads_of(session, "attachment", [attachment.id]),
        },
        {"bytes": _within(config.uploads_dir, attachment.stored_name)},
    )
    manager_purge.delete_attachment(session, attachment, config.uploads_dir)
    out = _to_out(session, entry)
    return JSONResponse({**out.model_dump(mode="json"), "undo_token": token})


class RestoreBody(BaseModel):
    token: str = Field(min_length=1, max_length=64)


@router.post("/files/restore")
def restore_file(body: RestoreBody, session: Session = Depends(get_session)) -> dict:
    """Put back a file `DELETE /files/{id}` took away (INBOX 898)."""
    config = deps.get_config()
    payload, kept = undo_bin.take(config.data_dir, "attachment", body.token)
    row = payload["row"]
    _existing_entry(session, row["entry_id"])
    if session.get(Attachment, row["id"]) is not None:
        raise HTTPException(status_code=409, detail="That file is already back.")
    config.uploads_dir.mkdir(parents=True, exist_ok=True)
    if "bytes" in kept and kept["bytes"].is_file():
        shutil.move(str(kept["bytes"]), str(_within(config.uploads_dir, row["stored_name"])))
    session.add(undo_bin.row_from(Attachment, row))
    reading_bin.put_page_reads_back(session, "attachment", row["id"], payload.get("reads"))
    _put_notes_back(session, payload.get("notes") or {})
    session.commit()
    undo_bin.finish(config.data_dir, body.token)
    return {"id": row["id"], "entry_id": row["entry_id"]}


def _put_notes_back(session: Session, changed: dict) -> None:
    """Undo `_strip_embeds`: a note still reading what that left is given its embeds back."""
    for note_id, (before, after) in changed.items():
        entry = session.get(Entry, int(note_id))
        if entry is not None and not entry.is_private and (entry.content or "") == (after or ""):
            entry.content = before


class AttachmentRenameBody(BaseModel):
    filename: str = Field(min_length=1, max_length=bounds.NAME_MAX)


@router.put("/files/{attachment_id}", response_model=EntryOut)
def rename_file(
    attachment_id: int, body: AttachmentRenameBody, session: Session = Depends(get_session)
) -> EntryOut:
    """Rename a file in the Library, the display name only, never the bytes.

    Mirrors `delete_file` above for the two checks that make this safe to
    expose per-item rather than globally:

    - `_existing_attachment` then `_existing_entry(attachment.entry_id)`, in
      that order, the same as `delete_file`. `Attachment` carries no
      workspace column of its own, its note does, so re-fetching the note
      through the same workspace-filtered query every other route uses is
      what makes an attachment in a workspace this request isn't in 404
      rather than quietly renaming across the boundary.
    - a private note's attachment is refused outright (403), matching the
      Library's own listing (`routes_library._images`), which already hides
      a private note's files from view entirely, renaming one from a
      surface that can't show it would be a hole the same shape as the ones
      CLAUDE.md's review section warns about: the guard here is new, but the
      boundary it enforces already exists elsewhere in the app.
    """
    attachment = FILES.writable(session, attachment_id)
    entry = _existing_entry(session, attachment.entry_id)
    if entry.is_private:
        raise HTTPException(
            status_code=403,
            detail="This file is on a private note and can't be renamed until the note is readable.",
        )
    try:
        manager_purge.rename_attachment(session, attachment, body.filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _to_out(session, entry)


# --- saving a file the app generated (§35E) ---------------------------------------
#
# Every export in this app builds a Blob in the browser and clicks a hidden
# `<a download>`. That works in a browser tab and does nothing at all in the
# desktop window: pywebview has no download handler, so the click is swallowed
# and the user gets no file and no error. Reported as "I don't think any of the
# file save features in the whole application work on the python desktop app".
#
# The fix is available because this app already runs a local server, it can
# write the file itself and say where it went. That is strictly more reliable
# than a download in every shell, and it is the only thing that works in the
# window.

#: Where generated files land by default. Beside the notes rather than in the
#: OS Downloads folder, so "where your data is" stays one answer unless the
#: user deliberately points it elsewhere, see `_exports_dir` below, added
#: after a direct request for a configurable location ("I have to dig in the
#: app data files to find and access them").
EXPORTS_DIRNAME = "exports"

#: A generated export is text or a small archive, never a media library.
MAX_SAVE_BYTES = 50 * 1024 * 1024


def _exports_dir() -> Path:
    """`export_save_dir` preference if set (validated at save time, see
    `_validated_export_dir` in routes_settings.py: so this is always a real,
    writable directory when non-empty), else the default beside the notes.
    """
    custom = deps.get_config().get_preference("export_save_dir", "")
    return Path(custom) if custom else deps.get_config().data_dir / EXPORTS_DIRNAME


class SaveFileBody(BaseModel):
    """One file the browser built and wants written to disk."""

    filename: str = Field(min_length=1, max_length=120)
    #: Base64, because the same route has to carry a .zip as well as a .md.
    content_base64: str = Field(max_length=bounds.FILE_BASE64_MAX)


def safe_filename(name: str) -> str:
    """A filename that cannot escape the exports folder.

    Not a sanitiser that tries to be clever, a whitelist. The name arrives
    from the browser, and the browser is not the trust boundary here even
    though the app is single-user: the AI writes some of these names.
    """
    cleaned = os.path.basename(str(name))  # drops any directory part, "..", drive letters
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", cleaned).strip(". ")
    if not cleaned:
        raise HTTPException(status_code=422, detail="That filename can't be used.")
    return cleaned[:120]


def _within(base_dir: Path, name: str, *, typed: bool = False) -> Path:
    """`base_dir / name` through `paths.contained`, a 422 when it reaches
    outside. The one containment check for exports, uploads and media; the
    CodeQL history of its shape is in `core/paths.py`. `typed`: the name is
    one the person wrote (an export), so the sentence says filename."""
    try:
        return paths.contained(base_dir, name)
    except paths.OutsideFolder:
        if typed:
            raise HTTPException(status_code=422, detail="That filename can't be used.") from None
        raise HTTPException(status_code=422, detail="That file can't be used.") from None


@router.post("/files/save", dependencies=[Depends(this_computer_only)])
def save_generated_file(body: SaveFileBody) -> dict:
    """Write a generated export next to the notes and say where it went."""
    try:
        data = base64.b64decode(body.content_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(status_code=422, detail="That file couldn't be read.") from exc
    if len(data) > MAX_SAVE_BYTES:
        raise HTTPException(status_code=413, detail="That file is too large to save.")

    exports = _exports_dir()
    exports.mkdir(parents=True, exist_ok=True)
    name = safe_filename(body.filename)
    target = _within(exports, name, typed=True)
    # Never silently overwrite: two exports of the same chat on the same day
    # are two files someone may want to compare.
    if target.exists():
        stem, suffix = target.stem, target.suffix
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = _within(exports, f"{stem}-{stamp}{suffix}", typed=True)
    #: A half-written export is worse than no export: it lands in the folder
    #: Settings lists, under the name the person chose, and opens as a
    #: truncated file rather than as an obvious failure. `write_bytes`
    #: truncates first and fills after, so out of space leaves exactly that.
    with diskspace.partial_write(target):
        target.write_bytes(data)
    return {"path": str(target), "filename": target.name, "bytes": len(data)}


#: **What is in the exports folder, and each file back out of it.**
#:
#: Asked for directly (INBOX 159): "exported or downloaded files and images
#: etc should appear in the notifications to be accessible, maybe there should
#: also be an area somewhere maybe in settings to open the exports folder
#: location and access exported or downloaded files". `save_generated_file`
#: above wrote the files and `open_exports_folder` below reveals the folder,
#: but only on the desktop, and only if you remembered a toast. This is the
#: list Settings draws and the download link each row carries, so a browser
#: tab can get its exports back too: a file the app wrote is served from the
#: folder it wrote it to, contained by `_within` exactly as the write
#: was.
#:
#: Newest first and capped, because the folder grows one file per export for
#: as long as the app is used and a settings screen is not a file manager;
#: the folder itself is one click away for the rest.
EXPORTS_LIST_LIMIT = 50


@router.get("/files/exports")
def list_exports(
    response: Response,
    limit: int = Query(EXPORTS_LIST_LIMIT, ge=1, le=500),
    offset: int = Query(0, ge=0),
    cursor: str | None = paging.cursor_param(),
) -> dict:
    """The exports folder, newest first, paged like every other growing list
    (`limit`/`offset`, `X-Total-Count` for the whole). Sorted on the raw mtime
    with the name as the tie-break: two files saved within one second, which
    CI's disks manage easily, would otherwise come back in either order."""
    offset = paging.start(cursor, offset)
    exports = _exports_dir()
    if not exports.is_dir():
        response.headers["X-Total-Count"] = "0"
        return {"path": str(exports), "files": []}
    rows = []
    for entry in exports.iterdir():
        if not entry.is_file() or entry.name.startswith("."):
            continue
        stat = entry.stat()
        rows.append(
            (
                stat.st_mtime,
                entry.name,
                {
                    "filename": entry.name,
                    "bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                },
            )
        )
    rows.sort(key=lambda row: (row[0], row[1]), reverse=True)
    response.headers["X-Total-Count"] = str(len(rows))
    paging.finish(response, offset, limit, len(rows))
    return {"path": str(exports), "files": [row[2] for row in rows[offset : offset + limit]]}


@router.get("/files/exports/{filename}")
def download_export(filename: str) -> FileResponse:
    """One exported file, as a download. `safe_filename` and `_within`
    are the same two locks the write went through, in the same order."""
    exports = _exports_dir()
    target = _within(exports, safe_filename(filename), typed=True)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="That export is no longer there.")
    return FileResponse(str(target), filename=target.name)


@router.post("/files/open-exports-folder", dependencies=[Depends(this_computer_only)])
def open_exports_folder() -> dict:
    """Reveal the exports folder in the OS file manager.

    Asked for directly ("I have to dig in the app data files to find and
    access them") after `save_generated_file` above started writing graph
    PNGs, chat exports and the like into `data_dir/exports` with only a
    toast naming the path, real, but no help finding it again later.
    Desktop only: a browser tab has no file manager to hand this to, and
    `webbrowser.open`-ing a `file://` URL from a server request a browser
    could also reach is a foothold a purely local desktop shell doesn't
    have to give a page.
    """
    if os.getenv("TESSELLATE_DESKTOP") != "1":
        raise HTTPException(
            status_code=409, detail="Only the desktop app can open a file manager window."
        )
    exports = _exports_dir()
    reveal_folder(exports, "the exports folder")
    return {"path": str(exports)}


def reveal_folder(folder: Path, what: str) -> None:
    """Open `folder` in the OS file manager, creating it first; a 500 that
    names the path when the OS refuses. Shared with Settings, About,
    Maintenance's launcher logs (routes_maintenance.py)."""
    folder.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "win32":
            # Safe even though the path can now be user-configured: passed as
            # a single argument, never through a shell, and _validated_export_dir
            # already refused anything that isn't a real, writable directory.
            os.startfile(folder)
        elif sys.platform == "darwin":
            # Popen, not run(): the launcher forks its own file-manager window
            # and normally returns at once, but this request must not hang
            # waiting on a GUI process either way, same reasoning as
            # `restart_in_console_mode` being fire-and-forget rather than
            # something this response waits on.
            subprocess.Popen(["open", str(folder)], creationflags=NO_WINDOW)
        else:
            subprocess.Popen(["xdg-open", str(folder)], creationflags=NO_WINDOW)
    except OSError as exc:
        logger.warning("couldn't open %s", what, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Couldn't open {what}. You can find it at {folder}.",
        ) from exc


#: What `/media/` will accept and, more to the point, what it will serve.
#:
#: This folder exists for images dropped into markdown, and `/media/{name}`
#: serves its contents from the app's **own origin**: so an `.html` or `.svg`
#: landing here is a script running with the notebook's cookies and unlock
#: token, not a picture. That is a stored-XSS shape even though the app is
#: single-user and local, and it is worth closing for one reason above the
#: others: the AI can write into this folder too, so "the only person who can
#: put a file here is the person at the keyboard" is not true.
#:
#: An allowlist rather than a denylist of dangerous types, because the failure
#: mode of a missing entry is "this image didn't upload", and the failure mode
#: of a missed denylist entry is the paragraph above.
MEDIA_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".bmp", ".ico", ".pdf"}
)


@router.post("/media/upload")
def upload_media(
    file: UploadFile,
    direct: bool = Form(False),
    board: bool = Form(False),
    session: Session = Depends(get_session),
) -> dict:
    """General file/image upload for drag-and-drop in markdown (documents &
    notes), and for the Library's own direct "Upload images" button.

    `direct` distinguishes the two: a note, document or chat composer
    upload is *staged*: it may be discarded before ever being saved or
    sent, so nothing runs on it here (see `direct` below) and OCR/
    captioning/vision-OCR instead fire when whatever referenced it is
    actually committed (`core/media_process.py`, called from the note,
    document and conversation save routes). The Library's own upload
    button sends `direct=True`: there is no separate "save" step for it: 
    the upload itself *is* the commit, the third case named directly
    ("uploaded directly to the library").
    """
    media_dir = deps.get_config().data_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "file").suffix[:12].lower()
    if suffix not in MEDIA_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail=(
                "Only images and PDFs can be dropped in here. "
                "Use the note's attachments for anything else."
            ),
        )
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    destination = media_dir / stored_name

    #: Same guard, same measured reason as the attachment upload above.
    size = 0
    with diskspace.partial_write(destination):
        with destination.open("wb") as out:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_FILE_BYTES:
                    out.close()
                    destination.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="That file is larger than 50 MB.")
                out.write(chunk)

    try:
        with destination.open("rb") as written:
            bounds.check_image_upload(written.read(64), size, suffix)
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    original_name = bounds.display_name(file.filename, stored_name)
    # `size` was already counted above while streaming the upload to disk, 
    # storing it here means `GET /media` never has to `stat()` this file to
    # answer "how big is it" (PLAN.md §0 P6).
    #: `board`: a picture placed on a board or map. It is not listed in the
    #: Library and nothing reads it until Save to Library (K18).
    upload = MediaUpload(
        filename=stored_name, original_name=original_name, size_bytes=size, board_only=board and not direct
    )
    session.add(upload)
    session.commit()
    session.refresh(upload)
    # OCR, captioning and vision OCR (core/media_process.py) all run on a
    # background thread, never on this request, Tesseract alone can take a
    # second or two per image, and a vision-model round trip far longer.
    # Only fired here for `direct=True` (the Library's own upload button);
    # every staged upload gets processed later, at the moment it's actually
    # committed: see this function's own docstring and media_process.py's.
    if direct:
        media_process.process_committed_upload(upload, media_dir)
    # `id` lets a caller that changes its mind (the capture form's own
    # attachment chip, removable with a click) call DELETE /media/{id}
    # instead of just detaching the markdown reference and leaving the
    # file behind: asked for directly.
    return {"id": upload.id, "url": f"/media/{stored_name}", "filename": original_name}


class MediaUploadOut(BaseModel):
    id: int
    url: str
    original_name: str
    #: "" until OCR finishes (or never, off the tesseract binary, or a PDF)
    #:, never null over the wire, so the frontend can filter on it with a
    #: plain substring match without a null check at every call site.
    ocr_text: str = ""
    #: "" until captioning finishes (or never, no vision model available, or
    #: a PDF): same never-null convention as ocr_text, same reason.
    caption: str = ""
    #: Which model wrote `caption`, or "" when there is none or it was only
    #: ever typed by hand. Surfaced so a caption reads as one model's guess,
    #: not the app's own opinion (asked for directly).
    caption_model: str = ""
    #: True once a person has typed over an AI caption, or typed one from
    #: scratch: see `MediaUpload.caption_edited`'s docstring.
    caption_edited: bool = False
    #: A vision model's verbatim transcription of text in the image
    #: (`ai/vision_ocr.py`), distinct from `ocr_text` (Tesseract) and from
    #: `caption` (a description). "" until run, or when a run found no
    #: legible text: same never-null convention as the other two.
    vision_ocr_text: str = ""
    #: Which model wrote `vision_ocr_text`, or "" when there is none.
    vision_ocr_model: str = ""
    #: When it was uploaded, ISO-8601. Asked for with the lightbox rework, 
    #: "maybe it can have the image information and other info about it below
    #: the image", and it is the one fact of that kind the browser cannot
    #: work out for itself: dimensions come from the decoded image, the name
    #: is already here, and a byte count would cost one `stat` per row on
    #: every gallery load for a number nobody asked for.
    created_at: str = ""
    #: True when this upload has pages the server can draw (a PDF, with the
    #: render extra installed), the same field and meaning as the attachment
    #: gallery's: the tile asks for a first page only then.
    has_pages: bool = False
    #: True while the picture lives only on a board or map (K18); Save to
    #: Library (`POST /media/{id}/library`) clears it.
    board_only: bool = False
    #: Bytes on disk, filled by `media_meta` only (one `stat` for the one file
    #: asked about, which the listing above declines to pay per row). The
    #: attachment card states it beside the kind (INBOX 440 (2)); 0 means
    #: unknown or gone, and the card then says nothing rather than "0 B".
    size: int = 0
    #: **Where this file is actually used**, one entry per note, document or
    #: board that references it, as `{kind, id, label}`. The gallery showed a
    #: thumbnail, a filename and two empty prompts and could not answer the
    #: only question anyone brings to it: what is this attached to? Empty
    #: means genuinely unreferenced (the same condition the orphan check uses
    #:, both read `media_gc.referenced_names`, so they cannot disagree).
    used_by: list[dict] = []
    #: True when a locked private note made the usage scan incomplete, so an
    #: empty `used_by` means "could not check" rather than "not used". The UI
    #: must not call a file unused on this basis.
    usage_incomplete: bool = False
    #: Size on disk in bytes; 0 when the file cannot be stat'ed (a row
    #: outliving its file is a real state the gallery already draws a
    #: placeholder for). Asked for directly with the Files sub-tab redesign:
    #: "file details such as the type, size, topic/category".
    size_bytes: int = 0
    #: How many of this document's pages have a stored reading, see
    #: `AttachmentGalleryOut.pages_read` for why the count is sent rather than
    #: derived from the joined text.
    pages_read: int = 0


#: A page of the gallery, not a ceiling on how many uploads a notebook may
#: hold: `X-Total-Count` reports the real size and `offset` reaches the
#: rest, so `renderLibraryImagesGallery` and `ocrLoadSiblings` (library.js)
#: page until they have everything. 200 rather than the grid's own page
#: size because both of those need the whole set (one to search it, one to
#: build the OCR workspace's rail), and 200 keeps the number of round trips
#: sane. The **max** is 500 rather than the 1000 the document and reminder
#: lists allow, because a row here is not a fixed cost: `ocr_text`,
#: `caption` and `vision_ocr_text` ride along, and a page of scanned text
#: can be kilobytes on its own, so a row count is a poor proxy for bytes and
#: the ceiling is set lower to compensate.
MEDIA_PAGE_SIZE = 200
MEDIA_PAGE_SIZE_MAX = 500


def _readings(upload: MediaUpload, used: dict, usage_incomplete: bool, page_text: dict) -> dict:
    """SEC-A2: with a private note locked, an upload that note embeds and no
    readable note names keeps its readings back until unlock."""
    if usage_incomplete and upload.in_private_note and not used.get(upload.filename):
        return {"ocr_text": "", "caption": "", "vision_ocr_text": ""}
    return {
        "ocr_text": upload.ocr_text or "",
        "caption": upload.caption or "",
        "vision_ocr_text": upload.vision_ocr_text or page_text.get(upload.id, ""),
    }


@router.get("/media", response_model=list[MediaUploadOut])
def list_media(
    response: Response,
    limit: int = Query(default=MEDIA_PAGE_SIZE, ge=1, le=MEDIA_PAGE_SIZE_MAX),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = paging.cursor_param(),
    session: Session = Depends(get_session),
) -> list[MediaUploadOut]:
    """A page of the uploads `/media/upload` has produced: asked for
    directly (a gallery for note-attached and whiteboard images alike).
    Newest first, the same convention the Library's own sort defaults to.

    Paged for the reason `GET /entries` is: one response used to be the
    whole table (300 uploads measured at 117.6 KB, growing with the table),
    which is a real risk for a local app that is supposed to degrade
    gracefully rather than stall. `X-Total-Count` is the real size whatever
    the page, and the id breaks a tie on `created_at` so two uploads made in
    the same second cannot swap places between pages and hide a row.
    """
    offset = paging.start(cursor, offset)
    total, uploads = uploads_repo.library_page(session, limit, offset)
    response.headers["X-Total-Count"] = str(total)
    paging.finish(response, offset, limit, total)
    # One scan for the whole gallery rather than one per file: `usage_map`
    # walks each table once and inverts the result, so this stays a single
    # pass no matter how many uploads there are.
    used, usage_incomplete = media_gc.usage_map(session)
    media_dir = deps.get_config().data_dir / "media"

    # PLAN.md §0 P6: `size_bytes` used to be `Path.stat()`'d here on *every*
    # row of *every* call, the disk hit this whole column exists to remove.
    # Uploads made after the column existed already carry it (see
    # `upload_media`); this backfills only the rows that predate it, NULL,
    # never 0, is what a pre-existing row reads as (the column's own
    # docstring): one `stat()` each, the only time each row ever pays it,
    # in a single commit rather than one write per row.
    unsized = [u for u in uploads if u.size_bytes is None]
    if unsized:
        for u in unsized:
            try:
                u.size_bytes = (media_dir / u.filename).stat().st_size
            except OSError:
                # A row whose file is gone still lists, the gallery has a
                # placeholder for exactly that, so this leaves size_bytes at
                # 0 rather than leaving it NULL (which would just retry the
                # same failing stat() on every future call) or raising.
                u.size_bytes = 0
        session.commit()

    media_page_text = _page_read_text_map("upload", [u.id for u in uploads])
    #: Asked once per page of the gallery: an import check, the same answer for
    #: every row (OPEN.md, "A Files row asks for a PDF first page that this
    #: sandbox cannot render": the tile used to guess from the name and 404).
    can_draw_pages = pdfpages.available()
    media_pages_read = _page_read_count_map("upload", [u.id for u in uploads])
    return [
        MediaUploadOut(
            id=u.id,
            pages_read=media_pages_read.get(u.id, 0),
            used_by=used.get(u.filename, []),
            usage_incomplete=usage_incomplete,
            size_bytes=u.size_bytes or 0,
            url=f"/media/{u.filename}",
            original_name=u.original_name,
            **_readings(u, used, usage_incomplete, media_page_text),
            caption_model=u.caption_model or "",
            caption_edited=u.caption_edited,
            vision_ocr_model=u.vision_ocr_model or "",
            created_at=u.created_at.isoformat() if u.created_at else "",
            has_pages=can_draw_pages and Path(u.filename).suffix.lower() == ".pdf",
        )
        for u in uploads
    ]


class MediaOrphansOut(BaseModel):
    orphans: list[MediaUploadOut]
    #: True when a locked private note made the check incomplete, the list
    #: above is not exhaustive in that case, and DELETE refuses to act on it.
    skipped_private: bool
    #: How many uploads DELETE actually removed. Always 0 for the GET dry run.
    deleted: int = 0
    #: How many orphans there are in total, which is not `len(orphans)` once
    #: the GET is paged.
    total: int = 0


# Declared ahead of the `/media/{upload_id}` routes below: FastAPI compiles
# `{upload_id}` as a plain path segment and only rejects a non-integer value
# (like "orphans") when the handler runs, by which point an earlier-declared
# `/media/{upload_id}` would already have claimed the match and returned a
# 422 instead of ever reaching these.
@router.get("/media/orphans", response_model=MediaOrphansOut)
def list_orphaned_media(
    response: Response,
    limit: int = Query(default=MEDIA_PAGE_SIZE_MAX, ge=1, le=MEDIA_PAGE_SIZE_MAX),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = paging.cursor_param(),
    session: Session = Depends(get_session),
) -> MediaOrphansOut:
    """Uploads no live note, document or whiteboard image object still
    points at (ROADMAP.md item 20a). A dry run: nothing is deleted here.

    `total` rather than a header, unlike the other paged lists here, because
    this one has a body of its own already and the number is the answer the
    screen actually shows ("42 files nothing points at"). The page bounds the
    response, not the check: `DELETE /media/orphans` still acts on every
    orphan it finds, because deleting a page at a time would mean the count
    on screen and the count deleted could never agree.
    """
    offset = paging.start(cursor, offset)
    orphans, skipped_private = media_gc.find_orphaned_media(session)
    paging.finish(response, offset, limit, len(orphans))
    return MediaOrphansOut(
        orphans=[
            MediaUploadOut(id=u.id, url=f"/media/{u.filename}", original_name=u.original_name)
            for u in orphans[offset : offset + limit]
        ],
        skipped_private=skipped_private,
        total=len(orphans),
    )


@router.delete("/media/orphans", response_model=MediaOrphansOut)
def clean_orphaned_media(session: Session = Depends(get_session)) -> MediaOrphansOut:
    """Deletes every currently-orphaned upload's file and tracking row.

    Refuses to delete anything (`skipped_private: true`, `deleted: 0`)
    while a locked private note leaves the check incomplete, see
    `media_gc`'s own docstring for why.
    """
    media_dir = deps.get_config().data_dir / "media"
    deleted, skipped_private = media_gc.delete_orphaned_media(session, media_dir)
    return MediaOrphansOut(
        orphans=[
            MediaUploadOut(
                id=row["id"], url=f"/media/{row['filename']}", original_name=row["original_name"]
            )
            for row in deleted
        ],
        skipped_private=skipped_private,
        deleted=len(deleted),
    )


# Declared ahead of `/media/{upload_id}` for the same reason `/media/orphans`
# above is: "meta" would otherwise be matched as an `{upload_id}` and 422 out
# before ever reaching this handler.
@router.get("/media/meta/{filename}", response_model=MediaUploadOut)
def media_meta(filename: str, session: Session = Depends(get_session)) -> MediaUploadOut:
    """Everything the app knows *about* one upload, looked up by its stored
    filename: which is the only identifier most of the app actually holds.

    Reported directly: the lightbox showed a caption, OCR text and the
    picture's own facts when opened from the Image Gallery and nothing at
    all anywhere else. The cause was not the lightbox, it was that
    `openLightbox` took this metadata as *arguments*, and of its nine
    callers only the gallery had a full `MediaUpload` row to pass. Every
    other one (a note's attachment, a chat image, a graph or dashboard
    thumbnail, a whiteboard object) has a `/media/<filename>` url and
    nothing else, so it passed a filename and a url and the panel below the
    picture stayed empty.

    Handing the lightbox a way to *ask* fixes it in one place instead of
    nine, and keeps working for any caller added later, which is the same
    reason `GET /media` exists rather than each surface keeping its own
    list. Keyed on filename rather than id precisely because a url is what
    those callers have.
    """
    upload = session.query(MediaUpload).filter(MediaUpload.filename == filename).first()
    if not upload:
        # A url can outlive its row: deleting an upload deliberately leaves
        # any note still pointing at it alone (see delete_media below), so a
        # miss here is an ordinary state, not a fault.
        raise HTTPException(status_code=404, detail="No upload by that name.")
    if media_gc.sealed_only(session, upload.filename):
        raise HTTPException(status_code=409, detail="Unlock first.")
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
        created_at=upload.created_at.isoformat() if upload.created_at else "",
        size=_media_size(upload.filename),
        board_only=bool(upload.board_only),
    )


def _media_size(filename: str) -> int:
    """Bytes on disk for one upload, or 0 when it is gone or unreadable."""
    try:
        return _within(deps.get_config().data_dir / "media", filename).stat().st_size
    except (OSError, HTTPException):
        return 0


@router.get("/media/text/{filename}", response_model=AttachedFileTextOut)
def media_text(filename: str, session: Session = Depends(get_session)) -> AttachedFileTextOut:
    """One uploaded document's *text*, for reading it in the lightbox.

    Asked for directly: the lightbox should become "a sort of document
    preview… for viewing pdfs, word documents, spreadsheets, text files, code
    files etc but in a presentable way that isn't editable".

    Almost none of that is new work, and deliberately so, `docview.extract`
    and its whole format table already existed for **attachments**
    (`GET /files/{id}/text`), and it already returns the `kind`
    (markdown/code/plain) that says how to render and the `source` that says
    whether a human wrote the text or a vision model read it off a scan. The
    only thing missing was that uploads, which is what the Library and the
    lightbox actually hold, had no way to reach it. So this is the same
    extraction pointed at `media/` instead of `uploads/`.

    **There is no `PUT` beside this one, and that is not an oversight.** Its
    sibling `save_attached_file_text` exists because a note's attachment can
    be a .md, a .txt or a source file. A `/media/` upload cannot: `MEDIA_SUFFIXES`
    is images and PDF, so `editable` here is always False and a save route
    would be a feature that never ran once, the shape CLAUDE.md names. The
    flag and its message are still returned, so the viewer can say *why*
    rather than silently omitting Edit.

    Deliberately returns **text, never the file**, for the reason
    `read_file_text` above states at length and `media_file` at the bottom of
    this module explains: what this sends has already stopped being a .docx,
    so a viewer built on it cannot inherit the serve-it-inline problem once
    per file type. That is also why the preview is read-only, a property of
    the extraction, not a missing feature. Editing here would mean writing
    text back into a format it was never in.
    """
    upload = session.query(MediaUpload).filter(MediaUpload.filename == filename).first()
    if not upload:
        raise HTTPException(status_code=404, detail="No upload by that name.")
    path = deps.get_config().data_dir / "media" / upload.filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="That file is no longer on disk.")
    # Same scanned-PDF fallback the attachment viewer passes. It only does any
    # work for a PDF with no text layer, and only when the pdfpages extra and
    # a vision model are both present; every other file returns before it is
    # consulted.
    viewed = docview.extract(path, vision_reader=vision_ocr.pdf_reader_or_none())
    editable, edit_message = docview.editability(path, viewed)
    return AttachedFileTextOut(
        filename=upload.original_name,
        kind=viewed.kind,
        source=viewed.source,
        text=viewed.text,
        truncated=viewed.truncated,
        message=viewed.message,
        extra=viewed.extra,
        editable=editable,
        edit_message=edit_message,
    )


def _media_upload_path(session: Session, filename: str) -> tuple[MediaUpload, Path]:
    upload = session.query(MediaUpload).filter(MediaUpload.filename == filename).first()
    if not upload:
        raise HTTPException(status_code=404, detail="No upload by that name.")
    path = _within(deps.get_config().data_dir / "media", upload.filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="That file is no longer on disk.")
    return upload, path


@router.get("/media/pdf-info/{filename}", response_model=PdfInfoOut)
def media_pdf_info(filename: str, session: Session = Depends(get_session)) -> PdfInfoOut:
    """Page count for `pdf_page` below to page through, deliberately its
    own round trip rather than folded into `media_text`'s response, so the
    lightbox can show real PDF pages **without ever calling `media_text` (and
    therefore without markitdown or a vision model in the loop at all)**.
    That split is the point: viewing a PDF like a PDF and *reading* it with
    AI are two different questions (`docview.py`'s module docstring answers
    the second one at length), and until now this app only had an answer for
    the second: a scanned lecture PDF got stuck on the AI extraction path
    with no way to just look at the pages, direct instruction: "pdfs and
    documents should be viewable, accessible and manageable without the ai,
    even if the ai cant read them."
    """
    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=422, detail="Not a PDF.")
    _upload, path = _media_upload_path(session, filename)
    if not pdfpages.available():
        return PdfInfoOut(
            available=False,
            pages=0,
            message=(
                "Viewing PDF pages needs a small rasteriser: install "
                "“Read scanned PDFs” in Settings, Packages."
            ),
        )
    count = pdfpages.page_count(path)
    if count == 0:
        return PdfInfoOut(
            available=False,
            pages=0,
            message=(
                "This PDF couldn't be opened. It may be corrupted, "
                "password-protected, or saved in a way this app's reader "
                "doesn't support."
            ),
        )
    return PdfInfoOut(available=True, pages=count)


@media_router.get("/media/pdf-page/{filename}/{index}")
def media_pdf_page(
    filename: str, index: int, thumb: bool = False, session: Session = Depends(get_session)
) -> Response:
    """One page of an uploaded PDF, rasterised to a PNG, the actual pixels
    a `<img>` in the lightbox loads, one per page, so a PDF scrolls like a
    PDF. On `media_router` rather than `router`: this is loaded the same
    declarative way `/media/{filename}` already is (`mediaSrc()` in app.js
    appends the unlock token as a query param for exactly these routes,
    since a plain `<img src>` cannot carry a header), not fetched with
    `apiJson` the way `media_pdf_info` above is.

    Always a **freshly rendered PNG**, never the PDF's own bytes: the
    security reasoning `get_media`'s own docstring gives for refusing to
    serve a PDF inline (a script host, from a folder not guaranteed to hold
    only what this app wrote) does not apply to pixels this process drew
    itself. A rasterised page cannot carry a PDF action, an embedded script,
    or anything else a PDF's own structure can.
    """
    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="Not a PDF.")
    _upload, path = _media_upload_path(session, filename)
    png = pdfpages.render_page(path, index, thumb=thumb)
    if png is None:
        raise HTTPException(status_code=404, detail="That page doesn't exist.")
    # Kept in memory by `pdfpages` (a bounded LRU keyed by the file's mtime and
    # size), not on disk. `thumb=1` is the rail's quarter-width picture.
    # `Cache-Control` still lets the *browser* avoid re-fetching a page it has.
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


#: An embed of one stored file: `![alt](/media/name.png)` or
#: `![alt](/files/12)`, with the optional title markdown allows. Written
#: against a *literal* url (escaped by the caller), so there is no
#: user-controlled repetition in it, the shape CodeQL flags as
#: polynomial-ReDoS is exactly what this avoids.
def _embed_pattern(url: str) -> re.Pattern[str]:
    #: Markdown's optional title, in either quote style.
    title = r"""(?:\s+["'][^"'\n]{0,200}["'])?"""
    return re.compile(r"!\[[^\]\n]{0,200}\]\(" + re.escape(url) + title + r"\)")


def _strip_embeds(session: Session, url: str, changed: dict | None = None) -> list[int]:
    """Remove every `![...](url)` from the notes that hold one.

    Reported directly: *"notes still mention removed images"*. Deleting the
    file left the markdown behind, so the note rendered a placeholder saying
    the image was gone, forever, with no way to tidy it but editing the note
    by hand and knowing what to look for.

    Only the **embed** is removed, never a link: `[see the scan](/media/x.png)`
    is a sentence the author wrote and would be a hole in their prose if it
    vanished. And only exact-url matches, so nothing else in the note moves.

    `changed`, when given, is filled with `{note id: [text before, text after]}`
    so the undo bin can put the embeds back (INBOX 898).
    """
    pattern = _embed_pattern(url)
    touched: list[int] = []
    #: `LIKE` narrows the scan to notes that mention the url at all; the
    #: regex above decides. A private note is encrypted at rest and its
    #: content is not readable here, which is also why one cannot embed a
    #: Library image into one in the first place.
    rows = session.scalars(
        select(Entry).where(
            Entry.is_deleted.is_(False),
            Entry.is_private.is_(False),
            Entry.content.contains(url),
        )
    ).all()
    for entry in rows:
        cleaned = pattern.sub("", entry.content or "")
        if cleaned == entry.content:
            continue
        #: The blank line the embed used to sit on goes with it, otherwise a
        #: note loses a picture and gains a gap where it was.
        before = entry.content
        entry.content = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        if changed is not None:
            changed[str(entry.id)] = [before, entry.content]
        touched.append(entry.id)
    if touched:
        session.commit()
    return touched


@router.delete("/media/{upload_id}")
def delete_media(
    upload_id: int,
    strip_references: bool = False,
    session: Session = Depends(get_session),
) -> dict:
    """Removes the file and its tracking row.

    `strip_references` also takes the `![...](...)` out of every note that
    embedded it: asked for after the placeholder shipped: a note that keeps
    pointing at a file you deleted is a note that renders "this image was
    removed" for the rest of its life. Off by default, because deleting a
    file and editing someone's notes are different acts and the second one
    has to be chosen: the caller asks, the UI offers it in the confirm.
    """
    upload = deps.get_or_404(session, MediaUpload, upload_id, "That upload could not be found.")
    config = deps.get_config()
    media_dir = (config.data_dir / "media").resolve()
    candidate = (media_dir / upload.filename).resolve()
    cleaned: list[int] = []
    changed: dict = {}
    if strip_references:
        #: Before the row goes: the url is built from `upload.filename`.
        cleaned = _strip_embeds(session, f"/media/{upload.filename}", changed)
    #: The row and its bytes go to the undo bin, not to nowhere (INBOX 898):
    #: `POST /media/restore` with this token puts both back.
    token = undo_bin.stash(
        config.data_dir,
        "media",
        {
            "row": undo_bin.row_dict(upload),
            "notes": changed,
            "reads": reading_bin.page_reads_of(session, "upload", [upload.id]),
        },
        {"bytes": candidate} if candidate.is_relative_to(media_dir) else {},
    )
    reading_bin.forget_page_reads(session, "upload", [upload.id])
    session.delete(upload)
    session.commit()
    return {"status": "ok", "cleaned_notes": cleaned, "undo_token": token}


@router.post("/media/restore", response_model=MediaUploadOut)
def restore_media(body: RestoreBody, session: Session = Depends(get_session)) -> MediaUploadOut:
    """Put back a Library file `DELETE /media/{id}` took away (INBOX 898).

    The same id when it is free, so a note that still points at the file works
    again; a new one when it is not.
    """
    config = deps.get_config()
    payload, kept = undo_bin.take(config.data_dir, "media", body.token)
    row = payload["row"]
    media_dir = config.data_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    if "bytes" in kept and kept["bytes"].is_file():
        shutil.move(str(kept["bytes"]), str(media_dir / row["filename"]))
    upload = undo_bin.row_from(MediaUpload, row, keep_id=session.get(MediaUpload, row["id"]) is None)
    session.add(upload)
    session.flush()
    reading_bin.put_page_reads_back(session, "upload", upload.id, payload.get("reads"))
    _put_notes_back(session, payload.get("notes") or {})
    session.commit()
    session.refresh(upload)
    undo_bin.finish(config.data_dir, body.token)
    return MediaUploadOut(id=upload.id, url=f"/media/{upload.filename}", original_name=upload.original_name)


class MediaRenameBody(BaseModel):
    original_name: str = Field(min_length=1, max_length=300)


@router.put("/media/{upload_id}", response_model=MediaUploadOut)
def rename_media(
    upload_id: int, body: MediaRenameBody, session: Session = Depends(get_session)
) -> MediaUploadOut:
    """Rename a Library image, the display name only.

    `original_name` is a label, exactly like `Attachment.filename`: the bytes
    live under `upload.filename`, a generated name, and nothing here touches
    the disk. So it goes through the same validator rather than a laxer one of
    its own: two "rename a file" endpoints in one module with two different
    ideas of what a filename may contain is how the strict one quietly stops
    being the rule.
    """
    upload = deps.get_or_404(session, MediaUpload, upload_id, "That upload could not be found.")
    try:
        upload.original_name = manager_purge.validate_attachment_filename(body.original_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return MediaUploadOut(
        id=upload.id, url=f"/media/{upload.filename}", original_name=upload.original_name
    )


class CaptionBody(BaseModel):
    #: The write-once rule (`captioning.caption_and_store`) otherwise leaves
    #: an existing caption alone, this is the one way to overwrite one,
    #: asked for directly: "if one is already there, another doesn't need
    #: to be written unless the user presses the button to rewrite it."
    force: bool = False
    #: A caption typed by hand instead of generated, asked for directly
    #: ("allow for manual input of image captions"). `None` (the default)
    #: means "generate one"; any string, including "", sets the caption to
    #: exactly that text and skips the model entirely, a person editing a
    #: caption is not asking for a second opinion. `""` clears it back to
    #: uncaptioned rather than storing an empty string as if it meant
    #: something, matching the null/"not captioned yet" convention
    #: `MediaUpload.caption` already uses.
    text: str | None = Field(default=None, max_length=2000)
    #: Who wrote `text` (the owner, 2026-09-24). "hand" is a person at a caption field,
    #: which is every caller but one. "app" is the app describing a picture
    #: it made itself, a board export's "Part of the mind map ..., exported
    #: from Tessellate" line: stored as written by `APP_CAPTION_AUTHOR` and not
    #: as edited, so the lightbox and the Library card stop saying "typed by
    #: hand" about text nobody typed, and a vision model that later replaces
    #: it is credited alone rather than read as a person's edit. Kept in
    #: `caption_model` rather than a new column: that field already means
    #: "who wrote this caption", and a sentinel there needs no migration.
    source: Literal["hand", "app"] = "hand"


#: The name the app's own captions are credited to (see `CaptionBody.source`).
#: A stored sentinel, not copy: captions written before the rename to
#: Tessellate carry it, so it stays; the lightbox shows the current name.
APP_CAPTION_AUTHOR = "MemoryMap"  # brand: keep


@router.post("/media/{upload_id}/library", response_model=MediaUploadOut)
def save_media_to_library(upload_id: int, session: Session = Depends(get_session)) -> MediaUploadOut:
    """Save a board-only picture to the Library: it is listed from now on and
    its readers (text, caption) start, as for a direct upload (K18)."""
    upload = _existing_upload(session, upload_id)
    if upload.board_only:
        upload.board_only = False
        session.commit()
        session.refresh(upload)
        media_process.process_committed_upload(upload, deps.get_config().data_dir / "media")
    return MediaUploadOut(
        id=upload.id,
        url=f"/media/{upload.filename}",
        original_name=upload.original_name,
        ocr_text=upload.ocr_text or "",
        caption=upload.caption or "",
        caption_model=upload.caption_model or "",
        caption_edited=upload.caption_edited,
        created_at=upload.created_at.isoformat() if upload.created_at else "",
        board_only=False,
    )


@router.post("/media/{upload_id}/caption", response_model=MediaUploadOut)
def caption_media(
    upload_id: int, body: CaptionBody = CaptionBody(), session: Session = Depends(get_session)
) -> MediaUploadOut:
    """Generate (or, with `force`, regenerate) a caption for one image, or, 
    with `text`, set one by hand. The manual-generate trigger and the
    manual-edit field are both reached from the Library and the Notes tab.

    Runs synchronously: captioning one image is a single model round trip,
    no different in shape from the AI-edit or link-reason calls this app
    already blocks on behind a spinner. `caption_and_store` opens its own
    session (the same shape `ocr.extract_and_store` uses from a background
    thread): `session.refresh` below picks up what it committed.
    """
    upload = _existing_upload(session, upload_id)
    is_picture = Path(upload.filename).suffix.lower() in captioning.CAPTION_SUFFIXES
    if body.text is not None:
        # A hand-typed caption needs no model at all, set it and return,
        # skipping every Ollama/vision-model check below.
        stripped = body.text.strip() or None
        upload.caption = stripped
        if stripped and body.source == "app":
            upload.caption_model = APP_CAPTION_AUTHOR
            upload.caption_edited = False
        elif stripped:
            # `caption_model` is left as-is: if this text started as one
            # model's caption, the badge can still credit it alongside
            # "edited" instead of losing that history the moment someone
            # fixes a typo (see MediaUpload.caption_edited's docstring).
            upload.caption_edited = True
        else:
            # Cleared back to "no caption", a full reset, not a caption
            # with nothing to show for whichever model or person last wrote one.
            upload.caption_model = None
            upload.caption_edited = False
        session.commit()
    elif not is_picture:
        #: The same document describer the attachment route uses, for the
        #: rows that arrived through `/media/upload` rather than as a note's
        #: attachment: both kinds land in the same Files sub-tab, and a
        #: button that works on one of them and 415s on the other would be
        #: the same report again from the other side.
        if upload.caption and not body.force:
            pass
        else:
            if not deps.get_ollama().is_running():
                raise HTTPException(status_code=409, detail="The AI model isn't running.")
            media_dir = deps.get_config().data_dir / "media"
            path = _within(media_dir, upload.filename)
            readable = (upload.ocr_text or "").strip() or (docview.extract(path).text or "").strip()
            if not readable:
                raise HTTPException(
                    status_code=415,
                    detail="There is no readable text in this file to describe.",
                )
            models = deps.get_model_manager()
            described = captioning.describe_document(readable, models, deps.get_ollama())
            upload.caption = described or None
            upload.caption_model = models.utility_model() if described else None
            upload.caption_edited = False
            session.commit()
    else:
        if not deps.get_ollama().is_running():
            raise HTTPException(status_code=409, detail="The AI model isn't running.")
        model = deps.get_model_manager().resolve_vision_model(deps.get_ollama())
        if not model:
            raise HTTPException(
                status_code=409,
                detail="No installed model can read images. Install or "
                "pick one in Settings, Models.",
            )
        media_dir = deps.get_config().data_dir / "media"
        captioning.caption_and_store(upload.id, media_dir / upload.filename, force=body.force)
        session.refresh(upload)
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


class OcrBody(BaseModel):
    #: A correction typed by hand instead of re-run, asked for directly
    #: ("allow the user to access, view, and edit OCR extracted text"),
    #: same "None means generate, any string sets it exactly" convention as
    #: `CaptionBody.text`. `""` clears it back to "nothing extracted",
    #: matching `ocr_text`'s own null/"not run or found nothing" meaning.
    text: str | None = Field(default=None, max_length=10_000)
    #: True only from the workspace's editor: the text is a correction the
    #: person made to the sections on screen, so those sections must stay what
    #: is shown (`_set_edited_reading`). Any other text-setting call (a
    #: fixture, a clear, an import) just replaces the stored text and lets the
    #: sections be derived again.
    edited: bool = False
    #: The local engine to read with (INBOX 717): "" for the automatic pick,
    #: or "tesseract" / "rapidocr" by name, validated like a reader.
    engine: str = Field(default="", max_length=20)


@router.post("/media/{upload_id}/ocr", response_model=MediaUploadOut)
def ocr_media(
    upload_id: int, body: OcrBody = OcrBody(), session: Session = Depends(get_session)
) -> MediaUploadOut:
    """Re-read one image with Tesseract, or, with `text`, set the
    extracted text by hand. The manual retry asked for directly: `ocr_text`
    otherwise only ever gets written once, automatically, at the moment the
    image is actually saved into a note/document/chat (`core/media_process.
    py`), this is the only way to try again (a first Tesseract pass that
    misread something, or ran before Tesseract was installed) or to correct
    what it found.

    `extract_text`/`extract_and_store` (core/ocr.py) have no write-once
    guard of their own, every call re-reads the image, which is exactly
    what "retry" needs, no `force` field required. Runs synchronously:
    local OCR is fast, and the frontend already blocks caption/vision-OCR
    regenerate behind a spinner the same way.
    """
    upload = _existing_upload(session, upload_id)
    suffix = Path(upload.filename).suffix.lower()
    is_pdf = suffix == ".pdf"
    if not is_pdf and suffix not in ocr.OCR_SUFFIXES:
        raise HTTPException(status_code=415, detail="Only images and PDFs can be read this way.")
    if body.text is not None:
        upload.ocr_text = body.text.strip() or None
        session.commit()
        if body.edited:
            _set_edited_reading(_page_read_key(None, upload.id), upload.ocr_text, "tesseract")
        else:
            _forget_regions(_page_read_key(None, upload.id))
    else:
        #: A missing engine used to come back as a 200 with no text, which the
        #: workspace painted as "Read <file>." over an empty panel. Say so.
        choice = _checked_engine(body.engine)
        reason = "" if is_pdf else ocr.unavailable_reason(choice)
        if reason:
            raise HTTPException(status_code=409, detail=reason)
        media_dir = deps.get_config().data_dir / "media"
        #: **A person pressing Read again is the one case that must read.**
        #: This called `extract_and_store`, whose guards ("once per picture",
        #: "stand down when a vision model exists") are right for the
        #: background pass after an upload and wrong here: with a reading on
        #: the row, or a model running, "Read again" did nothing at all.
        read = _local_pdf_text if is_pdf else _local_text
        text = read(media_dir / upload.filename, choice)
        if text:
            upload.ocr_text = text
            session.commit()
            _forget_regions(_page_read_key(None, upload.id))
        session.refresh(upload)
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


@media_router.get("/media/{filename}")
def get_media(filename: str, session: Session = Depends(get_session)) -> FileResponse:
    """Serve generic uploaded media.

    The suffix is checked again on the way out, not only on the way in. Upload
    is not the only route into this folder, a restored backup, a synced data
    directory, or a future writer could put something here, and this is the
    endpoint that decides what the browser executes.
    """
    name = safe_filename(filename)
    if Path(name).suffix.lower() not in MEDIA_SUFFIXES:
        raise HTTPException(status_code=404, detail="That media file could not be found.")
    path = deps.get_config().data_dir / "media" / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That media file could not be found.")
    # SEC-A2: a picture only a locked private note uses is part of that note.
    if media_gc.sealed_only(session, name):
        raise HTTPException(status_code=409, detail="Unlock first.")
    # `nosniff` is already set globally, but the header below is the one that
    # decides whether a PDF opens in the page or downloads, and an inline PDF
    # viewer is a script host. Nothing here needs to render in-place: markdown
    # embeds images with <img>, which ignores Content-Disposition.
    return FileResponse(
        path, headers={"Content-Disposition": f'inline; filename="{name}"'}
    )


# The OCR routes and their helpers live in routes_files_ocr.py (K24). Imported
# last, once everything above exists, and re-exported here because code in this
# module, routes_files_readings.py and the tests reach them as
# `routes_files.<name>`; the moved code reaches back through `rf.<name>` (bound
# below) so a patch on this module applies.
from tessellate.api.routes_files_ocr import (  # noqa: E402,F401
    _REGION_LOCKS,
    _REGION_MISSES,
    LOCAL_READERS,
    READERS,
    OcrPageReadOut,
    _checked_engine,
    _checked_reader,
    _describe_page,
    _engine_choice,
    _forget_region_misses,
    _forget_regions,
    _local_region_text,
    _local_pdf_text,
    _local_text,
    _page_read_count_map,
    _page_read_key,
    _page_read_text_map,
    _pdf_regions_for,
    _read_page,
    _reader_model,
    _region_lock,
    _regions_for,
    _reindex_file,
    _remember_page_caption,
    _remember_page_read,
    _set_edited_reading,
    _stored_page_reads,
)

#: The names above are this module's on purpose (callers, `rf.<name>` and the
#: tests' patches reach them here), so they are listed as its exports;
#: nothing star-imports this module.
__all__ = [
    "router",
    "LOCAL_READERS",
    "READERS",
    "OcrPageReadOut",
    "_checked_engine",
    "_checked_reader",
    "_describe_page",
    "_engine_choice",
    "_forget_region_misses",
    "_forget_regions",
    "_local_region_text",
    "_local_pdf_text",
    "_local_text",
    "_page_read_count_map",
    "_page_read_key",
    "_page_read_text_map",
    "_pdf_regions_for",
    "_read_page",
    "_reader_model",
    "_region_lock",
    "_regions_for",
    "_reindex_file",
    "_remember_page_caption",
    "_remember_page_read",
    "_set_edited_reading",
    "_stored_page_reads",
    "_REGION_LOCKS",
    "_REGION_MISSES",
]

from tessellate.api import routes_files_ocr as _routes_files_ocr  # noqa: E402

_routes_files_ocr.bind(sys.modules[__name__])
