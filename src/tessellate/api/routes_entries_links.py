"""The Connections block and a note's link routes (create, remove, retype, reason, generate a reason).

Split out of routes_entries.py (K24); mounted in app.py beside that module's router. The helpers the
Connections block reads (`_stored_connections`, `_connected_files`, ...) stay in
routes_entries, which routes_documents and the tests reach them through.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from tessellate.ai import librarian
from tessellate.api.routes_entries import (
    LinkBody,
    LinkPatchBody,
    LinkReasonBody,
    _add_referenced,
    _add_wiki_outgoing,
    _attached_documents,
    _boards_of,
    _connected_files,
    _existing_entry,
    _refuse_while_sealed,

    _stored_connections,
    _to_out,
)
from tessellate.api.routes_entities import names_in_note
from tessellate.api.routes_entries_refs import _reference_rows
from tessellate.api.schemas import EntryOut
from tessellate.core import deps
from tessellate.core.database import Entry
from tessellate.core.deps import get_session
from tessellate.entry import manager_links
from tessellate.entry import manager_text
from tessellate.repo import relations as relations_repo
from tessellate.repo.content import NOTES

logger = logging.getLogger("tessellate.api.entries")

router = APIRouter(tags=["entries"], prefix="/entries")


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
    outgoing, incoming = _stored_connections(session, entry)
    documents = _attached_documents(session, entry)
    references = _reference_rows(session, entry)
    _add_referenced(session, references, documents, incoming)
    _add_wiki_outgoing(session, entry, outgoing)
    boards = _boards_of(session, entry, references)
    files = _connected_files(session, manager_text.readable_content(entry))

    return {
        "outgoing": outgoing,
        "incoming": incoming,
        "documents": documents,
        "boards": boards,
        "files": files,
        #: B4: the names it says, each opening its person or project page.
        "names": names_in_note(session, entry),
        "total": len(outgoing) + len(incoming) + len(documents) + len(boards) + len(files),
    }


@router.post("/{entry_id}/links", response_model=EntryOut)
def create_link(
    entry_id: int, body: LinkBody, session: Session = Depends(get_session)
) -> EntryOut:
    source = NOTES.writable(session, entry_id)
    # A binned target would leave an edge to an invisible note until purge (409).
    target = NOTES.writable(session, body.target_id)
    # A link would put a private note's presence on a plain note's chip (and
    # the reverse), so while the vault is locked either end refuses it (W3 A11).
    _refuse_while_sealed(source)
    _refuse_while_sealed(target)
    link = manager_links.create_link(
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
    entry = NOTES.writable(session, entry_id)
    link = relations_repo.get_for_note(session, entry.id, link_id)
    manager_links.delete_link(session, link)
    return _to_out(session, entry)


@router.patch("/{entry_id}/links/{link_id}", response_model=EntryOut)
def patch_link(
    entry_id: int, link_id: int, body: LinkPatchBody, session: Session = Depends(get_session)
) -> EntryOut:
    """Change a link's type (GRAPH_PLAN KG9), its properties (KG3) or its
    direction (INBOX 693)."""
    entry = NOTES.writable(session, entry_id)
    link = relations_repo.get_for_note(session, entry.id, link_id)
    sent = body.model_fields_set
    if "link_type" in sent:
        if body.link_type is not None and not manager_links.is_link_type(session, body.link_type):
            raise HTTPException(status_code=422, detail="That isn't a kind of link this notebook knows.")
        manager_links.set_link_type(session, link, body.link_type)
    if "props" in sent:
        manager_links.set_link_props(session, link, body.props)
    if "two_way" in sent:
        manager_links.set_link_two_way(session, link, body.two_way)
    return _to_out(session, entry)


@router.put("/{entry_id}/links/{link_id}/reason", response_model=EntryOut)
def update_link_reason(
    entry_id: int, link_id: int, body: LinkReasonBody, session: Session = Depends(get_session)
) -> EntryOut:
    """Add, edit, or clear a link's reason by hand, whether it started
    with none, one somebody typed, or one `create_link` deduced on its own.
    """
    entry = NOTES.writable(session, entry_id)
    link = relations_repo.get_for_note(session, entry.id, link_id)
    try:
        manager_links.set_link_reason(session, link, body.reason)
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
    entry = NOTES.writable(session, entry_id)
    link = relations_repo.get_for_note(session, entry.id, link_id)

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
            manager_text.readable_content(source),
            manager_text.readable_content(target),
            deps.get_model_manager(),
            deps.get_ollama(),
        )
        return {"reason": reason}
    except Exception:
        logger.error("Failed to generate link reason", exc_info=True)
        raise HTTPException(status_code=500, detail="Couldn't generate a reason right now.") from None
