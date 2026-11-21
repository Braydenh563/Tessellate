"""Editing a note: what a save writes and sets going (decision 55, L-world-class-632).

The route keeps the guards that need the request (`If-Match`, the stale-text
and stale-tags refusals, which answer 412 or 409 with the note as it is now)
and the response; the write itself is here and imports nothing from the API
layer. `body` is the `EntryUpdate` the route parsed, read by attribute.
`tests/test_note_editing_api.py` and `tests/test_entry_editing.py` hold it.
"""

from __future__ import annotations

import contextlib
import logging
import re
from types import SimpleNamespace

from sqlalchemy import delete as sa_delete
from sqlalchemy.orm import Session

from tessellate.core import events
from tessellate.core.database import EmbeddingRecord
from tessellate.core.events import ACTOR_USER_AND_AI
from tessellate.entry import capture, filing_background, manager, manager_text, manager_wiki, private_space

logger = logging.getLogger("tessellate.api.entries")


def stored_form(entry, text: str, session: Session | None = None) -> str:  # noqa: ANN001
    """A past version's text, in the form this note stores it in now.

    A private note's restored text marks the pictures it embeds, as an edit
    does (SEC-A2): a picture only an older version used was served locked."""
    stored = manager_text.content_for_entry(entry, text or "")
    if stored is None:
        raise private_space.NeedsKey("Unlock the app first: this version needs the encryption key.")
    if session is not None and entry.is_private:
        manager_text.flag_private_media(session, readable(stored))
    return stored


def readable(content: str) -> str:
    """Decrypt stored content for display, the same way a note itself is.

    `manager.readable_content` reads one attribute, so an event's stored
    content can borrow it without a row to hang it on."""
    return manager_text.readable_content(SimpleNamespace(content=content or ""))


def _content_change(entry, body) -> tuple[bool, str | None]:  # noqa: ANN001
    """`(changed, text to store)`; the text is None when nothing is written."""
    new_content = body.content
    if entry.is_private and body.content is not None:
        #: A private note's column holds ciphertext, so "changed" is judged on
        #: the text the editor saw, and the new text is stored encrypted: it
        #: was written plain, with the note still flagged private, and sat in
        #: `entries.content` and the full-text index in the clear (found
        #: 2026-10-04 by scanning a data dir for a private note's words).
        content_changed = body.content != manager_text.readable_content(entry)
        new_content = stored_form(entry, body.content) if content_changed else None
    else:
        content_changed = body.content is not None and body.content != entry.content
    return content_changed, new_content


def _after_content_edit(session: Session, entry, text: str | None) -> None:  # noqa: ANN001
    """What an edited text sets going: the stale vector goes, links resolve, media settles."""
    # The old vector describes the old text, refresh it, best effort.
    try:
        session.execute(sa_delete(EmbeddingRecord).where(EmbeddingRecord.entry_id == entry.id))
        session.commit()
    except Exception:  # noqa: BLE001  # never fail the edit over the index
        logging.getLogger("tessellate.embeddings").warning(
            "couldn't clear the stale vector for entry %s", entry.id, exc_info=True
        )
        session.rollback()
    else:
        #: Off the request (audit 2026-10-05, ARCH-02 step 5): an edit
        #: used to embed here, a model call of 200 to 400 ms on a real
        #: embedder before the editor's save returned. The stale vector
        #: is already gone, so until the job runs the note is found by
        #: its words, as a note saved with the embedder off is.
        filing_background._queue_embedding(entry)
    # Editing a note can introduce new [[links]]; resolve those too.
    try:
        manager_wiki.sync_wiki_links(session, entry)
        manager_wiki.resolve_links_to(session, entry)
        session.commit()
    except Exception:
        session.rollback()
        logger.warning("couldn't sync wiki links for entry %s", entry.id, exc_info=True)
    # Same "committed" trigger point as a new note, an edit can be
    # the first time an image the note already referenced actually
    # gets saved (a staged upload attached, then the note edited to
    # include it, rather than created with it already there).
    capture.process_committed_media(session, text)


def _apply_flags(session: Session, entry, body) -> None:  # noqa: ANN001
    """Colour (null clears it) and draft from an edit, each saved when it moves."""
    if "colour" in body.model_fields_set and body.colour != entry.colour:
        entry.colour = body.colour
        session.commit()
    if body.is_draft is not None and body.is_draft != entry.is_draft:
        entry.is_draft = body.is_draft
        session.commit()


def _wiki_rename(session: Session, entry, old_name: str) -> dict | None:  # noqa: ANN001
    """Set when the opening line changed and other notes link to the old name."""
    if not old_name or manager_wiki.wiki_opening(entry.content) == old_name:
        return None
    # Spelt as the holders wrote it, the opening line as the note does.
    first = (entry.content or "").strip().split("\n", 1)[0]
    new_name = re.sub(r"^\s{0,3}#{1,6}\s+", "", first).strip()
    holders = manager_wiki.wiki_holders(session, entry, old_name)
    if not holders or not new_name:
        return None
    spelt = re.search(r"\[\[\s*(" + re.escape(old_name) + r")", holders[0].content, re.IGNORECASE)
    return {"old": spelt.group(1) if spelt else old_name, "new": new_name, "notes": len(holders)}


def update(session: Session, entry, body) -> dict | None:  # noqa: ANN001
    """Write an edit: text, tags, category, pin, colour and draft, with a
    revision of what it replaces and the follow-up work an edited text needs.
    Returns the rename offer when the opening line moved and others link to
    the old name. Raises `private_space.NeedsKey` for a private note's text
    when the key is not loaded."""
    content_changed, new_content = _content_change(entry, body)
    tags_changed = body.tags is not None and body.tags != manager.entry_tags(entry)
    #: The note's [[name]] before the edit (a private note is never a target).
    old_name = manager_wiki.wiki_opening(entry.content) if content_changed and not entry.is_private else ""
    #: A save that carries an applied Atlas suggestion is both of theirs.
    with events.acting_as(ACTOR_USER_AND_AI) if body.ai_assisted else contextlib.nullcontext():
        # Snapshot BEFORE the change, so the newest revision is always the
        # version being replaced rather than the one replacing it.
        if content_changed or tags_changed:
            manager.record_revision(session, entry)
        manager.update_entry(session, entry, content=new_content, category_name=body.category, tags=body.tags)
    if body.pinned is not None and body.pinned != entry.pinned:
        entry.pinned = body.pinned
        manager.log_action(session, "edited", "entry", entry.id, "pinned" if body.pinned else "unpinned")
        session.commit()
    _apply_flags(session, entry, body)
    if content_changed:
        _after_content_edit(session, entry, body.content)
    return _wiki_rename(session, entry, old_name)
