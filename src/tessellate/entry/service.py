"""The entries service: what the entries routes do, without HTTP (decision 55).

A route in `api/routes_entries.py` (and its split modules) parses the request,
calls one function here, and shapes the answer. Nothing here imports from
`tessellate.api` or raises an `HTTPException`: an error is a domain name from
`tessellate.repo` or a plain `ValueError` the route turns into a status code.
Like a repository, a function here flushes but leaves the commit to the
caller unless its docstring says it owns the transaction (a background pass).
`tests/test_entry_service.py` calls it directly; `tests/test_thin_routes.py`
keeps the converted routes from growing their own queries back.
"""

from __future__ import annotations

import dataclasses
import logging
import re
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai import filing_certainty, janitor, lexical_filing
from tessellate.core import deps
from tessellate.core.database import LIKE_ESCAPE, Entry, MediaUpload, WhiteboardNode, impersonate_workspace, like_escape
from tessellate.entry import manager, manager_links, manager_private, manager_text, manager_wiki
from tessellate.repo import documents as documents_repo
from tessellate.repo import relation_types

#: How many candidate sources a references scan will read. The same cap
#: `routes_documents._backlinks` uses, and for the same reason: the scan is a
#: LIKE over the notes and documents tables, which is fine at any notebook
#: size and is not free at every one. `routes_entries_refs` reads it here.
REFERENCE_SOURCES_MAX = 400

#: The entries routes' logger, kept so a log line reads the same as before.
logger = logging.getLogger("tessellate.api.entries")


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


def daily_note(session: Session, day: date) -> Entry | None:
    """That day's journal entry, or None when nothing was written on it."""
    heading = DAILY_HEADING.format(date=day.isoformat())
    for entry in _daily_notes(session):
        if _first_line(entry) == heading:
            return entry
    return None


def journal(session: Session, last: date, days: int) -> tuple[list[tuple[date, bool]], int]:
    """`(days, streak)`: each of the `days` days up to `last`, oldest first,
    with whether it has a journal entry, and the days written in a row.

    The streak counts back from `last` and **allows that day to be empty**: a
    person who has written nine days running and has not yet opened today's
    note has a streak of nine, not zero. Breaking it at the first missing day
    including today would make the number drop every midnight and reappear
    when they wrote, which is a counter that punishes the morning.
    """
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
    return [(day, day in written) for day in reversed(window)], streak


def open_daily_note(session: Session, day: date) -> Entry:
    """One day's journal entry, made if it is not there yet ("creates or
    returns", so two presses of the key never make two notes). Nothing else
    about the note is decided here, which is what keeps a journal entry an
    ordinary note."""
    existing = daily_note(session, day)
    if existing is not None:
        return existing
    entry = manager.create_entry(
        session,
        DAILY_HEADING.format(date=day.isoformat()) + "\n\n",
        category_name=manager.UNCATEGORISED,
    )
    # Re-read rather than trusting the insert: two callers pressing the key at
    # the same moment both reach here, and the one that lost should hand back
    # the note that won rather than its own duplicate.
    settled = daily_note(session, day)
    return settled if settled is not None else entry

# --- Connections: what a note is joined to, and what it is called from outside it


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
                connection_label(other)
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
                "preview": connection_label(other),
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
            "preview": connection_label(other),
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


def connection_label(entry, length: int = 80) -> str:  # noqa: ANN001
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


def connected_files(session: Session, text: str) -> list[dict]:
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


def connections(session: Session, entry: Entry, references: list[dict]) -> dict:
    """Everything `entry` is joined to, grouped by kind and direction kept:
    `outgoing`, `incoming`, `documents`, `boards` and `files`. `references`
    are the text-only rows (`routes_entries_refs._reference_rows`), folded in
    after the rows the database holds exactly."""
    outgoing, incoming = _stored_connections(session, entry)
    documents = _attached_documents(session, entry)
    _add_referenced(session, references, documents, incoming)
    _add_wiki_outgoing(session, entry, outgoing)
    return {
        "outgoing": outgoing,
        "incoming": incoming,
        "documents": documents,
        "boards": _boards_of(session, entry, references),
        "files": connected_files(session, manager_text.readable_content(entry)),
    }


# --- Filing: stop it, accept it, and say where a note ended up

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


def stop_all_filing(action: str = "fallback") -> int:
    """Every note still filing, in every space: the Stop on the filing rows
    of Settings, Background tasks and the activity popup. Each note is
    stopped in its own space, so the fallback weighs that space's
    categories only. Returns how many were stopped."""
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
    return {"id": other.id, "preview": connection_label(other, 60)}


def _choices_filled(session: Session, content: str, entry_id: int, category: str, choices: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """The filing call's choices, then recent categories by the words, up to three, never the current one."""
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
    try:
        decision = lexical_filing.decide(
            session, manager_text.readable_content(entry) or "", exclude_entry_id=entry.id
        )
        return next((c.why for c in decision.ranked if c.name == category), "")
    except Exception:  # noqa: BLE001 - a hint never fails the status
        logger.debug("no filing reason for entry %s", entry.id, exc_info=True)
        return ""


def filed_by(entry, state: str) -> str:  # noqa: ANN001
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


def stop_filing_one(session: Session, entry, action: str) -> tuple[bool, str]:  # noqa: ANN001
    """`(stopped, category)`: stop one note that is still filing; a note that
    already settled is left as it is and only says where it is."""
    if (getattr(entry, "filing_state", "") or "") not in ("pending", manager.STAND_IN):
        return False, manager.category_name_for(session, entry)
    return True, stop_filing(session, entry, action)


def accept_filing(session: Session, entry, accepted: bool) -> None:  # noqa: ANN001
    """The review queue's Accept (WORLD_CLASS_PLAN section 17, row 1): the
    category stays and becomes the person's (`user_filed`), which is what a
    move to another category already does. Logged, so the activity log says
    who decided; commits only when something changed."""
    if bool(entry.user_filed) == accepted:
        return
    entry.user_filed = accepted
    manager.log_action(
        session,
        "filing_accepted" if accepted else "filing_unaccepted",
        "entry",
        entry.id,
        detail=manager.category_name_for(session, entry),
    )
    session.commit()


def filing_status(session: Session, entry) -> dict:  # noqa: ANN001
    """Where a note filed in the background ended up, and what to offer when
    nothing (or an unsure pick) filed it: the whole of what the "Filed under
    X" notification reads."""
    similar = _filing_similar(session, entry)
    state = getattr(entry, "filing_state", "done") or "done"
    category = manager.category_name_for(session, entry)
    decided_by = filed_by(entry, state)
    shown = filing_certainty.shown(
        entry.ai_confidence, user_filed=bool(getattr(entry, "user_filed", False))
    )
    #: A pick the calibration put under the review line (`filing_certainty`)
    #: is offered the same way: the alternatives beside the one it chose.
    unsure_pick = decided_by == "ai" and 0 < shown < manager.REVIEW_CONFIDENCE
    suggestions: list[str] = []
    reasons: dict[str, str] = {}
    why = ""
    proposal = None
    held = None
    waits = ""
    if (decided_by == "none" and category == manager.UNCATEGORISED) or unsure_pick:
        suggestions, reasons, proposal, held, waits = _offered_categories(session, entry, category)
    elif decided_by == "words" and category != manager.UNCATEGORISED:
        why = _filing_why(session, entry, category)
    return {
        "id": entry.id,
        "filing_state": state,
        "category": category,
        "ai_confidence": shown,
        "similar": similar,
        "filed_by": decided_by,
        "suggestions": suggestions,
        "suggestion_reasons": reasons,
        "why": why,
        "proposal": proposal,
        "held_sensitive": held,
        #: Why the words left it waiting ("A close call between Hobbies and
        #: Study, so it waits for you to choose."), said by the saved line.
        "waits_why": waits if decided_by == "none" else "",
    }


# --- Extract notes (BACKLOG.md §62): write what a preview showed


def commit_extraction(
    session: Session,
    notes: list[tuple[str, str, str, list[str]]],
    links: list[tuple[str, str, str]],
    source_document_id: int | None,
) -> tuple[list[Entry], int]:
    """`(created, links_created)`: write exactly what a preview showed
    (possibly edited, possibly trimmed). `notes` are `(ref, content,
    category, tags)` with refs already unique, `links` are `(source_ref,
    target_ref, reason)` where a ref is one of these notes or
    `existing:<id>`. `manager.create_link`'s own `reason=` bypasses the
    generic `AUTO_REASON_TEXT` guess, so every link keeps the reason the
    preview generated for it."""
    by_ref: dict[str, Entry] = {}
    created: list[Entry] = []
    for ref, content, category, tags in notes:
        entry = manager.create_entry(
            session,
            content=content,
            category_name=category or manager.UNCATEGORISED,
            tags=tags,
            # Reviewed (and possibly edited) by the person before it was
            # ever asked to save, the same confidence level a user-filed
            # category gets in `create_entry`, not the AI's own guess from
            # the preview (which was about the SPLIT, not the filing).
            ai_confidence=100,
        )
        by_ref[ref] = entry
        deps.store_quietly(session, entry)
        created.append(entry)

    if source_document_id is not None:
        document = documents_repo.find(session, source_document_id)
        # A document deleted between preview and commit is skipped rather
        # than refused: the notes are the thing being saved, same reasoning
        # `create_entry`'s own `document_ids` handling already uses.
        if document is not None:
            for entry in created:
                manager.link_document(session, document.id, entry.id)

    links_created = 0
    for source_ref, target_ref, reason in links:
        source = by_ref.get(source_ref)
        if source is None:
            continue  # a ref that isn't among the notes just created, ignore rather than fail the whole save
        if target_ref.startswith("existing:"):
            try:
                target_id = int(target_ref.removeprefix("existing:"))
            except ValueError:
                continue
            target = manager.get_entry(session, target_id)
            if target is None or target.is_deleted:
                continue  # deleted between preview and commit
        else:
            target = by_ref.get(target_ref)
            if target is None:
                continue
        if manager_links.create_link(session, source, target, reason=reason) is not None:
            links_created += 1
    return created, links_created


# --- Titles and privacy


def retitle(session: Session, entry, content: str, title: str, note: str) -> None:  # noqa: ANN001
    """Put `title` on the note, replacing a title it already has rather than
    stacking a second heading; the old text goes to the revision history and
    `note` to the activity log. Commits. The caller has refused a private
    note: writing its decrypted text back would un-encrypt it."""
    manager.record_revision(session, entry)
    entry.content = manager_text.apply_title(content, title)
    manager.mark_edited(entry)
    manager.log_action(session, "edited", "entry", entry.id, note)
    session.commit()
    session.refresh(entry)


def remove_title(session: Session, entry) -> None:  # noqa: ANN001
    """Take the leading heading line back out; a note with no title is left
    as it is (the client only offers this when a title is set, and a stale
    menu should not fail). Commits only when something changed."""
    content = manager_text.readable_content(entry)
    stripped = manager_text.remove_title(content)
    if stripped == content:
        return
    manager.record_revision(session, entry)
    entry.content = stripped
    manager.mark_edited(entry)
    manager.log_action(session, "edited", "entry", entry.id, "removed the title")
    session.commit()
    session.refresh(entry)


def set_privacy(session: Session, entry, private: bool) -> bool:  # noqa: ANN001
    """Encrypt this note at rest, or decrypt it again; False when the vault is
    shut (the data key only exists in memory while the app is unlocked).
    Commits, then on sealing scrubs the note's words out of the search
    index's segments and the WAL too (SEC-03), not only out of the answers."""
    if not manager_private.set_private(session, entry, private):
        return False
    #: KG4: a private note has no property index; a public one gets it back.
    manager.reindex_properties(session, entry)
    session.commit()
    if private:
        manager_private.scrub_private_leftovers(session)
    session.refresh(entry)
    return True


def make_all_private(session: Session) -> list[int] | None:
    """Seal every ordinary note (INBOX 1695 d): the ids sealed, or None when
    the vault is shut. Commits, then scrubs what the sealed notes left."""
    sealed = manager_private.make_all_private(session)
    if sealed is None:
        return None
    session.commit()
    if sealed:
        manager_private.scrub_private_leftovers(session)
    return sealed
