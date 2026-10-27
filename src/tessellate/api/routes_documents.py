"""Long-form documents (the editor tab): CRUD, export, and AI editing.

Documents are markdown, stored whole. They're deliberately not Entries, see
the model docstring: so they never appear in note search, the graph, or the
AI's retrieved context unless the user asks for them by name.
"""

from __future__ import annotations

import json
import logging
import re
import tempfile
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile
from fastapi.responses import StreamingResponse

from tessellate.api import paging
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.api.edit_conflicts import content_hash, refuse_if_stale
from tessellate.ai import drafter, utilities, vision_ocr
from tessellate.core import activity, deps, docexport, docmeta, docview, filetypes, syntaxcheck
from tessellate.core.config import user_now
from tessellate.core.database import (
    LIKE_ESCAPE,
    Bookmark,
    Document,
    Entry,
    DocumentAiEdit,
    DocumentBookmark,
    DocumentRevision,
    utcnow,
    like_escape,
)
from tessellate.core.deps import get_session
from tessellate.entry import link_offers
from tessellate.entry.mentions import (
    BACKLINK_ROWS_MAX,
    BACKLINK_SOURCES_MAX,
    backlink_rows as _backlink_rows,
    backlink_spans as _backlink_spans,
)
from tessellate.entry.manager import (
    entries_for_document,
    join_blocks,
    strip_inline_markdown,
    get_entry,
    link_document,
    log_action,
    unlink_document,
)
from tessellate.entry.properties import strip as strip_properties

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

# A generous cap: this is long-form writing, but an unbounded column is how a
# runaway paste takes the database with it.
MAX_CONTENT = 500_000

#: The AI-edit changelog (DocumentAiEdit) is a per-document log, not a
#: process-lifetime ring buffer like taskhistory.py's: it has to survive a
#: restart: but it still needs a ceiling, or a document rewritten by the AI
#: hundreds of times over its life would keep every full before/after
#: snapshot forever. Oldest entries are pruned past this on each new write.
MAX_AI_EDIT_LOG_PER_DOCUMENT = 20
#: How much of the targeted passage a changelog entry shows, enough to say
#: what it touched, not the whole thing (that's what reverting is for).
SELECTION_EXCERPT_CHARS = 160


class DocumentBody(BaseModel):
    title: str = Field(default="Untitled", min_length=1, max_length=200)
    content: str = Field(default="", max_length=MAX_CONTENT)
    #: A bare extension ("md", "py"). Not validated as an enum here on
    #: purpose: `filetypes.normalise` accepts a filename, a dotted
    #: extension or a bare one and falls back to markdown for anything it
    #: does not know, which is the right answer for a field that only
    #: describes how to *display* the content. A 422 over it would refuse
    #: to save someone's writing because of its label.
    file_type: str = Field(default=filetypes.DEFAULT_FILE_TYPE, max_length=40)


class DocumentPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, max_length=MAX_CONTENT)
    #: None means "leave it alone", the same convention as the two fields
    #: above, so an autosave sending only `content` cannot reset a
    #: document's type back to markdown.
    file_type: str | None = Field(default=None, max_length=40)
    #: Who is making this change, for the history: "edit" (a person typing),
    #: "ai" (an accepted suggestion), "restore" (rolling back). The frontend
    #: says so because only it knows, by the time a PATCH arrives the text
    #: looks the same whoever wrote it.
    revision_source: Literal["edit", "ai", "restore"] = "edit"
    #: The `content_hash` of the text this edit started from: a save over
    #: text another window has since changed is refused with 409 rather than
    #: silently overwriting it (api/edit_conflicts.py). None is unchecked.
    base_hash: str | None = Field(default=None, max_length=64)


class AiEditBody(BaseModel):
    """Ask the AI to rewrite, write, or remove, the document editor's AI
    panel reskinned from a single rewrite action into a small general
    assistant, asked for directly. `verb` picks which of the three the
    instruction is asking for; `instruction` is validated against it below
    rather than at the field level, since "remove this" needs no words at
    all when a selection already says what to remove.
    """

    instruction: str = Field(default="", max_length=500)
    # When set: "edit"/"remove" rewrite or strip from just this passage;
    # "write" inserts new text directly after it. Empty means "the whole
    # document" for edit/remove, or "at the end" for write.
    selection: str = Field(default="", max_length=MAX_CONTENT)
    #: "edit" (default, unchanged): rewrite the target to the instruction.
    #: "write": generate a new passage and insert it, the target is
    #: context, not something to overwrite. "remove": delete what the
    #: instruction (or the selection alone) describes, leaving everything
    #: else exactly as written.
    verb: Literal["edit", "write", "remove"] = "edit"


#: How much of a document's opening the list view gets. Long enough for three
#: lines at the card's width, short enough that listing 200 documents does not
#: ship 200 whole documents to draw a list, which is the reason `_summary`
#: withholds `content` in the first place.
PREVIEW_CHARS = 240


_TABLE_RULE = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$")


def _preview_line(line: str) -> str:
    """One line as plain words: a table row becomes its cells ("REM, 25%"), the
    `| --- |` rule under its header nothing, and bold, links and code lose
    their markers. dog3-1026 D7: the list card showed raw `| Stage | Share |`."""
    if line.startswith("|") and line.endswith("|"):
        if _TABLE_RULE.match(line):
            return ""
        line = ", ".join(cell.strip() for cell in line.strip("|").split("|") if cell.strip())
    return strip_inline_markdown(line).lstrip("#>-*+ \t")


def _preview(content: str) -> str:
    """The opening of a document, flattened to one run of prose.

    The Library's document list showed a title, a word count and a date and
    nothing else, so telling four similarly-named drafts apart meant opening
    each one. Reported as the Documents sub-tab being "boring" and wanting
    previews.

    Markdown structure is stripped rather than rendered: a preview that begins
    with `# ` or `- ` spends its first characters on syntax, and a heading is
    usually a restatement of the title that is already on the card. Blank
    lines collapse for the same reason, three lines of preview should be
    three lines of the document's words.
    """
    # Leading markdown syntax only, a `#` inside a sentence stays. The blocks
    # stay apart (`join_blocks`, INBOX 464): a heading is not the first word
    # of the sentence under it.
    text = join_blocks(strip_properties(content), strip=_preview_line, limit=PREVIEW_CHARS)
    if len(text) <= PREVIEW_CHARS:
        return text
    # Cut at a word boundary, not mid-word. A hard slice ended the first
    # rendered preview on "a different kind of de", which reads as the text
    # being broken rather than as there being more of it. The ellipsis is what
    # says "there is more"; without it a clean cut just looks like a document
    # that stops.
    cut = text[:PREVIEW_CHARS]
    space = cut.rfind(" ")
    if space > PREVIEW_CHARS // 2:
        cut = cut[:space]
    return cut.rstrip(" ,;:-") + "\u2026"


def _summary(document: Document) -> dict:
    return {
        "id": document.id,
        "title": document.title,
        "updated_at": document.updated_at.isoformat(),
        "words": len(document.content.split()),
        "preview": _preview(document.content),
        # Normalised on the way out as well as in: a row written before this
        # column existed, or by a restore from an older backup, can hold
        # anything at all, and the editor picks its whole mode from this.
        "file_type": filetypes.normalise(document.file_type),
        "archived_at": document.archived_at.isoformat() if document.archived_at else None,
        # The frontmatter's keys and values, so the Library can filter on a
        # property without a request per document (DOCUMENTS_PLAN Phase 3 item
        # 4's second clause). It rides on the summary rather than on `_full`
        # because the list is the only place that needs it: the editor has the
        # content and parses its own. See `core/docmeta.py` for why the parse
        # is here at all rather than in the browser.
        "properties": docmeta.properties(document.content or ""),
    }


def _full(document: Document, session: Session | None = None) -> dict:
    body = {**_summary(document), "content": document.content, "content_hash": content_hash(document.content)}
    if session is not None:
        body["notes"] = _linked_notes(session, document.id)
    return body


def _linked_notes(session: Session, document_id: int) -> list[dict]:
    """The notes attached to this document, as previews.

    A note and a document are different things on purpose, but they are
    usually about the same thing, asked for directly: "the documents and
    notes sections and features need to be more integrated together".
    """
    from tessellate.entry.manager import readable_content

    return [
        {
            "id": entry.id,
            "preview": readable_content(entry)[:120],
            "is_private": bool(entry.is_private),
        }
        for entry in entries_for_document(session, document_id)
    ]


def _existing(session: Session, document_id: int) -> Document:
    return deps.get_or_404(session, Document, document_id, "That document could not be found.")


class AttachBookmarkBody(BaseModel):
    bookmark_id: int


@router.get("/{document_id}/bookmarks")
def document_bookmarks(document_id: int, session: Session = Depends(get_session)) -> list[dict]:
    """Bookmarks attached to this document, same References concept as a
    note's own `/entries/{id}/bookmarks` (asked about directly: "should
    bookmarks show in documents... as well?")."""
    _existing(session, document_id)
    rows = (
        session.query(Bookmark)
        .join(DocumentBookmark, DocumentBookmark.bookmark_id == Bookmark.id)
        .filter(DocumentBookmark.document_id == document_id)
        .order_by(DocumentBookmark.created_at)
        .all()
    )
    return [
        {"id": b.id, "url": b.url, "title": b.title, "group_name": b.group_name}
        for b in rows
    ]


@router.post("/{document_id}/bookmarks", status_code=201)
def attach_bookmark(
    document_id: int, body: AttachBookmarkBody, session: Session = Depends(get_session)
) -> dict:
    _existing(session, document_id)
    deps.get_or_404(session, Bookmark, body.bookmark_id, "That bookmark could not be found.")
    already = (
        session.query(DocumentBookmark)
        .filter_by(document_id=document_id, bookmark_id=body.bookmark_id)
        .first()
    )
    if not already:
        session.add(DocumentBookmark(document_id=document_id, bookmark_id=body.bookmark_id))
        session.commit()
    return {"attached": True}


@router.delete("/{document_id}/bookmarks/{bookmark_id}")
def detach_bookmark(
    document_id: int, bookmark_id: int, session: Session = Depends(get_session)
) -> dict:
    _existing(session, document_id)
    session.query(DocumentBookmark).filter_by(
        document_id=document_id, bookmark_id=bookmark_id
    ).delete()
    session.commit()
    return {"detached": True}


def _process_committed_media(session: Session, content: str) -> None:
    """Trigger OCR/captioning/vision-OCR for every `/media/…` upload this
    document's content references: see core/media_process.py's own
    docstring for why this fires on save rather than on upload."""
    from tessellate.core import media_process

    media_process.process_referenced_uploads(
        session, deps.get_config().data_dir / "media", content
    )


@router.get("/file-types")
def list_file_types() -> dict:
    """Every selectable document type, with what the editor needs to behave
    like one.

    Served rather than duplicated into `app.js` because indenting and
    comment-toggling happen on keystrokes and cannot wait for a round trip, 
    so the frontend needs the table itself, not a lookup endpoint. One copy,
    fetched once; two copies would be two things to update, and the failure
    mode of them disagreeing is Ctrl+/ writing the wrong comment marker into
    someone's file.

    Declared **above** `/{document_id}` deliberately: FastAPI matches routes in
    definition order, and "file-types" is a perfectly good string for a path
    parameter typed `int`, registered the other way round this would 422 on
    every call instead of answering.
    """
    return {"default": filetypes.DEFAULT_FILE_TYPE, "types": filetypes.as_dicts()}


class SyntaxCheckBody(BaseModel):
    language: str = Field(min_length=1, max_length=16)
    text: str = Field(default="", max_length=syntaxcheck.MAX_CHARS)


@router.post("/check-syntax")
def check_syntax(body: SyntaxCheckBody) -> list[dict]:
    """Syntax diagnostics for a code document (INBOX 392).

    `[{line, col, message, severity}]`, 1-based, empty when the text parses.
    Stateless on purpose: it takes the text rather than a document id, so the
    editor can check what is on screen before it has been saved, and it never
    touches the database. A language this server cannot check is a 400, not
    an empty list, because an empty list is what "no errors" looks like.
    Declared above `/{document_id}` for the reason `/file-types` is.
    """
    try:
        return syntaxcheck.check(body.language, body.text)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


class LinkOffersBody(BaseModel):
    text: str = Field(default="", max_length=link_offers.TEXT_MAX)
    #: The document being written: its own title is not a name to link to.
    document_id: int | None = None


@router.post("/link-offers")
def document_link_offers(body: LinkOffersBody, session: Session = Depends(get_session)) -> dict:
    """Where the text names another note or document (VC5): `{offers: [{start,
    end, text, kind, name, link}]}`, the first mention of each, in text order.

    Stateless like `/check-syntax`: it takes the text on screen rather than a
    saved document, and writes nothing. Declared above `/{document_id}`.
    """
    own = session.get(Document, body.document_id) if body.document_id else None
    return {"offers": link_offers.offers(session, body.text, exclude_title=own.title if own else None)}


#: A page of the document list, not a ceiling on how many documents a
#: notebook may hold: a caller that wants all of them pages until
#: `X-Total-Count` is satisfied (`loadDocuments` in documents.js,
#: `renderLibraryDocuments` in library.js), exactly the way `GET /entries`
#: is read. 200 because that is the number `GET /conversations` already
#: caps at, and because every surface built on this response draws far
#: fewer than that at once: the Documents sidebar shows eight
#: (`RECENT_DOCS_SHOWN`), the Library's own pager offers 24 or 48. At the
#: measured row cost (about 400 bytes of summary, never the document's
#: text) a page is about 78 KB instead of a response that grows with the
#: table forever.
DOCUMENTS_PAGE_SIZE = 200
DOCUMENTS_PAGE_SIZE_MAX = 1000


@router.get("")
def list_documents(
    response: Response,
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=DOCUMENTS_PAGE_SIZE, ge=1, le=DOCUMENTS_PAGE_SIZE_MAX),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = paging.cursor_param(),
    session: Session = Depends(get_session),
) -> list[dict]:
    """A page of documents, newest-first, optionally narrowed by `q`.

    **Paged, with an offset, which is the whole point.** This list was
    genuinely unbounded until now, and carried the reasoning that "an
    unbounded read is the same cost `GET /entries` already pays on every
    load". That premise stopped being true when `/entries` was capped: this
    was mirroring a sibling that had moved. Measured at 300 documents, one
    response was 300 rows and 116.7 KB and grew with the table with nothing
    to stop it.

    What the old comment was right about is the failure it was avoiding: a
    silent cap with *no* offset makes everything past it permanently
    unreachable. So the cap comes with `limit`, `offset` and an
    `X-Total-Count` header giving the real size of the current selection
    (with `q` applied, when `q` is given), and both frontends that need the
    whole list ask for the next page until they have it. Nothing that could
    be reached before is unreachable now; only the size of one response is
    bounded.

    `q`, when given, is the gap that client-side filtering can't close on
    its own: `_summary()` never sends document *content* to the browser (a
    document can run to thousands of words, unlike a note), so there was no
    way to search what a document actually says, only its title, despite
    the AI already being able to (`ai/tools/documents.py`'s `_list_documents`
    has searched title *and* content this way since it was written; this
    mirrors that filter rather than inventing a second one). Plain
    case-insensitive substring matching, not semantic search, whether
    documents get embeddings at all is a separate, larger decision.
    """
    offset = paging.start(cursor, offset)
    # Archived documents are kept, but out of the way, reachable via the
    # Library's Shelved filter (routes_library._shelved), not this list.
    live = Document.archived_at.is_(None)
    filters = [live]
    term = q.strip()
    #: **A window in the search is a window** (CHAT_PLAN section 2, the
    #: documents row): "harbor last week" is the documents about the harbor
    #: edited in the last week, read by the notes search's own reader
    #: (`search.query.understand`, through the one recogniser), so a phrase
    #: means one stretch of days in every search box.
    if term:
        from tessellate.search import query as search_query

        understood = search_query.understand(term, user_now(deps.get_config()))
        if understood.since is not None:
            filters.append(Document.updated_at >= datetime.combine(understood.since, time.min))
            if understood.until is not None:
                filters.append(Document.updated_at < datetime.combine(understood.until + timedelta(days=1), time.min))
            term = understood.subject if not understood.time_only else ""
    if term:
        like = f"%{like_escape(term)}%"
        filters.append(
            Document.title.ilike(like, escape=LIKE_ESCAPE)
            | Document.content.ilike(like, escape=LIKE_ESCAPE)
        )
    # Counted over the same filters as the page below, never over the whole
    # table: with `q` given, "how many are there" means how many match, or a
    # caller paging a search would loop past the end of its own results.
    total = session.scalar(select(func.count(Document.id)).where(*filters)) or 0
    query = (
        select(Document)
        .where(*filters)
        .order_by(Document.updated_at.desc(), Document.id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = session.scalars(query)
    response.headers["X-Total-Count"] = str(total)
    paging.finish(response, offset, limit, total)
    return [_summary(d) for d in rows]


#: How many documents and how many headings per document the Library's
#: Contents index reads. An index of a notebook is for finding your place; a
#: document with four hundred headings is a book, and its outline is in the
#: editor.
OUTLINE_DOCUMENTS = 500
OUTLINE_HEADINGS = 40


def _document_headings(content: str) -> list[dict]:
    """`{line, level, text}` for each markdown heading, `line` zero-based (the
    editor's `jumpToDocLine` takes that): `utilities.outline`, the one
    outline the editor, this index and the agent share."""
    return utilities.outline(content, limit=OUTLINE_HEADINGS)


@router.get("/outline")
def documents_outline(session: Session = Depends(get_session)) -> list[dict]:
    """Every live document with its headings, for the Library's Contents index
    (INBOX 445 (1)): categories hold notes, and documents hold sections.

    One request rather than one `GET /documents/{id}` per document, because the
    list deliberately never carries content (`_summary`); the headings are the
    only part of it this index needs, so only they are sent. Markdown only: a
    code file's "headings" are comments.
    """
    rows = session.scalars(
        select(Document)
        .where(Document.archived_at.is_(None))
        .order_by(Document.updated_at.desc(), Document.id.desc())
        .limit(OUTLINE_DOCUMENTS)
    )
    out = []
    for document in rows:
        kind = filetypes.get(document.file_type)
        out.append(
            {
                "id": document.id,
                "title": document.title,
                "created_at": document.created_at.isoformat(),
                "updated_at": document.updated_at.isoformat(),
                "file_type": kind.ext,
                "headings": _document_headings(document.content) if kind.previewable else [],
            }
        )
    return out


@router.post("", status_code=201)
def create_document(
    body: DocumentBody, session: Session = Depends(get_session)
) -> dict:
    document = Document(
        title=body.title.strip() or "Untitled",
        content=body.content,
        file_type=filetypes.normalise(body.file_type),
    )
    session.add(document)
    session.flush()
    log_action(session, "created", "document", document.id, document.title[:80])
    session.commit()
    _process_committed_media(session, document.content)
    return _full(document, session)


#: Same ceiling as every other upload in the app (routes_files.MAX_FILE_BYTES).
#: Kept as its own name rather than imported, because these two limits answer
#: different questions: how big a picture may be, and how big a document may
#: be: and a future change to one should not silently move the other.
MAX_IMPORT_BYTES = 50 * 1024 * 1024


class ContentItem(BaseModel):
    id: int
    content: str = Field(max_length=MAX_CONTENT)


class ContentBatch(BaseModel):
    documents: list[ContentItem] = Field(max_length=1000)


#: The most documents `GET /contents` reads, the same bound the write takes.
CONTENTS_READ_MAX = 1000


@router.get("/contents")
def read_contents(
    file_type: str | None = Query(default=None, max_length=40),
    session: Session = Depends(get_session),
) -> list[dict]:
    """Every live document's id, title and text in one response, for Replace
    in every document's scan (OPEN row 1055). It read `GET ""` (one page)
    and then each document by its own request, so past the first page it
    missed documents, and at fifty it cost fifty-one requests. The pattern is
    matched in the browser because it may be a regular expression.
    `file_type` narrows it to one kind: a SQL run reads the CSV documents
    its query names as tables (OPEN row 1069)."""
    query = select(Document).where(Document.archived_at.is_(None))
    if file_type:
        query = query.where(Document.file_type == filetypes.normalise(file_type))
    rows = session.scalars(query.order_by(Document.updated_at.desc(), Document.id.desc()).limit(CONTENTS_READ_MAX))
    return [
        {"id": d.id, "title": d.title, "file_type": filetypes.normalise(d.file_type), "content": d.content or ""}
        for d in rows
    ]


@router.post("/contents")
def write_contents(body: ContentBatch, session: Session = Depends(get_session)) -> dict:
    """Many documents' text in one transaction (DOCUMENTS 24 row 9): Replace in
    every document writes its results here, and its one undo step writes the
    originals back the same way, so a replace over fifty documents lands, or
    is taken back, whole. Every id is checked before anything is written; each
    changed document keeps the version it replaced in its history."""
    ids = [item.id for item in body.documents]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=422, detail="A document is listed twice.")
    documents = {doc.id: doc for doc in (_existing(session, doc_id) for doc_id in ids)}
    updated = []
    for item in body.documents:
        document = documents[item.id]
        if item.content == document.content:
            continue
        _record_document_revision(session, document, source="edit")
        document.content = item.content
        document.updated_at = utcnow()
        updated.append(document.id)
    if updated:
        log_action(session, "edited", "document", updated[0], f"{len(updated)} documents in one replace")
    session.commit()
    return {"updated": updated}


@router.post("/import", status_code=201)
def import_document(
    file: UploadFile, session: Session = Depends(get_session)
) -> dict:
    """Turn an uploaded file into a document.

    Asked for directly: the chat's attach button should take *any* file, with
    "images … in the image gallery (any image format), and the others should
    probably go in the documents subtab". This is the second half, images
    already had a home (`POST /media/upload`), and everything else had none.

    What arrives is a .docx, .pdf, .csv, .md, a source file; what is stored is
    its **text**, extracted by `core/docview.py`, in an ordinary Document row.
    That is deliberate and is the same decision the file viewer made: this app
    never serves an uploaded byte back inline, so importing means converting
    once, on the way in, rather than keeping a binary the rest of the app would
    have to learn to handle.

    Declared above `/{document_id}` because FastAPI matches in declaration
    order and "import" is not an int, the same trap `/file-types` sits above.
    """
    name = (file.filename or "file").strip() or "file"
    suffix = docview.effective_suffix(name)
    if suffix not in docview.VIEWABLE_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Can't read a {suffix or 'file'}. This takes documents, "
                "spreadsheets, PDFs, and text or code files."
            ),
        )

    # Written to a scratch file rather than held in memory: docview reads a
    # path (so does every extractor behind it), and a 50 MB upload buffered
    # whole is 50 MB of this process for as long as the request runs.
    with tempfile.TemporaryDirectory(prefix="mm-import-") as scratch:
        staged = Path(scratch) / f"upload{suffix}"
        size = 0
        with staged.open("wb") as out:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_IMPORT_BYTES:
                    raise HTTPException(
                        status_code=413, detail="That file is larger than 50 MB."
                    )
                out.write(chunk)
        # The scanned-PDF fallback, same as the file viewer's. Importing a
        # scan and importing a text PDF must not need different actions from
        # the user: this is the "hands off" half, and the models and the
        # rasteriser it needs are the "optionally customisable" half. Costs
        # nothing for every other file type: `docview` only consults a reader
        # once a PDF has turned out to have no text layer.
        #: Listed while it reads (OPEN 1095, the activity contract's rule 5):
        #: a 50 MB PDF or a scan read by the vision model takes a while.
        with activity.track("import", f"Importing {name[:80]}", stoppable=False):
            viewed = docview.extract(staged, vision_reader=vision_ocr.pdf_reader_or_none())

    #: **A saved web page becomes prose here, and only here** (Phase 7).
    #: `docview.extract` hands back an .html file's own markup, because the
    #: viewer's preview pane serves exactly that inside a sandboxed response
    #: and converting inside the extractor turned that pane into a page
    #: showing `# Hi`. An *import* wants the opposite: this is a document from
    #: now on, and a document of tags is not one anybody can edit.
    if suffix in docview.HTML_SUFFIXES and viewed.text.strip():
        viewed = docview.ViewedFile(
            text=docview.html_to_markdown(viewed.text),
            kind="markdown",
            source="converted",
            truncated=viewed.truncated,
        )

    if not viewed.text.strip():
        # The extractor's own message says *why*, a scan with no text layer
        # reads differently from a converter that is not installed, and it is
        # a better error than anything this route could invent.
        raise HTTPException(
            status_code=422,
            detail=viewed.message or "There was no readable text in that file.",
        )

    document = Document(
        title=Path(name).stem[:200] or "Imported",
        content=viewed.text,
        # The extracted text is markdown-ish prose whatever it came from, so
        # it opens in the editor that suits it. A code file keeps its own type
        # so the gutter and comment toggle work on it.
        #
        #: And a *converted* file is markdown now whatever its name was: a
        #: saved web page comes out of `docview` as markdown (Phase 7), and
        #: stored as "html" it would open in the editor as HTML source with
        #: every markdown feature off, which is the file's old shape being
        #: described rather than its new one.
        file_type=(
            "md"
            if viewed.kind == "markdown" and viewed.source == "converted"
            else filetypes.normalise(suffix.lstrip("."))
        ),
    )
    session.add(document)
    session.flush()
    log_action(session, "imported", "document", document.id, document.title[:80])
    session.commit()
    return {**_full(document, session), "truncated": viewed.truncated}


@router.get("/{document_id}")
def get_document(document_id: int, session: Session = Depends(get_session)) -> dict:
    return _full(_existing(session, document_id), session)


@router.put("/{document_id}")
def update_document(
    document_id: int, body: DocumentPatch, session: Session = Depends(get_session)
) -> dict:
    document = _existing(session, document_id)
    #: Two windows, one document (WORLD_CLASS_PLAN 22.1 item 5), checked
    #: before anything is written, the title included.
    refuse_if_stale(
        base_hash=body.base_hash,
        current_text=document.content,
        new_text=body.content,
        current=lambda: _full(document, session),
        noun="document",
    )
    if body.title is not None:
        document.title = body.title.strip() or document.title
    content_changed = body.content is not None and body.content != document.content
    #: Before the change lands, so the newest revision is always the version
    #: being replaced: the same rule `record_revision` follows for notes.
    #: Only on a real content change: a title-only edit or an autosave that
    #: sends the identical text must not add an entry saying nothing happened.
    if content_changed:
        _record_document_revision(session, document, source=body.revision_source)
    if body.content is not None:
        document.content = body.content
    if body.file_type is not None:
        document.file_type = filetypes.normalise(body.file_type)
    document.updated_at = utcnow()
    session.commit()
    if content_changed:
        # A save (autosave included) is one of the three "committed"
        # moments core/media_process.py waits for, asked for directly,
        # OCR/captioning/vision-OCR must not run on a staged upload that
        # was only ever dropped into a document draft, not saved.
        _process_committed_media(session, document.content)
    return _full(document, session)


#: How long a burst of editing counts as one revision. Autosave fires while you
#: type, so without coalescing a ten-minute sitting would leave a hundred
#: entries seconds apart: a log nobody can read rather than a history. Five
#: minutes is long enough that one sitting is one entry and short enough that
#: coming back after lunch is a new one.
REVISION_QUIET_SECONDS = 300

#: Enough to answer "what did it say before?" several edits back without the
#: table growing without bound. Matches the spirit of `MAX_REVISIONS` for notes.
MAX_DOCUMENT_REVISIONS = 40


def _record_document_revision(session: Session, document: Document, source: str = "edit") -> None:
    """Snapshot the document as it is *now*, before the caller changes it.

    Coalesced: an edit soon after the last snapshot replaces it, so the history
    reads as sittings rather than keystrokes. See `DocumentRevision`.

    Never raises: a history that fails to record must not fail the save it was
    recording. Losing one entry is a much smaller harm than refusing to let
    someone save their work.
    """
    try:
        latest = (
            session.query(DocumentRevision)
            .filter(DocumentRevision.document_id == document.id)
            .order_by(DocumentRevision.id.desc())
            .first()
        )
        now = utcnow()
        if latest is not None:
            #: Both sides made naive-UTC before comparing: `utcnow()` here is
            #: naive and a value read back from SQLite is too, but a future
            #: backend could hand back an aware one and a mixed comparison
            #: raises rather than being wrong quietly.
            previous = latest.created_at
            if previous.tzinfo is not None:
                previous = previous.replace(tzinfo=None)
            reference = now.replace(tzinfo=None) if now.tzinfo is not None else now
            if not latest.name and (reference - previous).total_seconds() < REVISION_QUIET_SECONDS:
                latest.title = document.title
                latest.content = document.content
                latest.source = source
                latest.created_at = now
                return
        session.add(
            DocumentRevision(
                document_id=document.id,
                title=document.title,
                content=document.content,
                source=source,
            )
        )
        session.flush()
        stale = (
            session.query(DocumentRevision)
            .filter(DocumentRevision.document_id == document.id)
            .order_by(DocumentRevision.id.desc())
            .offset(MAX_DOCUMENT_REVISIONS)
            .all()
        )
        for row in stale:
            session.delete(row)
    except Exception:  # noqa: BLE001 - a history must never block a save
        logger.debug("could not record a document revision", exc_info=True)


@router.delete("/{document_id}")
def delete_document(document_id: int, session: Session = Depends(get_session)) -> dict:
    """To the recycle bin (WORLD_CLASS_PLAN 5 item 10), as a note goes: the
    document, its history, its notes and its reminders all stay, hidden, until
    it is restored or purged (`entry/bin.py`). It used to be the one thing in
    the app deleted outright, and its Undo made a new document with a new id."""
    document = _existing(session, document_id)
    document.deleted_at = utcnow()
    log_action(session, "deleted", "document", document.id, document.title[:80])
    session.commit()
    return {"deleted": True, "binned": True}


def _binned(session: Session, document_id: int) -> Document:
    from tessellate.entry import bin as other_bin

    with other_bin.including_binned(session):
        document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="That document could not be found.")
    return document


@router.post("/{document_id}/restore")
def restore_document(document_id: int, session: Session = Depends(get_session)) -> dict:
    """Out of the bin, with its id and everything that pointed at it."""
    document = _binned(session, document_id)
    if document.deleted_at is not None:
        document.deleted_at = None
        log_action(session, "restored", "document", document.id, document.title[:80])
        session.commit()
    return _summary(document)


@router.delete("/{document_id}/purge")
def purge_document(document_id: int, session: Session = Depends(get_session)) -> dict:
    """For good. Only a binned document, as only a binned note: a live one
    goes to the bin first, so no single press destroys a document."""
    from tessellate.entry import bin as other_bin

    document = _binned(session, document_id)
    if document.deleted_at is None:
        raise HTTPException(status_code=409, detail="Only a document in the bin can be deleted for good.")
    log_action(session, "purged", "document", document.id, document.title[:80])
    with other_bin.including_binned(session):
        other_bin.purge_document(session, document)
        session.commit()
    return {"purged": document_id}


@router.put("/{document_id}/archive")
def archive_document(document_id: int, session: Session = Depends(get_session)) -> dict:
    """Kept, but out of the way (BACKLOG §30b's named remaining scope), 
    same shape as `routes_entries.archive_entry`: never deleted, never
    auto-cleared, drops out of the Documents list, still reachable from
    the Library's Shelved filter."""
    document = _existing(session, document_id)
    if not document.archived_at:
        document.archived_at = utcnow()
        log_action(session, "archived", "document", document.id, document.title[:80])
        session.commit()
    return _summary(document)


@router.put("/{document_id}/unarchive")
def unarchive_document(document_id: int, session: Session = Depends(get_session)) -> dict:
    document = _existing(session, document_id)
    if document.archived_at:
        document.archived_at = None
        log_action(session, "unarchived", "document", document.id, document.title[:80])
        session.commit()
    return _summary(document)


def _safe_filename(title: str, extension: str) -> str:
    """A title is user text; it must not steer where the file lands."""
    cleaned = re.sub(r"[^\w\s-]", "", title).strip() or "document"
    cleaned = re.sub(r"[\s_]+", "-", cleaned)[:60]
    return f"{cleaned}.{extension}"


class LinkBody(BaseModel):
    entry_id: int


@router.post("/{document_id}/notes", status_code=201)
def attach_note(
    document_id: int, body: LinkBody, session: Session = Depends(get_session)
) -> dict:
    """Attach an existing note to this document."""
    document = _existing(session, document_id)
    entry = get_entry(session, body.entry_id)
    if entry is None or entry.is_deleted:
        raise HTTPException(status_code=404, detail="That note could not be found.")
    link_document(session, document.id, entry.id)
    return _full(document, session)


@router.delete("/{document_id}/notes/{entry_id}")
def detach_note(
    document_id: int, entry_id: int, session: Session = Depends(get_session)
) -> dict:
    """Detach a note. The note itself is untouched, this is a connection,
    not ownership."""
    document = _existing(session, document_id)
    unlink_document(session, document.id, entry_id)
    return _full(document, session)


# --- backlinks with context, and unlinked mentions ---------------------------
#: DOCUMENTS_PLAN Phase 4 item 1. The panel used to list the *titles* of the
#: notes that link here, which reads as a lookup rather than as knowledge: you
#: learn that a connection exists and nothing about what it says. Two things
#: change that, and they are the two Obsidian and Kortex both have: the
#: sentence the link sits in, and the mentions that are not links yet.
#:
#: **Why the server does this and the client does not.** The browser holds
#: every note (`allEntries`) but no document's *content*: `_summary()`
#: deliberately never sends it, because a document runs to thousands of words.
#: A client-side scan would therefore find note backlinks and silently miss
#: every document one, which is the half-built shape this plan exists to stop.
#: One scan here answers for both kinds and defines "a mention" exactly once.



def _backlinks(session: Session, document: Document) -> dict:
    from tessellate.entry.manager import plain_label

    title = (document.title or "").strip()
    if not title:
        # Nothing to match on. An untitled document has no name to be
        # mentioned by, which is a fact about the document rather than an
        # error, so this is an empty answer and not a 400.
        return {"title": "", "links": [], "mentions": []}

    like = f"%{like_escape(title)}%"
    sources: list[tuple[str, int, str, str]] = []
    sources.extend(
        ("document", row.id, row.title or "Untitled", row.content or "")
        for row in session.scalars(
            select(Document)
            .where(
                Document.id != document.id,
                Document.archived_at.is_(None),
                Document.content.ilike(like, escape=LIKE_ESCAPE),
            )
            .order_by(Document.updated_at.desc(), Document.id.desc())
            .limit(BACKLINK_SOURCES_MAX)
        )
    )
    note_rows = session.scalars(
        select(Entry)
        .where(
            Entry.is_deleted == False,  # noqa: E712
            # A private note is encrypted at rest, so its content would not
            # match the LIKE anyway; the filter is here so that stays true by
            # decision rather than by side effect.
            Entry.is_private == False,  # noqa: E712
            Entry.content.ilike(like, escape=LIKE_ESCAPE),
        )
        .order_by(Entry.id.desc())
        .limit(BACKLINK_SOURCES_MAX)
    )
    sources.extend(
        ("note", row.id, plain_label(row.content, 60) or "Untitled note", row.content or "")
        for row in note_rows
    )

    links: list[dict] = []
    mentions: list[dict] = []
    for kind, source_id, label, content in sources:
        linked, unlinked = _backlink_spans(content, title)
        links.extend(_backlink_rows(kind, source_id, label, content, linked))
        mentions.extend(_backlink_rows(kind, source_id, label, content, unlinked))
    return {
        "title": title,
        "links": links[:BACKLINK_ROWS_MAX],
        "mentions": mentions[:BACKLINK_ROWS_MAX],
    }


@router.get("/{document_id}/backlinks")
def document_backlinks(document_id: int, session: Session = Depends(get_session)) -> dict:
    """What links here, what mentions it, and the sentence each one says it in."""
    return _backlinks(session, _existing(session, document_id))


@router.get("/{document_id}/connections")
def document_connections(document_id: int, session: Session = Depends(get_session)) -> dict:
    """The same Connections block a note gets, for a document.

    A document's joins were split across three places before this: attached
    notes came back inside `GET /documents/{id}`, bookmarks had their own
    endpoint, and the images a document embeds were listed nowhere, you
    could only find them by reading the markdown. One shape, one request.
    """
    from tessellate.api.routes_entries import _connected_files

    document = _existing(session, document_id)
    bookmarks = [
        {"id": row.id, "title": row.title, "url": row.url}
        for row in session.scalars(
            select(Bookmark)
            .join(DocumentBookmark, DocumentBookmark.bookmark_id == Bookmark.id)
            .where(DocumentBookmark.document_id == document.id)
            .order_by(Bookmark.title)
        )
    ]
    notes = _linked_notes(session, document.id)
    files = _connected_files(session, document.content)
    return {
        "notes": notes,
        "bookmarks": bookmarks,
        "files": files,
        "total": len(notes) + len(bookmarks) + len(files),
    }


@router.get("/{document_id}/export.md")
def export_markdown(
    document_id: int, session: Session = Depends(get_session)
) -> Response:
    """The document's own text, as a download.

    Still routed at `export.md`, the path is what the frontend and any saved
    bookmark already point at, and renaming it would break both to describe
    something the URL never guaranteed. What *does* follow the document's type
    is the file the browser saves: a Python document downloads as `.py`, not
    as a `.md` containing Python.

    The title-as-H1 preamble is markdown-only for the same reason. `# Title`
    at the top of a .py file is a comment by luck; at the top of a .json file
    it is a syntax error, and a download that will not parse is worse than one
    without a heading.
    """
    document = _existing(session, document_id)
    kind = filetypes.get(document.file_type)
    if kind.ext == "md":
        #: A comment leaves as a footnote (DOCUMENTS_PLAN Phase 5 item 1): the
        #: remarks in `==words== %%about them%%` are part of the work, and a
        #: download that dropped them would be the one copy of this document
        #: that silently says less than the editor does. Markdown only, for the
        #: same reason the `# Title` preamble is markdown only: `%%` is not a
        #: comment in python, so in a code file it is text somebody typed.
        content = docexport.comments_to_footnotes(document.content or "")
        body = docexport.with_title(content, document.title)
        media_type = "text/markdown; charset=utf-8"
    else:
        body = document.content
        # text/plain for everything else: the browser is being asked to save
        # the file, not to run or render it, and a specific type here buys
        # nothing while inviting a helpful handler to open it.
        media_type = "text/plain; charset=utf-8"
    return Response(
        content=body,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{_safe_filename(document.title, kind.ext)}"'
            )
        },
    )


@router.get("/{document_id}/export.zip")
def export_bundle(
    document_id: int, session: Session = Depends(get_session)
) -> Response:
    """The document and its pictures, as one zip (DOCUMENTS_PLAN Phase 7).

    `export.md` hands over the text, and a document with images in it then
    arrives somewhere else with `/media/…` links that resolve to nothing: the
    pictures live in this notebook and the file does not. This is the same
    markdown with every resolvable image beside it in `assets/` and its links
    rewritten to match, so it opens with its pictures showing in any markdown
    reader and needs this app for nothing.

    Markdown only. A .py or .json document has no image links to carry and a
    zip of one file is a worse download than the file.
    """
    from tessellate.core.media_gc import referenced_names

    document = _existing(session, document_id)
    kind = filetypes.get(document.file_type)
    if kind.ext != "md":
        raise HTTPException(
            status_code=400,
            detail="A bundle is for a markdown document; this one is "
            f"{kind.label}. Use the plain download instead.",
        )
    media_dir = deps.get_config().data_dir / "media"
    names = referenced_names(document.content or "")
    data, carried = docexport.bundle(document.title, document.content or "", media_dir, names)
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{_safe_filename(document.title, "zip")}"'
            ),
            #: What travelled, for the frontend's own message and for a test
            #: that wants the answer without opening the archive.
            "X-Assets": str(len(carried)),
        },
    )


@router.post("/{document_id}/ai-edit")
def ai_edit(
    document_id: int, body: AiEditBody, session: Session = Depends(get_session)
) -> dict:
    """Rewrite, write, or remove, three verbs on the same document-editor
    AI panel (asked for directly, reskinning it from a single rewrite
    action into a small general assistant).

    Nothing is saved here, the result comes back for the user to accept or
    reject, for all three verbs alike. An AI action that silently wrote
    into the file would be the single most destructive thing in the app.
    """
    document = _existing(session, document_id)
    instruction = body.instruction.strip()
    target = body.selection.strip() or document.content

    if body.verb == "write":
        if not instruction:
            raise HTTPException(status_code=400, detail="Say what to write.")
        inserted, thinking = drafter.compose_document_edit(
            document.content,
            deps.get_model_manager().for_feature("documents"),
            deps.get_ollama(),
            instruction=instruction,
            verb="write",
            context=body.selection.strip(),
        )
        offline = drafter.was_offline(thinking)
        return {
            "revised": inserted,
            "replaced_selection": False,
            "verb": "write",
            "thinking": None if offline else thinking,
            "message": drafter.offline_message() if offline else "",
            "ollama_running": not offline,
        }

    if not target.strip():
        raise HTTPException(status_code=400, detail="There's nothing to edit yet.")

    if body.verb == "remove":
        # A selection alone already says what to remove, asked for
        # directly, no need to also type "remove this" by hand.
        if not instruction and not body.selection.strip():
            raise HTTPException(
                status_code=400, detail="Say what to remove, or select it first."
            )
        revised, thinking = drafter.compose_document_edit(
            target,
            deps.get_model_manager().for_feature("documents"),
            deps.get_ollama(),
            instruction=instruction or "Remove this passage entirely.",
            verb="remove",
        )
        offline = drafter.was_offline(thinking)
        return {
            "revised": revised,
            "replaced_selection": bool(body.selection.strip()),
            "verb": "remove",
            "thinking": None if offline else thinking,
            "message": drafter.offline_message() if offline else "",
            "ollama_running": not offline,
        }

    if not instruction:
        raise HTTPException(status_code=400, detail="Say what you'd like changed.")
    revised, thinking = drafter.compose(
        "",
        target,
        deps.get_model_manager().for_feature("documents"),
        deps.get_ollama(),
        instruction=instruction,
    )
    offline = drafter.was_offline(thinking)
    return {
        "verb": "edit",
        # The caller replaces either the selection or the whole document.
        "revised": revised,
        "replaced_selection": bool(body.selection.strip()),
        "thinking": None if offline else thinking,
        "message": drafter.offline_message() if offline else "",
        "ollama_running": not offline,
    }


class AiCheckBody(BaseModel):
    """What to check: the selection when there is one, else the document."""

    selection: str = Field(default="", max_length=MAX_CONTENT)


@router.post("/{document_id}/ai-check")
def ai_check(
    document_id: int, body: AiCheckBody, session: Session = Depends(get_session)
) -> StreamingResponse:
    """Check with AI, in place (INBOX 410): findings streamed as NDJSON.

    It used to hand the document to the Chat tab with a long prompt, which
    left the editor, answered in a chat bubble with nothing to apply, and
    drew a skill suggestion over it that did not fit (INBOX 413). Now each
    finding arrives in the suggestions panel as the model writes it: the
    exact words, a one-line reason, a one-line fix. Nothing is changed here;
    the panel applies a fix only when it is pressed. Read before the stream
    starts, because the session is closed by the time the body is sent.
    """
    document = _existing(session, document_id)
    text = body.selection.strip() or (document.content or "")
    if not text.strip():
        raise HTTPException(status_code=400, detail="There's nothing to check yet.")

    def lines():
        for event in drafter.review_stream(
            text,
            deps.get_model_manager().for_feature("documents"),
            deps.get_ollama(),
        ):
            yield json.dumps(event) + "\n"

    return StreamingResponse(
        activity.tracked_stream("generation", "Reviewing a document", lines()),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


class RephraseBody(BaseModel):
    """A passage the writer wants alternatives for, and what is wrong with it."""

    passage: str = Field(min_length=1, max_length=2000)
    #: The checker's own message ("This sentence runs long", "its/it's"), so
    #: the model fixes the thing that was flagged rather than rewriting to
    #: taste. Optional: the toolbar can ask for alternatives to any selection.
    note: str = Field(default="", max_length=200)


@router.post("/{document_id}/rephrase")
def rephrase_passage(
    document_id: int, body: RephraseBody, session: Session = Depends(get_session)
) -> dict:
    """Two or three other ways to word one passage.

    Asked for directly: *"the listed errors in suggestions have no way to have
    the ai write a suggested replacement or multiple for the user to choose."*
    The app's own checks catch spelling, spacing and sentence length, and can
    offer a fix for the first two; for "this sentence is hard to follow" there
    is no mechanical answer and the panel could only say so.

    Nothing is saved. The alternatives come back for the writer to pick from, 
    the same rule `ai_edit` follows and for the same reason: a writing aid that
    edits the document by itself is the most destructive thing in the app.
    `options` is empty rather than an error when the model is offline or its
    reply is unusable, because "no suggestions" is a true statement and not a
    failure the writer caused.
    """
    _existing(session, document_id)
    options = drafter.rephrase(
        body.passage,
        deps.get_model_manager().for_feature("documents"),
        deps.get_ollama(),
        note=body.note,
    )
    running = deps.get_ollama().is_running()
    return {
        "options": options,
        "ollama_running": running,
        "message": "" if running else drafter.offline_message(),
    }


class DocumentRevisionOut(BaseModel):
    """One entry in a document's history."""

    id: int
    title: str
    source: str
    created_at: str
    #: Set on a named version, null on an ordinary sitting.
    name: str | None = None
    #: The size of the change, so the list says *how much* happened without
    #: making anyone open each entry: a history where every row looks the same
    #: is a history you have to read linearly.
    words: int
    #: Signed, against the version that replaced it: +120 words, -8 words.
    word_delta: int
    preview: str


@router.get("/{document_id}/revisions", response_model=list[DocumentRevisionOut])
def document_revisions(
    document_id: int, session: Session = Depends(get_session)
) -> list[DocumentRevisionOut]:
    """This document's history, newest first.

    Asked for by name: *"can the document have edit history like git logs??"*
    Notes have had revisions for a long time and documents had none, a rewrite
    destroyed what the document used to say, with nothing but the session's own
    undo stack, which forgets on reload.

    Each row carries a word count and the signed difference against whatever
    replaced it, which is the part that makes a list of timestamps readable: a
    git log is useful because every line says how big the change was.
    """
    document = _existing(session, document_id)
    rows = (
        session.query(DocumentRevision)
        .filter(DocumentRevision.document_id == document_id)
        .order_by(DocumentRevision.id.desc())
        .all()
    )
    out: list[DocumentRevisionOut] = []
    #: Newest first, and each row is compared with the version that *came
    #: after* it: for the newest revision that is the document as it stands
    #: now, which is why this walks with `newer` seeded from the document.
    newer_words = len((document.content or "").split())
    for row in rows:
        words = len((row.content or "").split())
        out.append(
            DocumentRevisionOut(
                id=row.id,
                title=row.title or document.title,
                source=row.source or "edit",
                created_at=row.created_at.isoformat(),
                name=row.name or None,
                words=words,
                word_delta=newer_words - words,
                preview=_preview(row.content or ""),
            )
        )
        newer_words = words
    return out


@router.get("/{document_id}/revisions/{revision_id}")
def document_revision(
    document_id: int, revision_id: int, session: Session = Depends(get_session)
) -> dict:
    """One past version, in full, so it can be read or diffed before restoring."""
    _existing(session, document_id)
    row = session.get(DocumentRevision, revision_id)
    if row is None or row.document_id != document_id:
        raise HTTPException(status_code=404, detail="That revision could not be found.")
    return {
        "id": row.id,
        "title": row.title,
        "content": row.content,
        "source": row.source,
        "created_at": row.created_at.isoformat(),
        "name": row.name or None,
    }


class RevisionNameBody(BaseModel):
    #: Empty or blank takes the name off.
    name: str = Field(default="", max_length=120)


@router.post("/{document_id}/revisions", status_code=201)
def name_current_version(
    document_id: int, body: RevisionNameBody, session: Session = Depends(get_session)
) -> dict:
    """Name the document as it stands now (DOCUMENTS 24 row 4, Google Docs's
    "Name current version"): a revision holding the current text, never
    coalesced into by the edits after it."""
    document = _existing(session, document_id)
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="A version needs a name.")
    row = DocumentRevision(
        document_id=document.id,
        title=document.title,
        content=document.content,
        source="edit",
        name=name,
    )
    session.add(row)
    session.commit()
    return {"id": row.id, "name": row.name, "created_at": row.created_at.isoformat()}


@router.put("/{document_id}/revisions/{revision_id}")
def rename_version(
    document_id: int,
    revision_id: int,
    body: RevisionNameBody,
    session: Session = Depends(get_session),
) -> dict:
    """Name, rename or un-name one version; the text it holds is untouched."""
    _existing(session, document_id)
    row = session.get(DocumentRevision, revision_id)
    if row is None or row.document_id != document_id:
        raise HTTPException(status_code=404, detail="That revision could not be found.")
    row.name = body.name.strip() or None
    session.commit()
    return {"id": row.id, "name": row.name}


@router.post("/{document_id}/revisions/{revision_id}/restore")
def restore_document_revision(
    document_id: int, revision_id: int, session: Session = Depends(get_session)
) -> dict:
    """Put the document back to how it was, keeping the version being replaced.

    A restore is itself an edit, so the current text is snapshotted first, 
    restoring the wrong entry must be as undoable as the edit that made you
    want to restore. Marked `source="restore"` so the history says what
    happened rather than looking like an ordinary rewrite.
    """
    document = _existing(session, document_id)
    row = session.get(DocumentRevision, revision_id)
    if row is None or row.document_id != document_id:
        raise HTTPException(status_code=404, detail="That revision could not be found.")
    #: **Read before writing, and this is not a style preference.** The
    #: snapshot below coalesces into the most recent revision when one is
    #: recent enough: and on the common path ("I rewrote this, undo that")
    #: the most recent revision *is* the one being restored. Recording first
    #: and reading `row.content` afterwards therefore restored the document to
    #: the text it had just overwritten that row with: the restore silently
    #: did nothing, and the version being rescued was destroyed on the way.
    #: Caught by `test_restoring_puts_the_text_back_and_keeps_the_one_it_replaced`.
    wanted_content = row.content or ""
    wanted_title = row.title
    _record_document_revision(session, document, source="restore")
    document.content = wanted_content
    if wanted_title:
        document.title = wanted_title
    document.updated_at = utcnow()
    log_action(session, "restored", "document", document.id, document.title[:80])
    session.commit()
    return _full(document, session)



class DocumentAiEditLogBody(BaseModel):
    """Recorded by the frontend right after it accepts an AI suggestion, 
    the write to `document.content` and the write to this changelog are two
    separate requests (accept can't itself know before_content once the
    document's already been saved), so the frontend sends both snapshots
    here rather than this route re-deriving "before" from a document it can
    no longer see the prior state of.
    """

    verb: Literal["edit", "write", "remove"] = "edit"
    instruction: str = Field(default="", max_length=500)
    selection: str = Field(default="", max_length=MAX_CONTENT)
    before_content: str = Field(max_length=MAX_CONTENT)
    after_content: str = Field(max_length=MAX_CONTENT)


class DocumentAiEditOut(BaseModel):
    id: int
    verb: str
    instruction: str
    selection_excerpt: str
    created_at: str


def _ai_edit_out(row: DocumentAiEdit) -> DocumentAiEditOut:
    return DocumentAiEditOut(
        id=row.id,
        verb=row.verb,
        instruction=row.instruction,
        selection_excerpt=row.selection_excerpt,
        created_at=row.created_at.isoformat(),
    )


@router.post("/{document_id}/ai-edit-log", status_code=201)
def record_ai_edit(
    document_id: int, body: DocumentAiEditLogBody, session: Session = Depends(get_session)
) -> DocumentAiEditOut:
    """Log one accepted AI edit, the changelog asked for directly. Prunes
    the oldest entries past `MAX_AI_EDIT_LOG_PER_DOCUMENT` so a heavily
    AI-edited document doesn't keep an unbounded pile of full-text
    snapshots forever."""
    _existing(session, document_id)  # 404s if the document is gone
    selection = body.selection.strip()
    excerpt = selection[:SELECTION_EXCERPT_CHARS]
    if len(selection) > SELECTION_EXCERPT_CHARS:
        excerpt += "…"
    row = DocumentAiEdit(
        document_id=document_id,
        verb=body.verb,
        instruction=body.instruction.strip(),
        selection_excerpt=excerpt,
        before_content=body.before_content,
        after_content=body.after_content,
    )
    session.add(row)
    session.flush()

    existing_ids = session.scalars(
        select(DocumentAiEdit.id)
        .where(DocumentAiEdit.document_id == document_id)
        .order_by(DocumentAiEdit.created_at.desc())
    ).all()
    stale_ids = existing_ids[MAX_AI_EDIT_LOG_PER_DOCUMENT:]
    if stale_ids:
        session.query(DocumentAiEdit).filter(DocumentAiEdit.id.in_(stale_ids)).delete(
            synchronize_session=False
        )

    session.commit()
    session.refresh(row)
    return _ai_edit_out(row)


@router.get("/{document_id}/ai-edit-log", response_model=list[DocumentAiEditOut])
def list_ai_edits(
    document_id: int, session: Session = Depends(get_session)
) -> list[DocumentAiEditOut]:
    """The changelog itself, newest first, asked for directly."""
    _existing(session, document_id)
    rows = session.scalars(
        select(DocumentAiEdit)
        .where(DocumentAiEdit.document_id == document_id)
        .order_by(DocumentAiEdit.created_at.desc())
    ).all()
    return [_ai_edit_out(row) for row in rows]


@router.post("/{document_id}/ai-edit-log/{entry_id}/revert")
def revert_ai_edit(document_id: int, entry_id: int, session: Session = Depends(get_session)) -> dict:
    """Restore the document to exactly how it read before this one AI edit
    - the "undone... after they are set" half of the changelog. Records a
    fresh "revert" entry of its own (before_content = the document's
    current, about-to-be-replaced text; after_content = what this entry is
    restoring) rather than deleting anything, so the changelog stays a
    truthful record of everything that happened, including the revert
    itself, and a revert can itself be reverted.
    """
    document = _existing(session, document_id)
    entry = deps.get_or_404(session, DocumentAiEdit, entry_id, "That AI edit could not be found.")
    if entry.document_id != document_id:
        raise HTTPException(status_code=404, detail="That AI edit could not be found.")

    reverted = DocumentAiEdit(
        document_id=document_id,
        verb="revert",
        instruction=f"Reverted: {entry.instruction}" if entry.instruction else "Reverted an AI edit",
        selection_excerpt=entry.selection_excerpt,
        before_content=document.content,
        after_content=entry.before_content,
    )
    document.content = entry.before_content
    document.updated_at = utcnow()
    session.add(reverted)
    session.commit()
    return _full(document, session)
