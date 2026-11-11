"""Create/read/update/soft-delete entries, links, and audit logging.

Deliberately AI-free: the API layer decides the category (by asking the
janitor) and this module just stores what it's told. That
keeps capture working even when every AI piece is down (plan §4).
"""

from __future__ import annotations

import importlib
import json
import logging
import re
from datetime import datetime, timedelta

from sqlalchemy import delete, func, or_, select, tuple_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


from tessellate.core.database import (
    LIKE_ESCAPE,
    MediaUpload,
    Category,
    EmbeddingRecord,
    Entry,
    DocumentLink,
    EntryDate,
    EntryLink,
    EntryProperty,
    EntryRevision,
    utcnow,
    like_escape,
)
from tessellate.core import events
from tessellate.core.lookahead import Ahead
from tessellate.entry import link_facts, timewords
from tessellate.entry.cleantext import clean_name, is_blank, name_key
from tessellate.entry.tagnames import normalise_tags
from tessellate.repo import relation_types

# Where entries land when no AI is available or the AI can't decide.
UNCATEGORISED = "Uncategorised"

#: Below this confidence a filing is worth a person's look: the card's "check
#: this" chip (`REVIEW_THRESHOLD` in app.js, the same number) and the review
#: queue (WORLD_CLASS_PLAN section 17, row 1). Section 17 wrote "under 60%";
#: the queue takes the card's 50 so a note in it always wears the chip that
#: says why (recorded in the plan's Decisions made).
REVIEW_CONFIDENCE = 50


def review_queue_count(session: Session) -> int:
    """How many live notes wait for a person to look at their filing: the
    janitor was unsure (an attempt under `REVIEW_CONFIDENCE`) or left them in
    Uncategorised, and nobody has decided since (`user_filed`). Drafts and
    boards are not notes in the list, so they are not counted."""
    return int(
        session.scalar(
            select(func.count(Entry.id))
            .outerjoin(Category, Entry.category_id == Category.id)
            .where(
                Entry.is_deleted == False,  # noqa: E712
                Entry.is_draft == False,  # noqa: E712
                Entry.is_board == False,  # noqa: E712
                Entry.user_filed == False,  # noqa: E712
                or_(
                    (Entry.ai_confidence > 0) & (Entry.ai_confidence < REVIEW_CONFIDENCE),
                    Entry.category_id.is_(None),
                    Category.name == UNCATEGORISED,
                ),
            )
        )
        or 0
    )


def log_action(
    session: Session,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    detail: str | None = None,
    payload: dict | None = None,
    actor: str | None = None,
):
    """Append to the audit log. Committed with the caller's transaction.

    Now a thin pass to `core/events.record`, which is the only writer of
    `AuditLog` rows (Brief 7). Kept as the name every caller in the app
    already uses, with the same five positional arguments in the same
    order, so that the event log arrived without eighty call sites being
    rewritten and without any of them losing an actor: `record` fills that
    in from the context (`events.acting_as`).

    `payload` is the whole value of each field this action set, for the
    writes that can be replayed. Returns the row, or None when the event
    was folded into the write that contains it (`events.writes`).
    """
    return events.record(
        session,
        action,
        entity_type,
        entity_id,
        detail=detail,
        payload=payload,
        actor=actor,
    )


def category_space(session: Session, workspace_id: str | None = None) -> str:
    """The one space a category lookup or insert belongs to.

    Given a space, that one. Otherwise the session's own when a request scoped
    it to a single space, and "default" when it did not ("All spaces", or a
    background pass with no request): that is where an unscoped insert lands
    anyway (`WorkspaceMixin`'s column default), so a lookup that answers for
    the same space can never find a row the insert would not have made.
    Callers filing an existing note pass the note's own space instead
    (`entry_space`), which is the only right answer in the "all" view.
    """
    if workspace_id:
        return workspace_id
    ambient = session.info.get("workspace_id")
    if ambient and ambient != "all":
        return ambient
    return "default"


def entry_space(entry: Entry) -> str:
    """A note's own space, for filing it: the space its category must be in."""
    return getattr(entry, "workspace_id", None) or "default"


#: The longest a category name may be; `/categories` refuses more, and now
#: every other writer clips to it instead of storing 300 characters.
#: **The one private-note rule** (audit 1031 N3, N23, N40): a private note's
#: words show in its own row and editor and nowhere else. Anything that points
#: at it (a link chip, the Connections sheet, the near-duplicate line) calls it
#: this, vault open or locked; the search never indexes it and the `[[` picker
#: leaves it out.
PRIVATE_LABEL = "Private note"

#: A note in a locked private space, seen from a link outside it (INBOX 1727):
#: the fact of the link stays, its title and reason do not.
PRIVATE_SPACE_NOTE = "A private note"


MAX_CATEGORY_LENGTH = 100


def category_label(name: str | None) -> str:
    """A category name as it is stored (audit 1031 N6): invisible characters
    gone, spacing collapsed, ends trimmed, clipped to 100, and a blank name is
    Uncategorised. The one rule every writer shares, as `normalise_tags` is for
    tags, so a note route cannot make a name `/categories` would refuse."""
    return clean_name(name)[:MAX_CATEGORY_LENGTH].strip() or UNCATEGORISED


def get_or_create_category(
    session: Session, name: str, workspace_id: str | None = None
) -> Category:
    """Categories are identified by name within a space; create on first use.

    `workspace_id` is for the caller that knows which space the category
    belongs in when the *session* does not: a background pass has no request
    and therefore no `X-Workspace-ID`, so the row would take the column
    default and the note's own space could not list the category it was filed
    into. Given one, both halves use it: the lookup, or a "Research" in
    another space would be reused, and the insert.

    **Two writers can reach this at the same moment**, and the naive
    check-then-insert loses that race: both see no row, both insert, and the
    second hits `UNIQUE constraint failed: categories.workspace_id,
    categories.name`, which surfaces as a 500 and loses whatever note was
    being saved. Not theoretical: measured with six concurrent writers
    capturing twelve notes each, 5 of 72 saves died that way, because the
    app genuinely has several writers (the desktop window, a browser tab,
    and the night shift's auto-filing all save notes).

    The insert therefore runs in a savepoint, and losing the race is treated
    as what it is: somebody else has made the category this caller wanted, so
    read theirs. The savepoint matters because without it the failed insert
    poisons the caller's whole transaction, turning a recoverable collision
    into the same 500 by a different route. The re-read is guaranteed to find
    the row: SQLite allows one writer at a time, so the other transaction had
    to have committed for its row to be what this one collided with.
    """
    # **Always one space, never "whichever space has that name".** With no
    # space given, the lookup used to be by name alone, which is right only
    # while the session itself is scoped to a space (the statement filter in
    # `core/database.py` then adds the space for us). In the "All spaces"
    # view the filter is off, so filing a note of space "uni" under "Kids"
    # found the default space's "Kids" and pointed the uni note at it; uni's
    # own view could not list that category and the note read as
    # Uncategorised (measured 2026-10-03). The insert half already landed in
    # one space (the session's, or the column default); the lookup now asks
    # the same space the insert would write to.
    workspace_id = category_space(session, workspace_id)
    name = category_label(name)

    def _find() -> Category | None:
        exact = session.scalar(
            select(Category).where(
                Category.name == name, Category.workspace_id == workspace_id
            )
        )
        if exact is not None:
            return exact
        # "work" is "Work": the first spelling made is the one kept, as tags do.
        wanted = name_key(name)
        for other in session.scalars(
            select(Category).where(Category.workspace_id == workspace_id).order_by(Category.id)
        ):
            if name_key(other.name) == wanted:
                return other
        return None

    category = _find()
    if category is not None:
        return category
    try:
        with session.begin_nested():
            category = Category(name=name, workspace_id=workspace_id)
            session.add(category)
            session.flush()  # assigns category.id without committing yet
    except IntegrityError:
        existing = _find()
        if existing is None:  # pragma: no cover - see the docstring's last line
            raise
        return existing
    log_action(session, "created", "category", category.id, name)
    return category


def mark_edited(entry: Entry) -> None:
    """Record that a person just changed what this note says.

    Called at each per-note edit of the text, title, tags or category, and
    only there; see `Entry.edited_at` for why `updated_at` cannot answer
    "recently edited". Not called by filing (`record_filing`), opening,
    pinning, a privacy toggle, or a notebook-wide tag or category rename:
    those change a note without anyone editing it, and a list sorted by
    "recently edited" that jumped on them would be sorting by noise.
    """
    entry.edited_at = utcnow()


def set_category(session: Session, entry: Entry, name: str) -> Entry:
    """Put a note in a category by name, creating the category if it is new.

    The plain "file this here" move, without the correction bookkeeping
    `update_entry_with_correction` does: that one exists to notice a person
    overruling the AI, and a caller that is simply placing a note (a fixture,
    an import, a tool) is not overruling anything. Kept beside
    `get_or_create_category` because the pair is the whole of filing by name.
    """
    # **Filed in the note's own space, whoever is doing the filing.** A new
    # category takes its space from `session.info["workspace_id"]`, which only
    # a request sets (from `X-Workspace-ID`). A caller with no request behind
    # it, a background pass, an import running off the main thread, would
    # create the category in "default" while the note it is filing sits in
    # another space, and a note filed into a category its own space cannot
    # list is a note that has quietly left the sidebar. The link path had
    # exactly this bug and it was measured; this is the same fact stated once
    # more, at the other place a row is made for a note.
    #
    # Passed as a value rather than by borrowing the session's ambient space
    # (`database.impersonate_workspace`): that import is `core.deps` from
    # `entry.manager`, which CodeQL flagged as the start of an import cycle,
    # and the value is the honest thing to pass anyway. It is one fact, the
    # note's own space, travelling to the one place that needs it.
    entry.category_id = get_or_create_category(
        session, name, workspace_id=entry_space(entry)
    ).id
    session.flush()
    return entry


@events.writes("entry", "created")
def create_entry(
    session: Session,
    content: str,
    category_name: str = UNCATEGORISED,
    tags: list[str] | None = None,
    ai_confidence: int = 0,
    client_key: str | None = None,
    commit: bool = True,
    dates: bool = True,
) -> Entry:
    """Store one thought. Commits the transaction.

    `client_key` is the offline queue's name for this save; the unique index
    on it makes a second save with the same key raise `IntegrityError`, which
    the route answers with the note the first one made.

    `commit=False` only flushes, for a bulk writer (an import) that commits
    in batches. `dates=False` leaves the date phrases to a caller that sets
    `created_at` first and calls `record_dates` itself (an import), so the
    note is not read for dates twice."""
    from tessellate.entry.properties import lift_title

    category = get_or_create_category(session, category_name)
    entry = Entry(
        content=lift_title(content),
        category_id=category.id,
        # The schema normalises an HTTP write; this is every other writer
        # (the AI tools, imports, passive capture), held to the same rule.
        # No comma split here: a restore or import brings back a legacy tag
        # that holds one, and the split is for what a person types (schema).
        tags=json.dumps(normalise_tags(tags, split=False)),
        ai_confidence=ai_confidence,
        client_key=client_key or None,
    )
    session.add(entry)
    session.flush()
    if dates:
        record_dates(session, entry)
    reindex_properties(session, entry)
    log_action(
        session,
        "created",
        "entry",
        entry.id,
        payload={"after": events.entry_state(entry)},
    )
    if commit:
        session.commit()
    else:
        session.flush()
    return entry


#: What a listing does about boards. A board (and therefore a mind map) *is*
#: an `Entry`, see `Entry.is_board`, so every query over entries has to say
#: which of the three it means rather than inherit whichever the last person
#: assumed.
#:
#: Reported: "I made a mindmap naming it test and I think it came up as a new
#: note??" It did. `GET /entries` had no board filter at all, so the notes
#: list, its count, and everything else built on that response listed every
#: board and map in the notebook as a note. Measured on a notebook with nine
#: maps: twelve rows in the Notes list, ten of them maps.
BOARDS_EXCLUDE = "exclude"
BOARDS_INCLUDE = "include"
BOARDS_ONLY = "only"
BOARD_MODES = (BOARDS_EXCLUDE, BOARDS_INCLUDE, BOARDS_ONLY)


def _list_entries_filter(
    query, include_deleted: bool, include_archived: bool, boards: str = BOARDS_INCLUDE
):
    """The where-clause `list_entries` and `count_entries` both need: kept
    in one place so a filter added to one can't quietly drift from the
    other and make the count lie about what the list actually shows.

    `boards` defaults to `include`, which is what every in-process caller
    (background jobs, the librarian, the AI tools) has always got; the HTTP
    route is the one that asks for `exclude`, because "the notes list" is
    exactly the thing that must not have boards in it.
    """
    if not include_deleted:
        query = query.where(Entry.is_deleted == False)  # noqa: E712
    if not include_archived:
        query = query.where(Entry.archived_at.is_(None))
    #: A blank note (whitespace only, INBOX 1439) is nobody's note: no list
    #: row, no count, no graph node, whichever surface asks.
    query = query.where(func.trim(Entry.content, " \t\r\n") != "")
    if boards == BOARDS_EXCLUDE:
        query = query.where(Entry.is_board == False)  # noqa: E712
    elif boards == BOARDS_ONLY:
        query = query.where(Entry.is_board == True)  # noqa: E712
    return query


def list_entries(
    session: Session,
    include_deleted: bool = False,
    include_archived: bool = False,
    limit: int | None = None,
    offset: int = 0,
    boards: str = BOARDS_INCLUDE,
    after: tuple | None = None,
    ids: list[int] | None = None,
) -> list[Entry]:
    """Pinned first, then newest first. Deleted and archived entries stay
    hidden until the recycle bin / archive UI asks for them explicitly, 
    archiving is not deleting, but it means the same "out of the way until
    asked for" thing for an ordinary list.

    `limit`/`offset` are optional and `None` means "everything", so every
    existing caller (background jobs, the librarian, tests) that wants the
    whole notebook keeps working unchanged, pagination is additive, not a
    breaking change to this function's contract. `routes_entries.py` is the
    one caller that always passes a bounded `limit`; see its own comment for
    why an HTTP response is a different situation from an in-process call.
    """
    query = select(Entry).order_by(
        Entry.pinned.desc(), Entry.created_at.desc(), Entry.id.desc()
    )
    query = _list_entries_filter(query, include_deleted, include_archived, boards)
    if after is not None:
        # A keyset page (WORLD_CLASS_PLAN B7): the rows that sort after the
        # last one the caller saw, by the same three keys the ORDER BY uses,
        # all descending, so "after" is "less than" as one row value. Served
        # from `ix_entries_live`'s trailing columns, which are these three in
        # this order and direction (measured in `tests/test_query_plans.py`).
        query = query.where(
            tuple_(Entry.pinned, Entry.created_at, Entry.id) < tuple_(*after)
        )
    if ids is not None:
        # Just these rows of the same list, in its order (audit 2026-10-05,
        # FE-05: the client re-reads what a save touched, not the notebook).
        query = query.where(Entry.id.in_(ids))
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    return list(session.scalars(query))


def list_sort_key(entry: Entry) -> tuple:
    """What `list_entries(after=...)` takes: the row's own ORDER BY values."""
    return (bool(entry.pinned), entry.created_at, entry.id)


def note_filter(
    query,
    *,
    include_archived: bool = True,
    boards: str = BOARDS_EXCLUDE,
    include_drafts: bool = False,
):
    """The where-clause that says what a note is (see `count_notes`); a
    surface that lists or groups notes builds on this, never its own."""
    #: `deleted_at` too: the bin is both flags, and some writers set one.
    query = _list_entries_filter(query, False, include_archived, boards).where(Entry.deleted_at.is_(None))
    return query if include_drafts else query.where(Entry.is_draft == False)  # noqa: E712


def count_notes(
    session: Session,
    *,
    include_archived: bool = True,
    boards: str = BOARDS_EXCLUDE,
    include_drafts: bool = False,
) -> int:
    """How many notes there are: the one definition every count in the app uses.

    A note is every entry not in the bin, archived included; boards, drafts
    (the graph, the categories and the Notes tab each keep them out, and a
    blank one is a draft nobody wrote) and blank entries are not notes.
    INBOX 1439: six surfaces counted six ways, 282, 279 and 277 in the same
    minute. Private notes count: that a note exists is not what privacy hides.
    A surface that shows a subset, such as the Notes list (`include_archived=
    False`, the archive is its own view; `include_drafts=True`, because the
    list endpoint still returns the rows and the client sorts drafts out),
    passes the flag that widens or narrows it; the predicate is
    `_list_entries_filter`'s, so a paginated list's total cannot drift from the
    rows under it either.
    """
    query = note_filter(
        select(func.count()).select_from(Entry),
        include_archived=include_archived,
        boards=boards,
        include_drafts=include_drafts,
    )
    return session.scalar(query) or 0


def entry_id_scope(
    session: Session,
    *,
    deleted: bool = False,
    archived: bool = False,
    boards: str = BOARDS_INCLUDE,
) -> set[int]:
    """Every entry id in one of the three views, live, bin, or archive.

    Exists because the caller that needs this (semantic search's scope check in
    `routes_entries.list_entries_route`) needs *only* ids, and its own comment
    already said so, "ids only, no row bodies, cheap even at real notebook
    scale". The code underneath it did not match: it called `list_entries()`
    and threw every mapped `Entry` away after reading `.id`, which is the exact
    cost `search_manager.semantic_search` was rewritten to stop paying
    (its docstring measures it at ~85% of a search at 20k+ notes, materialising
    entities to score and discard them). A comment describing an optimisation
    the code does not perform is worse than no comment, because the next
    profiler run has to rediscover it.

    Deliberately unpaginated, for the reason the call site gives: this decides
    which semantic hits are *in scope* at all, so a page boundary here would
    silently drop legitimate matches.
    """
    query = select(Entry.id)
    if deleted:
        query = query.where(Entry.is_deleted == True)  # noqa: E712
    elif archived:
        query = query.where(
            Entry.archived_at.is_not(None), Entry.is_deleted == False  # noqa: E712
        )
    else:
        query = _list_entries_filter(query, False, False, boards)
    return set(session.scalars(query))


def most_accessed_entries(session: Session, limit: int = 5) -> list[Entry]:
    """Most-used non-deleted, non-archived entries; untouched entries don't
    qualify."""
    return list(
        session.scalars(
            select(Entry)
            .where(
                Entry.is_deleted == False,  # noqa: E712
                Entry.archived_at.is_(None),
                Entry.access_count > 0,
            )
            .order_by(Entry.access_count.desc(), Entry.id.desc())
            .limit(limit)
        )
    )


def list_deleted_entries(
    session: Session, limit: int | None = None, offset: int = 0
) -> list[Entry]:
    """The recycle bin, most recently deleted first."""
    query = select(Entry).where(Entry.is_deleted == True).order_by(  # noqa: E712
        Entry.deleted_at.desc(), Entry.id.desc()
    )
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    return list(session.scalars(query))


def count_deleted_entries(session: Session) -> int:
    return session.scalar(
        select(func.count()).select_from(Entry).where(Entry.is_deleted == True)  # noqa: E712
    ) or 0


def list_archived_entries(
    session: Session, limit: int | None = None, offset: int = 0
) -> list[Entry]:
    """The archive, most recently archived first. Independent of the
    recycle bin: an archived note that's also deleted still belongs to
    the bin, not here (list_entries' own is_deleted filter already keeps
    the two from double-counting in the normal view)."""
    query = select(Entry).where(
        Entry.archived_at.is_not(None), Entry.is_deleted == False  # noqa: E712
    ).order_by(Entry.archived_at.desc(), Entry.id.desc())
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    return list(session.scalars(query))


def count_archived_entries(session: Session) -> int:
    return session.scalar(
        select(func.count())
        .select_from(Entry)
        .where(Entry.archived_at.is_not(None), Entry.is_deleted == False)  # noqa: E712
    ) or 0


def get_entry(session: Session, entry_id: int) -> Entry | None:
    return session.get(Entry, entry_id)


#: **`filing_state` when the AI chose the category and nobody has said
#: otherwise.** The other three values (`done`, `pending`, `failed`) describe
#: how far the *save* got; this one describes who decided, and it is the flag
#: that makes a later move by hand legible as a correction rather than as an
#: ordinary edit. A terminal state like `done` as far as every reader is
#: concerned: the composer's poller stops on anything that is not `pending`.
AUTO_FILED = "auto"
#: Filed by meaning because the model missed the wait; its answer replaces
#: this when it lands, or on the next launch if the app closed first.
STAND_IN = "standin"
#: Filed by the notebook's own words with no model (`ai/lexical_filing.py`,
#: INBOX 434): not the AI's decision, and said so, but like one in that a
#: later move by hand is a correction the next filing learns from.
WORDS_FILED = "words"
#: Filing stopped by hand: nothing files it again unless asked (re-evaluate).
FILING_STOPPED = "stopped"

#: Who moves a note when the auto-filer does (capture's background filing,
#: adding context, re-evaluation). Its own actor rather than the person's, so
#: the History sheet says the AI filed it and `POST /events/undo` can put back
#: exactly the filer's moves. `autonomous.py`'s librarian keeps its own.
FILING_ACTOR = "system:filing"


@events.writes("entry", "filed")
def record_filing(session: Session, entry: Entry, category_name: str, by: str | None = None) -> bool:
    """File a note where the AI decided, as an event the filer owns.

    Returns whether the category changed. No change, no event: a re-evaluation
    that agrees with the current category is not news. The three filing
    paths used to set `category_id` by hand, one with no event at all and two
    with an `edited` event carrying no values and the person's name, so a
    note's History could not rebuild the category it had between capture and
    now, and "undo auto-filing" had nothing to find.
    """
    # The note's own space: the filer runs off the request thread, so the
    # session's space is not the note's (see `category_space`).
    category = get_or_create_category(session, category_name, workspace_id=entry_space(entry))
    if category.id == entry.category_id:
        return False
    before = entry.category_id
    entry.category_id = category.id
    log_action(
        session,
        "filed",
        "entry",
        entry.id,
        # `by` says who decided (owner, 0.3.31: "should notes say which model
        # filed them"): "granite4.1:3b, 82% sure", "meaning (BAAI/...)".
        f"filed under {category_name}" + (f" by {by}" if by else ""),
        payload={"before": {"category_id": before}, "after": {"category_id": category.id}},
        actor=FILING_ACTOR,
    )
    return True


def update_entry(
    session: Session,
    entry: Entry,
    content: str | None = None,
    category_name: str | None = None,
    tags: list[str] | None = None,
) -> Entry:
    """Manual override: the user can change anything the AI decided.

    **A move out of an auto-filed category is a correction, and is recorded as
    one** (Brief 13). See `ai/librarian.corrections_note` for what reads it
    back: the point of the record is that the next filing decision for the
    same category can see it.

    The correction is written *outside* the `edited` write scope, which is
    what this wrapper is for. `events.record` folds anything recorded inside a
    write into that write's own event, correctly, because a category created
    on the way past is part of the one change the user asked for. A correction
    is not: it is a second, separately readable fact about the same moment,
    and folded into the edit it would be invisible to the query that looks for
    it.
    """
    before_category = category_name_for(session, entry)
    was_auto = (getattr(entry, "filing_state", "") or "") in (AUTO_FILED, STAND_IN, WORDS_FILED)
    excerpt = readable_content(entry) or ""
    _update_entry_fields(session, entry, content, category_name, tags)
    after_category = category_name_for(session, entry)
    if was_auto and after_category != before_category:
        entry.filing_state = "done"
        log_action(
            session,
            "correction",
            "entry",
            entry.id,
            f"moved from {before_category} to {after_category}",
            payload={
                "kind": "refile",
                "from": before_category,
                "to": after_category,
                # The note's own words, so a filing prompt can say what kind
                # of note this rule is about. Clipped here rather than at read
                # time: a payload is stored for ever and a whole note in one
                # is a copy of the notebook in the audit log.
                "excerpt": " ".join(excerpt.split())[:200],
            },
        )
        session.commit()
    return entry


@events.writes("entry", "edited")
def _update_entry_fields(
    session: Session,
    entry: Entry,
    content: str | None = None,
    category_name: str | None = None,
    tags: list[str] | None = None,
) -> Entry:
    """The edit itself. One write, one `edited` event; see `update_entry`."""
    from tessellate.entry.properties import lift_title

    was = events.entry_state(entry)
    changed = []
    if content is not None:
        content = lift_title(content)
    if content is not None and entry.is_private:
        #: Whoever the caller is, a private note's text lands encrypted.
        stored = content_for_entry(entry, content)
        if stored is None:
            raise PermissionError("The encryption key isn't loaded.")
        flag_private_media(session, content)
        content = stored
    if content is not None and content != entry.content:
        entry.content = content
        changed.append("content")
    if category_name is not None:
        # In the note's own space, never the view's: from "All spaces" the
        # view is every space at once (see `category_space`).
        category = get_or_create_category(session, category_name, workspace_id=entry_space(entry))
        if category.id != entry.category_id:
            entry.category_id = category.id
            # A manual move means the user decided, the janitor stays
            # out of this entry's filing from now on.
            entry.user_filed = True
            changed.append(f"category={category_name}")
    if tags is not None:
        #: No comma split: background writers (the janitor, a tag suggestion,
        #: undo) pass the note's own tags back, a legacy "work, home" with them.
        entry.tags = json.dumps(normalise_tags(tags, split=False))
        changed.append("tags")
    if changed:
        mark_edited(entry)
    if "content" in changed:
        # The text is what carries the phrases, so a rewrite re-reads them.
        # Resolved against *now*, not the original capture: the user is
        # writing "tomorrow" today.
        record_dates(session, entry)
        reindex_properties(session, entry)
    if changed:
        log_action(
            session,
            "edited",
            "entry",
            entry.id,
            ", ".join(changed),
            payload=events.changed(was, events.entry_state(entry)),
        )
        session.commit()
    return entry


def entry_dates(session: Session, entry: Entry) -> list[EntryDate]:
    """The resolved time phrases for one note, in the order they were written."""
    return list(
        session.scalars(
            select(EntryDate)
            .where(EntryDate.entry_id == entry.id)
            .order_by(EntryDate.id)
        )
    )


def entry_dates_bulk(session: Session, entry_ids: list[int]) -> dict[int, list[EntryDate]]:
    """`entry_dates` for several notes in one query, grouped by note id.

    `list_notes`/`summarize_notes` called `entry_dates` once per row inside
    `_note_summary`, an N+1 hit on the agent's most-used read tools
    (ROADMAP.md Tier 1 item 8). This is the batched form for that path;
    single-note callers (`get_note`, etc.) still use `entry_dates` above.
    """
    if not entry_ids:
        return {}
    out: dict[int, list[EntryDate]] = {}
    for date in session.scalars(
        select(EntryDate)
        .where(EntryDate.entry_id.in_(entry_ids))
        .order_by(EntryDate.id)
    ):
        out.setdefault(date.entry_id, []).append(date)
    return out


#: How each indexed value is read as a number or a date (KG4).
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?$")


def reindex_properties(session: Session, entry: Entry) -> None:
    """Rebuild this note's rows in `EntryProperty` from its text (KG4).

    The text is the truth; this is an index for queries. A private note has
    no rows (its text is encrypted at rest, and a plain table of its values
    would leak them), and a note with no block has none. Best effort, like
    `record_dates`: a note saves whatever happens here.
    """
    from tessellate.entry import properties as note_properties

    try:
        #: "fetch", not the default "auto": auto tries "evaluate" first, which
        #: walks every object the session holds, so an import's second note
        #: cost more than its first (an N-squared 5,000-note write).
        session.execute(
            delete(EntryProperty).where(EntryProperty.entry_id == entry.id).execution_options(synchronize_session="fetch")
        )
        if entry.is_private or entry.is_deleted:
            return
        found, _ = note_properties.split(entry.content or "")
        for key, values in found.items():
            for value in values or [""]:
                number = None
                when = None
                text = str(value)[:300]
                try:
                    number = float(text) if re.fullmatch(r"-?\d+(?:\.\d+)?", text.strip()) else None
                except ValueError:
                    number = None
                if _ISO_DATE.match(text.strip()):
                    try:
                        when = datetime.fromisoformat(text.strip().replace(" ", "T"))
                    except ValueError:
                        when = None
                session.add(EntryProperty(entry_id=entry.id, key=key[:60], value=text, number=number, date=when))
    except Exception:  # noqa: BLE001  # an index must never cost a save
        logging.getLogger("tessellate.properties").warning("couldn't index properties for %s", entry.id, exc_info=True)


@events.writes("entry", "dated")
def record_dates(session: Session, entry: Entry, now: datetime | None = None) -> None:
    """Resolve the relative time phrases in a note and store what they meant.

    Best-effort by design (principle 2): a note must save even if this cannot
    run at all, so every failure here is logged and swallowed. Private notes
    are skipped: their text is encrypted at rest, and lifting phrases out of
    it into a plain table would leak the one thing encryption is for.

    `now` is the day the phrases are read against; the default is today (the
    reader's clock). `entry/redate.py` passes the note's own day.
    """
    try:
        if entry.is_private:
            return
        from tessellate.core.config import user_now

        # `importlib`, not `from tessellate.core import deps`, see
        # `_ensure_tag_cache_reset_registered` below for why this module
        # can't have that import statement anywhere, function-local or not
        # (CodeQL's py/cyclic-import flags the statement itself, not merely
        # module-level ones).
        deps = importlib.import_module("tessellate.core.deps")

        if now is None:
            try:
                now = user_now(deps.get_config())
            except Exception:  # noqa: BLE001  # no app state (a script, a test)
                now = datetime.now()
        #: An imported note's words were written on its own day, not today:
        #: "tomorrow" in a 2024 export is a day in 2024 (CHAT_PLAN section 2,
        #: the import row). `app_import.write` sets that day and calls this
        #: again.
        if entry.source_path and entry.created_at is not None and entry.created_at.date() < now.date():
            now = entry.created_at
        session.execute(delete(EntryDate).where(EntryDate.entry_id == entry.id).execution_options(synchronize_session="fetch"))
        resolved = []
        for mention in timewords.find(entry.content or "", now):
            session.add(
                EntryDate(
                    entry_id=entry.id,
                    phrase=mention.phrase[:60],
                    # A date, or a date and the clock the note said beside it,
                    # both the writer's own wall clock with no zone: a day is
                    # not an instant, and storing one as UTC midnight put
                    # every mention a day early west of UTC (UX-02).
                    at=datetime.combine(mention.at, mention.time or datetime.min.time()),
                    precision=mention.precision,
                )
            )
            resolved.append(
                {
                    "phrase": mention.phrase[:60],
                    "at": mention.at.isoformat(),
                    "time": mention.time.strftime("%H:%M") if mention.time else None,
                    "precision": mention.precision,
                }
            )
        # Recorded even when nothing was found: "this text was read for dates
        # and had none" is the fact that explains an empty date list, and the
        # two are indistinguishable without it. Folded into the note's own
        # event whenever this runs as part of a save or an edit, so it only
        # becomes a row of its own when something calls it directly.
        log_action(
            session,
            "dated",
            "entry",
            entry.id,
            f"{len(resolved)} date(s)",
            payload={"dates": resolved},
        )
        session.flush()
    except Exception:  # noqa: BLE001  # never let this stop a note being saved
        logging.getLogger("tessellate.entries").warning(
            "Couldn't resolve the dates in entry %s", entry.id, exc_info=True
        )


# --- notes ↔ documents -------------------------------------------------------
# A note and a document are different things on purpose, but they are usually
# about the same thing. These are the only four functions that know how they
# are joined, so both sides of the relationship can never drift apart.


@events.writes("document", "linked")
def link_document(session: Session, document_id: int, entry_id: int) -> bool:
    """Attach a note to a document. False if it already was."""
    existing = session.scalar(
        select(DocumentLink).where(
            DocumentLink.document_id == document_id, DocumentLink.entry_id == entry_id
        )
    )
    if existing is not None:
        return False
    session.add(DocumentLink(document_id=document_id, entry_id=entry_id))
    log_action(
        session,
        "linked",
        "document",
        document_id,
        f"note {entry_id}",
        payload={"after": {"document_id": document_id, "entry_id": entry_id}},
    )
    session.commit()
    return True


@events.writes("document", "unlinked")
def unlink_document(session: Session, document_id: int, entry_id: int) -> bool:
    removed = session.execute(
        delete(DocumentLink).where(
            DocumentLink.document_id == document_id, DocumentLink.entry_id == entry_id
        )
    ).rowcount
    if removed:
        log_action(
            session,
            "unlinked",
            "document",
            document_id,
            f"note {entry_id}",
            payload={"before": {"document_id": document_id, "entry_id": entry_id}},
        )
        session.commit()
    return bool(removed)


def documents_for_entry(session: Session, entry: Entry) -> list:
    """The documents this note is attached to, oldest link first."""
    from tessellate.core.database import Document

    return list(
        session.scalars(
            select(Document)
            .join(DocumentLink, DocumentLink.document_id == Document.id)
            .where(DocumentLink.entry_id == entry.id)
            .order_by(DocumentLink.id)
        )
    )


def documents_for_entries_bulk(session: Session, entry_ids: list[int]) -> dict[int, list]:
    """`documents_for_entry` for several notes in one query, grouped by note id.

    Same batched-form pattern as `entry_dates_bulk`, built for `GET /entries`,
    which called `documents_for_entry` once per row via `_to_out` (ROADMAP.md
    #0 priority, item 1). Single-note callers keep using the function above.
    """
    from tessellate.core.database import Document

    if not entry_ids:
        return {}
    out: dict[int, list] = {}
    rows = session.execute(
        select(DocumentLink.entry_id, Document)
        .join(Document, DocumentLink.document_id == Document.id)
        .where(DocumentLink.entry_id.in_(entry_ids))
        .order_by(DocumentLink.id)
    )
    for entry_id, document in rows:
        out.setdefault(entry_id, []).append(document)
    return out


def sealed_stand_ins(session: Session, ids: set[int]) -> dict[int, Entry]:
    """For each of `ids` that lives in a locked private space, a stand-in
    note that says only that (`PRIVATE_SPACE_NOTE`): the request's reads leave
    the note itself out (`sealed_workspaces`), so a link to it would vanish.
    Read on the table, past the space filter, for the id and space alone."""
    sealed = session.info.get("sealed_workspaces")
    if not sealed or not ids:
        return {}
    table = Entry.__table__
    rows = session.execute(
        select(table.c.id, table.c.workspace_id).where(
            table.c.id.in_(ids), table.c.workspace_id.in_(sealed), table.c.is_deleted.is_(False)
        )
    )
    out: dict[int, Entry] = {}
    for row_id, space in rows:
        stand_in = Entry(id=row_id, content="", is_private=True, is_deleted=False, is_board=False, workspace_id=space)
        stand_in.sealed_placeholder = True
        out[row_id] = stand_in
    return out


def _placeholder_link(link: EntryLink) -> EntryLink:
    """A link to a stand-in, without its reason or properties (they speak of
    the sealed note)."""
    return EntryLink(
        id=link.id, source_entry_id=link.source_entry_id, target_entry_id=link.target_entry_id,
        created_at=link.created_at, link_type=link.link_type, origin=link.origin, two_way=link.two_way,
        workspace_id=link.workspace_id,
    )


def _with_stand_ins(session: Session, links: list[EntryLink], found: dict[int, Entry]) -> dict[int, Entry]:
    missing = {end for link in links for end in (link.source_entry_id, link.target_entry_id) if end not in found}
    return {**found, **sealed_stand_ins(session, missing)}


def _shown_link(link: EntryLink, other: Entry) -> EntryLink:
    return _placeholder_link(link) if getattr(other, "sealed_placeholder", False) else link


def links_for_entries_bulk(
    session: Session, entry_ids: list[int]
) -> dict[int, list[tuple[EntryLink, Entry]]]:
    """`links_for_entry` for several notes in one query, grouped by note id.

    Same batched-form pattern as `entry_dates_bulk`, built for `GET /entries`
    (ROADMAP.md #0 priority, item 1), which resolved each link's other-side
    entry with a separate `session.get` per link inside `_to_out`.
    """
    if not entry_ids:
        return {}
    id_set = set(entry_ids)
    links = list(
        session.scalars(
            select(EntryLink).where(
                or_(
                    EntryLink.source_entry_id.in_(id_set),
                    EntryLink.target_entry_id.in_(id_set),
                )
            )
        )
    )
    touched_ids = set()
    for link in links:
        touched_ids.add(link.target_entry_id)
        touched_ids.add(link.source_entry_id)
    entries_by_id = {e.id: e for e in session.scalars(select(Entry).where(Entry.id.in_(touched_ids)))}
    entries_by_id = _with_stand_ins(session, links, entries_by_id)

    out: dict[int, list[tuple[EntryLink, Entry]]] = {}
    for link in links:
        if link.source_entry_id in id_set:
            other = entries_by_id.get(link.target_entry_id)
            if other is not None:
                out.setdefault(link.source_entry_id, []).append((_shown_link(link, other), other))
        if link.target_entry_id in id_set and link.target_entry_id != link.source_entry_id:
            other = entries_by_id.get(link.source_entry_id)
            if other is not None:
                out.setdefault(link.target_entry_id, []).append((_shown_link(link, other), other))
    return out


def links_count_bulk(session: Session, entry_ids: list[int]) -> dict[int, int]:
    """How many notes each of `entry_ids` is linked to: `len` of what
    `links_for_entries_bulk` returns for it, without building the other side.

    The timeline draws a count and nothing else of a link, and the full form
    loads every linked note's whole text to throw it away (3.5 ms of a 20 ms
    page at 100 rows). Two reads of columns only, and the same rule: a link
    counts for each of its ends on the page, once for a note linked to itself,
    and not at all when the note at the other end is not visible here.
    """
    if not entry_ids:
        return {}
    id_set = set(entry_ids)
    pairs = session.execute(
        select(EntryLink.source_entry_id, EntryLink.target_entry_id).where(
            or_(EntryLink.source_entry_id.in_(id_set), EntryLink.target_entry_id.in_(id_set))
        )
    ).all()
    touched = {end for pair in pairs for end in pair}
    visible = set(session.scalars(select(Entry.id).where(Entry.id.in_(touched)))) if touched else set()
    counts: dict[int, int] = {}
    for source, target in pairs:
        if source in id_set and target in visible:
            counts[source] = counts.get(source, 0) + 1
        if target in id_set and target != source and source in visible:
            counts[target] = counts.get(target, 0) + 1
    return counts


def entries_for_document(session: Session, document_id: int) -> list[Entry]:
    """The notes attached to this document. Binned notes drop out on their
    own: a note in the recycle bin should not still be feeding a draft."""
    return list(
        session.scalars(
            select(Entry)
            .join(DocumentLink, DocumentLink.entry_id == Entry.id)
            .where(DocumentLink.document_id == document_id, Entry.is_deleted == False)  # noqa: E712
            .order_by(DocumentLink.id)
        )
    )


@events.writes("entry", "deleted")
def soft_delete_entry(session: Session, entry: Entry) -> None:
    """Into the recycle bin, recoverable until purged. Commits."""
    entry.is_deleted = True
    entry.deleted_at = utcnow()
    log_action(
        session,
        "deleted",
        "entry",
        entry.id,
        payload={
            "before": {"is_deleted": False, "deleted_at": None},
            "after": {"is_deleted": True, "deleted_at": entry.deleted_at.isoformat()},
        },
    )
    session.commit()


@events.writes("entry", "restored")
def restore_entry(session: Session, entry: Entry) -> None:
    """Out of the bin; flushes, never commits (audit 1031 row 2a): the caller
    owns the transaction, as `repo/content.restore` does for every kind."""
    was = entry.deleted_at.isoformat() if entry.deleted_at else None
    entry.is_deleted = False
    entry.deleted_at = None
    log_action(
        session,
        "restored",
        "entry",
        entry.id,
        payload={
            "before": {"is_deleted": True, "deleted_at": was},
            "after": {"is_deleted": False, "deleted_at": None},
        },
    )
    session.flush()


@events.writes("entry", "archived")
def archive_entry(session: Session, entry: Entry) -> None:
    """Out of the way, but never deleted, no auto-clear, no purge."""
    entry.archived_at = utcnow()
    log_action(
        session,
        "archived",
        "entry",
        entry.id,
        payload={
            "before": {"archived_at": None},
            "after": {"archived_at": entry.archived_at.isoformat()},
        },
    )
    session.commit()


@events.writes("entry", "unarchived")
def unarchive_entry(session: Session, entry: Entry) -> None:
    was = entry.archived_at.isoformat() if entry.archived_at else None
    entry.archived_at = None
    log_action(
        session,
        "unarchived",
        "entry",
        entry.id,
        payload={"before": {"archived_at": was}, "after": {"archived_at": None}},
    )
    session.commit()


# How close two notes' embeddings must be, cosine-wise, before a link left
# with no reason gets one deduced for it. The same bar `/entries/link-
# suggestions` ranks by, so a link made from approving a suggestion and a
# link the AI made unprompted read the same way if they're equally close.
AUTO_REASON_THRESHOLD = 0.55
AUTO_REASON_TEXT = "similar in meaning"
AUTO_REASON_TEXT_TEMPORAL = "similar in meaning, and around the same time"
#: How much a shared date pushes a borderline embedding score over
#: AUTO_REASON_THRESHOLD. Asked for directly (ROADMAP.md Tier 2 item 9):
#: two notes both mentioning "next Tuesday", or written the same day, should
#: read as related even when their topics don't overlap semantically enough
#: on their own. Deliberately small and a *rescue*, not a second path to a
#: link: see the `score >= AUTO_REASON_THRESHOLD` early return below, which
#: keeps every pair that already clears the bar on meaning alone exactly as
#: it was (the reason text, the confidence, and every existing test).
TEMPORAL_RESCUE_BOOST = 0.15


def _shares_a_date(session: Session, source_id: int, target_id: int) -> bool:
    """True when the two notes resolve to the same calendar day.

    Two ways in, both day-precision only (a coarser phrase like "last week"
    isn't specific enough to call two notes related on its own): a recorded
    time phrase in both (`EntryDate`, "next Tuesday" in one note and
    "next Tuesday" in another, each resolved against the day it was
    written), or simply being written on the same day, phrase or not.
    """
    dates_by_entry = entry_dates_bulk(session, [source_id, target_id])
    day_sets = {
        entry_id: {d.at.date() for d in dates if d.precision in ("day", "minute")}
        for entry_id, dates in dates_by_entry.items()
    }
    if day_sets.get(source_id, set()) & day_sets.get(target_id, set()):
        return True

    entries = {
        e.id: e
        for e in session.scalars(
            select(Entry).where(Entry.id.in_((source_id, target_id)))
        )
    }
    source, target = entries.get(source_id), entries.get(target_id)
    if source is None or target is None:
        return False
    return source.created_at.date() == target.created_at.date()


def _deduce_reason(
    session: Session, source_id: int, target_id: int
) -> tuple[str | None, float | None]:
    """Guess why two notes might be linked from how close their embeddings
    are, with a shared date as a tie-breaker for a borderline pair. Returns
    `(None, None)`, "no reason", when it can't: no embedding for one or
    both notes, a mid-reindex width mismatch, or a score under
    `AUTO_REASON_THRESHOLD` even after the date check. That's deliberately
    the same pair `reason` already had for "nobody gave one", so a weak
    guess never outranks silence, see `EntryLink.reason_confidence`.

    A private note has no embedding (`set_private` deletes it), so this is
    naturally a no-op for one rather than needing its own guard.

    Deliberately cheap: no model call. This used to also ask the AI for a
    specific reason here, synchronously, which meant `create_link` (and so
    every note-linking request, human or agent) stalled on a chat round-trip.
    Wording a *specific* reason is the background audit's job now
    (`ai.links.audit_vague_links`, driven from `ai.autonomous`): this always
    returns immediately with the embedding score's own verdict, the generic
    `AUTO_REASON_TEXT`, and leaves the wording to be upgraded later without
    the person who made the link ever waiting on it.
    """
    # `importlib`, same reason as `_ensure_tag_cache_reset_registered`'s own
    # `deps` lookup above: a plain `from tessellate.ai.embeddings import ...`
    # is CodeQL py/cyclic-import's other flagged site in this file (Note
    # severity: `tessellate.ai.embeddings` imports back into this module by
    # the same `deps` -> `ai.model_manager` chain), and deferring the import
    # to call time doesn't clear it; only dropping the `import` statement
    # itself does.
    embeddings = importlib.import_module("tessellate.ai.embeddings")

    rows = session.scalars(
        select(EmbeddingRecord).where(EmbeddingRecord.entry_id.in_((source_id, target_id)))
    ).all()
    vectors = {row.entry_id: embeddings.bytes_to_vector(row.embedding) for row in rows}
    if source_id not in vectors or target_id not in vectors:
        return None, None
    if vectors[source_id].shape != vectors[target_id].shape:
        return None, None  # mid embedding-model change, see search.similar_pairs
    score = embeddings.cosine_similarity(vectors[source_id], vectors[target_id])
    #: **What the two notes share, in words, when they share something a
    #: person can check** (INBOX 691): a tag, a name, one naming the other,
    #: the same category in the same week (`link_wording`). The score stays
    #: in `reason_confidence` either way; "similar in meaning" is what is left
    #: when the vectors are all there is.
    if score >= AUTO_REASON_THRESHOLD:
        return link_facts.reason_for(session, source_id, target_id) or AUTO_REASON_TEXT, round(score, 2)
    if score + TEMPORAL_RESCUE_BOOST >= AUTO_REASON_THRESHOLD and _shares_a_date(
        session, source_id, target_id
    ):
        specific = link_facts.reason_for(session, source_id, target_id)
        return specific or AUTO_REASON_TEXT_TEMPORAL, round(score, 2)
    return None, None


def _seal_reason(reason: str | None) -> str | None:
    """A link reason, encrypted for storage, for a link that touches a private
    note. `None` when there is nothing to seal or the vault is closed: a
    private note cannot be written while the vault is locked, and a reason
    that cannot be sealed is dropped rather than stored in the clear.
    """
    from tessellate.core import crypto, vault

    key = vault.key()
    if not reason or key is None:
        return None
    return crypto.encrypt(key, reason)


def _set_stored_reason(session: Session, link: EntryLink, stored: str | None) -> None:
    """Write `entry_links.reason` exactly as given, bypassing the attribute.

    The column decrypts on load (`database.LinkReason`), so the attribute
    holds plaintext whenever the vault is open, and assigning the plaintext
    back would look like "no change" to the ORM and write nothing. A Core
    update puts the real stored string in, and the expire makes the next
    read of the attribute go back through the decrypting load.
    """
    session.execute(update(EntryLink).where(EntryLink.id == link.id).values(reason=stored))
    session.expire(link, ["reason"])


def _seal_props(props: dict | None) -> str | None:
    """`_seal_reason` for link properties: the encrypted JSON of the object,
    or `None` (dropped) when there is nothing to seal or the vault is closed.
    """
    from tessellate.core import crypto, vault

    key = vault.key()
    if not props or key is None:
        return None
    return crypto.encrypt(key, json.dumps(props))


def _set_stored_props(session: Session, link: EntryLink, stored: str | dict | None) -> None:
    """`_set_stored_reason` for `entry_links.props`: a Core update writes the
    stored form as given (ciphertext string, plain object or null) and the
    expire sends the next read back through the decrypting load."""
    session.execute(update(EntryLink).where(EntryLink.id == link.id).values(props=stored))
    session.expire(link, ["props"])


def _touches_private(session: Session, link: EntryLink) -> bool:
    ends = session.scalars(
        select(Entry.is_private).where(
            Entry.id.in_((link.source_entry_id, link.target_entry_id))
        )
    ).all()
    return any(ends)


def _redact_link_audit(session: Session, entry: Entry, key: bytes) -> None:
    """Take a private note's link reasons out of the activity log.

    The "linked" and "relinked" rows spell the reason in `detail` and carry
    it in `payload.after.reason`, both in the clear when the link was made
    before the note went private. The detail loses its parenthesis (the
    reason is the only part that is about the notes' meaning; the ids stay
    so the log still reads), and the payload's copy is encrypted like the
    content next to it.
    """
    from tessellate.core import crypto
    from tessellate.core.database import AuditLog

    own = f"-> entry {entry.id}"
    rows = session.scalars(
        select(AuditLog).where(
            AuditLog.entity_type == "entry",
            AuditLog.action.in_(("linked", "relinked")),
            or_(
                AuditLog.entity_id == entry.id,
                AuditLog.detail.like(f"{own} (%", escape=LIKE_ESCAPE),
            ),
        )
    )
    for row in rows:
        if row.detail and " (" in row.detail:
            row.detail = row.detail.split(" (", 1)[0]
        payload = row.payload
        state = payload.get("after") if isinstance(payload, dict) else None
        text = state.get("reason") if isinstance(state, dict) else None
        if isinstance(text, str) and text and not crypto.is_encrypted(text):
            row.payload = {**payload, "after": {**state, "reason": crypto.encrypt(key, text)}}


@events.writes("entry", "linked")
def create_link(
    session: Session,
    source: Entry,
    target: Entry,
    reason: str | None = None,
    link_type: str | None = None,
    origin: str | None = None,
    reason_confidence: float | None = None,
    props: dict | None = None,
) -> EntryLink | None:
    """Manually connect two entries. Returns None if the link already
    exists (either direction) or the user tried to link an entry to
    itself. Commits on success.

    `reason` is optional free text, "why are these connected?", the thing
    a shared tag or a reply thread says on its own and a link doesn't. Not
    required: most links are still obviously why (two notes about the same
    trip), and forcing an explanation on every one would make linking
    slower for the common case to help the uncommon one. When nobody gives
    one, `_deduce_reason` gets a try instead of leaving the link mute.
    """
    if source.id == target.id:
        return None
    # **A draft cannot be linked to a committed note.** Asked for directly:
    # "draft notes shouldnt be able to connect with actual notes, they need to
    # be separate."
    #
    # Drafts are already excluded from every other view in the app, the
    # sidebar counts, the category lists, the Ask box's retrieval: precisely
    # because an unfinished note is not part of the notebook yet. A link is the
    # one thing that was still crossing that line, and it crossed it in the
    # worst direction: the link outlives the draft's own invisibility, so a
    # committed note quietly grew an edge to something the reader cannot see
    # from anywhere else.
    #
    # Guarded here rather than in the picker because every route in reaches
    # this function: the UI's link button, the AI's linking tool, the
    # auto-linker and the graph, and a rule enforced in one caller is a rule
    # three other callers do not have.
    #
    # Draft-to-draft is allowed, and that is the literal reading of the
    # request: drafts are to be separate *from real notes*, not from each
    # other. Two drafts of the same idea are exactly the pair worth connecting
    # before either is saved. (A link made that way and then half-committed, 
    # one draft saved, the other not, is left alone: it was legitimate when it
    # was made, and deleting a person's link on their behalf because they
    # finished one end of it first is a bigger claim than this rule supports.)
    if bool(source.is_draft) != bool(target.is_draft):
        return None
    existing = session.scalar(
        select(EntryLink).where(
            or_(
                (EntryLink.source_entry_id == source.id)
                & (EntryLink.target_entry_id == target.id),
                (EntryLink.source_entry_id == target.id)
                & (EntryLink.target_entry_id == source.id),
            )
        )
    )
    if existing is not None:
        return None
    reason = (reason or "").strip() or None
    #: A reason the suggestions' signals wrote keeps their confidence (KG9);
    #: a person's own words have none, as before.
    confidence = None if reason is None or reason_confidence is None else max(0.0, min(1.0, reason_confidence))
    if reason is None:
        reason, confidence = _deduce_reason(session, source.id, target.id)
    # A reason is a sentence about the two notes, so on a link with a private
    # end it is stored encrypted and kept out of the activity log's text
    # (`entry_links.reason` decrypts on load, `database.LinkReason`).
    private_link = bool(source.is_private or target.is_private)
    shown_reason = None if private_link else reason
    if private_link:
        reason = _seal_reason(reason)
        stored_props = _seal_props(props)
    else:
        stored_props = dict(props) if props else None
    # An unrecognised kind is stored as null rather than rejected: the column
    # is advisory (it styles an edge and weights a traversal), and refusing an
    # otherwise-valid link because a caller sent a typo would trade a working
    # connection for a validation error nobody asked for.
    kind = link_type if is_link_type(session, link_type) else None
    link = EntryLink(
        source_entry_id=source.id,
        target_entry_id=target.id,
        reason=reason,
        reason_confidence=confidence,
        link_type=kind,
        origin=origin,
        props=stored_props,
        # **The link belongs to the space its notes are in, whoever made it.**
        # A new row usually takes its space from `session.info["workspace_id"]`
        # (the before-flush hook in core/database.py), which is set from the
        # request's `X-Workspace-ID` header. A background pass has no request
        # and no header: `ai/autonomous.py` opens a plain session, so every
        # link the librarian created was written with the column default,
        # "default". Measured: two notes in `space-b`, a link made the way the
        # night shift makes one, and the space that owns both notes could see
        # zero links.
        #
        # Taken from the source note rather than from the session, because
        # that is the fact that is true in both cases: in a request the note
        # is already in the session's space, and in a background pass the note
        # is the only thing that knows.
        workspace_id=source.workspace_id or "default",
    )
    session.add(link)
    session.flush()
    if private_link:
        # The attribute holds the ciphertext just stored; make the next read
        # go back through the decrypting load (`expire_on_commit` is off).
        session.expire(link, ["reason", "props"])
    detail = f"-> entry {target.id}" + (f" ({shown_reason})" if shown_reason else "")
    log_action(
        session,
        "linked",
        "entry",
        source.id,
        detail,
        payload={
            "after": {
                "link_id": link.id,
                "source_entry_id": source.id,
                "target_entry_id": target.id,
                "reason": reason,  # as stored: ciphertext on a private link
                "link_type": link.link_type,
            }
        },
    )
    session.commit()
    return link


def backfill_link_reasons(session: Session) -> dict:
    """Give `_deduce_reason` a try on every existing link that has none.

    Asked directly: *"none of my notes have a linked reason yet, is there
    an easy way to give them all a reason?"* There wasn't one: `_deduce_reason`
    only ever ran at the moment `create_link` made a *new* link, so a
    notebook full of links made before that existed (or made without an
    embedding backend running at the time) stays mute forever with no way to
    revisit it. This is that revisit, run once over every link rather than
    one at a time.

    Same rule as a fresh link: a reason a person already gave is never
    touched, and a link that still can't be deduced (no embedding for one or
    both notes, or a score under the threshold) is left exactly as it was, 
    "no reason" is still the honest answer, not a false one manufactured to
    fill the field.
    """
    reasonless = list(
        session.scalars(select(EntryLink).where(EntryLink.reason.is_(None)))
    )
    updated = 0
    for link in reasonless:
        reason, confidence = _deduce_reason(
            session, link.source_entry_id, link.target_entry_id
        )
        if reason is not None:
            link.reason = reason
            link.reason_confidence = confidence
            updated += 1
    if updated:
        log_action(session, "backfilled", "entry", detail=f"reasons for {updated} link(s)")
        session.commit()
    return {"checked": len(reasonless), "updated": updated}


def remove_link(session: Session, source: Entry, target: Entry) -> bool:
    """Disconnect two entries, whichever way round the link was made.

    Returns False when there was nothing to remove, so a caller can say "those
    aren't linked" rather than reporting a success that changed nothing.

    Direction-agnostic on purpose, matching `create_link`: a link is a
    connection rather than an arrow, and requiring the caller to know which
    note was the source would make removal fail for half of them depending on
    who made the link.
    """
    link = session.scalar(
        select(EntryLink).where(
            or_(
                (EntryLink.source_entry_id == source.id)
                & (EntryLink.target_entry_id == target.id),
                (EntryLink.source_entry_id == target.id)
                & (EntryLink.target_entry_id == source.id),
            )
        )
    )
    if link is None:
        return False
    delete_link(session, link)
    return True


def set_link_reason(session: Session, link: EntryLink, reason: str | None) -> EntryLink:
    """A person setting, changing, or clearing a link's reason by hand.

    Always wins over whatever `_deduce_reason` guessed: `reason_confidence`
    is cleared here because a person's words aren't a similarity score, and
    null already means "not deduced", so an edited link and a freshly
    auto-reasoned one that hasn't been touched stay tellable apart.
    """
    text = (reason or "").strip() or None
    link.reason_confidence = None
    if _touches_private(session, link):
        # Encrypted, and not spelled in the activity log (see `create_link`).
        _set_stored_reason(session, link, _seal_reason(text))
        detail = f"-> entry {link.target_entry_id}"
    else:
        link.reason = text
        detail = f"-> entry {link.target_entry_id}" + (f" ({text})" if text else "")
    log_action(session, "relinked", "entry", link.source_entry_id, detail)
    session.commit()
    return link


def is_link_type(session: Session, key: str | None) -> bool:
    """A built-in or a custom type's key (KG3)."""
    if not key:
        return False
    return key in relation_types.kinds(session)


def relation_label(types: dict[str, dict], link_type: str | None, outgoing: bool) -> str | None:
    """What a link of this type is called from one end: its name from the
    source, its inverse from the target (when it has one). None for an
    untyped link or a type no longer known."""
    kind = types.get(link_type or "")
    if kind is None:
        return None
    if not outgoing and kind["directed"] and kind["inverse"]:
        return kind["inverse"]
    return kind["name"]


def set_link_props(session: Session, link: EntryLink, props: dict | None) -> EntryLink:
    """Replace a link's properties (KG3); an empty object clears them."""
    if _touches_private(session, link):
        _set_stored_props(session, link, _seal_props(props))
    else:
        _set_stored_props(session, link, dict(props) if props else None)
    log_action(session, "relinked", "entry", link.source_entry_id, f"-> entry {link.target_entry_id} (properties)")
    session.commit()
    return link


def set_link_two_way(session: Session, link: EntryLink, two_way: bool | None) -> EntryLink:
    """Make a link run both ways or one way (INBOX 693), or null to let its
    type decide again (`is_two_way_link`)."""
    link.two_way = two_way
    log_action(
        session,
        "relinked",
        "entry",
        link.source_entry_id,
        f"-> entry {link.target_entry_id} ({'two-way' if two_way else 'one-way' if two_way is False else 'direction by type'})",
    )
    session.commit()
    return link


def is_two_way_link(link_two_way: bool | None, link_type: str | None, types: dict[str, dict]) -> bool:
    """Whether a link is drawn with no arrow: its own choice when it has
    one, else its type's (a type with no inverse has no direction), else one
    way (INBOX 693)."""
    if link_two_way is not None:
        return bool(link_two_way)
    kind = types.get(link_type or "")
    return bool(kind) and not kind["directed"]


def set_link_type(session: Session, link: EntryLink, link_type: str | None) -> EntryLink:
    """Give a link a kind, built-in or custom (KG3), or none (GRAPH_PLAN KG9:
    the inbox's type suggestions, and the link menu's Type). The caller has
    checked the key; an unknown one here is a bug, so it raises."""
    if link_type is not None and not is_link_type(session, link_type):
        raise ValueError(f"unknown link type {link_type!r}")
    before = link.link_type
    link.link_type = link_type
    log_action(
        session,
        "relinked",
        "entry",
        link.source_entry_id,
        f"-> entry {link.target_entry_id} ({link_type or 'untyped'})",
        payload={"before": {"link_type": before}, "after": {"link_id": link.id, "link_type": link_type}},
    )
    session.commit()
    return link


def apply_audited_reason(link: EntryLink, reason: str) -> None:
    """Set a link's reason from the background audit, field mutation only,
    no commit, no audit-log row.

    `set_link_reason` is right for a person editing one link: they did one
    thing, so one commit and one "relinked" row is an honest record. The
    background audit (`ai.links.audit_vague_links`) is the opposite shape, 
    up to a `limit` of links rewritten in one pass, and calling
    `set_link_reason` per link there was the bug: a 500-link backfill did 500
    commits and left 500 near-identical "relinked" rows in the user's
    activity log, drowning out the log entries a person actually made. This
    just sets the fields; the caller commits once for the whole batch and
    writes one summary log row.

    Same field-level meaning as `set_link_reason`: `reason_confidence` is
    cleared because a reason the AI wrote out in words is no longer a guess
    from embedding similarity: see `EntryLink.reason_confidence`.
    """
    link.reason = (reason or "").strip() or None
    link.reason_confidence = None


def delete_link(session: Session, link: EntryLink) -> None:
    log_action(
        session,
        "unlinked",
        "entry",
        link.source_entry_id,
        f"-> entry {link.target_entry_id}",
    )
    session.delete(link)
    session.commit()


def links_for_entry(session: Session, entry: Entry) -> list[tuple[EntryLink, Entry]]:
    """All links touching this entry, with the entry on the other end."""
    links = session.scalars(
        select(EntryLink).where(
            or_(
                EntryLink.source_entry_id == entry.id,
                EntryLink.target_entry_id == entry.id,
            )
        )
    )
    result = []
    pending = []
    for link in links:
        other_id = (
            link.target_entry_id
            if link.source_entry_id == entry.id
            else link.source_entry_id
        )
        other = session.get(Entry, other_id)
        if other is not None:
            result.append((link, other))
        else:
            pending.append((link, other_id))
    stand_ins = sealed_stand_ins(session, {other_id for _link, other_id in pending})
    result += [(_placeholder_link(link), stand_ins[other_id]) for link, other_id in pending if other_id in stand_ins]
    return result


def category_name_for(session: Session, entry: Entry) -> str:
    """Resolve an entry's category name (entries always have one)."""
    if entry.category_id is None:
        return UNCATEGORISED
    category = session.get(Category, entry.category_id)
    return category.name if category else UNCATEGORISED


def bulk_category_names(session: Session, entries: list[Entry]) -> dict[int | None, str]:
    """Resolve category names for multiple entries efficiently in a single query."""
    ids = {e.category_id for e in entries if e.category_id is not None}
    if not ids:
        return {None: UNCATEGORISED}
    rows = session.scalars(select(Category).where(Category.id.in_(ids)))
    mapping = {c.id: c.name for c in rows}
    mapping[None] = UNCATEGORISED
    return mapping


def tags_from_json(tags_json: str | None) -> list[str]:
    """Parse a tags JSON string directly without an Entry object."""
    if not tags_json:
        return []
    try:
        loaded = json.loads(tags_json)
        return loaded if isinstance(loaded, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def entry_tags(entry: Entry) -> list[str]:
    """Tags are stored as a JSON string; hand callers a real list."""
    return tags_from_json(entry.tags)


def note_is_sealed(is_private: object) -> bool:
    """True when a private note's words must stay hidden right now: the note
    is private and the vault is locked. The one vault gate for the read
    surfaces that are not the note's text (tags, previews, word counts,
    export, history; INBOX 1437), so each asks here instead of re-deriving it."""
    from tessellate.core import vault

    return bool(is_private) and vault.key() is None


def shown_tags(entry: Entry) -> list[str]:
    """`entry_tags` for a response: a private note's tags are as private as
    its text, so none while the vault is locked. Writers keep `entry_tags`,
    which must see the stored list (a locked rename must not drop them)."""
    return [] if note_is_sealed(getattr(entry, "is_private", False)) else tags_from_json(entry.tags)


# --- category management (rename / delete) -----------------------------------


def all_categories(session: Session) -> list[dict]:
    """Every category with how many live entries sit in it, biggest first.

    The number is the Notes list's own under that category, so it counts
    exactly what the list shows: not binned, not archived, not a draft (the
    list keeps drafts in their own view), not a board. It used to exclude
    only the bin, and two numbers for one category disagreed on screen:
    Health 4 in the sidebar and 5 in Manage categories with one archived
    note, Work 5 and 6 with one draft (measured 2026-10-03). The where-clause
    is `_list_entries_filter`'s, the same one `GET /entries` uses, so the two
    cannot drift apart again by one of them gaining a filter.
    """
    rows = list(session.scalars(select(Category).order_by(Category.name)))
    query = note_filter(select(Entry.category_id, func.count(Entry.id)), include_archived=False)
    counts = {
        category_id: total
        for category_id, total in session.execute(query.group_by(Entry.category_id))
    }
    out = [
        {"id": c.id, "name": c.name, "count": counts.get(c.id, 0), "colour": c.colour}
        for c in rows
    ]
    out.sort(key=lambda c: (-c["count"], c["name"].lower()))
    return out


# **A category's name is part of what its notes embed, so renaming one makes
# every vector under it stale.**
#
# `ai/embeddings.embedding_text` folds the category name and the note's tags
# into the embedded text, that change is itself the fix for a reported
# problem ("I have a whole category called hobbies but basically none came up
# in the semantic search"). The consequence nobody wired up: rename "Games"
# to "Hobbies", or merge it into an existing "Hobbies", and every note that
# moved still has a vector built from the *old* name. Semantic search then
# keeps missing exactly the notes the user just tidied, which is the same
# symptom again, produced by the fix for it.
#
# The vectors are dropped rather than recomputed here. Re-embedding is a model
# call per note and this runs inside a rename the user is waiting on; dropping
# is instant, and the search path already treats a missing vector as "fall
# back to keywords for this note" rather than as an error. They are rebuilt by
# the next re-index (`POST /models/reindex`, or the periodic backfill), so the
# worst case is keyword-quality results for those notes until then, instead of
# semantic results that are quietly wrong.
def _restale_category_vectors(session: Session, category_id: int) -> int:
    """Drop the embeddings of every note in a category whose name just
    changed. Returns how many were dropped."""
    entry_ids = [
        row[0]
        for row in session.execute(
            select(Entry.id).where(Entry.category_id == category_id)
        ).all()
    ]
    if not entry_ids:
        return 0
    dropped = (
        session.query(EmbeddingRecord)
        .filter(EmbeddingRecord.entry_id.in_(entry_ids))
        .delete(synchronize_session=False)
    )
    session.commit()
    return int(dropped or 0)


def rename_category(session: Session, category_id: int, new_name: str) -> dict:
    """Rename a category; renaming onto an existing name merges the two.

    Merging is the useful behaviour rather than an error, "Work" and "work"
    turning up as separate categories is exactly the mess this is here to fix.
    """
    category = session.get(Category, category_id)
    if category is None:
        raise ValueError("That category no longer exists.")
    if is_blank(new_name):
        raise ValueError("A category needs a name.")
    new_name = category_label(new_name)
    if new_name == category.name:
        return {"renamed": False, "merged": False, "moved": 0}

    # Only a same-named category in *this one's own space* is a merge. By
    # name alone, renaming uni's "Lectures" to "Garden" from the "All spaces"
    # view merged it into the default space's "Garden" and both uni notes
    # then read as Uncategorised in uni (measured 2026-10-03). In another
    # space the name is simply free, so this is a plain rename.
    wanted = name_key(new_name)
    existing = next(
        (
            other
            for other in session.scalars(
                select(Category)
                .where(
                    Category.workspace_id == category_space(session, category.workspace_id),
                    Category.id != category.id,
                )
                .order_by(Category.id)
            )
            if name_key(other.name) == wanted
        ),
        None,
    )
    if existing is not None:
        # Merge: move the entries across, then drop the now-empty category.
        moved = _reassign(session, category.id, existing.id)
        log_action(session, "edited", "category", existing.id, f"merged {category.name} → {new_name}")
        session.delete(category)
        session.commit()
        _restale_category_vectors(session, existing.id)
        return {"renamed": True, "merged": True, "moved": moved}

    old = category.name
    category.name = new_name
    log_action(session, "edited", "category", category.id, f"{old} → {new_name}")
    session.commit()
    _restale_category_vectors(session, category.id)
    return {"renamed": True, "merged": False, "moved": 0}


def delete_category(session: Session, category_id: int) -> dict:
    """Remove a category. Its notes are kept and become Uncategorised.

    Deleting a category must never delete notes, that would make an organising
    action destructive, which is never what anyone means by "delete category".
    """
    category = session.get(Category, category_id)
    if category is None:
        raise ValueError("That category no longer exists.")
    if category.name == UNCATEGORISED:
        raise ValueError("Uncategorised is where notes go, so it can't be removed.")

    # The deleted category's own Uncategorised, not the view's: a note must
    # stay filed in a category its own space can list.
    fallback = get_or_create_category(
        session, UNCATEGORISED, workspace_id=category_space(session, category.workspace_id)
    )
    moved = _reassign(session, category.id, fallback.id)
    log_action(session, "deleted", "category", category.id, category.name)
    session.delete(category)
    session.commit()
    return {"deleted": True, "moved": moved}


def _reassign(session: Session, from_id: int, to_id: int) -> int:
    """Point every entry in one category at another. Returns how many moved."""
    entries = list(session.scalars(select(Entry).where(Entry.category_id == from_id)))
    for entry in entries:
        entry.category_id = to_id
    return len(entries)


# --- where a note's words came from (SEC-02) ----------------------------------


def came_from_outside(entry: Entry) -> bool:
    """Whether this note's text was written by somebody other than the person:
    clipped from a web page (`source_url`), brought in by an import
    (`source_path`, set by the folder, markdown and document importers), or
    an email pasted in by hand (`holds_pasted_mail`).

    The agent's injection guard reads this (audit 2026-10-05, SEC-02): a page
    clipped into a note and read back later is the same untrusted text a web
    search returns, so it taints the turn the same way. Derived from columns
    every clipped and imported note already has, so no row needs migrating.
    """
    if getattr(entry, "source_url", None) or getattr(entry, "source_path", None):
        return True
    return not getattr(entry, "is_private", False) and holds_pasted_mail(getattr(entry, "content", None) or "")


#: A pasted email is somebody else's words in the person's note, with no
#: `source_url` to say so (audit 1028 E42): a reply's "On ... wrote:" line, a
#: forwarded or original message rule, or a "From:" header beside a "Sent:",
#: "Subject:", "Date:" or "Cc:" one. "From: 10am / To: 11am" in a meeting
#: note is not mail. Line-anchored with bounded runs, so the scan stays linear.
_MAIL_RULE = re.compile(
    r"^-{3,} ?(?:forwarded message|original message) ?-{3,}[ \t]*$|^on [^\n]{4,200} wrote:[ \t]*$", re.I | re.M
)
_MAIL_HEADER = re.compile(r"^(from|sent|to|cc|subject|date|reply-to):[ \t]*\S", re.I | re.M)
_MAIL_SCAN = 20_000


def holds_pasted_mail(content: str) -> bool:
    """Whether a note's text carries a pasted email (`_MAIL_RULE` says how)."""
    head = content[:_MAIL_SCAN]
    if _MAIL_RULE.search(head):
        return True
    names = {m.group(1).lower() for m in _MAIL_HEADER.finditer(head)}
    return "from" in names and bool(names & {"sent", "subject", "date", "cc"})


def document_came_from_outside(session: Session, document_id: int) -> bool:
    """A document made by importing a file (the "imported" event its import
    logged), as opposed to one written here. Events are never deleted
    (`events.compact` strips payloads, not rows), so the answer lasts."""
    from tessellate.core.database import AuditLog

    return (
        session.scalar(
            select(AuditLog.id)
            .where(
                AuditLog.entity_type == "document",
                AuditLog.entity_id == document_id,
                AuditLog.action == "imported",
            )
            .limit(1)
        )
        is not None
    )


# --- private notes -----------------------------------------------------------
# Encryption lives behind these two helpers so every read and write goes
# through the same place. Scattering encrypt/decrypt calls across the routes is
# how a path gets missed and a note is stored in the clear.


def readable_content(entry: Entry) -> str:
    """The note's text, decrypting it if it's private and the vault is open.

    A locked vault returns a placeholder rather than raising: a private note
    must not break the notes list, the graph, or an export for everything else.
    """
    from tessellate.core import crypto, vault

    if not crypto.is_encrypted(entry.content):
        return entry.content
    key = vault.key()
    if key is None:
        return "Private note: unlock to read it."
    try:
        return crypto.decrypt(key, entry.content)
    except crypto.DecryptionError:
        # Kept deliberately non-fatal. The stored bytes are still there, so a
        # key problem is recoverable; crashing the list is not.
        return "This private note couldn't be decrypted."


def _heading_text(stripped: str) -> str | None:
    r"""The text of a leading Markdown heading (1-6 `#`, then a required
    space/tab, then the title), a `#` three paragraphs into a long note is
    a section break, not what the note is *called*, so this only ever looks
    at one already-stripped line. Requires the space after the hashes, so
    "#recipe" (a tag someone typed at the very top) is never mistaken for a
    heading.

    Hand-rolled instead of a `^#{1,6}[ \t]+(\S.*)$` regex: CodeQL flagged
    that shape as a polynomial-ReDoS risk on note content, which is as
    uncontrolled as input gets in this app. This scan is a single linear
    pass with no backtracking.
    """
    n = 0
    while n < len(stripped) and n < 6 and stripped[n] == "#":
        n += 1
    if n == 0 or n >= len(stripped) or stripped[n] not in " \t":
        return None
    text = stripped[n:].lstrip(" \t")
    if not text or text[0].isspace():
        return None
    return text


def _md_links(text: str, image: bool) -> str:
    """`![alt](src)` removed, or `[text](src)` reduced to its text.

    What `!\\[[^\\]]*\\]\\([^)]*\\)` and `\\[([^\\]]*)\\]\\([^)]*\\)` did, with
    the same answers, but linear: those scanned to the end of the line from
    every unclosed `[`, so a first line of `[[[[...` (a note's own text, a
    paste) took 0.3 to 0.8 s at 20 KB (final scan, 2026-10-06). The next `]`
    and the next `)` are looked up through `Ahead`, which remembers its last
    hit, so each is found once per stretch rather than once per `[`.
    """
    opener = "![" if image else "["
    size = len(text)
    close, paren = Ahead(text, r"\]"), Ahead(text, r"\)")
    out: list[str] = []
    done = scan = 0
    while True:
        start = text.find(opener, scan)
        if start < 0:
            break
        mid = close.first(start + len(opener))
        if text.startswith("](", mid):
            end = paren.first(mid + 2)
            if end < size:
                out.append(text[done:start])
                if not image:
                    out.append(text[start + 1 : mid])
                done = scan = end + 1
                continue
        scan = start + 1
    out.append(text[done:])
    return "".join(out)


def plain_label(content: str, limit: int = 80) -> str:
    """A note's first line as a *person* would read it, for a chip or a card.

    Reported directly: "the used in note links dont render inline md", a
    usage chip in the Library's file gallery read
    `# Leafeon Pokemon image test ![WallpaperEngineOv…`, because the label was
    the raw first line of markdown. A chip is one line of plain text in a
    pill; it cannot render markdown and should not try, so the markup is
    removed rather than displayed.

    Deliberately small and regex-only: this is a label, not a document render.
    Images lose their alt text entirely (an image is not what the note *says*),
    links keep their text, and the usual inline emphasis/code markers go.
    """
    from tessellate.entry.properties import strip as strip_properties

    #: KG4: a note opening with properties is named by what follows them.
    text = strip_properties(content or "").strip()
    if not text:
        return ""
    first = ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        first = stripped
        break
    first = re.sub(r"^#{1,6}\s*", "", first)          # heading markers
    first = re.sub(r"^[-*+]\s+|^>\s*", "", first)     # list bullet / quote
    first = _md_links(first, image=True)               # images, alt and all
    #: **Before the markdown link rule, because that one cannot see this.**
    #: `[text](url)` needs the `(url)` to match, so `[[a wiki link]]` fell
    #: straight through it and every chip for a note whose first line links
    #: to another note read `[[The roof quote]]`, brackets and all. Found
    #: while building the references row (INBOX 246), where four of the five
    #: source labels were wiki links and every one of them showed its
    #: brackets. Same rule as the markdown link below: the link keeps its
    #: text, because the text is what the note says.
    first = wiki_plain(first)
    first = _md_links(first, image=False)              # links keep their text
    first = re.sub(r"[*_`~]{1,3}", "", first)          # emphasis, code, strike
    first = re.sub(r"\s+", " ", first).strip()
    return first[:limit]


def extract_title(content: str) -> str | None:
    """A note's own title, if it wrote one, its first line, when that line
    is a Markdown heading. Not a stored field: there is nothing to fall out
    of sync with the content, and "editing the title" is just editing that
    line, the same as any other (asked for directly, and simpler than a
    second input box fighting the single-box capture flow this app is built
    around).
    """
    from tessellate.entry.properties import strip as strip_properties

    for line in strip_bidi(strip_properties(content or "")).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        text = _heading_text(stripped)
        return text.strip() if text else None
    return None


def _first_content_line(content: str) -> int | None:
    """Index of the first non-blank line, or None if there isn't one."""
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.strip():
            return i
    return None


def _split_block(content: str) -> tuple[str, str]:
    """`(properties block, body)`: a title lives in the body, never in the
    block (KG4), so editing one must leave the block where it is."""
    from tessellate.entry.properties import block_end

    end = block_end(content or "")
    return (content or "")[:end], (content or "")[end:]


def apply_title(content: str, title: str) -> str:
    """Set (or replace) a note's title: its first line, as a heading.
    Prepends a new heading line if the note doesn't have one yet; replaces
    the existing one otherwise, so generating a title for a note that
    already has one swaps it rather than stacking two. A note that opens
    with properties gets its heading after them."""
    block, body = _split_block(content or "")
    lines = body.splitlines()
    i = _first_content_line(body)
    heading = f"# {title}"
    if i is not None and _heading_text(lines[i].strip()) is not None:
        lines[i] = heading
        return block + "\n".join(lines)
    return block + (heading if not body else f"{heading}\n{body}")


def remove_title(content: str) -> str:
    """Take a note's title back out, asked for directly, it's just the
    leading heading line, so removing it is removing that line (and one
    blank line right after it, so the body doesn't start with a gap). A
    note with no title is returned unchanged; properties stay as written.
    """
    block, body = _split_block(content or "")
    lines = body.splitlines()
    i = _first_content_line(body)
    if i is None or _heading_text(lines[i].strip()) is None:
        return content
    del lines[i]
    if i < len(lines) and not lines[i].strip():
        del lines[i]
    return block + "\n".join(lines)


#: Inline markdown markers, matched with their content so stripping keeps
#: the words. An image or link becomes its alt/link text, the URL is never
#: captured, only whichever group actually matched ("first non-None group
#: wins", same trick every alternative here relies on). Originally lived
#: only in routes_graph.py (graph node labels); routes_library.py's Library
#: title/preview needed the identical fix, an image-only note (a sketch,
#: most often, but any note whose whole content is a pasted image works the
#: same way) read as literal `![sketch](/media/...)` there too, one surface
#: at a time, until this was factored out to stop that from happening a
#: third time somewhere else.
_INLINE_MD = re.compile(
    r"\*\*([^*\n]{1,500})\*\*|\*([^*\n]{1,500})\*|__([^_\n]{1,500})__"
    r"|_([^_\n]{1,500})_|~~([^~\n]{1,500})~~|`([^`\n]{1,500})`"
    r"|!\[([^\]\n]{0,200})\]\((?:[^)\n]{1,500})\)"
    r"|\[([^\]\n]{1,200})\]\((?:[^)\n]{1,500})\)"
    # A board text run, `{{size=24 ink=red|words}}` (notes-list.js `MD_RUN`).
    r"|\{\{(?:(?:size|font|ink|hl)=[a-z0-9]{1,12} ?){1,4}\|([^}\n]{1,500})\}\}"
)


#: A line that starts a block of its own: a heading, a list item, a quote, a
#: table row.
_BLOCK_LINE = re.compile(r"^(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|>|\|)")
#: A block that already ends its sentence needs no separator after it.
_BLOCK_ENDED = re.compile(r"[.!?:;,…·)\]\"'”’]$")


def join_blocks(text: str, strip=lambda line: line, limit: int | None = None) -> str:
    """A note's or document's lines as one line of prose, its blocks kept apart.

    INBOX 464: a preview that joins every line with a space reads a heading
    and the list under it as one run-on sentence, "Goals Ship the notebook
    redesign Cut travel spend by 15% Risks The hiring freeze...". A boundary
    between blocks (a heading, a list item, a quote, or a blank line) whose
    first half ends without a stop gets the app's dot separator, the one the
    facts lines use; a block that ends its own sentence is followed by a
    space. Lines inside one paragraph (hard-wrapped prose) are joined with a
    space, so an imported file wrapped at 80 columns does not grow dots in
    the middle of its sentences. `strip` cleans one line (its markers) after
    its kind is read; `limit` stops reading once that many characters are
    in, so a long document is not walked to its end for a 240-char preview.
    """
    out: list[str] = []
    size = 0
    gap = prev_block = False
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            gap = True
            continue
        block = bool(_BLOCK_LINE.match(line))
        line = strip(line).strip()
        if not line:
            continue
        if out:
            boundary = gap or block or prev_block
            out.append(" · " if boundary and not _BLOCK_ENDED.search(out[-1]) else " ")
        out.append(line)
        size += len(line)
        gap, prev_block = False, block
        if limit is not None and size > limit:
            break
    return "".join(out)


#: A picture's `|` options in its alt (`![A river|300|right](url)`): a width in
#: pixels (or `300x200`) and left, centre or right. Not words.
_IMAGE_OPTION = re.compile(r"\d{1,4}(?:x\d{1,4})?|left|centre|center|right", re.IGNORECASE)
_IMAGE_ALT_GROUP = 7  # the `!\[(...)\]` group of _INLINE_MD


def _picture_words(alt: str) -> str:
    """A picture's alt as the words it says: the caption written after its
    options when there is one, else its name (image-layout.js
    `imageOptionsFromAlt`, so the preview and the picture agree)."""
    name, *rest = alt.split("|")
    caption = [p.strip() for p in rest if p.strip() and not _IMAGE_OPTION.fullmatch(p.strip())]
    return " ".join(caption) or name.strip()


#: `![[Title]]`: a diagram written into a document (documents-mermaid.js). Not a block embed (`#^id`) and not a file (`.png`).
_EMBED = re.compile(r"!\[\[[ \t]*([^\]\n|#]{1,300}?)[ \t]*\]\]")


def readable_embeds(text: str) -> str:
    """A diagram embed as words for a preview: `Diagram: Trip map`, or the title alone when it starts with Diagram
    (dgbt-1109 12: the Library printed "!Diagram 2026-11-09 19:11"). An image embed is left alone."""

    def label(m: re.Match) -> str:
        title = m.group(1)
        if re.search(r"\.\w{2,5}$", title):
            return m.group(0)
        return title if title.lower().startswith("diagram") else f"Diagram: {title}"

    return _EMBED.sub(label, text)


def strip_inline_markdown(text: str) -> str:
    """A note's text as plain words: bold/italic/strike/code markers gone,
    an image or link reduced to its alt/link text (a picture's width and
    alignment dropped). Markers only: block structure (headings,
    blockquotes, wiki-links) is each caller's own concern, since callers
    disagree on what to do with those."""
    return _INLINE_MD.sub(
        lambda m: _picture_words(m.group(m.lastindex))
        if m.lastindex == _IMAGE_ALT_GROUP
        else next(g for g in m.groups() if g is not None),
        text,
    )


def content_for_entry(entry: Entry, text: str) -> str | None:
    """`text` (from a past version) in the form this note stores its text in
    now: ciphertext when it is private, plain when it is not. None when that
    needs the vault and it is locked. A version written while the note was in
    the other state would otherwise put ciphertext in a note anyone reads, or
    plain text in a private one."""
    from tessellate.core import crypto, vault

    if bool(entry.is_private) == crypto.is_encrypted(text):
        return text
    key = vault.key()
    if key is None:
        return None
    return crypto.encrypt(key, text) if entry.is_private else crypto.decrypt(key, text)


def flag_private_media(session: Session, text: str) -> None:
    """Mark the uploads a private note's readable text embeds (SEC-A2), so a
    locked session can tell them from plain orphans (`MediaUpload.in_private_note`)."""
    names = importlib.import_module("tessellate.core.media_gc").referenced_names(text or "")
    if names:
        session.execute(
            update(MediaUpload).where(MediaUpload.filename.in_(names)).values(in_private_note=True)
        )


WIKI_LINK = re.compile(r"\[\[([^\[\]]{1,120})\]\]")


def wiki_target(inner: str) -> str:
    """The note a `[[Target|Shown]]` names: the part before the first `|`.

    The part after the bar is only what is drawn. One definition, because
    several readers (`sync_wiki_links`, a document's backlinks, a note's
    references row) each used to decide for themselves and gave different
    answers for the same text.
    """
    return (inner or "").split("|", 1)[0].strip()


def wiki_shown(inner: str) -> str:
    """The words a `[[Target|Shown]]` draws: the part after the bar, else the target."""
    target, bar, shown = (inner or "").partition("|")
    return (shown.strip() if bar else "") or target.strip()


#: Bidi embedding, override and isolate controls: they reorder what follows on
#: screen, so a label could read differently from the note (audit 1029 N20).
_BIDI_CONTROLS = re.compile("[\u202a-\u202e\u2066-\u2069]")


def strip_bidi(text: str) -> str:
    """`text` without bidi controls, for anything shown as a label."""
    return _BIDI_CONTROLS.sub("", text or "")


def wiki_plain(text: str) -> str:
    """Some text with each `[[link]]` replaced by the words it draws, bidi
    controls dropped (it builds previews)."""
    return WIKI_LINK.sub(lambda match: wiki_shown(match.group(1)), strip_bidi(text))


def wiki_link_targets(content: str) -> list[str]:
    """The [[names]] mentioned in some text, de-duplicated, in order.

    A `[[Target|Shown]]` is named by its target, so `[[bread]]` and
    `[[Bread|loaf]]` are one name.
    """
    seen = {}
    for match in WIKI_LINK.finditer(content or ""):
        name = wiki_target(match.group(1))
        if name:
            seen.setdefault(name.lower(), name)
    return list(seen.values())


def find_by_wiki_name(session: Session, name: str) -> Entry | None:
    """The note a [[name]] refers to, or None.

    Matched against the start of the note, because a note has no title, its
    opening words are what a person would call it. An exact opening beats a
    partial one, and among equals the oldest wins so a link doesn't silently
    change meaning when a newer note happens to start the same way.
    """
    wanted = wiki_target(name).lower()
    if not wanted:
        return None
    #: **A vault's links name the file, not the first words.** An imported
    #: note carries the path it came from (`Entry.source_path`), and Obsidian
    #: writes `[[Roadmap]]` for `Projects/Roadmap.md`, so without this an
    #: imported vault resolves almost none of its own links, since the note's
    #: text starts with the heading the importer wrote, not with the name.
    #: Tried first and matched exactly: a file called "Index" should not lose
    #: to a note that merely opens with the word "index".
    #: Filtered in SQL rather than by loading every imported note: this runs
    #: once per `[[link]]` per save, and a real vault is thousands of files.
    #: The `LIKE` can over-match (`Roadmap.md` also matches `My Roadmap.md`),
    #: so the stem is checked exactly in Python below: the query narrows, it
    #: does not decide. A name containing `%` used to over-match far wider
    #: than that, matching any path at all; `like_escape` ends that, and the
    #: `escape=` beside it is what makes the escaped pattern mean anything.
    vault_clauses = []
    for suffix in (".md", ".markdown"):
        stem = like_escape(wanted)
        vault_clauses.append(Entry.source_path.ilike(f"{stem}{suffix}", escape=LIKE_ESCAPE))
        vault_clauses.append(Entry.source_path.ilike(f"%/{stem}{suffix}", escape=LIKE_ESCAPE))
    vault = session.scalars(
        select(Entry)
        .where(
            Entry.is_deleted == False,  # noqa: E712
            Entry.is_private == False,  # noqa: E712
            or_(*vault_clauses),
        )
        .order_by(Entry.id)
    ).all()
    for entry in vault:
        stem = (entry.source_path or "").rsplit("/", 1)[-1].lower()
        if stem.removesuffix(".md").removesuffix(".markdown") == wanted:
            return entry
    #: **A note that opens with a heading is named by the heading** (INBOX
    #: 517). Most notes start `# Name`, and matching the raw text against
    #: `name%` never saw past the `#`, so `[[Name]]` linked to nothing. The
    #: SQL narrows (raw start, or a heading marker then the name); the
    #: opening line with its marker stripped decides.
    escaped = like_escape(wanted)
    candidates = session.scalars(
        select(Entry)
        .where(
            Entry.is_deleted == False,  # noqa: E712
            Entry.is_private == False,  # noqa: E712
            or_(
                Entry.content.ilike(f"{escaped}%", escape=LIKE_ESCAPE),
                Entry.content.ilike(f"#% {escaped}%", escape=LIKE_ESCAPE),
                # KG4: a note opening with properties; the name is after them.
                Entry.content.ilike(f"---%{escaped}%", escape=LIKE_ESCAPE),
            ),
        )
        .order_by(Entry.id)
    ).all()
    candidates = [e for e in candidates if wiki_opening(e.content).startswith(wanted)]
    if not candidates:
        return None
    for entry in candidates:
        if wiki_opening(entry.content) == wanted:
            return entry  # its name, exactly: the whole opening line
    return candidates[0]


_HEADING_MARK = re.compile(r"^\s{0,3}#{1,6}\s+")


def wiki_opening(content: str | None) -> str:
    """A note's name for [[links]]: its first line, heading marker stripped
    (after its properties block, KG4)."""
    from tessellate.entry.properties import strip as strip_properties

    first = strip_properties(content or "").strip().split("\n", 1)[0]
    return _HEADING_MARK.sub("", first).strip().lower()


def resolve_links_to(session: Session, entry: Entry) -> int:
    """Link the notes that already wrote `[[this note's name]]` (INBOX 517).

    A link is often written before the note it names; `sync_wiki_links` runs
    only on the note that holds the link, so without this such a link stayed
    unresolved until that other note happened to be saved again.
    """
    name = wiki_opening(entry.content)
    if not name or len(name) > 120:
        return 0
    holders = session.scalars(
        select(Entry).where(
            Entry.is_deleted == False,  # noqa: E712
            Entry.id != entry.id,
            Entry.content.ilike(f"%[[{like_escape(name)}]]%", escape=LIKE_ESCAPE),
        )
    ).all()
    made = 0
    for holder in holders:
        if find_by_wiki_name(session, name) is entry and create_link(session, holder, entry, origin="wiki"):
            made += 1
    return made


def sync_wiki_links(session: Session, entry: Entry) -> list[str]:
    """Create links for the [[names]] in this note. Returns the unresolved ones.

    A [[name]] that matches nothing is left alone rather than reported as an
    error, you often write the link before the note it points at, and having
    that fail the save would be worse than useless.

    **And takes away the ones whose name left the text** (GRAPH_PLAN 518): a
    link this note's own `[[name]]` made (`origin == "wiki"`) whose target no
    name in the text resolves to any more. A link made any other way is never
    touched here.
    """
    unresolved = []
    named: set[int] = set()
    for name in wiki_link_targets(entry.content):
        target = find_by_wiki_name(session, name)
        if target is None or target.id == entry.id:
            if target is None:
                unresolved.append(name)
            continue
        named.add(target.id)
        create_link(session, entry, target, origin="wiki")
    stale = session.scalars(
        select(EntryLink).where(
            EntryLink.source_entry_id == entry.id,
            EntryLink.origin == "wiki",
            EntryLink.target_entry_id.not_in(named),
        )
    ).all()
    for link in stale:
        delete_link(session, link)
    return unresolved


def _wiki_name_pattern(name: str) -> re.Pattern:
    """`[[name]]`, `[[name|alias]]` and `[[name#part]]`, any case."""
    return re.compile(r"\[\[\s*" + re.escape(name.strip()) + r"\s*(?=[\]|#])", re.IGNORECASE)


def wiki_holders(session: Session, entry: Entry, name: str) -> list[Entry]:
    """The other notes whose text has `[[name]]` in one of its forms."""
    if not name or len(name) > 120:
        return []
    pattern = _wiki_name_pattern(name)
    rows = session.scalars(
        select(Entry).where(
            Entry.is_deleted == False,  # noqa: E712
            Entry.is_private == False,  # noqa: E712
            Entry.id != entry.id,
            Entry.content.ilike(f"%[[{like_escape(name.strip())}%", escape=LIKE_ESCAPE),
        )
    ).all()
    return [row for row in rows if pattern.search(row.content or "")]


def rewrite_wiki_name(
    session: Session, entry: Entry, old: str, new: str, saved: list[dict] | None = None
) -> int:
    """Rewrite `[[old]]` as `[[new]]` in every note that names it (GRAPH_PLAN
    518: a renamed note offers this). Each note keeps its alias and part, gets
    a revision first so it can be undone from its history, and is synced so
    its links point where the names now do. Returns how many notes changed.

    `saved`, when given, gets `{"id", "revision_id"}` for each note changed:
    the version each held before, which is how Undo puts the old name back
    (`POST /entries/{id}/history/{revision_id}/restore`, INBOX 898)."""
    pattern = _wiki_name_pattern(old)
    changed = 0
    for holder in wiki_holders(session, entry, old):
        revision = record_revision(session, holder)
        if saved is not None:
            saved.append({"id": holder.id, "revision_id": revision.id})
        update_entry(session, holder, content=pattern.sub(lambda _m: f"[[{new.strip()}", holder.content))
        sync_wiki_links(session, holder)
        changed += 1
    if changed:
        log_action(session, "edited", "entry", entry.id, f"renamed [[{old}]] in {changed} notes")
    session.commit()
    return changed


# ROADMAP.md's onboarding item: "seeded example notes so the graph, timeline
# and dashboard have something to show before the first note exists". Content
# is deliberately about the app itself, a first-run tour that also
# demonstrates linking and categories, rather than generic placeholder text.
#: Each note's content deliberately opens with its own name verbatim, 
#: `find_by_wiki_name` resolves a [[link]] by matching the *start* of
#: another note's content (there's no separate title field), so this is
#: what makes the two real [[links]] below actually resolve.
_EXAMPLE_NOTES = [
    (
        "About Tessellate",
        ["welcome"],
        "Local-first, always: Tessellate keeps everything on this machine, "
        "notes, search, even the AI, if you point it at a local model. "
        "Nothing is sent anywhere unless you explicitly turn on web search.",
        9,
    ),
    (
        "About Tessellate",
        ["welcome", "graph"],
        "Linking notes together: type [[Local-first, always]] and it "
        "becomes a real link, click it, or see it drawn on the Graph tab. "
        "That's how a notebook here becomes a map instead of a pile.",
        7,
    ),
    (
        "About Tessellate",
        ["welcome", "ai"],
        "Try asking a question: open the Ask tab and try something like "
        "\"what's in my notebook about being local-first?\" The answer will "
        "point back to [[Local-first, always]] and show its reasoning.",
        5,
    ),
    (
        "Personal",
        ["example"],
        "A running shopping list: not every note has to be deep, jot down "
        "a shopping list, a name you don't want to forget, a link to read "
        "later. This one just fills out a second category and a different "
        "day on the Timeline.",
        3,
    ),
    (
        "About Tessellate",
        ["welcome"],
        "Delete these whenever: these five notes are just here so the "
        "Graph, Timeline and Dashboard have something to show on a "
        "brand-new notebook. Filter the Library by the welcome tag and "
        "delete them any time, nothing about them is special.",
        1,
    ),
]


def seed_example_notes(session: Session) -> int:
    """Create the starter notes above, oldest first so each [[link]] resolves
    against a target that already exists (`sync_wiki_links` only ever adds,
    never fails a save on an unresolved name, but an unresolved name here
    would just be a missed demonstration, not a bug).

    Refuses silently (returns 0) on a notebook that already has any note, 
    seeding is an onboarding offer, never something that could land on top of
    real work if this were ever called twice.
    """
    if session.scalar(select(func.count(Entry.id))) or 0:
        return 0
    now = utcnow()
    for category_name, tags, content, days_ago in _EXAMPLE_NOTES:
        entry = create_entry(
            session, content=content, category_name=category_name, tags=tags
        )
        entry.created_at = now - timedelta(days=days_ago)
        entry.updated_at = entry.created_at
        session.commit()
        sync_wiki_links(session, entry)
        session.commit()
    return len(_EXAMPLE_NOTES)


# --- edit history ------------------------------------------------------------
# The recycle bin covers deletion. Nothing covered editing, so rewriting a note
# destroyed what it used to say with no way back, and the AI can rewrite notes
# too, which makes an undo more than a nicety.

# Per note. Enough to walk back a bad session, few enough that a note edited
# hundreds of times doesn't quietly become the largest thing in the database.
MAX_REVISIONS = 20


@events.writes("entry", "revised")
def record_revision(session: Session, entry: Entry):  # noqa: ANN201
    """Save the note as it is now, before it's changed. Returns the revision.

    Private notes store their ciphertext, which is what's in the column, a
    revision must never be the one place a private note sits in the clear.
    """

    revision = EntryRevision(
        entry_id=entry.id, content=entry.content, tags=entry.tags or "[]"
    )
    session.add(revision)
    session.flush()
    # The snapshot is the state *before* whatever the caller is about to do,
    # so the payload says `before`, not `after`: applying it during a replay
    # would undo the very edit this row was written to protect.
    log_action(
        session,
        "revised",
        "entry",
        entry.id,
        f"version {revision.id}",
        payload={"before": {"content": entry.content, "tags": tags_from_json(entry.tags)}},
    )

    stale = list(
        session.scalars(
            select(EntryRevision)
            .where(EntryRevision.entry_id == entry.id)
            .order_by(EntryRevision.id.desc())
            .offset(MAX_REVISIONS)
        )
    )
    for old_revision in stale:
        session.delete(old_revision)
    return revision


def revisions_for(session: Session, entry: Entry) -> list:
    """This note's past versions, newest first."""

    return list(
        session.scalars(
            select(EntryRevision)
            .where(EntryRevision.entry_id == entry.id)
            .order_by(EntryRevision.id.desc())
        )
    )
