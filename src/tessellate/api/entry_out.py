"""An entry as the API answers it: the `EntryOut` every notes route returns.

Shaping the response model is the route layer's job, so this lives under
`api/` and the services (`entry/capture.py`, `entry/listing.py`,
`entry/editing.py`) never build one (L-world-class-632). `to_out` reads one
note; `to_out_bulk` shapes a whole list page in a fixed number of queries.
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from tessellate.ai import filing_certainty
from tessellate.core import cjk
from tessellate.api.edit_conflicts import content_hash
from tessellate.api.schemas import (
    AttachmentOut,
    DocumentRefOut,
    EntryDateOut,
    EntryOut,
    LinkOut,
    SimilarOut,
)
from tessellate.entry import manager, manager_links, manager_purge, manager_text, provenance, tag_reasons, tag_suggestions
from tessellate.entry import properties as note_properties
from tessellate.entry import service as entry_service
from tessellate.repo import memberships, relation_types


def to_out(
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
    transcribed: bool | None = None,
    member: tuple[list[str], list[str]] | None = None,
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
    #: Where the note came from (`entry/provenance.py`); the audio check is one query unless a list pre-fetched it.
    source_kind, source_label = provenance.source_kind(
        getattr(entry, "source_url", None),
        getattr(entry, "source_path", None),
        bool(provenance.transcribed_ids(session, [entry.id])) if transcribed is None and entry.id else bool(transcribed),
    )
    also_in, in_groups = member if member is not None else memberships.for_one(session, entry)
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
        also_in=also_in,
        groups=in_groups,
        tags=manager.shown_tags(entry),
        ai_confidence=filing_certainty.shown(
            entry.ai_confidence, user_filed=bool(getattr(entry, "user_filed", False))
        ),
        tag_suggest_off=bool(getattr(entry, "tag_suggest_off", False)),
        suggested_tags=(offered := tag_suggestions.open_suggestions(entry)),
        suggested_tag_reasons=tag_reasons.reasons(content, offered),
        #: Never a private note's: derived from its text, as its suggestions
        #: are (tests/test_private_suggested_tags.py).
        discarded_tags=[] if getattr(entry, "is_private", False) else tag_suggestions.json_tags(getattr(entry, "discarded_tags", "[]")),
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
        source_kind=source_kind,
        source_label=source_label,
        is_board=bool(getattr(entry, "is_board", False)),
        board_kind=getattr(entry, "board_kind", None),
        map_topic=bool(getattr(entry, "map_topic", False)),
        workspace_id=getattr(entry, "workspace_id", "default") or "default",
        created_at=entry.created_at,
        deleted_at=entry.deleted_at if entry.is_deleted else None,
        archived_at=entry.archived_at,
        dates=date_outs(resolved_dates),
        documents=[
            DocumentRefOut(id=doc.id, title=doc.title) for doc in resolved_documents
        ],
        links=link_outs(session, entry, resolved_links),
        attachments=attachment_outs(resolved_attachments),
        filed_by=filed_by,
        filing_state=getattr(entry, "filing_state", "done") or "done",
        similar=similar,
    )


def date_outs(dates: list) -> list[EntryDateOut]:
    return [
        EntryDateOut(
            phrase=d.phrase,
            at=d.at.date(),
            precision=d.precision,
            time=d.at.strftime("%H:%M") if d.precision == "minute" else None,
        )
        for d in dates
    ]


def link_outs(session: Session, entry, links: list) -> list[LinkOut]:  # noqa: ANN001
    return [
        LinkOut(
            link_id=link.id,
            entry_id=other.id,
            preview=entry_service.connection_label(other, 60),
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


def attachment_outs(attachments: list) -> list[AttachmentOut]:
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


def to_out_bulk(session: Session, entries: list) -> list[EntryOut]:
    """`to_out` for a whole list-endpoint page in a fixed number of queries
    instead of ~4 per entry (ROADMAP.md #0 priority, item 1)."""
    ids = [e.id for e in entries]
    category_names = manager.bulk_category_names(session, entries)
    dates_by_id = manager.entry_dates_bulk(session, ids)
    documents_by_id = manager.documents_for_entries_bulk(session, ids)
    links_by_id = manager.links_for_entries_bulk(session, ids)
    attachments_by_id = manager_purge.attachments_for_entries_bulk(session, ids)
    heard = provenance.transcribed_ids(session, ids)
    also_in, in_groups = memberships.bulk(session, entries)
    return [
        to_out(
            session,
            e,
            category_name=category_names.get(e.category_id, manager.UNCATEGORISED),
            dates=dates_by_id.get(e.id, []),
            documents=documents_by_id.get(e.id, []),
            links=links_by_id.get(e.id, []),
            attachments=attachments_by_id.get(e.id, []),
            transcribed=e.id in heard,
            member=(also_in.get(e.id, []), in_groups.get(e.id, [])),
        )
        for e in entries
    ]


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


def previewed(rows: list[EntryOut], preview: int) -> list[EntryOut]:
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
        #: A meeting's card reads its sections from the whole text (`meetingGlance`), so a meeting is sent whole. So is
        #: a private note: the index never reads one, so the list's filter box matches it on the text the list holds
        #: (INBOX 1525 review). Locked, its text is the short placeholder anyway.
        whole = row.is_private or "meeting" in {v.lower() for v in row.properties.get("type", [])}
        if len(row.content) > preview and not whole:
            cut = row.content[:preview]
            row.content = (cut.rsplit(None, 1)[0] if " " in cut or "\n" in cut else cut).rstrip()
            row.content_truncated = True
    return rows


def similar_out(found: tuple | None) -> SimilarOut | None:
    """The near-duplicate warning (`filing_background.near_duplicate`'s entry and score) as the API says it."""
    if found is None:
        return None
    other, score = found
    return SimilarOut(id=other.id, preview=manager_text.preview(other.content), similarity=round(score, 2))
