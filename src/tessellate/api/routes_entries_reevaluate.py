"""Re-evaluate a note: the route and the two helpers that suggest other categories and tags.

Split out of routes_entries.py (K24); mounted in app.py beside that module's router. The helpers the
route reads (`_existing_entry`, `_to_out`, `_engine_tags`, ...) stay in routes_entries.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import janitor, librarian
from tessellate.ai.ollama_client import OllamaError
from tessellate.api.routes_entries import (
    _engine_tags,
    _existing_entry,
    _preview,
    _tag_reasons,
    _tag_vocabulary,
    _to_out,
)
from tessellate.core import deps, jobruns
from tessellate.core.database import Entry
from tessellate.core.deps import get_session
from tessellate.entry import manager
from tessellate.search import search_manager

logger = logging.getLogger("tessellate.api.entries")

router = APIRouter(tags=["entries"], prefix="/entries")


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
