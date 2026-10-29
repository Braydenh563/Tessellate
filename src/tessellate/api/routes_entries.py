"""Capture, read, edit, soft-delete, restore, and link entries.

Handlers are plain `def` (not async) on purpose: FastAPI then runs them
in a threadpool, which keeps the server responsive while blocking AI
calls run (plan §4).
"""

from __future__ import annotations

import contextlib
import json
import logging
import threading
import re
from datetime import date, datetime, timedelta
from collections import OrderedDict
from types import SimpleNamespace

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tessellate.ai import backend_hint, extractor, filing_certainty, janitor, learning, lexical_filing, librarian, links, relations
from tessellate.ai import tensions as tensions_module
from tessellate.ai.ollama_client import OllamaError
from tessellate.api import paging
from tessellate.api.edit_conflicts import content_hash, entity_tag, refuse_if_stale, refuse_unless_match
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
from tessellate.core import deps, events, jobruns, jobs, vault
from tessellate.core.events import ACTOR_USER_AND_AI
from tessellate.core.database import (  # noqa: F401 (EntryLink used in link_suggestions)
    AuditLog,
    Bookmark,
    DerivedTension,
    Document,
    DocumentLink,
    EmbeddingRecord,
    Entry,
    EntryBookmark,
    Entity,
    EntityMention,
    EntryLink,
    EntryRevision,
    MediaUpload,
    WhiteboardNode,
    WhiteboardObject,
    like_escape,
    utcnow,
)
from tessellate.core.database import LIKE_ESCAPE
from tessellate.core.deps import get_session
from tessellate.entry import duplicates, link_facts, manager
from tessellate.entry.mentions import MENTION_MIN_TITLE_CHARS, names_label
from tessellate.entry import meetings as meeting_shape
from tessellate.entry import properties as note_properties
from tessellate.entry.tagnames import inline_tags, normalise_tags
from tessellate.search import engine as search_engine
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

    plain = manager.wiki_plain(strip_properties(text or "").lstrip())
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
    content = manager.readable_content(entry)
    resolved_dates = manager.entry_dates(session, entry) if dates is None else dates
    resolved_documents = (
        manager.documents_for_entry(session, entry) if documents is None else documents
    )
    resolved_links = manager.links_for_entry(session, entry) if links is None else links
    resolved_attachments = (
        manager.attachments_for(session, entry) if attachments is None else attachments
    )
    return EntryOut(
        id=entry.id,
        content=content,
        content_hash=content_hash(content),
        title=manager.extract_title(content),
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
        dates=[
            EntryDateOut(
                phrase=d.phrase,
                at=d.at.date(),
                precision=d.precision,
                time=d.at.strftime("%H:%M") if d.precision == "minute" else None,
            )
            for d in resolved_dates
        ],
        documents=[
            DocumentRefOut(id=doc.id, title=doc.title) for doc in resolved_documents
        ],
        links=[
            LinkOut(
                link_id=link.id,
                entry_id=other.id,
                preview=_preview(manager.readable_content(other)),
                reason=link.reason,
                reason_confidence=link.reason_confidence,
                # The one fact the merged list could never carry. See
                # `LinkOut.direction`.
                direction="out" if link.source_entry_id == entry.id else "in",
                link_type=link.link_type,
                link_label=manager.relation_label(
                    manager.relation_types(session), link.link_type, link.source_entry_id == entry.id
                ),
                props=link.props,
            )
            for link, other in resolved_links
        ],
        attachments=[
            AttachmentOut(
                id=a.id,
                filename=a.filename,
                size=a.size,
                is_image=a.mime.startswith("image/"),
                created_at=a.created_at.isoformat() if a.created_at else "",
            )
            for a in resolved_attachments
        ],
        filed_by=filed_by,
        filing_state=getattr(entry, "filing_state", "done") or "done",
        similar=similar,
    )


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


def _tag_reasons(content: str, tags: list[str]) -> dict[str, str]:
    """Each offered tag's one line for its chip (decision 5: each explained)."""
    if not tags or not content:
        return {}
    from tessellate.ai import tagging, taxonomy

    hits = taxonomy.topic_hits(tagging.clean(content))
    return {tag: why for tag in tags if (why := tagging.reason(tag, content, hits))}


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
    content = manager.readable_content(entry)
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
    attachments_by_id = manager.attachments_for_entries_bulk(session, ids)
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
        from tessellate.core.deps import impersonate_workspace

        try:
            with deps.get_db().session() as session:
                with impersonate_workspace(session, self.workspace_id):
                    entry = session.get(Entry, self.entry_id)
                    if entry is not None:
                        return filing_certainty.calibrated(
                            session, manager.readable_content(entry), category, raw, "llm",
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
        with self._lock:
            if self._stand_in is None:
                self._early = (category, confidence)
                return
            stand_in = self._stand_in
        self.apply(category, confidence, stand_in)

    def apply(self, category: str, confidence: int, stand_in: str) -> None:
        from tessellate.core.deps import impersonate_workspace

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
    from tessellate.core.deps import impersonate_workspace

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
                late = _LateFiling(entry_id, workspace_id, manager.readable_content(entry))
                category, confidence, filed_by = _file_entry_now(
                    session,
                    manager.readable_content(entry),
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
    from tessellate.core.deps import impersonate_workspace

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
                    content = manager.readable_content(entry)
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
    from tessellate.core.deps import impersonate_workspace

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


@router.post("", response_model=EntryOut, status_code=201)
def create_entry(body: EntryCreate, session: Session = Depends(get_session)) -> EntryOut:
    earlier = _already_delivered(session, body.client_key)
    if earlier is not None:
        return _to_out(session, earlier, filed_by=None, similar=None)
    parent = None
    if body.parent_id is not None:
        parent = _existing_entry(session, body.parent_id)

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
    if filed_by == "user":
        entry.user_filed = True
    if body.is_draft:
        entry.is_draft = True
    if body.map_topic:
        entry.map_topic = True
    if body.source_url:
        entry.source_url = body.source_url
        entry.source_title = body.source_title
    if defer:
        entry.filing_state = "pending"
    elif janitor.settled_state(filed_by) != "done":
        entry.filing_state = janitor.settled_state(filed_by)
    session.commit()
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
    # Settings → Logs instead of quietly shrinking search.
    #
    # Skipped when filing is deferred: the same background thread does it,
    # right before the near-duplicate search that depends on it.
    if not defer:
        deps.store_quietly(session, entry)

    # [[wiki links]] become real links. Best effort for the same reason: a
    # link that can't be resolved must never cost someone their note.
    try:
        manager.sync_wiki_links(session, entry)
        manager.resolve_links_to(session, entry)
        session.commit()
    except Exception:
        session.rollback()
        logger.warning("couldn't sync wiki links for entry %s", entry.id, exc_info=True)

    # Documents this note belongs with, attached as it is saved. A document
    # that has since been deleted is skipped rather than refused: the note is
    # the thing being saved, and losing it over a stale id would be absurd.
    for document_id in dict.fromkeys(body.document_ids):
        if session.get(Document, document_id) is not None:
            manager.link_document(session, document_id, entry.id)

    # A note is one of the three "committed" moments core/media_process.py
    # waits for (asked for directly: OCR/captioning/vision-OCR must not run
    # on a staged upload that never made it into a saved note). `body.content`
    # here, never `entry.content`, is deliberate: a private note's stored
    # content may already be encrypted at rest, and this is the plaintext
    # that was actually just submitted, before that happens.
    _process_committed_media(session, body.content)

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
    last = _daily_date(through) if through else date.today()
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
            manager.readable_content(entry),
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
    entry = _existing_entry(session, entry_id)
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
    from tessellate.core.deps import impersonate_workspace

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
    similar = None
    duplicate_id = getattr(entry, "filing_similar_id", None)
    if duplicate_id is not None:
        other = session.get(Entry, duplicate_id)
        if other is not None:
            similar = {
                "id": other.id,
                "preview": _preview(manager.readable_content(other)),
            }
    state = getattr(entry, "filing_state", "done") or "done"
    category = manager.category_name_for(session, entry)
    filed_by = _filed_by(entry, state)
    #: Nothing was sure enough to file it: up to three categories to offer as
    #: one-tap choices (INBOX 434), the ones its words lean to first.
    suggestions: list[str] = []
    #: Each choice's one line, the filed category's, and a new category the
    #: pack proposes (WORLD_CLASS 23, decisions 2, 3 and 6).
    reasons: dict[str, str] = {}
    why = ""
    proposal = None
    held = None
    shown = filing_certainty.shown(
        entry.ai_confidence, user_filed=bool(getattr(entry, "user_filed", False))
    )
    #: A pick the calibration put under the review line (`filing_certainty`)
    #: is offered the same way: the alternatives beside the one it chose.
    unsure_pick = filed_by == "ai" and 0 < shown < manager.REVIEW_CONFIDENCE
    if (filed_by == "none" and category == manager.UNCATEGORISED) or unsure_pick:
        from tessellate.ai import lexical_filing

        try:
            content = manager.readable_content(entry) or ""
            explained = [
                (name, reason)
                for name, reason in lexical_filing.suggest_categories_explained(
                    session, content, exclude_entry_id=entry.id, limit=4,
                )
                if name != category
            ][:3]
            suggestions = [name for name, _ in explained]
            reasons = {name: reason for name, reason in explained if reason}
            decision = lexical_filing.decide(session, content, exclude_entry_id=entry.id)
            if decision.proposal is not None:
                proposal = {"name": decision.proposal.name, "why": decision.proposal.why}
            if decision.held and decision.ranked:
                held = {"category": decision.ranked[0].name, "topic": decision.sensitive}
        except Exception:  # noqa: BLE001 - a hint never fails the status
            logger.debug("no category suggestions for entry %s", entry.id, exc_info=True)
    elif filed_by == "words" and category != manager.UNCATEGORISED:
        from tessellate.ai import lexical_filing

        try:
            decision = lexical_filing.decide(
                session, manager.readable_content(entry) or "", exclude_entry_id=entry.id
            )
            why = next((c.why for c in decision.ranked if c.name == category), "")
        except Exception:  # noqa: BLE001 - a hint never fails the status
            logger.debug("no filing reason for entry %s", entry.id, exc_info=True)
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
    apart. `manager.all_tags` is cached by notebook fingerprint, so this is
    a dictionary lookup rather than a scan on the common path.
    """
    counts = manager.all_tags(session)
    return [tag for tag, _count in sorted(counts.items(), key=lambda row: (-row[1], row[0]))]


class SuggestTagsBody(BaseModel):
    content: str
    tags: list[str] = Field(default_factory=list)
    #: Capture's title field: a note's title says what it is, so it counts
    #: with its first line (`ai/tagging.lead`).
    title: str = Field(default="", max_length=300)

#: Said once per process, not once per keystroke pause.
_SAID_ONCE: set[str] = set()


@router.post("/suggest-category")
def suggest_category_for_draft(body: SuggestTagsBody, session: Session = Depends(get_session)) -> dict:
    """The category the notebook's own words point to for a note that is not
    saved yet, with the reason (INBOX 1330: "a live, inline organization
    suggestion while typing"). The words only, no model and no write: the
    same decision filing makes with no model, so what is offered here is what
    saving would have done. Nothing comes back where it has no reason to give
    (a recently used category is a filing fallback, not a suggestion), and a
    sensitive topic is offered like any other: it is a chip to press, and
    pressing is the person filing it (decision 6)."""
    from tessellate.ai import lexical_filing

    content = body.content.strip()
    if body.title.strip() and content:
        content = f"# {body.title.strip()}\n\n{content}"
    if not content:
        return {"category": None, "reason": ""}
    try:
        decision = lexical_filing.decide(session, content)
    except Exception:  # noqa: BLE001 - a hint never fails the form
        logger.debug("no category suggestion for a draft", exc_info=True)
        return {"category": None, "reason": ""}
    pick = decision.filed or next((c for c in decision.ranked if c.score > 0 and c.why), None)
    if pick is None or not pick.why:
        return {"category": None, "reason": ""}
    return {"category": pick.name, "reason": pick.why}


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
    entry = _existing_entry(session, entry_id)
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
    entry = _existing_entry(session, entry_id)
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


def _linked_entry_ids(session: Session, entry) -> set[int]:  # noqa: ANN001
    """Ids this note is already connected to, explicit links plus its
    thread parent/children: so re-evaluate never re-suggests them."""
    linked = {other.id for _link, other in manager.links_for_entry(session, entry)}
    if entry.parent_id is not None:
        linked.add(entry.parent_id)
    # Was `for child in manager.list_entries(session)`, loading and
    # ORM-hydrating every non-deleted note in the notebook (decrypting private
    # ones) just to find the handful whose parent_id matches. This entry has
    # at most a few children; the notebook can have thousands of notes.
    child_ids = session.scalars(
        select(Entry.id).where(Entry.parent_id == entry.id, Entry.is_deleted == False)  # noqa: E712
    )
    linked.update(child_ids)
    return linked


@router.post("/{entry_id}/reevaluate")
def reevaluate_entry(entry_id: int, session: Session = Depends(get_session)) -> dict:
    """Re-run the AI on one note (Wave: re-evaluate). Refreshes its
    confidence, and its category, unless the user filed it themselves , 
    and suggests tags and links for the user to apply. Tags and links are
    suggestion-only: nothing is tagged or linked without the user's click."""
    entry = _existing_entry(session, entry_id)
    # Every step below sends the note's text to the model or the search index:
    # ciphertext while the vault is locked, the plain text of a note that is
    # private so that no model reads it once it is open (sweep 1004). Refused
    # outright, like generate-title; the menu's toast shows the sentence.
    if entry.is_private:
        raise HTTPException(
            status_code=400, detail="Make this note readable first: Atlas doesn't read private notes."
        )

    # 1. Re-file: refresh confidence, and the category if the AI owns it.
    filed_by = None
    recategorised_to = None
    # The last "filing" run (INBOX 438). This step swallows its own errors so a
    # down model never fails the re-evaluation, which is exactly why the record
    # has to be told about them: `refiling` is how the screen hears.
    refiling = jobruns.begin("filing")
    try:
        category, confidence, filed_by = janitor.categorise(
            session,
            entry.content,
            deps.get_embeddings(),
            deps.get_model_manager(),
            deps.get_ollama(),
            exclude_entry_id=entry.id,  # don't let the note anchor to itself
        )
        if filed_by != "none":
            entry.ai_confidence = confidence
            if not entry.user_filed:
                if manager.record_filing(
                    session, entry, category,
                    by=janitor.filed_by_label(
                        filed_by, confidence, deps.get_model_manager(), deps.get_embeddings()
                    ),
                ):
                    recategorised_to = category
                # As on adding context: the AI owns this category now, so a
                # move by hand is a correction the filing loop should read.
                if janitor.settled_state(filed_by) != "done":
                    entry.filing_state = janitor.settled_state(filed_by)
            session.commit()
            refiling.result = (
                f"note {entry.id} moved to {recategorised_to}"
                if recategorised_to
                else f"note {entry.id} re-read, category kept"
            )
        else:
            refiling.fail("No filing model or embeddings were available.")
    except Exception as exc:
        #: One line: a model that is off (connection refused) is a state, not a bug.
        logger.warning(
            "re-evaluation's filing step failed: %s", exc,
            exc_info=not isinstance(exc, (OllamaError, ConnectionError)),
        )
        filed_by = None  # AI down, keep the note exactly as it was
        refiling.fail("The filing step stopped before it finished. The log has the reason.")
    finally:
        #: Every way out, a cancel included: nothing stays "running" (B77).
        refiling.finish()

    # 2. Suggest tags (best effort: never blocks the re-evaluation).
    suggested_tags = _reevaluate_tags(session, entry)

    # 3. Suggest links: semantic neighbours that aren't connected yet.
    suggested_links: list[dict] = []
    try:
        already = _linked_entry_ids(session, entry)
        results = search_manager.semantic_search(
            session, entry.content, deps.get_embeddings(), limit=6
        )
        for other, score in results or []:
            if other.id == entry.id or other.id in already or score < 0.4:
                continue
            suggested_links.append(
                {"id": other.id, "preview": _preview(other.content), "similarity": round(score, 2)}
            )
            if len(suggested_links) >= 4:
                break
    except Exception:
        logger.warning("re-evaluation's link step failed", exc_info=True)
        suggested_links = []

    return {
        "entry": _to_out(session, entry, filed_by=filed_by).model_dump(),
        "recategorised_to": recategorised_to,
        "suggested_categories": _other_categories(session, entry),
        "suggested_tags": suggested_tags,
        "suggested_tag_reasons": {} if getattr(entry, "is_private", False) else _tag_reasons(entry.content or "", suggested_tags),
        "suggested_links": suggested_links,
    }


def _other_categories(session: Session, entry) -> list[dict]:  # noqa: ANN001
    """The other places the note could go, with why (owner, 2026-10-17: Tag with
    Atlas "didn't suggest alternate categories to make or move to"). Not from a
    private note's text, like the tags."""
    if getattr(entry, "is_private", False):
        return []
    try:
        from tessellate.ai import lexical_filing

        here = manager.category_name_for(session, entry)
        found = lexical_filing.suggest_categories_explained(
            session, manager.readable_content(entry) or "", exclude_entry_id=entry.id, limit=4,
        )
        return [{"name": name, "why": why} for name, why in found if name not in (here, manager.UNCATEGORISED)][:3]
    except Exception:
        logger.info("re-evaluation's category step failed", exc_info=True)
        return []


def _reevaluate_tags(session: Session, entry) -> list[str]:  # noqa: ANN001
    """The model's tags when one answers, then the notebook's own: with no
    model, Tag and file with Atlas offered no tag at all (INBOX 781). Not
    from a private note's text: nothing derives a suggestion from it
    (`_keep_suggestions`)."""
    have = manager.entry_tags(entry)
    model: list[str] = []
    try:
        model = librarian.suggest_tags(
            entry.content, have, deps.get_model_manager(), deps.get_ollama(), vocabulary=_tag_vocabulary(session),
        )
    except Exception as exc:
        logger.info(
            "re-evaluation's model tag step failed; using the notebook's own: %s", exc,
            exc_info=not isinstance(exc, (OllamaError, ConnectionError)),
        )
    if getattr(entry, "is_private", False):
        return model
    try:
        return _engine_tags(session, entry.content or "", have, model, entry.id)
    except Exception:
        logger.warning("re-evaluation's tag step failed", exc_info=True)
        return []


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


# Notes this similar are almost certainly worth connecting.
LINK_SUGGESTION_THRESHOLD = 0.55

#: How many of the twelve suggestions any one note may anchor. See
#: `link_suggestions` for the measurement that put this here: without a cap,
#: one note paired with six copies of itself filled half the list.
MAX_SUGGESTIONS_PER_NOTE = 2

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
        content = manager.readable_content(entry)
        found = {} if entry.is_private else note_properties.split(content)[0]
        for key in found:
            counts[key] = counts.get(key, 0) + 1
        rows.append({
            "id": entry_id,
            "title": manager.extract_title(content) or manager.plain_label(content, 60) or "Untitled note",
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


class _LazyNoteFacts:
    """`relations.NoteFacts` whose label is read only when asked for.

    `recognise` names a note only when it is a hub of shared neighbours, yet
    every note's label was cleaned up front: at 5,000 notes 0.66 s of a
    1.08 s warm `/entries/link-suggestions` (audit 2026-10-05, ARCH-11).
    """

    __slots__ = ("_content", "_label", "tags", "created_at")

    def __init__(self, content: str, tags: frozenset[str], created_at) -> None:  # noqa: ANN001
        self._content = content
        self._label: str | None = None
        self.tags = tags
        self.created_at = created_at

    @property
    def label(self) -> str:
        if self._label is None:
            self._label = manager.plain_label(self._content, 40) or "Untitled note"
        return self._label


@router.get("/link-suggestions")
def link_suggestions(session: Session = Depends(get_session)) -> list[dict]:
    """Pairs of notes that mean similar things but aren't linked yet: 
    the auto-linker. Suggestion-only: it never links anything on
    its own, it hands the pairs to the UI to approve. Empty when the
    embedding backend is unavailable (semantic search off).

    Used to call `semantic_search` once *per entry*: a full embedding scan,
    for every entry, so O(entries) database round-trips each doing O(entries)
    work, and each one **re-embedding that entry's own content from scratch**
    on top of the scan. At any real notebook size that's the O(n^2) trap this
    file was checked for after §38.1's scale-test found two others: found by
    the same kind of sweep, not by profiling this one specifically, since a
    75k-note notebook running this by hand was not something worth actually
    waiting out. Rewritten to match `routes_graph._similarity_edges`'s
    already-correct shape: fetch every stored vector once, compare all
    pairs in memory: which turns O(n) queries plus O(n) re-embeddings into
    one query and zero re-embedding calls."""
    entries = manager.list_entries(session)
    entries_by_id = {e.id: e for e in entries if not e.is_private}
    already_linked: set[frozenset[int]] = set()
    for link in session.scalars(select(EntryLink)):
        already_linked.add(frozenset((link.source_entry_id, link.target_entry_id)))
    # Threads are already a connection, don't re-suggest parent/child.
    for entry in entries:
        if entry.parent_id is not None:
            already_linked.add(frozenset((entry.parent_id, entry.id)))
    # A pair the person has already said no to (WORLD_CLASS_PLAN I7). The same
    # set as the two above, because "you dismissed this" and "these are
    # already linked" are the same answer to this endpoint's only question:
    # is there anything left to suggest about these two. A suggestion that
    # comes back after being dismissed is the single most annoying thing a
    # suggester can do, and it is what this feature did until now: the
    # dismissal lived in the browser and died with the tab.
    for pair in learning.boosts(session, kind="links"):
        already_linked.add(frozenset(pair))

    # **Structure as well as wording** (GRAPH_PLAN KG2): shared entities,
    # shared link neighbours, shared rare tags and time join the cosine pairs
    # in `ai/relations.recognise`, each with its own reason and confidence, so
    # the list explains itself and is not empty with the embedding backend
    # off. The cosine pairs come from the engine's matrix (Brief 11), cached
    # per version of it (WORLD_CLASS_PLAN row 9); the filters below are per
    # request because what is linked or dismissed moves without any vector
    # changing.
    candidates = {i: e for i, e in entries_by_id.items() if not e.is_board}
    similar: list[tuple[int, int, float]] = []
    if deps.get_embeddings().is_ready():
        similar = search_engine.cached_similar_pairs(
            session, LINK_SUGGESTION_THRESHOLD, only=set(candidates)
        )
    edges = [(a, b) for a, b in session.execute(select(EntryLink.source_entry_id, EntryLink.target_entry_id))]
    edges += [(e.parent_id, e.id) for e in entries if e.parent_id is not None]
    mentions = [
        (name, entry_id)
        for name, entry_id in session.execute(
            select(Entity.name, EntityMention.entry_id).join(Entity, Entity.id == EntityMention.entity_id)
        )
    ]
    notes = {
        i: _LazyNoteFacts(e.content, frozenset(t.lower() for t in manager.entry_tags(e)), e.created_at)
        for i, e in candidates.items()
    }
    found = relations.recognise(
        notes, edges, mentions, similar, already_linked, weights=learning.signal_weights(session)
    )

    # **Two filters stand between "best-first" and "useful"**, both added
    # after measuring a real 116-note notebook whose twelve suggestions were
    # all a note paired with copies of itself (tests/test_link_suggestion_quality.py):
    #  1. A near-identical pair is a *duplicate* (`entry/duplicates.py`, same
    #     word-overlap score), not a connection.
    #  2. One note anchors at most `MAX_SUGGESTIONS_PER_NOTE` of the twelve, so
    #     the list is a survey of the notebook and not of its best-linked note.
    suggestions = []
    appearances: dict[int, int] = {}
    for candidate in found:
        a, b = candidate.a, candidate.b
        if (
            appearances.get(a, 0) >= MAX_SUGGESTIONS_PER_NOTE
            or appearances.get(b, 0) >= MAX_SUGGESTIONS_PER_NOTE
        ):
            continue
        if (
            duplicates.similarity(candidates[a].content, candidates[b].content)
            >= duplicates.DEFAULT_THRESHOLD
        ):
            continue
        appearances[a] = appearances.get(a, 0) + 1
        appearances[b] = appearances.get(b, 0) + 1
        signals = candidate.signals()
        reason = "; ".join(s["reason"] for s in signals if s["signal"] != "time")
        #: Meaning alone previews what linking would write, and linking now
        #: names what the two notes share when they share something (INBOX
        #: 691, `entry/link_wording.py`), so the preview does too.
        if [s["signal"] for s in signals if s["signal"] != "time"] == ["similarity"]:
            reason = link_facts.reason_for(session, a, b) or reason
        suggestions.append({
            "source_id": a,
            "target_id": b,
            "source_preview": _preview(candidates[a].content),
            "target_preview": _preview(candidates[b].content),
            "similarity": round(candidate.similarity, 2) if candidate.similarity is not None else None,
            "confidence": round(candidate.confidence, 2),
            "signals": signals,
            # Similarity alone previews what `create_link` deduces at the same
            # bar (`manager.AUTO_REASON_THRESHOLD`): the specific reason, else
            # "similar in meaning". Otherwise every signal, strongest first,
            # less the time, which supports a pair but is no reason to link.
            "reason": reason,
        })
        if len(suggestions) == 12:
            break
    return suggestions


#: Where dismissed tensions are remembered. A preference key rather than a new
#: table: this is a small list of pair keys, it belongs to the person rather
#: than to either note, and adding a migration for "I looked at this and it
#: was not a contradiction" would be a heavy answer to a light question.
TENSION_DISMISSED_KEY = "tensions_dismissed"

#: Tensions look at pairs the notebook already believes are about the same
#: thing (see `ai/tensions.py`, contradiction is only possible between notes
#: sharing a subject). A lower bar than `LINK_SUGGESTION_THRESHOLD` on
#: purpose: two notes that *disagree* often share less vocabulary than two
#: that agree, because the disagreement is exactly where their words differ.
TENSION_CANDIDATE_THRESHOLD = 0.45


def _tension_key(a: int, b: int) -> str:
    """A stable id for a pair, order-independent."""
    low, high = sorted((a, b))
    return f"{low}:{high}"


def _dismissed_tensions() -> set[str]:
    stored = deps.get_config().get_preference(TENSION_DISMISSED_KEY, []) or []
    return {str(key) for key in stored}


@router.get("/tensions")
def find_tensions(
    limit: int = Query(default=8, ge=1, le=20),
    session: Session = Depends(get_session),
) -> dict:
    """Places the notebook appears to disagree with itself.

    The feature `core/database.py`'s `LINK_TYPES` comment says the typed-link
    vocabulary was built for and that nothing ever produced, see
    `ai/tensions.py` for the full reasoning. Read-only and suggestion-only:
    finding a tension writes nothing, and `POST /entries/tensions/accept` is
    the only thing that creates the `contradicts` link.

    Returns `{"tensions": [...], "status": "..."}` rather than a bare list so
    an empty result can say *why* it is empty, "no model running" and "your
    notebook does not contradict itself" are completely different answers and
    a bare `[]` renders them identically, which is how a feature that never
    ran gets reported as a feature that found nothing.
    """

    ollama = deps.get_ollama()
    if not backend_hint.running(ollama):
        return {"tensions": [], "status": "no_model"}

    embeddings = deps.get_embeddings()
    if not embeddings.is_ready():
        return {"tensions": [], "status": "no_embeddings"}

    entries = manager.list_entries(session)
    by_id = {e.id: e for e in entries if not e.is_private and not e.is_board}
    if len(by_id) < 2:
        return {"tensions": [], "status": "too_few_notes"}

    # Cached per version of the matrix, as link suggestions are (row 9).
    pairs = search_engine.cached_similar_pairs(
        session, TENSION_CANDIDATE_THRESHOLD, only=set(by_id)
    )

    # A pair already marked as contradicting is a finding the person has
    # already accepted, not one to re-propose. Every other link type is left
    # alone deliberately: notes can be linked as "related" *and* disagree,
    # and that is one of the more interesting cases.
    known: set[str] = set(_dismissed_tensions())
    for link in session.scalars(select(EntryLink).where(EntryLink.link_type == "contradicts")):
        known.add(_tension_key(link.source_entry_id, link.target_entry_id))
    # WORLD_CLASS_PLAN B4: a pair already in the tensions table (found by an
    # earlier scan or the night shift, whatever became of it) is never asked
    # about again; the widget and `GET /entries/tensions/known` list it.
    tensions_module.refresh(session)
    known.update(session.scalars(select(DerivedTension.pair)))

    models = deps.get_model_manager()
    found: list[dict] = []
    checked = 0
    for a_id, b_id, score in pairs:
        if checked >= tensions_module.MAX_PAIRS_PER_PASS or len(found) >= limit:
            break
        if _tension_key(a_id, b_id) in known:
            continue
        ordered = tensions_module.order_by_time(by_id[a_id], by_id[b_id])
        if ordered is None:
            continue  # same few days, or undated, see MIN_GAP_DAYS
        checked += 1
        tension = tensions_module.compare_pair(ordered[0], ordered[1], models, ollama)
        if tension is None:
            continue
        #: Kept as an event, so the finding outlives this response and the
        #: table can be rebuilt from it (B4).
        tensions_module.record_event(
            session,
            tensions_module.FOUND,
            tension.earlier_id,
            tension.later_id,
            reason=tension.explanation,
            model=str(models.utility_model() or "local"),
            confidence=0.7,
        )
        found.append(
            {
                "key": _tension_key(tension.earlier_id, tension.later_id),
                "earlier_id": tension.earlier_id,
                "later_id": tension.later_id,
                "explanation": tension.explanation,
                "earlier_excerpt": tension.earlier_excerpt,
                "later_excerpt": tension.later_excerpt,
                "earlier_at": tension.earlier_at,
                "later_at": tension.later_at,
                "gap_days": tension.gap_days,
                "similarity": round(score, 2),
            }
        )
    status = "ok" if found else ("none_found" if checked else "no_candidates")
    session.commit()
    return {"tensions": found, "status": status, "pairs_checked": checked}


@router.get("/tensions/known")
def known_tensions(
    status: str = Query(default="open", pattern="^(open|accepted|dismissed|all)$"),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict:
    """The tensions the notebook already knows (WORLD_CLASS_PLAN B4): the
    derived table, rebuilt from its sources when one moved, in the shape the
    scan returns plus who decided each and when. Reads nothing with a model,
    so the Tensions widget can show it on every Dashboard draw."""
    rows, counts = tensions_module.listing(session, status=None if status == "all" else status, limit=limit)
    session.commit()
    notes = {
        e.id: e
        for e in session.scalars(
            select(Entry).where(Entry.id.in_({r.earlier_id for r in rows} | {r.later_id for r in rows}))
        )
    }
    out = []
    for row in rows:
        earlier, later = notes.get(row.earlier_id), notes.get(row.later_id)
        if earlier is None or later is None:
            continue
        out.append(
            {
                "key": row.pair,
                "earlier_id": row.earlier_id,
                "later_id": row.later_id,
                "explanation": row.reason,
                "earlier_excerpt": tensions_module._excerpt(manager.readable_content(earlier))[:280],
                "later_excerpt": tensions_module._excerpt(manager.readable_content(later))[:280],
                "earlier_title": manager.extract_title(manager.readable_content(earlier))
                or manager.plain_label(manager.readable_content(earlier), 60),
                "later_title": manager.extract_title(manager.readable_content(later))
                or manager.plain_label(manager.readable_content(later), 60),
                "earlier_at": tensions_module._stamp(earlier.created_at),
                "later_at": tensions_module._stamp(later.created_at),
                "gap_days": abs((later.created_at - earlier.created_at).days)
                if earlier.created_at and later.created_at
                else 0,
                "status": row.status,
                "model": row.model,
                "confidence": row.confidence,
                "computed_at": row.computed_at.isoformat() if row.computed_at else None,
                "source": row.source,
                "event_id": row.event_id,
            }
        )
    return {"tensions": out, "counts": counts}


class TensionPair(BaseModel):
    earlier_id: int
    later_id: int


@router.post("/tensions/accept")
def accept_tension(body: TensionPair, session: Session = Depends(get_session)) -> dict:
    """Record a tension as a real `contradicts` link between the two notes.

    Uses `manager.create_link` rather than inserting a row, so the link gets
    the same audit entry, the same self-link and duplicate guards, and the
    same graph/traversal treatment as one made by hand.
    """
    earlier = _existing_entry(session, body.earlier_id)
    later = _existing_entry(session, body.later_id)
    link = manager.create_link(
        session,
        earlier,
        later,
        reason="these disagree with each other",
        link_type="contradicts",
    )
    #: KG9: the inbox's decisions are corrections like every other kind.
    learning.record(session, kind="accept_tension", subject={"a": earlier.id, "b": later.id})
    tensions_module.record_event(session, tensions_module.ACCEPTED, earlier.id, later.id)
    session.commit()
    return {"created": link is not None}


@router.post("/tensions/dismiss")
def dismiss_tension(body: TensionPair, session: Session = Depends(get_session)) -> dict:
    """Stop offering this pair. Remembered across restarts.

    Capped, and oldest-first: without a cap this preference would grow
    without bound on a notebook where most candidates are rejected, and it
    is written to disk on every change (see `Config.set_preference`).
    """
    config = deps.get_config()
    stored = list(config.get_preference(TENSION_DISMISSED_KEY, []) or [])
    key = _tension_key(body.earlier_id, body.later_id)
    if key not in stored:
        stored.append(key)
    del stored[:-500]
    config.set_preference(TENSION_DISMISSED_KEY, stored)
    learning.record(session, kind="dismiss_tension", subject={"a": body.earlier_id, "b": body.later_id})
    tensions_module.record_event(session, tensions_module.DISMISSED, body.earlier_id, body.later_id)
    session.commit()
    return {"dismissed": key}


class TensionReopen(TensionPair):
    #: The accept made the `contradicts` link (it was not there before), so
    #: Undo takes it away; a link the person already had is left alone.
    remove_link: bool = False


@router.post("/tensions/reopen")
def reopen_tension(body: TensionReopen, session: Session = Depends(get_session)) -> dict:
    """Undo of accepting or dismissing a tension: the pair is offered again (INBOX 898).

    The event log is a history, so this writes a `tension_reopened` event
    rather than editing the earlier one, and drops the correction the
    decision taught the learning loop (it was a slip, not a lesson).
    """
    pair = {body.earlier_id, body.later_id}
    config = deps.get_config()
    stored = [k for k in (config.get_preference(TENSION_DISMISSED_KEY, []) or []) if k != _tension_key(body.earlier_id, body.later_id)]
    config.set_preference(TENSION_DISMISSED_KEY, stored)
    removed_link = False
    if body.remove_link:
        for link in session.scalars(select(EntryLink).where(EntryLink.link_type == "contradicts")).all():
            if {link.source_entry_id, link.target_entry_id} == pair:
                manager.delete_link(session, link)
                removed_link = True
    for kind in ("accept_tension", "dismiss_tension"):
        for item in reversed(learning.corrections(session, kind=kind)):
            if {item.subject.get("a"), item.subject.get("b")} == pair:
                row = session.get(AuditLog, item.id)
                if row is not None:
                    session.delete(row)
                break
    tensions_module.record_event(session, tensions_module.REOPENED, body.earlier_id, body.later_id)
    session.commit()
    return {"reopened": _tension_key(body.earlier_id, body.later_id), "removed_link": removed_link}


class LinkSuggestionReasonPair(BaseModel):
    source_id: int
    target_id: int


class LinkSuggestionReasonsBody(BaseModel):
    pairs: list[LinkSuggestionReasonPair]


@router.post("/link-suggestions/reasons")
def link_suggestion_reasons(
    body: LinkSuggestionReasonsBody, session: Session = Depends(get_session)
) -> dict:
    """Reasons for *pending* suggestions, not yet real links, the gap
    `/links/backfill-reasons` (below) deliberately doesn't cover, since that
    one only ever touches links that already exist. Asked for directly: the
    suggestions panel's own "Why?" boxes had no way to get an AI guess
    without linking first, editing, and re-linking. Best-effort per pair: 
    one bad or private pair doesn't sink the rest, and the whole call
    degrades to an empty list rather than an error the moment the model is
    down, so the caller can tell "nothing generated" from "everything
    genuinely had one already" without a special-cased response shape."""
    reasons = []
    ai_unavailable = False
    for pair in body.pairs[:12]:  # same cap link_suggestions() itself uses
        source = session.get(Entry, pair.source_id)
        target = session.get(Entry, pair.target_id)
        if not source or not target or source.is_private or target.is_private:
            continue
        try:
            reason = librarian.generate_link_reason(
                manager.readable_content(source),
                manager.readable_content(target),
                deps.get_model_manager(),
                deps.get_ollama(),
            )
        except Exception as exc:  # noqa: BLE001  # model offline is the expected case, once per pair; the message is logged
            logger.info("link suggestion reason skipped: %s", exc)
            ai_unavailable = True
            continue
        reasons.append(
            {"source_id": pair.source_id, "target_id": pair.target_id, "reason": reason}
        )
    result = {"reasons": reasons}
    if ai_unavailable:
        result["ai_unavailable"] = True
    return result


class BackfillReasonsBody(BaseModel):
    """`ai=False` runs only the cheap embedding pass, useful when the model
    is known to be down and you just want the links marked."""

    ai: bool = True
    limit: int = Field(default=100, ge=1, le=500)


@router.post("/links/backfill-reasons")
def backfill_link_reasons(
    body: BackfillReasonsBody | None = None, session: Session = Depends(get_session)
) -> dict:
    """"None of my notes have a linked reason yet, is there an easy way to
    give them all a reason?" There wasn't: `_deduce_reason` only ever ran at
    the moment a link was *made*, so every link from before that shipped, or
    made while the embedding backend was off, stays mute forever with
    nothing to revisit it. One pass over every reason-less link, same rule
    as a fresh one, a link that still can't be deduced is left alone rather
    than given a manufactured answer.

    **Two passes, not one, and the second is the one the user actually
    wanted.** The first (embeddings) can only ever write the literal string
    "similar in meaning", it compares two vectors and has no words for what
    it found. So a notebook that ran this ended up with every link reading
    *"similar in meaning"*, which is what was reported: the button appeared to
    work and the reasons it produced said nothing.

    The second pass hands those to the model and asks it to name the actual
    connection. It is best-effort: if the model is down, the embedding pass
    has still marked the links and the audit can be re-run later, which is
    why a failure here is reported in the result rather than raised.
    """
    options = body or BackfillReasonsBody()
    with jobruns.job_run("link-reasons", origin="you") as run:
        result = _backfill_reasons(session, options)
        run.result = (
            f"checked {result.get('checked', 0)} links, "
            f"added {result.get('updated', 0)} reasons, "
            f"reworded {result['rewritten']}"
        )
        if result.get("ai_unavailable"):
            run.result += " (the model was not available)"
    return result


def _backfill_reasons(session: Session, options: "BackfillReasonsBody") -> dict:
    result = manager.backfill_link_reasons(session)

    result["rewritten"] = 0
    if not options.ai:
        return result
    try:
        result["rewritten"] = links.audit_vague_links(
            session, deps.get_model_manager(), deps.get_ollama(), limit=options.limit
        )
    except Exception as exc:  # noqa: BLE001  # model offline is the expected case; the message is logged
        # Not an error the caller should see as a failure: the cheap pass
        # succeeded and its work is committed.
        logger.info("link reason audit skipped: %s", exc)
        result["ai_unavailable"] = True
    return result


#: How alike two notes have to be before one is offered as "see also".
#: Unchanged from the number this route already used inline; named now that
#: the scoring moved into the engine, so the threshold and the engine's own
#: `MIN_SIMILARITY` are visibly two different decisions rather than one
#: number copied twice.
RELATED_MIN_SIMILARITY = 0.3


@router.get("/{entry_id}/related", response_model=list[EntryOut])
def related_entries(entry_id: int, session: Session = Depends(get_session)) -> list[EntryOut]:
    """Semantic neighbours of one entry ("see also")."""
    entry = _existing_entry(session, entry_id)
    # The engine's matrix rather than a scan of every stored vector per note
    # opened (Brief 11). `warm_vectors` is idempotent: it builds once per
    # process and per notebook, and returns immediately after that, so this
    # is not per-request work. `related()` itself never builds, which is what
    # the spec pins.
    try:
        search_engine.warm_vectors(session)
        neighbours = search_engine.related(session, entry.id, k=8)
    except Exception:  # noqa: BLE001  # a "see also" panel never fails a note
        neighbours = []
    wanted = [other_id for other_id, score in neighbours if score >= RELATED_MIN_SIMILARITY]
    if not wanted:
        return []
    #: Each row is a press that links the two notes, so a note already linked
    #: (either way round) is left out, and so is a draft against a committed
    #: note (`manager.create_link` refuses both with a 400).
    linked = {
        other_id
        for pair in session.execute(
            select(EntryLink.source_entry_id, EntryLink.target_entry_id).where(
                or_(EntryLink.source_entry_id == entry.id, EntryLink.target_entry_id == entry.id)
            )
        )
        for other_id in pair
    }
    found = {
        other.id: other
        for other in session.scalars(
            select(Entry).where(Entry.id.in_(wanted), Entry.is_deleted == False)  # noqa: E712
        )
        if not other.is_private and other.id not in linked and bool(other.is_draft) == bool(entry.is_draft)
    }
    ordered = [found[other_id] for other_id in wanted if other_id in found]
    return [_to_out(session, e) for e in ordered[:3]]


class AttachBookmarkBody(BaseModel):
    bookmark_id: int
    #: Undo's door (undo-1005): a detached reference re-attached where it was,
    #: since References list in attach order. The DELETE answers with it.
    created_at: datetime | None = None


@router.get("/{entry_id}/bookmarks")
def entry_bookmarks(entry_id: int, session: Session = Depends(get_session)) -> list[dict]:
    """Bookmarks attached to this note, its References, alongside the
    [[wiki links]] `links` already carries. Its own endpoint rather than a
    field on EntryOut, matching `/related` right above: only the editor
    needs this, and `_to_out_bulk`'s per-list-page bulk fetch shouldn't grow
    a query for something most renders of a note never show."""
    _existing_entry(session, entry_id)
    rows = (
        session.query(Bookmark)
        .join(EntryBookmark, EntryBookmark.bookmark_id == Bookmark.id)
        .filter(EntryBookmark.entry_id == entry_id)
        .order_by(EntryBookmark.created_at)
        .all()
    )
    return [
        {"id": b.id, "url": b.url, "title": b.title, "group_name": b.group_name}
        for b in rows
    ]


@router.post("/{entry_id}/bookmarks", status_code=201)
def attach_bookmark(
    entry_id: int, body: AttachBookmarkBody, session: Session = Depends(get_session)
) -> dict:
    _existing_entry(session, entry_id)
    deps.get_or_404(session, Bookmark, body.bookmark_id, "That bookmark could not be found.")
    already = (
        session.query(EntryBookmark)
        .filter_by(entry_id=entry_id, bookmark_id=body.bookmark_id)
        .first()
    )
    if not already:
        row = EntryBookmark(entry_id=entry_id, bookmark_id=body.bookmark_id)
        if body.created_at is not None:
            row.created_at = body.created_at.replace(tzinfo=None)
        session.add(row)
        session.commit()
    return {"attached": True}


@router.delete("/{entry_id}/bookmarks/{bookmark_id}")
def detach_bookmark(
    entry_id: int, bookmark_id: int, session: Session = Depends(get_session)
) -> dict:
    _existing_entry(session, entry_id)
    row = session.query(EntryBookmark).filter_by(entry_id=entry_id, bookmark_id=bookmark_id).first()
    # When it was attached, so Undo puts it back in its place in the list.
    created_at = row.created_at.isoformat() if row is not None and row.created_at else None
    session.query(EntryBookmark).filter_by(
        entry_id=entry_id, bookmark_id=bookmark_id
    ).delete()
    session.commit()
    return {"detached": True, "created_at": created_at}


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
        return _to_out_bulk(session, matched)

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
        response.headers["X-Total-Count"] = str(manager.count_entries(session, boards=boards))
        return _to_out_bulk(session, entries)

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
        total = manager.count_entries(session, boards=boards)
    response.headers["X-Total-Count"] = str(total)
    return _to_out_bulk(session, entries)


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
    return {"count": session.scalar(select(func.count(Entry.id))) or 0}


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
    created = manager.seed_example_notes(session)
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
    session: Session = Depends(get_session),
) -> EntryOut:
    """One entry. `?deleted=true` also reaches into the bin.

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
    if not entry.is_deleted:
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
        raise HTTPException(status_code=409, detail="Unlock first")


def _safe_filename(title: str, extension: str) -> str:
    """A title is user text; it must not steer where the file lands.

    Same rule `routes_documents.py`'s own `_safe_filename` already enforces
    for a document: not shared, because the two files don't otherwise
    import from each other and a title-to-filename sanitiser is small
    enough that a shared module for it would be the premature abstraction.
    """
    cleaned = re.sub(r"[^\w\s-]", "", title).strip() or "note"
    cleaned = re.sub(r"[\s_]+", "-", cleaned)[:60]
    return f"{cleaned}.{extension}"


@router.get("/{entry_id}/export.md")
def export_entry(entry_id: int, session: Session = Depends(get_session)) -> Response:
    """One note's own text, as a download, BACKLOG.md §95 item D.14: "Full
    export exists. There is no way to hand one note to someone."

    Mirrors `routes_documents.py`'s `export_markdown` (same route shape,
    same `Content-Disposition` filename sanitising) rather than reusing it
    directly: a note has no `file_type` the way a document does, so there
    is no second branch to share, and the two routes would only be coupled
    by the part that's already this short.

    A locked private note answers 409 "Unlock first" (`_refuse_while_sealed`):
    a download named like the note and holding a placeholder is a file that
    looks like the note and is not.
    """
    entry = _existing_entry(session, entry_id)
    if entry.is_deleted:
        raise HTTPException(status_code=404, detail="That note could not be found.")
    _refuse_while_sealed(entry)
    content = manager.readable_content(entry)
    title = manager.extract_title(content) or content.strip()[:60] or "Untitled note"
    body = content if manager.extract_title(content) else f"# {title}\n\n{content}"
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{_safe_filename(title, "md")}"'
        },
    )


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
    entry = _existing_entry(session, entry_id)
    refuse_unless_match(
        if_match,
        current_hash=content_hash(manager.readable_content(entry)),
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
            current_text=manager.readable_content(entry),
            new_text=body.content,
            current=lambda: _to_out(session, entry),
            noun="note",
        )
    new_content = body.content
    if entry.is_private and body.content is not None:
        #: A private note's column holds ciphertext, so "changed" is judged on
        #: the text the editor saw, and the new text is stored encrypted: it
        #: was written plain, with the note still flagged private, and sat in
        #: `entries.content` and the full-text index in the clear (found
        #: 2026-10-04 by scanning a data dir for a private note's words).
        content_changed = body.content != manager.readable_content(entry)
        new_content = _stored_form(entry, body.content) if content_changed else None
    else:
        content_changed = body.content is not None and body.content != entry.content
    tags_changed = body.tags is not None and body.tags != manager.entry_tags(entry)
    #: The note's [[name]] before the edit (a private note is never a target).
    old_name = (
        manager.wiki_opening(entry.content) if content_changed and not entry.is_private else ""
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
    if body.is_draft is not None and body.is_draft != entry.is_draft:
        entry.is_draft = body.is_draft
        session.commit()
    if content_changed:
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
            manager.sync_wiki_links(session, entry)
            manager.resolve_links_to(session, entry)
            session.commit()
        except Exception:
            session.rollback()
            logger.warning("couldn't sync wiki links for entry %s", entry.id, exc_info=True)
        # Same "committed" trigger point as create_entry, an edit can be
        # the first time an image the note already referenced actually
        # gets saved (a staged upload attached, then the note edited to
        # include it, rather than created with it already there).
        _process_committed_media(session, body.content)
    out = _to_out(session, entry)
    if old_name and manager.wiki_opening(entry.content) != old_name:
        # Spelt as the holders wrote it, the opening line as the note does.
        first = (entry.content or "").strip().split("\n", 1)[0]
        new_name = re.sub(r"^\s{0,3}#{1,6}\s+", "", first).strip()
        holders = manager.wiki_holders(session, entry, old_name)
        if holders and new_name:
            spelt = re.search(r"\[\[\s*(" + re.escape(old_name) + r")", holders[0].content, re.IGNORECASE)
            out.wiki_rename = {"old": spelt.group(1) if spelt else old_name, "new": new_name, "notes": len(holders)}
    response.headers["ETag"] = entity_tag(out.content_hash)
    return out


class WikiRenameIn(BaseModel):
    old: str = Field(min_length=1, max_length=120)


@router.post("/{entry_id}/wiki-rename")
def wiki_rename(entry_id: int, body: WikiRenameIn, session: Session = Depends(get_session)) -> dict:
    """Rewrite `[[old]]` as this note's current name in every note that still
    writes the old one (GRAPH_PLAN 518; offered by the edit that renamed it)."""
    entry = _existing_entry(session, entry_id)
    first = (manager.readable_content(entry) or "").strip().split("\n", 1)[0]
    new_name = re.sub(r"^\s{0,3}#{1,6}\s+", "", first).strip()
    if not new_name or len(new_name) > 120 or "]" in new_name or "[" in new_name:
        raise HTTPException(status_code=422, detail="This note's first line can't be a [[name]].")
    notes: list[dict] = []
    rewritten = manager.rewrite_wiki_name(session, entry, body.old, new_name, notes)
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
        current_hash=content_hash(manager.readable_content(entry)),
        current=lambda: _to_out(session, entry),
        noun="note",
    )
    if not entry.is_deleted:
        manager.soft_delete_entry(session, entry)
    return _to_out(session, entry)


@router.post("/{entry_id}/restore", response_model=EntryOut)
def restore_entry(entry_id: int, session: Session = Depends(get_session)) -> EntryOut:
    entry = _existing_entry(session, entry_id)
    if entry.is_deleted:
        manager.restore_entry(session, entry)
    return _to_out(session, entry)


@router.post("/{entry_id}/archive", response_model=EntryOut)
def archive_entry(entry_id: int, session: Session = Depends(get_session)) -> EntryOut:
    """Kept, but out of the way (BACKLOG §30b): distinct from the recycle
    bin: never auto-cleared, never purgeable, no confirmation needed since
    nothing is at risk of being lost."""
    entry = _existing_entry(session, entry_id)
    if not entry.archived_at:
        manager.archive_entry(session, entry)
    return _to_out(session, entry)


@router.post("/{entry_id}/unarchive", response_model=EntryOut)
def unarchive_entry(entry_id: int, session: Session = Depends(get_session)) -> EntryOut:
    entry = _existing_entry(session, entry_id)
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
    removed = manager.purge_entries(
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
        raise ValueError(f"A link holds {LINK_PROPS_MAX} properties at most.")
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


def _stored_form(entry, text: str) -> str:  # noqa: ANN001
    """A past version's text, in the form this note stores it in now."""
    stored = manager.content_for_entry(entry, text or "")
    if stored is None:
        raise HTTPException(status_code=409, detail="Unlock the app first: this version needs the encryption key.")
    return stored


def _readable(content: str) -> str:
    """Decrypt stored content for display, the same way a note itself is.

    `manager.readable_content` reads one attribute, so an event's stored
    content can borrow it without a row to hang it on.
    """
    return manager.readable_content(SimpleNamespace(content=content or ""))


#: How many candidate sources a references scan will read, and how many rows
#: it will answer with. The same two caps `routes_documents._backlinks` uses,
#: and for the same reason: the scan is a LIKE over the notes and documents
#: tables, which is fine at any notebook size and is not free at every one.
REFERENCE_SOURCES_MAX = 400
REFERENCE_ROWS_MAX = 60


def _board_reference_rows_batch(session: Session, entry_ids: list[int]) -> dict[int, list[dict]]:
    """The boards and maps each of these notes is on, one row per board,
    boards and maps told apart. Two statements for the whole page.

    Two tables hold "this note is on that board", and a reader that knows
    one of them is wrong half the time (INBOX 246's first gap). A whiteboard
    card is a `WhiteboardNode` row. A mind map's note is a `WhiteboardObject`
    of kind "note" whose `data.ref_id` is the note (`MAP_REFERENCE_KINDS` in
    routes_whiteboard), and nothing else in `data` says which table the id
    belongs to: the kind does. So the object read filters on the kind first
    and only then on the id, the way routes_graph learnt to (a document and
    a note both numbered 1 exist in any notebook with one of each).

    `json_extract` because SQLite has JSON1 built in and the column is JSON;
    the verify-after in Python stays because a row written before the
    schema was tightened can hold anything. Shared by the Referenced-by row,
    the Connections dialog and the card's counts, so the three cannot
    disagree about what a board reference is.

    **A page at a time** (the performance pass, 2026-10-03). This was a pair
    of statements per note, so sixty cards were a hundred and twenty trips,
    each scanning `whiteboard_nodes` (no index on `entry_id`) and every
    `note` object of every map. `IN (...)` over the page is the same two
    scans once. Rows are read in id order, which is the order the per-note
    reads happened to return them in, and which makes the order a fact
    rather than the planner's choice.
    """
    from tessellate.entry.manager import plain_label

    wanted = set(entry_ids)
    seen_boards: dict[int, set[int]] = {i: set() for i in wanted}
    found: dict[int, list[tuple[int, Entry]]] = {i: [] for i in wanted}
    if not wanted:
        return {}
    for entry_id, board_id, board in session.execute(
        select(WhiteboardNode.entry_id, WhiteboardNode.board_id, Entry)
        .join(Entry, Entry.id == WhiteboardNode.board_id)
        .where(
            WhiteboardNode.entry_id.in_(wanted),
            Entry.is_deleted.is_(False),
        )
        .order_by(WhiteboardNode.id)
    ).all():
        if board_id is None or board_id in seen_boards[entry_id]:
            continue
        seen_boards[entry_id].add(board_id)
        found[entry_id].append((board_id, board))
    for board_id, board, raw in session.execute(
        select(WhiteboardObject.board_id, Entry, WhiteboardObject.data)
        .join(Entry, Entry.id == WhiteboardObject.board_id)
        .where(
            WhiteboardObject.kind == "note",
            func.json_extract(WhiteboardObject.data, "$.ref_id").in_(wanted),
            Entry.is_deleted.is_(False),
        )
        .order_by(WhiteboardObject.id)
    ).all():
        try:
            ref_id = (json.loads(raw or "{}") or {}).get("ref_id")
        except (ValueError, AttributeError):
            continue
        if board_id is None or not isinstance(ref_id, int) or ref_id not in wanted:
            continue
        if board_id in seen_boards[ref_id]:
            continue
        seen_boards[ref_id].add(board_id)
        found[ref_id].append((board_id, board))

    out: dict[int, list[dict]] = {}
    for entry_id, boards in found.items():
        rows: list[dict] = []
        for board_id, board in boards:
            #: `board_settings` says whether this is a whiteboard or a mind map,
            #: and the owner asked for both by name, so the row says which.
            #: Through `manager.board_type_of` rather than parsed here: this app
            #: already reads that column in four places and CodeQL caught the
            #: fifth arriving with a bare `except: pass`, which is fair. One
            #: reader, one decision about what a malformed value means.
            kind = manager.board_type_of(board)
            rows.append({
                "kind": kind,
                "id": board_id,
                "label": plain_label(board.content, 60) or ("Untitled map" if kind == "map" else "Untitled board"),
                "how": "on it",
            })
        out[entry_id] = rows[:REFERENCE_ROWS_MAX]
    return out


def _reference_rows_batch(session: Session, entries: list[Entry]) -> dict[int, list[dict]]:
    """Everything that points at each of these notes: documents, notes,
    boards, maps. Four statements for the whole page, whatever its size.

    INBOX 246, the owner's second sentence: "I want it to show in notes if
    they are attached to or referenced in/by a document, note, whiteboard, or
    mindmap."

    **Two kinds of pointing, and they are found two different ways.** A board
    or a map carries a note as a real row (`WhiteboardNode.entry_id`), so that
    half is a join and is exact. A document or another note carries it as
    text, either a `[[wiki link]]` or a bare mention of its label, so that
    half is the same LIKE-then-verify scan `routes_documents._backlinks`
    runs, and it says which of the two it found because "it links to this"
    and "it happens to say these words" are different facts about a note.

    A note with no label to be named by (an image-only note, a note that
    starts with a heading marker and nothing else) still gets its board rows:
    a card on a board is a reference whether or not the note has a name.

    **One scan for the page, not one per note** (the performance pass,
    2026-10-03, INBOX 441). The text half used to be two LIKE scans per note,
    each reading every note's and document's text: sixty cards at boot were
    two hundred and forty statements and 172 ms on 500 notes, growing with
    the notebook. Now each table is read once, with one `LIKE` flag column per
    distinct label, so SQLite still decides what matches (same ASCII case
    folding, same escaped wildcards, nothing re-implemented in Python) and
    only rows that match some label come back. The per-label caps and the
    order are the old ones: documents newest-updated first, notes newest
    first, `REFERENCE_SOURCES_MAX` each, the note itself never its own source.
    """
    from tessellate.entry.manager import plain_label

    result = _board_reference_rows_batch(session, [entry.id for entry in entries])
    label_of: dict[int, str] = {}
    for entry in entries:
        label = plain_label(entry.content, 60).strip()
        if label:
            label_of[entry.id] = label
    distinct = sorted(set(label_of.values()))

    document_hits: dict[str, list[tuple[int, str, str]]] = {label: [] for label in distinct}
    note_hits: dict[str, list[tuple[int, str]]] = {label: [] for label in distinct}
    if distinct:
        #: `like`, not `ilike`: on SQLite a plain LIKE already folds ASCII case
        #: (the pragma that turns that off is never set here), and `ilike`
        #: compiles to `lower(x) LIKE lower(?)`, which copies every row's text
        #: once per label. Measured over 60 labels on 500 notes, same answers:
        #: 74 ms per call with `ilike`, 35 ms with `like`
        #: (`test_a_mention_matches_whatever_the_case...` pins the folding).
        flags = [Document.content.like(_mention_like(label), escape=LIKE_ESCAPE) for label in distinct]
        for row in session.execute(
            select(Document.id, Document.title, Document.content, *[f.label(f"m{i}") for i, f in enumerate(flags)])
            .where(Document.archived_at.is_(None), or_(*flags))
            .order_by(Document.updated_at.desc(), Document.id.desc())
        ):
            for i, label in enumerate(distinct):
                if row[3 + i] and len(document_hits[label]) < REFERENCE_SOURCES_MAX and _names(row[2], label):
                    document_hits[label].append((row[0], row[1] or "Untitled", row[2] or ""))
        #: Two groups (audit 2026-10-05, ARCH-11: 1.1 s for sixty cards at
        #: 5,000 notes, all of it SQLite running sixty LIKEs over every
        #: note). A label with an interior word has a phrase the full-text
        #: index can find, so its LIKE only reads the notes holding that
        #: phrase; a short label still reads every note. Each label is in
        #: one group, each group is read newest first, so a label's hits come
        #: back in the order they always did.
        narrowed = {label: _interior_phrase(label) for label in distinct}
        groups = [
            [label for label in distinct if narrowed[label] is None],
            [label for label in distinct if narrowed[label] is not None],
        ]
        for group in groups:
            if not group:
                continue
            flags = [Entry.content.like(_mention_like(label), escape=LIKE_ESCAPE) for label in group]
            where = [
                Entry.is_deleted.is_(False),
                #: A private note is encrypted at rest, so its content could not
                #: match the LIKE anyway; the filter is here so that stays true
                #: by decision rather than by side effect. The same sentence
                #: `routes_documents._backlinks` carries, for the same reason.
                Entry.is_private.is_(False),
                or_(*flags),
            ]
            if narrowed[group[0]] is not None:
                where.append(
                    Entry.id.in_(
                        text(
                            " UNION ".join(
                                f"SELECT rowid FROM entries_fts WHERE entries_fts MATCH :p{i}"
                                for i in range(len(group))
                            )
                        ).bindparams(**{f"p{i}": narrowed[label] for i, label in enumerate(group)})
                    )
                )
            for row in session.execute(
                select(Entry.id, Entry.content, *[f.label(f"m{i}") for i, f in enumerate(flags)])
                .where(*where)
                .order_by(Entry.id.desc())
            ):
                for i, label in enumerate(group):
                    #: One over the cap, because the note itself can be among its
                    #: own label's matches and is dropped per note below: the cap
                    #: is on sources other than the note, as it always was.
                    if row[2 + i] and len(note_hits[label]) <= REFERENCE_SOURCES_MAX and _names(row[1], label):
                        note_hits[label].append((row[0], row[1] or ""))

    for entry in entries:
        rows = list(result.get(entry.id, []))
        label = label_of.get(entry.id)
        if label is None:
            result[entry.id] = rows[:REFERENCE_ROWS_MAX]
            continue
        wanted = label.casefold()
        candidates: list[tuple[str, int, str, str]] = []
        for document_id, title, content in document_hits[label]:
            candidates.append(("document", document_id, title, content))
        others = [(nid, content) for nid, content in note_hits[label] if nid != entry.id]
        for note_id, content in others[:REFERENCE_SOURCES_MAX]:
            candidates.append(("note", note_id, plain_label(content, 60) or "Untitled note", content))
        for kind, source_id, source_label, content in candidates:
            rows.append({
                "kind": kind,
                "id": source_id,
                "label": source_label,
                #: A link is a decision someone made; a mention is a coincidence
                #: until they make it. Saying which is what stops this row being
                #: a list of every note that happens to share a word.
                "how": "links to it" if _links_to(content, wanted) else "mentions it",
            })
        #: Links before mentions, so the rows someone chose come first, and the
        #: boards before both because they are exact.
        rows.sort(key=lambda row: {"on it": 0, "links to it": 1, "mentions it": 2}[row["how"]])
        result[entry.id] = rows[:REFERENCE_ROWS_MAX]
    return result


def _mention_like(label: str) -> str:
    """The LIKE that narrows the scan; `_names` decides. A label too short to
    be mentioned (audit 1029 N1) can still be linked, `[[t]]`, so it only
    narrows to notes with that bracket."""
    if len(label) < MENTION_MIN_TITLE_CHARS:
        return f"%[[{like_escape(label)}%"
    return f"%{like_escape(label)}%"


def _names(content: str | None, label: str) -> bool:
    """Whether the text links to `label` or names it as a whole word: the
    one definition (`entry/mentions.py`) every mention surface shares."""
    return names_label(content, label) or _links_to(content, label.casefold())


#: A run of characters the full-text tokenizer may treat as one word: ASCII
#: letters and digits, and anything outside ASCII (whose class only the
#: tokenizer knows, so it is never assumed to split a word).
_FTS_WORDISH = re.compile(r"[A-Za-z0-9\u0080-\U0010ffff]+")


def _interior_phrase(label: str) -> str | None:
    """An `entries_fts` phrase every note containing `label` also contains.

    A note that holds the label as a substring (the LIKE's question) holds
    its interior words as whole words: the label's second word to its
    second-last are bounded by ASCII separators inside the label, so they are
    bounded the same way in the note, and the index (unicode61, which splits
    on every ASCII non-alphanumeric) tokenizes that span exactly as it
    tokenizes the phrase. The first and last words are left out because the
    note may run on into them ("biweekly reviews" holds "weekly review"), and
    no prefix query is used because porter stems a prefix too ("runn"* finds
    nothing where "running" is). None when there is no interior word, or no
    ASCII letter in it to be sure the phrase is not empty.
    """
    words = list(_FTS_WORDISH.finditer(label))
    if len(words) < 3:
        return None
    interior = label[words[1].start() : words[-2].end()]
    if not re.search(r"[A-Za-z0-9]", interior):
        return None
    return '"' + interior.replace('"', '""') + '"'


def _links_to(content: str | None, wanted: str) -> bool:
    """Whether some text has a `[[wiki link]]` whose target is `wanted` (casefolded)."""
    return any(
        manager.wiki_target(match.group(1)).casefold() == wanted
        for match in manager.WIKI_LINK.finditer(content or "")
    )


def _reference_rows(session: Session, entry: Entry) -> list[dict]:
    """Everything that points at this note: documents, notes, boards, maps.

    The page reader (`_reference_rows_batch`) asked about one note, so the
    Referenced-by row, the Connections dialog and the card's chip are the
    same code and cannot disagree.
    """
    return _reference_rows_batch(session, [entry])[entry.id]


@router.get("/{entry_id}/references")
def entry_references(entry_id: int, session: Session = Depends(get_session)) -> dict:
    """What points at this note, from anywhere in the notebook."""
    entry = _existing_entry(session, entry_id)
    items = _reference_rows(session, entry)
    return {"items": items, "total": len(items)}


@router.get("/{entry_id}/then-and-now")
def then_and_now(entry_id: int, as_of: date = Query(...), session: Session = Depends(get_session)) -> dict:
    """This note's claims as they stood at the end of `as_of` against its
    claims now (WORLD_CLASS_PLAN I5, row 23; `ai/timetravel.py`): `then` and
    `now` are its sentences, `changed` pairs them as revised, dropped or new."""
    from tessellate.ai import timetravel
    from tessellate.core.config import user_now

    entry = _existing_entry(session, entry_id)
    if entry.is_private:
        raise HTTPException(status_code=403, detail="This note is private, so its history is not compared.")
    zone = user_now(deps.get_config()).tzinfo
    then = timetravel.text_as_of(session, entry, timetravel.end_of_day(as_of, zone))
    if then is None:
        raise HTTPException(status_code=404, detail=f"This note did not exist on {timetravel.day_words(as_of)}.")
    out = timetravel.then_and_now(then.text, entry.content or "")
    out.update({"as_of": as_of.isoformat(), "revision_id": then.revision_id, "exact": then.exact})
    return out


class ThenTextBody(BaseModel):
    #: A version of the note the reader is looking at (a History row's text).
    then: str = Field(max_length=200_000)


@router.post("/{entry_id}/then-and-now")
def then_and_now_of_text(entry_id: int, body: ThenTextBody, session: Session = Depends(get_session)) -> dict:
    """The same comparison for one version the reader already has on screen,
    a History row: by its text rather than by a day, so two edits made the
    same day are still two versions. Reads nothing but the note now."""
    from tessellate.ai import timetravel

    entry = _existing_entry(session, entry_id)
    if entry.is_private:
        raise HTTPException(status_code=403, detail="This note is private, so its history is not compared.")
    return timetravel.then_and_now(body.then, entry.content or "")


@router.get("/{entry_id}/history")
def entry_history(
    entry_id: int,
    before: int | None = Query(default=None, ge=1),
    session: Session = Depends(get_session),
) -> dict:
    """This note's history, as events and as past versions.

    Two lists because they answer two questions and Brief 7 deliberately
    kept both. `items` is the event log (Brief 7, WORLD_CLASS_PLAN B1):
    everything that ever happened to this note, who did it, and the state
    it left the note in, which is what the History sheet renders and what
    `POST /entries/{id}/restore/{event_id}` replays. `revisions` is the
    older per-edit snapshot list (`EntryRevision`, capped at
    `manager.MAX_REVISIONS`), still written, still restorable through its
    own route, and still the only thing that holds a version of a note
    whose events predate the log.

    `before` pages backwards through the events by id, newest first.
    """
    entry = _existing_entry(session, entry_id)
    _refuse_while_sealed(entry)

    rows = events.events_for(
        session,
        "entry",
        entry.id,
        newest_first=True,
        limit=HISTORY_PAGE + 1,
        before_id=before,
        # The bookkeeping events (a version snapshotted, the dates
        # re-resolved) always accompany the edit that caused them and say the
        # same thing twice in a list a person reads. They are still in the
        # log, still in /audit, and still replayed: hidden here, not dropped.
        skip_actions=events.QUIET_ACTIONS,
    )
    more = len(rows) > HISTORY_PAGE
    rows = rows[:HISTORY_PAGE]
    # What the note said after each row on *this page*, folded in one
    # ascending pass (`events.states_at`). It was every event of the note
    # hydrated into an ORM object with a whole copy of the note's text kept
    # for each, whichever page was asked for. Measured on this sandbox, on a
    # note with 4,000 events: the newest page 109 ms before against 36 ms
    # after, the oldest page 104 ms against 2.9 ms.
    rebuilt = events.states_at(session, "entry", entry.id, [row.id for row in rows])
    items = []
    for row in rows:
        at_the_time = rebuilt.get(row.id, {})
        items.append(
            {
                "id": row.id,
                "action": row.action,
                "actor": row.actor or events.ACTOR_USER,
                "detail": row.detail,
                "created_at": row.created_at.isoformat(),
                # Decrypted for display exactly like the note itself, so a
                # private note's history is readable while unlocked and not
                # otherwise.
                "content": _readable(at_the_time.get("content") or ""),
                "tags": at_the_time.get("tags") or [],
                # Whether this event's values were dropped by the compactor
                # (`events.compact`), so the sheet can say "the text from this
                # change is no longer kept" rather than render a row with no
                # text and no reason for it.
                "compacted": events.is_compacted(row),
            }
        )

    return {
        "items": items,
        "next_cursor": rows[-1].id if (more and rows) else None,
        "revisions": [
            {
                "id": revision.id,
                "content": manager.readable_content(revision),
                "tags": json.loads(revision.tags or "[]"),
                "created_at": revision.created_at.isoformat(),
            }
            for revision in manager.revisions_for(session, entry)
        ],
    }


@router.post("/{entry_id}/restore/{event_id}", response_model=EntryOut)
def restore_event(
    entry_id: int, event_id: int, session: Session = Depends(get_session)
) -> EntryOut:
    """Put this note back the way one of its events left it.

    Replay rather than a stored copy: the state after an event is every
    `after` payload up to and including it, applied in order, which is the
    same definition the History sheet shows and the same one a note rebuilt
    from scratch would get. Restoring is itself an edit, so the current text
    is snapshotted first and the restore records its own event: undoing an
    undo has to work, or this is a trap rather than a safety net.
    """
    entry = _existing_entry(session, entry_id)
    row = session.get(AuditLog, event_id)
    if row is None or row.entity_type != "entry" or row.entity_id != entry.id:
        raise HTTPException(status_code=404, detail="That version no longer exists.")

    if events.is_compacted(row):
        # Not "did not change the note" and not "does not exist": this event
        # happened, and its text was deliberately dropped to stop the log
        # growing by a copy of the note on every edit (`events.compact`).
        # Gone rather than a bad request, which is what 410 is for.
        raise HTTPException(
            status_code=410,
            detail=(
                "That version is no longer kept: changes older than the "
                "history window keep the record of what happened, not the text."
            ),
        )

    state = events.replay(session, "entry", entry.id, upto_event_id=event_id)
    if "content" not in state and "tags" not in state:
        raise HTTPException(
            status_code=400, detail="That event did not change the note's text."
        )

    if "content" in state:
        restored = _stored_form(entry, state["content"])
    manager.record_revision(session, entry)
    if "content" in state:
        entry.content = restored
    if "tags" in state:
        entry.tags = json.dumps(state["tags"])
    manager.mark_edited(entry)
    manager.log_action(
        session,
        "restored",
        "entry",
        entry.id,
        f"back to event {event_id}",
        payload={
            "from_event": event_id,
            "after": {
                "content": entry.content,
                "tags": manager.tags_from_json(entry.tags),
            },
        },
    )
    session.commit()
    session.refresh(entry)
    return _to_out(session, entry)


@router.post("/{entry_id}/history/{revision_id}/restore", response_model=EntryOut)
def restore_revision(
    entry_id: int, revision_id: int, session: Session = Depends(get_session)
) -> EntryOut:
    """Put a past version back.

    Restoring is itself an edit, so the current text is saved first, undoing
    an undo has to work, or this is a trap rather than a safety net.
    """
    entry = _existing_entry(session, entry_id)
    revision = session.get(EntryRevision, revision_id)
    if revision is None or revision.entry_id != entry.id:
        raise HTTPException(status_code=404, detail="That version no longer exists.")

    restored = _stored_form(entry, revision.content)
    manager.record_revision(session, entry)
    entry.content = restored
    entry.tags = revision.tags
    manager.mark_edited(entry)
    manager.log_action(session, "edited", "entry", entry.id, "restored an earlier version")
    session.commit()
    session.refresh(entry)
    return _to_out(session, entry)


@router.post("/{entry_id}/privacy", response_model=EntryOut)
def set_entry_privacy(
    entry_id: int, body: PrivacyBody, session: Session = Depends(get_session)
) -> EntryOut:
    """Encrypt this note at rest, or decrypt it again.

    Needs the vault open, which means the app must be unlocked, the data key
    only exists in memory while it is.
    """
    entry = _existing_entry(session, entry_id)
    if not manager.set_private(session, entry, body.private):
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
        manager.scrub_private_leftovers(session)
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
    entry = _existing_entry(session, entry_id)
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
    content = manager.readable_content(entry)
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
    entry.content = manager.apply_title(content, title)
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

    title = composer_voice.title_for(manager.remove_title(content) or content)
    if not title:
        raise HTTPException(status_code=422, detail="There's no sentence here to take a title from yet.")
    manager.record_revision(session, entry)
    entry.content = manager.apply_title(content, title)
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
    entry = _existing_entry(session, entry_id)
    # Same reason as generate-title: writing decrypted text back to
    # `entry.content` would un-encrypt the note as a side effect.
    if entry.is_private:
        raise HTTPException(
            status_code=400, detail="Make this note readable first: private notes can't be edited here."
        )
    content = manager.readable_content(entry)
    stripped = manager.remove_title(content)
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


@router.get("/{entry_id}/connections")
def entry_connections(entry_id: int, session: Session = Depends(get_session)) -> dict:
    """Everything this note is joined to, in one place and grouped by kind.

    Asked for by way of Kortex's Connections block: *"I should be able to
    seamlessly utilise, flick, link, manage, create and search between
    multiple features"*. Every one of these joins already existed in the
    database: `EntryLink` both ways, `DocumentLink`, `WhiteboardNode`,
    `/media/<name>` references in the body, but each was surfaced (if at
    all) somewhere different: links as chips on the card, documents as a
    separate list, boards nowhere at all. A note could be on three boards
    and referenced by two documents and show none of it.

    Direction is kept, not merged. "This note points at that one" and "that
    one points at this" are different facts, and a merged list can state
    neither.
    """
    entry = _existing_entry(session, entry_id)
    outgoing: list[dict] = []
    incoming: list[dict] = []
    for link, other in manager.links_for_entry(session, entry):
        if other.is_deleted:
            continue
        row = {
            "link_id": link.id,
            "id": other.id,
            # A private note's text never leaves the vault for a list like
            # this: the *fact* of the connection is not secret, its content
            # is. Same rule as the Library's own file-usage chips.
            "preview": (
                "Private note" if other.is_private else _connection_label(other)
            ),
            "is_private": bool(other.is_private),
            **_connection_cue(session, other),
            "reason": link.reason,
            "reason_confidence": link.reason_confidence,
            #: KG3: the kind, named from this end, and the link's properties.
            "link_type": link.link_type,
            "link_label": manager.relation_label(
                manager.relation_types(session), link.link_type, link.source_entry_id == entry.id
            ),
            "props": link.props,
        }
        (outgoing if link.source_entry_id == entry.id else incoming).append(row)

    documents = [
        {"id": doc.id, "title": doc.title, "file_type": doc.file_type}
        for doc in session.scalars(
            select(Document)
            .join(DocumentLink, DocumentLink.document_id == Document.id)
            .where(DocumentLink.entry_id == entry.id)
            .order_by(Document.title)
        )
    ]

    #: **The same reader as the Referenced-by row and the card's chip**, so the
    #: three agree (INBOX 246). The chip says "in 1 document · linked by 1
    #: note" from `_reference_rows`, and this dialog is what it opens: a
    #: document that links to the note by `[[wiki link]]` without the note
    #: being attached to it, and a note that mentions this one without a
    #: stored `EntryLink`, both used to be counted on the chip and missing
    #: here. They are added to the group they belong in, after the rows the
    #: database holds exactly, skipping any the exact rows already carry.
    references = _reference_rows(session, entry)
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
                "preview": "Private note" if other.is_private else _connection_label(other),
                "is_private": bool(other.is_private),
                **_connection_cue(session, other),
                "reason": "Links to it" if row["how"] == "links to it" else "Mentions it",
                "reason_confidence": None,
            })

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
            "preview": "Private note" if other.is_private else _connection_label(other),
            "is_private": bool(other.is_private),
            **_connection_cue(session, other),
            "reason": "Links to it",
            "reason_confidence": None,
        })

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

    files = _connected_files(session, manager.readable_content(entry))

    return {
        "outgoing": outgoing,
        "incoming": incoming,
        "documents": documents,
        "boards": boards,
        "files": files,
        "total": len(outgoing) + len(incoming) + len(documents) + len(boards) + len(files),
    }


def _wiki_link_targets_of(session: Session, entry: Entry) -> list[Entry]:
    """The notes this note's `[[names]]` point at, in the order written.

    `manager.find_by_wiki_name` first, the resolver a save uses to make
    stored links, so a name means here what it means on the graph. Where it
    finds nothing, the note whose plain label is exactly the name, which is
    the rule `_reference_rows` applies from the other end ("links to it"
    when the text holds `[[label]]`): without that second reading a note
    named by its heading was incoming on the target and absent here.
    """
    from tessellate.entry.manager import plain_label

    found: list[Entry] = []
    for name in manager.wiki_link_targets(manager.readable_content(entry)):
        target = manager.find_by_wiki_name(session, name)
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


def _connection_label(entry) -> str:  # noqa: ANN001
    """What one note is called on another note's Connections list.

    A note's own leading `# Heading` is what it calls itself, so that is the
    label when it wrote one, `_preview` alone hands back "# Connections probe
    B\noven temperatures", which renders on a single-line row as the hash, the
    title and the first line of the body run together.
    """
    text = manager.readable_content(entry)
    return manager.extract_title(text) or _preview(text, 80)


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


@router.post("/{entry_id}/links", response_model=EntryOut)
def create_link(
    entry_id: int, body: LinkBody, session: Session = Depends(get_session)
) -> EntryOut:
    source = _existing_entry(session, entry_id)
    target = _existing_entry(session, body.target_id)
    link = manager.create_link(
        session, source, target, reason=body.reason, link_type=body.link_type,
        reason_confidence=body.reason_confidence, props=body.props,
    )
    if link is None:
        # Three refusals share one return value, so the message names the one
        # that actually applies: "already linked" on a draft/note pair would
        # send someone hunting for a link that was never allowed to exist.
        if bool(source.is_draft) != bool(target.is_draft):
            raise HTTPException(
                status_code=400,
                detail="A draft can't be linked to a saved note. Save the draft first.",
            )
        raise HTTPException(
            status_code=400, detail="Those notes are already linked, or you tried to link a note to itself."
        )
    return _to_out(session, source)


@router.delete("/{entry_id}/links/{link_id}", response_model=EntryOut)
def delete_link(
    entry_id: int, link_id: int, session: Session = Depends(get_session)
) -> EntryOut:
    entry = _existing_entry(session, entry_id)
    link = session.get(EntryLink, link_id)
    if link is None or entry.id not in (link.source_entry_id, link.target_entry_id):
        raise HTTPException(status_code=404, detail="That link could not be found.")
    manager.delete_link(session, link)
    return _to_out(session, entry)


@router.patch("/{entry_id}/links/{link_id}", response_model=EntryOut)
def patch_link(
    entry_id: int, link_id: int, body: LinkPatchBody, session: Session = Depends(get_session)
) -> EntryOut:
    """Change a link's type (GRAPH_PLAN KG9), its properties (KG3) or its
    direction (INBOX 693)."""
    entry = _existing_entry(session, entry_id)
    link = session.get(EntryLink, link_id)
    if link is None or entry.id not in (link.source_entry_id, link.target_entry_id):
        raise HTTPException(status_code=404, detail="That link could not be found.")
    sent = body.model_fields_set
    if "link_type" in sent:
        if body.link_type is not None and not manager.is_link_type(session, body.link_type):
            raise HTTPException(status_code=422, detail="That isn't a kind of link this notebook knows.")
        manager.set_link_type(session, link, body.link_type)
    if "props" in sent:
        manager.set_link_props(session, link, body.props)
    if "two_way" in sent:
        manager.set_link_two_way(session, link, body.two_way)
    return _to_out(session, entry)


@router.put("/{entry_id}/links/{link_id}/reason", response_model=EntryOut)
def update_link_reason(
    entry_id: int, link_id: int, body: LinkReasonBody, session: Session = Depends(get_session)
) -> EntryOut:
    """Add, edit, or clear a link's reason by hand, whether it started
    with none, one somebody typed, or one `create_link` deduced on its own.
    """
    entry = _existing_entry(session, entry_id)
    link = session.get(EntryLink, link_id)
    if link is None or entry.id not in (link.source_entry_id, link.target_entry_id):
        raise HTTPException(status_code=404, detail="That link could not be found.")
    try:
        manager.set_link_reason(session, link, body.reason)
        return _to_out(session, entry)
    except Exception:
        # The exception text can carry paths or content; only the log gets it
        # (see test_removing_a_model_never_returns_the_filesystem_path).
        logger.error("Failed to update link reason", exc_info=True)
        raise HTTPException(status_code=500, detail="Couldn't save that reason.") from None


@router.post("/{entry_id}/links/{link_id}/generate-reason")
def generate_link_reason_endpoint(
    entry_id: int, link_id: int, session: Session = Depends(get_session)
) -> dict:
    """Ask the model to generate a specific reason why these two notes are connected."""
    entry = _existing_entry(session, entry_id)
    link = session.get(EntryLink, link_id)
    if link is None or entry.id not in (link.source_entry_id, link.target_entry_id):
        raise HTTPException(status_code=404, detail="That link could not be found.")

    source = session.get(Entry, link.source_entry_id)
    target = session.get(Entry, link.target_entry_id)
    if not source or not target:
        raise HTTPException(status_code=404, detail="Those notes could not be found.")
    # Same boundary generate-title and remove-title enforce: a private note's
    # decrypted text must never reach the model. Every other AI-facing read
    # path in this codebase (search, embeddings, janitor, chat linking...)
    # excludes is_private notes for the same reason.
    if source.is_private or target.is_private:
        raise HTTPException(
            status_code=400, detail="Make both notes readable first: private notes can't be sent to the AI."
        )

    try:
        reason = librarian.generate_link_reason(
            manager.readable_content(source),
            manager.readable_content(target),
            deps.get_model_manager(),
            deps.get_ollama(),
        )
        return {"reason": reason}
    except Exception:
        logger.error("Failed to generate link reason", exc_info=True)
        raise HTTPException(status_code=500, detail="Couldn't generate a reason right now.") from None


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
        document = session.get(Document, body.source_document_id)
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
        if manager.create_link(session, source, target, reason=link.reason) is not None:
            links_created += 1

    return {
        "notes": _to_out_bulk(session, created),
        "links_created": links_created,
    }
