"""Read an attached document the moment it lands, the way an image is read.

The owner, 2026-09-09, with a screenshot of a Files row that was a wall of
transcription and no description: "the files description needs to be an
actual description or summary of what the file is about and includes, not a
transcription", and, of the same tab, "the describe with ai button in the
files tab doesnt work ... no notification, no bg process, nothing."

An `Attachment` had no analysis of any kind on upload. A `MediaUpload` image
gets Tesseract and a caption on background threads the moment it is stored
(`core/ocr.py`, `ai/captioning.py`); a document got neither, so every row in
the Files sub-tab was a filename until somebody opened each one by hand. This
module is the missing half, and it deliberately mirrors
`captioning.caption_and_store`: it runs off the request, it never raises, and
it never rewrites a reading or a description that is already there.

Two steps, and they are independent on purpose. The text comes out of
`docview`, which is local, deterministic and needs no model, so it happens on
every machine. The description is a utility-model completion over that text
(`captioning.describe_document`), so it happens only where a model is
running, and its absence costs the reader nothing they had before.
"""

from __future__ import annotations

import logging
from pathlib import Path

from tessellate.core import jobs, paths, sealed_files, spacelock, vault

logger = logging.getLogger("tessellate.docreader")

#: Attachment id -> the session that attached it and the space the file was
#: in then, for a private space's file (L-world-class-381, SECURITY.md T28).
#: In memory only, taken by the run (or dropped when it fails), and dropped
#: when that session locks or ends: the persisted queue carries the id alone,
#: so after a restart (when no key is loaded anyway) a private file waits to
#: be read in the viewer.
_HANDED: dict[int, tuple[str, str]] = {}


def forget_sessions(tokens: list[str] | None = None) -> None:
    """Drop what these sessions handed over (every session's with None: a
    restart, a lock of every space)."""
    for aid, (token, _space) in list(_HANDED.items()):
        if tokens is None or token in tokens:
            _HANDED.pop(aid, None)


vault.ended_hooks.append(forget_sessions)
spacelock.shut_hooks.append(forget_sessions)

#: What this pass does not touch. An image attachment is the vision path's
#: job: `docview` would return nothing for it, and describing a picture from
#: its non-existent text would be a worse answer than no answer.
IMAGE_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".bmp", ".ico", ".svg", ".tiff", ".tif"}
)


def read_document_and_store(attachment_id: int) -> str | None:
    """Extract an attachment's text, then describe it. Returns the
    description, or None when there was nothing to do.

    Synchronous, so a manual call and the tests can drive it without waiting
    on a thread, exactly as `caption_and_store` is split from
    `caption_in_background`. What the session handed over goes when the run
    ends, however it ends.
    """
    try:
        return _read_and_store(attachment_id, _HANDED.get(attachment_id))
    finally:
        _HANDED.pop(attachment_id, None)


def _read_and_store(attachment_id: int, handed: tuple[str, str] | None) -> str | None:
    from tessellate.ai import captioning
    from tessellate.core import deps
    from tessellate.core.database import Attachment

    with deps.get_db().session() as session:
        row = session.get(Attachment, attachment_id)
        if row is None:
            return None  # deleted, or its upload never committed, before this ran
        if Path(row.filename or "").suffix.lower() in IMAGE_SUFFIXES:
            return None
        # Nothing to do, and saying so early keeps a re-upload of the same
        # file from paying for a model call to produce what is already there.
        if row.ocr_text and row.caption:
            return row.caption
        #: A `stored_name` reaches here through a database round trip. A name
        #: that escapes the uploads directory is a bug or an attack, and a
        #: background pass is not the place to act on either, so it declines
        #: and says so once.
        try:
            path = paths.contained(deps.get_config().uploads_dir, row.stored_name or "")
        except paths.OutsideFolder:
            logger.warning("refusing to read an attachment outside the uploads directory")
            return None
        if sealed_files.wanted(session, row.workspace_id):
            _read_private(session, row, path, handed)
            return None
        if not sealed_files.plain_file(path):
            return None

        if not row.ocr_text:
            text = _extract(path, row.filename)
            if text:
                _fill_if_empty(session, Attachment, attachment_id, "ocr_text", text)
                session.refresh(row)

        if row.caption:
            return row.caption
        readable = (row.ocr_text or "").strip()
        if not readable:
            return None
        jobs.check_stop()  # Stop pressed after the text was kept, before the model call
        ollama = deps.get_ollama()
        if not ollama.is_running():
            # Not a failure worth logging on every upload: a notebook with no
            # model running would fill the log with the same expected line.
            return None
        try:
            models = deps.get_model_manager()
            described = captioning.describe_document(readable, models, ollama)
        except Exception:
            logger.info("could not describe %s", row.filename, exc_info=True)
            return None
        if not described:
            return None
        #: **Written only if the field is still empty when the answer lands.**
        #: The model call takes seconds, and a description typed in that time
        #: was overwritten by the late automatic one (caught by CI, where the
        #: upload's own background read raced the test's hand-written value).
        #: The check has to be in the write itself: reading the row again
        #: first would leave the same race a step narrower.
        wrote = _fill_if_empty(
            session,
            Attachment,
            attachment_id,
            "caption",
            described,
            caption_model=models.utility_model(),
            caption_edited=False,
        )
        session.refresh(row)
        return described if wrote else row.caption


def _extract(path: Path, filename: str | None) -> str:
    from tessellate.core import docview

    try:
        return (docview.extract(path).text or "").strip()
    except Exception:
        # A malformed document is a normal thing to be handed, and a
        # traceback out of a background thread would take the upload's
        # own log entry with it.
        logger.info("could not read %s", filename, exc_info=True)
        return ""


def _read_private(session, row, path: Path, handed: tuple[str, str] | None) -> None:  # noqa: ANN001
    """A private space's file: its text read as the session that attached it,
    only while that session has the space open, and written through the ORM
    so the sealing hook encrypts it (a bulk `update` would store it plain).
    Never described: the AI reads a private space only from a chat opened
    inside it (SECURITY.md T10). With no session it waits for the viewer.
    The session is bound to the space the file was in when it was handed
    over: a token handed for a file of space A reads nothing of space B."""
    token, space = handed or (None, None)
    if token is None or space != row.workspace_id or row.ocr_text:
        return
    try:
        with sealed_files.for_background(path, token) as (copy, check):
            text = _extract(copy, row.filename)
            if text:
                session.refresh(row)
                if not row.ocr_text:
                    row.ocr_text = text
                    check()  # immediately before the commit, after the refresh
                    session.commit()
    except sealed_files.SealedError:
        logger.info("a private space's file was left unread: the space closed")


def _fill_if_empty(session, model, row_id: int, field: str, value: str, **also) -> bool:  # noqa: ANN001
    """Set `field` (and `also`) only where `field` is still NULL or empty. True if it wrote."""
    from sqlalchemy import or_, update

    column = getattr(model, field)
    result = session.execute(
        update(model)
        .where(model.id == row_id, or_(column.is_(None), column == ""))
        .values({field: value, **also})
    )
    session.commit()
    return bool(result.rowcount)


def read_in_background(attachment_id: int) -> None:
    """Fire and forget, so `POST /entries/{id}/files` answers at once.

    A document extraction is fast and a model round trip is not, and neither
    is anything the person who just attached a file should wait behind.
    """
    token = vault.requester()
    space = _space_of(attachment_id) if token is not None else None
    if token is not None and space is not None:
        _HANDED[attachment_id] = (token, space)
    jobs.enqueue("document", read_document_and_store, attachment_id)


def _space_of(attachment_id: int) -> str | None:
    from tessellate.core import deps
    from tessellate.core.database import Attachment

    with deps.get_db().session() as session:
        row = session.get(Attachment, attachment_id)
        return row.workspace_id if row is not None else None
