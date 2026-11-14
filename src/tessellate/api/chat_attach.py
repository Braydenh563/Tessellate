"""What a chat turn brings with it: the notes, documents, files and boards
attached to a question, the pictures in them read into text, and the notes a
tool read, offered as grounding.

Moved whole from `routes_chat.py` (audit AR3, gods-1101): the code is
unchanged, and `routes_chat` re-exports every name here that anything
reads, so `routes_chat._attached_notes` still works. Imports run one way, down the
layer list in `routes_chat.py`'s docstring, never back to `routes_chat`.
"""

from __future__ import annotations

import re
from datetime import timezone
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import starter_acts, vision_ocr
from tessellate.core import deps, docview
from tessellate.core.config import days_from_today
from tessellate.core.database import Attachment, Entry, MediaUpload
from tessellate.repo import documents as documents_repo
from tessellate.repo import uploads as uploads_repo
from tessellate.repo.documents import Document
from tessellate.core.imagesize import image_size
from tessellate.entry import manager
from tessellate.entry import manager_text


#: `/media/<filename>` as it appears inside note and document content, 
#: the only record a note keeps of a picture it holds.
_MEDIA_REF = re.compile(r"/media/([A-Za-z0-9._-]{1,200})")


def _grounding_candidates(
    session: Session, notes: list[dict], touched_note_ids: list[int]
) -> list[dict]:
    """The retrieval set plus every note a tool read this turn, as
    `{id, content}` rows for `ground_answer_sentences`.

    Same refusals as `_attached_notes`: a binned or private note never
    becomes a citation, whatever a tool result said. A tool reads a note
    through `_require_note`, which already refuses both, so this is the
    guard kept where the shape is kept (CLAUDE.md section 6, shape 3) rather
    than a second opinion. Documents are left out on purpose: a document id
    and a note id share a number space in the citation UI, which opens the
    *note* with that id.
    """
    #: A note's attached files count as what it says (INBOX 604, the owner:
    #: "it didnt intext number reference the referenced notes??"). Two of
    #: three sketches are one word and a picture: the answer described them
    #: from their captions, which the prompt carries (`_files_on`), and the
    #: grounding, reading `content` alone, found no note saying it.
    rows = [
        {**note, "content": f"{note.get('content') or ''}\n\n" + "\n".join(note["files"])}
        if note.get("files") else note
        for note in notes
        if note.get("id") is not None
    ]
    seen = {note["id"] for note in rows}
    for note_id in dict.fromkeys(touched_note_ids):
        if note_id in seen:
            continue
        entry = session.get(Entry, note_id)
        if entry is None or entry.is_deleted or entry.is_private:
            continue
        seen.add(note_id)
        rows.append({"id": entry.id, "content": entry.content})
    return rows


def _attached_notes(session: Session, note_ids: list[int]) -> list[dict]:
    """The notes the user picked, in the order they picked them.

    Binned notes are skipped: attaching one would quietly resurrect content the
    user has already thrown away. Private notes are skipped too, a client-
    supplied id list is the one path into this prompt that never went through
    `tools._require_note`, which is the only thing that otherwise refuses a
    private note (CLAUDE.md's own reminder of exactly this shape of bug). A
    forged/stale `note_ids` entry for a private note would otherwise put its
    id and category straight into what the model sees, private-notebook rule
    or not: no plaintext leaks (the content column is ciphertext either way,
    unreadable without `manager.readable_content`), but its existence should
    not be either.
    """
    found = []
    for note_id in dict.fromkeys(note_ids):  # de-duplicate, keep order
        entry = session.get(Entry, note_id)
        if entry is None or entry.is_deleted or entry.is_private:
            continue
        found.append(entry)
    return found


def _attached_documents(session: Session, document_ids: list[int]) -> list[Document]:
    """The documents the user attached by hand, in the order picked.

    No privacy/soft-delete filter here, unlike Entry, Document has neither
    field (core/database.py's own Document docstring: it's the long-form
    editor, not the notebook), so there's nothing to check beyond existing.
    """
    found = []
    for document_id in dict.fromkeys(document_ids):
        document = documents_repo.find(session, document_id)
        if document is not None:
            found.append(document)
    return found


#: How much of one attached file's text is given to the model. A file can be a
#: 300-page PDF, and every character here is resent on every round of the turn
#: -- the same budget reasoning `MEDIA_READING_CHARS` below records. Generous
#: enough for a report or a source file, bounded enough that four of them
#: cannot fill a small local model's whole context on their own.
ATTACHED_FILE_CHARS = 12000


#: The words of a title that do not name it: a kind, or too common to.
_TITLE_FILLER = frozenset(
    "a an the my of on in for and to with board boards whiteboard map maps mind mindmap document documents doc docs "
    "note notes untitled new copy".split()
)


#: `_TITLE_FILLER` stemmed as `_title_words` stems a title: built once, not per title (400 a question).
_FILLER_STEMS = frozenset(f.rstrip("s") for f in _TITLE_FILLER)

_KIND_SAID = re.compile(r"\b(?:(?:white)?boards?|mind ?maps?|maps?|documents?|docs?)\b", re.I)


def _title_words(text: str) -> set[str]:
    return {w.rstrip("s") for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 2}


def _named_sources(session: Session, question: str) -> tuple[list, list[int]]:
    """Documents, boards and maps the question names by their title (INBOX
    1357, class F: "what's on my revision board" found nothing, because the
    note search reads notes only). A title counts as named when every word
    of it that names it is in the question, and the question either says a
    kind ("board", "map", "document") or the title has two such words, so a
    one-word title does not match every question that uses the word. At most
    three; the newest first."""
    asked = _title_words(question)
    if not asked or len(question or "") > 300:
        return [], []
    says_kind = bool(_KIND_SAID.search(question or ""))

    def named(title: str) -> bool:
        words = _title_words(title) - _FILLER_STEMS
        return bool(words) and words <= asked and (says_kind or len(words) >= 2)

    documents = [
        d for d in documents_repo.recent(session, 400) if named(d.title or "")
    ][:3]
    boards = [
        e.id for e in session.scalars(
            select(Entry).where(Entry.is_board == True, Entry.is_deleted == False, Entry.is_private == False)  # noqa: E712
            .order_by(Entry.created_at.desc()).limit(400)
        ) if named(manager_text.extract_title(e.content) or "")
    ][:3]
    return documents, boards


def _attached_files(session: Session, file_ids: list[int]) -> list[dict]:
    """The Library files the user attached, as note-shaped context rows.

    Text is extracted here rather than stored: `core.docview.extract` is the
    same call `GET /files/{id}/text` makes, so an attached spreadsheet reaches
    the model as the table the Files tab would show, and a file whose text
    cannot be read (a scanned PDF with no reader available, an image) still
    reaches it as its name and kind rather than silently as nothing -- a
    filename is a real clue, and a chip in the transcript that corresponded to
    nothing at all is the failure mode `document_ids` already shipped once.
    """
    found: list[dict] = []
    uploads = deps.get_config().uploads_dir
    for file_id in dict.fromkeys(file_ids):
        attachment = session.get(Attachment, file_id)
        if attachment is None:
            continue
        body = ""
        try:
            viewed = docview.extract(
                uploads / attachment.stored_name,
                vision_reader=vision_ocr.pdf_reader_or_none(),
            )
            body = (viewed.text or "").strip()
        except Exception:  # noqa: BLE001 - an unreadable file is still worth naming
            body = ""
        if len(body) > ATTACHED_FILE_CHARS:
            body = body[:ATTACHED_FILE_CHARS] + "\n\n[…truncated]"
        header = f"File: {attachment.filename}"
        found.append(
            {
                "id": attachment.id,
                "content": f"{header}\n\n{body}" if body else f"{header}\n\n(no readable text)",
                "category": "File",
                "kind": "file",
                #: A file's words were written by somebody else (audit 1028
                #: E4): the turn starts tainted, so a write asks first.
                "from_outside": True,
                "attached": True,
                "connected": False,
                "match_info": None,
            }
        )
    return found


def _upload_is_sealed(session: Session, upload: MediaUpload, used: dict | None) -> bool:
    """A file only a locked private note holds, or one from another space."""
    from tessellate.core import media_gc

    space = session.info.get("workspace_id")
    if space and space != "all" and upload.workspace_id != space:
        return True
    if not (upload.in_private_note and manager.note_is_sealed(True)):
        return False
    return not (used if used is not None else media_gc.usage_map(session)[0]).get(upload.filename)


def _attached_media_files(session: Session, media_ids: list[int]) -> list[dict]:
    """Files uploaded in the Library (`MediaUpload` rows) as the same
    note-shaped context rows `_attached_files` makes (INBOX 1687: the Library's
    own uploads never reached chat Attach). Text comes from the same
    `docview.extract`; a sealed or other-space row is refused."""
    found: list[dict] = []
    media_dir = deps.get_config().data_dir / "media"
    for media_id in dict.fromkeys(media_ids):
        upload = uploads_repo.get(session, media_id)
        if upload is None or _upload_is_sealed(session, upload, None):
            continue
        try:
            body = (docview.extract(media_dir / upload.filename, vision_reader=vision_ocr.pdf_reader_or_none()).text or "").strip()
        except Exception:  # noqa: BLE001 - an unreadable file is still worth naming
            body = ""
        body = (body or (upload.ocr_text or "").strip())[:ATTACHED_FILE_CHARS]
        header = f"File: {upload.original_name}"
        found.append(
            {
                "id": upload.id,
                "content": f"{header}\n\n{body}" if body else f"{header}\n\n(no readable text)",
                "category": "File",
                "kind": "file",
                "from_outside": True,
                "attached": True,
                "connected": False,
                "match_info": None,
            }
        )
    return found


#: How much of one attached map's outline reaches the model.
#:
#: Smaller than `ATTACHED_FILE_CHARS` by an order of magnitude, on purpose: a
#: file is prose the model reads once, while an outline is *structure*, and
#: past a few hundred nodes the tree stops being context and becomes the whole
#: window: `read_mindmap`'s own `MAX_OUTLINE_NODES` makes the same call for
#: the same reason. Four maps at this cap is ~12k characters, the same ceiling
#: one attached file already has, and every character is resent on every round
#: of the turn.
ATTACHED_MAP_CHARS = 3000


def _attached_boards(session: Session, board_ids: list[int]) -> list[dict]:
    """The mind maps the user attached, as note-shaped context rows holding
    the same indented outline `read_mindmap` returns.

    **One renderer, not two.** The outline is built by calling the map tool's
    own helpers rather than by walking the tree again here: the agent, the
    export and this must not disagree about what a map says, and a second walk
    is how they come to (§9.1 lists three edge cases, a dangling parent, a
    ring, board scoping: that a second copy gets subtly differently).

    A private board is skipped in silence rather than refused. Attaching is a
    deliberate act, so this is not the guard that matters, but `read_mindmap`
    refuses a private board on the AI's behalf, and a hand-attached one
    reaching the model by a different door would make that guard decorative.
    """
    from tessellate.api.routes_whiteboard import _board_settings, _build_tree, _map_objects
    from tessellate.entry import manager_text

    found: list[dict] = []
    for board_id in dict.fromkeys(board_ids):
        entry = session.get(Entry, board_id)
        if entry is None or entry.is_deleted or entry.is_private:
            continue
        board_type, _layout = _board_settings(entry)
        title = manager_text.extract_title(entry.content) or f"Board {board_id}"
        objects = _map_objects(session, board_id)
        lines: list[str] = []
        _outline_into(_build_tree(session, objects), 0, lines)
        outline = "\n".join(lines) if lines else "(empty: no nodes yet)"
        if len(outline) > ATTACHED_MAP_CHARS:
            outline = outline[:ATTACHED_MAP_CHARS] + "\n[…truncated]"
        #: A board is said as a board (INBOX 744: "a board must say board").
        is_map = board_type == "map"
        found.append(
            {
                "id": board_id,
                "content": (
                    f"{'Mind map' if is_map else 'Board'}: {title}\n"
                    f"({len(objects)} {'node' if is_map else 'item'}{'' if len(objects) == 1 else 's'}"
                    + (f", laid out as a {board_type})" if is_map else ")") + f"\n\n{outline}"
                ),
                "category": "Mind map" if is_map else "Board",
                "kind": "map" if is_map else "board",
                #: Its own day, so a newer note on the same thing is not
                #: set aside for a board that says none (`supersede`).
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
                "attached": True,
                "connected": False,
                "match_info": None,
            }
        )
    return found


starter_acts.ATTACHED_BOARDS = _attached_boards


def _outline_into(nodes: list[dict], depth: int, out: list[str]) -> None:
    """The tree as indented text, two spaces per level, one node per line.

    The same shape `ai/tools/whiteboard.py::_outline_lines` produces, minus its
    `[id N]` markers: those exist so the *model* can name a node in the next
    tool call, and an attached map is context for a question, not a handle for
    an edit. Keeping the ids would spend a third of the budget on numbers
    nothing in this path can use.
    """
    for node in nodes:
        text = node["text"] or "(untitled)"
        #: A plain text box says nothing by its kind; a shape or a link does.
        mark = "" if node["kind"] in ("topic", "text") else f" [{node['kind']}]"
        out.append(f"{'  ' * depth}- {text}{mark}")
        _outline_into(node["children"], depth + 1, out)


#: At most this many pictures from one note are described to the model, and at
#: most this much of each reading. A note can hold a dozen scans; the readings
#: are a *hint* about what is in the note, not a second copy of the notebook,
#: and every character here is resent on every round of the turn.
MEDIA_READINGS_PER_NOTE = 4


#: 1,200, not 240 (INBOX 491): a screenshot of typed notes is the note, and
#: 240 characters of it is a line and a half. The note's own allowance
#: (`librarian.note_for_prompt`) still caps the whole, readings included.
MEDIA_READING_CHARS = 1200


#: A retrieved note whose own words (pictures' Markdown taken out) are this
#: short is mostly its pictures, so it gets their readings too (INBOX 491:
#: "What are the specific feature suggestions?" over a note that was one
#: screenshot of typed ideas reached the model as `![image.png](...)`, and
#: the answer said the note gave no specifics, though retrieval had found the
#: note *by* that picture's text). A note with words of its own stays as it
#: is, so ten search hits do not spend the budget on incidental pictures.
MOSTLY_PICTURE_CHARS = 200


_IMAGE_MARKDOWN = re.compile(r"!\[[^\]]*\]\([^)]*\)")


#: How many of the retrieved notes' pictures get words for their thumbnails.
PICTURE_ALTS_MAX = 40


PICTURE_ALT_CHARS = 160


def _picture_alts(session: Session, entries: list) -> dict[str, str]:
    """`/media/<file>` -> words that say what a retrieved note's picture is.

    INBOX 502 (the owner: "should the ai chats be able to pull images and
    sketches and render them in chat responses?? with accompanying references
    and hyperlinks??", decision taken: yes). An answer draws a grounded note's
    pictures as thumbnails beside its citation, and a thumbnail needs alt
    text: the caption the app already wrote, else the start of the text read
    off it. A lookup, never a pipeline, for `_media_readings`' reason: a
    picture with no reading yet gets its Markdown alt on the page instead.
    One query for every note, sent once with the results.
    """
    filenames = list(
        dict.fromkeys(name for entry in entries for name in _MEDIA_REF.findall(entry.content or ""))
    )[:PICTURE_ALTS_MAX]
    if not filenames:
        return {}
    alts = {}
    for upload in session.query(MediaUpload).filter(MediaUpload.filename.in_(filenames)).all():
        words = (upload.caption or "").strip() or " ".join(
            (upload.vision_ocr_text or upload.ocr_text or "").split()
        )
        if words:
            alts[f"/media/{upload.filename}"] = words[:PICTURE_ALT_CHARS]
    return alts


def _picture_sizes(entries: list) -> dict[str, list[int]]:
    """`/media/<file>` -> [width, height] for the same pictures, read from the
    file headers (`core/imagesize`), so an answer's figure (INBOX 526) holds
    its space before the image loads. A picture whose size is unknown is left
    out and the figure sizes itself."""
    names = list(
        dict.fromkeys(name for entry in entries for name in _MEDIA_REF.findall(entry.content or ""))
    )[:PICTURE_ALTS_MAX]
    media_dir = deps.get_config().data_dir / "media"
    sizes = {}
    for name in names:
        size = image_size(media_dir / Path(name).name)
        if size:
            sizes[f"/media/{name}"] = list(size)
    return sizes


def _mostly_pictures(content: str) -> bool:
    """True when a note is little more than its pictures."""
    if not _MEDIA_REF.search(content or ""):
        return False
    words = _IMAGE_MARKDOWN.sub("", content or "")
    return len(" ".join(words.split())) < MOSTLY_PICTURE_CHARS


def _note_dates(entry, zone) -> str:  # noqa: ANN001
    """"Wednesday 23 September 2026, 09:40", and ", edited ..." when it has been
    since: spelled out, the form `_long_date` explains (a small model reasons
    about weekdays better than ISO dates)."""

    def day(when):  # noqa: ANN001, ANN202
        if when is None:
            return ""
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        when = when.astimezone(zone)
        #: With the time: notes written the same day are told apart only by
        #: it (measured: the model picked the wrong one of two on one day).
        return f"{when:%A} {when.day} {when:%B %Y}, {when:%H:%M}"

    written = day(getattr(entry, "created_at", None))
    edited = day(getattr(entry, "edited_at", None))
    return f"{written}, edited {edited}" if edited and edited != written else written


def _time_words(dates, today) -> list[str]:  # noqa: ANN001
    """Each resolved time phrase in a note, worded for the model with how far
    it is from today: '"this Friday" meant Friday 25 September 2026, 8 days
    ago' (INBOX 441). The app resolves the phrase against the day the note was
    written; without this the model read "this Friday" as this week's."""
    out = []
    for item in dates:
        when = item.at
        day = f"{when:%A} {when.day} {when:%B %Y}"
        if item.precision == "minute":
            span = f"{day} at {when:%H:%M}"
        else:
            span = day if item.precision == "day" else f"the {item.precision} of {day}"
        out.append(f'"{item.phrase}" meant {span}, {days_from_today(when.date(), today)}')
    return out


def _one_line(text: str) -> str:
    """A picture's read text as one line, its lines joined by " / "."""
    return " / ".join(line.strip() for line in text.splitlines() if line.strip())


def _reading_line(upload: MediaUpload, filename: str, captions_only: bool) -> str:
    caption = (upload.caption or "").strip()
    text = "" if captions_only else (upload.vision_ocr_text or upload.ocr_text or "").strip()
    #: One line a picture: the text's own lines joined by " / " (INBOX
    #: 787: a reading over several lines broke the block, and the answer
    #: quoted `text in it: "Ranked Solo/Duo.` and stopped).
    text = _one_line(text)
    if not caption and not text:
        return ""
    parts = []
    if caption:
        parts.append(f"shows {caption[:MEDIA_READING_CHARS]}")
    if text:
        parts.append(f'text in it: "{text[:MEDIA_READING_CHARS]}"')
    name = (upload.original_name or filename).strip()
    return f"- {name}: {'; '.join(parts)}"


def _media_readings(session: Session, content: str, captions_only: bool = False) -> str:
    """What the app already knows about the pictures inside a note.

    Asked directly: *"if there is an image/sketch/file in that note, can the ai
    read the captions or ocr in those attachments if they already exist??"* It
    could not. A note's content carries `/media/<filename>` references and
    nothing else: so a note whose entire point was a photographed whiteboard
    reached the model as a sentence and a link, and the caption and OCR text
    the app had already generated for that exact image sat unread in the
    database two tables away.

    "If they already exist" is the operative half, and it is why this is a
    lookup and not a pipeline: nothing here generates a caption or runs vision
    OCR. Captioning is a background job that may not have run yet, may be off,
    or may have no model to run against, and a chat turn is the worst possible
    place to start one, it would block the answer on a second model load. A
    picture with no reading yet simply contributes nothing.
    """
    filenames = _MEDIA_REF.findall(content or "")
    if not filenames:
        return ""
    # De-duplicated, in the order they appear in the note, the same order the
    # reader sees them in, so "the second diagram" means the same thing to both.
    ordered = list(dict.fromkeys(filenames))[:MEDIA_READINGS_PER_NOTE]
    rows = {
        upload.filename: upload
        for upload in session.query(MediaUpload)
        .filter(MediaUpload.filename.in_(ordered))
        .all()
    }
    lines = []
    for filename in ordered:
        upload = rows.get(filename)
        if upload is None:
            continue
        line = _reading_line(upload, filename, captions_only)
        if line:
            lines.append(line)
    if not lines:
        return ""
    # Bracketed and labelled so the model can tell the app's reading of a
    # picture from the user's own words. It is evidence about the note, not
    # part of it.
    return "\n\n[Pictures in this note, as this app read them:\n" + "\n".join(lines) + "]"


#: A file's caption as the prompt gives it beside a retrieved note: one line,
#: enough for "a sketch of a bean" to be seen as a sketch, not the reading
#: `_attachment_readings` gives a note picked by hand.
FILE_CAPTION_CHARS = 160


def _files_on(session: Session, entry_ids: list[int]) -> dict[int, list[str]]:
    """Each note's attached files, "sketch.png (a blue bean drawn in pen)",
    in one query. Names and stored captions only: nothing is read from disk
    here, so ten notes cost one SELECT."""
    if not entry_ids:
        return {}
    out: dict[int, list[str]] = {}
    rows = (
        session.query(Attachment.entry_id, Attachment.filename, Attachment.caption)
        .filter(Attachment.entry_id.in_(entry_ids))
        .order_by(Attachment.id)
        .all()
    )
    for entry_id, filename, caption in rows:
        names = out.setdefault(entry_id, [])
        if len(names) >= MEDIA_READINGS_PER_NOTE:
            continue
        said = " ".join((caption or "").split())[:FILE_CAPTION_CHARS]
        names.append(f"{filename} ({said})" if said else filename)
    return out


_FILE_PICTURE = re.compile(r"^(.+\.(?:png|jpe?g|gif|webp|heic|avif|bmp)) \((.+)\)$", re.I)


def _file_pictures(files: list[str]) -> str:
    """A note's attached *picture files* with a caption (`_files_on`'s
    "sketch.png (a blue bean)"), as the same block an inline picture gets, so
    the composer reads them as pictures too (CHAT_PLAN phase 5 d): a note
    that holds its picture as a file was a filename in the prompt and no
    picture to the composer. Names and stored captions only, no disk read."""
    lines = []
    for line in files or []:
        found = _FILE_PICTURE.match(line.strip())
        if found and len(found.group(2).split()) >= 2:
            lines.append(f"- {found.group(1)}: shows {found.group(2)}")
    if not lines:
        return ""
    return "\n\n[Pictures in this note, as this app read them:\n" + "\n".join(lines) + "]"


def _attachment_readings(session: Session, entry_id: int) -> str:
    """What's inside the *files* attached to a note (PDFs, Office documents,
    code, plain text): `_media_readings` above's own sibling, and the gap it
    left. Asked about directly in the same spirit as that function's own
    report: a note whose entire point was an attached spreadsheet or PDF
    reached the model as a filename and nothing else, even when the note
    carrying it was hand-attached to the very question being asked.

    Same "attached notes get more, retrieved ones don't" budget
    `_media_readings` already uses, and read live rather than cached: unlike
    a caption or an OCR pass (a background job that may not have run yet),
    extraction here is `docview.extract` (core/docview.py): exactly what
    `/documents/import` and `/files/{id}/text` already pay synchronously per
    request: bounded to a handful of files on a note the user explicitly
    picked, not a background sweep over the whole notebook.
    """
    attachments = (
        session.query(Attachment)
        .filter(Attachment.entry_id == entry_id)
        .order_by(Attachment.id)
        .limit(MEDIA_READINGS_PER_NOTE)
        .all()
    )
    if not attachments:
        return ""
    uploads_dir = deps.get_config().uploads_dir
    lines = []
    for attachment in attachments:
        path = uploads_dir / attachment.stored_name
        if not path.is_file():
            continue
        try:
            viewed = docview.extract(path)
        except Exception:  # noqa: BLE001  # a bad file must not cost the answer
            continue
        text = viewed.text.strip()
        if not text:
            continue
        lines.append(f"- {attachment.filename}: {text[:MEDIA_READING_CHARS]}")
    if not lines:
        return ""
    return "\n\n[Files attached to this note, as this app read them:\n" + "\n".join(lines) + "]"
