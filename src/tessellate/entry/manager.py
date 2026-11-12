"""Create/read/update/soft-delete entries, links, and audit logging.

Deliberately AI-free: the API layer decides the category (by asking the
janitor) and this module just stores what it's told. That
keeps capture working even when every AI piece is down (plan §4).
"""

from __future__ import annotations

from tessellate.entry.manager_text import content_for_entry, flag_private_media, readable_content

import importlib
import json
import logging
import re
from datetime import datetime

from sqlalchemy import delete, func, or_, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


from tessellate.core.database import (
    Category,
    Entry,
    DocumentLink,
    EntryDate,
    EntryLink,
    EntryProperty,
    EntryRevision,
    utcnow,
)
from tessellate.core import events
from tessellate.entry import timewords
from tessellate.entry.cleantext import clean_name, name_key
from tessellate.entry.tagnames import normalise_tags

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
                    until=datetime.combine(mention.until, datetime.min.time()) if mention.until else None,
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
