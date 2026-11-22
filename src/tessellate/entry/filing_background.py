"""Background filing and embedding of a note, and the offline queue's
delivery dedupe, out of the route file (L-world-class-633).

The job target for `file-entry` is `tessellate.entry.filing_background:
_file_entry_in_background`; rows saved under the old route-module name are
mapped by `core/jobstore.RENAMED_TARGETS`.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import janitor, lexical_filing
from tessellate.core import deps, jobruns, jobs
from tessellate.core.database import Entry
from tessellate.entry import manager, manager_text, tag_suggestions
from tessellate.search import search_manager

logger = logging.getLogger("tessellate.api.entries")


def near_duplicate(session: Session, entry):  # noqa: ANN001, ANN201
    """The saved note that says almost the same thing as `entry`, as
    `(other, score)`, or None. Purely informational: the save has already
    happened."""
    try:
        results = search_manager.semantic_search(
            session, entry.content, deps.get_embeddings(), limit=3
        )
    except Exception:
        logger.warning("the near-duplicate check failed; the note is saved", exc_info=True)
        return None
    for other, score in results or []:
        if other.id != entry.id and score >= 0.9:
            return other, score
    return None


def _file_entry_now(
    session: Session,
    content: str,
    on_late_llm=None,  # noqa: ANN001
    model_deadline: float | None = None,
    release_session: bool = False,
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
            release_session=release_session,
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
    """Embed the settled note, look for a near duplicate and run Tidy's
    automatic reviews (its tag suggestions are kept before it settles)."""
    deps.store_quietly(session, entry)
    found = near_duplicate(session, entry)
    if found is not None:
        entry.filing_similar_id = found[0].id
    session.commit()
    if run is not None:
        run.say("Saved its search vector and checked for a near duplicate.")
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
    """Decide the category of a note filed in the background after its POST has already returned.

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
                # **Suggestions in the same commit as the settled state.**
                # Kept after it, a reader polling `/entries/{id}/filing`
                # saw the note settled and read `suggested_tags` as []
                # (review of PR 240). The notebook's own only: the model's
                # are a round-trip, and the state must not wait for one
                # (PR 242 review); they land in a second commit below.
                tag_suggestions.keep_suggestions_safely(session, entry, entry_id, None)
                # **Settled first, embedded after.** The vector and the
                # near-duplicate search used to land before `filing_state`
                # did, so the card said "Filing…" for as long as the
                # embedding model took to load, minutes on a first launch,
                # after the category was already known (owner, 0.3.31). The
                # vector still has to exist before the duplicate search has
                # anything to compare against; a duplicate found after the
                # poller has stopped is simply not toasted.
                session.commit()
                if filed_by == "llm":
                    tag_suggestions.keep_suggestions_safely(session, entry, entry_id, filed_by)
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


#: The search model still loading is what the first note waits on
#: (L-world-class-6), so its activity row says so rather than "Filing a note".
SEARCH_MODEL_LOADING = "Loading the search model"


def _filing_label_now() -> str | None:
    try:
        return None if deps.get_embeddings().is_ready() else SEARCH_MODEL_LOADING
    except Exception:  # noqa: BLE001 - a label must never break the panel
        logger.debug("filing label: embeddings unreadable", exc_info=True)
        return None


jobs.LIVE_LABELS["file-entry"] = _filing_label_now


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
