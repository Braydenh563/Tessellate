"""Capture: how a new note is made (decision 55, L-world-class-632).

`create` runs everything a save does up to the response: the filing decision,
the commit, tag suggestions, the embedding, wiki links, documents, media. The
route in `api/routes_entries.py` parses the request, calls `create`, shapes the
answer, and then calls `start_background`: that is last on purpose, so the
filing thread can never race the commit that makes the note visible to its
own session. A body here is an `api.schemas.EntryCreate` (this module never
imports the API layer).
"""

from __future__ import annotations

import dataclasses
import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tessellate.ai import janitor
from tessellate.core import companion_events, deps
from tessellate.core.database import Entry
from tessellate.entry import (
    filing_background,
    manager,
    manager_private,
    manager_wiki,
    private_space,
    tag_suggestions,
)
from tessellate.entry import meetings as meeting_shape
from tessellate.entry import properties as note_properties
from tessellate.entry.tagnames import inline_tags, normalise_tags
from tessellate.repo import documents as documents_repo

logger = logging.getLogger("tessellate.api.entries")


@dataclasses.dataclass
class Created:
    """A save's result: the note, who filed it, and what to start once it is shaped."""

    entry: Entry
    filed_by: str | None
    #: The saved note that says almost the same thing, with its score; None while filing is deferred.
    similar: tuple[Entry, float] | None
    #: False for a resend of a save already delivered: nothing more to start.
    fresh: bool
    defer: bool
    client_key: str | None


def process_committed_media(session: Session, plaintext_content: str) -> None:
    """Trigger OCR/captioning/vision-OCR for every `/media/…` upload this
    (plaintext, pre-encryption) note content references, see
    core/media_process.py's own docstring for why this fires here rather
    than on upload. Best-effort: an image reference to an upload that's
    already gone, or one already processed, is a fast no-op either way."""
    from tessellate.core import media_process

    media_process.process_referenced_uploads(
        session, deps.get_config().data_dir / "media", plaintext_content
    )


def _mark_new_entry(entry, body, filed_by: str | None) -> None:  # noqa: ANN001
    """The flags a new note carries from its request: who filed it, draft,
    map topic, colour and the page it was clipped from."""
    if filed_by == "user":
        entry.user_filed = True
    if body.is_draft:
        entry.is_draft = True
    if body.map_topic:
        entry.map_topic = True
    if body.colour:
        entry.colour = body.colour
    if body.source_url:
        entry.source_url = body.source_url
        entry.source_title = body.source_title


def _decide_filing(session: Session, body, parent) -> tuple[str, int, str, bool]:  # noqa: ANN001
    """`(category, confidence, filed_by, defer)` for a new note."""
    # Filed in the background only when nothing else already decides the category: with an
    # explicit `category` or a `parent_id` there is no model call to wait
    # for, so deferring would add a round trip and buy nothing.
    defer = body.defer_filing and not body.category and parent is None

    if body.category:
        # Guided mode: the user chose: the AI stays out of it entirely.
        category, confidence, filed_by = body.category, 100, "user"
    elif parent is not None:
        # Continuing a thread: a train of thought stays in its
        # parent's category: predictable beats clever here.
        category = manager.category_name_for(session, parent)
        confidence, filed_by = 75, "thread"
    elif defer:
        # Saved to disk now, filed a moment later, see
        # `_file_entry_in_background`. Uncategorised is a real, visible
        # holding place rather than a null, so a note whose filing thread
        # dies with the process is still exactly where a user can find it.
        category, confidence, filed_by = manager.UNCATEGORISED, 0, "pending"
    else:
        #: The wait is bounded like the background pass's (INBOX 1313): this
        #: request holds a database connection while the model thinks, and the
        #: unbounded wait it had (three minutes) let twenty at once fill the pool.
        category, confidence, filed_by = filing_background._file_entry_now(
            session, body.content, model_deadline=janitor.filing_deadline(), release_session=True
        )
    return category, confidence, filed_by, defer


def _new_note_text(session: Session, body) -> tuple[str, list[str]]:
    """The content (a type's fields first) and tags (inline, meeting) a new note is saved with."""
    tags = normalise_tags([*body.tags, *inline_tags(body.content)]) if body.inline_tags else body.tags
    content = body.content
    if body.note_type:
        #: KG4: a new note of a type starts with the type's fields.
        content = note_properties.with_type_fields(session, content, body.note_type, deps.get_config())
    #: A note typed Meeting, however it was made (its type's New note, the
    #: Capture template, an import), is a meeting everywhere meetings are
    #: listed (INBOX 644): the Library's chip and the Notes sidebar's row
    #: count the tag, which the type alone never carried.
    if meeting_shape.is_meeting(content) and meeting_shape.MEETING_TAG not in {t.lower() for t in tags}:
        tags = normalise_tags([*tags, meeting_shape.MEETING_TAG])
    return content, tags


def _finish_new_entry(session: Session, entry, body, defer: bool) -> None:  # noqa: ANN001
    """Everything after the commit that must never cost someone their note."""
    if not defer:
        #: Filed already: keep its tag suggestions now, from the notebook's
        #: own tags (no second model call on the request; a note filed in the background
        #: gets the model's in the background pass).
        try:
            tag_suggestions.keep_suggestions(session, entry, None)
            session.commit()
        except Exception:
            logger.warning("couldn't keep tag suggestions for a new note", exc_info=True)
            session.rollback()

    # Best effort: a failed embedding only means this entry is invisible
    # to semantic search until re-indexed, never a failed save. It is logged
    # rather than swallowed, so a backend that has stopped working shows up in
    # Settings, Logs instead of quietly shrinking search.
    #
    # Skipped when filing runs in the background: the same background thread does it,
    # right before the near-duplicate search that depends on it.
    if not defer:
        deps.store_quietly(session, entry)

    # [[wiki links]] become real links. Best effort for the same reason: a
    # link that can't be resolved must never cost someone their note.
    try:
        manager_wiki.sync_wiki_links(session, entry)
        manager_wiki.resolve_links_to(session, entry)
        session.commit()
    except Exception:
        session.rollback()
        logger.warning("couldn't sync wiki links for entry %s", entry.id, exc_info=True)

    # Documents this note belongs with, attached as it is saved. A document
    # that has since been deleted is skipped rather than refused: the note is
    # the thing being saved, and losing it over a stale id would be absurd.
    for document_id in dict.fromkeys(body.document_ids):
        if documents_repo.find(session, document_id) is not None:
            manager.link_document(session, document_id, entry.id)

    # A note is one of the three "committed" moments core/media_process.py
    # waits for (asked for directly: OCR/captioning/vision-OCR must not run
    # on a staged upload that never made it into a saved note). `body.content`
    # here, never `entry.content`, is deliberate: a private note's stored
    # content may already be encrypted at rest, and this is the plaintext
    # that was actually just submitted, before that happens.
    process_committed_media(session, body.content)


def _starts_sealed(session: Session, body) -> tuple[bool, bool]:
    """INBOX 1695: (sealed, sealed by this note's own ask rather than its space)."""
    if private_space.is_private_space(session, session.info.get("workspace_id")):
        return True, False
    try:
        ask = private_space.starts_private(body.private)
    except private_space.VaultLocked as locked:
        raise private_space.NeedsKey("Unlock the app first: the encryption key isn't loaded.") from locked
    return ask, ask


def note_total(session: Session) -> int:
    """The notes the dashboard counts (`/insights/stats` `total_entries`): not deleted, drafts or boards."""
    return session.scalar(
        select(func.count(Entry.id)).where(Entry.is_deleted == False, Entry.is_draft == False, Entry.is_board == False)  # noqa: E712
    ) or 0


def _cheer_note_count(session: Session, entry: Entry) -> None:
    """Passing a round count is a cheer on the desk: a kind and a time (P7). A draft is no note yet, so the count moved not."""
    if not entry.is_draft:
        companion_events.counted(note_total(session))


def create(session: Session, body) -> Created:  # noqa: ANN001
    """Save a new note from a request body (the response is the route's)."""
    earlier = filing_background._already_delivered(session, body.client_key)
    if earlier is not None:
        return Created(earlier, None, None, False, False, body.client_key)
    parent = deps.get_or_404(session, Entry, body.parent_id, "That note could not be found.") if body.parent_id is not None else None
    sealed, by_ask = _starts_sealed(session, body)
    if sealed:
        # INBOX 1727: the model never reads a private space's note to file it.
        category, confidence, filed_by, defer = body.category or manager.UNCATEGORISED, 100, "user", False
    else:
        category, confidence, filed_by, defer = _decide_filing(session, body, parent)
    content, tags = _new_note_text(session, body)
    try:
        entry = manager.create_entry(
            session,
            content=content,
            category_name=category,
            tags=tags,
            ai_confidence=confidence,
            client_key=body.client_key,
        )
    except IntegrityError:
        # Two resends of one save at once: the other one won the unique
        # index on `client_key`, so its note is this save's answer.
        session.rollback()
        earlier = filing_background._already_delivered(session, body.client_key) if body.client_key else None
        if earlier is None:
            raise
        return Created(earlier, None, None, False, False, body.client_key)
    if parent is not None:
        entry.parent_id = parent.id
    _mark_new_entry(entry, body, filed_by)
    if by_ask:
        manager_private.set_private(session, entry, True)  # sealed before the first commit
    if defer:
        entry.filing_state = "pending"
    elif janitor.settled_state(filed_by) != "done":
        entry.filing_state = janitor.settled_state(filed_by)
    session.commit()  # a note in a private space is sealed on the way in (`database._seal_private_space_joins`)
    if sealed:
        manager_private.scrub_private_leftovers(session)
    else:
        _cheer_note_count(session, entry)
    _finish_new_entry(session, entry, body, defer)
    similar = None if defer else filing_background.near_duplicate(session, entry)
    return Created(entry, filed_by, similar, True, defer, body.client_key)


def start_background(made: Created) -> None:
    """Started last, on purpose: everything in `create` still runs inside the
    request, so the thread can never race the commit that makes this note
    visible to its own session."""
    if not made.fresh:
        return
    if made.defer:
        filing_background._queue_filing(made.entry)
    filing_background._remember_delivery(made.client_key, made.entry)
