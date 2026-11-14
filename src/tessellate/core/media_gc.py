"""Reconciles `/media/` uploads against what still references them.

ROADMAP.md item 20a: `MediaUpload` (added for the Library gallery) tracks
every file `/media/upload` has ever produced, but nothing before this
checked a row against whether any live note, document, whiteboard image
object or saved chat turn still points at it, pasting over an image in a
note, or deleting the note entirely, leaves the file on disk with only a
manual, one-at-a-time `DELETE /media/{id}` to ever find it again.

The one thing this has to get right, and would rather be slow about than
wrong about: a private note's content is encrypted at rest, so an image
referenced only inside a private note that's currently locked cannot be
ruled out as "still referenced", it can only be *not checked*. Rather than
treat "couldn't check" as "not referenced" (which would eventually delete a
real attachment out from under a locked note), any private note this pass
can't read makes the whole pass refuse to delete anything, not just skip
that one note.
"""

from __future__ import annotations

import json

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from tessellate.core import reading_bin
from tessellate.core.database import BoardLibraryItem, Conversation, Document, Entry, MediaUpload, WhiteboardObject
from tessellate.entry import manager_text

# Same shape routes_whiteboard.py's own MEDIA_URL_RE validates on the way in, 
# kept independent (not imported) since this only ever reads, never resolves
# a path from user input.
_MEDIA_NAME_RE = manager_text.MEDIA_NAME_RE


def referenced_names(text: str) -> set[str]:
    """Every `/media/<filename>` this text mentions. Public (not
    module-private): `core/media_process.py` reuses it to answer the same
    underlying question, "which uploads does this text reference", when
    deciding what to run OCR/captioning/vision-OCR on at save time, not
    just when deciding what counts as orphaned."""
    return set(_MEDIA_NAME_RE.findall(text or ""))


def _could_name_a_file(column):
    """A WHERE clause for the rows whose text could mention an upload.

    `referenced_names` finds nothing in text without a literal `/media/` in
    it, so a row without one cannot contribute, and loading it (as an object,
    text and all) only to run a regex over it is the whole cost of the
    Library's gallery on a big notebook: 177 ms on 5,000 notes with no uploads
    (the performance pass, 2026-10-03). SQLite's LIKE folds ASCII case, so
    this keeps a superset of what the regex reads. Ciphertext is kept too: a
    private note's stored text is `mmenc1:...`, which says nothing until it is
    opened, and the pass below must open it, or note that it could not.
    """
    from tessellate.core import crypto

    return or_(column.like("%/media/%"), column.startswith(crypto.PREFIX, autoescape=True))


def _referenced_filenames(session: Session) -> tuple[set[str], bool]:
    """Every filename this pass can actually see referenced, plus whether a
    locked private note forced it to skip a check.
    """
    from tessellate.core import crypto, vault

    referenced: set[str] = set()
    skipped_private = False

    #: **Every object on every board, not only the ones whose kind is
    #: `image`.** An image object was the only thing on a board that could
    #: point at an upload when this was written, and it stopped being true the
    #: moment a mind map topic could carry a picture (MINDMAP_PLAN.md §12.1
    #: item 2's fourth, `data.image`): a filter on `kind` would have left every
    #: picture topic's upload counted as an orphan, and "clean up orphaned
    #: media" would then delete the file out from under a topic that is drawing
    #: it. `referenced_names` reads the `data` blob as text and takes the
    #: `/media/...` names out of it, so it does not care which key holds one,
    #: and a kind added later is covered by having been added.
    for obj in session.scalars(select(WhiteboardObject).where(_could_name_a_file(WhiteboardObject.data))):
        referenced.update(referenced_names(obj.data))

    #: A board's background image lives in its settings (WHITEBOARD_PLAN
    #: decision 24, FEAT-06): before this, setting one made the upload an
    #: orphan, and "clean up orphaned media" deleted it.
    for entry in session.scalars(
        select(Entry).where(Entry.is_deleted == False, _could_name_a_file(Entry.board_settings))  # noqa: E712
    ):
        referenced.update(referenced_names(entry.board_settings or ""))

    #: A picture saved in the board library (decision 25), the bin's too: an
    #: item there can be restored or placed, and its picture has to be there.
    for item in session.scalars(select(BoardLibraryItem)):
        referenced.update(referenced_names(json.dumps(item.payload or {})))

    for doc in session.scalars(select(Document).where(_could_name_a_file(Document.content))):
        referenced.update(referenced_names(doc.content))

    for entry in session.scalars(
        select(Entry).where(Entry.is_deleted == False, _could_name_a_file(Entry.content))  # noqa: E712
    ):
        if entry.is_private and crypto.is_encrypted(entry.content) and vault.key() is None:
            skipped_private = True
            continue
        referenced.update(referenced_names(manager_text.readable_content(entry)))

    return referenced, skipped_private


def _conversation_referenced_ids(session: Session) -> set[int]:
    """Every MediaUpload id a saved chat turn still attaches.

    A conversation stores its images as ids
    (`routes_conversations.TurnBody.image_media_ids`, on the user message),
    not as inline `/media/…` markdown text: so `_referenced_filenames`
    above, which only ever looks for that text, can never see a chat's own
    images no matter how thoroughly it scans notes, documents and
    whiteboard content. Without this, `find_orphaned_media` would call
    every image ever attached to a chat message "orphaned", sent or not,
    and `delete_orphaned_media` would delete its file out from under a
    conversation someone can open and read.
    """
    ids: set[int] = set()
    for conversation in session.scalars(select(Conversation)):
        try:
            messages = json.loads(conversation.messages)
        except ValueError:
            continue
        for message in messages:
            #: A Library file sent with a message is kept the same way (INBOX 1687).
            for media_id in [*(message.get("image_media_ids") or []), *(message.get("media_file_ids") or [])]:
                if isinstance(media_id, int):
                    ids.add(media_id)
    return ids


def _board_uses(session: Session, note) -> None:  # noqa: ANN001
    #: Every object, for the reason `_referenced_filenames` gives above: a map
    #: topic carrying a picture is a use of that upload, and a screen that says
    #: "nothing points at this file" while a topic is drawing it is the screen
    #: that offers to delete it.
    for obj in session.scalars(select(WhiteboardObject).where(_could_name_a_file(WhiteboardObject.data))):
        for name in referenced_names(obj.data):
            note(name, "board", obj.board_id, "Whiteboard")

    for entry in session.scalars(
        select(Entry).where(Entry.is_deleted == False, _could_name_a_file(Entry.board_settings))  # noqa: E712
    ):
        for name in referenced_names(entry.board_settings or ""):
            note(name, "board", entry.id, "Board background")

    for item in session.scalars(select(BoardLibraryItem)):
        for name in referenced_names(json.dumps(item.payload or {})):
            note(name, "library", item.id, f"Board library: {item.name}")


def _note_uses(session: Session, note) -> bool:  # noqa: ANN001
    """Record each note's media uses; True when a locked private note was skipped."""
    from tessellate.core import crypto, vault

    skipped_private = False
    for entry in session.scalars(
        select(Entry).where(Entry.is_deleted == False, _could_name_a_file(Entry.content))  # noqa: E712
    ):
        if entry.is_private and crypto.is_encrypted(entry.content) and vault.key() is None:
            skipped_private = True
            continue
        content = manager_text.readable_content(entry)
        for name in referenced_names(content):
            # **A private note contributes the link but never its words.**
            # The label is rendered in the Library's file gallery, and the
            # first line of a private note is exactly the kind of thing that
            # must not appear on a wall of thumbnails anyone glancing at the
            # screen can read. The app already has this convention: a
            # document's linked-notes list (`routes_documents._linked_notes`)
            # sends `is_private` and the UI draws a lock instead of the
            # preview. Same answer here: the connection is still shown and
            # still clickable, because knowing *that* a file is in use is what
            # stops it being deleted; only the wording is withheld.
            if entry.is_private:
                note(name, "note", entry.id, "Private note")
                # Notes made private before the flag existed are marked the
                # first time they are read here with the vault open.
                manager_text.flag_private_media(session, content)
                continue
            # `plain_label`, not the raw first line: a chip cannot render
            # markdown, and one that tries shows `# Title ![alt](/media/…)`
            # verbatim: reported exactly that way.
            note(name, "note", entry.id, manager_text.plain_label(content))
    return skipped_private


def usage_map(session: Session) -> tuple[dict[str, list[dict]], bool]:
    """The reverse of `_referenced_filenames`: filename -> where it is used.

    The Library's Files & Images tab showed a thumbnail, a filename and two
    empty prompts, and nothing about what the file was *for*, so a gallery of
    sixty uploads could not answer the only question anyone brings to it,
    which is "where did this come from and what is it attached to?". Reported
    as the Files tab needing to be "properly integrated" rather than
    redesigned.

    Built from `referenced_names` rather than a second scanner, so this and
    the orphan check can never disagree about what "referenced" means: an
    important property, because a file this says is used and the GC says is
    orphaned would be a file the GC deletes out from under a live note.

    Returns `(map, skipped_private)`. `skipped_private` carries the same
    meaning it does for the orphan pass: a locked private note could not be
    read, so the answer is incomplete rather than negative, and the UI says so
    instead of claiming a file is unused.
    """
    used: dict[str, list[dict]] = {}

    def note(name: str, kind: str, ident, label: str) -> None:
        used.setdefault(name, []).append(
            {"kind": kind, "id": ident, "label": (label or "").strip()[:80] or "Untitled"}
        )

    _board_uses(session, note)
    for doc in session.scalars(select(Document).where(_could_name_a_file(Document.content))):
        for name in referenced_names(doc.content):
            note(name, "document", doc.id, doc.title)
    skipped_private = _note_uses(session, note)

    return used, skipped_private


def find_orphaned_media(session: Session) -> tuple[list[MediaUpload], bool]:
    """Uploads no live note, document, whiteboard object or saved chat turn
    still points at.

    Returns `(orphans, skipped_private)`. When `skipped_private` is True,
    at least one private note's content could not be checked (vault
    locked): the list is not exhaustive, and `delete_orphaned_media`
    refuses to act on it.
    """
    referenced, skipped_private = _referenced_filenames(session)
    referenced_ids = _conversation_referenced_ids(session)
    uploads = session.scalars(select(MediaUpload)).all()
    orphans = [
        u for u in uploads if u.filename not in referenced and u.id not in referenced_ids
    ]
    return orphans, skipped_private


def delete_orphaned_media(session: Session, media_dir) -> tuple[list[dict], bool]:
    """Deletes every currently-orphaned upload's file and tracking row.

    Returns `(deleted, skipped_private)`, `deleted` holds one
    `{"id", "filename", "original_name"}` dict per row removed, captured
    *before* the delete (a row's fields aren't safely readable through the
    ORM object once `session.commit()` has expired it). Refuses outright
    (deletes nothing) when a locked private note made the reference check
    incomplete: leaving a genuinely orphaned file on disk a while longer
    is the safe side of that trade; deleting one a locked note still
    references is not.
    """
    orphans, skipped_private = find_orphaned_media(session)
    if skipped_private:
        return [], True

    media_dir = media_dir.resolve()
    deleted = [
        {"id": u.id, "filename": u.filename, "original_name": u.original_name}
        for u in orphans
    ]
    for upload in orphans:
        candidate = (media_dir / upload.filename).resolve()
        if candidate.is_relative_to(media_dir):
            candidate.unlink(missing_ok=True)
        session.delete(upload)
    reading_bin.forget_page_reads(session, "upload", [u["id"] for u in deleted])
    session.commit()
    return deleted, False


def sealed_only(session: Session, filename: str) -> bool:
    """Whether this upload's only users are locked private notes: a private
    note embeds it, no readable one does, and the vault is shut to this caller."""
    from tessellate.core import vault

    if vault.key() is not None:
        return False
    flagged = session.scalar(select(MediaUpload.in_private_note).where(MediaUpload.filename == filename))
    if not flagged:
        return False
    used, _incomplete = usage_map(session)
    return not used.get(filename)
