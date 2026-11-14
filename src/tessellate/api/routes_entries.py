"""Capture, read, edit, soft-delete, restore, and link entries.

Handlers are plain `def` (not async) on purpose: FastAPI then runs them
in a threadpool, which keeps the server responsive while blocking AI
calls run (plan §4).
"""

from __future__ import annotations

import contextlib
import dataclasses
import functools
import json
import logging
import re
import threading
from collections import OrderedDict
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tessellate.ai import (
    composer_gist,
    extractor,
    filing_certainty,
    janitor,
    lexical_filing,
    librarian,
)
from tessellate.ai.ollama_client import OllamaError
from tessellate.api import paging
from tessellate.api.downloads import attachment_headers, safe_filename
from tessellate.api.edit_conflicts import (
    content_hash,
    entity_tag,
    refuse_if_stale,
    refuse_unless_match,
)
from tessellate.api.routes_entries_refs import REFERENCE_SOURCES_MAX, _reference_rows_batch
from tessellate.api.schemas import (
    AttachmentOut,
    ContextBody,
    DocumentRefOut,
    EntryCreate,
    EntryDateOut,
    EntryOut,
    EntryUpdate,
    LinkOut,
    SimilarOut,
)
from tessellate.core import cjk, companion_events, deps, events, jobruns, jobs, vault
from tessellate.core.database import (
    LIKE_ESCAPE,
    EmbeddingRecord,
    Entry,
    MediaUpload,
    WhiteboardNode,
    like_escape,
    utcnow,
)
from tessellate.core.deps import get_session
from tessellate.core.events import ACTOR_USER_AND_AI
from tessellate.core.validation_copy import Said
from tessellate.entry import manager, private_space
from tessellate.entry import manager_wiki
from tessellate.entry import manager_links
from tessellate.entry import manager_text
from tessellate.entry import manager_purge
from tessellate.entry import manager_private
from tessellate.entry import meetings as meeting_shape
from tessellate.entry import properties as note_properties
from tessellate.entry.tagnames import inline_tags, normalise_tags
from tessellate.repo import content as content_repo
from tessellate.repo import documents as documents_repo
from tessellate.repo import relation_types
from tessellate.repo import tags as tags_repo
from tessellate.repo.content import NOTES
from tessellate.search import search_manager

router = APIRouter(prefix="/entries", tags=["entries"])

logger = logging.getLogger("tessellate.api.entries")


def _preview(text: str, length: int = 60) -> str:
    """A short, readable version of a note for link chips and lists.

    The [[link]] syntax is scaffolding rather than content, so a preview shows
    the words without the brackets, seeing "[[bread proving]]" on a link chip
    that already means "linked to bread proving" is just noise.
    """
    from tessellate.entry.properties import strip as strip_properties

    plain = manager_text.strip_inline_markdown(manager_text.wiki_plain(strip_properties(text or "").lstrip()))
    return plain if len(plain) <= length else plain[: length - 1] + "…"


def _to_out(
    session: Session,
    entry,  # noqa: ANN001
    filed_by: str | None = None,
    similar: SimilarOut | None = None,
    *,
    category_name: str | None = None,
    dates: list | None = None,
    documents: list | None = None,
    links: list | None = None,
    attachments: list | None = None,
) -> EntryOut:
    # Decrypted here if private and the vault is open, every read of a
    # note's text goes through this one helper.
    #
    # The four `category_name`/`dates`/`documents`/`links` overrides let a
    # list endpoint pass in pre-fetched, bulk-queried values instead of this
    # function issuing one query per entry per field (ROADMAP.md #0 priority,
    # item 1: `GET /entries` was doing exactly that). Single-entry callers
    # (create/update/get) pass none of them and keep the original per-entry
    # queries below, unchanged.
    content = manager_text.readable_content(entry)
    resolved_dates = manager.entry_dates(session, entry) if dates is None else dates
    resolved_documents = (
        manager.documents_for_entry(session, entry) if documents is None else documents
    )
    resolved_links = manager_links.links_for_entry(session, entry) if links is None else links
    resolved_attachments = (
        manager_purge.attachments_for(session, entry) if attachments is None else attachments
    )
    return EntryOut(
        id=entry.id,
        content=content,
        content_hash=content_hash(content),
        title=manager_text.extract_title(content),
        #: KG4: what the note's `---` block says, and its type.
        properties=(props := note_properties.split(content)[0]),
        note_type=note_properties.note_type(props),
        category=(
            manager.category_name_for(session, entry) if category_name is None else category_name
        ),
        tags=manager.shown_tags(entry),
        ai_confidence=filing_certainty.shown(
            entry.ai_confidence, user_filed=bool(getattr(entry, "user_filed", False))
        ),
        tag_suggest_off=bool(getattr(entry, "tag_suggest_off", False)),
        suggested_tags=(offered := _open_suggestions(entry)),
        suggested_tag_reasons=_tag_reasons(content, offered),
        #: Never a private note's: derived from its text, as its suggestions
        #: are (tests/test_private_suggested_tags.py).
        discarded_tags=[] if getattr(entry, "is_private", False) else _json_tags(getattr(entry, "discarded_tags", "[]")),
        access_count=entry.access_count,
        last_opened_at=getattr(entry, "last_opened_at", None),
        edited_at=getattr(entry, "edited_at", None),
        parent_id=entry.parent_id,
        pinned=entry.pinned,
        colour=getattr(entry, "colour", None),
        user_filed=entry.user_filed,
        is_private=bool(getattr(entry, "is_private", False)),
        is_draft=bool(getattr(entry, "is_draft", False)),
        source_url=getattr(entry, "source_url", None),
        source_title=getattr(entry, "source_title", None),
        source_path=getattr(entry, "source_path", "") or "",
        is_board=bool(getattr(entry, "is_board", False)),
        board_kind=getattr(entry, "board_kind", None),
        map_topic=bool(getattr(entry, "map_topic", False)),
        workspace_id=getattr(entry, "workspace_id", "default") or "default",
        created_at=entry.created_at,
        deleted_at=entry.deleted_at if entry.is_deleted else None,
        archived_at=entry.archived_at,
        dates=_date_outs(resolved_dates),
        documents=[
            DocumentRefOut(id=doc.id, title=doc.title) for doc in resolved_documents
        ],
        links=_link_outs(session, entry, resolved_links),
        attachments=_attachment_outs(resolved_attachments),
        filed_by=filed_by,
        filing_state=getattr(entry, "filing_state", "done") or "done",
        similar=similar,
    )


def _date_outs(dates: list) -> list[EntryDateOut]:
    return [
        EntryDateOut(
            phrase=d.phrase,
            at=d.at.date(),
            precision=d.precision,
            time=d.at.strftime("%H:%M") if d.precision == "minute" else None,
        )
        for d in dates
    ]


def _link_outs(session: Session, entry, links: list) -> list[LinkOut]:  # noqa: ANN001
    return [
        LinkOut(
            link_id=link.id,
            entry_id=other.id,
            preview=_connection_label(other, 60),
            reason=link.reason,
            reason_confidence=link.reason_confidence,
            # The one fact the merged list could never carry. See
            # `LinkOut.direction`.
            direction="out" if link.source_entry_id == entry.id else "in",
            link_type=link.link_type,
            link_label=manager_links.relation_label(
                relation_types.kinds(session), link.link_type, link.source_entry_id == entry.id
            ),
            props=link.props,
        )
        for link, other in links
    ]


def _attachment_outs(attachments: list) -> list[AttachmentOut]:
    return [
        AttachmentOut(
            id=a.id,
            filename=a.filename,
            size=a.size,
            is_image=a.mime.startswith("image/"),
            created_at=a.created_at.isoformat() if a.created_at else "",
        )
        for a in attachments
    ]


def _json_tags(raw: str | None) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return [str(tag) for tag in value if tag] if isinstance(value, list) else []


def _open_suggestions(entry) -> list[str]:  # noqa: ANN001
    """The kept suggestions still worth showing: not on the note already and
    not discarded (a tag added by hand since filing drops out by itself).
    None while the note is set to "Don't suggest tags" (brief 89); what was
    kept is still on the row and comes back when that is cleared. None while
    a private note is locked, like its tags (INBOX 1437)."""
    if getattr(entry, "tag_suggest_off", False) or manager.note_is_sealed(getattr(entry, "is_private", False)):
        return []
    have = {tag.casefold() for tag in manager.entry_tags(entry)}
    gone = {tag.casefold() for tag in _json_tags(getattr(entry, "discarded_tags", "[]"))}
    return [
        tag for tag in _json_tags(getattr(entry, "suggested_tags", "[]"))
        if tag.casefold() not in have and tag.casefold() not in gone
    ]


#: Longest note whose reasons are remembered: the cache holds the text as its key.
REASONS_CACHE_CHARS = 20_000
#: A note longer than this, opened, is the in-app companion's reading glasses (`avatars.js` `nameMarkBuddyNoteOpened`).
LONG_NOTE_CHARS = 1200


def _kept_private(session: Session, entry) -> bool:  # noqa: ANN001
    """A private note, or one in a private space: the desk companion hears only the generic kind for these."""
    return bool(entry.is_private) or private_space.is_private_space(session, entry.workspace_id)


def _tag_reasons(content: str, tags: list[str]) -> dict[str, str]:
    """Each offered tag's one line for its chip (decision 5: each explained).

    A pure function of the text and the tags (the taxonomy is read once per
    process), so a list that reads the same two hundred notes on every load
    remembers the answers: 5 ms a note was 2.2 of 3.4 profiled seconds of
    `GET /entries?limit=200` at 530 notes (BK10)."""
    if not tags or not content:
        return {}
    if len(content) > REASONS_CACHE_CHARS:
        return dict(_reasons_for(content, tuple(tags)))
    return dict(_cached_reasons(content, tuple(tags)))


def _reasons_for(content: str, tags: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    from tessellate.ai import tagging, taxonomy

    hits = taxonomy.topic_hits(tagging.clean(content))
    return tuple((tag, why) for tag in tags if (why := tagging.reason(tag, content, hits)))


_cached_reasons = functools.lru_cache(maxsize=1024)(_reasons_for)


def _keep_suggestions(session: Session, entry, filed_by: str | None) -> None:  # noqa: ANN001
    """Make the note's tag suggestions at filing and keep them on it (INBOX
    440). The model's when it is the one that filed (it is up and answering);
    otherwise the notebook's own: the tags its nearest notes carry, and the
    vocabulary tags the note names. Best effort, never fails the filing.

    **A private note gets none made.** Its tags are the person's own (nothing
    derives them from its text), and a suggestion is derived from the text, so
    one made here would put a summary of a private note into a plain column,
    from ciphertext or the locked placeholder when the vault is shut. What it
    already holds (a note made private after filing) is handled like its
    tags: kept, shown where they are, nowhere else."""
    if getattr(entry, "is_private", False) or getattr(entry, "tag_suggest_off", False):
        return
    have = manager.entry_tags(entry)
    discarded = {tag.casefold() for tag in _json_tags(getattr(entry, "discarded_tags", "[]"))}
    suggested: list[str] = []
    if filed_by == "llm":
        try:
            suggested = librarian.suggest_tags(
                entry.content, have, deps.get_model_manager(), deps.get_ollama(),
                vocabulary=_tag_vocabulary(session),
            )
        except Exception:
            logger.info("tag suggestions from the model failed; using the notebook's own", exc_info=True)
    content = manager_text.readable_content(entry)
    keep = [tag for tag in _engine_tags(session, content, have, suggested, entry.id) if tag.casefold() not in discarded]
    from tessellate.ai import tagging

    entry.suggested_tags = json.dumps(keep[: tagging.TAG_LIMIT])


def _engine_tags(session: Session, content: str, have: list[str], model: list[str], entry_id: int | None) -> list[str]:
    """One engine on every path (INBOX 781): a model's tags kept only where
    the note has a word for them (WORLD_CLASS 23, decision 5: its reply to
    "prefer one of those" was the first two, whatever the note said, the
    Study bug), then the notebook's own (`ai/tagging.suggest`) filling the
    rest, so a model that offers one tag no longer hides two good ones. Room
    still left goes to a subject the note names that the notebook has never
    tagged (`tagging.filled`, B80)."""
    from tessellate.ai import tagging

    own = tagging.suggest(session, content, have=have, exclude_entry_id=entry_id)
    return tagging.filled(session, content, tagging.merged(tagging.grounded(content, model), own, have), have)


def _to_out_bulk(session: Session, entries: list) -> list[EntryOut]:
    """`_to_out` for a whole list-endpoint page in a fixed number of queries
    instead of ~4 per entry (ROADMAP.md #0 priority, item 1)."""
    ids = [e.id for e in entries]
    category_names = manager.bulk_category_names(session, entries)
    dates_by_id = manager.entry_dates_bulk(session, ids)
    documents_by_id = manager.documents_for_entries_bulk(session, ids)
    links_by_id = manager.links_for_entries_bulk(session, ids)
    attachments_by_id = manager_purge.attachments_for_entries_bulk(session, ids)
    return [
        _to_out(
            session,
            e,
            category_name=category_names.get(e.category_id, manager.UNCATEGORISED),
            dates=dates_by_id.get(e.id, []),
            documents=documents_by_id.get(e.id, []),
            links=links_by_id.get(e.id, []),
            attachments=attachments_by_id.get(e.id, []),
        )
        for e in entries
    ]


def _find_near_duplicate(session: Session, entry) -> SimilarOut | None:  # noqa: ANN001
    """Warn about a saved note that says almost the same thing.
    Purely informational: the save has already happened."""
    try:
        results = search_manager.semantic_search(
            session, entry.content, deps.get_embeddings(), limit=3
        )
    except Exception:
        logger.warning("the near-duplicate check failed; the note is saved", exc_info=True)
        return None
    for other, score in results or []:
        if other.id != entry.id and score >= 0.9:
            return SimilarOut(
                id=other.id, preview=_preview(other.content), similarity=round(score, 2)
            )
    return None


def _existing_entry(session: Session, entry_id: int):  # noqa: ANN202
    # `manager.get_entry` is `session.get(Entry, entry_id)` under the hood
    # (memorymap/entry/manager.py); going through `deps.get_or_404` directly
    # is equivalent and consolidates the 404.
    return deps.get_or_404(session, Entry, entry_id, "That note could not be found.")


def _process_committed_media(session: Session, plaintext_content: str) -> None:
    """Trigger OCR/captioning/vision-OCR for every `/media/…` upload this
    (plaintext, pre-encryption) note content references, see
    core/media_process.py's own docstring for why this fires here rather
    than on upload. Best-effort: an image reference to an upload that's
    already gone, or one already processed, is a fast no-op either way."""
    from tessellate.core import media_process

    media_process.process_referenced_uploads(
        session, deps.get_config().data_dir / "media", plaintext_content
    )


def _file_entry_now(
    session: Session,
    content: str,
    on_late_llm=None,  # noqa: ANN001
    model_deadline: float | None = None,
) -> tuple[str, int, str]:
    """Ask the janitor where a note belongs. Whatever goes wrong in AI land,
    the note still gets saved (plan §4)."""
    try:
        return janitor.categorise(
            session,
            content,
            deps.get_embeddings(),
            deps.get_model_manager(),
            deps.get_ollama(),
            on_late_llm=on_late_llm,
            model_deadline=model_deadline,
        )
    except Exception:
        # `categorise` handles a model that is down on its own (a keyword
        # fallback), so this is a fault in it: logged, or every note filed
        # "Uncategorised" is the only sign.
        logger.warning("filing failed; the note is saved uncategorised", exc_info=True)
        return manager.UNCATEGORISED, 0, "none"


class _LateFiling:
    """**The model's answer wins, even when it is slow.** Filing gives the
    model `janitor.FILING_MODEL_DEADLINE_SECONDS` so a note never looks stuck;
    past that the note is filed by meaning (a stand-in) and the model keeps
    going on its own thread. When its answer lands it replaces the stand-in,
    unless the note was moved by hand or deleted in the meantime: the owner's
    words, "there's no point in having the app if the notes arent filed
    accurately". Either order is handled: an answer that lands before the
    stand-in is decided is taken instead of it."""

    def __init__(self, entry_id: int, workspace_id: str, content: str = "") -> None:
        self.entry_id = entry_id
        self.workspace_id = workspace_id
        self._content = content
        self._lock = threading.Lock()
        self._stand_in: str | None = None
        self._early: tuple[str, int] | None = None
        #: Set by the janitor when the model misses the wait: the note is
        #: then saved as a stand-in (`manager.STAND_IN`) for its answer.
        self.is_waiting = False

    def waiting(self) -> None:
        self.is_waiting = True

    def stand_in(self, category: str, confidence: int, filed_by: str) -> tuple[str, int, str]:
        with self._lock:
            if self._early is not None:
                return self._early[0], self._early[1], "llm"
            self._stand_in = category
            return category, confidence, filed_by

    def _calibrated(self, category: str, raw: int) -> int:
        """The model's late number, calibrated as `janitor._ask_llm` does for
        an answer inside the wait (`filing_certainty`). On this thread's own
        session: the late answer has none of the request's."""
        from tessellate.ai import filing_certainty
        from tessellate.core.database import impersonate_workspace

        try:
            with deps.get_db().session() as session:
                with impersonate_workspace(session, self.workspace_id):
                    entry = session.get(Entry, self.entry_id)
                    if entry is not None:
                        return filing_certainty.calibrated(
                            session, manager_text.readable_content(entry), category, raw, "llm",
                            exclude_entry_id=entry.id,
                        )
        except Exception:
            logger.debug("couldn't calibrate the late answer for entry %s", self.entry_id, exc_info=True)
        return filing_certainty.calibrate(
            raw, "llm", support=None, category_notes=filing_certainty.ESTABLISHED_NOTES
        )

    def arrived(self, category: str, confidence: int) -> None:
        from tessellate.ai import lexical_filing

        if lexical_filing.holds_sensitive(self._content, category):
            return  # decision 6: the model's late answer is held like an early one
        confidence = self._calibrated(category, confidence)
        if lexical_filing.is_unsure(confidence):
            return  # ask when unsure: a late pick under the line waits like an early one
        with self._lock:
            if self._stand_in is None:
                self._early = (category, confidence)
                return
            stand_in = self._stand_in
        self.apply(category, confidence, stand_in)

    def apply(self, category: str, confidence: int, stand_in: str) -> None:
        from tessellate.core.database import impersonate_workspace

        try:
            with deps.get_db().session() as session:
                with impersonate_workspace(session, self.workspace_id):
                    entry = session.get(Entry, self.entry_id)
                    if entry is None or getattr(entry, "is_deleted", False):
                        return
                    if getattr(entry, "user_filed", False):
                        return
                    # Stopped by hand, or already settled: nothing to replace.
                    if (getattr(entry, "filing_state", "") or "") != manager.STAND_IN:
                        return
                    if manager.category_name_for(session, entry) != stand_in:
                        return  # moved by hand: the person's choice stands
                    manager.record_filing(
                        session,
                        entry,
                        category,
                        by=janitor.filed_by_label("llm", confidence, deps.get_model_manager()),
                    )
                    entry.ai_confidence = confidence
                    entry.filing_state = manager.AUTO_FILED
                    session.commit()
                    logger.info("janitor: late model answer refiled entry %s", self.entry_id)
        except Exception:
            logger.warning("couldn't apply the late filing for entry %s", self.entry_id, exc_info=True)


def _settle_filed_entry(session, entry, entry_id: int, late, category, confidence, filed_by):
    """Write the decided category and the settled `filing_state`; returns the
    active run (or None) so the later steps can add their lines to it."""
    manager.record_filing(
        session,
        entry,
        category,
        by=janitor.filed_by_label(
            filed_by, confidence, deps.get_model_manager(), deps.get_embeddings()
        ),
    )
    entry.ai_confidence = confidence
    # `auto` rather than `done` when the AI is the one that
    # chose (Brief 13): it is the flag that makes a later move by
    # hand legible as a correction, and it is terminal for every
    # reader, the composer's poller stops on anything but
    # `pending`.
    entry.filing_state = janitor.settled_state(filed_by)
    # A model answer is still coming: the note is a stand-in
    # until it lands, and is retried next launch if it never does.
    if late.is_waiting and filed_by != "llm":
        entry.filing_state = manager.STAND_IN
    #: The run's lines and its result (INBOX 805, B77: "how long it
    #: took to file"); the run itself carries the duration.
    run = jobruns.active()
    if run is not None:
        how = "by Atlas" if filed_by == "llm" else "by meaning" if filed_by != "none" else "with no model"
        run.say(f"Filed in {category or 'no category'} {how}.")
        run.result = f"note {entry_id} filed in {category or 'no category'} {how}"
    return run


def _embed_and_tidy(session, entry, entry_id: int, filed_by, run) -> None:
    """Embed the settled note, look for a near duplicate, keep tag
    suggestions and run Tidy's automatic reviews."""
    deps.store_quietly(session, entry)
    duplicate = _find_near_duplicate(session, entry)
    if duplicate is not None:
        entry.filing_similar_id = duplicate.id
    session.commit()
    if run is not None:
        run.say("Saved its search vector and checked for a near duplicate.")
    try:
        _keep_suggestions(session, entry, filed_by)
        session.commit()
    except Exception:
        logger.warning("couldn't keep tag suggestions for entry %s", entry_id, exc_info=True)
        session.rollback()
    # Tidy's reviews a person switched on (INBOX 691, off by
    # default): after filing, as `system:tidy`, each run undoable
    # from Tidy's history. Never raises.
    from tessellate.entry import tidy

    tidy.run_automatic(session)


def _mark_filing_failed(entry_id: int) -> None:
    """The last resort: a note whose filing raised is `failed`, never left pending."""
    try:
        with deps.get_db().session() as session:
            entry = session.get(Entry, entry_id)
            if entry is not None:
                entry.filing_state = "failed"
                session.commit()
    except Exception:
        logger.warning("couldn't mark entry %s as failed", entry_id, exc_info=True)


def _file_entry_in_background(entry_id: int, workspace_id: str) -> None:
    """Decide a deferred note's category after its POST has already returned.

    Runs on its own daemon thread with its own session, the same shape
    `core/ocr.py`'s `extract_in_background` uses and for the same reason:
    the request this belongs to is finished, and the user is already typing
    the next note.

    Two things here are load-bearing and easy to get wrong:

    **The workspace has to be re-established by hand.** A fresh session from
    `deps.get_db()` carries no `workspace_id` in `session.info`, so the
    scoping hooks in `core/database.py` sit out entirely: which means the
    janitor would otherwise weigh *every space's* categories when deciding
    where a note from one space belongs, and could file it into a category
    that space cannot even see. `impersonate_workspace` puts the session
    back in the note's own space for the duration.

    **The note is never left saying "pending" forever.** Every exit path, 
    success, a janitor that raised, an entry deleted while the thread was
    still running: settles `filing_state`, because the composer's status
    chip and the poller in `app.js` both read it as "still working" and a
    stuck value would show a note filing itself for eternity.

    **Filing is not the only slow thing in a save**, and deferring it alone
    left the request at ~1s measured locally with no model running at all.
    Embedding the note and the near-duplicate search (itself a full semantic
    search, run only to *maybe* show an advisory toast) were the rest of it,
    and neither is anything the composer needs before the user can start
    typing again. They move here too. The duplicate warning comes back
    through `GET /entries/{id}/filing` instead of the create response, so a
    note that triggers one still gets its "you already wrote something like
    this", a moment later, in the same notification that says where it was
    filed.
    """
    from tessellate.core.database import impersonate_workspace

    try:
        with deps.get_db().session() as session:
            with impersonate_workspace(session, workspace_id):
                entry = session.get(Entry, entry_id)
                if entry is None:
                    return  # deleted before filing finished, nothing to settle
                # Queued again by `filing_status` for a note a closed app left
                # pending, and that retry can race a first pass that has just
                # finished: a settled note is never filed twice.
                if (getattr(entry, "filing_state", "") or "") != "pending":
                    return
                late = _LateFiling(entry_id, workspace_id, manager_text.readable_content(entry))
                category, confidence, filed_by = _file_entry_now(
                    session,
                    manager_text.readable_content(entry),
                    on_late_llm=late,
                    model_deadline=janitor.filing_deadline(),
                )
                # The model answered after the deadline but before the
                # stand-in was decided: its answer is used instead.
                category, confidence, filed_by = late.stand_in(category, confidence, filed_by)
                # Stopped by hand while this ran (`stop_filing`): the
                # person's choice stands, this pass writes nothing.
                session.refresh(entry)
                if (getattr(entry, "filing_state", "") or "") != "pending":
                    return
                run = _settle_filed_entry(session, entry, entry_id, late, category, confidence, filed_by)
                # **Settled first, embedded after.** The vector and the
                # near-duplicate search used to land before `filing_state`
                # did, so the card said "Filing…" for as long as the
                # embedding model took to load, minutes on a first launch,
                # after the category was already known (owner, 0.3.31). The
                # vector still has to exist before the duplicate search has
                # anything to compare against; a duplicate found after the
                # poller has stopped is simply not toasted.
                session.commit()
                _embed_and_tidy(session, entry, entry_id, filed_by, run)
    except Exception:
        logger.warning("background filing failed for entry %s", entry_id, exc_info=True)
        _mark_filing_failed(entry_id)


def stand_ins_waiting() -> int:
    """How many notes are stand-ins (the model's answer was still coming when
    the app last closed). A count only: the launch asks it before queueing
    the retry, so a notebook with none shows no "Filing a note" row."""
    with deps.get_db().session() as session:
        return session.query(Entry).filter(Entry.filing_state == manager.STAND_IN).count()


def retry_stand_ins() -> int:
    """Ask the model again for every note left as a stand-in: its answer was
    still coming when the app closed. Runs once per launch on the model lane
    (`app.py`). A note moved by hand or stopped in the meantime keeps its
    place (`_LateFiling.apply`). Returns how many were asked about."""
    from tessellate.core.database import impersonate_workspace

    with deps.get_db().session() as session:
        waiting = [
            (row.id, getattr(row, "workspace_id", "default") or "default")
            for row in session.query(Entry).filter(Entry.filing_state == manager.STAND_IN).all()
        ]
    for entry_id, workspace_id in waiting:
        try:
            with deps.get_db().session() as session:
                with impersonate_workspace(session, workspace_id):
                    entry = session.get(Entry, entry_id)
                    if entry is None or entry.filing_state != manager.STAND_IN:
                        continue
                    stand_in = manager.category_name_for(session, entry)
                    content = manager_text.readable_content(entry)
                    category, confidence, method = janitor._ask_llm(
                        session,
                        content,
                        deps.get_model_manager(),
                        deps.get_ollama(),
                    )
            if method == "llm" and not lexical_filing.holds_sensitive(content, category):
                _LateFiling(entry_id, workspace_id, content).apply(category, confidence, stand_in)
        except Exception:
            logger.warning("couldn't retry the filing of entry %s", entry_id, exc_info=True)
    return len(waiting)


def _embed_entry_in_background(entry_id: int, workspace_id: str) -> None:
    """Embed an edited note's new text after its PUT has returned.

    Its own session in the note's own space, as `_file_entry_in_background`.
    A note deleted before this runs is left alone. An edit that lands while
    this one embeds is folded into it (the queue's dedupe returns the running
    job), so the text is read again after storing and embedded again if it
    moved: the vector left behind is always the newest text's.
    """
    from tessellate.core.database import impersonate_workspace

    try:
        with deps.get_db().session() as session:
            with impersonate_workspace(session, workspace_id):
                for _ in range(3):
                    entry = session.get(Entry, entry_id)
                    if entry is None or entry.is_deleted:
                        return
                    seen = entry.content
                    deps.store_quietly(session, entry)
                    session.expire_all()
                    again = session.get(Entry, entry_id)
                    if again is None or again.content == seen:
                        return
    except Exception:
        logger.warning("couldn't embed edited entry %s", entry_id, exc_info=True)


def _queue_embedding(entry) -> None:
    """One embedding job per note in flight, on the model lane: a burst of
    autosaves while the first job waits is one embed of the newest text."""
    jobs.enqueue(
        "embed-entry",
        _embed_entry_in_background,
        entry.id,
        getattr(entry, "workspace_id", "default") or "default",
        dedupe_key=("embed-entry", entry.id),
    )


def _queue_filing(entry) -> None:
    """One filing job per note in flight: the key makes a second call while
    the first is queued or running a no-op, so `filing_status` can ask again
    on every poll."""
    jobs.enqueue(
        "file-entry",
        _file_entry_in_background,
        entry.id,
        getattr(entry, "workspace_id", "default") or "default",
        dedupe_key=("file-entry", entry.id),
    )


#: client_key -> (workspace, entry id) for the notes the offline queue has
#: delivered, newest last. In memory and bounded: the window it covers is one
#: resend of a save whose answer was lost, seconds to minutes, and a
#: process that restarted in between is the one case it cannot see (said in
#: INBOX 434's report, not hidden).
_DELIVERED: OrderedDict[str, tuple[str, int]] = OrderedDict()
_DELIVERED_MAX = 512


def _already_delivered(session: Session, key: str | None):
    """The note an earlier save with this `client_key` made, or None.

    The column, not only the dict: the dict is the fast path inside one
    process, the column is what a restart keeps (ARCH-23). The space hook
    narrows the read, so a key from another space is not this space's note.
    """
    if not key:
        return None
    if key in _DELIVERED:
        workspace, entry_id = _DELIVERED[key]
        entry = session.get(Entry, entry_id)
        if entry is not None and (getattr(entry, "workspace_id", "default") or "default") == workspace:
            return entry
    return session.scalars(select(Entry).where(Entry.client_key == key)).first()


def _remember_delivery(key: str | None, entry) -> None:
    if not key:
        return
    _DELIVERED[key] = (getattr(entry, "workspace_id", "default") or "default", entry.id)
    while len(_DELIVERED) > _DELIVERED_MAX:
        _DELIVERED.popitem(last=False)


def _mark_new_entry(entry, body: EntryCreate, filed_by: str | None) -> None:  # noqa: ANN001
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


def _apply_flags(session: Session, entry, body) -> None:  # noqa: ANN001
    """Colour (null clears it) and draft from an edit, each saved when it moves."""
    if "colour" in body.model_fields_set and body.colour != entry.colour:
        entry.colour = body.colour
        session.commit()
    if body.is_draft is not None and body.is_draft != entry.is_draft:
        entry.is_draft = body.is_draft
        session.commit()


def _decide_filing(session: Session, body: EntryCreate, parent) -> tuple[str, int, str, bool]:  # noqa: ANN001
    """`(category, confidence, filed_by, defer)` for a new note."""
    # Deferred only when nothing else already decides the category: with an
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
        category, confidence, filed_by = _file_entry_now(
            session, body.content, model_deadline=janitor.filing_deadline()
        )
    return category, confidence, filed_by, defer


def _new_note_text(session: Session, body: EntryCreate) -> tuple[str, list[str]]:
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


def _finish_new_entry(session: Session, entry, body: EntryCreate, defer: bool) -> None:  # noqa: ANN001
    """Everything after the commit that must never cost someone their note."""
    if not defer:
        #: Filed already: keep its tag suggestions now, from the notebook's
        #: own tags (no second model call on the request; a deferred note
        #: gets the model's in the background pass).
        try:
            _keep_suggestions(session, entry, None)
            session.commit()
        except Exception:
            logger.warning("couldn't keep tag suggestions for a new note", exc_info=True)
            session.rollback()

    # Best effort: a failed embedding only means this entry is invisible
    # to semantic search until re-indexed, never a failed save. It is logged
    # rather than swallowed, so a backend that has stopped working shows up in
    # Settings, Logs instead of quietly shrinking search.
    #
    # Skipped when filing is deferred: the same background thread does it,
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
    _process_committed_media(session, body.content)


def _starts_sealed(session: Session, body: EntryCreate) -> tuple[bool, bool]:
    """INBOX 1695: (sealed, sealed by this note's own ask rather than its space)."""
    if private_space.is_private_space(session, session.info.get("workspace_id")):
        return True, False
    try:
        ask = private_space.starts_private(body.private)
    except private_space.VaultLocked as locked:
        raise HTTPException(status_code=409, detail="Unlock the app first: the encryption key isn't loaded.") from locked
    return ask, ask


def _note_total(session: Session) -> int:
    """The notes the dashboard counts (`/insights/stats` `total_entries`): not deleted, drafts or boards."""
    return session.scalar(
        select(func.count(Entry.id)).where(Entry.is_deleted == False, Entry.is_draft == False, Entry.is_board == False)  # noqa: E712
    ) or 0


def _cheer_note_count(session: Session, entry: Entry) -> None:
    """Passing a round count is a cheer on the desk: a kind and a time (P7). A draft is no note yet, so the count moved not."""
    if not entry.is_draft:
        companion_events.counted(_note_total(session))


@router.post("", response_model=EntryOut, status_code=201)
def create_entry(body: EntryCreate, session: Session = Depends(get_session)) -> EntryOut:
    earlier = _already_delivered(session, body.client_key)
    if earlier is not None:
        return _to_out(session, earlier, filed_by=None, similar=None)
    parent = _existing_entry(session, body.parent_id) if body.parent_id is not None else None
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
        earlier = _already_delivered(session, body.client_key) if body.client_key else None
        if earlier is None:
            raise
        return _to_out(session, earlier, filed_by=None, similar=None)
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
    out = _to_out(
        session,
        entry,
        filed_by=filed_by,
        similar=None if defer else _find_near_duplicate(session, entry),
    )

    # Started last, on purpose: everything above still runs inside the
    # request, so the thread can never race the commit that makes this note
    # visible to its own session.
    if defer:
        _queue_filing(entry)
    _remember_delivery(body.client_key, entry)

    return out


# --- D6: the journal's daily note (WORLD_CLASS_PLAN section 13, D6) ----------
#
# The convention came first and stays: a daily note is an ordinary note whose
# first line is `# <ISO date>` (`dailyNoteTitle` in app.js). Nothing about it
# is special, which is the point: it is searchable, it is in the graph, it
# exports, and a notebook opened in another editor still has it.
#
# **What was missing is the "or returns" half.** `startTodaysNote` posts a new
# note every time it is pressed, so opening today's journal twice in a day
# leaves two notes both headed with today's date and the writing split between
# them. D6's brief asks for `/entries/daily/{date}` "that creates or returns",
# and that is what makes the key safe to press from anywhere, which is the
# rest of D6 (Ctrl+D, the calendar strip, the streak) built on top.
#
# **The date is the caller's, never the server's.** "Today" is a fact about
# where the person is sitting, and this process may be in another timezone
# (`entry/timewords.py` makes the same argument at length). So the day is a
# path parameter and the server never guesses it.
#
# **The template body is not written here.** The four built-in templates'
# markdown only ever lived in the frontend (`BUILTIN_TEMPLATE_NAMES` in
# routes_settings.py records that, and why). The server writes the heading
# that makes the note findable; anything under it is the person's to type or
# the frontend's to prefill on the first open.

#: The day heading, and the only thing that makes a note a daily note.
DAILY_HEADING = "# {date}"

#: How far back the journal window looks by default. A month is what a
#: calendar strip shows and what a streak has to count over to be honest.
DAILY_WINDOW_DAYS = 31
DAILY_WINDOW_MAX = 366


class DailyDayOut(BaseModel):
    date: str
    written: bool


class DailyJournalOut(BaseModel):
    #: The caller's today, echoed, so a client that let the server default it
    #: can see which day the answer is about.
    through: str
    #: Oldest first, one entry per day in the window.
    days: list[DailyDayOut]
    #: Days written in a row, counting back from `through`.
    streak: int


def _daily_date(raw: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="Write a journal date as year-month-day, like 2026-10-04."
        ) from exc


def _first_line(entry) -> str:  # noqa: ANN001
    content = entry.content or ""
    return content.split("\n", 1)[0].strip()


def _daily_notes(session: Session) -> list:
    """Every note whose first line is a day heading.

    Narrowed in SQL by the heading's *shape* and confirmed in Python on the
    first line: a note that merely mentions `# 2026-09-13` further down is not
    the journal entry for that day, and a prefix match alone cannot tell a
    heading from a line that happens to start the same way.
    """
    rows = session.scalars(
        select(Entry)
        # `# ____-__-__%`: `_` is LIKE's single-character wildcard and both it
        # and the `%` are meant, so this pattern declares no escape and takes
        # no user text. Written inline rather than as a named constant because
        # that is exactly the shape `tests/test_like_escaping.py` exempts, and
        # a constant here reads to that lint like a value somebody built.
        .where(Entry.is_deleted.is_(False), Entry.content.like("# ____-__-__%"))
        .order_by(Entry.id)
    ).all()
    return [entry for entry in rows if _DAY_HEADING.match(_first_line(entry))]


_DAY_HEADING = re.compile(r"^# \d{4}-\d{2}-\d{2}$")


def _daily_note(session: Session, day: date):  # noqa: ANN202
    heading = DAILY_HEADING.format(date=day.isoformat())
    for entry in _daily_notes(session):
        if _first_line(entry) == heading:
            return entry
    return None


@router.get("/daily", response_model=DailyJournalOut)
def daily_journal(
    through: str | None = None,
    days: int = Query(default=DAILY_WINDOW_DAYS, ge=1, le=DAILY_WINDOW_MAX),
    session: Session = Depends(get_session),
) -> DailyJournalOut:
    """Which of the last `days` days have a journal entry, and the streak.

    Declared before `/{entry_id}` so FastAPI does not match "daily" as an
    entry id and answer 422 instead (the ordering trap `/media/orphans` in
    routes_files.py carries the same comment about).

    The streak counts back from `through` and **allows today to be empty**: a
    person who has written nine days running and has not yet opened today's
    note has a streak of nine, not zero. Breaking it at the first missing day
    including today would make the number drop every midnight and reappear
    when they wrote, which is a counter that punishes the morning.
    """
    #: Today on the user's clock (audit 1028 K22): a LAN phone in another zone
    #: saw its streak break at the server's midnight.
    from tessellate.core.config import user_now

    last = _daily_date(through) if through else user_now(deps.get_config()).date()
    window = [last - timedelta(days=offset) for offset in range(days)]
    heading_of = {DAILY_HEADING.format(date=day.isoformat()): day for day in window}
    written = {
        heading_of[_first_line(entry)]
        for entry in _daily_notes(session)
        if _first_line(entry) in heading_of
    }
    streak = 0
    for offset, day in enumerate(window):
        if day in written:
            streak += 1
        elif offset > 0 or streak:
            break
    return DailyJournalOut(
        through=last.isoformat(),
        days=[
            DailyDayOut(date=day.isoformat(), written=day in written)
            for day in reversed(window)
        ],
        streak=streak,
    )


@router.get("/daily/{day}", response_model=EntryOut)
def daily_note(day: str, session: Session = Depends(get_session)) -> EntryOut:
    """One day's journal entry, or 404 if nothing was written that day.

    Read-only, and the writing half is the POST below. The obvious shape for
    D6 is one GET that creates when it has to, and it was written that way
    first: a GET that writes is the shape a reviewer is right to stop, because
    the CSRF defence in `core/security.py` judges *methods*, and an endpoint
    that makes a row on a GET is outside it by construction.
    """
    found = _daily_note(session, _daily_date(day))
    if found is None:
        raise HTTPException(status_code=404, detail="Nothing is written on that day yet.")
    return _to_out(session, found)


@router.post("/daily/{day}", response_model=EntryOut)
def open_daily_note(day: str, session: Session = Depends(get_session)) -> EntryOut:
    """One day's journal entry, made if it is not there yet.

    "Creates or returns", which is what makes the key safe to press from
    anywhere: splitting it into a lookup plus a conditional create puts the
    race between two windows of the same app (or two presses of the key) back
    exactly where this endpoint exists to remove it. 200 rather than 201 for
    the same reason: whether this call made the note is not the caller's
    business and is not stable between two presses a second apart.

    Nothing else about the note is decided here, which is what keeps a journal
    entry an ordinary note.
    """
    wanted = _daily_date(day)
    existing = _daily_note(session, wanted)
    if existing is not None:
        return _to_out(session, existing)
    entry = manager.create_entry(
        session,
        DAILY_HEADING.format(date=wanted.isoformat()) + "\n\n",
        category_name=manager.UNCATEGORISED,
    )
    # Re-read rather than trusting the insert: two callers pressing the key at
    # the same moment both reach here, and the one that lost should hand back
    # the note that won rather than its own duplicate.
    settled = _daily_note(session, wanted)
    return _to_out(session, settled if settled is not None else entry)

FILING_STOP_ACTIONS = ("keep", "fallback")


def stop_filing(session: Session, entry, action: str) -> str:  # noqa: ANN001
    """Stop filing one note by hand (owner, 0.3.31: "a manual way to stop
    note filing and to just do it manually or leave what has already been
    done, or to just use the fall back"). `keep` leaves it where it is,
    `fallback` files it by meaning now (no chat model). Either way the note
    is marked as the person's to file, so a model answer that lands later
    (`_LateFiling`) or a job still queued for it writes nothing. Returns the
    category it ends in."""
    if action == "fallback":
        match = janitor._semantic_category(
            session,
            manager_text.readable_content(entry),
            deps.get_embeddings(),
            exclude_entry_id=entry.id,
        )
        if match is not None:
            manager.record_filing(
                session, entry, match[0],
                by=janitor.filed_by_label(match[2], match[1], embeddings=deps.get_embeddings()),
            )
            entry.ai_confidence = match[1]
    # **Stopped, not chosen.** It used to set `user_filed`, which reads as
    # "the person picked this category" and so kept re-evaluate away from
    # it for good; stopping only means "not now".
    entry.filing_state = manager.FILING_STOPPED
    session.commit()
    return manager.category_name_for(session, entry)


class FilingStopBody(BaseModel):
    action: str = "keep"


@router.post("/{entry_id}/filing/stop")
def stop_filing_one(
    entry_id: int, body: FilingStopBody, session: Session = Depends(get_session)
) -> dict:
    if body.action not in FILING_STOP_ACTIONS:
        raise HTTPException(status_code=422, detail="Pick keep or fallback.")
    entry = _existing_entry(session, entry_id)
    if (getattr(entry, "filing_state", "") or "") not in ("pending", manager.STAND_IN):
        return {"id": entry.id, "stopped": False, "category": manager.category_name_for(session, entry)}
    category = stop_filing(session, entry, body.action)
    return {"id": entry.id, "stopped": True, "category": category}


class FilingDecisionBody(BaseModel):
    #: True: the person keeps the janitor's category, so the note leaves the
    #: review queue and re-evaluate leaves it alone. False is Accept's Undo.
    accepted: bool = True


@router.post("/{entry_id}/filing", response_model=EntryOut)
def decide_filing(
    entry_id: int, body: FilingDecisionBody, session: Session = Depends(get_session)
) -> EntryOut:
    """The review queue's Accept (WORLD_CLASS_PLAN section 17, row 1): the
    category stays and becomes the person's (`user_filed`), which is what a
    move to another category already does. Logged, so the activity log says
    who decided."""
    entry = NOTES.writable(session, entry_id)
    if bool(entry.user_filed) != body.accepted:
        entry.user_filed = body.accepted
        manager.log_action(
            session,
            "filing_accepted" if body.accepted else "filing_unaccepted",
            "entry",
            entry.id,
            detail=manager.category_name_for(session, entry),
        )
        session.commit()
    return _to_out(session, entry)


def stop_all_filing(action: str = "fallback") -> int:
    """Every note still filing, in every space: the Stop on the filing rows
    of Settings, Background tasks and the activity popup. Each note is
    stopped in its own space, so the fallback weighs that space's
    categories only. Returns how many were stopped."""
    from tessellate.core.database import impersonate_workspace

    stopped = 0
    with deps.get_db().session() as session:
        pending = [
            (row.id, getattr(row, "workspace_id", "default") or "default")
            for row in session.query(Entry)
            .filter(Entry.filing_state.in_(("pending", manager.STAND_IN)))
            .all()
        ]
    for entry_id, workspace_id in pending:
        try:
            with deps.get_db().session() as session:
                with impersonate_workspace(session, workspace_id):
                    entry = session.get(Entry, entry_id)
                    if entry is not None and entry.filing_state in ("pending", manager.STAND_IN):
                        stop_filing(session, entry, action)
                        stopped += 1
        except Exception:
            logger.warning("couldn't stop filing entry %s", entry_id, exc_info=True)
    return stopped


def _filing_similar(session: Session, entry) -> dict | None:  # noqa: ANN001
    """The near-duplicate the filing pass found, as `{id, preview}`, or None."""
    duplicate_id = getattr(entry, "filing_similar_id", None)
    other = session.get(Entry, duplicate_id) if duplicate_id is not None else None
    if other is None:
        return None
    return {"id": other.id, "preview": _connection_label(other, 60)}


def _choices_filled(session: Session, content: str, entry_id: int, category: str, choices: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """The filing call's choices, then recent categories by the words, up to three, never the current one."""
    from tessellate.ai import lexical_filing

    explained = [(name, reason) for name, reason in choices if name != category]
    if len(explained) < 3:
        taken = {name for name, _ in explained} | {category}
        for name, reason in lexical_filing.suggest_categories_explained(session, content, exclude_entry_id=entry_id, limit=4):
            if name not in taken:
                explained.append((name, reason))
                taken.add(name)
    return explained


def _offered_categories(session: Session, entry, category: str) -> tuple[list[str], dict[str, str], dict | None, dict | None, str]:  # noqa: ANN001
    """`(suggestions, reasons, proposal, held, why)`: up to three categories to offer as
    one-tap choices (INBOX 434), each one's line, a new category the pack proposes
    (WORLD_CLASS 23, decisions 2, 3 and 6), a sensitive topic that held it back, and
    why it waits. The choices are the filing call's own, first and in its order
    (`lexical_filing.filing_call`, INBOX 1583), so the saved note offers what the
    Capture hint offered; recent categories fill the row only after them."""
    from tessellate.ai import lexical_filing

    explained: list[tuple[str, str]] = []
    proposal = None
    held = None
    why = ""
    try:
        content = manager_text.readable_content(entry) or ""
        call = lexical_filing.filing_call(session, content, exclude_entry_id=entry.id)
        explained = _choices_filled(session, content, entry.id, category, call.choices)
        #: A pick the person asked to be asked about (a model's, or by
        #: meaning) is first among the choices, with the words' reason.
        if call.category and call.category != category and lexical_filing.ask_when_unsure():
            explained = [(call.category, call.why)] + [row for row in explained if row[0] != call.category]
            call = dataclasses.replace(call, why=lexical_filing.ASK_WHY)
        explained = explained[:3]
        if call.proposal is not None:
            proposal = {"name": call.proposal.name, "why": call.proposal.why}
        if call.held and call.choices:
            held = {"category": call.choices[0][0], "topic": call.held}
        why = call.why
    except Exception:  # noqa: BLE001 - a hint never fails the status
        logger.debug("no category suggestions for entry %s", entry.id, exc_info=True)
    suggestions = [name for name, _ in explained]
    reasons = {name: reason for name, reason in explained if reason}
    return suggestions, reasons, proposal, held, why


def _filing_why(session: Session, entry, category: str) -> str:  # noqa: ANN001
    """The one line behind a filing by words, or an empty string."""
    from tessellate.ai import lexical_filing

    try:
        decision = lexical_filing.decide(
            session, manager_text.readable_content(entry) or "", exclude_entry_id=entry.id
        )
        return next((c.why for c in decision.ranked if c.name == category), "")
    except Exception:  # noqa: BLE001 - a hint never fails the status
        logger.debug("no filing reason for entry %s", entry.id, exc_info=True)
        return ""


@router.get("/{entry_id}/filing")
def filing_status(entry_id: int, session: Session = Depends(get_session)) -> dict:
    """Where a deferred note ended up, the one thing the composer polls.

    Deliberately not `GET /entries/{id}`: that serialises links, documents,
    dates and attachments through four more queries, and a poller running
    every second while a note settles would pay all of it to read three
    fields. This is the whole of what the "Filed under X" notification
    needs.
    """
    entry = _existing_entry(session, entry_id)
    # **A note is never pending with nothing working on it.** The filing job
    # lives in this process's queue, so a note saved moments before the app
    # closed came back "pending" on the next launch with no job behind it,
    # and its card said "Filing…" forever (owner, 0.3.31: "it still looks
    # like it is endlessly filing"). Asking here re-queues it; the dedupe
    # key makes that a no-op while a job for it is already queued or running.
    if (getattr(entry, "filing_state", "") or "") == "pending":
        _queue_filing(entry)
    similar = _filing_similar(session, entry)
    state = getattr(entry, "filing_state", "done") or "done"
    category = manager.category_name_for(session, entry)
    filed_by = _filed_by(entry, state)
    shown = filing_certainty.shown(
        entry.ai_confidence, user_filed=bool(getattr(entry, "user_filed", False))
    )
    #: A pick the calibration put under the review line (`filing_certainty`)
    #: is offered the same way: the alternatives beside the one it chose.
    unsure_pick = filed_by == "ai" and 0 < shown < manager.REVIEW_CONFIDENCE
    suggestions: list[str] = []
    reasons: dict[str, str] = {}
    why = ""
    proposal = None
    held = None
    waits = ""
    if (filed_by == "none" and category == manager.UNCATEGORISED) or unsure_pick:
        suggestions, reasons, proposal, held, waits = _offered_categories(session, entry, category)
    elif filed_by == "words" and category != manager.UNCATEGORISED:
        why = _filing_why(session, entry, category)
    return {
        "id": entry.id,
        "filing_state": state,
        "category": category,
        "ai_confidence": shown,
        "similar": similar,
        "filed_by": filed_by,
        "suggestions": suggestions,
        "suggestion_reasons": reasons,
        "why": why,
        "proposal": proposal,
        "held_sensitive": held,
        #: Why the words left it waiting ("A close call between Hobbies and
        #: Study, so it waits for you to choose."), said by the saved line.
        "waits_why": waits if filed_by == "none" else "",
    }


def _filed_by(entry, state: str) -> str:  # noqa: ANN001
    """Who decided, in the composer's three words (INBOX 432).

    `ai` when the model or a match by meaning chose; `user` when the person
    did; `none` when nothing could, which is a note left in Uncategorised
    with no AI behind it. The composer said "Filed under Uncategorised (0%
    sure)" for that last one, which reads as a decision when it is the
    absence of one, and offered no way to pick a category instead.
    """
    if getattr(entry, "user_filed", False):
        return "user"
    if state == manager.WORDS_FILED:
        return "words"
    if state in (manager.AUTO_FILED, manager.STAND_IN):
        return "ai"
    if state == "pending":
        return "pending"
    if state == "failed" or not (entry.ai_confidence or 0):
        return "none"
    return "ai"


def _tag_vocabulary(session: Session) -> list[str]:
    """The notebook's own tags, most used first.

    Both tag suggesters read this, so a note filed before saving and a note
    refiled afterwards are offered the same vocabulary and cannot drift
    apart. `tags_repo.counts` is cached by notebook fingerprint, so this is
    a dictionary lookup rather than a scan on the common path.
    """
    counts = tags_repo.counts(session)
    return [tag for tag, _count in sorted(counts.items(), key=lambda row: (-row[1], row[0]))]


class SuggestTagsBody(BaseModel):
    content: str
    tags: list[str] = Field(default_factory=list)
    #: Capture's title field: a note's title says what it is, so it counts
    #: with its first line (`ai/tagging.lead`).
    title: str = Field(default="", max_length=300)

#: Said once per process, not once per keystroke pause.
_SAID_ONCE: set[str] = set()


@router.post("/suggest-tags")
def suggest_tags_for_draft(
    body: SuggestTagsBody, session: Session = Depends(get_session)
) -> dict:
    """Tag suggestions for a note that doesn't exist yet: the other half of
    a report that `/{entry_id}/reevaluate` only ever covered post-save:
    "the ai and application doesnt suggest tags either before creating a
    new note or after." "After" already had a path (buried in a kebab
    menu action, easy to never find); "before" had none at all. Reuses
    `librarian.suggest_tags` directly on the draft's own text: it only
    ever needed a string and the tags already on it, never a saved
    `Entry`, so the Capture form can offer suggestions while the user is
    still typing, before Save exists to be clicked.
    """
    content = body.content.strip()
    if body.title.strip() and content:
        content = f"# {body.title.strip()}\n\n{content}"
    if not content:
        return {"suggested_tags": [], "suggested_tag_reasons": {}}
    #: **No model, no model call** (measured on the running app: with none
    #: running, every pause in Capture asked the client for a completion from
    #: model "" and logged a WARNING with its traceback, three per note typed,
    #: and offered nothing). Then, and when the model fails, the notebook's own
    #: tags answer, the fallback filing already uses (`_suggest_after_filing`).
    model_manager, ollama = deps.get_model_manager(), deps.get_ollama()
    suggested: list[str] = []
    if model_manager.utility_model() and ollama.is_running():
        try:
            suggested = librarian.suggest_tags(
                content, body.tags, model_manager, ollama, vocabulary=_tag_vocabulary(session)
            )
        except Exception:
            logger.info("tag suggestions from the model failed; using the notebook's own", exc_info=True)
    else:
        if "no-model-tags" not in _SAID_ONCE:
            _SAID_ONCE.add("no-model-tags")
            logger.info("no model running: tag suggestions come from the notebook's own tags")
    offered = _engine_tags(session, content, body.tags, suggested, None)
    return {"suggested_tags": offered, "suggested_tag_reasons": _tag_reasons(content, offered)}


class SuggestedTagsBody(BaseModel):
    take: list[str] = Field(default_factory=list, max_length=20)
    discard: list[str] = Field(default_factory=list, max_length=20)
    #: Turned down before, offered again (the owner, 2026-10-10: "is there a
    #: way to undo it or see the list"): off `discarded_tags`, back into the
    #: suggestions.
    restore: list[str] = Field(default_factory=list, max_length=20)
    #: True stops suggesting tags for this note, False starts again (brief 89).
    mute: bool | None = None


def _discard_tags(entry, body) -> dict[str, str]:  # noqa: ANN001
    """Remember the tags turned down on this note (the last 200), and return the
    ones taken back, keyed by their folded form."""
    gone = _json_tags(entry.discarded_tags)
    gone_folded = {tag.casefold() for tag in gone}
    gone += [tag.strip() for tag in body.discard if tag.strip() and tag.strip().casefold() not in gone_folded]
    restored = {tag.strip().casefold(): tag.strip() for tag in body.restore if tag.strip()}
    gone = [tag for tag in gone if tag.casefold() not in restored]
    entry.discarded_tags = json.dumps(gone[-200:])
    return restored


@router.post("/{entry_id}/suggested-tags", response_model=EntryOut)
def answer_suggested_tags(
    entry_id: int, body: SuggestedTagsBody, session: Session = Depends(get_session)
) -> EntryOut:
    """Take or discard the tags filing suggested (INBOX 440). A taken tag is
    added like one typed by hand; a discarded one is remembered so no later
    filing pass offers it on this note again."""
    entry = NOTES.writable(session, entry_id)
    if body.mute is not None:
        entry.tag_suggest_off = body.mute
    offered = {tag.casefold(): tag for tag in _json_tags(entry.suggested_tags)}
    take = [offered.get(tag.casefold(), tag.strip()) for tag in body.take if tag.strip()]
    if take:
        have = manager.entry_tags(entry)
        folded = {tag.casefold() for tag in have}
        manager.update_entry(session, entry, tags=have + [tag for tag in take if tag.casefold() not in folded])
    restored = _discard_tags(entry, body)
    answered = {tag.casefold() for tag in [*take, *body.discard]}
    kept = [tag for tag in _json_tags(entry.suggested_tags) if tag.casefold() not in answered]
    kept_folded = {tag.casefold() for tag in kept}
    entry.suggested_tags = json.dumps(kept + [tag for key, tag in restored.items() if key not in kept_folded])
    session.commit()
    return _to_out(session, entry)


@router.post("/{entry_id}/context", response_model=EntryOut)
def add_context(
    entry_id: int, body: ContextBody, session: Session = Depends(get_session)
) -> EntryOut:
    """Append context to an existing note and let the janitor rethink the
    category with the fuller picture. If the user filed this
    entry themselves, the category is left alone, their call stands."""
    entry = NOTES.writable(session, entry_id)
    # Appending to the ciphertext made the note unreadable for good, and the
    # filing below would read its text: a private note is edited in its own
    # editor (same refusal as generate-title and remove-title).
    if entry.is_private:
        raise HTTPException(
            status_code=400, detail="Make this note readable first: private notes can't be edited here."
        )
    entry.content = f"{entry.content}\n\n--- added context ---\n{body.text.strip()}"
    manager.mark_edited(entry)
    manager.log_action(session, "edited", "entry", entry.id, "context added")
    session.commit()

    # The old vector describes the old text, refresh it, best effort.
    try:
        session.execute(
            sa_delete(EmbeddingRecord).where(EmbeddingRecord.entry_id == entry.id)
        )
        session.commit()
    except Exception:  # noqa: BLE001  # never fail the edit over the index
        logging.getLogger("tessellate.embeddings").warning(
            "couldn't clear the stale vector for entry %s", entry.id, exc_info=True
        )
        session.rollback()
    else:
        deps.store_quietly(session, entry)

    filed_by = None
    if not entry.user_filed:
        try:
            category, confidence, filed_by = janitor.categorise(
                session,
                entry.content,
                deps.get_embeddings(),
                deps.get_model_manager(),
                deps.get_ollama(),
                exclude_entry_id=entry.id,  # don't let it anchor to itself
            )
            if filed_by != "none":
                manager.record_filing(
                    session, entry, category,
                    by=janitor.filed_by_label(
                        filed_by, confidence, deps.get_model_manager(), deps.get_embeddings()
                    ),
                )
                entry.ai_confidence = confidence
                # The same two lines as the create paths: a category the AI
                # chose here is one a later move by hand corrects, and without
                # the flag that correction went unrecorded (Brief 13).
                if janitor.settled_state(filed_by) != "done":
                    entry.filing_state = janitor.settled_state(filed_by)
                session.commit()
        except Exception:
            logger.warning("re-filing after new context failed", exc_info=True)
            filed_by = None  # AI down, the note keeps its old category

    return _to_out(session, entry, filed_by=filed_by)


class ImproveBody(BaseModel):
    text: str
    mode: str = "proofread"  # proofread | rewrite | concise | custom
    # Only read when mode == "custom", the user's own instruction, in their
    # own words, instead of picking from the three presets. Length-capped to
    # match the input's own maxlength; this is one line of steering, not a
    # second prompt.
    custom_instruction: str | None = Field(default=None, max_length=200)


@router.post("/improve")
def improve_writing(body: ImproveBody) -> dict:
    """Return an AI-polished version of some note text without saving it, 
    the UI shows a before/after and the user decides. Never
    touches the note itself; the AI is a servant, not a gatekeeper."""
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="There's no text to improve.")
    custom_instruction = (body.custom_instruction or "").strip()
    if body.mode == "custom" and not custom_instruction:
        raise HTTPException(
            status_code=400, detail="Say what you want changed, then try again."
        )
    if not deps.get_ollama().is_running():
        #: O7 (INBOX 904 B33): proofreading is the app's own with no model;
        #: rewording is writing, and says so.
        if body.mode != "proofread":
            raise HTTPException(
                status_code=503,
                detail="Rewording needs a model (Settings, Models). Proofread works without one.",
            )
        from tessellate.ai import proofread

        improved, changes = proofread.proofread(text)
        return {
            "original": text, "improved": improved, "mode": body.mode, "by": "composer",
            "said": proofread.said(changes, text), "truncated": proofread.covered(text) < len(text),
        }
    try:
        improved = librarian.improve_writing(
            text,
            body.mode,
            deps.get_model_manager(),
            deps.get_ollama(),
            custom_instruction=custom_instruction,
        )
    except OllamaError as exc:
        # The provider's own text names the model and carries the transport's
        # error; it belongs in the log, not in the toast.
        logger.warning("improve writing failed", exc_info=True)
        raise HTTPException(status_code=502, detail=librarian.AI_FAILED_MESSAGE) from exc
    return {"original": text, "improved": improved, "mode": body.mode}


#: How many concept matches `?semantic=true` returns. A search result is a
#: shortlist to read, not a second copy of the notebook.
SEMANTIC_LIST_LIMIT = 25


#: KG7: the table view's columns, and its rows, at most.
QUERY_COLUMNS_MAX = 8
QUERY_ROWS_MAX = 500


@router.get("/query")
def query_entries(q: str = "", session: Session = Depends(get_session)) -> dict:
    """The notes a live query matches (GRAPH_PLAN KG7, `entry/query.py`),
    newest first, with the table view's columns (the properties they carry,
    most common first, `type` leading) and rows. The Notes list, the table
    and the graph all take these ids, so one query is one answer."""
    from tessellate.entry import query as live_query

    terms = live_query.parse(q)
    if not terms:
        return {"ids": [], "columns": [], "rows": [], "structural": False, "rollups": {}}
    ids = live_query.run(session, q)
    rows = []
    counts: dict[str, int] = {}
    shown = ids[:QUERY_ROWS_MAX]
    entries = {e.id: e for e in session.scalars(select(Entry).where(Entry.id.in_(shown)))} if shown else {}
    for entry_id in shown:
        entry = entries[entry_id]
        content = manager_text.readable_content(entry)
        found = {} if entry.is_private else note_properties.split(content)[0]
        for key in found:
            counts[key] = counts.get(key, 0) + 1
        rows.append({
            "id": entry_id,
            "title": manager_text.extract_title(content) or manager_text.plain_label(content, 60) or "Untitled note",
            "properties": found,
        })
    columns = sorted(counts, key=lambda k: (k != "type", -counts[k], k))[:QUERY_COLUMNS_MAX]
    return {
        "ids": ids,
        "columns": columns,
        "rows": rows,
        "structural": live_query.is_structural(terms),
        #: The footer's count, sum, min, max, earliest and latest, over every
        #: match (not only the rows drawn), per column.
        "rollups": live_query.rollups(session, ids, columns),
    }


#: A page of the plain list, not a hard ceiling on notebook size, the
#: frontend fetches pages in a loop until X-Total-Count says it has
#: everything (loadEntries in app.js). Bounds each individual request so a
#: notebook that has grown for years can't make one response unbounded; the
#: max just stops a client from asking for one absurdly large page.
ENTRIES_PAGE_SIZE = 1000
ENTRIES_PAGE_SIZE_MAX = 5000
#: How many notes one `?ids=` read may name: more than any one change touches
#: (a bulk action over more falls back to the paged list on the client).
ENTRIES_BY_IDS_MAX = 200


#: The most characters `?preview=` may ask for: past it a caller wants the text.
ENTRIES_PREVIEW_MAX = 2000


_TASK_OPEN = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+\[[ \t]\]", re.M)
_TASK_DONE = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+\[[xX]\]", re.M)
#: The list's own `[[wiki link]]` test (`matchesSearch`, `is:linked`), for the part of a note past the preview.
_WIKI_LINK = re.compile(r"\[\[[^\]\n]{1,120}\]\]")


_FENCE = re.compile(r"^[ \t]*(?:```|~~~)")
_ATX = re.compile(r"^#{1,6}[ \t]+\S")


def _heading_count(text: str) -> int:
    """`#` headings outside code fences, as the card's outline (`mdTocEntries`) counts them."""
    fenced, count = False, 0
    for line in text.split("\n"):
        if _FENCE.match(line):
            fenced = not fenced
        elif not fenced and _ATX.match(line):
            count += 1
    return count


def _previewed(rows: list[EntryOut], preview: int) -> list[EntryOut]:
    """`rows` with each note's text cut to `preview` characters (0 keeps it
    whole), at the last space before the cut when there is one, and
    `content_truncated` set so a caller knows it holds a part. `content_hash`
    stays the whole text's, so a save is still checked against the note as it
    is. A list that draws a row's first lines never needs the rest (BK10)."""
    if not preview:
        return rows
    for row in rows:
        #: The numbers a list draws from the whole text (the dashboard's words and open tasks), counted before the cut.
        row.word_count = cjk.word_count(row.content)
        row.tasks_open = len(_TASK_OPEN.findall(row.content))
        row.tasks_done = len(_TASK_DONE.findall(row.content))
        row.wiki_linked = bool(_WIKI_LINK.search(row.content))
        row.heading_count = _heading_count(row.content)
        row.gist = "" if row.is_private else composer_gist.gist(row.content)
        #: A meeting's card reads its sections from the whole text (`meetingGlance`), so a meeting is sent whole. So is
        #: a private note: the index never reads one, so the list's filter box matches it on the text the list holds
        #: (INBOX 1525 review). Locked, its text is the short placeholder anyway.
        whole = row.is_private or "meeting" in {v.lower() for v in row.properties.get("type", [])}
        if len(row.content) > preview and not whole:
            cut = row.content[:preview]
            row.content = (cut.rsplit(None, 1)[0] if " " in cut or "\n" in cut else cut).rstrip()
            row.content_truncated = True
    return rows


@router.get("", response_model=list[EntryOut])
def list_entries(
    response: Response,
    deleted: bool = False,
    archived: bool = False,
    semantic: bool = False,
    q: str = "",
    limit: int = Query(default=ENTRIES_PAGE_SIZE, ge=1, le=ENTRIES_PAGE_SIZE_MAX),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = paging.cursor_param(),
    #: `after` is the same cursor under the name ARCH-04's first cut gave
    #: it; one keyset, read by `paging` either way.
    after: str = Query(default="", max_length=512),
    # **This list is the notes list, so boards are not in it by default.**
    #
    # Reported: "I made a mindmap naming it test and I think it came up as a
    # new note??", it did, on every surface built on this response. A board
    # (and a mind map, which is a board with `type: "map"`) is an `Entry`, so
    # it came back here with everything else; measured on a notebook with
    # nine maps, ten of the Notes list's twelve rows were maps.
    #
    # The default is the fix, rather than a filter in each of the four
    # surfaces that draw notes, because "the same object drawn five ways" is
    # this app's recurring failure and four client-side filters is that shape
    # exactly. `boards=only` is how the two callers that genuinely want boards
    # (the `[[wiki]]` resolver and the editor's `@` picker) ask for them, and
    # `boards=include` restores the old response for anything wanting both.
    boards: str = Query(default=manager.BOARDS_EXCLUDE),
    # **Just these notes, of the same list** (audit 2026-10-05, FE-05). Every
    # save used to re-read the whole notebook (27 requests and 5.3 MB at
    # 5,010 notes); the client now asks for the notes a change touched and
    # patches them in. An id outside the view (binned, archived, a board) is
    # simply absent, which is how the client learns to drop it, and
    # `X-Total-Count` stays the whole list's size so it can check its patched
    # list against this one. No side effect: unlike `GET /entries/{id}`,
    # this is not opening the note.
    ids: str = Query(default="", description="Comma-separated note ids"),
    #: **Each note's first characters, not all of it** (audit 1031 BK10): 0
    #: keeps the whole text, which every caller in the app that holds the list
    #: for search and the card body still asks for. `content_truncated` marks
    #: a clipped row; `content_hash` stays the whole text's.
    preview: int = Query(default=0, ge=0, le=ENTRIES_PREVIEW_MAX),
    session: Session = Depends(get_session),
) -> list[EntryOut]:
    """Normal list, the recycle bin when ?deleted=true, the archive when
    ?archived=true, or a concept search. `deleted` and `archived` are
    mutually exclusive views (each its own held-back set), not filters
    that combine: same as `deleted` already worked before `archived`
    existed.

    `?semantic=true&q=…` is the one case the browser cannot do for itself: the
    notes list is filtered client-side by keyword, but cosine distance needs
    the vectors, which only live here.

    `limit`/`offset` page the plain list; `X-Total-Count` on the response
    says the real size regardless of the page, so a caller knows when it has
    everything. Was genuinely unbounded before, every note, every load, no
    matter the notebook's size: which is real risk for a "just works" local
    app that's supposed to degrade gracefully rather than time out or OOM.
    """
    cursor = cursor or after or None
    if boards not in manager.BOARD_MODES:
        raise HTTPException(
            status_code=422,
            detail=f"Pick one of these board options: {', '.join(manager.BOARD_MODES)}.",
        )
    if semantic and q:
        from tessellate.core import deps

        # The *complete* id set, deliberately not paginated: `allowed` below
        # decides which semantic hits are even in scope for this view (bin,
        # archive, or live), and paginating this fetch would silently drop
        # legitimate matches that happen to live past the first page. Ids
        # only, no row bodies, cheap even at real notebook scale, and the
        # thing the original unbounded-response risk was actually about was
        # sending full rows over HTTP, not counting ids in-process.
        scope_ids = manager.entry_id_scope(
            session, deleted=deleted, archived=archived, boards=boards
        )

        # Ranked, and returned ranked. The first version rebuilt the result as
        # `[e for e in entries if e.id in found_ids]`, which is the *notebook's*
        # order: so the best match could land anywhere in the list and the
        # feature looked like it was picking notes at random.
        results = search_manager.semantic_search(
            session, q, deps.get_embeddings(), limit=SEMANTIC_LIST_LIMIT
        )
        if results is None:
            # No embedding backend ready. Saying so beats silently handing back
            # the entire notebook as though it were the search result, the
            # caller can fall back to its own keyword filter.
            raise HTTPException(
                status_code=503,
                detail="Semantic search isn't ready yet: the embedding model is still loading.",
            )
        # `semantic_search` already drops anything under MIN_SIMILARITY; a
        # second threshold here was a different number for the same job.
        matched = [e for e, _score in results if e.id in scope_ids]
        response.headers["X-Total-Count"] = str(len(matched))
        return _previewed(_to_out_bulk(session, matched), preview)

    if ids:
        parts = [part.strip() for part in ids.split(",") if part.strip()]
        if not all(part.isdigit() for part in parts) or len(parts) > ENTRIES_BY_IDS_MAX:
            raise HTTPException(
                status_code=422,
                detail=f"Ask for up to {ENTRIES_BY_IDS_MAX} note ids, as numbers.",
            )
        if deleted or archived:
            raise HTTPException(
                status_code=422, detail="Note ids are read from the notes list only."
            )
        wanted = [int(part) for part in parts]
        entries = manager.list_entries(session, boards=boards, ids=wanted)
        response.headers["X-Total-Count"] = str(manager.count_notes(session, include_archived=False, boards=boards, include_drafts=True))
        return _previewed(_to_out_bulk(session, entries), preview)

    if deleted or archived:
        # The bin and the archive page by position: both are short, both sort
        # on a column that can be NULL on rows from before it existed (a
        # keyset over NULLs needs a second ordering rule), and neither is
        # written to while somebody scrolls it.
        page = paging.resolve(response, offset=offset, limit=limit, cursor=cursor)
        lister = manager.list_deleted_entries if deleted else manager.list_archived_entries
        entries = lister(session, limit=limit, offset=page.offset)
        total = (
            manager.count_deleted_entries(session)
            if deleted
            else manager.count_archived_entries(session)
        )
        page.finish(len(entries), total)
    else:
        # The notes list pages by keyset (B7): a note saved while page one is
        # on screen cannot push a row of page one onto page two as well.
        after = paging.read_keyset(cursor, 3) if cursor else None
        entries = manager.list_entries(
            session,
            limit=limit + 1,
            offset=0 if after else offset,
            boards=boards,
            after=after,
        )
        more = len(entries) > limit
        entries = entries[:limit]
        if more and entries:
            response.headers[paging.NEXT_CURSOR] = paging.keyset_cursor(
                manager.list_sort_key(entries[-1])
            )
        total = manager.count_notes(session, include_archived=False, boards=boards, include_drafts=True)
    response.headers["X-Total-Count"] = str(total)
    return _previewed(_to_out_bulk(session, entries), preview)


# Declared before /{entry_id} so "most-accessed" isn't parsed as an id.
@router.get("/most-accessed", response_model=list[EntryOut])
def most_accessed(session: Session = Depends(get_session)) -> list[EntryOut]:
    """Top entries by how often they've been opened or matched a
    question: the quick-access dashboard."""
    entries = manager.most_accessed_entries(session, limit=5)
    return _to_out_bulk(session, entries)


# Onboarding's own "is this notebook empty" check: deliberately just a
# number (never the full /entries payload) so the first-run tour can decide
# whether to offer example notes without pulling a real notebook's worth of
# content over the wire just to find out it isn't empty.
@router.get("/count")
def count_entries(session: Session = Depends(get_session)) -> dict:
    return {"count": manager.count_notes(session)}


#: The most ids one `/entries/changes` answer carries; past it, `more` says
#: re-read the list (a bulk retag or an import touched more than a patch is
#: worth).
CHANGES_IDS_MAX = 60
#: How far behind the newest change the next stamp starts (see below).
CHANGES_OVERLAP_SECONDS = 2.0


@router.get("/changes")
def entry_changes(
    since: str = Query(default="", max_length=40),
    session: Session = Depends(get_session),
) -> dict:
    """**Which notes changed since `since`** (INBOX 881, the owner: "what if I
    make a change on my phone?? does it live update??"). The notes list on
    another device asks every few seconds and patches those ids in with
    `refreshEntries`. With no `since` it is only a stamp to ask from next.

    By `updated_at`, which every write moves (an edit, a filing, a bin, an
    archive, an open too: a refresh of an unchanged row costs one small read
    and is the price of not missing a change made by a path that forgot
    `edited_at`). Boards are left out, as the list leaves them out. The stamp
    sent back is two seconds behind now, so a write whose
    transaction committed a moment after this read is asked about again
    rather than missed (and never further back than the newest change, so a
    change is not sent for ever); the client drops ids it has already seen at
    the same `updated_at`, which `stamps` carries."""
    now = utcnow()
    overlap = timedelta(seconds=CHANGES_OVERLAP_SECONDS)
    if not since:
        return {"since": (now - overlap).isoformat(), "ids": [], "stamps": {}, "more": False}
    try:
        after = datetime.fromisoformat(since)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="That time is not one this app wrote.") from exc
    if after.tzinfo is None:
        after = after.replace(tzinfo=now.tzinfo)
    rows = session.execute(
        select(Entry.id, Entry.updated_at)
        .where(Entry.updated_at > after, Entry.is_board.is_(False))
        .order_by(Entry.updated_at.desc())
        .limit(CHANGES_IDS_MAX + 1)
    ).all()
    more = len(rows) > CHANGES_IDS_MAX
    rows = rows[:CHANGES_IDS_MAX]
    newest = max((r.updated_at for r in rows), default=None)
    stamp = max(after, min(newest, now - overlap) if newest is not None else now - overlap)
    return {
        "since": stamp.isoformat(),
        "ids": [r.id for r in rows],
        "stamps": {str(r.id): r.updated_at.isoformat() for r in rows},
        "more": more,
    }


@router.post("/seed-examples")
def seed_example_entries(session: Session = Depends(get_session)) -> dict:
    """The onboarding tour's "add example notes" offer (ROADMAP.md's
    onboarding item). Refuses on any notebook that already has a note, 
    see `manager.seed_example_notes`'s own guard."""
    created = manager_wiki.seed_example_notes(session)
    return {"created": created}


#: How many notes one counts call may cover. A page of the list is at most
#: `ENTRIES_PAGE_SIZE` on the client (50); anything past that is a caller
#: asking for a report, not a chip row.
REFERENCE_COUNT_IDS_MAX = 60


@router.get("/reference-counts")
def entry_reference_counts(
    ids: str = Query(default="", description="Comma-separated note ids"),
    session: Session = Depends(get_session),
) -> dict:
    """Per note, how many things point at it, by kind, for one page at once.

    INBOX 246's third gap. A card showed nothing until Connections was opened,
    so a note on two boards and in three documents looked exactly like a note
    nothing had ever touched. The row on the card needs a number per kind and
    nothing else, and it needs it for every note on screen in one round trip:
    fifty cards asking `/references` each would be fifty scans per render.

    One reader. The numbers come from the same `_reference_rows` the
    Referenced-by row draws, so the chip and the row cannot disagree about
    what counts as a reference (the LIKE-then-verify rule, the deleted-note
    rule, the board-versus-map rule all live there once).

    A static path before the `/{entry_id}/...` routes on purpose: FastAPI
    matches in declaration order, and `{entry_id}` is typed `int`, so
    "reference-counts" would 422 rather than fall through if it came second.
    """
    wanted: list[int] = []
    for part in ids.split(","):
        part = part.strip()
        if part.isdigit():
            wanted.append(int(part))
    wanted = wanted[:REFERENCE_COUNT_IDS_MAX]
    if not wanted:
        return {"counts": {}}
    #: One query for the page's rows, then the reader per note. Rows that do
    #: not exist or are deleted are simply absent from the answer, so a stale
    #: id on the client is a missing key rather than a 404 that fails the
    #: whole page's chips.
    entries = session.scalars(
        select(Entry).where(Entry.id.in_(wanted), Entry.is_deleted.is_(False))
    ).all()
    counts: dict[str, dict[str, int]] = {}
    #: The whole page in one go (`_reference_rows_batch`): the per-note reader
    #: this called was four statements a card, and sixty cards at every unlock.
    page = _reference_rows_batch(session, list(entries))
    for entry in entries:
        by_kind: dict[str, int] = {}
        for row in page[entry.id]:
            by_kind[row["kind"]] = by_kind.get(row["kind"], 0) + 1
        by_kind["total"] = sum(by_kind.values())
        counts[str(entry.id)] = by_kind
    return {"counts": counts}


@router.get("/{entry_id}", response_model=EntryOut)
def get_entry(
    entry_id: int,
    response: Response,
    deleted: bool = False,
    open: bool = False,  # noqa: A002 - the query word is the contract
    session: Session = Depends(get_session),
) -> EntryOut:
    """One entry. `?deleted=true` also reaches into the bin.

    **Only `?open=1` counts as an open** (audit 1031 N5). The graph hover card,
    the swipe sheet, the chat agent and the image layout all read a note this
    way without a person reading it, and each bumped "Views", the "most used"
    sort and the Continue pill; a read is not an open unless the caller says
    a person is looking at the note.

    The bin used to be a panel that listed every deleted note with its full
    text, so "read a binned note before deciding whether to restore it" came
    free. The Library shows a preview instead, which is right for a grid of
    mixed things and wrong as the *only* way to see a note you are about to
    delete for good: so the reader needs a way to fetch one binned note.

    Two things stay different from a live read, and both are deliberate:
    a deleted note is only reachable when the caller says so (a stale link to
    a binned note should still 404 rather than quietly resurrect it), and
    reading one does **not** count as using it. `access_count` feeds
    "most accessed", and a note in the bin climbing that list because you
    looked at it on the way to deleting it is the counter lying.
    """
    entry = _existing_entry(session, entry_id)
    if entry.is_deleted and not deleted:
        raise HTTPException(status_code=404, detail="That note could not be found.")
    if open and not entry.is_deleted:
        entry.access_count += 1  # opening an entry counts as using it
        #: And on which day (WORLD_CLASS_PLAN section 17 row 5): "most opened
        #: this month" cannot be read off an all-time count.
        from tessellate.entry import opens

        opens.record_open(session, entry.id)
        # And *when*, which is the half the dashboard's Continue pill needs:
        # a count cannot answer "the note I was last in", and `updated_at`
        # only moves when the text changes, so reading an old note left the
        # pill pointing at whatever was newest. Same guard as the count: a
        # note read on its way out of the bin has not been come back to.
        entry.last_opened_at = utcnow()
        #: The in-app companion's reading glasses and covered eyes, for the desk one (W31): a kind and a time. A private
        #: note is only ever the generic kind (not its length, not which note).
        if _kept_private(session, entry):
            companion_events.record("private_note")
        elif len(entry.content or "") > LONG_NOTE_CHARS:
            companion_events.record("long_note")
    if not entry.is_deleted:
        # A private note has no audit trail at all otherwise, encrypted at
        # rest and invisible to the AI is the whole promise, but nothing
        # recorded *when* one was actually opened and decrypted for
        # reading, which is the one thing that would tell you if that
        # promise had ever been tested. Scoped to private notes only: every
        # other note already has plenty of activity logged elsewhere (see
        # the Library's own "activity is 93%+ of a real notebook" note) and
        # doesn't need a second entry for the same open.
        # Only when the vault is actually open, readable_content() returns
        # a placeholder ("Private note: unlock to read it.") rather than
        # the real text when it's locked, and logging "decrypted" for a
        # request that decrypted nothing is worse than not logging at all:
        # a trail meant to build confidence that lies about what happened
        # is the one bug this feature cannot afford.
        if bool(getattr(entry, "is_private", False)) and vault.key() is not None:
            manager.log_action(session, "decrypted", "entry", entry.id)
        session.commit()
    out = _to_out(session, entry)
    #: B7: the note's version as an HTTP entity tag, the same text hash the
    #: editor already sends back as `base_hash`, so a client that never reads
    #: the body's fields can still say "only if it is still this version" with
    #: `If-Match` on its write (`refuse_unless_match`).
    response.headers["ETag"] = entity_tag(out.content_hash)
    return out


def _refuse_while_sealed(entry) -> None:  # noqa: ANN001
    """Export and history hand out a note's text, so a locked private note
    answers 409 rather than a placeholder that looks like the note (INBOX
    1437). The same gate as writes: the person unlocks, then asks again."""
    if manager.note_is_sealed(entry.is_private):
        raise HTTPException(status_code=409, detail="Unlock first.")


@router.get("/{entry_id}/export.md")
def export_entry(entry_id: int, session: Session = Depends(get_session)) -> Response:
    """One note's own text, as a download, BACKLOG.md §95 item D.14: "Full
    export exists. There is no way to hand one note to someone."

    Mirrors `routes_documents.py`'s `export_markdown` (same route shape,
    same `Content-Disposition` filename sanitising) rather than reusing it
    directly: a note has no `file_type` the way a document does, so there
    is no second branch to share, and the two routes would only be coupled
    by the part that's already this short.

    A locked private note answers 409 "Unlock first." (`_refuse_while_sealed`):
    a download named like the note and holding a placeholder is a file that
    looks like the note and is not.
    """
    entry = _existing_entry(session, entry_id)
    if entry.is_deleted:
        raise HTTPException(status_code=404, detail="That note could not be found.")
    _refuse_while_sealed(entry)
    content = manager_text.readable_content(entry)
    title = manager_text.extract_title(content) or content.strip()[:60] or "Untitled note"
    body = content if manager_text.extract_title(content) else f"# {title}\n\n{content}"
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers=attachment_headers(safe_filename(title, "md")),
    )


def _content_change(entry, body: EntryUpdate) -> tuple[bool, str | None]:  # noqa: ANN001
    """`(changed, text to store)`; the text is None when nothing is written."""
    new_content = body.content
    if entry.is_private and body.content is not None:
        #: A private note's column holds ciphertext, so "changed" is judged on
        #: the text the editor saw, and the new text is stored encrypted: it
        #: was written plain, with the note still flagged private, and sat in
        #: `entries.content` and the full-text index in the clear (found
        #: 2026-10-04 by scanning a data dir for a private note's words).
        content_changed = body.content != manager_text.readable_content(entry)
        new_content = _stored_form(entry, body.content) if content_changed else None
    else:
        content_changed = body.content is not None and body.content != entry.content
    return content_changed, new_content


def _after_content_edit(session: Session, entry, body: EntryUpdate) -> None:  # noqa: ANN001
    """What an edited text sets going: the stale vector goes, links resolve, media settles."""
    # The old vector describes the old text, refresh it, best effort.
    try:
        session.execute(
            sa_delete(EmbeddingRecord).where(EmbeddingRecord.entry_id == entry.id)
        )
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
        _queue_embedding(entry)
    # Editing a note can introduce new [[links]]; resolve those too.
    try:
        manager_wiki.sync_wiki_links(session, entry)
        manager_wiki.resolve_links_to(session, entry)
        session.commit()
    except Exception:
        session.rollback()
        logger.warning("couldn't sync wiki links for entry %s", entry.id, exc_info=True)
    # Same "committed" trigger point as create_entry, an edit can be
    # the first time an image the note already referenced actually
    # gets saved (a staged upload attached, then the note edited to
    # include it, rather than created with it already there).
    _process_committed_media(session, body.content)


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


@router.put("/{entry_id}", response_model=EntryOut)
def update_entry(
    entry_id: int,
    body: EntryUpdate,
    response: Response,
    session: Session = Depends(get_session),
    if_match: str | None = Header(default=None),
) -> EntryOut:
    """Manual override: the user can correct anything the AI decided
    (plan §4: the AI is a servant, not a gatekeeper).

    `If-Match` (B7) is the HTTP spelling of `base_hash`: a write that names
    the version it was made from is refused with 412 when the note is no
    longer that version, whatever the body changes, so an outside client
    cannot clobber a background AI edit it never saw."""
    entry = NOTES.writable(session, entry_id)
    refuse_unless_match(
        if_match,
        current_hash=content_hash(manager_text.readable_content(entry)),
        current=lambda: _to_out(session, entry),
        noun="note",
    )
    #: Two windows, one note (WORLD_CLASS_PLAN 22.1 item 5): a save that
    #: started from text another window has since replaced is refused, with
    #: that text, before anything is written. Compared as the reader sees it
    #: (decrypted), which is what the editor's hash was taken from.
    if body.base_hash and body.content is not None:
        refuse_if_stale(
            base_hash=body.base_hash,
            current_text=manager_text.readable_content(entry),
            new_text=body.content,
            current=lambda: _to_out(session, entry),
            noun="note",
        )
    content_changed, new_content = _content_change(entry, body)
    tags_changed = body.tags is not None and body.tags != manager.entry_tags(entry)
    #: The note's [[name]] before the edit (a private note is never a target).
    old_name = (
        manager_wiki.wiki_opening(entry.content) if content_changed and not entry.is_private else ""
    )
    #: A save that carries an applied Atlas suggestion is both of theirs.
    with events.acting_as(ACTOR_USER_AND_AI) if body.ai_assisted else contextlib.nullcontext():
        # Snapshot BEFORE the change, so the newest revision is always the
        # version being replaced rather than the one replacing it.
        if content_changed or tags_changed:
            manager.record_revision(session, entry)
        manager.update_entry(
            session,
            entry,
            content=new_content,
            category_name=body.category,
            tags=body.tags,
        )
    if body.pinned is not None and body.pinned != entry.pinned:
        entry.pinned = body.pinned
        manager.log_action(
            session, "edited", "entry", entry.id, "pinned" if body.pinned else "unpinned"
        )
        session.commit()
    _apply_flags(session, entry, body)
    if content_changed:
        _after_content_edit(session, entry, body)
    out = _to_out(session, entry)
    out.wiki_rename = _wiki_rename(session, entry, old_name)
    response.headers["ETag"] = entity_tag(out.content_hash)
    return out


class WikiRenameIn(BaseModel):
    old: str = Field(min_length=1, max_length=120)


@router.post("/{entry_id}/wiki-rename")
def wiki_rename(entry_id: int, body: WikiRenameIn, session: Session = Depends(get_session)) -> dict:
    """Rewrite `[[old]]` as this note's current name in every note that still
    writes the old one (GRAPH_PLAN 518; offered by the edit that renamed it)."""
    entry = NOTES.writable(session, entry_id)
    first = (manager_text.readable_content(entry) or "").strip().split("\n", 1)[0]
    new_name = re.sub(r"^\s{0,3}#{1,6}\s+", "", first).strip()
    if not new_name or len(new_name) > 120 or "]" in new_name or "[" in new_name:
        raise HTTPException(status_code=422, detail="This note's first line can't be a [[name]].")
    notes: list[dict] = []
    rewritten = manager_wiki.rewrite_wiki_name(session, entry, body.old, new_name, notes)
    return {"rewritten": rewritten, "notes": notes}


@router.delete("/{entry_id}", response_model=EntryOut)
def delete_entry(
    entry_id: int,
    session: Session = Depends(get_session),
    if_match: str | None = Header(default=None),
) -> EntryOut:
    """Soft delete → recycle bin. Restorable until purged. `If-Match` as on
    the edit: a client binning the version it read does not bin a newer one."""
    entry = _existing_entry(session, entry_id)
    refuse_unless_match(
        if_match,
        current_hash=content_hash(manager_text.readable_content(entry)),
        current=lambda: _to_out(session, entry),
        noun="note",
    )
    if not entry.is_deleted:
        manager.soft_delete_entry(session, entry)
        companion_events.record("private_note" if _kept_private(session, entry) else "note_binned")  # kind and time only (W31)
    return _to_out(session, entry)


@router.post("/{entry_id}/restore", response_model=EntryOut)
def restore_entry(entry_id: int, session: Session = Depends(get_session)) -> EntryOut:
    entry, _was_binned = content_repo.restore(session, "note", entry_id)
    session.commit()
    return _to_out(session, entry)


@router.post("/{entry_id}/archive", response_model=EntryOut)
def archive_entry(entry_id: int, session: Session = Depends(get_session)) -> EntryOut:
    """Kept, but out of the way (BACKLOG §30b): distinct from the recycle
    bin: never auto-cleared, never purgeable, no confirmation needed since
    nothing is at risk of being lost."""
    entry = NOTES.writable(session, entry_id)
    if not entry.archived_at:
        manager.archive_entry(session, entry)
    return _to_out(session, entry)


@router.post("/{entry_id}/unarchive", response_model=EntryOut)
def unarchive_entry(entry_id: int, session: Session = Depends(get_session)) -> EntryOut:
    entry = NOTES.writable(session, entry_id)
    if entry.archived_at:
        manager.unarchive_entry(session, entry)
    return _to_out(session, entry)


@router.delete("/{entry_id}/purge")
def purge_entry(entry_id: int, session: Session = Depends(get_session)) -> dict:
    """Permanently delete ONE note from the recycle bin. Asked for directly.

    Emptying the whole bin was all-or-nothing, so getting rid of a single note
    for good meant destroying everything else in there too, which is why
    people leave the bin full instead, and then the bin is not a bin.

    **Only a binned note can be purged.** A note still in the notebook has to
    go through `DELETE /entries/{id}` first, so there is always the soft-delete
    step between an ordinary click and permanent loss. Enforced here rather
    than trusted to the UI: this is the one route in the app that destroys
    something with no undo.
    """
    entry = _existing_entry(session, entry_id)
    if not entry.is_deleted:
        raise HTTPException(
            status_code=400,
            detail="Only notes in the recycle bin can be permanently deleted.",
        )
    removed = manager_purge.purge_entries(
        session, [entry], uploads_dir=deps.get_config().uploads_dir
    )
    return {"purged": removed, "id": entry_id}


class LinkBody(BaseModel):
    target_id: int
    # Optional: "why are these connected?" A shared tag or a reply thread
    # says why on its own; a manual link often doesn't.
    reason: str | None = Field(default=None, max_length=200)
    # What kind of connection, from core.database.LINK_TYPES. Optional, and an
    # unrecognised value is stored as null rather than rejected, see
    # manager.create_link on why a typo should not cost you the link.
    link_type: str | None = Field(default=None, max_length=24)
    #: How sure the suggestion was, kept with a `reason` its signals wrote
    #: (GRAPH_PLAN KG9). Ignored without a reason.
    reason_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    #: GRAPH_PLAN KG3: the link's own properties.
    props: dict | None = None

    @field_validator("props")
    @classmethod
    def _props_shape(cls, value: dict | None) -> dict | None:
        return check_link_props(value)


#: A link's properties: a few short scalar values, never a document.
LINK_PROPS_MAX = 20


def check_link_props(value: dict | None) -> dict | None:
    if value is None:
        return None
    if len(value) > LINK_PROPS_MAX:
        raise Said(f"A link holds {LINK_PROPS_MAX} properties at most.")
    out = {}
    for key, item in value.items():
        key = " ".join(str(key).split())[:40]
        if not key:
            raise ValueError("A property needs a name.")
        if item is not None and not isinstance(item, (str, int, float, bool)):
            raise ValueError("A property is a word, a number or yes/no, not a list or a group.")
        out[key] = item[:200] if isinstance(item, str) else item
    return out


class LinkPatchBody(BaseModel):
    #: A kind (built-in or custom), or null for none. Unlike creation, a bad
    #: name here is refused: changing a link's type is the whole request.
    #: Only the fields sent change.
    link_type: str | None = Field(default=None, max_length=24)
    props: dict | None = None
    #: INBOX 693: true for a link that runs both ways, false for one way,
    #: null to let its type decide (`manager.is_two_way_link`).
    two_way: bool | None = None

    @field_validator("props")
    @classmethod
    def _props_shape(cls, value: dict | None) -> dict | None:
        return check_link_props(value)


class LinkReasonBody(BaseModel):
    # None (or omitted/blank) clears the reason, this is also how a link
    # that got an auto-deduced reason it disagrees with is corrected back
    # to nothing, same as it would have started with.
    reason: str | None = Field(default=None, max_length=200)


class PrivacyBody(BaseModel):
    private: bool


#: How many events one request of a note's history returns. A note edited
#: every day for a year has a history worth paging through rather than
#: sending whole to a sheet that shows a dozen rows at a time.
HISTORY_PAGE = 50


def _stored_form(entry, text: str, session: Session | None = None) -> str:  # noqa: ANN001
    """A past version's text, in the form this note stores it in now.

    A private note's restored text marks the pictures it embeds, as an edit
    does (SEC-A2): a picture only an older version used was served locked."""
    stored = manager_text.content_for_entry(entry, text or "")
    if stored is None:
        raise HTTPException(status_code=409, detail="Unlock the app first: this version needs the encryption key.")
    if session is not None and entry.is_private:
        manager_text.flag_private_media(session, _readable(stored))
    return stored


def _readable(content: str) -> str:
    """Decrypt stored content for display, the same way a note itself is.

    `manager.readable_content` reads one attribute, so an event's stored
    content can borrow it without a row to hang it on.
    """
    return manager_text.readable_content(SimpleNamespace(content=content or ""))


class MakeAllPrivateBody(BaseModel):
    confirm: bool


@router.post("/make-all-private")
def make_all_private(body: MakeAllPrivateBody, session: Session = Depends(get_session)) -> dict:
    """Seal every ordinary note (INBOX 1695 d). The client asks first; the
    server refuses without `confirm` so a stray call cannot do it."""
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Confirm first: this locks every note.")
    sealed = manager_private.make_all_private(session)
    if sealed is None:
        raise HTTPException(status_code=409, detail="Unlock the app first: the encryption key isn't loaded.")
    session.commit()
    if sealed:
        manager_private.scrub_private_leftovers(session)
    return {"sealed": len(sealed), "ids": sealed}


@router.post("/{entry_id}/privacy", response_model=EntryOut)
def set_entry_privacy(
    entry_id: int, body: PrivacyBody, session: Session = Depends(get_session)
) -> EntryOut:
    """Encrypt this note at rest, or decrypt it again.

    Needs the vault open, which means the app must be unlocked, the data key
    only exists in memory while it is.
    """
    entry = NOTES.writable(session, entry_id)
    if not body.private and private_space.is_private_space(session, entry.workspace_id):
        # INBOX 1727: no per-note opt-out inside a private space.
        raise HTTPException(status_code=409, detail=private_space.MOVE_OUT_TO_SHARE)
    if not manager_private.set_private(session, entry, body.private):
        raise HTTPException(
            status_code=409,
            detail="Unlock the app first: the encryption key isn't loaded.",
        )
    #: KG4: a private note has no property index; a public one gets it back.
    manager.reindex_properties(session, entry)
    session.commit()
    if body.private:
        # SEC-03: the note's words out of the search index's segments and the
        # WAL too, not only out of the answers.
        manager_private.scrub_private_leftovers(session)
    session.refresh(entry)
    return _to_out(session, entry)


@router.post("/{entry_id}/generate-title", response_model=EntryOut)
def generate_entry_title(
    entry_id: int, session: Session = Depends(get_session)
) -> EntryOut:
    """Write a title for this note with AI, on request.

    Recognising a title the user already wrote (`manager.extract_title`) is
    free; writing one is a real model call, so this is its own opt-in
    action rather than something that runs on every save. Replaces an
    existing title rather than stacking a second heading on top of it.
    """
    entry = NOTES.writable(session, entry_id)
    # `readable_content` decrypts a private note for reading; writing that
    # decrypted text straight back to `entry.content` (below) would silently
    # replace the ciphertext with plaintext, the note would stop being
    # private as a side effect of titling it. Refused outright rather than
    # risked: unlike a plain edit, there's no form here the user reviewed
    # before it reached the server.
    if entry.is_private:
        raise HTTPException(
            status_code=400, detail="Make this note readable first: private notes can't be re-titled here."
        )
    content = manager_text.readable_content(entry)
    if not content.strip():
        raise HTTPException(status_code=400, detail="There's no text to title yet.")
    if not deps.get_ollama().is_running():
        return _composed_title(session, entry, content)
    try:
        title = librarian.generate_title(content, deps.get_model_manager(), deps.get_ollama())
    except OllamaError as exc:
        logger.warning("title generation failed", exc_info=True)
        raise HTTPException(status_code=502, detail=librarian.AI_FAILED_MESSAGE) from exc
    if not title:
        raise HTTPException(status_code=502, detail="The AI didn't return a usable title.")

    manager.record_revision(session, entry)
    entry.content = manager_text.apply_title(content, title)
    manager.mark_edited(entry)
    manager.log_action(session, "edited", "entry", entry.id, f"generated title: {title}")
    session.commit()
    session.refresh(entry)
    return _to_out(session, entry)


def _composed_title(session: Session, entry, content: str) -> EntryOut:  # noqa: ANN001
    """**A title with no model** (O7; INBOX 904 B33: "they arent ai actions
    if the composer does them"): the note's own words, its first sentence cut
    at seven words (`composer_voice.title_for`), never a word it does not
    hold. The client says it was taken, not written."""
    from tessellate.ai import composer_voice

    title = composer_voice.title_for(manager_text.remove_title(content) or content)
    if not title:
        raise HTTPException(status_code=422, detail="There's no sentence here to take a title from yet.")
    manager.record_revision(session, entry)
    entry.content = manager_text.apply_title(content, title)
    manager.mark_edited(entry)
    manager.log_action(session, "edited", "entry", entry.id, f"title from its own words: {title}")
    session.commit()
    session.refresh(entry)
    return _to_out(session, entry)


@router.post("/{entry_id}/remove-title", response_model=EntryOut)
def remove_entry_title(entry_id: int, session: Session = Depends(get_session)) -> EntryOut:
    """Take a note's title back out, asked for directly. Just the leading
    heading line; a note with no title is returned unchanged rather than
    treated as an error, since the client only offers this action when
    `entry.title` is already set and a stale menu shouldn't 400."""
    entry = NOTES.writable(session, entry_id)
    # Same reason as generate-title: writing decrypted text back to
    # `entry.content` would un-encrypt the note as a side effect.
    if entry.is_private:
        raise HTTPException(
            status_code=400, detail="Make this note readable first: private notes can't be edited here."
        )
    content = manager_text.readable_content(entry)
    stripped = manager_text.remove_title(content)
    if stripped != content:
        manager.record_revision(session, entry)
        entry.content = stripped
        manager.mark_edited(entry)
        manager.log_action(session, "edited", "entry", entry.id, "removed the title")
        session.commit()
        session.refresh(entry)
    return _to_out(session, entry)


def _connection_cue(session: Session, other: Entry) -> dict:
    """What tells two connected notes with the same title apart
    (tests/test_connection_row_cues.py): the category, and when it was
    written. The client shows one only when two titles collide. A private
    note keeps its category back with its text, because the category is what
    the filer read it as; the date says nothing about what it says."""
    created = getattr(other, "created_at", None)
    return {
        "category": None if other.is_private else manager.category_name_for(session, other),
        "created_at": created.isoformat() if created else None,
    }


def _stored_connections(session: Session, entry: Entry) -> tuple[list[dict], list[dict]]:
    """`(outgoing, incoming)` from the stored links, direction kept."""
    outgoing: list[dict] = []
    incoming: list[dict] = []
    for link, other in manager_links.links_for_entry(session, entry):
        if other.is_deleted:
            continue
        row = {
            "link_id": link.id,
            "id": other.id,
            # A private note's text never leaves the vault for a list like
            # this: the *fact* of the connection is not secret, its content
            # is. Same rule as the Library's own file-usage chips.
            "preview": (
                _connection_label(other)
            ),
            "is_private": bool(other.is_private),
            **_connection_cue(session, other),
            "reason": link.reason,
            "reason_confidence": link.reason_confidence,
            #: KG3: the kind, named from this end, and the link's properties.
            "link_type": link.link_type,
            "link_label": manager_links.relation_label(
                relation_types.kinds(session), link.link_type, link.source_entry_id == entry.id
            ),
            "props": link.props,
        }
        (outgoing if link.source_entry_id == entry.id else incoming).append(row)
    return outgoing, incoming


def _attached_documents(session: Session, entry: Entry) -> list[dict]:
    """The documents this note is attached to, by title."""
    return [
        {"id": doc.id, "title": doc.title, "file_type": doc.file_type}
        for doc in documents_repo.attached_to_entry(session, entry.id)
    ]


def _add_referenced(session: Session, references: list[dict], documents: list[dict], incoming: list[dict]) -> None:
    """Fold the text-only references into the documents and incoming rows."""
    #: **The same reader as the Referenced-by row and the card's chip**, so the
    #: three agree (INBOX 246). The chip says "in 1 document · linked by 1
    #: note" from `_reference_rows`, and this dialog is what it opens: a
    #: document that links to the note by `[[wiki link]]` without the note
    #: being attached to it, and a note that mentions this one without a
    #: stored `EntryLink`, both used to be counted on the chip and missing
    #: here. They are added to the group they belong in, after the rows the
    #: database holds exactly, skipping any the exact rows already carry.
    known_docs = {doc["id"] for doc in documents}
    for row in references:
        if row["kind"] == "document" and row["id"] not in known_docs:
            known_docs.add(row["id"])
            documents.append({"id": row["id"], "title": row["label"], "file_type": None, "how": row["how"]})
    known_notes = {row["id"] for row in incoming}
    for row in references:
        if row["kind"] == "note" and row["id"] not in known_notes:
            known_notes.add(row["id"])
            other = session.get(Entry, row["id"])
            if other is None:
                continue
            incoming.append({
                "link_id": None,
                "id": other.id,
                "preview": _connection_label(other),
                "is_private": bool(other.is_private),
                **_connection_cue(session, other),
                "reason": "Links to it" if row["how"] == "links to it" else "Mentions it",
                "reason_confidence": None,
            })


def _add_wiki_outgoing(session: Session, entry: Entry, outgoing: list[dict]) -> None:
    """Fold this note's own `[[wiki links]]` into the outgoing rows."""
    #: **And this note's own `[[wiki links]]`, outgoing.** The block above
    #: gives the *target* of a link its incoming row by reading the text of
    #: the note that wrote it; nothing gave the writer the matching outgoing
    #: row unless a stored `EntryLink` happened to exist, and one does not
    #: when the link was typed before its target was made, or names a note
    #: by its `# Heading` (the stored-link resolver matches the raw start of
    #: the text). Measured 2026-10-03: "[[Sourdough starter]]" showed
    #: `outgoing: []` and "Nothing is joined to this note yet" while the
    #: target listed the note as incoming. Read the same way both ends now.
    known_out = {row["id"]: row for row in outgoing}
    for other in _wiki_link_targets_of(session, entry):
        if other.id in known_out:
            #: Stored now that [[links]] resolve (INBOX 517); a link with no
            #: reason of its own still says why it exists.
            if not known_out[other.id]["reason"]:
                known_out[other.id]["reason"] = "Links to it"
            continue
        known_out[other.id] = None
        outgoing.append({
            "link_id": None,
            "id": other.id,
            "preview": _connection_label(other),
            "is_private": bool(other.is_private),
            **_connection_cue(session, other),
            "reason": "Links to it",
            "reason_confidence": None,
        })


def _boards_of(session: Session, entry: Entry, references: list[dict]) -> list[dict]:
    """The boards and maps this note sits on, and the scratch whiteboard when it does."""
    #: Boards and maps: `kind` is "board" or "map" so the dialog can say
    #: which (a map's own note node counts too). The unnamed scratch board
    #: (`board_id IS NULL`) is not an entry and so has no row there; it is a
    #: real board, the one every notebook starts with, and it is added here
    #: on its own.
    boards: list[dict] = [
        {"id": row["id"], "title": row["label"], "kind": row["kind"]}
        for row in references
        if row["kind"] in ("board", "map")
    ]
    on_scratch = session.scalars(
        select(WhiteboardNode.id)
        .where(WhiteboardNode.entry_id == entry.id, WhiteboardNode.board_id.is_(None))
        .limit(1)
    ).first()
    if on_scratch is not None:
        boards.append({"id": None, "title": "Whiteboard", "kind": "board"})
    return boards


def _wiki_link_targets_of(session: Session, entry: Entry) -> list[Entry]:
    """The notes this note's `[[names]]` point at, in the order written.

    `manager.find_by_wiki_name` first, the resolver a save uses to make
    stored links, so a name means here what it means on the graph. Where it
    finds nothing, the note whose plain label is exactly the name, which is
    the rule `_reference_rows` applies from the other end ("links to it"
    when the text holds `[[label]]`): without that second reading a note
    named by its heading was incoming on the target and absent here.
    """
    from tessellate.entry.manager_text import plain_label

    found: list[Entry] = []
    for name in manager_wiki.wiki_link_targets(manager_text.readable_content(entry)):
        target = manager_wiki.find_by_wiki_name(session, name)
        if target is None:
            wanted = name.strip().casefold()
            pattern = "%" + like_escape(name.strip()) + "%"
            for other in session.scalars(
                select(Entry)
                .where(
                    Entry.id != entry.id,
                    Entry.is_deleted.is_(False),
                    Entry.is_private.is_(False),
                    Entry.content.ilike(pattern, escape=LIKE_ESCAPE),
                )
                .order_by(Entry.id)
                .limit(REFERENCE_SOURCES_MAX)
            ):
                if plain_label(other.content, 60).strip().casefold() == wanted:
                    target = other
                    break
        if target is not None and target.id != entry.id and not target.is_deleted:
            found.append(target)
    return found


def _connection_label(entry, length: int = 80) -> str:  # noqa: ANN001
    """What one note is called on another note's Connections list, its link
    chips and the near-duplicate line: the one place a note is named from
    outside itself, so the private-note rule (`manager.PRIVATE_LABEL`) lives
    here and nowhere else.

    A note's own leading `# Heading` is what it calls itself, so that is the
    label when it wrote one, `_preview` alone hands back "# Connections probe
    B\noven temperatures", which renders on a single-line row as the hash, the
    title and the first line of the body run together.
    """
    if getattr(entry, "sealed_placeholder", False):
        return manager.PRIVATE_SPACE_NOTE
    if entry.is_private:
        return manager.PRIVATE_LABEL
    return manager_text.plain_label(manager_text.readable_content(entry), length)


def _connected_files(session: Session, text: str) -> list[dict]:
    """The uploads a body of markdown actually references, as cards.

    `referenced_names` is the same parse the media garbage collector uses to
    decide what is *not* an orphan, so a file listed here and a file the GC
    spares are guaranteed to be the same set, there is no second regex to
    drift out of step with it.
    """
    from tessellate.core.media_gc import referenced_names

    names = referenced_names(text)
    if not names:
        return []
    rows = session.scalars(select(MediaUpload).where(MediaUpload.filename.in_(names)))
    return [
        {
            "name": media.filename,
            "original_name": media.original_name,
            "url": f"/media/{media.filename}",
            "caption": media.caption or "",
        }
        for media in rows
    ]


# --- extract notes (BACKLOG.md §62) ------------------------------------------
# Select a block of writing, the Writing Room's draft, a Document's body, or
# several notes' content selected on the whiteboard, and turn it into one or
# several AI-drafted notes, auto-linked with real reasons. Preview first,
# matching `generate_diagram`'s own preview-before-commit convention (see
# `ai.extractor`'s module docstring): nothing is written here until
# `/extract/commit` is called with what the preview actually showed.


class ExtractPreviewBody(BaseModel):
    text: str = Field(min_length=1, max_length=extractor.EXTRACT_MAX_CHARS)
    # A Graph/whiteboard selection's notes-in-context: existing notes this
    # extraction should try to link every new note back to, regardless of
    # how similar the wording is, the user already said they're connected
    # by selecting them together.
    source_entry_ids: list[int] = Field(default_factory=list)


@router.post("/extract/preview")
def extract_preview(body: ExtractPreviewBody, session: Session = Depends(get_session)) -> dict:
    """Propose one or more notes from `body.text`, with the links they'd get
    and why: nothing saved yet. See `ai.extractor.build_extraction`."""
    try:
        return extractor.build_extraction(
            session,
            body.text,
            deps.get_embeddings(),
            deps.get_model_manager(),
            deps.get_ollama(),
            source_entry_ids=body.source_entry_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


class ExtractNoteIn(BaseModel):
    """One note from a preview, as the user reviewed it, possibly edited,
    possibly dropped (the caller just omits it) before commit."""

    ref: str = Field(min_length=1, max_length=40)
    title: str = Field(default="", max_length=200)
    content: str = Field(min_length=1, max_length=extractor.EXTRACT_MAX_CHARS)
    category: str = Field(default=manager.UNCATEGORISED, max_length=100)
    tags: list[str] = Field(default_factory=list)


class ExtractLinkIn(BaseModel):
    """One proposed link, as shown in the preview. `source_ref`/`target_ref`
    are either `nN` (one of this batch's own notes) or `existing:<id>` (a
    note already in the notebook)."""

    source_ref: str = Field(min_length=1, max_length=48)
    target_ref: str = Field(min_length=1, max_length=48)
    reason: str = Field(min_length=1, max_length=200)


class ExtractCommitBody(BaseModel):
    notes: list[ExtractNoteIn] = Field(min_length=1, max_length=extractor.MAX_EXTRACT_NOTES)
    links: list[ExtractLinkIn] = Field(default_factory=list)
    # When extracting from a Document's body, attach every note created here
    # to it: the same connection `POST /documents/{id}/notes` makes by hand.
    source_document_id: int | None = None


@router.post("/extract/commit", status_code=201)
def extract_commit(body: ExtractCommitBody, session: Session = Depends(get_session)) -> dict:
    """Write exactly what a preview showed (possibly edited, possibly
    trimmed) to the notebook: the notes, then the links between them, 
    `manager.create_link`'s own `reason=` bypasses the generic
    `AUTO_REASON_TEXT` guess entirely, so every link gets the specific
    reason the preview generated for it.
    """
    by_ref: dict[str, Entry] = {}
    created = []
    for note in body.notes:
        if note.ref in by_ref:
            raise HTTPException(status_code=400, detail=f"Each note needs its own reference, and '{note.ref}' is used by more than one.")
        entry = manager.create_entry(
            session,
            content=note.content,
            category_name=note.category or manager.UNCATEGORISED,
            tags=note.tags,
            # Reviewed (and possibly edited) by the person before it was
            # ever asked to save, the same confidence level a user-filed
            # category gets in `create_entry` above, not the AI's own guess
            # from the preview (which was about the SPLIT, not the filing).
            ai_confidence=100,
        )
        by_ref[note.ref] = entry
        deps.store_quietly(session, entry)
        created.append(entry)

    if body.source_document_id is not None:
        document = documents_repo.find(session, body.source_document_id)
        # A document deleted between preview and commit is skipped rather
        # than refused: the notes are the thing being saved, same reasoning
        # `create_entry`'s own `document_ids` handling already uses.
        if document is not None:
            for entry in created:
                manager.link_document(session, document.id, entry.id)

    links_created = 0
    for link in body.links:
        source = by_ref.get(link.source_ref)
        if source is None:
            continue  # a ref that isn't among the notes just created, ignore rather than fail the whole save
        if link.target_ref.startswith("existing:"):
            try:
                target_id = int(link.target_ref.removeprefix("existing:"))
            except ValueError:
                continue
            target = manager.get_entry(session, target_id)
            if target is None or target.is_deleted:
                continue  # deleted between preview and commit
        else:
            target = by_ref.get(link.target_ref)
            if target is None:
                continue
        if manager_links.create_link(session, source, target, reason=link.reason) is not None:
            links_created += 1

    return {
        "notes": _to_out_bulk(session, created),
        "links_created": links_created,
    }
