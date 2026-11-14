"""OCR routes of files and media: the reading workbench's regions, page reads, readers and language.

Split out of routes_files.py (K24); mounted next to that module's router in app.py.
routes_files binds itself into `rf` below once it has loaded, so import that module, not this one.
Helpers that tests patch as `routes_files.<name>` are reached here as `rf.<name>`
(the way routes_files_readings.py does), so a patch on routes_files still applies;
routes_files re-exports them from this module at its foot.
"""

from __future__ import annotations

import contextlib
import json
import logging
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.ai import captioning, vision_ocr
from tessellate.core import activity, deps, ocr, pdfpages
from tessellate.core.database import PageRead
from tessellate.core.deps import get_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["files"])


#: `routes_files`, bound by that module at its foot (`bind`). It re-exports this
#: module, so importing it here would close an import cycle; a back-reference set
#: after both are loaded does not, and `rf.<name>` is read at call time, so a
#: test's patch of `routes_files.<name>` is what these routes see.
rf = None


def bind(module) -> None:  # noqa: ANN001
    """Called once by routes_files after it has finished loading."""
    global rf
    rf = module


class OcrRegionBox(BaseModel):
    #: Fractions of the image, top-left origin, see `ocr.extract_regions`
    #: for why these are not pixels.
    x: float
    y: float
    w: float
    h: float


class OcrWordOut(BaseModel):
    text: str
    x: float
    y: float
    w: float
    h: float


class OcrRegionOut(BaseModel):
    index: int
    #: From Tesseract: "text" or "heading" only: it reports boxes and
    #: confidences, and a semantic label guessed from box *geometry* would be a
    #: guess presented as a fact. From a reading (`ocr.regions_from_reading`),
    #: also "list", "table" and "code", because those are read off the block's
    #: own shape, pipes, bullets, a fence, which is evidence rather than
    #: inference.
    kind: str
    text: str
    confidence: float
    #: **None when nothing measured where this block sits.** A reading gives
    #: order and structure but no pixels, and a box covering the whole page
    #: would be a wrong answer rather than a missing one, the workspace can
    #: render a list without a rectangle, but it cannot un-draw a lie about
    #: where the text was.
    box: OcrRegionBox | None = None
    #: Each word and where it sits, from an optical reader only (Live Text,
    #: WORLD_CLASS_PLAN 28.4 row 7). Empty for a reading, which has no pixels,
    #: and for a cache stored before words were kept.
    words: list[OcrWordOut] = []


class OcrStoredReadingOut(BaseModel):
    #: "vision" or "tesseract": which field this is, and so which one a
    #: delete clears.
    source: str
    label: str
    text: str
    #: Whether the regions in the same answer were split from this text.
    in_regions: bool = False


def _stored_readings(
    vision_text: str | None, vision_model: str | None, tesseract_text: str | None, regions_source: str
) -> list[OcrStoredReadingOut]:
    vision = (vision_text or "").strip()
    tesseract = (tesseract_text or "").strip()
    out: list[OcrStoredReadingOut] = []
    if vision:
        out.append(
            OcrStoredReadingOut(
                source="vision",
                label=f"Read by {vision_model or 'a vision model'}",
                text=vision,
                in_regions=regions_source in {"reading", "edited-vision"},
            )
        )
    if tesseract:
        out.append(
            OcrStoredReadingOut(
                source="tesseract",
                label="Read with Tesseract OCR",
                text=tesseract,
                #: The sections are split from the vision reading when there
                #: is one (`stored` prefers it), and are Tesseract's own boxes
                #: when the source says so.
                in_regions=regions_source in {"tesseract", "edited-tesseract"}
                or (regions_source == "reading" and not vision),
            )
        )
    return out


class OcrRegionsOut(BaseModel):
    width: int
    height: int
    regions: list[OcrRegionOut]
    #: "tesseract" when the boxes are real; "reading" when they were derived
    #: from the text the vision model (or any other reader) already produced, 
    #: real blocks in real order, with no box; "none" when the page has not
    #: been read at all. The reader is told which, because a block list without
    #: boxes and a page of measured rectangles answer different questions and
    #: the UI draws them differently.
    #:
    #: "stored-text" is the retired third value: it meant "one region covering
    #: the whole page", which was a fallback that told you nothing about
    #: structure and existed only because splitting the reading had not been
    #: tried. Nothing emits it now.
    source: str
    message: str = ""
    #: How many pages this file has, when it is a document the workspace can
    #: page through (a PDF). 1 for an image, one page, no rail. The page rail
    #: is built from this rather than from a second request, because the
    #: workspace needs the count before it can draw anything at all.
    pages: int = 1
    #: Which page (0-based) these regions were read from. Echoed rather than
    #: assumed: `page` is clamped into range server-side, so a workspace that
    #: asked for page 99 of a 3-page PDF must be told which page it actually
    #: got.
    page: int = 0
    #: **Every stored reading of a picture, named by its reader** (INBOX 421
    #: e: "the text in the lightbox doesnt even appear in the ocr workspace").
    #: A picture keeps two: the vision model's and Tesseract's, separate
    #: fields, and the lightbox shows both (`lightboxReadingsFor`). The
    #: sections above come from one of them at most (`in_regions`); the
    #: workspace lists the other beside them, so the two views agree. Empty
    #: for a PDF, whose readings are per page (`PageRead`).
    readings: list[OcrStoredReadingOut] = []


#: **Reading a PDF page is rasterise-then-read, not a second OCR engine.**
#:
#: Reported: *"I begin generating ocr for a document… is the document ocr even
#: working??"* It was not, for the case that matters: `ocr.OCR_SUFFIXES` is
#: raster formats only, so both region routes below answered a PDF with 415, 
#: the workspace this feature was asked for ("for the document ocr I want smth
#: like this", three screenshots of Baidu's Unlimited-OCR) could not open a
#: document at all. Every piece needed already existed and was never joined up:
#: `core/pdfpages.py` renders a page to PNG for the lightbox, and
#: `ocr.extract_regions` reads a PNG.
def _pdf_regions_for(
    path: Path,
    index: int,
    stored_text: str,
    stored_label: str,
    key: tuple[str, int] | None = None,
    auto: bool = True,
    choice: str = "",
) -> OcrRegionsOut:
    if not pdfpages.available():
        return OcrRegionsOut(
            width=0,
            height=0,
            regions=[],
            source="none",
            pages=0,
            message=(
                "Reading a PDF page needs the small PDF rasteriser: install "
                "the “PDF pages” package in Settings, Packages."
            ),
        )
    count = pdfpages.page_count(path)
    if count <= 0:
        return OcrRegionsOut(
            width=0,
            height=0,
            regions=[],
            source="none",
            pages=0,
            message="That PDF could not be opened.",
        )
    index = max(0, min(index, count - 1))
    #: **Before the rasteriser, not after it.** `_regions_for` consults the
    #: same store, but by then this has already rendered the page to a PNG,
    #: and that render is ~20ms *serialised* behind `pdfpages`'s own lock (see
    #: that module on why the lock exists). Scrolling a long scan asks for
    #: every page it passes, so the render is the same per-look cost the
    #: reader was, on the same path, for an answer already in hand.
    cached = _stored_regions(key, index)
    if cached is not None:
        cached.pages = count
        cached.page = index
        return cached
    png = pdfpages.render_page(path, index)
    if not png:
        return OcrRegionsOut(
            width=0,
            height=0,
            regions=[],
            source="none",
            pages=count,
            page=index,
            message=f"Page {index + 1} could not be rendered.",
        )
    with tempfile.TemporaryDirectory() as tmp:
        page_path = Path(tmp) / f"page-{index}.png"
        page_path.write_bytes(png)
        #: Stored text belongs to the *document*, not to this page. Offering
        #: the whole file's reading as page 7's fallback would be the app
        #: stating a guess about where the text came from as a fact, the same
        #: line `_regions_for`'s own "stored-text" badge exists to hold.
        #: `key` and `index`, not the temporary file's path: the rasterised
        #: page lives in a directory that is deleted three lines from here, so
        #: the store has to be keyed by the page of the document it came from.
        out = rf._regions_for(
            page_path, stored_text if index == 0 else "", stored_label, key, index, auto, choice, str(path)
        )
    out.pages = count
    out.page = index
    if out.source == "none":
        #: Points at the button, not at a system package. The vision reader is
        #: named first because it is the default and the one that needs no
        #: install; Tesseract is named too, but only when it is actually here, 
        #: an app that suggests a thing you do not have is an app telling you
        #: to go and solve a problem it created (see `READERS`, and the two
        #: opposite instructions this feature has been given).
        out.message = (
            f"Nothing has been read off page {index + 1} yet. "
            "Use “Read this page” to transcribe it."
        )
        if ocr.local_available():
            out.message += (
                " Either reader works here, the AI vision model, or "
                f"{ocr.engine_name()}, which is faster and marks where each block sits."
            )
    if out.source == "stored-text":
        out.message = f"{stored_label}: this is the whole document's reading, not page {index + 1}."
    return out


#: **The regions of a page, kept, because looking is not reading.**
#:
#: Reported (INBOX 314): *"the tesseract generates it continuously not only the
#: first time or when prompted by the iser"*. Measured before it was changed,
#: with a fake reader counting its own calls (`tests/test_ocr_region_cache.py`):
#: four looks at one image ran the reader four times, and two passes over a two
#: page PDF ran it four times, because the workspace re-asks this route every
#: time the page on screen changes and scroll mode changes it on every page you
#: scroll past. Nothing was stored and nothing was consulted.
#:
#: The pair below is the whole fix: read the store first, write it after a real
#: extraction. Both are silent on failure for the same reason
#: `_remember_page_read` is: the answer reached the caller, and losing the
#: *cache* of it must never turn that into an error a reader sees.
def _stored_regions(key: tuple[str, int] | None, page: int) -> OcrRegionsOut | None:
    """What the optical reader saw on this page last time, or None."""
    if not key:
        return None
    kind, source_id = key
    try:
        with deps.get_db().session() as session:
            row = (
                session.query(PageRead.regions)
                .filter(
                    PageRead.kind == kind,
                    PageRead.source_id == source_id,
                    PageRead.page == int(page),
                )
                .one_or_none()
            )
        blob = (row[0] if row else "") or ""
        if not blob.strip():
            return None
        stored = json.loads(blob)
        out = OcrRegionsOut(**stored)
        #: **A cache stored before words were kept has boxes and no `words`
        #: key at all**, so Live Text stays empty with no reason (libr-1011
        #: row 1228). A read since then writes the key, empty or not, which is
        #: how an old cache is told from a reader that found no words. Said in
        #: the line the workspace already shows; reading again replaces it.
        if (
            out.source == "tesseract"
            and out.regions
            and not out.message
            and any("words" not in region for region in stored.get("regions", []))
        ):
            out.message = "Read this page again to select its words on the picture."
        return out
    except Exception:  # noqa: BLE001 - an unreadable cache is an empty one
        logger.debug("could not load the stored regions for a page", exc_info=True)
        return None


def _remember_regions(key: tuple[str, int] | None, page: int, out: OcrRegionsOut) -> None:
    """Store what the optical reader saw on this page, replacing any earlier copy.

    `pages` and `page` are left out of the stored body on purpose: how long the
    document is, and which page was asked for, are properties of the request
    rather than of the regions, and `_pdf_regions_for` sets both on the way
    out. Storing them would be a page count going stale in a cache.
    """
    rf._forget_region_misses(key, page)
    if not key or out.source not in {"tesseract", "edited-tesseract", "edited-vision"}:
        return
    kind, source_id = key
    try:
        body = out.model_dump(exclude={"pages", "page"})
        with deps.get_db().session() as session:
            row = (
                session.query(PageRead)
                .filter(
                    PageRead.kind == kind,
                    PageRead.source_id == source_id,
                    PageRead.page == int(page),
                )
                .one_or_none()
            )
            if row is None:
                #: A page looked at but never read is a real state: the row
                #: carries the regions and an empty `text`, which is what keeps
                #: "N pages read" honest. See `PageRead.regions`.
                row = PageRead(kind=kind, source_id=source_id, page=int(page))
                session.add(row)
            row.regions = json.dumps(body)
            session.commit()
    except Exception:  # noqa: BLE001 - a cache write must never fail a read
        logger.debug("could not store the regions for a page", exc_info=True)


def _forget_regions(
    key: tuple[str, int] | None, page: int = 0, only_source: str | None = None
) -> None:
    """Throw away the stored rectangles for a page whose text just changed.

    The cache describes the page as it was read. A re-read, or a correction
    typed by hand, makes it describe something that no longer exists, and the
    workspace would go on drawing the old reading's boxes over the new one's
    words (found driving "Read again": the second read came back as the first).
    """
    if not key:
        return
    kind, source_id = key
    try:
        with deps.get_db().session() as session:
            row = (
                session.query(PageRead)
                .filter(
                    PageRead.kind == kind,
                    PageRead.source_id == source_id,
                    PageRead.page == int(page),
                )
                .one_or_none()
            )
            if row is not None and row.regions:
                if only_source and f'"source": "{only_source}' not in row.regions:
                    return
                row.regions = ""
                session.commit()
    except Exception:  # noqa: BLE001 - a cache clear must never fail a read
        logger.debug("could not clear the stored regions for a page", exc_info=True)


def _set_edited_reading(key: tuple[str, int] | None, text: str | None, field: str) -> None:
    """A reading corrected by hand becomes what the workspace shows.

    The sections are normally *derived*: Tesseract re-reads the picture, or
    the stored text is split. A hand edit has to win over a re-derivation, or
    the person saves a correction and sees the old words come back on the next
    look (found driving the editor). So the corrected text is stored as the
    page's sections, under the source "edited", and `_regions_for` serves it
    first like any stored look. `field` ("tesseract" or "vision") says which
    stored reading was edited, so Delete and the next edit write the same one.
    Empty text is a delete, not an edit: the page goes back to unread.
    """
    if not key:
        return
    stripped = (text or "").strip()
    if not stripped:
        rf._forget_regions(key)
        return
    blocks = ocr.regions_from_reading(stripped)
    _remember_regions(
        key,
        0,
        OcrRegionsOut(
            width=0,
            height=0,
            regions=[OcrRegionOut(**block) for block in blocks],
            source=f"edited-{field}",
            message="Edited by you. Read again to replace it with a fresh reading.",
        ),
    )


def _regions_for(
    path: Path,
    stored_text: str,
    stored_label: str,
    key: tuple[str, int] | None = None,
    page: int = 0,
    auto: bool = True,
    choice: str = "",
    doc: str = "",
) -> OcrRegionsOut:
    """Region extraction with the honest fallback both callers below share.

    **Read once per page, not once per look at a page** (INBOX 314). `key` and
    `page` say which page this is, which is what makes the answer storable;
    without them (a caller that has no row to hang it on) this behaves exactly
    as it always did and reads the image every time. See `PageRead.regions` for
    why the store is a column on that table and not a reading of its own.
    """
    cached = _stored_regions(key, page)
    if cached is not None:
        return cached
    if not key:
        return _regions_read(path, stored_text, stored_label, key, page, auto, choice)
    #: **One reader per page at a time** (INBOX 1716: "request 5753ms on
    #: library: /files/4/ocr-regions"). The viewer asks again when a page
    #: changes under it, a retry or a second window asks the same page, and
    #: each ask ran Tesseract for seconds before the first had stored its
    #: answer. The later ones wait here and are served from the store.
    with rf._region_lock(key, page):
        cached = _stored_regions(key, page)
        if cached is not None:
            return cached
        #: A read that found no regions (an error, a timeout, no Tesseract) is not stored, so the asks queued behind it
        #: would each read again, one after another: they share its answer for a short while instead (keyed by the
        #: file too, so a reused row id in another notebook never sees it).
        #: Keyed by every input of the answer (the reader, `auto`, the stored text), so a different ask is never
        #: served another's miss; only a reader run is shared (`auto` off runs none: nothing to save).
        #: `doc` is the source document for a rasterised PDF page, whose `path` is a temp file new on every look.
        miss_key = (*key, page, doc or str(path), bool(auto), str(choice or ""), hash(stored_text or ""))
        missed = _REGION_MISSES.get(miss_key) if auto else None
        if missed is not None and time.monotonic() - missed[0] < REGION_MISS_FOR:
            #: A copy: callers set `pages`, `page` and `message` on what they get, concurrently.
            return missed[1].model_copy(deep=True)
        out = _regions_read(path, stored_text, stored_label, key, page, auto, choice)
        if auto and _stored_regions(key, page) is None:
            _prune_region_misses()
            _REGION_MISSES[miss_key] = (time.monotonic(), out.model_copy(deep=True))
        else:
            _REGION_MISSES.pop(miss_key, None)
        return out


REGION_MISS_FOR = 30.0
_REGION_MISSES: dict[tuple, tuple[float, OcrRegionsOut]] = {}


def _prune_region_misses() -> None:
    """Drop the expired shares, so the dict holds only the last 30 s of misses, never one per page ever asked."""
    now = time.monotonic()
    for k in [k for k, (at, _) in _REGION_MISSES.items() if now - at >= REGION_MISS_FOR]:
        _REGION_MISSES.pop(k, None)


def _forget_region_misses(key: tuple[str, int] | None, page: int) -> None:
    """A reading stored for this page ends any miss shared for it (the next ask reads the store, not "not read yet")."""
    if not key:
        return
    for k in [k for k in _REGION_MISSES if k[:3] == (*key, page)]:
        _REGION_MISSES.pop(k, None)


_REGION_LOCKS: dict[tuple[str, int, int], list] = {}
_REGION_LOCKS_GUARD = threading.Lock()


@contextlib.contextmanager
def _region_lock(key: tuple[str, int], page: int):
    """The page's lock, held for the block; the entry goes when its last user leaves, so the dict
    holds only pages being read now, never one per page ever asked."""
    slot = (key[0], key[1], int(page))
    with _REGION_LOCKS_GUARD:
        entry = _REGION_LOCKS.setdefault(slot, [threading.Lock(), 0])
        entry[1] += 1
    try:
        with entry[0]:
            yield
    finally:
        with _REGION_LOCKS_GUARD:
            entry[1] -= 1
            if entry[1] <= 0:
                _REGION_LOCKS.pop(slot, None)


def _regions_read(
    path: Path,
    stored_text: str,
    stored_label: str,
    key: tuple[str, int] | None,
    page: int,
    auto: bool,
    choice: str,
) -> OcrRegionsOut:
    #: **Nothing stored and nobody asked: read nothing.** The owner, 2026-09-21:
    #: "I want to be able to disable tesseract in the ocr workspace, or if I am
    #: not selected on tesseract and am instead selected on the ocr model, then
    #: tesseract wont activate. I want tesseract to work once and then not alter
    #: what is generated after that unless the user selects an option."
    #:
    #: Storing the answer (above) stopped the *repeat* reads, but a first look
    #: at a page still ran Tesseract whether or not it was the reader the person
    #: had chosen, which is how a page they meant to read with the vision model
    #: came back transcribed by the other one. `auto` is false whenever the
    #: workspace's reader is not Tesseract, and then this returns the honest
    #: empty answer and the "use Read this page" message with it.
    #:
    #: **Not reading is not the same as not showing** (INBOX 421 e). This
    #: used to return the empty answer outright, which skipped the stored
    #: reading below as well as Tesseract: with the vision model chosen (the
    #: owner's setting) a picture the model had already read opened on an
    #: empty panel while the lightbox showed its text. Only the read is
    #: skipped now; what is stored still becomes the sections.
    found = _local_regions(path, choice) if auto else None
    if found is not None:
        out = OcrRegionsOut(
            width=found["width"],
            height=found["height"],
            regions=[OcrRegionOut(**region) for region in found["regions"]],
            source="tesseract",
            message="" if found["regions"] else "No text was found on this page.",
        )
        #: Stored even when it found nothing: "this page was looked at and had
        #: no text on it" is an answer, and re-running the reader on every
        #: later look to be told the same thing is the cost this exists to
        #: remove. A real read of the page clears it (`_remember_page_read`).
        _remember_regions(key, page, out)
        return out
    text = (stored_text or "").strip()
    if not text:
        return OcrRegionsOut(
            width=0,
            height=0,
            regions=[],
            source="none",
            message=(
                "This page hasn't been read yet, read it and its sections "
                "will appear here."
            ),
        )
    #: **The page was read; split what it said.** Reported as "the regions
    #: dont work without tesseract but surely there's a better way", and there
    #: is: the vision model is this app's primary reader and it returns the
    #: page in order with its structure intact, so the blocks are already
    #: there: only the rectangles are missing. `regions_from_reading` types
    #: them from their own shape and numbers them, which is what makes "this
    #: text came from section 4 of page 2" answerable with nothing installed.
    blocks = ocr.regions_from_reading(text)
    #: **Worded by whether Tesseract is actually missing** (INBOX 423d). This
    #: always said "Install Tesseract", even when it was already on the
    #: machine and simply was not the reader that produced this text (the
    #: vision model is the default reader, so that is the common case, not
    #: the rare one): a program you already have does not need installing,
    #: it needs choosing. `ocr.local_available()` is the same check the
    #: "nothing read yet" message above already makes before naming it, and
    #: the engine is named as it is (Tesseract, or RapidOCR where Tesseract is
    #: not ready).
    positions_offer = (
        "Install Tesseract or RapidOCR to also see where each one sits on the page."
        if not ocr.local_available()
        #: The local reader was the reader and still placed nothing: telling
        #: the person to switch to what they already chose sent them in a circle.
        else f"{ocr.engine_name()} could not mark where each one sits on this page."
        if auto
        else f"Switch to {ocr.engine_name()} as the reader to also see where each one sits on the page."
    )
    return OcrRegionsOut(
        width=0,
        height=0,
        regions=[OcrRegionOut(**block) for block in blocks],
        source="reading",
        message=f"{stored_label}: sections come from the reading itself. {positions_offer}",
    )


@router.get("/media/{upload_id}/ocr-regions", response_model=OcrRegionsOut)
def media_ocr_regions(
    upload_id: int,
    page: int = 0,
    auto: bool = True,
    engine: str = "",
    session: Session = Depends(get_session),
) -> OcrRegionsOut:
    """The page, region by region, what the OCR workspace draws its boxes
    from. Asked for with three screenshots of Baidu's Unlimited-OCR: a page
    beside its regions, each separately readable, instead of one wall of
    text with no way to tell which part of the page a line came from."""
    upload = rf._existing_upload(session, upload_id)
    suffix = Path(upload.filename).suffix.lower()
    if suffix not in ocr.OCR_SUFFIXES and suffix != ".pdf":
        raise HTTPException(status_code=415, detail="Only images and PDFs can be read this way.")
    path = rf._within(deps.get_config().data_dir / "media", upload.filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That file is no longer on disk.")
    stored = (upload.vision_ocr_text or upload.ocr_text or "")
    label = (
        f"Read by {upload.vision_ocr_model or 'a vision model'}"
        if upload.vision_ocr_text
        else "Text already extracted from this file"
    )
    key = rf._page_read_key(None, upload_id)
    if suffix == ".pdf":
        return rf._pdf_regions_for(path, page, stored, label, key, auto, rf._checked_engine(engine))
    #: An image is a one page document, and page 0 is where its regions go.
    out = rf._regions_for(path, stored, label, key, 0, auto, rf._checked_engine(engine))
    out.readings = _stored_readings(upload.vision_ocr_text, upload.vision_ocr_model, upload.ocr_text, out.source)
    return out


@router.get("/files/{attachment_id}/ocr-regions", response_model=OcrRegionsOut)
def attachment_ocr_regions(
    attachment_id: int,
    page: int = 0,
    auto: bool = True,
    engine: str = "",
    session: Session = Depends(get_session),
) -> OcrRegionsOut:
    """`media_ocr_regions`'s sibling for an attached file. Two tables, two
    routes: the same split every other file endpoint in this module has."""
    attachment = rf._existing_attachment(session, attachment_id)
    suffix = Path(attachment.filename).suffix.lower()
    if suffix not in ocr.OCR_SUFFIXES and suffix != ".pdf":
        raise HTTPException(status_code=415, detail="Only images and PDFs can be read this way.")
    path = rf._within(deps.get_config().uploads_dir, attachment.stored_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That file is no longer on disk.")
    stored = (attachment.vision_ocr_text or attachment.ocr_text or "")
    label = (
        f"Read by {attachment.vision_ocr_model or 'a vision model'}"
        if attachment.vision_ocr_text
        else "Text already extracted from this file"
    )
    key = rf._page_read_key(attachment_id, None)
    if suffix == ".pdf":
        return rf._pdf_regions_for(path, page, stored, label, key, auto, rf._checked_engine(engine))
    out = rf._regions_for(path, stored, label, key, 0, auto, rf._checked_engine(engine))
    out.readings = _stored_readings(
        attachment.vision_ocr_text, attachment.vision_ocr_model, attachment.ocr_text, out.source
    )
    return out


class OcrPageReadOut(BaseModel):
    """One page of a document, read by a vision model."""

    page: int
    text: str = ""
    model: str = ""
    message: str = ""
    #: **What the figures on this page show**, a different claim from `text`,
    #: which is what the page *says*. Asked for directly: "image captioning,
    #: how it is done and displayed needs to be refined for pdf documents and
    #: other similar documents. with graphs, images and diagrams in them."
    #:
    #: On this model rather than in a separate response so the workspace and
    #: the lightbox render a page's reading and its description from one
    #: object; `""` when the page has never been described, which is the
    #: ordinary case and not an error. Same never-null convention the rest of
    #: this module keeps.
    caption: str = ""
    caption_model: str = ""
    #: **What an optical reader saw on this page while it was on screen**, as
    #: plain text, and a different claim again from `text`.
    #:
    #: Reported (INBOX 314): *"I can only view the extracted text on a single
    #: page"*. The reading panel lists one section per page of the document, and
    #: it could only list pages with a stored *reading*: a scan being read by
    #: Tesseract as you scroll has no reading of any page, so the panel held
    #: whichever page was on screen and nothing else, which is also why
    #: clicking a section could not take you to another page. This carries
    #: those pages, so the panel can list them without any of them claiming to
    #: be a transcription somebody asked for. See `PageRead.regions`.
    regions_text: str = ""


#: **A vision read scoped to the page you are looking at.**
#:
#: The existing vision path (`analyse`, kind="vision") reads a whole PDF, up
#: to `pdfpages.MAX_PAGES`, and stores one blob. That is the right shape for
#: "what is this document"; it is the wrong shape for the OCR workspace, where
#: the question is always "what does *this page* say" and a reader who wants
#: page 6 should not wait through five pages they have already checked.
#:
#: Nothing is stored: the workspace shows the reading beside the page and the
#: reader decides what to keep (Copy, Save to a note, or Save the reading onto
#: the file through the existing analyse endpoint). Reading is cheap to repeat
#: and a wrong transcription written onto the row is not.
def _reader_model(reader: str) -> str:
    """The model the named reader will actually use, or "" if there is none.

    One function so the picker (`ocr_readers`) and the read (`_vision_read_page`)
    cannot answer this differently, which is exactly what they did before, and
    is why "my ocr model shows as a vision model" survived a first fix.
    """
    manager = deps.get_model_manager()
    ollama = deps.get_ollama()
    if reader == "ocr":
        # The general "can anything here see an image" resolver. Named `ocr`
        # only because it is the *other* one from the workspace's default;
        # what it returns is whatever vision model the app would otherwise use.
        return manager.resolve_vision_model(ollama) or ""
    return manager.resolve_ocr_model(ollama) or ""


def _vision_read_page(path: Path, index: int, reader: str = "vision") -> OcrPageReadOut:
    if not pdfpages.available():
        return OcrPageReadOut(
            page=index,
            message=(
                "Reading a PDF page needs the small PDF rasteriser: install "
                "the “PDF pages” package in Settings, Packages."
            ),
        )
    if not deps.get_ollama().is_running():
        raise HTTPException(status_code=409, detail="The AI model isn't running.")
    model = rf._reader_model(reader)
    if not model:
        raise HTTPException(
            status_code=409,
            detail="No installed model can read images. Install or "
            "pick one in Settings, Models.",
        )
    count = pdfpages.page_count(path)
    if count <= 0:
        return OcrPageReadOut(page=index, message="That PDF could not be opened.")
    index = max(0, min(index, count - 1))
    png = pdfpages.render_page(path, index)
    if not png:
        return OcrPageReadOut(page=index, message=f"Page {index + 1} could not be rendered.")
    with tempfile.TemporaryDirectory(prefix="mm-pageocr-") as scratch:
        page_path = Path(scratch) / f"page-{index}.png"
        page_path.write_bytes(png)
        text = vision_ocr.vision_ocr_text(page_path, model, deps.get_ollama()) or ""
    return OcrPageReadOut(
        page=index,
        text=text.strip(),
        model=model if text.strip() else "",
        message="" if text.strip() else f"{model} found no text on page {index + 1}.",
    )


#: **The two readers, and why both exist.**
#:
#: This project was told, twice, in opposite directions. First: *"I basically
#: dont want to download tesseract and only want to use an ai vision learning
#: and ocr model for images and scanned documents"*, which is why every read
#: path here defaults to a vision model and why `core/pdfpages.py` exists at
#: all. Then, later and just as directly: *"make sure tesseract exists as an
#: alternative as well."*
#:
#: Both are satisfiable because they are not the same claim. The vision model
#: is the *default*; Tesseract is an *alternative you can pick*, and it is a
#: genuinely better answer for some work: it needs no model running, it reads a
#: page in about a tenth of a second rather than several seconds, it never
#: invents words that were not on the page (the failure `VisionOcrBody.text`
#: exists to let you correct), and it returns *where* each block sits, which a
#: vision model cannot. It is also the only reader that works with no GPU and
#: no model installed at all.
#:
#: Neither is silently substituted for the other: the reader that produced a
#: reading is named in the response, and a request for one that is not
#: installed says so rather than quietly answering with the other.
#: **Three, not two, because "the AI" was hiding two different models.**
#: Reported: *"in the ocr workspace, my ocr model shows as a vision model and
#: my actual vision model doesnt appear as an option at all."* Exactly right.
#: `resolve_ocr_model` prefers a dedicated document reader (GLM-OCR,
#: DeepSeek-OCR, PaddleOCR-VL) and falls back to a general vision model;
#: `resolve_vision_model` answers "can anything here see an image". On a
#: machine with both installed they return different models, and the
#: workspace offered one option, labelled "AI vision model", which named
#: whichever of the two the picker happened to resolve. The other model was
#: unreachable from the UI entirely.
#:
#: Worse, the two halves disagreed: `ocr_readers` was fixed to call
#: `resolve_ocr_model` and `_vision_read_page` was left calling
#: `resolve_vision_model`, so the picker could name one model and the read use
#: the other. That is the same "fixed at one of two call sites" shape this
#: repo keeps hitting, and it is why the report came back after the first fix.
#:
#: So each resolver gets its own reader name and its own option, and the read
#: uses the resolver its name promises. `"vision"` keeps meaning "the app's
#: default choice" for every existing caller and stored preference, it maps
#: to `resolve_ocr_model`, which is what a read has always actually done.
#: **RapidOCR by name** (INBOX 717, the owner: "does the ocr worspace give
#: rapidocr as an alternative??"). It was only ever the silent stand-in when
#: Tesseract was not ready. `"tesseract"` stays the local reader's id with the
#: automatic pick behind it (Tesseract when ready, else RapidOCR), because
#: stored readings and every older caller say it; `"rapidocr"` reads with
#: RapidOCR even when Tesseract is ready, and is refused when it is missing.
READERS = ("vision", "ocr", "tesseract", "rapidocr")
LOCAL_READERS = ("tesseract", "rapidocr")


def _checked_reader(reader: str) -> str:
    """400 on an unknown reader rather than silently using the default.

    A typo'd `?reader=tesserract` that quietly ran the vision model would
    charge a reader seconds of GPU time for a request they meant to be
    instant, and tell them Tesseract had done it. A named engine that is not
    installed is refused the same way, with the reason, rather than read by
    another one under its name.
    """
    name = (reader or "vision").strip().lower()
    if name not in rf.READERS:
        raise HTTPException(
            status_code=400,
            detail=f"Pick one of these readers: {', '.join(rf.READERS)}.",
        )
    if name == "rapidocr" and not ocr.rapidocr_available():
        raise HTTPException(status_code=400, detail=ocr.unavailable_reason("rapidocr"))
    return name


def _engine_choice(reader: str) -> str:
    """The `core.ocr` engine choice a local reader name stands for: `""` (the
    automatic pick) for "tesseract", the engine itself for "rapidocr"."""
    return "rapidocr" if reader == "rapidocr" else ""


def _checked_engine(engine: str) -> str:
    """The `?engine=` of a first look at a page: empty (automatic), or one of
    the local engines, validated like a reader."""
    name = (engine or "").strip().lower()
    if not name:
        return ""
    if name not in ocr.LOCAL_ENGINES:
        raise HTTPException(
            status_code=400,
            detail=f"Pick one of these engines: {', '.join(ocr.LOCAL_ENGINES)}.",
        )
    if name == "rapidocr" and not ocr.rapidocr_available():
        raise HTTPException(status_code=400, detail=ocr.unavailable_reason("rapidocr"))
    return "rapidocr" if name == "rapidocr" else ""


def _local_text(path: Path, choice: str = "") -> str:
    """`ocr.extract_text`, naming the engine only when one was chosen (a fake
    in a test, or an older caller, takes the path alone)."""
    with activity.track("ocr", "Reading text from a picture", stoppable=False):
        return ocr.extract_text(path, choice) if choice else ocr.extract_text(path)


def _local_pdf_text(path: Path, choice: str = "") -> str:
    """An uploaded PDF read without a model (L631): its text layer when it has
    one, else its first pages drawn to pictures and read with the chosen OCR
    engine. Raises 409 with a plain reason when neither can be done, so the
    caller never shows an empty panel as if the PDF had no words."""
    from tessellate.core import docview

    text = (docview.extract(path).text or "").strip()
    if text:
        return text
    if not pdfpages.available():
        raise HTTPException(
            status_code=409,
            detail="This PDF has no text layer, and reading its pages needs the PDF viewer extra. Install it in Settings, then try again.",
        )
    if reason := ocr.unavailable_reason(choice):
        raise HTTPException(status_code=409, detail=reason)
    out: list[str] = []
    with tempfile.TemporaryDirectory(prefix="mm-pdfocr-") as scratch:
        for number, png in enumerate(pdfpages.render_pages(path), start=1):
            page_path = Path(scratch) / f"page-{number:03d}.png"
            page_path.write_bytes(png)
            if page_text := _local_text(page_path, choice).strip():
                out.append(page_text)
    return "\n\n".join(out)


def _local_region_text(path: Path, choice: str = "") -> str:
    """`ocr.extract_region_text`: a crop is read as one block (INBOX 1568)."""
    with activity.track("ocr", "Reading text from a picture", stoppable=False):
        return ocr.extract_region_text(path, choice)


def _local_regions(path: Path, choice: str = "") -> dict | None:
    """`ocr.extract_regions`, the same way as `_local_text`."""
    return ocr.extract_regions(path, choice) if choice else ocr.extract_regions(path)


def _page_read_key(attachment_id: int | None, upload_id: int | None) -> tuple[str, int] | None:
    """Which id space this read belongs to. See `PageRead` on why both."""
    if attachment_id is not None:
        return ("attachment", int(attachment_id))
    if upload_id is not None:
        return ("upload", int(upload_id))
    return None


def _remember_page_read(key: tuple[str, int] | None, result: OcrPageReadOut, reader: str) -> None:
    """Store one page's reading, replacing any earlier one for the same page.

    Silent on failure and never raises: a reading that reached the caller is a
    success, and losing the *cache* of it must not turn that into an error the
    reader sees. Empty readings are not stored, "the model found nothing on
    page 4" is not a transcription, and storing it would stop a later, better
    reader from being asked.
    """
    if not key or not (result.text or "").strip():
        return
    rf._forget_region_misses(key, int(result.page))
    kind, source_id = key
    try:
        with deps.get_db().session() as session:
            row = (
                session.query(PageRead)
                .filter(
                    PageRead.kind == kind,
                    PageRead.source_id == source_id,
                    PageRead.page == int(result.page),
                )
                .one_or_none()
            )
            if row is None:
                row = PageRead(kind=kind, source_id=source_id, page=int(result.page))
                session.add(row)
            row.reader = reader
            row.model = result.model or ""
            row.text = result.text
            #: **The regions cache belongs to the page as it was read.** A
            #: fresh reading of this page replaces what the app knows about it,
            #: so the stored rectangles from the previous look are thrown away
            #: rather than left to describe a reading that no longer exists
            #: (INBOX 314). The next look re-reads the page once and stores
            #: that. Deleting a reading takes the whole row, so it needs no
            #: invalidation of its own.
            row.regions = ""
            row.created_at = datetime.now(timezone.utc)
            session.flush()
            rf._reindex_file(session, kind, source_id)
            #: Explicit: `DatabaseManager.session()` hands back a bare Session,
            #: and `with` on one closes it without committing, the whole point
            #: of this table is that the reading outlives the request.
            session.commit()
    except Exception:  # noqa: BLE001 - a cache write must never fail a read
        logger.debug("could not store the page reading", exc_info=True)


def _reindex_file(session, kind: str, source_id: int) -> None:  # noqa: ANN001
    """A page's words are the file's words (F10): put them in its index row.

    `page_reads` is not a model the index's flush hook watches, so a page read
    in the OCR workspace was never findable by search; the file's row is
    re-read here, in the same transaction as the reading it now carries.
    """
    from tessellate.search import index as search_index

    source = {"attachment": "attachments", "upload": "media"}.get(kind)
    if source is None:
        return
    try:
        search_index.touch(session, source, int(source_id))
    except Exception:  # noqa: BLE001  # the reading is kept even if the index is not
        logger.debug("could not re-index a file after a page reading", exc_info=True)


def _remember_page_caption(key: tuple[str, int] | None, page: int, caption: str, model: str) -> None:
    """Store one page's description, beside that page's reading.

    A near-twin of `_remember_page_read` above, and separate from it on
    purpose: a page can be described without being transcribed and transcribed
    without being described, so neither may touch the other's columns. Folding
    them into one function with optional arguments is how a describe call ends
    up quietly clearing a reading that took a minute of GPU time to produce.

    Silent on failure and never raises, same contract: a description that
    reached the caller is a success, and losing the *cache* of it must not turn
    that into an error the reader sees.
    """
    if not key or not (caption or "").strip():
        return
    kind, source_id = key
    try:
        with deps.get_db().session() as session:
            row = (
                session.query(PageRead)
                .filter(
                    PageRead.kind == kind,
                    PageRead.source_id == source_id,
                    PageRead.page == int(page),
                )
                .one_or_none()
            )
            if row is None:
                #: A page described but never read is a real state, the whole
                #: point of this being its own column, so the row is created
                #: here rather than requiring a reading to exist first.
                row = PageRead(kind=kind, source_id=source_id, page=int(page))
                session.add(row)
            row.caption = caption.strip()
            row.caption_model = model or ""
            session.flush()
            rf._reindex_file(session, kind, source_id)
            session.commit()
    except Exception:  # noqa: BLE001 - a cache write must never fail a describe
        logger.debug("could not store the page description", exc_info=True)


def _page_read_text_map(kind: str, ids: list[int]) -> dict[int, str]:
    """The joined per-page reading for each of `ids`, page order, one query.

    **Why a list endpoint needs this at all.** Reported: "the extracted ocr for
    files doesnt actually appear in the file rows in the files library subtab".
    A whole-file reading is stored on the row itself (`vision_ocr_text`); a PDF
    read *page by page* in the OCR workspace is stored as `PageRead` rows
    instead, and nothing joined the two, so a document with every page read
    still said "No text yet" everywhere outside the workspace, including to
    anyone scanning the library for it.

    One grouped query rather than one per row: these endpoints render whole
    galleries, and the same lookup done per row is the N+1 that makes a library
    of a hundred files feel broken.
    """
    #: `kind` is the same vocabulary `_page_read_key` writes: "attachment" for
    #: a file hanging off a note, "upload" for one in the media gallery. Using
    #: the route prefixes ("file"/"media") here instead would match no rows at
    #: all and fail silently, which is the shape this join exists to fix.
    if not ids:
        return {}
    try:
        with deps.get_db().session() as session:
            rows = (
                session.query(PageRead)
                .filter(PageRead.kind == kind, PageRead.source_id.in_(ids))
                .order_by(PageRead.source_id.asc(), PageRead.page.asc())
                .all()
            )
    except Exception:  # noqa: BLE001 - an unreadable cache is an empty one
        logger.debug("could not load stored page readings for a list", exc_info=True)
        return {}
    out: dict[int, list[str]] = {}
    for row in rows:
        text = (row.text or "").strip()
        if text:
            out.setdefault(row.source_id, []).append(text)
    #: A form feed between pages: the Files row draws a "Page N" mark at each (the one reader of this map).
    return {source_id: "\n\n\f\n\n".join(parts) for source_id, parts in out.items()}


def _page_read_count_map(kind: str, ids: list[int]) -> dict[int, int]:
    """How many pages of each file have a stored reading, one query.

    **Why the count and not just the text.** UI_MODERNISATION_PLAN Phase 7.5:
    "OCR text for a long document does not fit where a photo's caption fits.
    The Files row shows a one-line summary (first sentence / N pages read / N
    words)". The joined text is already carried (`_page_read_text_map`), but
    counting pages out of it means splitting a string on a separator and
    hoping: a reading that happens to contain a blank line would be counted
    as two pages.

    A count of rows rather than of distinct pages, because `(kind, source_id,
    page)` is unique on this table: re-reading a page replaces its row, so
    there is exactly one row per page that has ever been read.
    """
    if not ids:
        return {}
    try:
        with deps.get_db().session() as session:
            rows = (
                session.query(PageRead.source_id, PageRead.text)
                .filter(PageRead.kind == kind, PageRead.source_id.in_(ids))
                .all()
            )
    except Exception:  # noqa: BLE001 - an unreadable cache is an empty one
        logger.debug("could not count stored page readings for a list", exc_info=True)
        return {}
    counts: dict[int, int] = {}
    for source_id, text in rows:
        #: Only pages with a *reading*. A page that has only been described
        #: (Phase 7.3) has a row here too, and counting it would tell the row
        #: that a transcription exists where none does.
        if (text or "").strip():
            counts[source_id] = counts.get(source_id, 0) + 1
    return counts


def _regions_text(blob: str | None) -> str:
    """The stored regions of one page as plain text, blocks in reading order.

    The blocks are joined with a blank line between them rather than a newline:
    they are separate blocks on the page, and running them together would make
    a heading and the paragraph under it look like one sentence.
    """
    if not (blob or "").strip():
        return ""
    try:
        found = json.loads(blob)
        parts = [(region.get("text") or "").strip() for region in found.get("regions") or []]
    except Exception:  # noqa: BLE001 - an unreadable cache is an empty one
        logger.debug("could not read the stored regions of a page", exc_info=True)
        return ""
    return "\n\n".join(part for part in parts if part)


def _stored_page_reads(key: tuple[str, int] | None) -> list[OcrPageReadOut]:
    """Every page of this document that has already been read, oldest page first."""
    if not key:
        return []
    kind, source_id = key
    try:
        with deps.get_db().session() as session:
            rows = (
                session.query(PageRead)
                .filter(PageRead.kind == kind, PageRead.source_id == source_id)
                .order_by(PageRead.page.asc())
                .all()
            )
            pages = [
                OcrPageReadOut(
                    page=row.page,
                    text=row.text or "",
                    model=row.model or "",
                    caption=row.caption or "",
                    caption_model=row.caption_model or "",
                    regions_text=_regions_text(row.regions),
                )
                for row in rows
            ]
            #: A row with nothing on it is one this table keeps for its own
            #: bookkeeping, not a page the workspace has anything to say about.
            #: Filtered here rather than in each caller: "already read" has
            #: three callers and they must not be able to disagree about it.
            return [
                page
                for page in pages
                if page.text.strip() or page.caption.strip() or page.regions_text.strip()
            ]
    except Exception:  # noqa: BLE001 - an unreadable cache is an empty one
        logger.debug("could not load stored page readings", exc_info=True)
        return []


def _read_page(
    path: Path,
    index: int,
    reader: str,
    key: tuple[str, int] | None = None,
) -> OcrPageReadOut:
    """One page, by whichever reader was asked for.

    Registered in `vision_ocr`'s running-reads list for the length of the call,
    which is what puts it in Settings, Background tasks. Asked for directly:
    "make sure eveyrhting appears in the bg processes in settings." A read is a
    model round-trip of several seconds and it appeared there nowhere, so
    closing the workspace mid-read left no sign anywhere that the app was still
    working.

    Here rather than in either reader, and here rather than in the two
    endpoints: `_read_range` loops over this function, so a range read shows up
    as its pages complete, which is also the only progress a range read has to
    report.
    """
    local = reader in rf.LOCAL_READERS
    token = vision_ocr.register_page_read(
        f"Reading page {index + 1} of {path.name}",
        model=ocr.engine_name(rf._engine_choice(reader)) if local else "",
    )
    try:
        result = (
            _tesseract_read_page(path, index, rf._engine_choice(reader))
            if local
            else _vision_read_page(path, index, reader)
        )
        #: Stored as each page completes, not once the whole range is done:
        #: the point is that a read which finishes after the workspace has been
        #: closed is not lost, and a range read that is interrupted half way
        #: should keep the half it managed. See `PageRead`. A local reading is
        #: stored under the local reader's id, "tesseract", whichever engine
        #: ran; `model` says which one did (INBOX 717).
        rf._remember_page_read(key, result, "tesseract" if local else reader)
        return result
    finally:
        vision_ocr.finish_page_read(token)


def _describe_page(
    path: Path,
    index: int,
    key: tuple[str, int] | None = None,
) -> OcrPageReadOut:
    """Describe one page's figures with a vision model, and store the answer.

    Deliberately the same envelope (`OcrPageReadOut`) as a page *read*: the two
    are the two halves of "what is on page 4", the workspace renders them in
    one panel, and a second response shape would be a second renderer that can
    drift from it: the mistake `_stored_range`'s own docstring records.

    `resolve_vision_model`, not `resolve_ocr_model`: describing a figure is the
    general "can anything here see an image" job, and a dedicated document
    reader (GLM-OCR and friends) is tuned to transcribe, not to explain. That
    is also the distinction the reader picker draws between its two AI options
    - see `READERS` above.
    """
    if not pdfpages.available():
        return OcrPageReadOut(
            page=index,
            message=(
                "Describing a PDF page needs the small PDF rasteriser: install "
                "the “PDF pages” package in Settings, Packages."
            ),
        )
    if not deps.get_ollama().is_running():
        raise HTTPException(status_code=409, detail="The AI model isn't running.")
    model = deps.get_model_manager().resolve_vision_model(deps.get_ollama()) or ""
    if not model:
        raise HTTPException(
            status_code=409,
            detail="No installed model can read images. Install or "
            "pick one in Settings, Models.",
        )
    count = pdfpages.page_count(path)
    if count <= 0:
        return OcrPageReadOut(page=index, message="That PDF could not be opened.")
    index = max(0, min(index, count - 1))
    png = pdfpages.render_page(path, index)
    if not png:
        return OcrPageReadOut(page=index, message=f"Page {index + 1} could not be rendered.")
    #: Registered in the same running-reads list a page read uses, so a
    #: describe shows up in Settings, Background tasks like everything else, 
    #: "make sure eveyrhting appears in the bg processes in settings."
    token = vision_ocr.register_page_read(f"Describing page {index + 1} of {path.name}", model=model)
    try:
        with tempfile.TemporaryDirectory(prefix="mm-pagecap-") as scratch:
            page_path = Path(scratch) / f"page-{index}.png"
            page_path.write_bytes(png)
            caption = captioning.page_caption_text(
                page_path, index, count, model, deps.get_ollama()
            )
    finally:
        vision_ocr.finish_page_read(token)
    caption = (caption or "").strip()
    rf._remember_page_caption(key, index, caption, model)
    return OcrPageReadOut(
        page=index,
        caption=caption,
        caption_model=model if caption else "",
        message="" if caption else f"{model} had nothing to say about page {index + 1}.",
    )


def _tesseract_read_page(path: Path, index: int, choice: str = "") -> OcrPageReadOut:
    """Rasterise one PDF page and read it with Tesseract.

    Same shape as `_vision_read_page` on purpose: the caller should not have
    to know which reader it asked for to understand the answer. `model` carries
    the reader's name for the same reason the vision path puts the model's name
    there: the workspace prints *who read this*, and "a vision model" and
    "Tesseract" are different enough claims that the difference must survive
    the round trip.
    """
    if not pdfpages.available():
        return OcrPageReadOut(
            page=index,
            message=(
                "Reading a PDF page needs the small PDF rasteriser: install "
                "the “PDF pages” package in Settings, Packages."
            ),
        )
    reason = ocr.unavailable_reason(choice)
    if reason:
        raise HTTPException(status_code=409, detail=reason)
    count = pdfpages.page_count(path)
    if count <= 0:
        return OcrPageReadOut(page=index, message="That PDF could not be opened.")
    index = max(0, min(index, count - 1))
    png = pdfpages.render_page(path, index)
    if not png:
        return OcrPageReadOut(page=index, message=f"Page {index + 1} could not be rendered.")
    with tempfile.TemporaryDirectory(prefix="mm-pagetess-") as scratch:
        page_path = Path(scratch) / f"page-{index}.png"
        page_path.write_bytes(png)
        text = (rf._local_text(page_path, choice) or "").strip()
    #: The engine that read it, not the reader's id: the automatic pick can be
    #: RapidOCR, and a chosen RapidOCR always is (INBOX 717).
    engine = ocr.engine(choice) or "tesseract"
    return OcrPageReadOut(
        page=index,
        text=text,
        model=engine if text else "",
        message="" if text else f"{ocr.engine_name(choice)} found no text on page {index + 1}.",
    )


class OcrReadersOut(BaseModel):
    """Which readers this machine can actually use, right now.

    The workspace asks before it offers: a picker whose second entry always
    fails is worse than no picker, and "install Tesseract" is a real, one-click
    answer this app already knows how to give (`core/extras.py`).
    """

    #: The reader used when nothing is chosen.
    default: str = "vision"
    tesseract: bool = False
    vision: bool = False
    #: The model that would answer for the *default* reader, so the picker can
    #: name it rather than saying "a vision model" and leaving you to go and
    #: look. This is `resolve_ocr_model`: a dedicated document reader if one is
    #: installed, else the general vision model.
    vision_model: str = ""
    #: Why the default reader is unavailable, when it is, "the model isn't
    #: running" and "nothing installed can see images" need different fixes.
    vision_reason: str = ""
    #: The *other* model: what `resolve_vision_model` returns. Offered as its
    #: own reader whenever it differs from `vision_model`, because a machine
    #: with both GLM-OCR and Qwen-VL installed has two genuinely different
    #: readers and the workspace used to expose only one of them under a label
    #: that named the other. Empty when there is no second choice to make.
    ocr: bool = False
    ocr_model: str = ""
    ocr_reason: str = ""
    #: The Tesseract engine in full (`ocr.engine_status`): both halves, the
    #: version, the language packs and the one in use, and the one fix. The
    #: workspace's status line and Settings' Packages row read the same
    #: object, so they cannot disagree about what is installed.
    engine: dict = {}


@router.get("/ocr-readers", response_model=OcrReadersOut)
def ocr_readers() -> OcrReadersOut:
    """What can read a page here, asked by the workspace's reader picker.

    Reported directly: "I can only select the vision models not OCR
    models." This called `resolve_vision_model`, the same, name-agnostic
    "can anything here see an image" resolver `/models/vision-model` uses: 
    so the picker always described whatever generic vision model
    auto-detect happened to find first, never the dedicated document
    reader (GLM-OCR/DeepSeek-OCR/PaddleOCR-VL) an explicit `ocr_model`
    preference names, even though the actual read (`routes_files.py`'s own
    page-read endpoint) already calls `resolve_ocr_model` and gets it
    right. The picker's own idea of "which model" just never matched what
    a read would actually use."""
    ollama = deps.get_ollama()
    running = ollama.is_running()
    model = rf._reader_model("vision") if running else ""
    other = rf._reader_model("ocr") if running else ""
    if not running:
        reason = "The AI model isn't running."
    elif not model:
        reason = "No installed model reports it can see images."
    else:
        reason = ""
    #: Only when it is a genuinely *different* model. On the common machine
    #: with one vision model both resolvers return it, and offering the same
    #: model twice under two names is a worse picker than offering it once.
    second = other if (other and other != model) else ""
    engine = ocr.engine_status()
    return OcrReadersOut(
        #: Ready, not merely "the program exists": a program with no Python
        #: wrapper offered as a reader fails on the first page.
        tesseract=engine["ready"],
        vision=bool(model),
        vision_model=model or "",
        vision_reason=reason,
        ocr=bool(second),
        ocr_model=second,
        ocr_reason="" if second else reason,
        engine=engine,
    )


class OcrLanguageBody(BaseModel):
    #: A Tesseract language code (`eng`, `deu`, `eng+deu`), or "" for the
    #: engine's default.
    language: str = Field(default="", max_length=80)


@router.post("/ocr/language")
def set_ocr_language(body: OcrLanguageBody) -> dict:
    """Remember which language Tesseract reads in. One setting for every read
    (see `ocr.LANGUAGE_PREFERENCE`); the answer is the engine status, so the
    caller repaints from the truth rather than from what it sent."""
    try:
        ocr.set_language(body.language)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ocr.engine_status()
